from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def dashboard_overview():
    return {"status": "operational", "services": []}


@router.get("/health")
async def dashboard_health():
    return {"status": "ok"}
