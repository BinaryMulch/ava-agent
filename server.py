"""
Ava Agent - FastAPI Server
Web API and SSE streaming endpoints.
"""

import json
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

import database as db
from agent import stream_response, format_messages_for_api, handle_tool_call
from config import HOST, PORT, REPO_DIR, SERVICE_NAME

app = FastAPI(title="Ava Agent")


# ── Pydantic models ──────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    message: str

class RenameRequest(BaseModel):
    title: str


# ── Startup ──────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    db.init_db()


# ── Conversation endpoints ───────────────────────────────────────────

@app.get("/api/conversations")
async def list_conversations():
    return db.list_conversations()


@app.post("/api/conversations")
async def create_conversation():
    return db.create_conversation()


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    conv["messages"] = db.get_messages(conv_id)
    return conv


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if not db.delete_conversation(conv_id):
        raise HTTPException(404, "Conversation not found")
    return {"status": "deleted"}


@app.patch("/api/conversations/{conv_id}")
async def rename_conversation(conv_id: str, body: RenameRequest):
    if not db.rename_conversation(conv_id, body.title):
        raise HTTPException(404, "Conversation not found")
    return {"status": "updated"}


# ── Chat endpoint (SSE streaming) ────────────────────────────────────

@app.post("/api/conversations/{conv_id}/messages")
async def send_message(conv_id: str, body: SendMessageRequest):
    """Send a message and stream the response via SSE."""
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Save the user message
    db.add_message(conv_id, "user", body.message)

    # Auto-title: use the first message as the conversation title
    if conv["title"] == "New Conversation":
        title = body.message[:80].strip()
        if len(body.message) > 80:
            title += "..."
        db.rename_conversation(conv_id, title)

    # Build message history for the API
    history = db.get_messages(conv_id)
    api_messages = format_messages_for_api(history)

    async def event_stream():
        full_content = ""
        tool_calls_to_save = []

        try:
            async for event in stream_response(api_messages):
                if event["type"] == "text":
                    full_content += event["content"]
                    yield f"data: {json.dumps(event)}\n\n"

                elif event["type"] == "tool_call":
                    tool_calls_to_save.append({
                        "id": event["id"],
                        "type": "function",
                        "function": {
                            "name": event["name"],
                            "arguments": event["arguments"],
                        },
                    })
                    yield f"data: {json.dumps(event)}\n\n"

                elif event["type"] == "tool_result":
                    # Find the matching tool call to include command info
                    matched_tc = None
                    for tc in tool_calls_to_save:
                        if tc["id"] == event["tool_call_id"]:
                            matched_tc = tc
                            break

                    # Save the assistant message with tool calls if we haven't yet
                    if tool_calls_to_save:
                        db.add_message(
                            conv_id, "assistant", "",
                            tool_calls=tool_calls_to_save,
                        )
                        tool_calls_to_save = []

                    # Save the tool result message
                    db.add_message(
                        conv_id, "tool", event["result"],
                        tool_call_id=event["tool_call_id"],
                    )

                    # Include command info in the event for the frontend
                    enriched_event = dict(event)
                    if matched_tc:
                        enriched_event["name"] = matched_tc["function"]["name"]
                        enriched_event["arguments"] = matched_tc["function"]["arguments"]
                    yield f"data: {json.dumps(enriched_event)}\n\n"

                elif event["type"] == "done":
                    # Save remaining tool calls if any
                    if tool_calls_to_save:
                        db.add_message(
                            conv_id, "assistant", event.get("full_content", ""),
                            tool_calls=tool_calls_to_save,
                        )
                    elif event.get("full_content"):
                        db.add_message(conv_id, "assistant", event["full_content"])

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            db.add_message(conv_id, "assistant", error_msg)
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Update endpoint ──────────────────────────────────────────────────

@app.post("/api/update")
async def update_agent():
    """Pull latest from git and restart the service."""
    import subprocess

    # Git pull
    result = subprocess.run(
        ["git", "pull"],
        cwd=str(REPO_DIR),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Git pull failed: {result.stderr}",
            },
        )

    git_output = result.stdout.strip()

    # Schedule restart after response is sent
    async def restart_later():
        await asyncio.sleep(1)
        subprocess.Popen(["systemctl", "restart", SERVICE_NAME])

    asyncio.create_task(restart_later())

    return {
        "status": "updating",
        "git_output": git_output,
        "message": "Update pulled. Service restarting...",
    }


# ── Health check ─────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ava-agent"}


# ── Serve the frontend ───────────────────────────────────────────────

@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text())


# ── Main entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    db.init_db()
    uvicorn.run(app, host=HOST, port=PORT)
