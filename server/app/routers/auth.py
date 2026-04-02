from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import get_db
from ..models.user import User
from ..utils.responses import error_response, success_response
from ..utils.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "Student"


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    hashed = hash_password(request.password)
    user = User(
        email=request.email,
        password_hash=hashed,
        role=request.role,
    )

    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return error_response(
            status_code=409,
            code="CONFLICT",
            message=f"A user with email '{request.email}' already exists",
        )
    await db.refresh(user)

    return success_response({
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role,
    })


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        return error_response(
            status_code=401,
            code="AUTH_ERROR",
            message="Invalid email or password",
        )

    if not verify_password(request.password, user.password_hash):
        return error_response(
            status_code=401,
            code="AUTH_ERROR",
            message="Invalid email or password",
        )

    token = create_access_token({"sub": str(user.id), "role": user.role})

    return success_response({
        "access_token": token,
        "token_type": "bearer",
    })
