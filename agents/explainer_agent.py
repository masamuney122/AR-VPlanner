"""
Açıklama Ajanı (Explainer Agent)
Itinerary için insancıl açıklamalar üretir (LLM + fallback)
"""
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from models.data_models import Itinerary, AgentResponse
from models.message_models import MessageType
from utils.message_bus import message_bus


class ExplainerAgent:
    """Açıklama Ajanı - Itinerary açıklamaları"""
    
    LLM_TIMEOUT = 90  # saniye
    
    def __init__(self):
        self.agent_name = "explainer"
        self._register_message_handler()
    
    def _register_message_handler(self):
        message_bus.subscribe(self.agent_name, self._handle_message)
    
    def _handle_message(self, message):
        pass
    
    def generate_itinerary_explanation(self, itinerary: Itinerary) -> str:
        """Itinerary için açıklama üret"""
        # LLM dene, timeout olursa template kullan
        llm_text = self._try_llm_explanation(itinerary)
        if llm_text:
            return llm_text
        return self._template_explanation(itinerary)
    
    def _try_llm_explanation(self, itinerary: Itinerary) -> str:
        """LLM ile insancıl açıklama üret"""
        try:
            from utils.llm_wrapper import llm_wrapper
            
            if llm_wrapper.model is None:
                return None
            
            # Kısa özet oluştur
            place_names = []
            for day in itinerary.days:
                for p in day.places[:2]:
                    place_names.append(p.name)
            
            places_str = ", ".join(place_names[:6])
            budget = itinerary.budget
            
            messages = [
                {
                    "role": "system",
                    "content": "Sen bir seyahat danışmanısın. Samimi, heyecanlı ve kısa açıklamalar yazarsın. Türkçe yaz. 3-4 cümle yeterli."
                },
                {
                    "role": "user",
                    "content": (
                        f"{itinerary.city} için {itinerary.total_days} günlük gezi planını tanıt. "
                        f"Yerler: {places_str}. "
                        f"Bütçe: {budget.total:.0f} TL (konaklama {budget.accommodation:.0f} TL dahil). "
                        f"Samimi ve heyecanlı 3-4 cümle yaz."
                    )
                }
            ]
            
            print(f"🤖 LLM ile açıklama üretiliyor...")
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    llm_wrapper.chat,
                    messages=messages,
                    max_tokens=200,
                    temperature=0.8
                )
                try:
                    result = future.result(timeout=self.LLM_TIMEOUT)
                    if result and len(result.strip()) > 20:
                        print(f"🤖 LLM açıklama başarılı")
                        return result.strip()
                except FutureTimeout:
                    print(f"⏳ LLM timeout, template kullanılıyor")
        
        except Exception as e:
            print(f"⚠ LLM hatası: {e}")
        
        return None
    
    def _template_explanation(self, itinerary: Itinerary) -> str:
        """Template-based fallback açıklama"""
        total_places = sum(len(d.places) for d in itinerary.days)
        budget = itinerary.budget
        
        text = (
            f"{itinerary.city} için {itinerary.total_days} günlük harika bir plan hazırladık! "
            f"Toplamda {total_places} farklı yer ziyaret edeceksiniz. "
        )
        
        if itinerary.accommodation:
            text += f"Konaklamanız {itinerary.accommodation.name} otelinde ({itinerary.accommodation.rating}⭐). "
        
        text += (
            f"Toplam tahmini maliyet {budget.total:.0f} TL olup, "
            f"bütçenizden {budget.remaining:.0f} TL kalacaktır."
        )
        
        return text
