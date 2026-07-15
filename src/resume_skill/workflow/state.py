"""Application state definition for LangGraph workflow."""

from typing import TypedDict, Optional, List, Dict, Any
from typing_extensions import NotRequired


class ApplicationState(TypedDict):
    """Application workflow state."""
    
    # Task identification
    task_id: str
    
    # Input data
    user_profile: Dict[str, Any]
    resume_data: Dict[str, Any]
    resume_pdf_path: str
    job_description: Dict[str, Any]
    
    # Generated content
    application_form: Dict[str, Any]
    generated_documents: Dict[str, Any]
    
    # Browser execution context
    browser_context: Dict[str, Any]
    
    # Workflow state
    current_task: str
    next_action: str
    execution_history: List[Dict[str, Any]]
    errors: List[str]
    
    # Recovery and manual intervention flags
    gui_recovery_needed: bool
    manual_required: bool
    
    # Success indicators
    success: bool
    
    # Retry management
    retry_count: int
    max_retries: int
    
    # Additional optional fields for future extension
    metadata: NotRequired[Dict[str, Any]]
    visual_verification_result: NotRequired[Dict[str, Any]]
    llm_decision_log: NotRequired[List[Dict[str, Any]]]
    _chrome_client: NotRequired[Any]
    _llm_client: NotRequired[Any]
    _vision_client: NotRequired[Any]
