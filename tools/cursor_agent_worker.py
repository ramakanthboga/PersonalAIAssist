"""Run a single Cursor Agent.prompt in an isolated process (stdin JSON -> stdout JSON).

Avoids WinError 10038 when the SDK local bridge runs inside uvicorn's process on Windows.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        prompt = payload["prompt"]
        model = payload.get("model") or os.environ.get("DEFAULT_MODEL", "composer-2.5")
        api_key = os.environ.get("CURSOR_API_KEY", "").strip()
        cwd = os.environ.get("CURSOR_CWD") or os.getcwd()
        if not api_key:
            raise RuntimeError("CURSOR_API_KEY is not set")

        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=cwd),
            ),
        )
        if getattr(result, "status", None) == "error":
            raise RuntimeError(f"Cursor agent run failed: {getattr(result, 'id', 'unknown')}")

        json.dump({"ok": True, "content": result.result or ""}, sys.stdout)
        return 0
    except Exception as exc:
        json.dump({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, sys.stdout)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
