"""Validation of the `initData` Telegram gives to a Mini App (HMAC-SHA256, see the Bot API docs)."""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

MAX_AGE = 24 * 3600     # how old initData may be, in seconds


@dataclass(frozen=True)
class Auth:
    user_id: int
    name: str
    start_param: str | None
    auth_date: int


def sign(fields: dict[str, str], bot_token: str) -> str:
    """The `hash` Telegram would compute for these fields (also used by the tests)."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()


def validate(init_data: str, bot_token: str, now: float | None = None,
             max_age: int = MAX_AGE) -> Auth | None:
    """The user behind a genuine, fresh initData string, or None."""
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    theirs = fields.pop("hash", None)
    if not theirs or not bot_token:
        return None
    if not hmac.compare_digest(sign(fields, bot_token), theirs):
        return None
    try:
        auth_date = int(fields["auth_date"])
        user = json.loads(fields["user"])
        uid = int(user["id"])
    except (KeyError, ValueError, TypeError):
        return None
    if (now if now is not None else time.time()) - auth_date > max_age:
        return None
    name = " ".join(p for p in (user.get("first_name"), user.get("last_name")) if p) or str(uid)
    return Auth(user_id=uid, name=name, start_param=fields.get("start_param"), auth_date=auth_date)
