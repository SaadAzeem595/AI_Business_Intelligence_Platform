from pydantic import BaseModel, EmailStr, ConfigDict


class GenerateReportPayload(BaseModel):
    title: str
    type: str
    frequency: str
    recipient: EmailStr


class ReportResponse(BaseModel):
    id: str
    title: str
    type: str
    frequency: str
    created: str
    size: str
    recipient: EmailStr

    model_config = ConfigDict(from_attributes=True)
