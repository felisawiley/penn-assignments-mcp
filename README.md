# penn-assignments-mcp

An MCP server that gives a Claude model a sense of coursework it doesn't
have on its own: what's assigned, what's due, and when the week is heavy —
pulled live from Canvas. See [docs/adr/0001](docs/adr/0001-canvas-rest-api-and-academic-week.md)
for the reasoning behind the API choice and the week definition.

Built from the [CIS 7000](https://www.cis.upenn.edu/) "your-first-instrument"
starter (Computationally Assisted Metacognition, Penn, Fall 2026).

## Tools

| Tool | What it does |
|---|---|
| `canvas()` | Active courses, their instructors, modules, and latest announcements. |
| `assignments(course?)` | All active (published) assignments, optionally filtered to one course by name or code. |
| `due_this_week()` | Assignments due in the current Monday–Sunday academic week, earliest first. |
| `academic_week()` | What's due this week, from which classes, what's coming next week, and which days/courses are unusually loaded. |

## Setup

1. Canvas → Account → Settings → **New access token**. Copy it.
2. Set two environment variables before running the server:

```bash
export CANVAS_API_TOKEN="paste-your-token"
export CANVAS_BASE_URL="https://canvas.upenn.edu"   # optional, this is the default
```

## Run it locally

```bash
uv run server.py     # starts the server on port 8000
```

Connect it to the `claude` CLI:

```bash
claude mcp add --transport http assignment-mcp http://localhost:8000/mcp
```

Then ask Claude something like "what's due this week?" or "give me a
synthesis of my academic week."

## Connect to claude.ai (browser)

claude.ai calls from Anthropic's cloud, so it can't reach `localhost`
directly — you need a tunnel or a deployment.

**Tunnel (temporary, dies with your terminal):**

```bash
cloudflared tunnel --url http://localhost:8000
```

Add the printed `https://….trycloudflare.com/mcp` URL under claude.ai →
Settings → Connectors.

**Deploy to Render (permanent, free tier):**

1. [render.com](https://render.com) → Sign in with GitHub → **New +** →
   **Blueprint** → select this repo → **Apply**. (`render.yaml` handles the
   rest.)
2. Set `CANVAS_API_TOKEN` as a secret environment variable in the Render
   dashboard — never commit it.
3. Copy the resulting `https://….onrender.com` URL and point a claude.ai
   connector at `https://….onrender.com/mcp`.

Free tier note: the instance naps when idle, so the first call after a nap
takes ~30s.

## License

New work under this repo is yours to license as you choose. It carries
forward attribution to the CIS 7000 template lineage it was built from —
see [NOTICE.txt](NOTICE.txt).
