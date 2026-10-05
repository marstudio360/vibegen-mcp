"""
studio-mcp - Direct bridge between an AI agent and a Generative Studio instance.

Lets the agent read the live canvas state, move sliders, switch engines, list
and write preset JSONs in the studio's saves directory, and edit engine source
code (the generative math) with live HMR. All ops go through the studio
server's HTTP API (/api/state, /api/saves, /api/engine-source).

Works against ANY studio instance - local, VPS, or hosted:

    STUDIO_URL     where the studio server runs
                   (default: http://localhost:3000)
    STUDIO_TOKEN   optional shared secret, sent as `x-studio-token` on every
                   request. Set this when the studio server runs with
                   STUDIO_API_TOKEN (recommended for any non-localhost host).

To see param changes live in a browser, open the studio with ?remote=1
(e.g. https://your-host/studio?remote=1) - that enables the state-sync loop.
"""

import base64
import json
import os
import time
from typing import Any

import requests
from fastmcp import FastMCP

STUDIO_URL = os.environ.get("STUDIO_URL", "http://localhost:3000").rstrip("/")
STUDIO_TOKEN = os.environ.get("STUDIO_TOKEN", "").strip()
HTTP_TIMEOUT = 15  # seconds - generous enough for remote hosts

mcp = FastMCP("studio-mcp")


# ── helpers ────────────────────────────────────────────────────────────────

def _headers() -> dict:
    """Auth header when a token is configured; empty otherwise."""
    return {"x-studio-token": STUDIO_TOKEN} if STUDIO_TOKEN else {}


def _err(msg: str, **extra: Any) -> dict:
    """Uniform error shape so tool callers can branch on `error`."""
    out = {"error": msg}
    out.update(extra)
    return out


def _get(path: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(f"{STUDIO_URL}{path}", params=params, headers=_headers(), timeout=HTTP_TIMEOUT)
        return {"_status": r.status_code, **(r.json() if r.content else {})}
    except requests.exceptions.ConnectionError:
        return _err(
            f"Cannot reach studio at {STUDIO_URL}. Is the studio server running? "
            f"(Set STUDIO_URL to point at your instance.)"
        )
    except Exception as e:
        return _err(f"GET {path} failed: {e}")


def _post(path: str, body: dict) -> dict:
    try:
        r = requests.post(f"{STUDIO_URL}{path}", json=body, headers=_headers(), timeout=HTTP_TIMEOUT)
        return {"_status": r.status_code, **(r.json() if r.content else {})}
    except requests.exceptions.ConnectionError:
        return _err(f"Cannot reach studio at {STUDIO_URL}.")
    except Exception as e:
        return _err(f"POST {path} failed: {e}")


def _put(path: str, body: dict) -> dict:
    try:
        r = requests.put(f"{STUDIO_URL}{path}", json=body, headers=_headers(), timeout=HTTP_TIMEOUT)
        return {"_status": r.status_code, **(r.json() if r.content else {})}
    except requests.exceptions.ConnectionError:
        return _err(f"Cannot reach studio at {STUDIO_URL}.")
    except Exception as e:
        return _err(f"PUT {path} failed: {e}")


# ── state / params ─────────────────────────────────────────────────────────

@mcp.tool()
def get_state() -> dict:
    """Read the studio's full live state: current engineId, every param value,
    applied recipe label, seed image URL, version counter. Use this BEFORE
    proposing param changes so you know what's actually there.
    """
    return _get("/api/state")


@mcp.tool()
def set_params(params: dict) -> dict:
    """Apply a partial param patch to the live studio. Browser's RemoteSync
    poller picks it up within ~1s - sliders snap, canvas updates. Pass only
    the keys you want to change; everything else is preserved.

    Example: set_params({"trailFade": 30, "frameBlend": 0.3, "kaleidoscope": 8})
    """
    if not isinstance(params, dict) or not params:
        return _err("params must be a non-empty dict of key→value pairs")
    return _post("/api/state", {"params": params})


@mcp.tool()
def set_engine(engine_id: str) -> dict:
    """Switch the studio to a different engine. The browser will remount the
    canvas with the new engine's defaults (unless params are also set in the
    same call via set_params after).
    """
    if not isinstance(engine_id, str) or not engine_id:
        return _err("engine_id must be a non-empty string")
    return _post("/api/state", {"engineId": engine_id})


@mcp.tool()
def highlight_params(keys: list[str]) -> dict:
    """Briefly highlight specific sliders in the right CONTROLS panel - useful
    when you're suggesting tweaks and want the user to see WHICH knobs to look
    at. Highlight fades after a few seconds (driven by highlightVersion bump).
    """
    return _post("/api/state", {"highlightedParams": keys})


# ── disk saves (the studio's saves directory) ─────────────────────────────────────

@mcp.tool()
def list_saves() -> dict:
    """List every preset JSON in the studio's saves directory (recursive). Returns
    a sorted list of {relPath, label, group, mtimeMs} entries. These are the
    same files shown in the studio's "💾 My Saves" panel.
    """
    return _get("/api/saves")


@mcp.tool()
def read_save(rel_path: str) -> dict:
    """Read one preset JSON from the studio's saves directory by relative path.
    Returns the full preset object: engineId, params, seedUrl, thumbnail,
    canvas dims. Use this when the user references a specific saved file.

    Example: read_save("ForceField Batch 01/FF09_DoubleHelix.json")
    """
    if not rel_path:
        return _err("rel_path required")
    return _get("/api/saves", {"file": rel_path})


@mcp.tool()
def write_save(rel_path: str, content: dict) -> dict:
    """Write a preset JSON to the studio's saves directory. Creates subfolders as
    needed. Use this to save proposals as files the user can preview by
    clicking them in the "💾 My Saves" panel.

    Content shape: {$schema, savedAt, engineId, engineVersion, seedUrl,
    params, canvas, thumbnail}. If unsure, read_save an existing one first
    and modify only what you need to change.
    """
    if not rel_path or not isinstance(content, dict):
        return _err("rel_path (string) + content (dict) required")
    return _post("/api/saves", {"relPath": rel_path, "content": content})


@mcp.tool()
def apply_save(rel_path: str) -> dict:
    """Load a saved JSON into the live studio (engine switch + every param
    applied). Equivalent to the user clicking that file in My Saves. Returns
    the applied params so you can sanity-check.
    """
    preset = _get("/api/saves", {"file": rel_path})
    if "error" in preset:
        return preset
    params = preset.get("params") or {}
    engine_id = preset.get("engineId")
    seed_url = preset.get("seedUrl")
    body: dict = {}
    if engine_id:
        body["engineId"] = engine_id
    if seed_url:
        body["seedUrl"] = seed_url
    if params:
        body["params"] = params
    if not body:
        return _err("preset had no engineId/params/seedUrl to apply")
    result = _post("/api/state", body)
    return {"applied": body, "result": result}


# ── engine source (live HMR via /api/engine-source) ────────────────────────

@mcp.tool()
def read_engine_source(engine_id: str) -> dict:
    """Read the TypeScript source of an engine (engines/<id>/engine.ts or
    index.ts). Returns {id, path, code}. Use to inspect what an engine does
    before suggesting code edits.
    """
    if not engine_id:
        return _err("engine_id required")
    return _get("/api/engine-source", {"id": engine_id})


@mcp.tool()
def write_engine_source(engine_id: str, code: str) -> dict:
    """Replace an engine's full source with `code`. Next.js dev-mode HMR
    auto-reloads the engine module - live canvas updates within ~1s if the
    new code compiles. If it doesn't compile the dev overlay shows the
    error; fix and call again.

    WARNING: this overwrites the whole file. Always read_engine_source
    first if you're modifying an existing engine.
    """
    if not engine_id or not isinstance(code, str):
        return _err("engine_id + code (full file) required")
    return _put("/api/engine-source", {"id": engine_id, "code": code})


# ── canvas snapshot (see what the user sees) ────────────────────────────────

@mcp.tool()
def snapshot_canvas(save_to: str | None = None, timeout_seconds: float = 5.0) -> dict:
    """Capture the live studio canvas as a PNG so the agent can SEE the art.

    Flow: POSTs a snapshot request → browser-side <CanvasSnapshotter/> grabs
    the canvas and uploads the PNG → this tool polls until the image arrives.

    If `save_to` is given (path), writes the PNG file there and returns
    {ok, path, bytes}. Otherwise returns the base64 PNG data URL inline
    (use sparingly - large response).

    Requires the studio dev server to be running AND the /studio page to be
    open in a browser tab (the snapshotter polls every ~500ms).
    """
    # Request a fresh capture.
    req = _post("/api/canvas-snapshot", {"action": "request"})
    if "error" in req:
        return req
    target_id = req.get("requestId", 0)
    if not target_id:
        return _err("server did not assign a requestId")

    # Poll for fulfillment.
    deadline = time.time() + max(1.0, timeout_seconds)
    poll_interval = 0.3
    last = {}
    while time.time() < deadline:
        # Cheap metadata check (no image - the API now omits imageDataUrl
        # unless ?full=1, which keeps the browser snapshotter's polls light).
        last = _get("/api/canvas-snapshot")
        if "error" in last:
            return last
        if last.get("fulfilledId", 0) >= target_id:
            # Now fetch the full payload with the image bytes.
            last = _get("/api/canvas-snapshot", {"full": "1"})
            if "error" in last:
                return last
            if last.get("imageDataUrl"):
                break
        time.sleep(poll_interval)
    else:
        return _err(
            "snapshot timed out - is the studio open in a browser tab? "
            "The <CanvasSnapshotter/> needs an active /studio page to "
            "respond to capture requests.",
            requestId=target_id, lastSeen=last,
        )

    data_url: str = last["imageDataUrl"]
    if save_to:
        try:
            # Strip "data:image/png;base64," prefix
            comma = data_url.index(",")
            png_bytes = base64.b64decode(data_url[comma + 1:])
            os.makedirs(os.path.dirname(os.path.abspath(save_to)) or ".", exist_ok=True)
            with open(save_to, "wb") as f:
                f.write(png_bytes)
            return {
                "ok": True,
                "path": os.path.abspath(save_to),
                "bytes": len(png_bytes),
                "capturedAt": last.get("capturedAt"),
            }
        except Exception as e:
            return _err(f"failed to write {save_to}: {e}")

    return {
        "ok": True,
        "imageDataUrl": data_url,
        "capturedAt": last.get("capturedAt"),
        "bytes_b64": len(data_url),
    }


# ── meta ───────────────────────────────────────────────────────────────────

@mcp.tool()
def vibedna_info() -> dict:
    """Self-describe: what this MCP does, current studio URL, available tools."""
    return {
        "name": "studio-mcp",
        "purpose": "Direct bridge to Generative Studio - read live canvas, "
                   "control sliders, manage saves, edit engines.",
        "studio_url": STUDIO_URL,
        "studio_running_check_hint": "Call get_state. If it returns a "
                                     "connection error, start your studio and "
                                     "check that STUDIO_URL points at it.",
        "homepage": "https://vibedna.ai/store/vibegen",
        "source": "https://github.com/marstudio360/vibegen-mcp",
        "support": "admin@vibedna.ai",
        "tools": [
            "get_state", "set_params", "set_engine", "highlight_params",
            "list_saves", "read_save", "write_save", "apply_save",
            "read_engine_source", "write_engine_source",
            "snapshot_canvas",
        ],
        "deferred_v2": ["bake_video", "export_png", "diff_params"],
    }


if __name__ == "__main__":
    mcp.run()
