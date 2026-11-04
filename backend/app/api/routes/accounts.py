from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, SessionDep
from app.core.errors import NotFoundError
from app.repositories.crm_master import CrmMasterRepository

router = APIRouter(tags=["accounts"])

DATA_LABEL = "Fictional demo data"


@router.get("/accounts")
async def list_accounts(
    _user: CurrentUserDep,
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    repo = CrmMasterRepository(session)
    items, total = await repo.list_accounts(limit=limit, offset=offset)
    as_of = items[0]["as_of_date"] if items else None
    return {
        "items": [{**item, "data_label": DATA_LABEL} for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "as_of_date": as_of,
        "data_label": DATA_LABEL,
    }


@router.get("/accounts/{account_id}")
async def get_account(account_id: str, _user: CurrentUserDep, session: SessionDep) -> dict:
    repo = CrmMasterRepository(session)
    account = await repo.get_account(account_id)
    if account is None:
        raise NotFoundError("account")
    return {**account, "data_label": DATA_LABEL}
