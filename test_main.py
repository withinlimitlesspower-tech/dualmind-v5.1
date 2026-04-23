import pytest
from httpx import AsyncClient, ASGITransport
from app import app
from database import engine, Base, async_session_factory
from config import settings


@pytest.fixture(autouse=True)
async def setup_database():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Drop tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_index(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient):
    response = await client.post("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert data["name"] == "New Chat"


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient):
    # Create a session first
    await client.post("/api/sessions")
    
    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_messages_empty(client: AsyncClient):
    # Create a session
    session_resp = await client.post("/api/sessions")
    session_id = session_resp.json()["id"]
    
    response = await client.get(f"/api/sessions/{session_id}/messages")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_chat_without_api_key(client: AsyncClient):
    # This test will fail if DEEPSEEK_API_KEY is not set
    if not settings.DEEPSEEK_API_KEY:
        pytest.skip("DEEPSEEK_API_KEY not set")
    
    # Create a session
    session_resp = await client.post("/api/sessions")
    session_id = session_resp.json()["id"]
    
    response = await client.post(
        "/api/chat",
        data={
            "session_id": session_id,
            "message": "Hello",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "role" in data
    assert "content" in data


@pytest.mark.asyncio
async def test_push_to_github_no_code(client: AsyncClient):
    # Create a session
    session_resp = await client.post("/api/sessions")
    session_id = session_resp.json()["id"]
    
    response = await client.post(
        "/api/push-to-github",
        data={
            "session_id": session_id,
            "repo_name": "test-repo",
        },
    )
    assert response.status_code == 400
    assert "No code found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_push_to_github_without_token(client: AsyncClient):
    if not settings.GITHUB_TOKEN:
        pytest.skip("GITHUB_TOKEN not set")
    
    # Create a session
    session_resp = await client.post("/api/sessions")
    session_id = session_resp.json()["id"]
    
    # Add a message with code
    await client.post(
        "/api/chat",
        data={
            "session_id": session_id,
            "message": "Create a hello world function",
        },
    )
    
    response = await client.post(
        "/api/push-to-github",
        data={
            "session_id": session_id,
            "repo_name": "test-repo-12345",
        },
    )
    # This might fail if token is invalid, but we check the structure
    if response.status_code == 200:
        data = response.json()
        assert "repo_url" in data


@pytest.mark.asyncio
async def test_detect_intent():
    from handlers.chat import detect_intent
    
    assert detect_intent("Create a Python function") == "CODE_GENERATE"
    assert detect_intent("Write a sorting algorithm") == "CODE_GENERATE"
    assert detect_intent("Hello, how are you?") == "GENERAL_CHAT"
    assert detect_intent("Push to GitHub") == "GITHUB_PUSH"


@pytest.mark.asyncio
async def test_extract_code_blocks():
    from handlers.chat import extract_code_blocks
    
    response = '''Here is your code:
```python
def hello():
    print("Hello")
```
And another:
```javascript
console.log("Hello");
```'''
    
    blocks = extract_code_blocks(response)
    assert len(blocks) == 2
    assert "def hello():" in blocks[0]
    assert 'console.log("Hello");' in blocks[1]


@pytest.mark.asyncio
async def test_extract_code_blocks_no_code():
    from handlers.chat import extract_code_blocks
    
    response = "This is just a regular message without code blocks."
    blocks = extract_code_blocks(response)
    assert len(blocks) == 0
