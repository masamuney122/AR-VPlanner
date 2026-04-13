"""
Optimizasyon Ajanı (Optimizer Agent)
Günlük rota planı oluşturur, bütçe hesaplar, ulaşım sürelerini ekler
"""
from typing import List, Dict, Any, Optional
from models.data_models import (
    Place, Accommodation, DayPlan, TransportLeg,
    BudgetBreakdown, Itinerary, AgentResponse, UserPreferences
)
from utils.google_api import google_api
from utils.config import config
from datetime import datetime, timedelta
import math


class OptimizerAgent:
    """Optimizasyon Ajanı - Günlük rota ve bütçe optimizasyonu"""
    
    def __init__(self):
        self.max_activities_per_day = config.get('itinerary.max_activities_per_day', 5)
        self.daily_start_hour = config.get('itinerary.daily_start_hour', 9)
        self.daily_end_hour = config.get('itinerary.daily_end_hour', 21)
        self.meal_budget_per_day = config.get('itinerary.meal_budget_per_day', 300)
        self.transport_budget_per_day = config.get('itinerary.transport_budget_per_day', 100)
        self.buffer_percentage = config.get('itinerary.buffer_percentage', 10)

    def create_itinerary(
        self,
        city: str,
        attractions: List[Place],
        restaurants: List[Place],
        hotels: List[Accommodation],
        user_prefs: UserPreferences
    ) -> AgentResponse:
        """
        Tam bir itinerary (günlük rota planı) oluştur.
        
        1. Bütçeye uygun otel seç
        2. Günlere etkinlik dağıt
        3. Yerler arası ulaşım sürelerini hesapla
        4. Bütçe dağılımını çıkar
        """
        try:
            total_days = (user_prefs.end_date - user_prefs.start_date).days
            if total_days <= 0:
                total_days = 1
            
            total_budget = user_prefs.budget
            
            print(f"\n{'='*50}")
            print(f"📐 İTİNERARY OPTİMİZASYONU")
            print(f"   Şehir: {city}")
            print(f"   Gün: {total_days}")
            print(f"   Bütçe: {total_budget:.0f} TL")
            print(f"   Turistik yer: {len(attractions)}")
            print(f"   Restoran: {len(restaurants)}")
            print(f"   Otel: {len(hotels)}")
            print(f"{'='*50}")
            
            # 1. Konaklama seç
            print(f"\n🏨 Konaklama seçiliyor...")
            accommodation = self._select_accommodation(hotels, total_days, total_budget)
            accommodation_cost = accommodation.total_cost if accommodation else 0
            
            # 2. Kalan bütçeyi hesapla
            remaining_after_hotel = total_budget - accommodation_cost
            daily_meal = self.meal_budget_per_day
            daily_transport = self.transport_budget_per_day
            total_meal = daily_meal * total_days
            total_transport = daily_transport * total_days
            buffer = total_budget * (self.buffer_percentage / 100)
            
            activity_budget = remaining_after_hotel - total_meal - total_transport - buffer
            if activity_budget < 0:
                activity_budget = remaining_after_hotel * 0.3  # En az %30'u etkinliklere
            
            print(f"   Konaklama: {accommodation_cost:.0f} TL")
            print(f"   Yemek tahmini: {total_meal:.0f} TL")
            print(f"   Ulaşım tahmini: {total_transport:.0f} TL")
            print(f"   Etkinlik bütçesi: {activity_budget:.0f} TL")
            
            # 3. Bütçeye uygun etkinlikleri seç ve sırala
            print(f"\n🎯 Etkinlikler seçiliyor...")
            selected_attractions = self._select_attractions(
                attractions, activity_budget, total_days
            )
            
            # 4. Günlere dağıt
            print(f"\n📅 Günlere dağıtılıyor...")
            days = self._distribute_to_days(
                selected_attractions, restaurants, total_days, user_prefs
            )
            
            # 5. Ulaşım sürelerini hesapla
            print(f"\n🚗 Ulaşım süreleri hesaplanıyor...")
            days = self._add_transport_legs(days, accommodation)
            
            # 6. Bütçe dağılımı
            total_activities_cost = sum(d.activities_cost for d in days)
            total_transport_cost = sum(d.transport_cost for d in days)
            total_meals_cost = sum(d.meals_cost for d in days)
            extras = total_budget * (self.buffer_percentage / 100)
            grand_total = accommodation_cost + total_activities_cost + total_meals_cost + total_transport_cost + extras
            
            budget = BudgetBreakdown(
                accommodation=accommodation_cost,
                activities=total_activities_cost,
                food=total_meals_cost,
                transport=total_transport_cost,
                extras=extras,
                total=grand_total,
                remaining=total_budget - grand_total,
                user_budget=total_budget
            )
            
            # Optimizasyon skoru
            opt_score = self._calculate_score(days, budget, user_prefs)
            
            itinerary = Itinerary(
                city=city,
                days=days,
                accommodation=accommodation,
                budget=budget,
                total_days=total_days,
                optimization_score=opt_score
            )
            
            print(f"\n✅ Itinerary oluşturuldu!")
            print(f"   Toplam maliyet: {grand_total:.0f} TL / {total_budget:.0f} TL bütçe")
            print(f"   Kalan: {total_budget - grand_total:.0f} TL")

            return AgentResponse(
                success=True,
                data=itinerary,
                message=f"Itinerary oluşturuldu: {total_days} gün, {len(selected_attractions)} etkinlik",
                metadata={"total_cost": grand_total, "remaining": total_budget - grand_total}
            )
        
        except Exception as e:
            import traceback
            print(f"❌ Optimizer hatası: {e}")
            print(traceback.format_exc())
            return AgentResponse(
                success=False, data=None,
                message=f"Optimizasyon hatası: {str(e)}", metadata={"error": str(e)}
            )
    
    # =========================================================
    # Konaklama Seçimi
    # =========================================================
    
    def _select_accommodation(
        self, hotels: List[Accommodation], nights: int, total_budget: float
    ) -> Optional[Accommodation]:
        """Bütçeye uygun en iyi oteli seç"""
        if not hotels:
            return None
        
        # Bütçenin max %40'ı konaklamaya
        max_accommodation = total_budget * 0.40
        max_per_night = max_accommodation / max(nights, 1)
        
        candidates = []
        for hotel in hotels:
            if hotel.price_per_night <= max_per_night:
                h = Accommodation(
                    name=hotel.name,
                    place_id=hotel.place_id,
                    address=hotel.address,
                    lat=hotel.lat,
                    lng=hotel.lng,
                    rating=hotel.rating,
                    price_per_night=hotel.price_per_night,
                    total_nights=nights,
                    total_cost=hotel.price_per_night * nights,
                    photo_ref=hotel.photo_ref
                )
                candidates.append(h)
        
        if not candidates:
            # Bütçe sıkıysa en ucuzunu al
            cheapest = min(hotels, key=lambda x: x.price_per_night)
            return Accommodation(
                name=cheapest.name,
                place_id=cheapest.place_id,
                address=cheapest.address,
                lat=cheapest.lat,
                lng=cheapest.lng,
                rating=cheapest.rating,
                price_per_night=cheapest.price_per_night,
                total_nights=nights,
                total_cost=cheapest.price_per_night * nights,
                photo_ref=cheapest.photo_ref
            )
        
        # Rating/fiyat oranına göre en iyisini seç
        candidates.sort(key=lambda x: (x.rating / max(x.price_per_night, 1)), reverse=True)
        selected = candidates[0]
        print(f"   ✓ {selected.name} - {selected.price_per_night:.0f} TL/gece, {selected.rating}⭐")
        return selected
    
    # =========================================================
    # Etkinlik Seçimi
    # =========================================================
    
    def _select_attractions(
        self, attractions: List[Place], budget: float, days: int
    ) -> List[Place]:
        """Bütçeye uygun etkinlikleri seç"""
        # Rating'e göre sırala (en yüksek önce)
        sorted_attr = sorted(attractions, key=lambda x: x.rating, reverse=True)
        
        selected = []
        total_cost = 0
        max_count = days * self.max_activities_per_day
        
        for place in sorted_attr:
            if len(selected) >= max_count:
                break
            if total_cost + place.estimated_cost <= budget:
                selected.append(place)
                total_cost += place.estimated_cost
        
        print(f"   ✓ {len(selected)} etkinlik seçildi (toplam: {total_cost:.0f} TL)")
        return selected
    
    # =========================================================
    # Günlere Dağıtım
    # =========================================================
    
    def _distribute_to_days(
        self, 
        attractions: List[Place], 
        restaurants: List[Place],
        total_days: int,
        user_prefs: UserPreferences
    ) -> List[DayPlan]:
        """Etkinlikleri günlere dengeli şekilde dağıt"""
        days = []
        daily_max_minutes = (self.daily_end_hour - self.daily_start_hour) * 60
        
        # Etkinlikleri günlere dağıt
        attractions_per_day = max(1, len(attractions) // total_days)
        
        start_date = user_prefs.start_date
        attraction_idx = 0
        restaurant_idx = 0
        
        for day_num in range(1, total_days + 1):
            day_date = start_date + timedelta(days=day_num - 1)
            
            # Bu günün etkinlikleri
            day_places = []
            day_minutes = 0
            
            # Son gün kalan tüm etkinlikleri al
            if day_num == total_days:
                end_idx = len(attractions)
            else:
                end_idx = min(attraction_idx + attractions_per_day, len(attractions))
            
            for i in range(attraction_idx, end_idx):
                place = attractions[i]
                if day_minutes + place.duration_minutes <= daily_max_minutes:
                    day_places.append(place)
                    day_minutes += place.duration_minutes
            
            attraction_idx = end_idx
            
            # Günlük maliyetler
            activities_cost = sum(p.estimated_cost for p in day_places)
            meals_cost = self.meal_budget_per_day
            transport_cost = self.transport_budget_per_day
            
            days.append(DayPlan(
                day_number=day_num,
                date=day_date.strftime('%Y-%m-%d'),
                places=day_places,
                transport_legs=[],
                meals_cost=meals_cost,
                transport_cost=transport_cost,
                activities_cost=activities_cost,
                day_total=activities_cost + meals_cost + transport_cost
            ))
            
            print(f"   Gün {day_num}: {len(day_places)} etkinlik, {activities_cost:.0f} TL")
        
        return days
    
    # =========================================================
    # Ulaşım Hesaplama
    # =========================================================
    
    def _add_transport_legs(
        self, days: List[DayPlan], accommodation: Optional[Accommodation]
    ) -> List[DayPlan]:
        """Her gün için yerler arası ulaşım süreleri ve maliyetleri ekle"""
        for day in days:
            if len(day.places) < 2:
                continue
            
            transport_legs = []
            total_transport_minutes = 0
            
            # Otel → ilk yer (varsa)
            if accommodation and day.places:
                first = day.places[0]
                leg = self._get_transport(
                    accommodation.name, accommodation.lat, accommodation.lng,
                    first.name, first.lat, first.lng
                )
                if leg:
                    transport_legs.append(leg)
                    total_transport_minutes += leg.duration_minutes
            
            # Yerler arası
            for i in range(len(day.places) - 1):
                origin = day.places[i]
                dest = day.places[i + 1]
                leg = self._get_transport(
                    origin.name, origin.lat, origin.lng,
                    dest.name, dest.lat, dest.lng
                )
                if leg:
                    transport_legs.append(leg)
                    total_transport_minutes += leg.duration_minutes
            
            # Son yer → otel (varsa)
            if accommodation and day.places:
                last = day.places[-1]
                leg = self._get_transport(
                    last.name, last.lat, last.lng,
                    accommodation.name, accommodation.lat, accommodation.lng
                )
                if leg:
                    transport_legs.append(leg)
                    total_transport_minutes += leg.duration_minutes
            
            day.transport_legs = transport_legs
            
            # Ulaşım maliyetini güncelle (tahmini: ~15 TL/km taksi)
            total_km = sum(
                leg.duration_minutes * 0.5  # yaklaşık km tahmini
                for leg in transport_legs
            )
            day.transport_cost = max(total_km * 15, self.transport_budget_per_day * 0.5)
            day.day_total = day.activities_cost + day.meals_cost + day.transport_cost
        
        return days
    
    def _get_transport(
        self, 
        origin_name: str, origin_lat: float, origin_lng: float,
        dest_name: str, dest_lat: float, dest_lng: float
    ) -> Optional[TransportLeg]:
        """İki nokta arası ulaşım bilgisi al"""
        # Önce Google Directions dene
        directions = google_api.get_directions(origin_lat, origin_lng, dest_lat, dest_lng)
        
        if directions:
            return TransportLeg(
                origin_name=origin_name,
                destination_name=dest_name,
                distance_text=directions['distance_text'],
                duration_text=directions['duration_text'],
                duration_minutes=directions['duration_minutes'],
                mode='driving'
            )
        
        # Fallback: Haversine mesafe tahmini
        dist_km = self._haversine(origin_lat, origin_lng, dest_lat, dest_lng)
        duration_min = max(int(dist_km * 3), 5)  # Yaklaşık 20 km/h şehir içi
        
        return TransportLeg(
            origin_name=origin_name,
            destination_name=dest_name,
            distance_text=f"{dist_km:.1f} km",
            duration_text=f"{duration_min} dk",
            duration_minutes=duration_min,
            mode='driving'
        )
    
    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """İki koordinat arası mesafe (km)"""
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    
    # =========================================================
    # Skor Hesaplama
    # =========================================================
    
    def _calculate_score(
        self, days: List[DayPlan], budget: BudgetBreakdown, prefs: UserPreferences
    ) -> float:
        """Optimizasyon skoru (0-1)"""
        # Bütçe kullanımı (%80-%100 arası ideal)
        usage = budget.total / budget.user_budget if budget.user_budget > 0 else 0
        budget_score = 1.0 - abs(0.85 - min(usage, 1.0))
        
        # Etkinlik yoğunluğu
        total_activities = sum(len(d.places) for d in days)
        activity_score = min(total_activities / (len(days) * 3), 1.0)
        
        # Rating ortalaması
        all_ratings = [p.rating for d in days for p in d.places if p.rating > 0]
        avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 3.0
        rating_score = avg_rating / 5.0
        
        score = budget_score * 0.3 + activity_score * 0.3 + rating_score * 0.4
        return round(min(max(score, 0), 1), 3)
