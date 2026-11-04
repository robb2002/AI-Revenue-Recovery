from fastapi import APIRouter

from app.api.deps import CurrentUserDep

router = APIRouter(tags=["auth"])


@router.get("/me")
async def me(user: CurrentUserDep) -> dict:
    return {
        "user_id": str(user.user_id),
        "clerk_user_id": user.clerk_user_id,
        "email": user.email,
        "role": user.role,
    }
