import os
from dotenv import load_dotenv

# Load .env file if exists (local development)
load_dotenv()


class Settings:
    # Try to get from Replit Secrets first, then from environment variables
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
    GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "") or os.getenv("GITHUB_TOKEN", "")
    
    # Database - Use Replit persistent storage
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///studio.db")
    
    # Server settings
    PORT: int = int(os.environ.get("PORT", "8000"))
    HOST: str = "0.0.0.0"


settings = Settings()

# Debug output (remove in production)
if settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_KEY != "your_deepseek_api_key_here":
    print("✅ DeepSeek API key loaded from Secrets")
else:
    print("⚠️  DeepSeek API key not found in Secrets")

if settings.GITHUB_TOKEN and settings.GITHUB_TOKEN != "your_github_personal_access_token_here":
    print("✅ GitHub token loaded from Secrets")
else:
    print("⚠️  GitHub token not found in Secrets")