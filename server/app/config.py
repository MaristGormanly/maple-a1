"""
Central Configuration Management for maple-a1

This module manages all environment variables and application settings for the maple-a1 backend.
It uses `pydantic-settings` to automatically load, validate, and type-cast environment variables 
(typically from a `.env` file or the system environment).

Significance to maple-a1:
1. Fail-Fast Validation: If critical environment variables (like DATABASE_URL or SECRET_KEY) are 
   missing or incorrectly typed, the application will crash immediately on startup rather than 
   failing unpredictably later.
2. Single Source of Truth: Instead of using `os.getenv()` scattered throughout the codebase, 
   all configuration is accessed via the globally instantiated `settings` object defined here.
3. Type Safety: Pydantic ensures that variables like APP_PORT are integers, preventing type errors.
"""

from pathlib import Path
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    """
    Application settings model.
    
    Each attribute corresponds to an environment variable. Attributes without a default value 
    (like DATABASE_URL and SECRET_KEY) are strictly required.
    """
    
    # --- Database Configuration ---
    # The connection string for the primary database (e.g., PostgreSQL).
    DATABASE_URL: str
    
    # --- Application Configuration ---
    # Defines the environment the app is running in (e.g., "development", "production", "test").
    APP_ENV: str = "development"
    # The host IP the FastAPI server will bind to.
    APP_HOST: str = "0.0.0.0"
    # The port the FastAPI server will listen on.
    APP_PORT: int = 8000
    
    # --- Authentication & Security ---
    # The secret key used to sign JSON Web Tokens (JWTs). Must be kept secure and never committed.
    SECRET_KEY: str
    # The hashing algorithm used for JWTs.
    ALGORITHM: str = "HS256"
    # How long an access token remains valid before the user must re-authenticate.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # --- External Services ---
    # Key used to encrypt per-instructor GitHub Personal Access Tokens at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    GITHUB_TOKEN_ENCRYPTION_KEY: str = ""
    
    # --- Docker Configuration ---
    # The Docker daemon socket URL. Default is the standard Linux UNIX socket.
    DOCKER_SOCKET_URL: str = "unix:///var/run/docker.sock"
    # Optional absolute host checkout path used when this app runs in a container
    # but creates sibling sandbox containers through the host Docker socket.
    DOCKER_HOST_PROJECT_ROOT: str = ""
    # Fallback image when no language-specific image is specified.
    DOCKER_DEFAULT_IMAGE: str = "python:3.12-slim"
    # Default timeout (seconds) to wait for a container to finish before giving up.
    DOCKER_CONTAINER_TIMEOUT: int = 60

    # --- LLM Configuration ---
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    LLM_TIMEOUT_STANDARD: int = 30
    LLM_TIMEOUT_COMPLEX: int = 60
    LLM_MAX_RETRIES: int = 2
    LLM_BACKOFF_BASE: float = 1.0

    # --- CORS (Cross-Origin Resource Sharing) ---
    # Defines which frontend domains are allowed to make requests to this backend API.
    # Can be a single string (comma-separated) or a list of strings.
    CORS_ORIGINS: str | List[str] = ["http://localhost:4200"]
    
    @property
    def cors_origins_list(self) -> List[str]:
        """
        Helper property to ensure CORS origins are always returned as a list.
        
        Since environment variables are strings, a list of origins in a `.env` file 
        is often provided as a comma-separated string (e.g., "http://localhost:4200,https://maple.app").
        This property parses that string into a proper Python list for FastAPI's CORS middleware.
        """
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS

    @model_validator(mode="after")
    def _reject_wildcard_cors_in_production(self) -> "Settings":
        if self.APP_ENV == "production" and "*" in self.cors_origins_list:
            raise ValueError(
                "CORS_ORIGINS must not contain '*' when APP_ENV=production "
                "(M4.A.4 — no wildcard in production)."
            )
        if self.APP_ENV == "production" and not self.GITHUB_TOKEN_ENCRYPTION_KEY:
            raise ValueError(
                "GITHUB_TOKEN_ENCRYPTION_KEY must be set when APP_ENV=production."
            )
        return self

    # Pydantic model configuration
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", SERVER_ROOT / ".env"),
        env_file_encoding="utf-8",   # Read the .env file using UTF-8 encoding
        case_sensitive=True,         # Environment variables must match the exact case defined above
        extra="ignore"               # Ignore extra environment variables not defined in this class
    )

# Global singleton instance of the Settings class.
# Import this `settings` object in other modules to access configuration values.
# Example: `from server.app.config import settings; print(settings.DATABASE_URL)`
settings = Settings()
