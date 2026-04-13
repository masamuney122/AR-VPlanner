"""
Erişim Ajanı (Retriever Agent)
Google Places API ile yer, otel, restoran verileri çeker
FAISS bilgi tabanından RAG ile zengin context sağlar
Otel fiyatları LLM tarafından konum bazlı tahmin edilir
"""
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from models.data_models import Place, Accommodation, Evidence
from utils.google_api import google_api
from utils.vector_store import vector_store
from utils.config import config
from datetime import datetime, timedelta
import json
import re


class RetrieverAgent:
    """Erişim Ajanı - Google Places API + RAG bilgi tabanı"""

    def __init__(self):
        self.data_sources = config.get('data_sources', [])
        self.cache = {}
        self.cache_ttl = timedelta(hours=24)

        if google_api.is_available:
            print(f"🗺️ Google Places + Maps API modu aktif")
        else:
            print(f"⚠ Google API key bulunamadı!")

        if vector_store.is_ready:
            print(f"📚 RAG bilgi tabanı aktif ({len(vector_store.documents)} paragraf)")

    # =========================================================
    # Şehir için yer arama
    # =========================================================

    def fetch_city_places(self, city: str, interests: List[str]) -> Dict[str, List[Place]]:
        """
        Şehir için turistik yerler, restoranlar çek.

        Returns:
            {
                'attractions': [Place, ...],
                'restaurants': [Place, ...],
            }
        """
        cache_key = f"places_{city}_{'_'.join(sorted(interests))}"
        if cache_key in self.cache:
            cached, cached_time = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                print(f"📦 Cache'den yüklendi: {city}")
                return cached

        coords = google_api.geocode(city)
        if not coords:
            print(f"❌ {city} için koordinat bulunamadı")
            return {'attractions': [], 'restaurants': []}

        lat, lng = coords['lat'], coords['lng']
        print(f"✓ {city} koordinatları: {lat}, {lng}")

        print(f"🏛️ {city} turistik yerler aranıyor...")
        attractions = []

        raw_attractions = google_api.search_places(lat, lng, 'tourist_attraction', radius=8000, max_results=15)
        attractions.extend(raw_attractions)

        interest_types = {
            'kültür': [('museum', 'müze'), ('art_gallery', 'sanat')],
            'tarih': [('museum', 'tarihi'), ('mosque', 'tarihi cami')],
            'doğa': [('park', 'park')],
            'deniz': [],
            'plaj': [],
            'yemek': [],
            'macera': [('amusement_park', '')],
            'alışveriş': [('shopping_mall', '')],
        }

        for interest in interests:
            interest_lower = interest.lower()
            if interest_lower in interest_types:
                for place_type, keyword in interest_types[interest_lower]:
                    extra = google_api.search_places(lat, lng, place_type, radius=8000, keyword=keyword, max_results=8)
                    attractions.extend(extra)

        attractions = self._deduplicate_places(attractions)

        print(f"🍽️ {city} restoranlar aranıyor...")
        restaurants = google_api.search_places(lat, lng, 'restaurant', radius=5000, max_results=10)
        restaurants = self._deduplicate_places(restaurants)

        result = {
            'attractions': [self._dict_to_place(p) for p in attractions],
            'restaurants': [self._dict_to_place(p) for p in restaurants],
        }

        self.cache[cache_key] = (result, datetime.now())

        print(f"✅ {city}: {len(result['attractions'])} turistik yer, {len(result['restaurants'])} restoran bulundu")
        return result

    def fetch_hotels(self, city: str, budget_per_night: float) -> List[Accommodation]:
        """
        Şehir için otelleri çek ve LLM ile gerçekçi fiyat tahmini yap.
        Google Places otel isim/rating/price_level verir,
        LLM bu bilgilere bakarak gecelik TL fiyat tahmin eder.
        """
        cache_key = f"hotels_{city}_{budget_per_night}"
        if cache_key in self.cache:
            cached, cached_time = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                return cached

        coords = google_api.geocode(city)
        if not coords:
            return []

        lat, lng = coords['lat'], coords['lng']

        print(f"🏨 {city} oteller aranıyor...")
        raw_hotels = google_api.search_places(lat, lng, 'lodging', radius=5000, max_results=10)

        if not raw_hotels:
            print(f"⚠ Google'dan otel bulunamadı")
            return []

        print(f"🤖 LLM ile otel fiyatları tahmin ediliyor...")
        llm_prices = self._estimate_hotel_prices_with_llm(city, raw_hotels)

        hotels = []
        for i, h in enumerate(raw_hotels):
            if llm_prices and i < len(llm_prices) and llm_prices[i] is not None:
                price = llm_prices[i]
            else:
                price = self._fallback_price_estimate(h.get('price_level', 2), city)

            hotels.append(Accommodation(
                name=h['name'],
                place_id=h.get('place_id', ''),
                address=h.get('address', ''),
                lat=h.get('lat', 0),
                lng=h.get('lng', 0),
                rating=h.get('rating', 0),
                price_per_night=price,
                total_nights=0,
                total_cost=0,
                photo_ref=h.get('photo_ref', '')
            ))

        affordable = [h for h in hotels if h.price_per_night <= budget_per_night * 1.3]
        if not affordable:
            hotels.sort(key=lambda x: x.price_per_night)
            affordable = hotels[:3]

        affordable.sort(key=lambda x: x.rating, reverse=True)

        self.cache[cache_key] = (affordable, datetime.now())

        for h in affordable:
            print(f"   🏨 {h.name}: {h.price_per_night:.0f} TL/gece ({h.rating}⭐)")
        print(f"✅ {len(affordable)} otel bulundu")
        return affordable

    def _estimate_hotel_prices_with_llm(self, city: str, hotels: List[Dict]) -> Optional[List[float]]:
        """
        LLM'den otel gecelik fiyat tahmini al.
        Tek bir çağrı ile tüm otellerin fiyatını tahmin eder.
        """
        LLM_TIMEOUT = 90

        try:
            from utils.llm_wrapper import llm_wrapper

            if llm_wrapper.model is None:
                return None

            hotel_list = ""
            for i, h in enumerate(hotels, 1):
                name = h.get('name', 'Otel')
                rating = h.get('rating', 0)
                price_level = h.get('price_level', 2)
                address = h.get('address', '')
                hotel_list += f"{i}. {name} (Rating: {rating}/5, Fiyat seviyesi: {price_level}/4, Adres: {address})\n"

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Sen bir otel fiyat uzmanısın. Türkiye'deki otel fiyatlarını iyi biliyorsun. "
                        "Sana verilen otellerin gecelik fiyatını Türk Lirası (TL) olarak tahmin et. "
                        "SADECE bir JSON dizisi döndür, başka hiçbir şey yazma. "
                        "Örnek: [850, 1200, 600]"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"{city} şehrindeki bu otellerin 2025-2026 yılı gecelik fiyatlarını TL olarak tahmin et.\n\n"
                        f"{hotel_list}\n"
                        f"SADECE JSON dizisi döndür, örn: [800, 1500, 450]. Başka bir şey yazma."
                    )
                }
            ]

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    llm_wrapper.chat,
                    messages=messages,
                    max_tokens=100,
                    temperature=0.3
                )
                try:
                    result = future.result(timeout=LLM_TIMEOUT)
                    if result:
                        prices = self._parse_price_json(result, len(hotels))
                        if prices:
                            print(f"🤖 LLM fiyat tahmini başarılı: {prices}")
                            return prices
                except FutureTimeout:
                    print(f"⏳ LLM fiyat tahmini timeout ({LLM_TIMEOUT}s)")

        except Exception as e:
            print(f"⚠ LLM fiyat tahmini hatası: {e}")

        print(f"⚠ LLM fiyat tahmini başarısız, fallback kullanılıyor")
        return None

    def _parse_price_json(self, text: str, expected_count: int) -> Optional[List[float]]:
        """LLM çıktısından fiyat dizisini ayıkla"""
        try:
            match = re.search(r'\[[\d\s,\.]+\]', text)
            if match:
                prices = json.loads(match.group())
                valid = []
                for p in prices:
                    p = float(p)
                    if 100 <= p <= 50000:
                        valid.append(p)
                    else:
                        valid.append(None)
                return valid if len(valid) >= expected_count else None

            numbers = re.findall(r'[\d]+(?:[.,]\d+)?', text)
            if len(numbers) >= expected_count:
                prices = []
                for n in numbers[:expected_count]:
                    p = float(n.replace(',', '.'))
                    prices.append(p if 100 <= p <= 50000 else None)
                return prices

        except Exception as e:
            print(f"Fiyat parse hatası: {e}")

        return None

    def _fallback_price_estimate(self, price_level: int, city: str) -> float:
        """LLM başarısız olursa basit fiyat tahmini"""
        city_multiplier = {
            'istanbul': 1.3,
            'antalya': 1.2,
            'bodrum': 1.5,
            'marmaris': 1.1,
            'fethiye': 1.0,
            'izmir': 1.0,
            'ankara': 0.9,
            'kapadokya': 1.2,
            'trabzon': 0.8,
        }

        multiplier = 1.0
        for key, val in city_multiplier.items():
            if key in city.lower():
                multiplier = val
                break

        base_prices = {0: 400, 1: 700, 2: 1200, 3: 2500, 4: 5000}
        return base_prices.get(price_level, 800) * multiplier

    # =========================================================
    # RAG - Bilgi Tabanı Araması
    # =========================================================

    def search_knowledge_base(self, city: str, interests: List[str], top_k: int = 5) -> List[Evidence]:
        """
        FAISS bilgi tabanından şehir + ilgi alanına göre semantik arama.
        Dönen paragraflar LLM'e context olarak verilir.
        """
        if not vector_store.is_ready:
            return []

        query_parts = [city]
        query_parts.extend(interests)
        query = " ".join(query_parts)

        city_normalized = city.lower().replace("'", "").replace("ı", "i").replace("ş", "s").replace("ç", "c").replace("ö", "o").replace("ü", "u").replace("ğ", "g")

        results = vector_store.search(query, top_k=top_k, city_filter=city_normalized)

        if not results:
            results = vector_store.search(query, top_k=top_k, city_filter=None)

        if results:
            print(f"📚 RAG: {len(results)} alakalı paragraf bulundu ({city})")

        return results

    # =========================================================
    # Yardımcı metodlar
    # =========================================================

    def _deduplicate_places(self, places: List[Dict]) -> List[Dict]:
        """Place ID'ye göre tekrarları kaldır"""
        seen = set()
        unique = []
        for p in places:
            pid = p.get('place_id', p.get('name', ''))
            if pid not in seen:
                seen.add(pid)
                unique.append(p)
        return unique

    def _dict_to_place(self, d: Dict) -> Place:
        """Dict → Place dataclass"""
        return Place(
            name=d.get('name', ''),
            place_id=d.get('place_id', ''),
            address=d.get('address', ''),
            lat=d.get('lat', 0),
            lng=d.get('lng', 0),
            rating=d.get('rating', 0),
            category=d.get('category', 'Turistik Yer'),
            price_level=d.get('price_level', 1),
            description=d.get('description', ''),
            duration_minutes=d.get('duration_minutes', 60),
            estimated_cost=d.get('estimated_cost', 50),
            photo_ref=d.get('photo_ref', ''),
            opening_hours=d.get('opening_hours', []),
            types=d.get('types', []),
            user_ratings_total=d.get('user_ratings_total', 0),
        )
