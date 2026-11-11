"""Encrypted session store (SQLite + Fernet).

* Each session has a random bearer token; only its SHA-256 hash is stored.
* Case state is encrypted at rest with a key from LEGALLISTEN_SECRET_KEY (or a generated key file,
  chmod 600, at data/legallisten/secret.key).
* Sessions expire after LEGALLISTEN_RETENTION_DAYS (default 30) and can be deleted by the client at any time.
* Accounts are optional. Passwords are hashed with scrypt; the e-mail is stored as a keyed hash (for login)
  and encrypted (for display), the name is encrypted, and login tokens are stored only as SHA-256 hashes.
  A signed-in user's consultations are linked to the account so they can be reopened on any device;
  deleting the account deletes all of them.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .knowledge import ROOT
from .state import CaseState

DATA_DIR = Path(os.environ.get("LEGALLISTEN_DATA_DIR", ROOT / "data" / "legallisten"))


def _key() -> bytes:
    env = os.environ.get("LEGALLISTEN_SECRET_KEY")
    if env:
        return env.encode()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "secret.key"
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        os.chmod(path, 0o600)
    return path.read_bytes().strip()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: Path | None = None, retention_days: int | None = None):
        self.path = Path(path or DATA_DIR / "sessions.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = _key()
        self.fernet = Fernet(key)
        self.email_secret = hashlib.sha256(b"legallisten-email|" + key).digest()
        self.retention = retention_days if retention_days is not None else int(os.environ.get("LEGALLISTEN_RETENTION_DAYS", "30"))
        self.lock = threading.Lock()
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, "
                       "created TEXT NOT NULL, updated TEXT NOT NULL, blob BLOB NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email_key TEXT UNIQUE NOT NULL, "
                       "email_enc BLOB NOT NULL, name_enc BLOB NOT NULL, pw_hash TEXT NOT NULL, lang TEXT, created TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS logins (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
                       "expires TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS owned (session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
                       "token_enc BLOB NOT NULL)")
        self.purge()

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def create(self, state: CaseState) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock, self._db() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (state.session_id, _hash(token), state.created,
                                                                  state.updated, self._enc(state)))
        return token

    def load(self, session_id: str, token: str) -> CaseState | None:
        with self._db() as db:
            row = db.execute("SELECT token_hash, blob FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row or not hmac.compare_digest(row[0], _hash(token or "")):
            return None
        try:
            return CaseState.model_validate_json(self.fernet.decrypt(row[1]))
        except InvalidToken:
            return None

    def save(self, state: CaseState) -> None:
        with self.lock, self._db() as db:
            db.execute("UPDATE sessions SET updated=?, blob=? WHERE id=?", (state.updated, self._enc(state), state.session_id))

    def delete(self, session_id: str, token: str) -> bool:
        if self.load(session_id, token) is None:
            return False
        with self.lock, self._db() as db:
            db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            db.execute("DELETE FROM owned WHERE session_id=?", (session_id,))
        return True

    def purge(self) -> int:
        now = dt.datetime.now(dt.timezone.utc)
        cutoff = (now - dt.timedelta(days=self.retention)).isoformat(timespec="seconds")
        with self.lock, self._db() as db:
            cur = db.execute("DELETE FROM sessions WHERE updated < ?", (cutoff,))
            db.execute("DELETE FROM owned WHERE session_id NOT IN (SELECT id FROM sessions)")
            db.execute("DELETE FROM logins WHERE expires < ?", (now.isoformat(timespec="seconds"),))
            return cur.rowcount

    # ------------------------------------------------------------------ accounts
    def _email_key(self, email: str) -> str:
        return hmac.new(self.email_secret, email.strip().lower().encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _pw_hash(password: str, salt: bytes | None = None) -> str:
        salt = salt or secrets.token_bytes(16)
        h = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
        return f"scrypt${salt.hex()}${h.hex()}"

    @classmethod
    def _pw_ok(cls, password: str, stored: str) -> bool:
        try:
            _, salt, _h = stored.split("$")
            return hmac.compare_digest(cls._pw_hash(password, bytes.fromhex(salt)), stored)
        except ValueError:
            return False

    def register(self, email: str, password: str, name: str, lang: str) -> str | None:
        """New user id, or None when the e-mail is already registered."""
        uid = secrets.token_hex(12)
        try:
            with self.lock, self._db() as db:
                db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)", (
                    uid, self._email_key(email), self.fernet.encrypt(email.strip().lower().encode()),
                    self.fernet.encrypt(name.strip().encode()), self._pw_hash(password), lang,
                    dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")))
        except sqlite3.IntegrityError:
            return None
        return uid

    def authenticate(self, email: str, password: str) -> str | None:
        with self._db() as db:
            row = db.execute("SELECT id, pw_hash FROM users WHERE email_key=?", (self._email_key(email),)).fetchone()
        if not row:
            self._pw_hash(password)            # same work either way, so timing does not reveal registered e-mails
            return None
        return row[0] if self._pw_ok(password, row[1]) else None

    def user(self, uid: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT email_enc, name_enc, lang, created FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            return None
        return {"id": uid, "email": self.fernet.decrypt(row[0]).decode(), "name": self.fernet.decrypt(row[1]).decode(),
                "lang": row[2], "created": row[3]}

    def set_user_lang(self, uid: str, lang: str) -> None:
        with self.lock, self._db() as db:
            db.execute("UPDATE users SET lang=? WHERE id=?", (lang, uid))

    def login_token(self, uid: str, days: int = 30) -> str:
        token = secrets.token_urlsafe(32)
        exp = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)).isoformat(timespec="seconds")
        with self.lock, self._db() as db:
            db.execute("INSERT INTO logins VALUES (?,?,?)", (_hash(token), uid, exp))
        return token

    def user_for_login(self, token: str | None) -> str | None:
        if not token:
            return None
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self._db() as db:
            row = db.execute("SELECT user_id FROM logins WHERE token_hash=? AND expires>=?", (_hash(token), now)).fetchone()
        return row[0] if row else None

    def logout(self, token: str) -> None:
        with self.lock, self._db() as db:
            db.execute("DELETE FROM logins WHERE token_hash=?", (_hash(token),))

    def link(self, session_id: str, token: str, uid: str) -> bool:
        """Attach a consultation to an account (the caller must hold the session token)."""
        if self.load(session_id, token) is None:
            return False
        with self.lock, self._db() as db:
            db.execute("INSERT OR REPLACE INTO owned VALUES (?,?,?)", (session_id, uid, self.fernet.encrypt(token.encode())))
        return True

    def owned(self, uid: str) -> list[tuple[str, str, CaseState]]:
        """(session id, session token, state) for every live consultation of this user, newest first."""
        with self._db() as db:
            rows = db.execute("SELECT o.session_id, o.token_enc, s.blob FROM owned o JOIN sessions s ON s.id=o.session_id "
                              "WHERE o.user_id=? ORDER BY s.updated DESC", (uid,)).fetchall()
        out = []
        for sid, tok, blob in rows:
            try:
                out.append((sid, self.fernet.decrypt(tok).decode(), CaseState.model_validate_json(self.fernet.decrypt(blob))))
            except InvalidToken:
                continue
        return out

    def delete_user(self, uid: str) -> int:
        with self.lock, self._db() as db:
            ids = [r[0] for r in db.execute("SELECT session_id FROM owned WHERE user_id=?", (uid,))]
            db.executemany("DELETE FROM sessions WHERE id=?", [(i,) for i in ids])
            db.execute("DELETE FROM owned WHERE user_id=?", (uid,))
            db.execute("DELETE FROM logins WHERE user_id=?", (uid,))
            db.execute("DELETE FROM users WHERE id=?", (uid,))
        return len(ids)

    def _enc(self, state: CaseState) -> bytes:
        return self.fernet.encrypt(state.model_dump_json().encode())
