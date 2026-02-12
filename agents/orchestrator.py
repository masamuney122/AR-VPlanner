"""
Ajan Orkestratörü
Tüm ajanları koordine eder: Retriever → Optimizer → Explainer
Itinerary (günlük rota planı) oluşturma akışı
"""
from typing import Dict, Any
from models.data_models import UserPreferences, Itinerary, AgentResponse
from models.message_models import MessageType
from agents.retriever_agent import RetrieverAgent
from agents.optimizer_agent import OptimizerAgent
from agents.explainer_agent import ExplainerAgent
from utils.message_bus import message_bus
from utils.workflow_manager import workflow_manager


class AgentOrchestrator:
    """Ajan Orkestratörü - Itinerary oluşturma akışı"""
    
    def __init__(self):
        self.retriever = RetrieverAgent()
        self.optimizer = OptimizerAgent()
        self.explainer = ExplainerAgent()
    
    def generate_itinerary(self, user_preferences: UserPreferences) -> Dict[str, Any]:
        """
        Tam bir itinerary (günlük rota planı) oluştur.
        
        Akış: Retriever → Optimizer → Explainer
        """
        city = user_preferences.location
        total_days = (user_preferences.end_date - user_preferences.start_date).days
        if total_days <= 0:
            total_days = 1
        
        print(f"\n{'='*60}")
        print(f"🗺️ İTİNERARY OLUŞTURMA BAŞLADI")
        print(f"   Şehir: {city}")
        print(f"   Tarih: {user_preferences.start_date.strftime('%d/%m/%Y')} - {user_preferences.end_date.strftime('%d/%m/%Y')} ({total_days} gün)")
        print(f"   Bütçe: {user_preferences.budget:.0f} TL")
        print(f"   İlgi: {', '.join(user_preferences.interests)}")
        print(f"{'='*60}")
        
        try:
            # ─── ADIM 1: Veri Toplama ───
            print(f"\n📌 ADIM 1/3: Veri toplama ({city})...")
            
            # Turistik yerler ve restoranlar
            places_data = self.retriever.fetch_city_places(city, user_preferences.interests)
            attractions = places_data.get('attractions', [])
            restaurants = places_data.get('restaurants', [])
            
            if not attractions:
                return {
                    "success": False,
                    "message": f"{city} için turistik yer bulunamadı. Google API key'i kontrol edin.",
                }
            
            # Oteller - gecelik bütçe tahmini (toplam bütçenin %30-40'ı / gece sayısı)
            budget_per_night = (user_preferences.budget * 0.35) / max(total_days, 1)
            hotels = self.retriever.fetch_hotels(city, budget_per_night)
            
            print(f"✅ ADIM 1 TAMAMLANDI: {len(attractions)} yer, {len(restaurants)} restoran, {len(hotels)} otel")
            
            # ─── ADIM 2: Optimizasyon & Rota ───
            print(f"\n📌 ADIM 2/3: Rota optimizasyonu...")
            
            optimizer_response = self.optimizer.create_itinerary(
                city=city,
                attractions=attractions,
                restaurants=restaurants,
                hotels=hotels,
                user_prefs=user_preferences
            )
            
            if not optimizer_response.success:
                return {
                    "success": False,
                    "message": f"Optimizasyon hatası: {optimizer_response.message}",
                }
            
            itinerary: Itinerary = optimizer_response.data
            print(f"✅ ADIM 2 TAMAMLANDI")
            
            # ─── ADIM 3: Açıklama ───
            print(f"\n📌 ADIM 3/3: Açıklama üretiliyor...")
            
            explanation = self.explainer.generate_itinerary_explanation(itinerary)
            itinerary.explanation = explanation
            
            print(f"✅ ADIM 3 TAMAMLANDI")
            
            print(f"\n{'='*60}")
            print(f"🎉 İTİNERARY OLUŞTURMA TAMAMLANDI!")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "itinerary": itinerary,
                "message": f"{city} için {total_days} günlük plan hazır!"
            }
        
        except Exception as e:
            import traceback
            print(f"❌ Orchestrator hatası: {e}")
            print(traceback.format_exc())
            return {
                "success": False,
                "message": f"Hata: {str(e)}"
            }
    
    # Eski uyumluluk
    def generate_plan(self, user_preferences: UserPreferences) -> Dict[str, Any]:
        """Eski arayüz - generate_itinerary'ye yönlendir"""
        return self.generate_itinerary(user_preferences)
