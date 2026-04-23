import os
import uuid
import logging
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings
from database import engine, get_db, Base, ChatSession, Message, Project
from handlers.chat import detect_intent, deepseek_chat, generate_code, extract_code_blocks
from handlers.github import push_to_github, validate_github_token
from models import ChatRequest, GitHubPushRequest, ApiResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup/shutdown events"""
    # Startup
    logger.info("Starting up AI Code Manager Studio...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Validate API keys
    if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
        logger.warning("DEEPSEEK_API_KEY not set or invalid. Code generation will not work.")
    if not settings.GITHUB_TOKEN or settings.GITHUB_TOKEN == "your_github_personal_access_token_here":
        logger.warning("GITHUB_TOKEN not set or invalid. GitHub push will not work.")
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await engine.dispose()

# Initialize FastAPI
app = FastAPI(
    title="AI Code Manager Studio",
    description="AI-powered code generation and management studio with GitHub integration",
    version="2.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - Production ready configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Health check endpoint
@app.get("/health", response_class=JSONResponse)
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }

# Main page
@app.get("/", response_class=HTMLResponse)
@limiter.limit("100/minute")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API Endpoints
@app.post("/api/chat", response_model=ApiResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to the AI and get response"""
    try:
        # Get or create session
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        
        if not session:
            # Create truncated name from first message
            name = message[:50] + "..." if len(message) > 50 else message
            session = ChatSession(id=session_id, name=name)
            db.add(session)
            await db.commit()
            await db.refresh(session)
            logger.info(f"Created new session: {session_id}")

        # Save user message
        user_msg = Message(
            session_id=session_id,
            role="user",
            content=message,
        )
        db.add(user_msg)
        await db.commit()

        # Detect intent
        intent = detect_intent(message)
        logger.info(f"Detected intent: {intent} for session {session_id}")

        # Get AI response with timeout handling
        try:
            if intent == "CODE_GENERATE":
                ai_response = await generate_code(message)
                code_blocks = extract_code_blocks(ai_response)
                code_content = "\n\n".join(code_blocks) if code_blocks else None
            else:
                ai_response = await deepseek_chat(message, intent)
                code_content = None
        except Exception as e:
            logger.error(f"AI API error: {str(e)}")
            ai_response = f"Sorry, I encountered an error: {str(e)}. Please check your API configuration."
            code_content = None

        # Save AI message
        ai_msg = Message(
            session_id=session_id,
            role="assistant",
            content=ai_response,
            code=code_content,
        )
        db.add(ai_msg)
        await db.commit()
        await db.refresh(ai_msg)

        return ApiResponse(
            success=True,
            data={
                "id": ai_msg.id,
                "role": "assistant",
                "content": ai_response,
                "code": code_content,
                "created_at": ai_msg.created_at.isoformat(),
            }
        )
    
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
@limiter.limit("100/minute")
async def list_sessions(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all chat sessions"""
    try:
        result = await db.execute(
            select(ChatSession)
            .order_by(ChatSession.created_at.desc())
            .limit(limit)
        )
        sessions = result.scalars().all()
        
        # Get message count for each session
        sessions_data = []
        for session in sessions:
            msg_count = await db.execute(
                select(func.count()).select_from(Message).where(Message.session_id == session.id)
            )
            sessions_data.append({
                "id": session.id,
                "name": session.name,
                "created_at": session.created_at.isoformat(),
                "message_count": msg_count.scalar() or 0
            })
        
        return {"success": True, "data": sessions_data}
    
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sessions")
@limiter.limit("20/minute")
async def create_session(request: Request, db: AsyncSession = Depends(get_db)):
    """Create a new chat session"""
    try:
        session_id = str(uuid.uuid4())
        session = ChatSession(id=session_id, name="New Chat")
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        logger.info(f"Created new session: {session_id}")
        
        return {
            "success": True,
            "data": {
                "id": session.id,
                "name": session.name,
                "created_at": session.created_at.isoformat(),
            }
        }
    
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
@limiter.limit("20/minute")
async def delete_session(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a session and all its messages"""
    try:
        # Delete messages first (cascade should handle this, but explicit is safer)
        await db.execute(delete(Message).where(Message.session_id == session_id))
        await db.execute(delete(Project).where(Project.session_id == session_id))
        result = await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
        
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        
        logger.info(f"Deleted session: {session_id}")
        return {"success": True, "message": "Session deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/messages")
@limiter.limit("100/minute")
async def get_messages(
    request: Request,
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """Get all messages for a session"""
    try:
        # Verify session exists
        session_result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        if not session_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Session not found")
        
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        messages = result.scalars().all()
        
        return {
            "success": True,
            "data": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "code": m.code,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/push-to-github")
@limiter.limit("10/minute")
async def push_to_github_endpoint(
    request: Request,
    session_id: str = Form(...),
    repo_name: str = Form(...),
    description: str = Form(""),
    is_private: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """Push generated code to GitHub repository"""
    try:
        # Validate GitHub token
        if not settings.GITHUB_TOKEN or settings.GITHUB_TOKEN == "your_github_personal_access_token_here":
            raise HTTPException(status_code=400, detail="GitHub token not configured")
        
        # Validate token
        token_valid = await validate_github_token(settings.GITHUB_TOKEN)
        if not token_valid:
            raise HTTPException(status_code=401, detail="Invalid GitHub token")
        
        # Get messages with code
        result = await db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.code.isnot(None),
                Message.code != "",
            )
            .order_by(Message.created_at.asc())
        )
        messages = result.scalars().all()

        if not messages:
            raise HTTPException(status_code=400, detail="No code found in this session")

        # Prepare files with smart naming
        files = {}
        code_count = 0
        for i, msg in enumerate(messages):
            if msg.code:
                # Try to extract filename from content
                language = detect_language(msg.code)
                filename = f"code_{i+1}.{language}"
                files[filename] = msg.code
                code_count += 1

        logger.info(f"Pushing {code_count} files to GitHub repo: {repo_name}")

        # Push to GitHub
        try:
            repo_url = await push_to_github(
                files=files,
                repo_name=repo_name,
                token=settings.GITHUB_TOKEN,
                description=description,
                private=is_private
            )
        except Exception as e:
            logger.error(f"GitHub push error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"GitHub error: {str(e)}")

        # Save project record
        project = Project(
            session_id=session_id,
            name=repo_name,
            repo_url=repo_url,
            description=description,
            files_count=code_count
        )
        db.add(project)
        await db.commit()

        logger.info(f"Successfully pushed code to {repo_url}")

        return {
            "success": True,
            "data": {
                "repo_url": repo_url,
                "message": f"Successfully pushed {code_count} files to {repo_url}",
                "files_count": code_count
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Push to GitHub error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects")
@limiter.limit("50/minute")
async def list_projects(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List all GitHub projects"""
    try:
        result = await db.execute(
            select(Project).order_by(Project.created_at.desc())
        )
        projects = result.scalars().all()
        
        return {
            "success": True,
            "data": [
                {
                    "id": p.id,
                    "name": p.name,
                    "repo_url": p.repo_url,
                    "description": p.description,
                    "files_count": p.files_count,
                    "created_at": p.created_at.isoformat(),
                }
                for p in projects
            ]
        }
    
    except Exception as e:
        logger.error(f"Error listing projects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def detect_language(code: str) -> str:
    """Detect programming language from code"""
    code_lower = code.lower()
    
    if "def " in code or "import " in code:
        return "py"
    elif "function " in code or "const " in code or "let " in code:
        return "js"
    elif "class " in code and "public static void main" in code:
        return "java"
    elif "#include" in code:
        return "cpp"
    elif "SELECT" in code.upper():
        return "sql"
    elif "<html" in code_lower:
        return "html"
    else:
        return "txt"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
