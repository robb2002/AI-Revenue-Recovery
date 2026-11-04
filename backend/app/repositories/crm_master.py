from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CrmMasterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_rows(self) -> int:
        result = await self._session.scalar(text("select count(*) from crm_master"))
        return int(result or 0)

    async def as_of_date(self) -> str | None:
        result = await self._session.scalar(
            text("select as_of_date::text from crm_master limit 1")
        )
        return str(result) if result else None

    async def list_accounts(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        total = await self.count_rows()
        rows = (
            await self._session.execute(
                text(
                    """
                    select account_id, account_name, opportunity_name, deal_status,
                           deal_value, currency, risk_category, revenue_risk_score,
                           recovery_eligibility, as_of_date::text as as_of_date
                    from crm_master
                    order by account_name
                    limit :limit offset :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            )
        ).mappings().all()
        return [dict(r) for r in rows], total

    async def get_account(self, account_id: str) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                text(
                    """
                    select account_id, account_name, opportunity_id, opportunity_name,
                           deal_status, deal_value, currency, contact_name, contact_email,
                           risk_category, revenue_risk_score, recovery_eligibility,
                           recommended_next_action, as_of_date::text as as_of_date
                    from crm_master
                    where account_id = :account_id
                    """
                ),
                {"account_id": account_id},
            )
        ).mappings().first()
        return dict(row) if row else None
