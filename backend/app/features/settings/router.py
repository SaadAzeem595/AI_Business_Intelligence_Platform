from typing import List
from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, MockUser, require_role
from app.features.settings.schemas import (
    WorkspaceInput,
    ProfileInput,
    BillingInput,
    InvoiceResponse,
    TeamMemberResponse,
    APIKeyResponse,
)

router = APIRouter(prefix="/settings", tags=["Workspace & Account Settings"], dependencies=[Depends(require_role(["Admin"]))])


@router.patch("/workspace")
async def update_workspace(
    payload: WorkspaceInput,
    current_user: MockUser = Depends(get_current_user),
) -> dict:
    """Updates active workspace credentials."""
    return {"status": "success"}


@router.patch("/profile")
async def update_profile(
    payload: ProfileInput,
    current_user: MockUser = Depends(get_current_user),
) -> dict:
    """Updates user information profile records."""
    return {"status": "success"}


@router.get("/billing", response_model=List[InvoiceResponse])
async def list_invoices(
    current_user: MockUser = Depends(get_current_user),
) -> List[InvoiceResponse]:
    """Returns past billing history invoices lists."""
    return [
        InvoiceResponse(invoiceId="INV-9021", amount="$79.00", date="2026-08-01", status="Paid"),
        InvoiceResponse(invoiceId="INV-7801", amount="$79.00", date="2026-07-01", status="Paid"),
        InvoiceResponse(invoiceId="INV-6204", amount="$79.00", date="2026-06-01", status="Paid"),
    ]


@router.post("/billing")
async def update_billing(
    payload: BillingInput,
    current_user: MockUser = Depends(get_current_user),
) -> dict:
    """Binds card metadata details to workspace subscriptions billing."""
    return {"status": "success"}


@router.get("/team", response_model=List[TeamMemberResponse])
async def list_team_members(
    current_user: MockUser = Depends(get_current_user),
) -> List[TeamMemberResponse]:
    """Exposes all active workspace collaborators emails."""
    return [
        TeamMemberResponse(name="Saad Alvi", email="saad@example.com", role="Owner"),
        TeamMemberResponse(name="Alex Mercer", email="alex@company.com", role="Admin"),
        TeamMemberResponse(name="Sarah Connor", email="sarah@company.com", role="Viewer"),
    ]


@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: MockUser = Depends(get_current_user),
) -> List[APIKeyResponse]:
    """Returns active tokens identifiers prefixes logs."""
    return [
        APIKeyResponse(id="1", name="Production duckdb link", keyPrefix="ag_live_••••••k91z", created="2026-08-01"),
        APIKeyResponse(id="2", name="AI agent chat token", keyPrefix="ag_live_••••••x32a", created="2026-07-28"),
    ]


@router.post("/api-keys", response_model=APIKeyResponse)
async def generate_api_key(
    name: str,
    current_user: MockUser = Depends(get_current_user),
) -> APIKeyResponse:
    """Generates new programmatic API key mappings."""
    return APIKeyResponse(
        id=str(uuid.uuid4()),
        name=name,
        keyPrefix="ag_live_••••••w40q",
        created=datetime.now().strftime("%Y-%m-%d"),
    )


@router.delete("/api-keys/{id}")
async def revoke_api_key(
    id: str,
    current_user: MockUser = Depends(get_current_user),
) -> dict:
    """Deletes API key identifiers mapping records."""
    return {"status": "success"}


@router.get("/notifications")
async def list_notifications(
    current_user: MockUser = Depends(get_current_user),
) -> List[dict]:
    """Returns recent alerts list details."""
    return [
        {"id": "1", "title": "Dataset uploaded successfully", "description": "Your file `q3_financials.xlsx` was processed.", "date": "5m ago", "read": False},
        {"id": "2", "title": "AI Analysis Complete", "description": "Anomaly checks flagged 2 outliers.", "date": "1h ago", "read": False},
    ]


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    current_user: MockUser = Depends(get_current_user),
) -> dict:
    """Marks all notifications logs read status flags true."""
    return {"status": "success"}
