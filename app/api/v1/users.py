"""User routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current user's profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update current user's profile."""
    update_data = user_update.model_dump(exclude_unset=True)

    if not update_data:
        return UserResponse.model_validate(current_user)

    # Check username uniqueness if updating
    if "username" in update_data:
        existing = await db.execute(
            select(User).where(
                User.username == update_data["username"],
                User.id != current_user.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

    # Update user
    for key, value in update_data.items():
        setattr(current_user, key, value)

    await db.flush()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)
