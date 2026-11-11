from enum import Enum
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT_OPTION = "select_option"
    PRESS_KEY = "press_key"
    WAIT = "wait"
    ASSERT = "assert"
    FINISH = "finish"


class AgentAction(BaseModel):
    action: ActionType = Field(..., description="Action to perform in the browser")
    element_id: Optional[str] = Field(None, description="Target element ID, e.g. e1, e2")
    selector: Optional[str] = Field(None, description="CSS or text selector if element_id is not used")
    value: Optional[str] = Field(None, description="Value for fill, select, or URL for navigate")
    assertion_condition: Optional[str] = Field(None, description="Expected text, URL fragment, or element presence to verify")
    test_passed: Optional[bool] = Field(None, description="True if test succeeded, False if failed (used when action is finish)")
    reasoning: str = Field(..., description="Step reasoning: why this action helps achieve the overall test goal")


class InteractiveElement(BaseModel):
    id: str
    tag: str
    role: Optional[str] = None
    text: Optional[str] = None
    name: Optional[str] = None
    input_type: Optional[str] = None
    placeholder: Optional[str] = None
    value: Optional[str] = None
    aria_label: Optional[str] = None
    href: Optional[str] = None
    selector: str
    bounding_box: Optional[Dict[str, float]] = None


class PageSnapshot(BaseModel):
    url: str
    title: str
    interactive_elements: List[InteractiveElement]
    clean_text_summary: str
    screenshot_path: Optional[str] = None


class StepRecord(BaseModel):
    step_number: int
    action: AgentAction
    status: str
    details: str
    screenshot_path: Optional[str] = None
    page_url: str


class TestResult(BaseModel):
    goal: str
    status: str  # "PASS" or "FAIL"
    summary: str
    total_steps: int
    duration_seconds: float
    steps: List[StepRecord] = []
    error_message: Optional[str] = None
    final_url: Optional[str] = None
    final_screenshot: Optional[str] = None
    report_path: Optional[str] = None

