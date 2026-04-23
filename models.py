from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl, validator


class ChatRequest(BaseModel):
    """Chat request model"""
    session_id: str = Field(..., min_length=1, max_length=36)
    message: str = Field(..., min_length=1, max_length=4000)
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Create a Python function to sort a list"
            }
        }


class GitHubPushRequest(BaseModel):
    """GitHub push request model"""
    session_id: str = Field(..., min_length=1, max_length=36)
    repo_name: str = Field(..., min_length=1, max_length=100, pattern="^[a-zA-Z0-9_.-]+$")
    description: Optional[str] = Field(None, max_length=500)
    is_private: bool = False
    
    @validator('repo_name')
    def validate_repo_name(cls, v):
        if ' ' in v:
            raise ValueError('Repository name cannot contain spaces')
        return v.lower()


class MessageResponse(BaseModel):
    """Message response model"""
    id: str
    role: str
    content: str
    code: Optional[str]
    created_at: str


class SessionResponse(BaseModel):
    """Session response model"""
    id: str
    name: str
    created_at: str
    message_count: Optional[int] = 0


class ProjectResponse(BaseModel):
    """Project response model"""
    id: str
    name: str
    repo_url: HttpUrl
    description: Optional[str]
    files_count: int
    created_at: str


class ApiResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
