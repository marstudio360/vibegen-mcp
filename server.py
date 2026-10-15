"""
studio-mcp: Direct bridge between an AI agent and a Generative Studio instance.

Lets the agent read the live canvas state, move sliders, switch engines, list
and write preset JSONs in the studio's saves directory, and edit engine source
code (the generative math) with live HMR. All ops go through the studio
server's HTTP API (/api/state, /api/saves, /api/engine-source).

Works against ANY studio instance, local, VPS, or hosted:

    STUDIO_URL     where the studio server runs
                   (default: http://localhost:3000)
    STUDIO_TOKEN   optional shared secret, sent as `x-studio-token` on every
                   request. Set this when the studio server runs with
                   STUDIO_API_TOKEN (recommended for any non-localhost host).

To see param changes live in a browser, open the studio with ?remote=1
(e.g. https://your-host/studio?remote=1), which enables the state-sync loop.

Renders (list_catalog, render_still, render_video, render_song) need no open
tab: they drive the studio's /embed page in a headless browser on this machine
(optional dependency: Playwright).
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
HTTP_TIMEOUT = 15  # seconds, generous enough for remote hosts

mcp = FastMCP("studio-mcp")

# This copy's version. Bump it when packaging; check_for_update compares it against
# what the site currently publishes, so an installed copy can tell it is behind.
VERSION = "1.1.0"
PRODUCT_SLUG = "vibegen"


@mcp.tool()
def check_for_update() -> str:
    """Is this copy behind the published version?

    Your copy is a folder on your machine, so it stays exactly as it was the day you
    installed it while fixes keep shipping. This asks what is published now and tells
    you whether to update, and how. It sends nothing about you: just a version number
    comes back."""
    try:
        r = requests.get("https://vibedna.ai/api/mcp/latest",
                         params={"slug": PRODUCT_SLUG}, timeout=15)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return f"could not reach the update check ({type(e).__name__}). Your copy still works; try later."

    latest = str(d.get("version") or "")
    if not latest:
        return "the update service did not report a version. Nothing to do."

    def parts(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except Exception:
            return (0,)

    if parts(latest) <= parts(VERSION):
        return f"up to date (you have {VERSION}, published is {latest})."

    return "\n".join([
        f"UPDATE AVAILABLE: you have {VERSION}, published is {latest}.",
        "",
        "To update:",
        f"  1. Download: https://vibedna.ai/api/free-download?slug={PRODUCT_SLUG}",
        "  2. Unzip over your current folder, keeping your own files:",
        "     your .env, your studio address and your token stay as they are.",
        "  3. Restart your AI so it loads the new tools.",
        "",
        "Nothing you made is in this folder: your presets, saves and engine code live",
        "in the studio you point at, so an update never touches your art or your presets.",
    ])


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
    poller picks it up within ~1s, sliders snap, canvas updates. Pass only
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
    """Briefly highlight specific sliders in the right CONTROLS panel, useful
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
    auto-reloads the engine module, live canvas updates within ~1s if the
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
    (use sparingly, large response).

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
        # Cheap metadata check (no image, the API now omits imageDataUrl
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
            "snapshot timed out, is the studio open in a browser tab? "
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


# ── renders: files straight from the studio, no open tab needed ──────────────
#
# These open the studio's /embed page in a headless browser on THIS machine and
# ask it for a file. The art renders on this machine's GPU with the studio's own
# engines, effects and music reactions, so a job gives the same file the studio
# would. Needs Playwright (optional):
#     pip install playwright && playwright install chromium
# Rendering through the MCP is an Ultra feature on the hosted studio; your own
# studio instance (no access code configured) is always allowed.

RENDER_TIMEOUT_S = float(os.environ.get("STUDIO_RENDER_TIMEOUT", "1800"))
_catalog_cache: dict | None = None


def _chrome_args() -> list[str]:
    extra = os.environ.get("STUDIO_CHROME_ARGS", "").strip()
    if extra:
        return extra.split()
    import sys
    if sys.platform.startswith("win"):
        return ["--enable-gpu", "--use-angle=d3d11"]
    if sys.platform.startswith("linux"):
        return ["--enable-gpu", "--use-gl=angle", "--use-angle=gl-egl", "--ignore-gpu-blocklist"]
    return ["--enable-gpu"]


def _render_allowed() -> dict | None:
    """None when this studio lets the MCP render; an error dict otherwise."""
    r = _get("/api/saves")
    if "error" in r:
        return r
    status = r.get("_status", 0)
    if status == 200:
        return None
    if status in (401, 403):
        return _err("Rendering through the MCP needs an Ultra license on the hosted studio: set STUDIO_TOKEN "
                    "to your Ultra token, or point STUDIO_URL at your own studio instance.")
    return _err(f"could not check render access (HTTP {status})")


def _with_embed(fn):
    """Open STUDIO_URL/embed headless, run fn(page), always close the browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return _err("Render tools need Playwright: pip install playwright && playwright install chromium")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=_chrome_args())
            try:
                page = browser.new_page(accept_downloads=True)
                page.set_default_timeout(RENDER_TIMEOUT_S * 1000)
                page.goto(f"{STUDIO_URL}/embed", wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_function("() => !!window.__vibegenRender && !!window.__vibegenCatalog", timeout=120_000)
                return fn(page)
            finally:
                browser.close()
    except Exception as e:
        return _err(f"render failed: {e}")


def _file_arg(path: str | None, label: str) -> tuple[str | None, str | None, dict | None]:
    """(base64, mime) for a local file, or an error dict."""
    if not path:
        return None, None, None
    if not os.path.isfile(path):
        return None, None, _err(f"{label} not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    mime = {
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".m4a": "audio/mp4",
        ".flac": "audio/flac", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii"), mime, None


_RUN_JOB_JS = """
async ({ job, song, picture }) => {
  const blobOf = (f) => f ? new Blob([Uint8Array.from(atob(f.b64), (c) => c.charCodeAt(0))], { type: f.mime }) : null;
  if (song) job.song = blobOf(song);
  if (picture) job.picture = blobOf(picture);
  const r = await window.__vibegenRender(job);
  window.__mcpLast = r.blob;
  return { mime: r.mime, width: r.width, height: r.height, frames: r.frames, durationS: r.durationS ?? null, bytes: r.blob.size };
}
"""

_SAVE_LAST_JS = """
(name) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(window.__mcpLast);
  a.download = name;
  document.body.appendChild(a);
  a.click();
}
"""


def _render(job: dict, out_path: str, song_path: str | None = None, picture_path: str | None = None) -> dict:
    denied = _render_allowed()
    if denied:
        return denied
    song_b64, song_mime, err = _file_arg(song_path, "song")
    if err:
        return err
    pic_b64, pic_mime, err = _file_arg(picture_path, "picture")
    if err:
        return err
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    def run(page):
        meta = page.evaluate(_RUN_JOB_JS, {
            "job": job,
            "song": {"b64": song_b64, "mime": song_mime} if song_b64 else None,
            "picture": {"b64": pic_b64, "mime": pic_mime} if pic_b64 else None,
        })
        with page.expect_download(timeout=120_000) as dl:
            page.evaluate(_SAVE_LAST_JS, os.path.basename(out_path))
        dl.value.save_as(out_path)
        return {"ok": True, "path": out_path, **meta}

    return _with_embed(run)


def _job(engine_id: str, mode: str, width: int, height: int, params: dict | None, fx: dict | None,
         look: str | None) -> dict:
    job: dict = {"engineId": engine_id, "mode": mode, "width": int(width), "height": int(height)}
    if params:
        job["params"] = params
    if fx:
        job["fx"] = fx
    if look:
        job["look"] = look
    return job


@mcp.tool()
def list_catalog(scene: str | None = None, save_to: str | None = None) -> dict:
    """What the studio can draw.

    No arguments: every scene (id, name, category) with the names of its curated looks.
    scene="<id>": that scene's sliders (key, type, range, default, group), defaults and curated
    looks (params + fx you can pass to the render tools).
    save_to="<path>": writes the whole catalog as JSON there.
    """
    global _catalog_cache
    if _catalog_cache is None:
        got = _with_embed(lambda page: page.evaluate("() => window.__vibegenCatalog()"))
        if isinstance(got, dict) and "error" in got:
            return got
        _catalog_cache = got
    cat = _catalog_cache
    if save_to:
        path = os.path.abspath(save_to)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cat, f, indent=1)
        return {"ok": True, "path": path, "scenes": len(cat.get("scenes", []))}
    if scene:
        for s in cat.get("scenes", []):
            if s.get("id") == scene:
                return s
        return _err(f"unknown scene {scene!r}; call list_catalog() for the ids")
    return {
        "scenes": [
            {"id": s["id"], "name": s["name"], "category": s.get("category"),
             "looks": [l["name"] for l in s.get("looks", [])]}
            for s in cat.get("scenes", [])
        ],
        "fxLooks": [l["id"] for l in cat.get("fxLooks", [])],
    }


@mcp.tool()
def render_still(engine_id: str, out_path: str, params: dict | None = None, fx: dict | None = None,
                 look: str | None = None, width: int = 1080, height: int = 1080, settle_frames: int = 60,
                 picture_path: str | None = None) -> dict:
    """Render one PNG of a scene. settle_frames: frames the scene runs before the shot.
    params/fx: sliders (see list_catalog(scene=...)); look: an effects look id.
    picture_path: your image, for the image scenes (image-trip, displacement...)."""
    job = _job(engine_id, "still", width, height, params, fx, look)
    job["settleFrames"] = int(settle_frames)
    return _render(job, out_path, picture_path=picture_path)


@mcp.tool()
def render_video(engine_id: str, out_path: str, params: dict | None = None, fx: dict | None = None,
                 look: str | None = None, width: int = 1080, height: int = 1920, duration_s: float = 10,
                 fps: int = 30, picture_path: str | None = None) -> dict:
    """Render an MP4 of a scene (no music). A video one scene loop long plays back seamlessly.
    Max 120 s and 4096 px per side."""
    job = _job(engine_id, "video", width, height, params, fx, look)
    job["durationS"] = float(duration_s)
    job["fps"] = int(fps)
    return _render(job, out_path, picture_path=picture_path)


@mcp.tool()
def render_song(engine_id: str, song_path: str, out_path: str, params: dict | None = None, fx: dict | None = None,
                look: str | None = None, width: int = 1080, height: int = 1920, fps: int = 30,
                macros: dict | None = None, lanes: list | None = None, start_s: float | None = None,
                end_s: float | None = None, picture_path: str | None = None) -> dict:
    """Render an audio-reactive MP4 of a scene with the song inside, exactly like the studio's
    "Export the whole song": same analysis, beats, accents, big kicks, section changes and pace.
    song_path: mp3/wav/ogg/m4a/flac. macros/lanes: the studio's music knobs and automation
    (studio defaults when left out). start_s/end_s: trim the song."""
    job = _job(engine_id, "song", width, height, params, fx, look)
    job["fps"] = int(fps)
    music: dict = {}
    if macros:
        music["macros"] = macros
    if lanes:
        music["lanes"] = lanes
    if start_s is not None:
        music["startS"] = float(start_s)
    if end_s is not None:
        music["endS"] = float(end_s)
    if music:
        job["music"] = music
    return _render(job, out_path, song_path=song_path, picture_path=picture_path)


# ── meta ───────────────────────────────────────────────────────────────────

@mcp.tool()
def vibedna_info() -> dict:
    """Self-describe: what this MCP does, current studio URL, available tools."""
    return {
        "name": "studio-mcp",
        "purpose": "Direct bridge to Generative Studio, read live canvas, "
                   "control sliders, manage saves, edit engines.",
        "studio_url": STUDIO_URL,
        "version": VERSION,
        "studio_running_check_hint": "Call get_state. If it returns a "
                                     "connection error, start your studio and "
                                     "check that STUDIO_URL points at it.",
        "homepage": "https://vibedna.ai/store/vibegen",
        "source": "https://github.com/marstudio360/vibegen-mcp",
        "support": "admin@vibedna.ai",
        "tools": [
            "check_for_update",
            "get_state", "set_params", "set_engine", "highlight_params",
            "list_saves", "read_save", "write_save", "apply_save",
            "read_engine_source", "write_engine_source",
            "snapshot_canvas",
            "list_catalog", "render_still", "render_video", "render_song",
        ],
        "renders_need": "Playwright (pip install playwright && playwright install chromium); "
                        "an Ultra token on the hosted studio, or your own studio instance",
    }


if __name__ == "__main__":
    mcp.run()
