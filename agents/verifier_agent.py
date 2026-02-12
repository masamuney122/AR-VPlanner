"""
Doğrulama Ajanı (Verifier Agent)
Olgusal uyumu kontrol eder - NLI modelleri kullanır
"""
from typing import List, Dict, Any
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from models.data_models import Activity, TravelPlan, AgentResponse, Evidence
from models.message_models import MessageType
from utils.config import config
from utils.message_bus import message_bus


class VerifierAgent:
    """Doğrulama Ajanı - Olgusal doğrulama"""
    
    def __init__(self):
        self.agent_name = "verifier"
        self.model_name = config.get('models.nli_model', 'microsoft/deberta-v3-base')
        self.tokenizer = None
        self.model = None
        self._load_model()
        self._register_message_handler()
    
    def _register_message_handler(self):
        """Mesajlaşma sistemine kayıt ol"""
        message_bus.subscribe(self.agent_name, self._handle_message)
    
    def _handle_message(self, message):
        """Gelen mesajları işle"""
        if message.message_type == MessageType.REQUEST:
            content = message.content
            if content.get("event") == "plan_ready_for_verification":
                # Plan doğrulama için hazır
                pass
    
    def _load_model(self):
        """NLI modelini yükle"""
        try:
            # Not: Gerçek uygulamada daha uygun bir NLI modeli kullanılmalı
            # Örnek: 'microsoft/deberta-v3-base' veya 'roberta-large-mnli'
            # Şimdilik basit bir yaklaşım kullanıyoruz
            print(f"NLI modeli yükleniyor: {self.model_name}")
            # Model yükleme işlemi (büyük modeller için GPU gerekebilir)
            # self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            # self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            print("Model yükleme atlandı (demo modu)")
        except Exception as e:
            print(f"Model yükleme hatası: {str(e)}")
            print("Basit doğrulama modu kullanılıyor")
    
    def verify_plan(self, plan: TravelPlan, evidence_list: List[Evidence]) -> AgentResponse:
        """
        Planın kanıtlarla uyumunu doğrula
        
        Args:
            plan: Doğrulanacak seyahat planı
            evidence_list: Kanıt listesi
        
        Returns:
            AgentResponse: Doğrulama sonuçları
        """
        try:
            # Mesajlaşma: Doğrulama başladı
            message_bus.send_message(
                sender=self.agent_name,
                receiver="broadcast",
                message_type=MessageType.STATUS_UPDATE,
                content={
                    "event": "verification_started",
                    "activity_count": len(plan.activities)
                }
            )
            
            if not plan.activities:
                return AgentResponse(
                    success=False,
                    data=plan,
                    message="Doğrulanacak etkinlik bulunamadı",
                    metadata={}
                )
            
            verification_details = {}
            all_verified = True
            
            for activity in plan.activities:
                # Her etkinlik için kanıt kontrolü yap
                verification_result = self._verify_activity(activity, evidence_list)
                activity.verification_score = verification_result['score']
                verification_details[activity.name] = verification_result
                
                if verification_result['score'] < 0.5:  # Eşik değer
                    all_verified = False
            
            # Plan seviyesinde doğrulama
            plan.verified = all_verified
            plan.verification_details = verification_details
            
            overall_score = sum(
                act.verification_score for act in plan.activities
            ) / len(plan.activities) if plan.activities else 0.0
            
            # Mesajlaşma: Doğrulama tamamlandı
            message_bus.send_message(
                sender=self.agent_name,
                receiver="broadcast",
                message_type=MessageType.NOTIFICATION,
                content={
                    "event": "verification_completed",
                    "overall_score": overall_score,
                    "verified": all_verified
                }
            )
            
            return AgentResponse(
                success=True,
                data=plan,
                message=f"Doğrulama tamamlandı. Genel skor: {overall_score:.2f}",
                metadata={
                    "overall_score": overall_score,
                    "verified": all_verified,
                    "verification_details": verification_details
                }
            )
        
        except Exception as e:
            # Mesajlaşma: Hata durumu
            message_bus.send_message(
                sender=self.agent_name,
                receiver="broadcast",
                message_type=MessageType.ERROR,
                content={
                    "event": "verification_error",
                    "error": str(e)
                }
            )
            
            return AgentResponse(
                success=False,
                data=plan,
                message=f"Doğrulama hatası: {str(e)}",
                metadata={"error": str(e)}
            )
    
    def _verify_activity(self, activity: Activity, evidence_list: List[Evidence]) -> Dict[str, Any]:
        """
        Tek bir etkinliği kanıtlarla doğrula
        
        Args:
            activity: Doğrulanacak etkinlik
            evidence_list: Kanıt listesi
        
        Returns:
            Doğrulama sonucu
        """
        # Basit bir doğrulama yaklaşımı
        # Gerçek uygulamada NLI modeli kullanılacak
        
        activity_text = f"{activity.name} {activity.description} {activity.location}"
        activity_text_lower = activity_text.lower()
        
        matching_evidence = []
        max_score = 0.0
        
        for evidence in evidence_list:
            evidence_text_lower = evidence.content.lower()
            
            # Basit kelime eşleşmesi (gerçek uygulamada NLI kullanılacak)
            activity_words = set(activity_text_lower.split())
            evidence_words = set(evidence_text_lower.split())
            
            # Jaccard benzerliği
            intersection = len(activity_words & evidence_words)
            union = len(activity_words | evidence_words)
            similarity = intersection / union if union > 0 else 0.0
            
            # Relevance score ile birleştir
            combined_score = similarity * evidence.relevance_score
            
            if combined_score > 0.1:  # Eşik değer
                matching_evidence.append({
                    "evidence": evidence.content[:100],  # İlk 100 karakter
                    "source": evidence.source,
                    "score": combined_score
                })
                max_score = max(max_score, combined_score)
        
        # NLI modeli kullanılırsa (şimdilik basit yaklaşım)
        # premise = evidence.content
        # hypothesis = f"{activity.name} is located in {activity.location}"
        # score = self._nli_inference(premise, hypothesis)
        
        return {
            "score": min(max_score, 1.0),
            "matching_evidence_count": len(matching_evidence),
            "matching_evidence": matching_evidence[:3]  # İlk 3 kanıt
        }
    
    def _nli_inference(self, premise: str, hypothesis: str) -> float:
        """
        NLI modeli ile çıkarım yap (gerçek implementasyon)
        
        Args:
            premise: Öncül (kanıt)
            hypothesis: Hipotez (etkinlik bilgisi)
        
        Returns:
            Doğruluk skoru (0-1)
        """
        # Gerçek implementasyon için:
        # inputs = self.tokenizer(premise, hypothesis, return_tensors="pt", truncation=True)
        # outputs = self.model(**inputs)
        # probs = torch.softmax(outputs.logits, dim=-1)
        # entailment_score = probs[0][2].item()  # ENTAILMENT label
        
        # Şimdilik basit bir placeholder
        return 0.5

