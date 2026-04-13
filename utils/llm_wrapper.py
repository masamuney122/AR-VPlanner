"""
LLM wrapper - Llama model desteği
"""
from typing import List, Dict, Any, Optional
from utils.config import config
import os


class LLMWrapper:
    """LLM wrapper - Llama ve diğer modeller için"""
    
    def __init__(self):
        self.model_name = config.get('models.llm_model', 'meta-llama/Llama-3.2-3B-Instruct')
        self.model_type = config.get('models.llm_type', 'transformers')  # 'transformers' veya 'llama-cpp'
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        """Modeli yükle"""
        try:
            if self.model_type == 'llama-cpp':
                # llama-cpp-python kullanımı
                try:
                    from llama_cpp import Llama
                    model_path = config.get('models.llm_model_path', '')
                    if model_path and os.path.exists(model_path):
                        self.model = Llama(
                            model_path=model_path,
                            n_ctx=2048,
                            n_threads=4,
                            verbose=False
                        )
                        print(f"Llama-cpp modeli yüklendi: {model_path}")
                    else:
                        print("Llama-cpp model yolu belirtilmemiş veya dosya bulunamadı")
                except ImportError:
                    print("llama-cpp-python yüklü değil, transformers kullanılıyor")
                    self.model_type = 'transformers'
            
            if self.model_type == 'transformers':
                # Transformers kütüphanesi ile Llama
                try:
                    from transformers import AutoTokenizer, AutoModelForCausalLM
                    import torch
                    # Token çözümleme sırası:
                    # 1) huggingface-cli login ile kaydedilen token
                    # 2) .env içindeki HUGGINGFACE_TOKEN / HF_TOKEN
                    hf_token = None
                    try:
                        from huggingface_hub import get_token
                        hf_token = get_token()
                    except Exception:
                        hf_token = None
                    if not hf_token:
                        hf_token = os.getenv('HUGGINGFACE_TOKEN') or os.getenv('HF_TOKEN')
                    
                    # Llama modeli yükleme
                    model_name = self.model_name
                    if 'llama' in model_name.lower() or 'meta-llama' in model_name.lower():
                        # Hugging Face'den Llama modeli
                        print(f"Llama modeli yükleniyor: {model_name}")
                        if not hf_token:
                            print("Uyarı: HUGGINGFACE_TOKEN bulunamadı. Gated model erişimi başarısız olabilir.")
                        self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=hf_token)
                        
                        # Llama 3.2 için özel ayarlar
                        if 'llama-3' in model_name.lower():
                            # Llama 3.x için tokenizer ayarları
                            if self.tokenizer.pad_token is None:
                                self.tokenizer.pad_token = self.tokenizer.eos_token
                            self.tokenizer.padding_side = "left"
                        
                        self.model = AutoModelForCausalLM.from_pretrained(
                            model_name,
                            token=hf_token,
                            dtype=torch.float16,
                            device_map="auto" if torch.cuda.is_available() else None,
                            low_cpu_mem_usage=True
                        )
                        print("Llama modeli başarıyla yüklendi")
                    else:
                        # Diğer modeller için
                        self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=hf_token)
                        self.model = AutoModelForCausalLM.from_pretrained(model_name, token=hf_token)
                except Exception as e:
                    print(f"Model yükleme hatası: {str(e)}")
                    print("Basit metin üretimi modu kullanılıyor")
                    self.model = None
                    self.tokenizer = None
        except Exception as e:
            print(f"LLM wrapper başlatma hatası: {str(e)}")
            self.model = None
            self.tokenizer = None
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """
        Metin üret
        
        Args:
            prompt: Girdi metni
            max_tokens: Maksimum token sayısı
            temperature: Sıcaklık parametresi
            top_p: Top-p sampling
            stop_sequences: Durdurma dizileri
        
        Returns:
            Üretilen metin
        """
        if self.model is None:
            # Fallback: Basit metin üretimi
            return self._simple_generate(prompt)
        
        try:
            if self.model_type == 'llama-cpp':
                return self._generate_llama_cpp(prompt, max_tokens, temperature, top_p, stop_sequences)
            elif self.model_type == 'transformers':
                return self._generate_transformers(prompt, max_tokens, temperature, top_p, stop_sequences)
        except Exception as e:
            print(f"Metin üretim hatası: {str(e)}")
            return self._simple_generate(prompt)
    
    def _generate_llama_cpp(self, prompt: str, max_tokens: int, temperature: float, top_p: float, stop_sequences: Optional[List[str]]) -> str:
        """Llama-cpp ile metin üret"""
        if self.model is None:
            return self._simple_generate(prompt)
        
        try:
            response = self.model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop_sequences or [],
                echo=False
            )
            return response['choices'][0]['text'].strip()
        except Exception as e:
            print(f"Llama-cpp üretim hatası: {str(e)}")
            return self._simple_generate(prompt)
    
    def _generate_transformers(self, prompt: str, max_tokens: int, temperature: float, top_p: float, stop_sequences: Optional[List[str]]) -> str:
        """Transformers ile metin üret"""
        if self.model is None or self.tokenizer is None:
            return self._simple_generate(prompt)
        
        try:
            import torch
            
            # Tokenize
            inputs = self.tokenizer(prompt, return_tensors="pt")
            input_length = inputs['input_ids'].shape[1]  # Girdi token uzunluğu
            
            if torch.cuda.is_available() and hasattr(self.model, 'device'):
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Sadece yeni üretilen tokenları decode et (prompt kısmını atla)
            new_tokens = outputs[0][input_length:]
            generated_text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
            
            # Stop sequences kontrolü
            if stop_sequences:
                for stop_seq in stop_sequences:
                    if stop_seq in generated_text:
                        generated_text = generated_text.split(stop_seq)[0]
            
            return generated_text.strip()
        except Exception as e:
            print(f"Transformers üretim hatası: {str(e)}")
            return self._simple_generate(prompt)
    
    def _simple_generate(self, prompt: str) -> str:
        """Basit metin üretimi (fallback)"""
        # Bu basit bir fallback - gerçek uygulamada daha iyi bir yaklaşım kullanılmalı
        return f"[LLM yanıtı: {prompt[:50]}...]"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> str:
        """
        Chat formatında konuşma (Llama 3.2 Instruct formatı)
        
        Args:
            messages: Mesaj listesi [{"role": "user", "content": "..."}, ...]
            max_tokens: Maksimum token
            temperature: Sıcaklık
        
        Returns:
            Yanıt metni
        """
        # Llama 3.2 için chat template kullan
        if self.tokenizer and hasattr(self.tokenizer, 'apply_chat_template'):
            try:
                # Llama 3.2'nin resmi chat template'ini kullan
                prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
                return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)
            except Exception as e:
                print(f"Chat template hatası: {str(e)}, basit format kullanılıyor")
        
        # Fallback: Basit chat formatı
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"<|system|>\n{content}<|end|>\n")
            elif role == "user":
                prompt_parts.append(f"<|user|>\n{content}<|end|>\n")
            elif role == "assistant":
                prompt_parts.append(f"<|assistant|>\n{content}<|end|>\n")
        
        prompt = "".join(prompt_parts) + "<|assistant|>\n"
        
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)


# Global LLM wrapper instance
llm_wrapper = LLMWrapper()

