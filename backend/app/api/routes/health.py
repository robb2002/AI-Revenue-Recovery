from fastapi import APIRouter, Request
from sqlalchemy import text

from app.core.config import get_settings

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health(request: Request) -> dict:
    settings = get_settings()
    database = "ok"
    crm_rows = None
    as_of = settings.demo_as_of_date
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("select 1"))
            result = await session.execute(text("select count(*), max(as_of_date)::text from crm_master"))
            row = result.one()
            crm_rows = int(row[0])
            if row[1]:
                as_of = row[1]
    except Exception:
        database = "error"

    return {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "as_of_date": as_of,
        "crm_rows": crm_rows,
        "version": "0.1.0",
    }
