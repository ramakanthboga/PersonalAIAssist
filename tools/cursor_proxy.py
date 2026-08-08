"""OpenAI-compatible proxy for Cursor SDK (runs on the Windows host, not in Docker).

Exposes:
  GET  /health
  GET  /v1/models
  POST /v1/chat/completions

Cursor SDK local agents are launched in a *separate Python process* to avoid
WinError 10038 socket conflicts with uvicorn on Windows.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

app = FastAPI(title="Cursor OpenAI Proxy")

_WORKER = Path(__file__).with_name("cursor_agent_worker.py")


def _api_key() -> str:
    key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not key:
        raise RuntimeError("CURSOR_API_KEY is not set")
    return key


def _default_model() -> str:
    return os.environ.get("DEFAULT_MODEL", "composer-2.5")


def _cwd() -> str:
    return os.environ.get("CURSOR_CWD") or str(Path(__file__).resolve().parents[1])


def _messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "user")).upper()
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


def _run_cursor_subprocess(prompt: str, model: str) -> str:
    """Blocking: spawn isolated worker process for Cursor Agent.prompt."""
    env = os.environ.copy()
    env["CURSOR_API_KEY"] = _api_key()
    env["CURSOR_CWD"] = _cwd()
    env["DEFAULT_MODEL"] = model or _default_model()

    payload = json.dumps({"prompt": prompt, "model": model or _default_model()})
    # Prefer project venv python (has cursor_sdk); fall back to current interpreter.
    venv_py = Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe"
    python = str(venv_py) if venv_py.exists() else sys.executable

    completed = subprocess.run(
        [python, str(_WORKER)],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=300,
        env=env,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    if not stdout:
        raise RuntimeError(stderr or f"cursor worker failed with code {completed.returncode}")

    data = json.loads(stdout)
    if not data.get("ok"):
        raise RuntimeError(data.get("error") or "cursor worker failed")
    return data.get("content") or ""


async def _run_cursor_async(prompt: str, model: str) -> str:
    return await asyncio.to_thread(_run_cursor_subprocess, prompt, model)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": "composer-2.5", "object": "model", "owned_by": "cursor"},
            {"id": "auto", "object": "model", "owned_by": "cursor"},
        ],
    }


def _sse_chunks(content: str, *, model: str, completion_id: str, created: int) -> list[str]:
    out: list[str] = []
    step = 48
    text = content or ""
    for i in range(0, max(len(text), 1), step):
        piece = text[i : i + step]
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {"index": 0, "delta": {"content": piece}, "finish_reason": None}
            ],
        }
        out.append(f"data: {json.dumps(payload)}\n\n")
    done = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    out.append(f"data: {json.dumps(done)}\n\n")
    out.append("data: [DONE]\n\n")
    return out


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages") or []
    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

    model = body.get("model") or _default_model()
    stream = bool(body.get("stream"))
    prompt = _messages_to_prompt(messages)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    try:
        content = await _run_cursor_async(prompt, model)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if stream:

        async def event_gen() -> AsyncIterator[str]:
            for line in _sse_chunks(
                content, model=model, completion_id=completion_id, created=created
            ):
                yield line
                await asyncio.sleep(0)

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    return JSONResponse(
        {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    )


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    print(f"Cursor OpenAI proxy listening on http://{host}:{port}")
    print(f"Backend should use: CURSOR_PROXY_URL=http://host.docker.internal:{port}/v1")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
