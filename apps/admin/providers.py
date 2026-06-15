from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_providers():
    return {"providers": []}


@router.get("/{provider_name}/status")
async def provider_status(provider_name: str):
    return {"provider": provider_name, "status": "unknown"}
