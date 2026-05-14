import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import get_db
from ..models.user import User
from ..utils.responses import error_response, success_response
from ..utils.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,80}$")


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    username: str | None = Field(default=None, max_length=80)
    school: str | None = Field(default=None, max_length=160)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("Enter a valid email address")
        return email

    @field_validator("name", "school", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        username = value.strip().lower()
        if not username:
            return None
        if not _USERNAME_RE.match(username):
            raise ValueError("Username must be 3-80 letters, numbers, dots, dashes, or underscores")
        return username


class LoginRequest(BaseModel):
    email: str
    password: str


def _user_payload(user: User) -> dict:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "name": getattr(user, "name", None),
        "username": getattr(user, "username", None),
        "school": getattr(user, "school", None),
        "role": user.role,
    }


@router.post("/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    hashed = hash_password(request.password)
    user = User(
        email=request.email,
        name=request.name,
        username=request.username,
        school=request.school,
        password_hash=hashed,
        role="Instructor",
    )

    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return error_response(
            status_code=409,
            code="CONFLICT",
            message="A user with that email or username already exists",
        )
    await db.refresh(user)

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "name": getattr(user, "name", None),
    })

    return success_response({
        **_user_payload(user),
        "access_token": token,
        "token_type": "bearer",
    })


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(func.lower(User.email) == request.email.strip().lower()))
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

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "name": getattr(user, "name", None),
    })

    return success_response({
        "access_token": token,
        "token_type": "bearer",
        "user": _user_payload(user),
    })
