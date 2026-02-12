"""
Görev akışı yönetimi (Workflow Manager)
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from models.message_models import Task, TaskStatus, WorkflowState, Message, MessageType
from utils.message_bus import message_bus
import uuid


class WorkflowManager:
    """Görev akışı yöneticisi"""
    
    def __init__(self):
        self.workflows: Dict[str, WorkflowState] = {}
        self.tasks: Dict[str, Task] = {}
    
    def create_workflow(
        self,
        workflow_type: str = "plan_generation",
        metadata: Optional[Dict[str, Any]] = None
    ) -> WorkflowState:
        """
        Yeni iş akışı oluştur
        
        Args:
            workflow_type: İş akışı tipi
            metadata: Ek bilgiler
        
        Returns:
            Oluşturulan iş akışı
        """
        workflow_id = str(uuid.uuid4())
        workflow = WorkflowState(
            workflow_id=workflow_id,
            current_step="initialized",
            metadata={"workflow_type": workflow_type, **(metadata or {})}
        )
        self.workflows[workflow_id] = workflow
        
        # Mesaj gönder
        message_bus.send_message(
            sender="workflow_manager",
            receiver="broadcast",
            message_type=MessageType.NOTIFICATION,
            content={
                "event": "workflow_created",
                "workflow_id": workflow_id,
                "workflow_type": workflow_type
            }
        )
        
        return workflow
    
    def create_task(
        self,
        workflow_id: str,
        task_type: str,
        assigned_agent: str,
        input_data: Dict[str, Any],
        dependencies: Optional[List[str]] = None
    ) -> Task:
        """
        Yeni görev oluştur
        
        Args:
            workflow_id: İş akışı ID'si
            task_type: Görev tipi
            assigned_agent: Atanan ajan
            input_data: Girdi verisi
            dependencies: Bağımlı görev ID'leri
        
        Returns:
            Oluşturulan görev
        """
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            assigned_agent=assigned_agent,
            input_data=input_data,
            dependencies=dependencies or []
        )
        
        self.tasks[task_id] = task
        
        if workflow_id in self.workflows:
            self.workflows[workflow_id].tasks[task_id] = task
        
        # Mesaj gönder
        message_bus.send_message(
            sender="workflow_manager",
            receiver=assigned_agent,
            message_type=MessageType.REQUEST,
            content={
                "event": "task_created",
                "task_id": task_id,
                "task_type": task_type,
                "workflow_id": workflow_id,
                "input_data": input_data,
                "dependencies": dependencies or []
            }
        )
        
        return task
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Görev durumunu güncelle
        
        Args:
            task_id: Görev ID'si
            status: Yeni durum
            output_data: Çıktı verisi
            error_message: Hata mesajı
        
        Returns:
            Başarı durumu
        """
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = status
        
        if output_data:
            task.output_data = output_data
        
        if error_message:
            task.error_message = error_message
        
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
        elif status == TaskStatus.IN_PROGRESS:
            task.status = TaskStatus.IN_PROGRESS
        
        # Mesaj gönder
        message_bus.send_message(
            sender="workflow_manager",
            receiver="broadcast",
            message_type=MessageType.STATUS_UPDATE,
            content={
                "event": "task_status_updated",
                "task_id": task_id,
                "status": status.value,
                "assigned_agent": task.assigned_agent
            }
        )
        
        return True
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        """İş akışını al"""
        return self.workflows.get(workflow_id)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Görevi al"""
        return self.tasks.get(task_id)
    
    def update_workflow_step(self, workflow_id: str, step: str, completed: bool = True):
        """
        İş akışı adımını güncelle
        
        Args:
            workflow_id: İş akışı ID'si
            step: Adım adı
            completed: Tamamlandı mı?
        """
        if workflow_id not in self.workflows:
            return
        
        workflow = self.workflows[workflow_id]
        workflow.current_step = step
        
        if completed:
            if step not in workflow.completed_steps:
                workflow.completed_steps.append(step)
        else:
            if step not in workflow.failed_steps:
                workflow.failed_steps.append(step)
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        İş akışı durumunu al
        
        Returns:
            Durum bilgisi
        """
        if workflow_id not in self.workflows:
            return {"error": "Workflow not found"}
        
        workflow = self.workflows[workflow_id]
        tasks_status = {
            task_id: {
                "status": task.status.value,
                "type": task.task_type,
                "agent": task.assigned_agent
            }
            for task_id, task in workflow.tasks.items()
        }
        
        return {
            "workflow_id": workflow_id,
            "current_step": workflow.current_step,
            "completed_steps": workflow.completed_steps,
            "failed_steps": workflow.failed_steps,
            "tasks": tasks_status,
            "created_at": workflow.created_at.isoformat()
        }


# Global workflow manager instance
workflow_manager = WorkflowManager()



