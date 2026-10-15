"""auth.py — a minimal OAuth 2.1 authorization server for assignment-mcp.

Copied from the your-protected-notes prototype (ADR-0002 there): claude.ai
custom connectors obtain tokens via OAuth — discovery, dynamic client
registration, PKCE, a browser sign-in. This server is its own authorization
server. The login page checks credentials against Neon Auth and the token
endpoint hands back Neon Auth's own JWTs, which server.py already verifies.

Prototype-grade, honestly: in-memory stores (single instance), public
clients + PKCE only, codes expire in 5 minutes.
"""
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

ISSUER = (os.environ.get("PUBLIC_URL") or "http://127.0.0.1:8000").rstrip("/")
# NEON_AUTH_BASE_URL present => Managed Better Auth; otherwise legacy Stack.
NEON_AUTH_BASE_URL = os.environ.get("NEON_AUTH_BASE_URL", "").rstrip("/")
BETTER = bool(NEON_AUTH_BASE_URL)
BA_COOKIE = "__Secure-neon-auth.session_token"
_m = __import__("re").search(r"/projects/([0-9a-fA-F-]+)/", os.environ.get("NEON_AUTH_JWKS_URL", ""))
STACK_PROJECT_ID = os.environ.get("STACK_PROJECT_ID") or (_m.group(1) if _m else "")
STACK_PUB_CLIENT_KEY = os.environ.get("STACK_PUB_CLIENT_KEY", "")

GUEST_TOKEN = "guest-no-shelf"   # declared guest credential. server.py maps it
# to guest mode on purpose — distinct from an absent header and from a bad token.

_codes: dict = {}
_clients: dict = {}


def _better(path, payload=None, cookie=None, method=None):
    """Managed Better Auth REST. Origin is required; the session is a cookie;
    GET /token exchanges the session for a short-lived EdDSA JWT."""
    h = {"Content-Type": "application/json",
         "Origin": NEON_AUTH_BASE_URL.split("/neondb")[0] if "/neondb" in NEON_AUTH_BASE_URL else NEON_AUTH_BASE_URL}
    if cookie:
        h["Cookie"] = f"{BA_COOKIE}={cookie}"
    req = urllib.request.Request(NEON_AUTH_BASE_URL + path,
                                 json.dumps(payload).encode() if payload is not None else None, h, method=method)
    with urllib.request.urlopen(req) as r:
        cookies = r.headers.get_all("Set-Cookie") or []
        session = ""
        for c in cookies:
            first = c.split(";")[0]
            if first.startswith(BA_COOKIE + "="):
                session = first.split("=", 1)[1]
        return json.loads(r.read() or b"{}"), session


def _better_login(email, password, signup):
    """Returns (jwt_access_token, session_refresh_token)."""
    path = "/sign-up/email" if signup else "/sign-in/email"
    payload = {"email": email, "password": password}
    if signup:
        payload["name"] = email.split("@")[0]
    _, session = _better(path, payload)
    if not session:
        raise RuntimeError("no session cookie returned")
    out, _ = _better("/token", cookie=session, method="GET")
    return out["token"], session


def _stack(path, payload=None, headers=None):
    h = {"Content-Type": "application/json",
         "X-Stack-Project-Id": STACK_PROJECT_ID,
         "X-Stack-Publishable-Client-Key": STACK_PUB_CLIENT_KEY,
         "X-Stack-Access-Type": "client"}
    if headers:
        h.update(headers)
    req = urllib.request.Request("https://api.stack-auth.com/api/v1" + path,
                                 json.dumps(payload).encode() if payload is not None else None, h)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


LOGIN_FORM = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in — assignment-mcp</title>
<style>
body{{font-family:Georgia,serif;background:#FBF7EE;display:flex;justify-content:center;padding-top:8vh}}
.card{{background:#fff;border:2px solid #1E4D2B;border-radius:14px;padding:28px 32px;width:340px}}
h1{{font-family:system-ui,sans-serif;color:#1E4D2B;font-size:1.15em;margin:0 0 4px}}
p{{font-size:.85em;color:#555;margin:4px 0 14px}}
input,button{{width:100%;box-sizing:border-box;padding:10px;margin:5px 0;border-radius:8px;font-size:.95em}}
input{{border:1px solid #1E4D2B55;background:#fffef9}}
button{{border:none;background:#1E4D2B;color:#fff;font-weight:bold;cursor:pointer}}
.alt{{background:#fff;color:#1E4D2B;border:2px solid #1E4D2B}}
.err{{color:#F0654E;font-size:.85em}}</style></head><body>
<div class="card"><h1>assignment-mcp</h1>
<p>Sign in to see your coursework. A guest sees none of it. {err}</p>
<form method="post" action="{issuer}/authorize">
{hidden}
<input name="email" type="email" placeholder="email" required>
<input name="password" type="password" placeholder="password" required>
<button name="mode" value="signin" type="submit">Sign in</button>
<button name="mode" value="signup" type="submit" class="alt">New here — sign up</button>
<button name="mode" value="guest" type="submit" class="alt" formnovalidate style="border-style:dashed;color:#777;border-color:#999">Continue as guest — no coursework</button>
</form></div></body></html>"""


def register_oauth_routes(mcp):
    @mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
    async def as_metadata(request: Request):
        return JSONResponse({
            "issuer": ISSUER,
            "authorization_endpoint": f"{ISSUER}/authorize",
            "token_endpoint": f"{ISSUER}/token",
            "registration_endpoint": f"{ISSUER}/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        })

    @mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
    async def pr_metadata(request: Request):
        return JSONResponse({"resource": f"{ISSUER}/mcp",
                             "authorization_servers": [ISSUER]})

    @mcp.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET"])
    async def pr_metadata2(request: Request):
        return await pr_metadata(request)

    @mcp.custom_route("/register", methods=["POST"])
    async def register(request: Request):
        body = json.loads(await request.body() or b"{}")
        client_id = secrets.token_urlsafe(16)
        _clients[client_id] = {"redirect_uris": body.get("redirect_uris", [])}
        return JSONResponse({"client_id": client_id,
                             "token_endpoint_auth_method": "none",
                             "redirect_uris": body.get("redirect_uris", []),
                             "grant_types": ["authorization_code", "refresh_token"],
                             "response_types": ["code"]}, status_code=201)

    def _render_form(params, err=""):
        hidden = "\n".join(
            f'<input type="hidden" name="{k}" value="{urllib.parse.quote(v, safe="")}">'
            for k, v in params.items())
        return HTMLResponse(LOGIN_FORM.format(issuer=ISSUER, hidden=hidden,
                                              err=f'<span class="err">{err}</span>' if err else ""))

    @mcp.custom_route("/authorize", methods=["GET"])
    async def authorize_get(request: Request):
        q = dict(request.query_params)
        keep = {k: q.get(k, "") for k in
                ("client_id", "redirect_uri", "state", "code_challenge",
                 "code_challenge_method", "response_type", "scope", "resource")}
        return _render_form(keep)

    @mcp.custom_route("/authorize", methods=["POST"])
    async def authorize_post(request: Request):
        form = dict(await request.form())
        params = {k: urllib.parse.unquote(form.get(k, "")) for k in
                  ("client_id", "redirect_uri", "state", "code_challenge",
                   "code_challenge_method", "response_type", "scope", "resource")}
        if form.get("mode") == "guest":
            code = secrets.token_urlsafe(24)
            _codes[code] = {"tokens": {"access_token": GUEST_TOKEN, "refresh_token": GUEST_TOKEN},
                            "code_challenge": params["code_challenge"],
                            "redirect_uri": params["redirect_uri"],
                            "client_id": params["client_id"],
                            "exp": time.time() + 300}
            sep = "&" if "?" in params["redirect_uri"] else "?"
            return RedirectResponse(
                f'{params["redirect_uri"]}{sep}code={code}&state={urllib.parse.quote(params["state"], safe="")}',
                status_code=302)
        email, password = form.get("email", ""), form.get("password", "")
        signup = form.get("mode") == "signup"
        try:
            if BETTER:
                jwt_tok, session = _better_login(email, password, signup)
                tokens = {"access_token": jwt_tok, "refresh_token": "ba:" + session}
            else:
                path = "/auth/password/sign-up" if signup else "/auth/password/sign-in"
                payload = {"email": email, "password": password}
                if signup:
                    payload["verification_callback_url"] = ISSUER
                tokens = _stack(path, payload)
        except (urllib.error.HTTPError, RuntimeError) as e:
            try:
                stack_code = json.loads(e.read()).get("code", "")
            except Exception:
                stack_code = ""
            if "EXISTS" in stack_code or (signup and getattr(e, "code", 0) == 409):
                msg = "Good news: this email already has an account — press SIGN IN instead."
            elif not signup:
                msg = "Sign-in failed — wrong password, or no account yet (then use sign up)."
            else:
                msg = "Sign-up failed — password may be too weak (8+ characters), or try sign in."
            return _render_form(params, err=msg)
        code = secrets.token_urlsafe(24)
        _codes[code] = {"tokens": tokens,
                        "code_challenge": params["code_challenge"],
                        "redirect_uri": params["redirect_uri"],
                        "client_id": params["client_id"],
                        "exp": time.time() + 300}
        sep = "&" if "?" in params["redirect_uri"] else "?"
        return RedirectResponse(
            f'{params["redirect_uri"]}{sep}code={code}&state={urllib.parse.quote(params["state"], safe="")}',
            status_code=302)

    @mcp.custom_route("/token", methods=["POST"])
    async def token(request: Request):
        form = dict(await request.form())
        grant = form.get("grant_type")
        if grant == "authorization_code":
            rec = _codes.pop(form.get("code", ""), None)
            if not rec or rec["exp"] < time.time():
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            verifier = form.get("code_verifier", "")
            import base64
            expect = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            if rec["code_challenge"] and expect != rec["code_challenge"]:
                return JSONResponse({"error": "invalid_grant",
                                     "error_description": "PKCE verification failed"}, status_code=400)
            t = rec["tokens"]
            return JSONResponse({"access_token": t["access_token"],
                                 "token_type": "bearer",
                                 "expires_in": 900 if BETTER else 3600,
                                 "refresh_token": t.get("refresh_token", "")})
        if grant == "refresh_token":
            rt = form.get("refresh_token", "")
            if BETTER and rt.startswith("ba:"):
                try:
                    out, _ = _better("/token", cookie=rt[3:], method="GET")
                    return JSONResponse({"access_token": out["token"], "token_type": "bearer",
                                         "expires_in": 900, "refresh_token": rt})
                except Exception:
                    return JSONResponse({"error": "invalid_grant"}, status_code=400)
            if rt == GUEST_TOKEN:
                return JSONResponse({"access_token": GUEST_TOKEN, "token_type": "bearer",
                                     "expires_in": 31536000, "refresh_token": GUEST_TOKEN})
            try:
                t = _stack("/auth/sessions/current/refresh", payload={},
                           headers={"X-Stack-Refresh-Token": form.get("refresh_token", "")})
                return JSONResponse({"access_token": t["access_token"],
                                     "token_type": "bearer", "expires_in": 3600,
                                     "refresh_token": form.get("refresh_token", "")})
            except Exception:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
