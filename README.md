# AI Code Manager Studio

An AI-powered code management studio with GitHub integration. Generate code using DeepSeek AI and push it directly to GitHub repositories.

## Features

- 🤖 AI-powered code generation using DeepSeek API
- 💬 ChatGPT-style chat interface with dark theme
- 📦 Session management for multiple conversations
- 🐙 Push generated code directly to GitHub repositories
- 📋 Copy code blocks with one click
- 🎨 Beautiful dark theme UI with animations

## Setup

### Prerequisites

- Python 3.8+
- DeepSeek API key
- GitHub Personal Access Token

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-code-manager-studio
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file from the example:
```bash
cp .env.example .env
```

4. Edit `.env` and add your API keys:
```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
GITHUB_TOKEN=your_github_personal_access_token_here
```

### Running the Application

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Or simply:
```bash
python app.py
```

Open your browser and navigate to `http://localhost:8000`

## Usage

1. **Start a new chat**: Click "+ New Chat" button in the sidebar
2. **Generate code**: Type your code request (e.g., "Create a Python function to sort a list")
3. **Copy code**: Click the "Copy" button on any code block
4. **Push to GitHub**: Click "Push to GitHub" button, enter a repository name
5. **View history**: Click on previous sessions in the sidebar

## API Endpoints

- `GET /` - Main page
- `POST /api/chat` - Send message to AI
- `GET /api/sessions` - List all sessions
- `POST /api/sessions` - Create new session
- `GET /api/sessions/{id}/messages` - Get session messages
- `POST /api/push-to-github` - Push code to GitHub

## Tech Stack

- **Backend**: FastAPI (Python)
- **AI**: DeepSeek API
- **Database**: SQLite with SQLAlchemy (async)
- **Frontend**: HTML, CSS, JavaScript
- **GitHub**: PyGithub library

## License

MIT
