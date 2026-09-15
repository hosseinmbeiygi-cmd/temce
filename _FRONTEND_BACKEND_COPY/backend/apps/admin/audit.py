from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_audit_logs():
    return {"logs": []}


@router.get("/{log_id}")
async def audit_log_detail(log_id: str):
    return {"id": log_id, "action": "", "timestamp": "", "actor": ""}
