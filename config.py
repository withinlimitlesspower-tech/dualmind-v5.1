import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # API Keys
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///studio.db")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # CORS - Configure for production
    ALLOWED_ORIGINS: List[str] = os.getenv(
        "ALLOWED_ORIGINS", 
        "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    
    # DeepSeek API
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT: int = int(os.getenv("DEEPSEEK_TIMEOUT", "30"))
    
    # GitHub
    GITHUB_API_URL: str = "https://api.github.com"
    GITHUB_DEFAULT_BRANCH: str = "main"
    
    # Application
    APP_NAME: str = "AI Code Manager Studio"
    APP_VERSION: str = "2.0.0"
    MAX_CODE_FILES: int = int(os.getenv("MAX_CODE_FILES", "50"))
    
    # Validate required settings on startup
    @classmethod
    def validate(cls):
        """Validate critical settings"""
        warnings = []
        if not cls.DEEPSEEK_API_KEY or cls.DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
            warnings.append("DEEPSEEK_API_KEY not set - AI features will not work")
        if not cls.GITHUB_TOKEN or cls.GITHUB_TOKEN == "your_github_personal_access_token_here":
            warnings.append("GITHUB_TOKEN not set - GitHub push features will not work")
        return warnings


settings = Settings()
