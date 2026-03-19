"""
Ava Agent - FastAPI Server
Web API and SSE streaming endpoints.
"""

import json
import re
import uuid
import asyncio
from functools import partial
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel, field_validator
from pathlib import Path

import logging
import database as db
from agent import stream_response, format_messages_for_api
from config import HOST, PORT, REPO_DIR, SERVICE_NAME, UPLOADS_DIR, setup_logging

log = logging.getLogger(__name__)


async def _db(func, *args, **kwargs):
    """Run a synchronous database function in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(partial(func, *args, **kwargs))


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    setup_logging()
    from config import XAI_API_KEY
    if not XAI_API_KEY:
        log.fatal("XAI_API_KEY is not set. Export it or add it to .env")
        import sys
        sys.exit(1)
    db.init_db()
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (REPO_DIR / "data" / "ava_files").mkdir(parents=True, exist_ok=True)
    log.info("Ava Agent started on %s:%s", HOST, PORT)
    yield
    log.info("Ava Agent shutting down")

app = FastAPI(title="Ava Agent", lifespan=lifespan)


# ── Pydantic models ──────────────────────────────────────────────────

class RenameRequest(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_must_be_valid(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("title must not be empty")
        if len(v) > 200:
            raise ValueError("title must not exceed 200 characters")
        return v


# ── Conversation endpoints ───────────────────────────────────────────

@app.get("/api/conversations")
async def list_conversations():
    return await _db(db.list_conversations)


@app.post("/api/conversations")
async def create_conversation():
    return await _db(db.create_conversation)


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = await _db(db.get_conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    conv["messages"] = await _db(db.get_messages, conv_id)
    return conv


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    # Collect image filenames before deleting conversation data
    messages = await _db(db.get_messages, conv_id)
    image_files = []
    for msg in messages:
        for img in (msg.get("images") or []):
            if img.get("filename"):
                image_files.append(img["filename"])

    # Scan message content for /api/files/ references (ava_files)
    ava_files_dir = REPO_DIR / "data" / "ava_files"
    ava_filenames = set()
    for msg in messages:
        content = msg.get("content") or ""
        ava_filenames.update(re.findall(r'/api/files/([A-Za-z0-9._-]+)', content))

    if not await _db(db.delete_conversation, conv_id):
        raise HTTPException(404, "Conversation not found")
    _conv_locks.pop(conv_id, None)

    # Clean up uploaded image files
    for filename in image_files:
        try:
            (UPLOADS_DIR / filename).unlink()
        except FileNotFoundError:
            pass

    # Clean up ava_files referenced in messages
    for filename in ava_filenames:
        if "/" in filename or "\\" in filename or ".." in filename:
            continue
        try:
            (ava_files_dir / filename).unlink()
        except FileNotFoundError:
            pass

    return {"status": "deleted"}


@app.patch("/api/conversations/{conv_id}")
async def rename_conversation(conv_id: str, body: RenameRequest):
    if not await _db(db.rename_conversation, conv_id, body.title):
        raise HTTPException(404, "Conversation not found")
    return {"status": "updated"}


# ── Chat endpoint (SSE streaming) ────────────────────────────────────

_conv_locks: dict[str, asyncio.Lock] = {}

@asynccontextmanager
async def _get_conv_lock(conv_id: str):
    _conv_locks.setdefault(conv_id, asyncio.Lock())
    lock = _conv_locks[conv_id]
    async with lock:
        yield lock
    # Evict if no one else is waiting
    if not lock.locked():
        _conv_locks.pop(conv_id, None)


ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_IMAGES = 4

EXTENSION_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

@app.post("/api/conversations/{conv_id}/messages")
async def send_message(
    conv_id: str,
    message: str = Form(...),
    images: list[UploadFile] = File(default=[]),
):
    """Send a message and stream the response via SSE."""
    # Validate
    if not message.strip():
        raise HTTPException(422, "message must not be empty")
    if len(images) > MAX_IMAGES:
        raise HTTPException(422, f"Too many images (max {MAX_IMAGES})")
    conv = await _db(db.get_conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Save images to disk, store only metadata
    image_data = []
    for img in images:
        if img.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(422, f"Unsupported image type: {img.content_type}")
        raw = await img.read()
        if len(raw) > MAX_IMAGE_SIZE:
            raise HTTPException(422, f"Image too large (max {MAX_IMAGE_SIZE // 1024 // 1024}MB)")
        ext = EXTENSION_MAP.get(img.content_type, ".bin")
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = UPLOADS_DIR / filename
        await asyncio.to_thread(filepath.write_bytes, raw)
        image_data.append({
            "filename": filename,
            "media_type": img.content_type,
        })

    async def event_stream():
        async with _get_conv_lock(conv_id):
            # Save the user message (with image metadata if any)
            await _db(
                db.add_message, conv_id, "user", message,
                images=image_data if image_data else None,
            )

            # Auto-title: re-read conversation inside lock to avoid stale snapshot
            current_conv = await _db(db.get_conversation, conv_id)
            if current_conv and current_conv["title"] == "New Conversation":
                title = message[:80].strip()
                if len(message) > 80:
                    title += "..."
                await _db(db.rename_conversation, conv_id, title)

            # Build message history for the API
            history = await _db(db.get_messages, conv_id)
            api_messages = format_messages_for_api(history)

            full_content = ""
            tool_calls_to_save = []
            tool_calls_by_id = {}

            try:
                async for event in stream_response(api_messages):
                    if event["type"] == "text":
                        full_content += event["content"]
                        yield f"data: {json.dumps(event)}\n\n"

                    elif event["type"] == "tool_call":
                        tc_entry = {
                            "id": event["id"],
                            "type": "function",
                            "function": {
                                "name": event["name"],
                                "arguments": event["arguments"],
                            },
                        }
                        tool_calls_to_save.append(tc_entry)
                        tool_calls_by_id[event["id"]] = tc_entry
                        yield f"data: {json.dumps(event)}\n\n"

                    elif event["type"] == "tool_result":
                        # Find the matching tool call to include command info
                        matched_tc = tool_calls_by_id.get(event["tool_call_id"])

                        # Save the assistant message with tool calls if we haven't yet
                        if tool_calls_to_save:
                            await _db(
                                db.add_message,
                                conv_id, "assistant", full_content,
                                tool_calls=tool_calls_to_save,
                            )
                            tool_calls_to_save = []
                            full_content = ""

                        # Save the tool result message
                        await _db(
                            db.add_message,
                            conv_id, "tool", event["result"],
                            tool_call_id=event["tool_call_id"],
                        )

                        # Include command info in the event for the frontend
                        enriched_event = dict(event)
                        if matched_tc:
                            enriched_event["name"] = matched_tc["function"]["name"]
                            enriched_event["arguments"] = matched_tc["function"]["arguments"]
                        yield f"data: {json.dumps(enriched_event)}\n\n"

                    elif event["type"] == "error":
                        error_msg = event.get("content", "Unknown error")
                        await _db(db.add_message, conv_id, "assistant", error_msg)
                        yield f"data: {json.dumps(event)}\n\n"
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"

                    elif event["type"] == "done":
                        if event.get("full_content"):
                            await _db(db.add_message, conv_id, "assistant", event["full_content"])

                        yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except asyncio.CancelledError:
                # Client disconnected — save placeholder so history stays valid
                log.info("Client disconnected from conversation %s", conv_id)
                if tool_calls_to_save:
                    await _db(
                        db.add_message,
                        conv_id, "assistant", full_content or "",
                    )
                await _db(db.add_message, conv_id, "assistant", "[Response interrupted]")
                return

            except Exception as e:
                log.exception("Error in conversation %s", conv_id)
                # Save any pending assistant message with tool calls
                if tool_calls_to_save:
                    await _db(
                        db.add_message,
                        conv_id, "assistant", full_content or "",
                    )
                    tool_calls_to_save = []
                    full_content = ""
                error_msg = f"Error: {str(e)}"
                await _db(db.add_message, conv_id, "assistant", error_msg)
                yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Uploads endpoint ─────────────────────────────────────────────────

@app.get("/api/uploads/{filename}")
async def serve_upload(filename: str):
    """Serve an uploaded image from disk."""
    # Sanitize: only allow simple filenames (no path traversal)
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    filepath = UPLOADS_DIR / filename
    if not filepath.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(filepath)


# ── File serving endpoint (for Ava to display images in chat) ────────

ALLOWED_SERVE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
AVA_FILES_DIR = REPO_DIR / "data" / "ava_files"

@app.get("/api/files/{filename}")
async def serve_ava_file(filename: str):
    """Serve a file that Ava saved for display in chat."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    filepath = AVA_FILES_DIR / filename
    if not filepath.is_file():
        raise HTTPException(404, "File not found")
    if filepath.suffix.lower() not in ALLOWED_SERVE_EXTENSIONS:
        raise HTTPException(403, "File type not allowed")
    return FileResponse(filepath)


# ── Update endpoint ──────────────────────────────────────────────────

@app.post("/api/update")
async def update_agent():
    """Pull latest from git and restart the service."""
    # Discard local changes and pull latest
    await asyncio.create_subprocess_exec(
        "git", "checkout", "--", ".",
        cwd=str(REPO_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    process = await asyncio.create_subprocess_exec(
        "git", "pull",
        cwd=str(REPO_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        log.error("Git pull failed: %s", stderr.decode())
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Git pull failed: {stderr.decode()}",
            },
        )

    git_output = stdout.decode().strip()
    log.info("Git pull succeeded: %s", git_output)

    # Schedule restart after response is sent
    async def restart_later():
        await asyncio.sleep(1)
        log.info("Restarting service %s", SERVICE_NAME)
        await asyncio.create_subprocess_exec("systemctl", "restart", SERVICE_NAME)

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


# ── System status endpoint ───────────────────────────────────────────

@app.get("/api/status")
async def system_status():
    """Return basic system info for the sidebar status panel."""
    import shutil
    import platform

    async def run_cmd(cmd):
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    hostname = platform.node()
    uptime = await run_cmd("uptime -p 2>/dev/null || uptime")
    uptime = uptime.replace("up ", "")  # Clean up "up X days, Y hours"

    # Memory
    try:
        mem_info = await run_cmd("free -b | awk '/^Mem:/ {printf \"%d %d\", $3, $2}'")
        mem_used, mem_total = [int(x) for x in mem_info.split()]
        mem_pct = round(mem_used / mem_total * 100) if mem_total else 0
        mem_str = f"{mem_used // (1024**3)}/{mem_total // (1024**3)}GB ({mem_pct}%)"
    except Exception:
        mem_str = "N/A"
        mem_pct = 0

    # Disk
    try:
        disk = shutil.disk_usage("/")
        disk_pct = round(disk.used / disk.total * 100)
        disk_str = f"{disk.used // (1024**3)}/{disk.total // (1024**3)}GB ({disk_pct}%)"
    except Exception:
        disk_str = "N/A"
        disk_pct = 0

    # Load average
    try:
        load = await run_cmd("cat /proc/loadavg | awk '{print $1}'")
    except Exception:
        load = "N/A"

    return {
        "hostname": hostname,
        "uptime": uptime,
        "memory": mem_str,
        "memory_pct": mem_pct,
        "disk": disk_str,
        "disk_pct": disk_pct,
        "load": load,
    }


# ── Serve the frontend ───────────────────────────────────────────────

@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    content = await asyncio.to_thread(html_path.read_text)
    return HTMLResponse(content)


# ── Main entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
