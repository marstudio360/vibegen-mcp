# VibeGen MCP

Lets your AI drive a live generative art studio: read the canvas, move knobs, switch engines.

VibeGen MCP connects your AI to a running VibeGen generative art studio over the studio's HTTP API. It reads the live canvas state and every parameter, moves sliders and switches engines in real time, briefly highlights the controls it is talking about, saves, lists, reads and applies presets as JSON files, and captures a PNG snapshot of the canvas so the AI can see what it made. It can also read an engine's source (GLSL or TypeScript) and write a new version that hot-reloads into the canvas.

Point it at the hosted studio (reached through vibedna.ai/studio) or at your own instance. The art renders in the browser, on your own GPU. What the studio allows depends on your studio tier: writing engine source needs a token that the studio accepts.

Homepage: https://vibedna.ai/store/vibegen

## Tools (12)

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
| `vibedna_info()` | What this MCP does and which studio it points at |

## Install

```bash
git clone https://github.com/marstudio360/vibegen-mcp
cd vibegen-mcp
pip install -r requirements.txt
```

Python 3.11+.

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

To watch the changes live, open the studio with `?remote=1` (for example `http://localhost:3000/?remote=1`).

## Network

Every call goes to `STUDIO_URL` and nowhere else.

## License

MIT, see [LICENSE](./LICENSE). Copyright (c) 2026 VibeDNA.

Support: admin@vibedna.ai
