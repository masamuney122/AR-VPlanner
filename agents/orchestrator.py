"""
Ajan Orkestratörü
Tüm ajanları koordine eder: Retriever → Optimizer → Verifier → Explainer
RAG bilgi tabanı ile zenginleştirilmiş ve doğrulanmış itinerary oluşturma akışı
"""
from typing import Dict, Any
from models.data_models import UserPreferences, Itinerary
from agents.retriever_agent import RetrieverAgent
from agents.optimizer_agent import OptimizerAgent
from agents.verifier_agent import VerifierAgent
from agents.explainer_agent import ExplainerAgent


class AgentOrchestrator:
    """Ajan Orkestratörü - RAG destekli ve doğrulanmış itinerary oluşturma akışı"""

    def __init__(self):
        self.retriever = RetrieverAgent()
        self.optimizer = OptimizerAgent()
        self.verifier = VerifierAgent()
        self.explainer = ExplainerAgent()

    def generate_itinerary(self, user_preferences: UserPreferences) -> Dict[str, Any]:
        """
        Tam bir itinerary (günlük rota planı) oluştur.

        Akış: Retriever (Google API + RAG) → Optimizer → Verifier (RAG) → Explainer (RAG context)
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
            # ─── ADIM 1: Veri Toplama (Google API + RAG) ───
            print(f"\n📌 ADIM 1/4: Veri toplama ({city})...")

            places_data = self.retriever.fetch_city_places(city, user_preferences.interests)
            attractions = places_data.get('attractions', [])
            restaurants = places_data.get('restaurants', [])

            if not attractions:
                return {
                    "success": False,
                    "message": f"{city} için turistik yer bulunamadı. Google API key'i kontrol edin.",
                }

            budget_per_night = (user_preferences.budget * 0.35) / max(total_days, 1)
            hotels = self.retriever.fetch_hotels(city, budget_per_night)

            rag_context = self.retriever.search_knowledge_base(
                city, user_preferences.interests
            )

            print(f"✅ ADIM 1 TAMAMLANDI: {len(attractions)} yer, {len(restaurants)} restoran, {len(hotels)} otel, {len(rag_context)} RAG paragraf")

            # ─── ADIM 2: Optimizasyon & Rota ───
            print(f"\n📌 ADIM 2/4: Rota optimizasyonu...")

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

            # ─── ADIM 3: Doğrulama (RAG çapraz kontrol) ───
            print(f"\n📌 ADIM 3/4: RAG doğrulama...")

            verification_response = self.verifier.verify_itinerary(
                itinerary, rag_context
            )
            if verification_response.success:
                itinerary = verification_response.data
                meta = verification_response.metadata
                verified_count = meta.get("verified_count", 0)
                total_places = meta.get("total_places", 0)
                overall_score = meta.get("overall_score", 0)
                print(
                    f"✅ ADIM 3 TAMAMLANDI: {verified_count}/{total_places} yer doğrulandı "
                    f"(skor: {overall_score:.2f})"
                )
            else:
                print(f"⚠ Doğrulama atlandı: {verification_response.message}")

            # ─── ADIM 4: Açıklama (RAG context ile) ───
            print(f"\n📌 ADIM 4/4: Açıklama üretiliyor (RAG destekli)...")

            explanation = self.explainer.generate_itinerary_explanation(
                itinerary, rag_context=rag_context
            )
            itinerary.explanation = explanation

            print(f"✅ ADIM 4 TAMAMLANDI")

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
