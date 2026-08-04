from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class GenerateReportPayload(BaseModel):
    title: str
    type: str = "PDF"  # PDF, PowerPoint
    frequency: str = "Ad-hoc"  # Daily, Weekly, Monthly, Quarterly, Ad-hoc
    workspace: str = "default"
    template: str = "CEO"  # CEO, Sales, Finance, Marketing, Operations
    recipient: EmailStr


class ReportResponse(BaseModel):
    id: str
    title: str
    type: str
    frequency: str
    template: str
    created: str
    size: str
    recipient: EmailStr
    workspace: str
    author: str
    datasets_used: Optional[str] = None
    delivery_status: str
    file_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReportSchedulePayload(BaseModel):
    title: str
    workspace: str = "default"
    report_type: str = "PDF"  # PDF, PowerPoint
    frequency: str  # Daily, Weekly, Monthly, Quarterly
    template: str = "CEO"  # CEO, Sales, Finance, Marketing, Operations
    recipient: EmailStr


class ReportScheduleResponse(BaseModel):
    id: str
    title: str
    workspace: str
    report_type: str
    frequency: str
    template: str
    recipient: EmailStr
    author: str
    is_active: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)
