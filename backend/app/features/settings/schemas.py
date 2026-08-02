from typing import Optional
from pydantic import BaseModel, EmailStr


class WorkspaceInput(BaseModel):
    name: str
    companyUrl: Optional[str] = None


class ProfileInput(BaseModel):
    name: str
    email: EmailStr


class BillingInput(BaseModel):
    plan: str
    cardNumber: str
    cvc: str
    expiry: str


class InvoiceResponse(BaseModel):
    invoiceId: str
    amount: str
    date: str
    status: str


class TeamMemberResponse(BaseModel):
    name: str
    email: EmailStr
    role: str


class APIKeyResponse(BaseModel):
    id: str
    name: str
    keyPrefix: str
    created: str
