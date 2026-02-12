# Ajan Tabanlı, Erişim Destekli ve Doğrulanabilir Seyahat ve Etkinlik Öneri Planlayıcısı

Bu proje, çoklu ajan mimarisi ile erişim destekli akıl yürütmeyi ve doğrulanabilir planlamayı bir araya getiren özgün bir seyahat ve etkinlik öneri planlayıcısıdır.

## Mimari

Proje, bir **Ajan Orkestratörü** tarafından yönetilen dört bileşenli çoklu ajan mimarisine sahiptir:

1. **Erişim Ajanı (Retriever Agent)**: Harici kaynaklardan kanıt toplar (FAISS vektör arama)
2. **Optimizasyon Ajanı (Optimizer Agent)**: Kullanıcı kısıtlamalarına göre planları ayarlar
3. **Doğrulama Ajanı (Verifier Agent)**: NLI tabanlı olgusal uyum kontrolü
4. **Açıklama Ajanı (Explainer Agent)**: Llama LLM ile kanıt destekli açıklamalar üretir

### Çoklu-Ajan Özellikleri

- **Mesajlaşma Sistemi**: Ajanlar arası merkezi mesajlaşma otobüsü (Message Bus)
- **Görev Akışı Yönetimi**: Görev bağımlılıkları ve durum takibi
- **Llama LLM Entegrasyonu**: Doğal dil üretimi için Llama model desteği
- **İş Akışı Koordinasyonu**: Retriever → Optimizer → Verifier → Explainer sıralı akış

Detaylı mimari dokümantasyonu için: [docs/MULTI_AGENT_ARCHITECTURE.md](docs/MULTI_AGENT_ARCHITECTURE.md)

## Proje Yapısı

```
tubitak/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py          # Ajan Orkestratörü
│   ├── retriever_agent.py       # Erişim Ajanı
│   ├── optimizer_agent.py       # Optimizasyon Ajanı
│   ├── verifier_agent.py        # Doğrulama Ajanı
│   └── explainer_agent.py       # Açıklama Ajanı
├── models/
│   ├── __init__.py
│   ├── data_models.py           # Veri modelleri
│   └── message_models.py        # Mesajlaşma modelleri
├── utils/
│   ├── __init__.py
│   ├── vector_store.py          # FAISS vektör deposu
│   ├── config.py                # Konfigürasyon
│   ├── message_bus.py           # Mesajlaşma otobüsü
│   ├── workflow_manager.py      # Görev akışı yöneticisi
│   └── llm_wrapper.py           # Llama LLM wrapper
├── docs/
│   └── MULTI_AGENT_ARCHITECTURE.md  # Mimari dokümantasyonu
├── web/
│   ├── __init__.py
│   ├── app.py                   # Flask uygulaması
│   └── templates/
│       └── index.html           # Web arayüzü
├── requirements.txt
├── config.yaml
└── main.py                      # Ana uygulama
```

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. Konfigürasyon dosyasını düzenleyin (`config.yaml`)

3. Uygulamayı çalıştırın:
```bash
python main.py
```

## Kullanım

Web arayüzü üzerinden kullanıcı tercihlerini (ilgi alanları, bütçe, tarih, konum) girin. Sistem otomatik olarak:
- İlgili kanıtları toplar
- Planları optimize eder
- Doğruluğu kontrol eder
- Açıklamalar üretir

## Teknolojiler

- Python 3.8+
- PyTorch
- Hugging Face Transformers
- **Llama 3.1 LLM** (meta-llama/Llama-3.1-8B-Instruct) - En güncel model
- FAISS (vektör arama)
- OR-Tools (optimizasyon)
- Flask (web arayüzü)
- Sentence-Transformers
- Accelerate (model optimizasyonu)

## Lisans

Bu proje TÜBİTAK 2209-A kapsamında geliştirilmiştir.





