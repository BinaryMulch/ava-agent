"""
Ava Agent - Configuration
All settings are loaded from environment variables or .env file.
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# xAI Grok API settings
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-3-latest")

# Server settings
HOST = os.getenv("AVA_HOST", "127.0.0.1")
PORT = int(os.getenv("AVA_PORT", "8888"))

# Database
DB_PATH = BASE_DIR / "data" / "conversations.db"

# Git update settings
REPO_DIR = BASE_DIR
SERVICE_NAME = os.getenv("AVA_SERVICE_NAME", "ava-agent")

# System prompt
SYSTEM_PROMPT_FILE = BASE_DIR / "system_prompt.md"


def load_system_prompt() -> str:
    """Load system prompt from file, re-reading each call for hot reload."""
    try:
        return SYSTEM_PROMPT_FILE.read_text().strip()
    except (FileNotFoundError, PermissionError) as e:
        raise RuntimeError(f"Failed to load system prompt from {SYSTEM_PROMPT_FILE}: {e}") from e

# Command execution settings
COMMAND_TIMEOUT = int(os.getenv("AVA_COMMAND_TIMEOUT", "300"))  # 5 minutes default
