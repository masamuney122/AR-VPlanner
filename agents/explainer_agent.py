"""
Açıklama Ajanı (Explainer Agent)
Itinerary için insancıl açıklamalar üretir
RAG context kullanarak bilgiye dayalı, zengin açıklamalar sağlar
"""
from typing import List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from models.data_models import Itinerary, Evidence


class ExplainerAgent:
    """Açıklama Ajanı - RAG destekli itinerary açıklamaları"""

    LLM_TIMEOUT = 90

    def generate_itinerary_explanation(
        self, itinerary: Itinerary, rag_context: List[Evidence] = None
    ) -> str:
        """RAG context ile zenginleştirilmiş açıklama üret."""
        llm_text = self._try_llm_explanation(itinerary, rag_context)
        if llm_text:
            return llm_text
        return self._template_explanation(itinerary)

    def _try_llm_explanation(
        self, itinerary: Itinerary, rag_context: List[Evidence] = None
    ) -> str:
        """LLM + RAG context ile insancıl açıklama üret."""
        try:
            from utils.llm_wrapper import llm_wrapper

            if llm_wrapper.model is None:
                return None

            place_names = []
            for day in itinerary.days:
                for p in day.places[:2]:
                    place_names.append(p.name)

            places_str = ", ".join(place_names[:6])
            budget = itinerary.budget

            context_block = ""
            if rag_context:
                context_parts = [e.content for e in rag_context[:4]]
                context_block = (
                    "Aşağıda bu şehir hakkında bilgi tabanından alınan notlar var. "
                    "Açıklamanda bu bilgilerden yararlan:\n\n"
                    + "\n---\n".join(context_parts)
                    + "\n\n"
                )

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Sen bir seyahat danışmanısın. Samimi, heyecanlı ve kısa açıklamalar yazarsın. "
                        "Türkçe yaz. 3-5 cümle yeterli. Bilgi tabanından gelen notları kullanarak "
                        "pratik ve bilgilendirici öneriler ekle."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"{context_block}"
                        f"{itinerary.city} için {itinerary.total_days} günlük gezi planını tanıt. "
                        f"Yerler: {places_str}. "
                        f"Bütçe: {budget.total:.0f} TL (konaklama {budget.accommodation:.0f} TL dahil). "
                        f"Samimi ve heyecanlı 3-5 cümle yaz. Bilgi tabanındaki pratik detaylardan bahset."
                    )
                }
            ]

            print(f"🤖 LLM ile açıklama üretiliyor (RAG context: {len(rag_context or [])} paragraf)...")

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    llm_wrapper.chat,
                    messages=messages,
                    max_tokens=250,
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
        """Template-based fallback açıklama."""
        total_places = sum(len(d.places) for d in itinerary.days)
        budget = itinerary.budget

        text = (
            f"{itinerary.city} için {itinerary.total_days} günlük harika bir plan hazırladık! "
            f"Toplamda {total_places} farklı yer ziyaret edeceksiniz. "
        )

        if itinerary.accommodation:
            text += (
                f"Konaklamanız {itinerary.accommodation.name} otelinde "
                f"({itinerary.accommodation.rating}⭐). "
            )

        text += (
            f"Toplam tahmini maliyet {budget.total:.0f} TL olup, "
            f"bütçenizden {budget.remaining:.0f} TL kalacaktır."
        )

        return text
