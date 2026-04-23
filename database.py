import uuid
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Boolean, Index
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool

from config import settings

# Create engine with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
)

async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


class ChatSession(Base):
    """Chat session model"""
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, default="New Chat")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="session", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_sessions_created_at", "created_at"),
    )


class Message(Base):
    """Message model for chat history"""
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    code = Column(Text, nullable=True)
    language = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index("idx_messages_session_id", "session_id"),
        Index("idx_messages_created_at", "created_at"),
        Index("idx_messages_role", "role"),
    )


class Project(Base):
    """GitHub project model"""
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    repo_url = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    files_count = Column(Integer, default=0)
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="projects")
    
    # Indexes
    __table_args__ = (
        Index("idx_projects_created_at", "created_at"),
        Index("idx_projects_name", "name"),
    )


class ApiUsage(Base):
    """API usage tracking for analytics"""
    __tablename__ = "api_usage"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=False)
    client_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_api_usage_created_at", "created_at"),
        Index("idx_api_usage_endpoint", "endpoint"),
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
