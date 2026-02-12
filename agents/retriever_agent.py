"""
Erişim Ajanı (Retriever Agent)
Google Places API ile yer, otel, restoran verileri çeker
Otel fiyatları LLM tarafından konum bazlı tahmin edilir
"""
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from models.data_models import Place, Accommodation, Evidence, AgentResponse, UserPreferences
from models.message_models import MessageType
from utils.google_api import google_api
from utils.config import config
from utils.message_bus import message_bus
from datetime import datetime, timedelta
import json
import re


class RetrieverAgent:
    """Erişim Ajanı - Google Places API ile veri toplama"""
    
    def __init__(self):
        self.agent_name = "retriever"
        self.data_sources = config.get('data_sources', [])
        self.cache = {}
        self.cache_ttl = timedelta(hours=24)
        
        if google_api.is_available:
            print(f"🗺️ Google Places + Maps API modu aktif")
        else:
            print(f"⚠ Google API key bulunamadı!")
        
        self._register_message_handler()
    
    def _register_message_handler(self):
        message_bus.subscribe(self.agent_name, self._handle_message)
    
    def _handle_message(self, message):
        if message.message_type == MessageType.REQUEST:
            pass
    
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
        
        # Geocode
        coords = google_api.geocode(city)
        if not coords:
            print(f"❌ {city} için koordinat bulunamadı")
            return {'attractions': [], 'restaurants': []}
        
        lat, lng = coords['lat'], coords['lng']
        print(f"✓ {city} koordinatları: {lat}, {lng}")
        
        # 1. Turistik yerler
        print(f"🏛️ {city} turistik yerler aranıyor...")
        attractions = []
        
        # Ana turistik yerler
        raw_attractions = google_api.search_places(lat, lng, 'tourist_attraction', radius=8000, max_results=15)
        attractions.extend(raw_attractions)
        
        # İlgi alanlarına göre ek aramalar
        interest_types = {
            'kültür': [('museum', 'müze'), ('art_gallery', 'sanat')],
            'tarih': [('museum', 'tarihi'), ('mosque', 'tarihi cami')],
            'doğa': [('park', 'park')],
            'deniz': [],  # tourist_attraction + keyword ile
            'plaj': [],
            'yemek': [],  # restoran olarak ele alınacak
            'macera': [('amusement_park', '')],
            'alışveriş': [('shopping_mall', '')],
        }
        
        for interest in interests:
            interest_lower = interest.lower()
            if interest_lower in interest_types:
                for place_type, keyword in interest_types[interest_lower]:
                    extra = google_api.search_places(lat, lng, place_type, radius=8000, keyword=keyword, max_results=8)
                    attractions.extend(extra)
        
        # Tekrar edenleri kaldır
        attractions = self._deduplicate_places(attractions)
        
        # 2. Restoranlar
        print(f"🍽️ {city} restoranlar aranıyor...")
        restaurants = google_api.search_places(lat, lng, 'restaurant', radius=5000, max_results=10)
        restaurants = self._deduplicate_places(restaurants)
        
        # Place nesnelerine dönüştür
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
        
        # LLM ile fiyat tahmini al
        print(f"🤖 LLM ile otel fiyatları tahmin ediliyor...")
        llm_prices = self._estimate_hotel_prices_with_llm(city, raw_hotels)
        
        # Accommodation nesnelerine dönüştür
        hotels = []
        for i, h in enumerate(raw_hotels):
            # LLM fiyatı varsa kullan, yoksa price_level'a göre fallback
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
        
        # Bütçeye uygun olanları filtrele (tolerans %30)
        affordable = [h for h in hotels if h.price_per_night <= budget_per_night * 1.3]
        if not affordable:
            # Hiçbiri uygun değilse en ucuz 3'ünü al
            hotels.sort(key=lambda x: x.price_per_night)
            affordable = hotels[:3]
        
        # Rating'e göre sırala
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
            
            # Otel listesini oluştur
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
                    max_tokens=100,  # Kısa yanıt - sadece sayı listesi
                    temperature=0.3  # Düşük sıcaklık - tutarlı fiyatlar
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
            # Metinde JSON dizisi bul
            match = re.search(r'\[[\d\s,\.]+\]', text)
            if match:
                prices = json.loads(match.group())
                # Geçerlilik kontrolü
                valid = []
                for p in prices:
                    p = float(p)
                    if 100 <= p <= 50000:  # Mantıklı aralık
                        valid.append(p)
                    else:
                        valid.append(None)
                return valid if len(valid) >= expected_count else None
            
            # JSON bulunamazsa, satır satır sayı ara
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
        # Şehre göre baz fiyat çarpanı
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
    # Evidence oluşturma (eski uyumluluk)
    # =========================================================
    
    def retrieve_evidence(self, query: str, user_preferences: UserPreferences, top_k: int = 15) -> AgentResponse:
        """Eski arayüz uyumluluğu - evidence olarak dön"""
        try:
            message_bus.send_message(
                sender=self.agent_name,
                receiver="broadcast",
                message_type=MessageType.STATUS_UPDATE,
                content={"event": "retrieval_started", "location": user_preferences.location}
            )
            
            city = user_preferences.location
            data = self.fetch_city_places(city, user_preferences.interests)
            
            evidence_list = []
            for place in data.get('attractions', [])[:top_k]:
                evidence_list.append(Evidence(
                    content=f"{place.name}: {place.description or place.category}",
                    source=f"Google Places - {place.category}",
                    relevance_score=place.rating / 5.0 if place.rating else 0.5,
                    metadata={
                        'name': place.name,
                        'place_id': place.place_id,
                        'category': place.category,
                        'lat': place.lat,
                        'lng': place.lng,
                        'cost': place.estimated_cost,
                        'duration': place.duration_minutes,
                    }
                ))
            
            message_bus.send_message(
                sender=self.agent_name,
                receiver="broadcast",
                message_type=MessageType.NOTIFICATION,
                content={"event": "retrieval_completed", "evidence_count": len(evidence_list)}
            )
            
            return AgentResponse(
                success=True,
                data=evidence_list,
                message=f"{len(evidence_list)} yer bulundu (Google Places)",
                metadata={"location": city, "total_found": len(evidence_list)}
            )
        
        except Exception as e:
            return AgentResponse(
                success=False, data=[], 
                message=f"Hata: {str(e)}", metadata={"error": str(e)}
            )
    
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
