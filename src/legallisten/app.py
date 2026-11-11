"""LegalListen web application (FastAPI).

    uvicorn legallisten.app:app --host 0.0.0.0 --port 8000     (or: make serve)

API (JSON; the session token goes in the X-Session-Token header):
    GET    /api/config                         languages, whether an LLM is configured, version
    POST   /api/session                        {lang, use_llm}            -> {session_id, token, messages, summary}
    POST   /api/session/{id}/message           {text, source, asr_confidence} or {chip}
    GET    /api/session/{id}                   full state view (messages, summary, graph)
    PATCH  /api/session/{id}                   {lang}                     change the preferred language
    GET    /api/session/{id}/graph             Legal Case Graph
    POST   /api/session/{id}/consultation      final consultation (JSON + Markdown)
    POST   /api/session/{id}/explain           {provision_id, mode: standard|simpler|why}
    GET    /api/session/{id}/export?fmt=md|json
    DELETE /api/session/{id}                   delete all data of this session
    GET    /api/session/{id}/drafts            ready-to-file drafts built from the case (police complaint, notice, …)
    POST   /api/transcribe                     audio file -> transcript (needs Gemini)

Accounts (optional; an HttpOnly, SameSite=Strict cookie carries the login):
    POST   /api/auth/register                  {name, email, password, lang}
    POST   /api/auth/login                     {email, password}
    POST   /api/auth/logout
    GET    /api/auth/me                        {user} (null when signed out)
    GET    /api/me/consultations               the user's consultations, on any device
    POST   /api/me/consultations/{id}/link     attach a guest consultation (needs its X-Session-Token)
    DELETE /api/me                             delete the account and all its consultations
"""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, consult, drafts
from .engine import Engine
from .i18n import LANGS
from .llm import LLMError, from_env
from .store import Store

STATIC = Path(__file__).parent / "static"
MAX_AUDIO = 10 * 1024 * 1024
AUTH_COOKIE = "ll_auth"
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


class Register(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=200)
    lang: str = "en"


class Login(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=200)


class NewSession(BaseModel):
    lang: str = "en"
    use_llm: bool = True
    conversation_date: str | None = None


class UserMessage(BaseModel):
    text: str = Field("", max_length=4000)
    source: str = "text"
    asr_confidence: float | None = None
    chip: str | None = None


class LangChange(BaseModel):
    lang: str


class ExplainReq(BaseModel):
    provision_id: str
    mode: str = "standard"


class RateLimiter:
    def __init__(self, per_minute: int = 60):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            raise HTTPException(429, "Too many requests, please slow down.")
        q.append(now)


def create_app(engine: Engine | None = None, store: Store | None = None) -> FastAPI:
    app = FastAPI(title="LegalListen", version=__version__, docs_url="/api/docs", redoc_url=None)
    eng = engine or Engine(from_env())
    db = store or Store()
    limiter = RateLimiter(int(os.environ.get("LEGALLISTEN_RATE_PER_MIN", "90")))
    auth_limiter = RateLimiter(int(os.environ.get("LEGALLISTEN_AUTH_PER_MIN", "10")))

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method != "GET":
            ip = request.client.host if request.client else "?"
            try:
                limiter.check(ip)
                if request.url.path in ("/api/auth/login", "/api/auth/register"):
                    auth_limiter.check(ip)
            except HTTPException as e:
                return JSONResponse({"detail": e.detail}, status_code=e.status_code)
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                                   "script-src 'self'; connect-src 'self'; media-src 'self' blob:")
        if request.url.path.startswith(("/api/session", "/api/auth", "/api/me")):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    def session(session_id: str, x_session_token: str = Header(default="")):
        st = db.load(session_id, x_session_token)
        if st is None:
            raise HTTPException(404, "Session not found or expired.")
        return st

    def current_user(request: Request) -> str | None:
        return db.user_for_login(request.cookies.get(AUTH_COOKIE))

    def need_user(request: Request) -> str:
        uid = current_user(request)
        if uid is None:
            raise HTTPException(401, "Please sign in.")
        return uid

    def signed_in(request: Request, uid: str) -> JSONResponse:
        resp = JSONResponse({"user": db.user(uid)})
        secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        resp.set_cookie(AUTH_COOKIE, db.login_token(uid), max_age=30 * 86400, httponly=True, samesite="strict",
                        secure=secure, path="/")
        return resp

    def view(st, full=False):
        out = {"session_id": st.session_id, "summary": eng.summary(st)}
        if full:
            out["messages"] = [m.model_dump() for m in st.messages]
            out["graph"] = eng.graph(st)
        return out

    @app.get("/api/config")
    def config():
        llm = eng.llm
        return {"version": __version__, "languages": list(LANGS), "llm_available": llm is not None,
                "llm_provider": llm.name if llm else None, "llm_model": llm.model if llm else None,
                "server_transcription": bool(llm is not None and llm.name == "gemini"),
                "retention_days": db.retention}

    @app.post("/api/session")
    def new_session(req: NewSession, request: Request):
        st = eng.start(req.lang, req.use_llm, req.conversation_date)
        token = db.create(st)
        uid = current_user(request)
        if uid:
            db.link(st.session_id, token, uid)
        return {"token": token, **view(st, full=True)}

    # ------------------------------------------------------------ accounts
    @app.post("/api/auth/register")
    def register(req: Register, request: Request):
        email = req.email.strip().lower()
        if not EMAIL_RE.match(email):
            raise HTTPException(400, "Please enter a valid e-mail address.")
        uid = db.register(email, req.password, req.name, req.lang if req.lang in LANGS else "en")
        if uid is None:
            raise HTTPException(409, "An account with this e-mail already exists. Please sign in.")
        return signed_in(request, uid)

    @app.post("/api/auth/login")
    def login(req: Login, request: Request):
        uid = db.authenticate(req.email, req.password)
        if uid is None:
            raise HTTPException(401, "E-mail or password is incorrect.")
        return signed_in(request, uid)

    @app.post("/api/auth/logout")
    def logout(request: Request):
        tok = request.cookies.get(AUTH_COOKIE)
        if tok:
            db.logout(tok)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(AUTH_COOKIE, path="/")
        return resp

    @app.get("/api/auth/me")
    def me(request: Request):
        uid = current_user(request)
        return {"user": db.user(uid) if uid else None}

    @app.get("/api/me/consultations")
    def my_consultations(uid: str = Depends(need_user)):
        out = []
        for sid, tok, st in db.owned(uid):
            sm = eng.summary(st)
            out.append({"id": sid, "token": tok, "title": sm.get("title") or "", "updated": sm.get("updated") or st.updated,
                        "lang": st.lang, "urgent": bool(sm.get("urgent")), "ready": bool(sm.get("consultation_ready"))})
        return {"consultations": out}

    @app.post("/api/me/consultations/{session_id}/link")
    def link(session_id: str, uid: str = Depends(need_user), x_session_token: str = Header(default="")):
        if not db.link(session_id, x_session_token, uid):
            raise HTTPException(404, "Session not found or expired.")
        return {"linked": True}

    @app.delete("/api/me")
    def delete_me(uid: str = Depends(need_user)):
        n = db.delete_user(uid)
        resp = JSONResponse({"deleted": True, "consultations_deleted": n})
        resp.delete_cookie(AUTH_COOKIE, path="/")
        return resp

    @app.get("/api/session/{session_id}")
    def get_session(st=Depends(session)):
        return view(st, full=True)

    @app.patch("/api/session/{session_id}")
    def change_lang(req: LangChange, st=Depends(session)):
        if req.lang not in LANGS:
            raise HTTPException(400, "unsupported language")
        st.lang = req.lang
        db.save(st)
        return view(st)

    @app.post("/api/session/{session_id}/message")
    def message(req: UserMessage, st=Depends(session)):
        if not req.text.strip() and not req.chip:
            raise HTTPException(400, "empty message")
        new = eng.handle(st, req.text, source=req.source, asr_confidence=req.asr_confidence, chip=req.chip)
        db.save(st)
        return {"messages": [m.model_dump() for m in new], **view(st), "graph": eng.graph(st)}

    @app.get("/api/session/{session_id}/graph")
    def get_graph(st=Depends(session)):
        return eng.graph(st)

    @app.post("/api/session/{session_id}/consultation")
    def consultation(st=Depends(session)):
        c = eng.consultation(st)
        db.save(st)
        return {"consultation": c, "markdown": consult.to_markdown(c)}

    @app.post("/api/session/{session_id}/explain")
    def explain(req: ExplainReq, st=Depends(session)):
        if req.mode not in ("standard", "simpler", "why"):
            raise HTTPException(400, "mode must be standard, simpler or why")
        text = eng.explain(st, req.provision_id, req.mode)
        db.save(st)
        return {"provision_id": req.provision_id, "mode": req.mode, "text": text}

    @app.get("/api/session/{session_id}/export")
    def export(fmt: str = "md", st=Depends(session)):
        c = eng.consultation(st, explain_with_llm=False)
        db.save(st)
        if fmt == "json":
            return JSONResponse({"consultation": c, "graph": eng.graph(st),
                                 "messages": [m.model_dump() for m in st.messages]},
                                headers={"Content-Disposition": 'attachment; filename="legallisten-case.json"'})
        return PlainTextResponse(consult.to_markdown(c), media_type="text/markdown; charset=utf-8",
                                 headers={"Content-Disposition": 'attachment; filename="legallisten-consultation.md"'})

    @app.get("/api/session/{session_id}/drafts")
    def get_drafts(st=Depends(session)):
        return drafts.build(st)

    @app.delete("/api/session/{session_id}")
    def delete(session_id: str, x_session_token: str = Header(default="")):
        if not db.delete(session_id, x_session_token):
            raise HTTPException(404, "Session not found or expired.")
        return {"deleted": True}

    @app.post("/api/transcribe")
    async def transcribe(audio: UploadFile = File(...), lang: str = Form("en")):
        llm = eng.llm
        if llm is None or llm.name != "gemini":
            raise HTTPException(501, "Server transcription needs a Gemini API key; use the browser microphone instead.")
        data = await audio.read()
        if len(data) > MAX_AUDIO:
            raise HTTPException(413, "Audio too long.")
        mime = (audio.content_type or "audio/webm").split(";")[0]
        lang_name = {"en": "English", "kn": "Kannada", "hi": "Hindi"}.get(lang, "English")
        prompt = ("Transcribe this audio verbatim, in the original language(s) and script the speaker uses "
                  f"(expected mainly {lang_name}; Kannada in Kannada script, Hindi in Devanagari, English words in Latin). "
                  "Do not translate, summarise or correct. Return ONLY JSON: {\"transcript\": str, \"confidence\": number "
                  "between 0 and 1, \"unclear\": [str]} — list words or phrases you could not hear clearly in \"unclear\".")
        try:
            r = llm.json(prompt, "transcribe", audio=(data, mime))
        except LLMError as e:
            raise HTTPException(502, f"Transcription failed: {e}") from e
        conf = r.get("confidence")
        conf = float(conf) if isinstance(conf, (int, float)) else 0.5
        if r.get("unclear"):
            conf = min(conf, 0.55)
        return {"transcript": str(r.get("transcript") or ""), "confidence": conf, "unclear": r.get("unclear") or []}

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/login")
    def login_page():
        return FileResponse(STATIC / "login.html")

    @app.get("/about")
    def about_page():
        return FileResponse(STATIC / "about.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app() if os.environ.get("LEGALLISTEN_NO_APP") != "1" else None
