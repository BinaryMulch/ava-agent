"""
Ava Agent - Core Agent Logic
Handles LLM interaction and tool execution.
"""

import os
import json
import uuid
import base64
import signal
import logging
import asyncio
from openai import AsyncOpenAI

log = logging.getLogger(__name__)

from config import (
    XAI_API_KEY,
    XAI_BASE_URL,
    XAI_MODEL,
    UPLOADS_DIR,
    load_system_prompt,
    load_skills,
    COMMAND_TIMEOUT,
    REPO_DIR,
    SERVICE_NAME,
)

# Initialize the OpenAI-compatible client for xAI
client = AsyncOpenAI(
    api_key=XAI_API_KEY,
    base_url=XAI_BASE_URL,
)

# Tool definitions for the LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Execute a bash command on the system with root privileges. "
                "Use this for ANY system operation: running programs, managing files, "
                "installing packages, configuring services, networking, etc. "
                "Returns stdout, stderr, and the exit code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"Timeout in seconds (default: {COMMAND_TIMEOUT}).",
                    },
                },
                "required": ["command"],
            },
        },
    }
]


async def execute_command(command: str, timeout: int | None = None) -> dict:
    """Execute a shell command and return the result."""
    timeout = timeout if timeout is not None else COMMAND_TIMEOUT
    log.info("Executing command: %s", command[:200])
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
        # Kill process group on any interruption (timeout, disconnect, etc.)
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError, OSError):
            pass
        if isinstance(e, asyncio.CancelledError):
            raise
        if isinstance(e, asyncio.TimeoutError):
            log.warning("Command timed out after %ds: %s", timeout, command[:200])
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "exit_code": -1,
            }
        log.error("Command failed with error: %s", e)
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
        }
    MAX_OUTPUT = 256 * 1024
    stdout_str = stdout.decode(errors="replace")
    stderr_str = stderr.decode(errors="replace")
    if len(stdout_str) > MAX_OUTPUT:
        stdout_str = stdout_str[:MAX_OUTPUT] + "\n... [output truncated]"
    if len(stderr_str) > MAX_OUTPUT:
        stderr_str = stderr_str[:MAX_OUTPUT] + "\n... [output truncated]"
    log.info("Command exited with code %d", process.returncode)
    if process.returncode != 0 and stderr_str:
        log.debug("Command stderr: %s", stderr_str[:500])
    return {
        "stdout": stdout_str,
        "stderr": stderr_str,
        "exit_code": process.returncode,
    }


async def handle_tool_call(name: str, arguments: dict) -> str:
    """Route a tool call to the appropriate handler."""
    if name == "execute_command":
        command = arguments.get("command")
        if not command:
            return json.dumps({"error": "Missing 'command' argument"})
        result = await execute_command(
            command=command,
            timeout=arguments.get("timeout"),
        )
        return json.dumps(result)
    return json.dumps({"error": f"Unknown tool: {name}"})


def build_system_prompt() -> str:
    """Build the system prompt with dynamic values and appended skills."""
    prompt = load_system_prompt()
    skills = load_skills()
    if skills:
        prompt = prompt + "\n\n" + skills
    return prompt.replace(
        "{service_name}", SERVICE_NAME
    ).replace(
        "{repo_dir}", str(REPO_DIR)
    )


def format_messages_for_api(db_messages: list[dict]) -> list[dict]:
    """Convert database messages into the format expected by the API.

    If a message has images, its content is converted to the multimodal
    content-parts format: [{"type": "text", ...}, {"type": "image_url", ...}].
    """
    api_messages = []
    for msg in db_messages:
        entry = {"role": msg["role"]}
        if msg["role"] == "tool":
            tool_call_id = msg.get("tool_call_id")
            if not tool_call_id:
                log.warning("Skipping tool message with missing tool_call_id: %s", msg.get("content", "")[:100])
                continue
            entry["content"] = msg["content"]
            entry["tool_call_id"] = tool_call_id
        elif msg.get("tool_calls"):
            entry["content"] = msg["content"] or ""
            entry["tool_calls"] = msg["tool_calls"]
        elif msg.get("images"):
            # Build multimodal content parts for vision
            parts = []
            if msg["content"]:
                parts.append({"type": "text", "text": msg["content"]})
            for img in msg["images"]:
                filepath = UPLOADS_DIR / img["filename"]
                try:
                    data = base64.b64encode(filepath.read_bytes()).decode("ascii")
                except FileNotFoundError:
                    continue
                parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['media_type']};base64,{data}",
                    },
                })
            entry["content"] = parts if parts else msg["content"] or ""
        else:
            entry["content"] = msg["content"]
        api_messages.append(entry)
    return api_messages


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return len(text) // 4


def _trim_messages(messages: list[dict], max_tokens: int = 100_000) -> list[dict]:
    """Trim older messages to fit within a token budget, preserving recent context.

    Always keeps at least the last 10 messages. Removes oldest messages first,
    but never breaks up a tool_calls/tool sequence (keeps assistant+tool groups intact).
    Ensures the result starts with a 'user' message (after system prompt is prepended).
    """
    if not messages:
        return messages

    total = sum(_estimate_tokens(json.dumps(m)) for m in messages)
    if total <= max_tokens:
        return messages

    # Always keep at least the last 10 messages
    min_keep = min(10, len(messages))
    trimmed = list(messages)

    while len(trimmed) > min_keep and total > max_tokens:
        msg = trimmed[0]
        if msg["role"] == "tool":
            total -= _estimate_tokens(json.dumps(trimmed.pop(0)))
        elif msg["role"] == "assistant" and msg.get("tool_calls"):
            # Calculate group size before removing
            group_size = 1
            while (group_size < len(trimmed)
                   and trimmed[group_size]["role"] == "tool"):
                group_size += 1
            # Only remove if we'd stay at or above min_keep
            if len(trimmed) - group_size >= min_keep:
                for _ in range(group_size):
                    total -= _estimate_tokens(json.dumps(trimmed.pop(0)))
            else:
                break
        else:
            total -= _estimate_tokens(json.dumps(trimmed.pop(0)))

    # Ensure conversation starts with a user message (after system prompt is prepended)
    # Pop assistant+tool groups together to avoid orphaned tool messages
    while len(trimmed) > 1 and trimmed[0]["role"] != "user":
        msg = trimmed[0]
        if msg["role"] == "assistant" and msg.get("tool_calls"):
            # Remove the assistant message and all following tool messages in its group
            total -= _estimate_tokens(json.dumps(trimmed.pop(0)))
            while trimmed and trimmed[0]["role"] == "tool":
                total -= _estimate_tokens(json.dumps(trimmed.pop(0)))
        else:
            total -= _estimate_tokens(json.dumps(trimmed.pop(0)))

    return trimmed


async def stream_response(messages: list[dict]):
    """
    Stream a response from the LLM. Yields events as dicts:
      {"type": "text", "content": "..."}
      {"type": "tool_call", "id": "...", "name": "...", "arguments": "..."}
      {"type": "tool_result", "tool_call_id": "...", "result": "..."}
      {"type": "done", "full_content": "...", "tool_calls": [...]}

    Handles the full tool-use loop: if the model requests tool calls,
    executes them and continues the conversation until a final text response.
    """
    MAX_TOOL_ROUNDS = 20
    system_prompt = build_system_prompt()
    trimmed = _trim_messages(messages)
    conversation = [{"role": "system", "content": system_prompt}] + trimmed

    for _round in range(MAX_TOOL_ROUNDS):
        full_content = ""
        tool_calls_acc = {}  # Accumulate streaming tool calls by index

        # Re-trim before each API call (conversation grows during tool rounds)
        if _round > 0:
            system_msg = conversation[0]
            conversation = [system_msg] + _trim_messages(conversation[1:])

        stream = await client.chat.completions.create(
            model=XAI_MODEL,
            messages=conversation,
            tools=TOOLS,
            stream=True,
        )

        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # Accumulate text content
                if delta.content:
                    full_content += delta.content
                    yield {"type": "text", "content": delta.content}

                # Accumulate tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": tc.id or f"tc_{uuid.uuid4().hex[:8]}",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments
        finally:
            await stream.close()

        # If there were tool calls, execute them and loop
        if tool_calls_acc:
            tool_calls_list = [tool_calls_acc[i] for i in sorted(tool_calls_acc.keys())]

            # Add the assistant message with tool calls to conversation
            assistant_msg = {"role": "assistant", "content": full_content or ""}
            assistant_msg["tool_calls"] = tool_calls_list
            conversation.append(assistant_msg)

            # Parse and emit all tool_call events first so the server
            # can batch-save one assistant message with all tool calls.
            # Skip malformed tool calls (bad JSON args) — return error results directly.
            parsed_calls = []
            malformed_calls = []
            # Emit tool_call events for ALL calls (including malformed) so server saves them
            for tc in tool_calls_list:
                name = tc["function"]["name"]
                yield {
                    "type": "tool_call",
                    "id": tc["id"],
                    "name": name,
                    "arguments": tc["function"]["arguments"],
                }
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                    parsed_calls.append((tc, name, arguments))
                except json.JSONDecodeError:
                    malformed_calls.append(tc)

            # Emit error results for malformed tool calls
            for tc in malformed_calls:
                result = json.dumps({"error": "Failed to parse tool arguments", "raw": tc["function"]["arguments"]})
                yield {"type": "tool_result", "tool_call_id": tc["id"], "result": result}
                conversation.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

            # Now execute each valid tool call and emit results
            for tc, name, arguments in parsed_calls:
                result = await handle_tool_call(name, arguments)

                yield {
                    "type": "tool_result",
                    "tool_call_id": tc["id"],
                    "result": result,
                }

                # Truncate tool result to 32KB before feeding back to the model
                truncated = result if len(result) <= 32768 else result[:32768] + "\n... [output truncated]"

                # Add tool result to conversation
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": truncated,
                })

            # Continue the loop to get the next response
            continue

        # No tool calls — we have the final response
        yield {
            "type": "done",
            "full_content": full_content,
            "tool_calls": None,
        }
        return

    # Exceeded max tool rounds
    yield {
        "type": "error",
        "content": f"Stopped after {MAX_TOOL_ROUNDS} tool call rounds.",
    }
