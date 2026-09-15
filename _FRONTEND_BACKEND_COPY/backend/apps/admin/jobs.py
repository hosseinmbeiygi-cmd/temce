from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_jobs():
    return {"jobs": []}


@router.post("/{job_name}/run")
async def run_job(job_name: str):
    return {"job": job_name, "status": "started"}


@router.get("/{job_name}/history")
async def job_history(job_name: str):
    return {"job": job_name, "history": []}
