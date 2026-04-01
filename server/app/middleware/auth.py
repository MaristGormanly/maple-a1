"""
Authentication and Authorization Middleware for maple-a1

This module provides the core security layer for the maple-a1 project's FastAPI backend.
It is responsible for protecting sensitive API endpoints (such as code evaluation and 
administrative routes) by ensuring that only authenticated and authorized users can access them.

Key Responsibilities:
1. Token Extraction: Uses OAuth2 with Password Flow (Bearer token) to extract JWTs from incoming requests.
2. Authentication: Validates the JWT access token to ensure the user is who they claim to be.
3. Role-Based Access Control (RBAC): Provides dependency injectors to restrict endpoints to specific user roles (e.g., 'admin', 'user').

How it fits into maple-a1:
When a user logs in via the `/api/v1/code-eval/auth/login` endpoint, they receive a JWT.
Any subsequent requests to protected routes must include this token in the `Authorization` header.
This module intercepts those requests, decodes the token using utility functions from `server.app.utils.security`,
and either grants access (passing user details to the route) or rejects it with a 401/403 HTTP error.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Callable
from ..utils.security import decode_access_token

# Defines the security scheme for FastAPI's auto-generated OpenAPI documentation (Swagger UI).
# It tells the client where to send credentials to obtain a bearer token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/code-eval/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI Dependency that extracts and validates the current user's JWT token.
    
    This function is injected into protected routes. It automatically extracts the Bearer token
    from the request header, decodes it, and returns the token payload (user data).
    
    Args:
        token (str): The JWT bearer token extracted by `oauth2_scheme`.
        
    Returns:
        dict: The decoded JWT payload containing user information (like user ID and role).
        
    Raises:
        HTTPException (401): If the token is missing, invalid, expired, or cannot be decoded.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Attempt to decode the token to verify its authenticity and extract user data
        payload = decode_access_token(token)
        if payload is None:
            raise credentials_exception
        return payload
    except ValueError:
        # Catch any decoding errors (e.g., malformed token, signature mismatch)
        raise credentials_exception

def require_role(required_role: str) -> Callable:
    """
    Dependency factory for Role-Based Access Control (RBAC).
    
    Creates a FastAPI dependency that ensures the authenticated user has a specific role
    before allowing access to an endpoint. This is crucial for restricting administrative
    or sensitive actions in maple-a1.
    
    Args:
        required_role (str): The role string required to access the endpoint (e.g., "admin").
        
    Returns:
        Callable: An asynchronous dependency function to be used in FastAPI route definitions.
        
    Example:
        @app.get("/admin/data", dependencies=[Depends(require_role("admin"))])
        async def admin_data():
            return {"data": "secret"}
    """
    async def role_checker(current_user: dict = Depends(get_current_user)):
        # Check if the 'role' claim in the decoded JWT payload matches the required role
        if current_user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires {required_role} role"
            )
        return current_user
        
    return role_checker
