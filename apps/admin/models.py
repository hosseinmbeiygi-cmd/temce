from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_models():
    return {"models": []}


@router.post("/{model_id}/promote")
async def promote_model(model_id: str):
    return {"model": model_id, "status": "promoted"}
