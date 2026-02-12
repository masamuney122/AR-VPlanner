# Çoklu-Ajan (Multi-Agent) Mimari Dokümantasyonu

## Genel Bakış

Bu proje, Retriever, Verifier, Optimizer ve Explainer ajanlarının birbirleriyle etkileşimini yöneten bir çoklu-ajan mimarisi içermektedir. Sistem, ajanlar arası mesajlaşma ve görev akışı yönetimi ile koordine edilmektedir.

## Mimari Bileşenler

### 1. Mesajlaşma Sistemi (Message Bus)

**Dosya:** `utils/message_bus.py`

Ajanlar arası iletişim için merkezi bir mesajlaşma otobüsü sağlar:

- **MessageBus**: Tüm ajanların mesaj gönderebileceği ve alabileceği merkezi sistem
- **Mesaj Tipleri**: REQUEST, RESPONSE, NOTIFICATION, ERROR, STATUS_UPDATE
- **Yayınlama (Publish/Subscribe)**: Ajanlar belirli mesajlara abone olabilir veya broadcast yapabilir

**Kullanım Örneği:**
```python
from utils.message_bus import message_bus
from models.message_models import MessageType

# Mesaj gönder
message_bus.send_message(
    sender="retriever",
    receiver="optimizer",
    message_type=MessageType.NOTIFICATION,
    content={"event": "evidence_retrieved", "count": 10}
)
```

### 2. Görev Akışı Yönetimi (Workflow Manager)

**Dosya:** `utils/workflow_manager.py`

Görevlerin yaşam döngüsünü ve bağımlılıklarını yönetir:

- **WorkflowState**: İş akışının genel durumu
- **Task**: Tek bir görev (retrieve, optimize, verify, explain)
- **TaskStatus**: PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
- **Bağımlılık Yönetimi**: Görevler arası bağımlılıklar takip edilir

**Kullanım Örneği:**
```python
from utils.workflow_manager import workflow_manager
from models.message_models import TaskStatus

# İş akışı oluştur
workflow = workflow_manager.create_workflow(workflow_type="plan_generation")

# Görev oluştur
task = workflow_manager.create_task(
    workflow_id=workflow.workflow_id,
    task_type="retrieve",
    assigned_agent="retriever",
    input_data={"query": "..."}
)

# Görev durumunu güncelle
workflow_manager.update_task_status(task.task_id, TaskStatus.COMPLETED)
```

### 3. LLM Wrapper (Llama Desteği)

**Dosya:** `utils/llm_wrapper.py`

Llama ve diğer LLM modelleri için birleşik bir arayüz sağlar:

- **Transformers Desteği**: Hugging Face transformers ile Llama modelleri
- **Llama-cpp Desteği**: Opsiyonel llama-cpp-python desteği
- **Chat ve Generate**: Hem chat hem de text generation modları

**Konfigürasyon (config.yaml):**
```yaml
models:
  llm_model: "meta-llama/Llama-3.1-8B-Instruct"  # En güncel Llama modeli
  llm_type: "transformers"  # veya "llama-cpp"
  llm_model_path: ""  # llama-cpp için yerel yol
```

**Not:** Llama 3.1-8B-Instruct, Llama 2'ye göre daha iyi performans ve daha güncel özellikler sunar. Daha güçlü bir model için `Llama-3.1-70B-Instruct` de kullanılabilir.

**Kullanım Örneği:**
```python
from utils.llm_wrapper import llm_wrapper

# Metin üret
response = llm_wrapper.generate(
    prompt="Seyahat planı için açıklama oluştur...",
    max_tokens=512,
    temperature=0.7
)
```

### 4. Ajan Orkestratörü (Orchestrator)

**Dosya:** `agents/orchestrator.py`

Tüm ajanları koordine eder ve iş akışını yönetir:

**İş Akışı:**
1. **Retriever** → Kanıt toplama
2. **Optimizer** → Plan optimizasyonu (Retriever'dan sonra)
3. **Verifier** → Doğrulama (Optimizer'dan sonra)
4. **Explainer** → Açıklama üretimi (Verifier'dan sonra)

Her adım mesajlaşma sistemi ile koordine edilir ve görev akışı yöneticisi tarafından takip edilir.

## Ajan Yapısı

### Retriever Agent
- **Görev**: Harici kaynaklardan kanıt toplama
- **Teknoloji**: FAISS vektör arama
- **Mesajlaşma**: Kanıt toplama başladı/tamamlandı mesajları gönderir

### Optimizer Agent
- **Görev**: Kullanıcı kısıtlamalarına göre plan optimizasyonu
- **Teknoloji**: OR-Tools, kısıt programlama
- **Mesajlaşma**: Optimizasyon durumu mesajları gönderir

### Verifier Agent
- **Görev**: NLI tabanlı doğrulama
- **Teknoloji**: Transformers NLI modelleri
- **Mesajlaşma**: Doğrulama sonuçları mesajları gönderir

### Explainer Agent
- **Görev**: Kanıt destekli açıklama üretimi
- **Teknoloji**: Llama LLM
- **Mesajlaşma**: Açıklama üretim durumu mesajları gönderir

## Mesajlaşma Protokolü

### Mesaj Formatı
```python
Message(
    message_id: str,
    sender: str,  # Ajan adı
    receiver: str,  # Ajan adı veya "broadcast"
    message_type: MessageType,
    content: Dict[str, Any],
    timestamp: datetime,
    correlation_id: Optional[str]
)
```

### Mesaj Akışı Örneği

1. **Orchestrator** → **Broadcast**: İş akışı başlatıldı
2. **Orchestrator** → **Retriever**: Kanıt toplama görevi
3. **Retriever** → **Broadcast**: Kanıt toplama tamamlandı
4. **Retriever** → **Optimizer**: Kanıtlar hazır
5. **Optimizer** → **Broadcast**: Optimizasyon tamamlandı
6. **Optimizer** → **Verifier**: Plan doğrulama için hazır
7. **Verifier** → **Broadcast**: Doğrulama tamamlandı
8. **Verifier** → **Explainer**: Plan doğrulandı
9. **Explainer** → **Broadcast**: Açıklama üretildi
10. **Orchestrator** → **Broadcast**: İş akışı tamamlandı

## Görev Bağımlılıkları

```
Retriever (Task 1)
    ↓
Optimizer (Task 2) [depends on: Task 1]
    ↓
Verifier (Task 3) [depends on: Task 2]
    ↓
Explainer (Task 4) [depends on: Task 3]
```

## Konfigürasyon

`config.yaml` dosyasında aşağıdaki ayarlar yapılabilir:

```yaml
models:
  llm_model: "meta-llama/Llama-2-7b-chat-hf"
  llm_type: "transformers"
  embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
  nli_model: "microsoft/deberta-v3-base"
```

## Bağımlılıklar

Yeni eklenen bağımlılıklar:
- `accelerate>=0.20.0` - Model yükleme optimizasyonu
- `bitsandbytes>=0.41.0` - Quantization desteği (opsiyonel)

## Kullanım

```python
from agents.orchestrator import AgentOrchestrator
from models.data_models import UserPreferences
from datetime import datetime

orchestrator = AgentOrchestrator()

user_preferences = UserPreferences(
    interests=["tarih", "doğa"],
    budget=2000.0,
    start_date=datetime(2026, 4, 1),
    end_date=datetime(2026, 4, 5),
    location="İzmir"
)

result = orchestrator.generate_plan(user_preferences)
```

## Özellikler

✅ Ajanlar arası mesajlaşma sistemi
✅ Görev akışı yönetimi ve bağımlılık takibi
✅ Llama LLM entegrasyonu
✅ Merkezi mesajlaşma otobüsü
✅ İş akışı durumu takibi
✅ Hata yönetimi ve mesajlaşma
✅ Genişletilebilir mimari

## Gelecek Geliştirmeler

- [ ] Asenkron mesajlaşma desteği
- [ ] Ajan durumu izleme dashboard'u
- [ ] Mesaj geçmişi analizi
- [ ] Performans metrikleri
- [ ] Ajan ölçeklendirme



