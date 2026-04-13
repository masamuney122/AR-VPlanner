"""
Doğrulama Ajanı (Verifier Agent)
RAG bilgi tabanını kullanarak itinerary'deki yerleri çapraz doğrular.
Her yer için bilgi tabanında kanıt arar ve doğrulama skoru üretir.
"""
from typing import List, Dict, Any
from models.data_models import Itinerary, Place, Evidence, AgentResponse
from utils.vector_store import vector_store


class VerifierAgent:
    """Doğrulama Ajanı — RAG tabanlı çapraz doğrulama"""

    VERIFICATION_THRESHOLD = 0.3

    def verify_itinerary(
        self,
        itinerary: Itinerary,
        rag_context: List[Evidence],
    ) -> AgentResponse:
        """
        Itinerary'deki her yeri RAG bilgi tabanı ile çapraz doğrula.

        Her yer için:
        1. Bilgi tabanından en alakalı paragrafları bul (FAISS)
        2. Yer adının paragrafta geçip geçmediğini kontrol et
        3. Semantik benzerlik skoru hesapla
        4. Birleşik doğrulama skoru üret

        Returns:
            AgentResponse with verification details per place
        """
        try:
            all_places = [p for day in itinerary.days for p in day.places]
            if not all_places:
                return AgentResponse(
                    success=True, data=itinerary,
                    message="Doğrulanacak yer bulunamadı",
                    metadata={"overall_score": 0, "verified": False}
                )

            verification_details: Dict[str, Dict[str, Any]] = {}
            total_score = 0.0
            verified_count = 0

            for place in all_places:
                result = self._verify_place(place, rag_context)
                verification_details[place.name] = result
                total_score += result["score"]
                if result["score"] >= self.VERIFICATION_THRESHOLD:
                    verified_count += 1

            overall_score = total_score / len(all_places) if all_places else 0
            verification_ratio = verified_count / len(all_places) if all_places else 0

            itinerary.verified = verification_ratio >= 0.5
            itinerary.verification_details = {
                "overall_score": round(overall_score, 3),
                "verified_count": verified_count,
                "total_places": len(all_places),
                "verification_ratio": round(verification_ratio, 3),
                "per_place": verification_details
            }

            return AgentResponse(
                success=True,
                data=itinerary,
                message=(
                    f"Doğrulama tamamlandı: {verified_count}/{len(all_places)} yer doğrulandı "
                    f"(skor: {overall_score:.2f})"
                ),
                metadata={
                    "overall_score": round(overall_score, 3),
                    "verified_count": verified_count,
                    "total_places": len(all_places),
                    "verification_ratio": round(verification_ratio, 3),
                }
            )

        except Exception as e:
            return AgentResponse(
                success=True, data=itinerary,
                message=f"Doğrulama hatası (plan yine de kullanılabilir): {e}",
                metadata={"overall_score": 0, "error": str(e)}
            )

    def _verify_place(self, place: Place, rag_context: List[Evidence]) -> Dict[str, Any]:
        """
        Tek bir yeri RAG bilgi tabanıyla doğrula.

        Üç sinyal kullanır:
        1. name_match: Yer adı bilgi tabanı paragraflarında geçiyor mu?
        2. semantic_score: FAISS semantik benzerlik skoru
        3. rag_context_match: Önceden çekilmiş RAG context'te geçiyor mu?
        """
        place_name_lower = place.name.lower()
        name_tokens = set(place_name_lower.split())

        rag_match_score = self._check_rag_context(place_name_lower, name_tokens, rag_context)

        faiss_score = 0.0
        faiss_evidence = []
        if vector_store.is_ready:
            results = vector_store.search(place.name, top_k=3)
            for ev in results:
                ev_lower = ev.content.lower()
                if self._fuzzy_name_match(place_name_lower, name_tokens, ev_lower):
                    faiss_score = max(faiss_score, ev.relevance_score * 1.5)
                    faiss_evidence.append(ev.content[:120])
                else:
                    faiss_score = max(faiss_score, ev.relevance_score * 0.5)

        combined = max(rag_match_score, min(faiss_score, 1.0))

        verified = combined >= self.VERIFICATION_THRESHOLD
        return {
            "score": round(combined, 3),
            "verified": verified,
            "evidence_snippets": faiss_evidence[:2],
            "method": "rag_cross_reference"
        }

    def _check_rag_context(
        self, name_lower: str, name_tokens: set, rag_context: List[Evidence]
    ) -> float:
        """Check if the place name appears in pre-fetched RAG context."""
        if not rag_context:
            return 0.0

        best = 0.0
        for ev in rag_context:
            ev_lower = ev.content.lower()
            if self._fuzzy_name_match(name_lower, name_tokens, ev_lower):
                best = max(best, 0.8 * ev.relevance_score + 0.2)
        return min(best, 1.0)

    @staticmethod
    def _fuzzy_name_match(name_lower: str, name_tokens: set, text_lower: str) -> bool:
        """
        Check whether a place name matches within a text block.
        Handles partial matches for multi-word names.
        """
        if name_lower in text_lower:
            return True

        significant = {t for t in name_tokens if len(t) > 3}
        if not significant:
            return False
        matched = sum(1 for t in significant if t in text_lower)
        return matched / len(significant) >= 0.6
