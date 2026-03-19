"""
Ava Agent - Configuration
All settings are loaded from environment variables or .env file.
"""

import os
import logging
import logging.handlers
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Logging
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_FILE = LOG_DIR / "ava-agent.log"
LOG_LEVEL = os.getenv("AVA_LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = int(os.getenv("AVA_LOG_MAX_BYTES", str(5 * 1024 * 1024)))  # 5 MB default
LOG_BACKUP_COUNT = int(os.getenv("AVA_LOG_BACKUP_COUNT", "5"))  # Keep 5 rotated files


def setup_logging() -> None:
    """Configure logging with file rotation and console output."""
    root = logging.getLogger()
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Formatter
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        str(LOG_FILE),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Console handler (for journalctl / dev)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    # Quiet down noisy libraries
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# xAI Grok API settings
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4-1-fast-reasoning")

# Server settings
HOST = os.getenv("AVA_HOST", "0.0.0.0")
PORT = int(os.getenv("AVA_PORT", "8888"))

# Database
DB_PATH = BASE_DIR / "data" / "conversations.db"

# Uploads
UPLOADS_DIR = BASE_DIR / "data" / "uploads"

# Git update settings
REPO_DIR = BASE_DIR
SERVICE_NAME = os.getenv("AVA_SERVICE_NAME", "ava-agent")

# System prompt
SYSTEM_PROMPT_FILE = BASE_DIR / "system_prompt.md"

# Skills directory
SKILLS_DIR = BASE_DIR / "skills"


def load_system_prompt() -> str:
    """Load system prompt from file, re-reading each call for hot reload."""
    try:
        return SYSTEM_PROMPT_FILE.read_text().strip()
    except (FileNotFoundError, PermissionError) as e:
        raise RuntimeError(f"Failed to load system prompt from {SYSTEM_PROMPT_FILE}: {e}") from e


def load_skills() -> str:
    """Load all skill files from the skills directory, re-reading each call for hot reload.

    Each .md file in the skills/ directory is treated as a skill.
    Returns a combined string with all skills, or empty string if none found.
    """
    if not SKILLS_DIR.is_dir():
        return ""
    skills = []
    for skill_file in sorted(SKILLS_DIR.glob("*.md")):
        try:
            content = skill_file.read_text().strip()
            if content:
                skills.append(content)
        except (PermissionError, OSError):
            continue
    return "\n\n".join(skills)

# Command execution settings
COMMAND_TIMEOUT = int(os.getenv("AVA_COMMAND_TIMEOUT", "300"))  # 5 minutes default
