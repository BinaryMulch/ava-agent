# Ava Agent

A lightweight AI agent powered by xAI's Grok with full root system access and a mobile-responsive web UI.

## Features

- **Full system access** — Runs as root, can execute any bash command
- **Web UI** — Clean, mobile-responsive chat interface
- **Conversation history** — Saved in SQLite, deletable from the UI
- **Streaming responses** — Real-time SSE streaming with tool call visualization
- **Self-updating** — Pull updates from GitHub and restart via the UI or by asking Ava
- **Simple** — ~6 files, no build tools, no npm, no frontend framework

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USER/ava-agent.git
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
├── server.py          # FastAPI web server & API endpoints
├── agent.py           # LLM interaction & tool execution
├── database.py        # SQLite conversation storage
├── config.py          # Configuration from environment
├── static/
│   └── index.html     # Web UI (single file)
├── install.sh         # System installer
├── requirements.txt   # Python dependencies
├── .env               # API keys & settings (not in git)
├── .gitignore
└── data/              # SQLite database (not in git)
```

## Configuration

All settings are in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `XAI_API_KEY` | (required) | Your xAI API key |
| `XAI_BASE_URL` | `https://api.x.ai/v1` | API base URL |
| `XAI_MODEL` | `grok-3-latest` | Model to use |
| `AVA_HOST` | `127.0.0.1` | Bind address |
| `AVA_PORT` | `8888` | Port number |
| `AVA_SERVICE_NAME` | `ava-agent` | Systemd service name |
| `AVA_COMMAND_TIMEOUT` | `300` | Command timeout (seconds) |

## Updating

Three ways to update:

1. **From the UI** — Click "Update Agent" in the sidebar
2. **Ask Ava** — Tell her "update yourself from GitHub"
3. **Manual** — `cd /path/to/ava-agent && git pull && systemctl restart ava-agent`

## Exposing to the Network

By default, Ava binds to `127.0.0.1` (localhost only). To access from your phone on the same network:

```bash
# In .env, change:
AVA_HOST=0.0.0.0

# Then restart:
sudo systemctl restart ava-agent

# Access at http://YOUR_SERVER_IP:8888
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
| `POST` | `/api/conversations/:id/messages` | Send message (SSE stream) |
| `POST` | `/api/update` | Pull from git & restart |
