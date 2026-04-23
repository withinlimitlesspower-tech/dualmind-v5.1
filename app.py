import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from config import settings
from database import engine, get_db, Base, Session as DBSession, Message, Project
from handlers.chat import detect_intent, deepseek_chat, generate_code, extract_code_blocks
from handlers.github import push_to_github

app = FastAPI(title="AI Code Manager Studio", lifespan="on")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat")
async def chat(
    request: Request,
    session_id: str = Form(...),
    message: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    # Get or create session
    result = await db.execute(select(DBSession).where(DBSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        session = DBSession(id=session_id, name=message[:50])
        db.add(session)
        await db.commit()
        await db.refresh(session)

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

    # Get AI response
    if intent == "CODE_GENERATE":
        ai_response = await generate_code(message)
        code_blocks = extract_code_blocks(ai_response)
        code_content = "\n\n".join(code_blocks) if code_blocks else None
    else:
        ai_response = await deepseek_chat(message, intent)
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

    return {
        "id": ai_msg.id,
        "role": "assistant",
        "content": ai_response,
        "code": code_content,
        "created_at": ai_msg.created_at.isoformat(),
    }


@app.get("/api/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DBSession).order_by(DBSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


@app.post("/api/sessions")
async def create_session(db: AsyncSession = Depends(get_db)):
    session_id = str(uuid.uuid4())
    session = DBSession(id=session_id, name="New Chat")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {
        "id": session.id,
        "name": session.name,
        "created_at": session.created_at.isoformat(),
    }


@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "code": m.code,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@app.post("/api/push-to-github")
async def push_to_github_endpoint(
    request: Request,
    session_id: str = Form(...),
    repo_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
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

    # Prepare files
    files = {}
    for i, msg in enumerate(messages):
        if msg.code:
            filename = f"generated_code_{i+1}.py"
            files[filename] = msg.code

    # Push to GitHub
    try:
        repo_url = push_to_github(files, repo_name, settings.GITHUB_TOKEN)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Save project
    project = Project(
        session_id=session_id,
        name=repo_name,
        repo_url=repo_url,
    )
    db.add(project)
    await db.commit()

    return {"repo_url": repo_url, "message": f"Code pushed to {repo_url}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
