"""
Ajanlar arası mesajlaşma otobüsü (Message Bus)
"""
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict
from threading import Lock
from models.message_models import Message, AgentMessage, MessageType
import uuid


class MessageBus:
    """Ajanlar arası mesajlaşma otobüsü"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_queue: List[Message] = []
        self._lock = Lock()
        self._message_history: List[Message] = []
        self._max_history = 1000
    
    def subscribe(self, agent_name: str, callback: Callable[[Message], None]):
        """
        Ajanı mesajlaşma sistemine kaydet
        
        Args:
            agent_name: Ajan adı
            callback: Mesaj alındığında çağrılacak fonksiyon
        """
        with self._lock:
            self._subscribers[agent_name].append(callback)
    
    def unsubscribe(self, agent_name: str, callback: Callable[[Message], None]):
        """Ajanı mesajlaşma sisteminden çıkar"""
        with self._lock:
            if agent_name in self._subscribers:
                if callback in self._subscribers[agent_name]:
                    self._subscribers[agent_name].remove(callback)
    
    def publish(self, message: Message) -> bool:
        """
        Mesaj yayınla
        
        Args:
            message: Yayınlanacak mesaj
        
        Returns:
            Başarı durumu
        """
        with self._lock:
            # Mesaj geçmişine ekle
            self._message_history.append(message)
            if len(self._message_history) > self._max_history:
                self._message_history.pop(0)
            
            # Kuyruğa ekle
            self._message_queue.append(message)
            
            # Abonelere ilet
            if message.receiver == "broadcast":
                # Tüm abonelere gönder
                for agent_name, callbacks in self._subscribers.items():
                    for callback in callbacks:
                        try:
                            callback(message)
                        except Exception as e:
                            print(f"Mesaj iletim hatası ({agent_name}): {str(e)}")
            else:
                # Sadece hedef ajana gönder
                if message.receiver in self._subscribers:
                    for callback in self._subscribers[message.receiver]:
                        try:
                            callback(message)
                        except Exception as e:
                            print(f"Mesaj iletim hatası ({message.receiver}): {str(e)}")
            
            return True
    
    def send_message(
        self,
        sender: str,
        receiver: str,
        message_type: MessageType,
        content: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Message:
        """
        Mesaj gönder (kolaylık fonksiyonu)
        
        Returns:
            Oluşturulan mesaj
        """
        message = Message(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            content=content,
            correlation_id=correlation_id
        )
        self.publish(message)
        return message
    
    def get_message_history(self, agent_name: Optional[str] = None, limit: int = 100) -> List[Message]:
        """
        Mesaj geçmişini al
        
        Args:
            agent_name: Belirli bir ajan için filtrele (None = tümü)
            limit: Maksimum mesaj sayısı
        
        Returns:
            Mesaj listesi
        """
        with self._lock:
            if agent_name:
                filtered = [m for m in self._message_history if m.sender == agent_name or m.receiver == agent_name]
                return filtered[-limit:]
            return self._message_history[-limit:]
    
    def clear_queue(self):
        """Mesaj kuyruğunu temizle"""
        with self._lock:
            self._message_queue.clear()


# Global mesaj otobüsü instance
message_bus = MessageBus()



