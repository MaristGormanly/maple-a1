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

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os

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
    # GitHub Personal Access Token, required by Sylvie's ingestion pipeline to clone
    # private student repositories. Must be present in the environment at startup.
    GITHUB_PAT: str
    
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

    # Pydantic model configuration
    model_config = SettingsConfigDict(
        env_file=".env",             # Look for a .env file in the root directory
        env_file_encoding="utf-8",   # Read the .env file using UTF-8 encoding
        case_sensitive=True,         # Environment variables must match the exact case defined above
        extra="ignore"               # Ignore extra environment variables not defined in this class
    )

# Global singleton instance of the Settings class.
# Import this `settings` object in other modules to access configuration values.
# Example: `from server.app.config import settings; print(settings.DATABASE_URL)`
settings = Settings()
