# VibeGen MCP: Install Guide

Drive the **VibeGen** generative art studio from any MCP-capable AI (Claude Code, Claude Desktop, Cursor, or anything that speaks MCP). Your AI can:

- read the live canvas state + every parameter
- move sliders and switch engines in real time
- save, load, and apply preset JSONs
- **read and rewrite the engine's generative math** (GLSL / TypeScript) with live hot-reload into the canvas
- capture PNG snapshots so your AI can SEE what it made
- list every scene with its sliders, defaults and curated looks
- **render files with no studio tab open**: a PNG, an MP4, or an audio-reactive MP4 with your song inside

Free. Point it at a VibeGen studio (yours or the hosted one). What it can unlock depends on your studio tier.

## The fast way (let your AI do it)

1. Clone the repo somewhere stable, like `~/vibegen-mcp/`:
   ```
   git clone https://github.com/marstudio360/vibegen-mcp
   ```
   (or unzip the download from vibedna.ai).
2. Open an AI session in that folder and say:

   > "Install this VibeGen MCP. Run `pip install -r requirements.txt`, add the `.mcp.json` entry below pointing at the absolute path of server.py, set STUDIO_URL to my studio, then close and reopen the tab."

## Requirements

- Python 3.10+
- A VibeGen studio to drive (the hosted studio at vibedna.ai/studio, or one you run yourself)
- `pip install -r requirements.txt` (fastmcp, requests)
- Optional, only for the render tools: `pip install playwright && playwright install chromium`

## Configure

| Variable | What it does | Default |
|---|---|---|
| `STUDIO_URL` | the studio to drive | `http://localhost:3000` (a studio you run yourself) |
| `STUDIO_TOKEN` | shared secret sent as `x-studio-token`. Required only when the studio enforces one (your subscription token). | *(empty)* |
| `STUDIO_CHROME_ARGS` | browser flags for the render tools, if the defaults do not reach your GPU | picked per OS |
| `STUDIO_RENDER_TIMEOUT` | longest single render, in seconds | `1800` |

> **Where the studio runs: your machine, never ours.** The studio renders in your own browser (the art and the video bake happen on your GPU, client-side). Point `STUDIO_URL` at wherever you run it: `http://localhost:3000` (run it yourself), your own VPS, or the hosted studio at **https://studio.vibedna.ai**. The render still happens locally, on your GPU.

> The easiest path is not this file: go to **vibedna.ai/studio**, click **Set up in your AI**, and drop the file it gives you into your AI chat. If you're a subscriber, your token is baked in automatically. This repo is the manual path.

## Add to your MCP client

`.mcp.json`:

```json
{
  "mcpServers": {
    "vibegen": {
      "type": "stdio",
      "command": "python",
      "args": ["/absolute/path/to/vibegen-mcp/server.py"],
      "env": {
        "STUDIO_URL": "http://localhost:3000",
        "STUDIO_TOKEN": ""
      }
    }
  }
}
```

Close and reopen your tab so the MCP loads.

## Live view

To watch your AI's changes in a browser in real time, open the studio with the remote flag:

```
http://localhost:3000/?remote=1
```

That enables the state-sync loop. Without the flag, public visitors get a clean sandboxed session by design.

## Tool reference

| Tool | What it does |
|---|---|
| `get_state()` | engine id, params, schema, applied recipe |
| `set_params(params)` | move any sliders (partial updates fine) |
| `set_engine(engine_id)` | switch engine |
| `highlight_params(keys)` | flash specific sliders |
| `list_saves()` / `read_save()` / `write_save()` / `apply_save()` | preset JSON workflow |
| `read_engine_source(engine_id)` | fetch the engine's generative math |
| `write_engine_source(engine_id, code)` | rewrite the math, hot-reloads live |
| `snapshot_canvas(save_to?)` | PNG capture of the live canvas |
| `list_catalog(scene?, save_to?)` | every scene and its curated looks; one scene's sliders, defaults and looks; or the whole catalog saved to a JSON file |
| `render_still(engine_id, out_path, ...)` | a PNG of a scene, no studio tab needed (params, effects, look, size, a picture of yours for the image scenes) |
| `render_video(engine_id, out_path, ...)` | an MP4 of a scene (up to 120 s, up to 4096 px) |
| `render_song(engine_id, song_path, out_path, ...)` | an audio-reactive MP4 with your song inside, the same as the studio's "Export the whole song" (music knobs, automation lanes, start and end cut) |
| `check_for_update()` | tells you if a newer version is published, and how to update |
| `vibedna_info()` | what this MCP does and which studio it points at |

The same request always renders the same pixels. The render tools open the studio's `/embed` page in a headless browser on your machine and render on your GPU. On the hosted studio they need an Ultra token in `STUDIO_TOKEN`; a studio you run yourself always allows them.

## Trouble

- **Cannot reach studio**: the studio is not running or `STUDIO_URL` is wrong.
- **401 unauthorized**: the studio enforces a token; set the matching `STUDIO_TOKEN` (from your subscription).
- **snapshot_canvas times out**: open `<STUDIO_URL>?remote=1` in a browser tab; the snapshotter runs in the page.
- **Render tools need Playwright**: run `pip install playwright && playwright install chromium`.
- **needs an Ultra license**: the hosted studio renders for Ultra tokens only; use your Ultra token or a studio you run yourself.

## Support

`admin@vibedna.ai` · https://vibedna.ai/store/vibegen

License: MIT.

VibeDNA, 2026
