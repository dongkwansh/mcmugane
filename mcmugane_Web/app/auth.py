from __future__ import annotations
import os, json, time, hmac, base64, hashlib, secrets
from pathlib import Path
from typing import Dict, Any, Tuple
from fastapi import HTTPException, Request

USERS_PATH = Path(os.getenv("USERS_PATH", Path(__file__).resolve().parents[1] / "configs" / "users.json"))
SECRET_KEY = os.getenv("AUTH_SECRET", "change-this-secret")

def pbkdf2_hash(password: str, salt: str, rounds: int = 120000) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), rounds, dklen=32)
    return base64.urlsafe_b64encode(dk).decode()

def load_users() -> Dict[str, Any]:
    if not USERS_PATH.exists():
        return {}
    with open(USERS_PATH, "r") as f:
        return json.load(f)

def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    return hmac.compare_digest(pbkdf2_hash(password, salt), stored_hash)

def _sign(payload: str) -> str:
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode()

def create_token(username: str, minutes: int = 720) -> str:
    exp = int(time.time()) + minutes * 60
    nonce = secrets.token_hex(8)
    payload = f"{username}|{exp}|{nonce}"
    token = base64.urlsafe_b64encode((payload + "|" + _sign(payload)).encode()).decode()
    return token

def verify_token(token: str) -> Tuple[str, int]:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.split("|")
        assert len(parts) == 4, "bad_token_format"
        username, exp_s, nonce, sig = parts
        payload = f"{username}|{exp_s}|{nonce}"
        if not hmac.compare_digest(sig, _sign(payload)):
            raise AssertionError("bad_signature")
        exp = int(exp_s)
        if exp < int(time.time()):
            raise AssertionError("expired")
        return username, exp
    except Exception:
        raise HTTPException(status_code=401, detail="invalid_token")

def token_from_request(request: Request) -> str:
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    raise HTTPException(status_code=401, detail="missing_token")

def require_auth(request: Request) -> str:
    token = token_from_request(request)
    username, _ = verify_token(token)
    return username
