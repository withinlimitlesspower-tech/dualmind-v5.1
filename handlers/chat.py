import re
import json
import logging
from typing import List, Tuple
import httpx
from config import settings

logger = logging.getLogger(__name__)

# System prompts for different intents
SYSTEM_PROMPTS = {
    "CODE_GENERATE": """You are an expert programmer. Generate clean, efficient, and well-documented code. 
    Include error handling and follow best practices. Format code blocks with proper language tags.""",
    
    "GENERAL_CHAT": """You are a helpful AI assistant focused on programming and software development. 
    Provide clear, accurate, and practical answers.""",
    
    "GITHUB_PUSH": """You are helping with GitHub integration. Provide clear instructions about pushing code to GitHub."""
}

async def deepseek_chat(message: str, intent: str = "GENERAL_CHAT") -> str:
    """Send message to DeepSeek API and get response"""
    async with httpx.AsyncClient(timeout=settings.DEEPSEEK_TIMEOUT) as client:
        try:
            response = await client.post(
                settings.DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["GENERAL_CHAT"])},
                        {"role": "user", "content": message}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "top_p": 0.9,
                    "frequency_penalty": 0,
                    "presence_penalty": 0
                }
            )
            
            if response.status_code == 401:
                raise Exception("Invalid DeepSeek API key")
            elif response.status_code == 429:
                raise Exception("Rate limit exceeded. Please try again later")
            elif response.status_code != 200:
                raise Exception(f"DeepSeek API error: {response.status_code} - {response.text}")
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except httpx.TimeoutException:
            raise Exception("Request timeout. Please try again")
        except Exception as e:
            logger.error(f"DeepSeek API error: {str(e)}")
            raise

async def generate_code(prompt: str) -> str:
    """Generate code using DeepSeek API with enhanced prompts"""
    enhanced_prompt = f"""Generate production-ready code for the following request:
    
{prompt}

Requirements:
- Include proper error handling
- Add docstrings/comments
- Follow language best practices
- Make it reusable and modular
- Add type hints where applicable

Return only the code with proper formatting."""
    
    return await deepseek_chat(enhanced_prompt, "CODE_GENERATE")

def detect_intent(message: str) -> str:
    """Detect user intent from message"""
    message_lower = message.lower()
    
    # Code generation keywords
    code_keywords = [
        "create", "generate", "write code", "function", "class", "algorithm",
        "implement", "build", "develop", "script", "program", "api",
        "database", "query", "sort", "search", "calculate"
    ]
    
    # GitHub keywords
    github_keywords = [
        "push to github", "commit", "repository", "repo", "github",
        "upload to github", "deploy to github"
    ]
    
    # Check for code generation
    if any(keyword in message_lower for keyword in code_keywords):
        # Refine: check if it's actually asking for code
        if "not" not in message_lower[:50] or "without code" not in message_lower:
            return "CODE_GENERATE"
    
    # Check for GitHub actions
    if any(keyword in message_lower for keyword in github_keywords):
        return "GITHUB_PUSH"
    
    # Default to general chat
    return "GENERAL_CHAT"

def extract_code_blocks(response: str) -> List[str]:
    """Extract code blocks from AI response"""
    # Pattern for ```language\ncode``` or ```\ncode```
    pattern = r'```(?:\w+)?\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)
    
    if not matches:
        # Try to find inline code blocks
        inline_pattern = r'`([^`]+)`'
        inline_matches = re.findall(inline_pattern, response)
        if inline_matches and len(inline_matches[0]) > 20:  # Likely code
            return inline_matches
    
    # Clean up the extracted code
    cleaned_blocks = []
    for block in matches:
        # Remove leading/trailing whitespace
        block = block.strip()
        # Remove language identifiers if they appear in the block
        if block.startswith(('python', 'javascript', 'java', 'cpp', 'html', 'css')):
            lines = block.split('\n')
            block = '\n'.join(lines[1:]) if len(lines) > 1 else block
        cleaned_blocks.append(block)
    
    return cleaned_blocks

def detect_language_from_code(code: str) -> str:
    """Detect programming language from code content"""
    code_lower = code.lower()
    
    language_patterns = {
        'python': ['def ', 'import ', 'class ', 'self.', 'if __name__'],
        'javascript': ['function ', 'const ', 'let ', '=>', 'console.log'],
        'java': ['public class', 'public static void', 'System.out.println'],
        'cpp': ['#include', 'int main', 'std::', 'using namespace'],
        'html': ['<html', '<div', '<body', '<head'],
        'css': [':root', '@media', '{', '}', ';'],
        'sql': ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE TABLE'],
        'bash': ['#!/bin', 'echo', 'export', 'chmod'],
    }
    
    for language, patterns in language_patterns.items():
        if any(pattern in code_lower for pattern in patterns):
            return language
    
    return 'text'