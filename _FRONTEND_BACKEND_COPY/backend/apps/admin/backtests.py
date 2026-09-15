from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_backtests():
    return {"backtests": []}


@router.post("/run")
async def run_backtest():
    return {"status": "started"}
