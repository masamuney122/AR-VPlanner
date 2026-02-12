"""
Ajanlar arası mesajlaşma modelleri
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class MessageType(Enum):
    """Mesaj tipleri"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"
    STATUS_UPDATE = "status_update"


class TaskStatus(Enum):
    """Görev durumları"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Message:
    """Temel mesaj yapısı"""
    message_id: str
    sender: str  # Ajan adı
    receiver: str  # Ajan adı veya "broadcast"
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None  # İlişkili mesajlar için
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessage:
    """Ajan mesajı - iş mantığı içerir"""
    message: Message
    task_id: Optional[str] = None
    requires_response: bool = True
    priority: int = 0  # 0-10 arası, yüksek sayı = yüksek öncelik


@dataclass
class Task:
    """Görev yapısı"""
    task_id: str
    task_type: str  # "retrieve", "optimize", "verify", "explain"
    status: TaskStatus
    assigned_agent: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)  # Bağımlı görev ID'leri
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowState:
    """İş akışı durumu"""
    workflow_id: str
    current_step: str
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    tasks: Dict[str, Task] = field(default_factory=dict)
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)



