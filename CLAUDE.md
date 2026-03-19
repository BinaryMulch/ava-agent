# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Ava Agent is a lightweight AI chat agent powered by xAI's Grok API with full root system access and a mobile-responsive web UI. It uses the OpenAI-compatible client to talk to xAI, streams responses via SSE, and can execute arbitrary bash commands on the host.

## Running Locally

```bash
# Install dependencies (uses venv)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up environment
cp .env.example .env  # or create .env with XAI_API_KEY=...

# Run the server
python server.py
# Serves at http://127.0.0.1:8888
```

For production (systemd): `sudo bash install.sh` then `sudo systemctl start ava-agent`.

## Architecture

**Four Python files, no build tools, no frontend framework.**

- `server.py` — FastAPI app. REST endpoints for conversations CRUD, SSE streaming for chat (`/api/conversations/{id}/messages`), git-pull update endpoint, serves `static/index.html` at `/`.
- `agent.py` — LLM interaction. Uses `openai.AsyncOpenAI` pointed at xAI. Defines a single tool (`execute_command`) for running bash commands. `stream_response()` is an async generator that handles the full tool-use loop: stream LLM output → execute tool calls → feed results back → repeat until final text response.
- `database.py` — SQLite layer via raw `sqlite3`. Two tables: `conversations` and `messages`. Messages store tool calls as JSON. Uses WAL mode and context-managed connections.
- `config.py` — All settings from env vars / `.env`. Loads the system prompt from `system_prompt.md` via `load_system_prompt()`, which re-reads on each call for hot reload.
- `system_prompt.md` — The system prompt template sent to the LLM. Uses `{service_name}` and `{repo_dir}` placeholders that are replaced at runtime.

**Data flow for a chat message:**
1. `POST /api/conversations/{id}/messages` receives user message
2. `server.py` saves it to DB, builds message history, calls `agent.stream_response()`
3. `agent.py` streams from xAI, yields events (text/tool_call/tool_result/done)
4. `server.py` saves assistant messages and tool results to DB, forwards SSE events to client
5. `static/index.html` (single-file vanilla JS) renders the stream in real-time

## Key Conventions

- The xAI API is accessed through the OpenAI Python SDK (`AsyncOpenAI`) with a custom `base_url`.
- Tool calls are accumulated during streaming by index, then executed sequentially after the stream completes for that turn.
- Database connections are short-lived (context manager per operation), not pooled.
- The frontend is a single HTML file with inline CSS/JS — no bundler, no framework.
- Environment config uses `os.getenv()` with defaults; `.env` is loaded by the systemd `EnvironmentFile` directive (not python-dotenv).
