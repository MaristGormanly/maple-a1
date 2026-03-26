from fastapi import APIRouter
from pydantic import BaseModel
from server.app.utils.responses import error_response

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "Student"

@router.post("/login")
async def login(request: LoginRequest):
    return error_response(
        status_code=501,
        code="NOT_IMPLEMENTED",
        message="Login endpoint not yet implemented. Waiting for User model.",
    )

@router.post("/register")
async def register(request: RegisterRequest):
    return error_response(
        status_code=501,
        code="NOT_IMPLEMENTED",
        message="Registration endpoint not yet implemented. Waiting for User model.",
    )
