import re
from typing import List, Optional

import httpx

from config import settings

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def detect_intent(message: str) -> str:
    """Detect the intent of the user message."""
    code_keywords = [
        "code", "function", "class", "script", "program", "algorithm",
        "implement", "write", "generate", "create", "build", "develop",
        "python", "javascript", "typescript", "java", "go", "rust",
    ]
    message_lower = message.lower()
    
    if any(keyword in message_lower for keyword in code_keywords):
        return "CODE_GENERATE"
    elif "github" in message_lower or "push" in message_lower:
        return "GITHUB_PUSH"
    else:
        return "GENERAL_CHAT"


async def deepseek_chat(message: str, intent: str) -> str:
    """Send message to DeepSeek API and get response."""
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    
    system_prompt = "You are an AI coding assistant. Help users with programming questions and code generation."
    if intent == "CODE_GENERATE":
        system_prompt = "You are an expert programmer. Generate clean, well-documented code. Always include the code in a code block."
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def generate_code(message: str) -> str:
    """Generate code using DeepSeek API."""
    return await deepseek_chat(message, "CODE_GENERATE")


def extract_code_blocks(response: str) -> List[str]:
    """Extract code blocks from the response."""
    pattern = r"```(?:\w+)?\n([\s\S]*?)```"
    matches = re.findall(pattern, response)
    return [match.strip() for match in matches]
