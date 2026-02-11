"""
Application Configuration - MemAgent

Loads environment variables and provides application settings using Pydantic.
All ports have been standardized: Frontend=3002, Backend=8000
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Google API Keys
    google_api_key: str = Field(..., description="Google Gemini API key")
    google_auth_client_id: str = Field(..., description="Google OAuth client ID")
    google_auth_client_secret: str = Field(..., description="Google OAuth client secret")
    google_places_api_key: str | None = Field(None, description="Google Places API key for location resolution")
    google_maps_api_key: str | None = Field(None, description="Google Maps API key")
    
    # Database
    database_url: str = Field(default="sqlite:///./memagent.db", description="Database connection URL")
    
    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production", description="Secret key for session management")
    
    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:3002", "http://localhost:8000"], description="Allowed CORS origins")
    
    # Frontend URL
    frontend_url: str = Field(default="http://localhost:3002", description="Frontend application URL for OAuth redirects")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Token Budgets
    max_tokens_per_session: int = Field(default=15000, description="Maximum tokens per session")
    max_tokens_per_user_daily: int = Field(default=50000, description="Maximum tokens per user per day")
    token_warning_threshold: float = Field(default=0.8, description="Warning threshold for token usage (0-1)")
    
    # Rate Limiting
    max_memories_per_day: int = Field(default=10, description="Maximum memories a user can create per day")
    
    # Temp Storage
    temp_image_dir: str = Field(default="./tmp/images", description="Directory for temporary image storage")
    
    model_config = SettingsConfigDict(
        env_file="../.env.local",  # Load from project root
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
