from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.core.config import get_settings
from app.repositories.crm_master import CrmMasterRepository

router = APIRouter(tags=["data"])


@router.get("/data/status")
async def data_status(_user: CurrentUserDep, session: SessionDep) -> dict:
    repo = CrmMasterRepository(session)
    settings = get_settings()
    count = await repo.count_rows()
    as_of = await repo.as_of_date() or settings.demo_as_of_date
    return {
        "schema": "revenue_recovery",
        "table": "crm_master",
        "crm_rows": count,
        "as_of_date": as_of,
        "data_label": "Fictional demo data",
        "kb_path": "backend/data/crm_master/knowledge_base",
        "sample_meetings_path": "backend/data/crm_master/sample_meetings",
    }
