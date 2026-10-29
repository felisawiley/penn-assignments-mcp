# assignment-mcp

Read-only Canvas tools for a Claude model: your active courses, your published assignments, and the current academic week.

The week runs Monday 00:00 through Sunday in the server's local timezone. On Render that timezone is `America/New_York`. Locally it is whatever timezone the machine is using.

## Which thing is which

| Place | Name | What it does |
|---|---|---|
| This GitHub repo | [`penn-assignments-mcp`](https://github.com/felisawiley/penn-assignments-mcp) | The assignments project. This is the repo to keep editing. |
| The other GitHub repo | [`canvas-mcp-tool`](https://github.com/felisawiley/canvas-mcp-tool) | Used to be `my-new-instrument`. The same server was built there first. |
| Render service | `assignment-mcp` | The website Claude calls: `https://assignment-mcp-04kl.onrender.com/mcp`. |
| Neon | your Neon project | Not tied to either GitHub repo. This server does not use the database connection string. Sign-in uses `NEON_AUTH_BASE_URL` on the Render service. |

Render deploys whichever GitHub repo its Blueprint is pointed at. Point that Blueprint at `felisawiley/penn-assignments-mcp` and sync it. Leave the Render service name as `assignment-mcp`. On that service, set `PUBLIC_URL` to `https://assignment-mcp-04kl.onrender.com` (no `/mcp`). Do not reset the Neon password.

## Tools

| Tool | What it returns |
|---|---|
| `user_status()` | Guest, or the signed-in email. Always answers. |
| `canvas()` | Active courses, instructors, up to ten modules each, and the two latest announcements. |
| `assignments(course?)` | Every published assignment, earliest due date first, plus the module it lives in and links to files or pages that sit with it. Pass a course name or code (`CIS 7000`) to limit it to one class. |
| `due_this_week()` | Assignments due this Monday–Sunday week. The first line names the week and the timezone. |
| `academic_week()` | This week, next week, and where the load is heavy: two or more due the same day, or two or more from the same course. |
| `priorities(outside?)` | Open work ranked six ways: due soonest, most points, least stated time, most stated time, current grade in each course, and the unweighted mean of those scores. Without `outside`, it says to ask what else is fixed this week before anyone turns the list into a plan. |

The Canvas tools refuse a guest. Coursework is not a shared shelf ([ADR-0008](docs/adr/0008-coursework-is-not-a-commons.md)). A bad or expired token is an error, not a guest.

`assignments()` includes how you turn the work in, a short plain-text description, the module the assignment lives in, and links to files or pages placed with it or titled like it. The file itself is not downloaded. The week tools stay shorter: course, name, due date, points, turn-in status, and the Canvas link. A detailed line looks like this:

```text
- [CIS 7000] Reading response — due Sun Oct 18, 11:59 PM (10 pts) · text entry · submitted
  https://canvas.upenn.edu/courses/1/assignments/2
  Write 300 words.
  Module: Week 3
  https://canvas.upenn.edu/courses/1/modules/9
  With it:
  - Smith reading.pdf · file
    https://canvas.upenn.edu/courses/1/files/4
```

Status is shown when it changes what you would do next (`submitted`, `graded`, `pending review`, `missing`, `late`). An assignment you have not turned in yet has no status word.

## Setup

1. In Canvas, open Account → Settings → **New access token**. Copy the token. It is a password for your courses: it goes in `.env` only, never in git or chat.
2. From this folder:

```bash
cp .env.example .env
```

3. Put the token in `.env`:

```bash
CANVAS_API_TOKEN=paste-your-token
CANVAS_BASE_URL=https://canvas.upenn.edu
```

Leave `CANVAS_BASE_URL` as is for Penn. Change it if the courses live on another Canvas.

4. On the Neon project, open **Auth** and enable it (Managed Better Auth). Copy the one auth URL into `.env`, plus this server's own address and the email that may see the courses:

```bash
NEON_AUTH_BASE_URL=https://….neonauth….neon.tech/neondb/auth
PUBLIC_URL=http://127.0.0.1:8000
OWNER_EMAIL=you@upenn.edu
```

`PUBLIC_URL` on Render is `https://<your-service>.onrender.com`. Set `OWNER_EMAIL` to the account you sign in with. Without it, every signed-in user can see this Canvas. A legacy Stack Auth project uses `NEON_AUTH_JWKS_URL` and `STACK_PUB_CLIENT_KEY` instead of `NEON_AUTH_BASE_URL`.

## Run it locally

From this folder:

```bash
uv run server.py
```

The server listens on port 8000, or on `PORT` if that variable is set.

Connect it to the `claude` CLI:

```bash
claude mcp add --transport http assignment-mcp http://localhost:8000/mcp
```

The week boundary, the assignment line, and the guest / bad-token gate can be checked without a Canvas token:

```bash
uv run python -m unittest test_server.py
```

## Connect to claude.ai

claude.ai calls from Anthropic's cloud, so it cannot reach `localhost`. Use a tunnel or Render.

**Tunnel.** This lasts until you close the terminal:

```bash
cloudflared tunnel --url http://localhost:8000
```

In claude.ai, open Settings → Connectors and add the printed `https://….trycloudflare.com/mcp` URL. claude.ai may say "No sign-in — Detected". Override that to **Sign in now**, and set the OAuth client to **Register automatically (DCR)**. The server's login page opens. Sign in, or sign up. Then ask "what's my user status?" — it should name your email — and "what's due this week?"

A guest who skips sign-in gets a refusal, not the courses. The first login page can take about a minute while a free-tier server wakes up. Finish sign-in within 5 minutes; the code expires after that.

**Render.** This stays up:

1. [render.com](https://render.com) → Sign in with GitHub → **New +** → **Blueprint** → select this repo → **Apply**. [`render.yaml`](render.yaml) creates the `assignment-mcp` service and sets `TZ=America/New_York`.
2. Open that service → **Environment** and set `CANVAS_API_TOKEN`, `NEON_AUTH_BASE_URL`, `PUBLIC_URL`, and `OWNER_EMAIL`. Render does not read those from git. `PUBLIC_URL` is the service's own `https://….onrender.com` address — paste it once the service exists, then redeploy. If the Blueprint already exists, add the variables there and save.
3. Point the claude.ai connector at `https://<your-service>.onrender.com/mcp`, with the same **Sign in now** and **Register automatically (DCR)** overrides as the tunnel.

On the free plan the instance sleeps when idle. The first call after a nap takes about 30 seconds.

## Project layout

- [`server.py`](server.py) — the Canvas tools, and who is allowed to call them.
- [`auth.py`](auth.py) — the login page and OAuth endpoints Claude uses to sign in.
- [`.claude/skills/my-ways/SKILL.md`](.claude/skills/my-ways/SKILL.md) — when to use this server, and when to leave it alone.
- [`.env.example`](.env.example) — the variable names, with no token in them.
- [`test_server.py`](test_server.py) — Monday week boundary, the assignment line, and the guest / bad-token gate.
- [`docs/adr/`](docs/adr/) — why these choices: the assignments API ([ADR-0005](docs/adr/0005-canvas-rest-api-and-academic-week.md)), what a line includes ([ADR-0006](docs/adr/0006-show-the-assignment-not-just-the-deadline.md)), Eastern time on Render ([ADR-0007](docs/adr/0007-render-runs-on-eastern-time.md)), why guests see no coursework ([ADR-0008](docs/adr/0008-coursework-is-not-a-commons.md)), why a line names its module and the file beside it ([ADR-0009](docs/adr/0009-attach-the-module-and-the-file-beside-it.md)), why a ranking stays six lists ([ADR-0010](docs/adr/0010-rank-open-work-on-separate-axes.md)), and why a plan asks what is fixed outside class ([ADR-0011](docs/adr/0011-ask-what-is-fixed-outside-class.md)).
- [`render.yaml`](render.yaml) — the Render service.

## License

MPL-2.0, plus the grant for work built from the course template. See [LICENSE.txt](LICENSE.txt), [TEMPLATE-GRANT.md](TEMPLATE-GRANT.md), and [NOTICE.txt](NOTICE.txt).
