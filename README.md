# VibeGen MCP

Lets your AI drive a live generative art studio: read the canvas, move knobs, switch engines.

VibeGen MCP connects your AI to a running VibeGen generative art studio over the studio's HTTP API. It reads the live canvas state and every parameter, moves sliders and switches engines in real time, briefly highlights the controls it is talking about, saves, lists, reads and applies presets as JSON files, and captures a PNG snapshot of the canvas so the AI can see what it made. It can also read an engine's source (GLSL or TypeScript) and write a new version that hot-reloads into the canvas.

It also renders files with no studio tab open: it lists every scene with its sliders, defaults and curated looks, and renders a PNG, an MP4, or an audio-reactive MP4 with your song inside (the same as the studio's "Export the whole song"). The same request always renders the same pixels.

Point it at the hosted studio (https://studio.vibedna.ai, reached through vibedna.ai/studio) or at your own instance. The art renders in the browser, on your own GPU. What the studio allows depends on your studio tier: writing engine source needs a token that the studio accepts.

Homepage: https://vibedna.ai/store/vibegen

## Tools (17)

| Tool | What it does |
|---|---|
| `get_state()` | Engine id, every parameter value, schema, applied recipe |
| `set_params(params)` | Partial parameter update, applied live |
| `set_engine(engine_id)` | Switch engine |
| `highlight_params(keys)` | Briefly flash specific sliders |
| `list_saves()` | List preset JSON files in the studio's saves folder |
| `read_save(rel_path)` | Read one preset |
| `write_save(rel_path, content)` | Write a preset |
| `apply_save(rel_path)` | Load a preset into the live studio |
| `read_engine_source(engine_id)` | Read an engine's source |
| `write_engine_source(engine_id, code)` | Replace an engine's source; the studio hot-reloads it |
| `snapshot_canvas(save_to, timeout_seconds)` | PNG capture of the live canvas |
| `list_catalog(scene, save_to)` | Every scene and its curated looks; one scene's sliders, defaults and looks; or the whole catalog to a JSON file |
| `render_still(engine_id, out_path, ...)` | PNG of a scene, no studio tab needed |
| `render_video(engine_id, out_path, ...)` | MP4 of a scene (up to 120 s, up to 4096 px) |
| `render_song(engine_id, song_path, out_path, ...)` | Audio-reactive MP4 with the song inside: music knobs, automation lanes, start and end cut |
| `check_for_update()` | Whether a newer version is published, and how to update |
| `vibedna_info()` | What this MCP does and which studio it points at |

## Install

```bash
git clone https://github.com/marstudio360/vibegen-mcp
cd vibegen-mcp
pip install -r requirements.txt
```

Python 3.10+. The render tools also need Playwright (optional): `pip install playwright && playwright install chromium`.

### Claude Code

```bash
claude mcp add vibegen --scope user -e STUDIO_URL=http://localhost:3000 -- python /absolute/path/to/vibegen-mcp/server.py
```

Or in a project's `.mcp.json`:

```json
{
  "mcpServers": {
    "vibegen": {
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

### Cursor

Add the same `mcpServers` block to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).

### Claude Desktop

Add the same `mcpServers` block to `claude_desktop_config.json` (Settings > Developer > Edit Config), then restart Claude Desktop.

The shortest path for the hosted studio: open vibedna.ai/studio, click **Set up in your AI**, and drop the file it gives you into your AI chat. [INSTALL.md](./INSTALL.md) covers the manual path step by step.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `STUDIO_URL` | `http://localhost:3000` | The studio API host to drive |
| `STUDIO_TOKEN` | (empty) | Sent as `x-studio-token`; needed only when the studio enforces one |
| `STUDIO_CHROME_ARGS` | picked per OS | Browser flags for the render tools, if the defaults do not reach your GPU |
| `STUDIO_RENDER_TIMEOUT` | `1800` | Longest single render, in seconds |

The render tools open the studio's `/embed` page in a headless browser on your machine and render on your GPU. On the hosted studio they need an Ultra token in `STUDIO_TOKEN`; a studio you run yourself always allows them.

To watch the changes live, open the studio with `?remote=1` (for example `http://localhost:3000/?remote=1`).

## Network

Every call goes to `STUDIO_URL`, except `check_for_update()`, which asks `https://vibedna.ai/api/mcp/latest?slug=vibegen` for the published version number and sends nothing about you.

## License

MIT, see [LICENSE](./LICENSE). Copyright (c) 2026 VibeDNA.

Support: admin@vibedna.ai
