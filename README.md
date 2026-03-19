# Ava Agent

A lightweight AI agent powered by xAI's Grok with full root system access and a mobile-responsive web UI.

## Features

- **Full system access** — Runs as root, can execute any bash command
- **Web UI** — Dark-themed, mobile-responsive chat interface built with Tailwind CSS
- **Image support** — Send images to Ava for vision analysis; Ava can display images inline from the web
- **Conversation history** — Saved in SQLite, deletable from the UI
- **Streaming responses** — Real-time SSE streaming with tool call visualization
- **Skills system** — Drop `.md` files into `skills/` to extend Ava's capabilities without editing code
- **Self-updating** — Pull updates from GitHub and restart via the UI or by asking Ava
- **Simple** — Python + vanilla JS, no build tools, no npm, no frontend framework

## Quick Start

```bash
# Clone the repo
git clone https://github.com/BinaryMulch/ava-agent.git
cd ava-agent

# Run the installer (as root)
sudo bash install.sh

# Set your API key
sudo nano .env

# Start the service
sudo systemctl start ava-agent

# Open in browser
# http://127.0.0.1:8888
```

## File Structure

```
ava-agent/
├── server.py            # FastAPI web server & API endpoints
├── agent.py             # LLM interaction & tool execution
├── database.py          # SQLite conversation storage
├── config.py            # Configuration from environment
├── system_prompt.md     # Core system prompt (hot-reloaded)
├── skills/              # Skill files (hot-reloaded)
│   └── image_display.md # Image display instructions
├── static/
│   └── index.html       # Web UI (single file, Tailwind CSS)
├── install.sh           # System installer
├── requirements.txt     # Python dependencies
├── .env.example         # Example environment config
├── .env                 # API keys & settings (not in git)
├── .gitignore
└── data/                # Runtime data (not in git)
    ├── conversations.db # SQLite database
    ├── uploads/         # User-uploaded images
    └── ava_files/       # Images Ava downloads for display
```

## Configuration

All settings are in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `XAI_API_KEY` | (required) | Your xAI API key |
| `XAI_BASE_URL` | `https://api.x.ai/v1` | API base URL |
| `XAI_MODEL` | `grok-4-1-fast-reasoning` | Model to use |
| `AVA_HOST` | `0.0.0.0` | Bind address |
| `AVA_PORT` | `8888` | Port number |
| `AVA_SERVICE_NAME` | `ava-agent` | Systemd service name |
| `AVA_COMMAND_TIMEOUT` | `300` | Command timeout (seconds) |

## Skills

Skills are `.md` files in the `skills/` directory that extend Ava's knowledge and capabilities. They're automatically loaded and appended to the system prompt on every message, so changes take effect immediately without a restart.

To add a new skill, create a file like `skills/my_skill.md` with instructions for Ava. You can use `{repo_dir}` and `{service_name}` placeholders — they're replaced at runtime.

## Image Support

**Sending images to Ava:** Click the image button next to the input box to attach up to 4 images. Ava can see and analyze them using Grok's vision capabilities.

**Ava displaying images:** Ava can download images from the web and show them inline in the chat. She saves them to `data/ava_files/` and references them with markdown image syntax.

## Updating

Three ways to update:

1. **From the UI** — Click "Update Agent" in the sidebar
2. **Ask Ava** — Tell her "update yourself"
3. **Manual** — `cd /opt/ava-agent && git pull && systemctl restart ava-agent`

Updates discard any local file changes and pull the latest from GitHub. Edit and commit changes to the repo rather than modifying files directly on the server.

## Exposing to the Network

By default, Ava binds to `0.0.0.0` (all interfaces). To restrict to localhost only:

```bash
# In .env, change:
AVA_HOST=127.0.0.1

# Then restart:
sudo systemctl restart ava-agent
```

**Warning:** There is no authentication. Only expose on trusted networks.

## Service Management

```bash
sudo systemctl start ava-agent    # Start
sudo systemctl stop ava-agent     # Stop
sudo systemctl restart ava-agent  # Restart
sudo systemctl status ava-agent   # Status
journalctl -u ava-agent -f        # Live logs
```

The service starts automatically on boot via `systemctl enable`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/conversations` | List conversations |
| `POST` | `/api/conversations` | Create conversation |
| `GET` | `/api/conversations/:id` | Get conversation + messages |
| `DELETE` | `/api/conversations/:id` | Delete conversation |
| `PATCH` | `/api/conversations/:id` | Rename conversation |
| `POST` | `/api/conversations/:id/messages` | Send message with optional images (SSE stream) |
| `GET` | `/api/uploads/:filename` | Serve user-uploaded image |
| `GET` | `/api/files/:filename` | Serve Ava-downloaded image |
| `POST` | `/api/update` | Pull from git & restart |
