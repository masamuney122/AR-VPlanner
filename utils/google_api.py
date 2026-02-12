"""
Google Places & Maps API Wrapper
Turistik yer, otel, restoran arama ve rota hesaplama
"""
import os
import requests
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
from utils.config import config

# .env'yi bir kez daha garanti olarak yükle
_env_file = Path(__file__).resolve().parent.parent / '.env'
if _env_file.exists():
    load_dotenv(dotenv_path=_env_file, override=True)


class GoogleAPI:
    """Google Places + Maps API entegrasyonu"""
    
    PLACES_BASE = "https://maps.googleapis.com/maps/api/place"
    DIRECTIONS_BASE = "https://maps.googleapis.com/maps/api/directions/json"
    GEOCODE_BASE = "https://maps.googleapis.com/maps/api/geocode/json"
    
    # Fiyat seviyesi → tahmini TL maliyet eşleştirmesi
    PRICE_ESTIMATES = {
        # Turistik yerler (giriş ücreti)
        'attraction': {0: 0, 1: 50, 2: 150, 3: 250, 4: 400},
        # Restoranlar (kişi başı)
        'restaurant': {0: 50, 1: 100, 2: 200, 3: 350, 4: 500},
        # Oteller (gecelik)
        'lodging': {0: 300, 1: 500, 2: 1000, 3: 2000, 4: 4000},
    }
    
    # Kategori → tahmini ziyaret süresi (dakika)
    DURATION_ESTIMATES = {
        'tourist_attraction': 90,
        'museum': 120,
        'park': 60,
        'mosque': 45,
        'church': 40,
        'art_gallery': 75,
        'amusement_park': 240,
        'zoo': 180,
        'aquarium': 120,
        'shopping_mall': 120,
        'restaurant': 75,
        'cafe': 45,
        'bar': 60,
        'lodging': 0,
        'default': 60,
    }
    
    def __init__(self):
        # Birden fazla yoldan key'i bulmaya çalış
        self.api_key = (
            os.getenv('GOOGLE_API_KEY', '') or 
            config.get('api.google_api_key', '') or
            self._read_key_from_env_file()
        )
        self.timeout = config.get('api.timeout', 30)
        
        if not self.api_key:
            print("⚠ GOOGLE_API_KEY bulunamadı! .env dosyasına ekleyin.")
        else:
            print(f"✅ Google API key yüklendi ({self.api_key[:8]}...)")
    
    @staticmethod
    def _read_key_from_env_file() -> str:
        """Son çare: .env dosyasını doğrudan oku"""
        try:
            env_path = Path(__file__).resolve().parent.parent / '.env'
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('GOOGLE_API_KEY=') and not line.startswith('#'):
                            key = line.split('=', 1)[1].strip()
                            if key:
                                print(f"✓ API key .env dosyasından doğrudan okundu")
                                return key
        except Exception as e:
            print(f"⚠ .env dosyası okunamadı: {e}")
        return ''
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    # =========================================================
    # Geocoding
    # =========================================================
    
    def geocode(self, city: str) -> Optional[Dict[str, float]]:
        """Şehir adından koordinat al (Geocoding API → Text Search fallback)"""
        if not self.is_available:
            return None
        
        # 1. Geocoding API dene
        try:
            params = {
                'address': f"{city}, Turkey",
                'key': self.api_key,
                'language': 'tr'
            }
            resp = requests.get(self.GEOCODE_BASE, params=params, timeout=self.timeout)
            data = resp.json()
            
            if data.get('status') == 'OK' and data.get('results'):
                loc = data['results'][0]['geometry']['location']
                print(f"✓ Geocoding API ile konum bulundu: {city}")
                return {'lat': loc['lat'], 'lng': loc['lng']}
            else:
                print(f"⚠ Geocoding API: {data.get('status')} - {data.get('error_message', 'bilinmeyen hata')}")
        except Exception as e:
            print(f"⚠ Geocoding API hatası: {e}")
        
        # 2. Fallback: Places Text Search ile koordinat bul
        try:
            print(f"🔄 Text Search ile konum aranıyor: {city}")
            url = f"{self.PLACES_BASE}/textsearch/json"
            params = {
                'query': f"{city} Turkey",
                'key': self.api_key,
                'language': 'tr'
            }
            resp = requests.get(url, params=params, timeout=self.timeout)
            data = resp.json()
            
            if data.get('status') == 'OK' and data.get('results'):
                loc = data['results'][0]['geometry']['location']
                print(f"✓ Text Search ile konum bulundu: {city}")
                return {'lat': loc['lat'], 'lng': loc['lng']}
            else:
                print(f"⚠ Text Search: {data.get('status')} - {data.get('error_message', '')}")
        except Exception as e:
            print(f"⚠ Text Search hatası: {e}")
        
        # 3. Son fallback: Hardcoded Türkiye şehirleri
        fallback = {
            'istanbul': {'lat': 41.0082, 'lng': 28.9784},
            'izmir': {'lat': 38.4237, 'lng': 27.1428},
            'ankara': {'lat': 39.9334, 'lng': 32.8597},
            'antalya': {'lat': 36.8969, 'lng': 30.7133},
            'kapadokya': {'lat': 38.6431, 'lng': 34.8286},
            'bodrum': {'lat': 37.0345, 'lng': 27.4305},
            'fethiye': {'lat': 36.6221, 'lng': 29.1164},
            'marmaris': {'lat': 36.8547, 'lng': 28.2739},
            'trabzon': {'lat': 41.0015, 'lng': 39.7178},
            'bursa': {'lat': 40.1826, 'lng': 29.0665},
            'konya': {'lat': 37.8746, 'lng': 32.4932},
        }
        
        city_lower = city.lower().replace('İ', 'i').replace('ı', 'i')
        for key, coords in fallback.items():
            if key in city_lower or city_lower in key:
                print(f"✓ Fallback koordinat kullanılıyor: {city} → {key}")
                return coords
        
        return None
    
    # =========================================================
    # Google Places - Nearby Search
    # =========================================================
    
    def search_places(
        self, 
        lat: float, lng: float, 
        place_type: str = 'tourist_attraction',
        radius: int = 5000,
        keyword: str = '',
        max_results: int = 20
    ) -> List[Dict]:
        """
        Belirli koordinat çevresinde yer ara
        
        place_type: tourist_attraction, museum, restaurant, lodging, park, cafe, etc.
        """
        if not self.is_available:
            return []
        
        places = []
        url = f"{self.PLACES_BASE}/nearbysearch/json"
        
        params = {
            'location': f"{lat},{lng}",
            'radius': radius,
            'type': place_type,
            'key': self.api_key,
            'language': 'tr'
        }
        if keyword:
            params['keyword'] = keyword
        
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            data = resp.json()
            
            if data.get('status') == 'OK':
                for item in data.get('results', [])[:max_results]:
                    place = self._parse_place(item, place_type)
                    if place:
                        places.append(place)
            else:
                print(f"⚠ Places API: {data.get('status')} - {data.get('error_message', '')}")
        
        except Exception as e:
            print(f"❌ Places search hatası: {e}")
        
        return places
    
    def search_text(self, query: str, max_results: int = 10) -> List[Dict]:
        """Metin bazlı yer araması"""
        if not self.is_available:
            return []
        
        url = f"{self.PLACES_BASE}/textsearch/json"
        params = {
            'query': query,
            'key': self.api_key,
            'language': 'tr'
        }
        
        places = []
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            data = resp.json()
            
            if data.get('status') == 'OK':
                for item in data.get('results', [])[:max_results]:
                    place = self._parse_place(item, 'tourist_attraction')
                    if place:
                        places.append(place)
        except Exception as e:
            print(f"❌ Text search hatası: {e}")
        
        return places
    
    def get_place_details(self, place_id: str) -> Optional[Dict]:
        """Place ID ile detaylı bilgi al"""
        if not self.is_available:
            return None
        
        url = f"{self.PLACES_BASE}/details/json"
        params = {
            'place_id': place_id,
            'fields': 'name,formatted_address,geometry,rating,price_level,opening_hours,editorial_summary,types,user_ratings_total,photos',
            'key': self.api_key,
            'language': 'tr'
        }
        
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            data = resp.json()
            
            if data.get('status') == 'OK':
                return data.get('result')
        except Exception as e:
            print(f"❌ Place details hatası: {e}")
        
        return None
    
    def _parse_place(self, raw: Dict, category_hint: str = '') -> Optional[Dict]:
        """API sonucunu standart formata çevir"""
        name = raw.get('name', '')
        if not name:
            return None
        
        loc = raw.get('geometry', {}).get('location', {})
        types = raw.get('types', [])
        price_level = raw.get('price_level', 1)
        
        # Kategori belirle
        category = self._determine_category(types, category_hint)
        
        # Tahmini süre
        duration = self.DURATION_ESTIMATES.get(
            category_hint, 
            self.DURATION_ESTIMATES.get('default', 60)
        )
        
        # Tahmini maliyet
        cost_type = 'attraction'
        if category_hint in ('restaurant', 'cafe', 'bar'):
            cost_type = 'restaurant'
        elif category_hint == 'lodging':
            cost_type = 'lodging'
        
        estimated_cost = self.PRICE_ESTIMATES.get(cost_type, {}).get(price_level, 50)
        
        # Fotoğraf referansı
        photos = raw.get('photos', [])
        photo_ref = photos[0].get('photo_reference', '') if photos else ''
        
        # Açıklama
        description = raw.get('editorial_summary', {}).get('overview', '') if isinstance(raw.get('editorial_summary'), dict) else ''
        
        return {
            'name': name,
            'place_id': raw.get('place_id', ''),
            'address': raw.get('vicinity', raw.get('formatted_address', '')),
            'lat': loc.get('lat', 0),
            'lng': loc.get('lng', 0),
            'rating': raw.get('rating', 0),
            'user_ratings_total': raw.get('user_ratings_total', 0),
            'price_level': price_level,
            'category': category,
            'types': types,
            'duration_minutes': duration,
            'estimated_cost': estimated_cost,
            'photo_ref': photo_ref,
            'description': description,
            'opening_hours': raw.get('opening_hours', {}).get('weekday_text', []),
            'is_open': raw.get('opening_hours', {}).get('open_now', None),
        }
    
    def _determine_category(self, types: List[str], hint: str) -> str:
        """Google types → Türkçe kategori"""
        type_map = {
            'museum': 'Müze',
            'mosque': 'Cami',
            'church': 'Kilise',
            'park': 'Park',
            'tourist_attraction': 'Turistik Yer',
            'art_gallery': 'Sanat Galerisi',
            'amusement_park': 'Eğlence Parkı',
            'zoo': 'Hayvanat Bahçesi',
            'aquarium': 'Akvaryum',
            'restaurant': 'Restoran',
            'cafe': 'Kafe',
            'bar': 'Bar',
            'lodging': 'Otel',
            'shopping_mall': 'AVM',
            'night_club': 'Gece Kulübü',
            'spa': 'Spa',
            'stadium': 'Stadyum',
        }
        
        for t in types:
            if t in type_map:
                return type_map[t]
        
        if hint in type_map:
            return type_map[hint]
        
        return 'Turistik Yer'
    
    # =========================================================
    # Google Maps - Directions & Distance
    # =========================================================
    
    def get_directions(
        self,
        origin_lat: float, origin_lng: float,
        dest_lat: float, dest_lng: float,
        mode: str = 'driving'  # driving, walking, transit
    ) -> Optional[Dict]:
        """İki nokta arası yol tarifi ve süre"""
        if not self.is_available:
            return None
        
        params = {
            'origin': f"{origin_lat},{origin_lng}",
            'destination': f"{dest_lat},{dest_lng}",
            'mode': mode,
            'key': self.api_key,
            'language': 'tr'
        }
        
        try:
            resp = requests.get(self.DIRECTIONS_BASE, params=params, timeout=self.timeout)
            data = resp.json()
            
            if data.get('status') == 'OK' and data.get('routes'):
                leg = data['routes'][0]['legs'][0]
                return {
                    'distance_text': leg['distance']['text'],
                    'distance_meters': leg['distance']['value'],
                    'duration_text': leg['duration']['text'],
                    'duration_minutes': leg['duration']['value'] // 60,
                    'mode': mode,
                }
        except Exception as e:
            print(f"❌ Directions hatası: {e}")
        
        return None
    
    def get_distance_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
        mode: str = 'driving'
    ) -> Optional[List[List[Dict]]]:
        """Çoklu nokta arası mesafe matrisi"""
        if not self.is_available:
            return None
        
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        
        origins_str = '|'.join(f"{lat},{lng}" for lat, lng in origins)
        destinations_str = '|'.join(f"{lat},{lng}" for lat, lng in destinations)
        
        params = {
            'origins': origins_str,
            'destinations': destinations_str,
            'mode': mode,
            'key': self.api_key,
            'language': 'tr'
        }
        
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            data = resp.json()
            
            if data.get('status') == 'OK':
                matrix = []
                for row in data.get('rows', []):
                    row_data = []
                    for elem in row.get('elements', []):
                        if elem.get('status') == 'OK':
                            row_data.append({
                                'distance_text': elem['distance']['text'],
                                'distance_meters': elem['distance']['value'],
                                'duration_text': elem['duration']['text'],
                                'duration_minutes': elem['duration']['value'] // 60,
                            })
                        else:
                            row_data.append(None)
                    matrix.append(row_data)
                return matrix
        except Exception as e:
            print(f"❌ Distance matrix hatası: {e}")
        
        return None
    
    def get_photo_url(self, photo_ref: str, max_width: int = 400) -> str:
        """Fotoğraf URL'i oluştur"""
        if not photo_ref or not self.is_available:
            return ''
        return (
            f"{self.PLACES_BASE}/photo"
            f"?maxwidth={max_width}"
            f"&photo_reference={photo_ref}"
            f"&key={self.api_key}"
        )


# Global instance
google_api = GoogleAPI()
