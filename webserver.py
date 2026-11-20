"""Mini App backend (Starlette): static files plus a small JSON API for the canvas.

Every /api request carries `Authorization: tma <initData>`; the chat of the match comes from
the Mini App start parameter (`c<chat id>`, set by the direct link in the group messages).
"""
import logging
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

import auth
import config
from engine import Engine, GameError, chat_from_param

LOG = logging.getLogger("carmink.web")


class NoCache(BaseHTTPMiddleware):
    """Telegram's webviews cache hard: make them revalidate, so updates show up at once."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") \
            else "no-cache"
        return response


def create_app(engine: Engine, bot_token: str, static_dir: Path = config.WEB_DIR,
               clock=time.time) -> Starlette:

    def who(request: Request) -> tuple[int, auth.Auth] | JSONResponse:
        header = request.headers.get("authorization", "")
        data = auth.validate(header[4:], bot_token, now=clock()) if header[:4] == "tma " else None
        if not data:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        chat_id = chat_from_param(data.start_param)
        if chat_id is None:
            return JSONResponse({"error": "no_game"}, status_code=400)
        return chat_id, data

    def api(handler):
        """Authenticate, run the handler, turn GameError into a 409."""
        async def wrapper(request: Request) -> Response:
            ident = who(request)
            if isinstance(ident, JSONResponse):
                return ident
            chat_id, user = ident
            try:
                return await handler(request, chat_id, user.user_id)
            except GameError as e:
                return JSONResponse({"error": e.code}, status_code=409)
        return wrapper

    async def state(request, chat_id, uid):
        return JSONResponse(engine.web_state(chat_id, uid))

    async def choose(request, chat_id, uid):
        try:
            index = int((await request.json())["index"])
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "bad_request"}, status_code=400)
        engine.choose(chat_id, uid, index)
        return JSONResponse({"ok": True})

    async def start(request, chat_id, uid):
        await engine.start_drawing(chat_id, uid)
        return JSONResponse({"ok": True})

    async def hint(request, chat_id, uid):
        return JSONResponse({"ok": True, "mask": await engine.hint(chat_id, uid)})

    async def skip(request, chat_id, uid):
        await engine.skip(chat_id, uid)
        return JSONResponse({"ok": True})

    async def post_snapshot(request, chat_id, uid):
        if int(request.headers.get("content-length") or 0) > config.SNAPSHOT_MAX_BYTES:
            return JSONResponse({"error": "bad_image"}, status_code=413)
        engine.snapshot(chat_id, uid, await request.body())
        return JSONResponse({"ok": True})

    async def get_snapshot(request, chat_id, uid):
        g = engine.games.get(chat_id)
        if not g or not g.snapshot:
            return Response(status_code=204)
        return Response(g.snapshot, media_type="image/jpeg")

    async def health(request):
        return JSONResponse({"ok": True, "games": len(engine.games)})

    routes = [
        Route("/api/health", health),
        Route("/api/state", api(state)),
        Route("/api/choose", api(choose), methods=["POST"]),
        Route("/api/start", api(start), methods=["POST"]),
        Route("/api/hint", api(hint), methods=["POST"]),
        Route("/api/skip", api(skip), methods=["POST"]),
        Route("/api/snapshot", api(post_snapshot), methods=["POST"]),
        Route("/api/snapshot.jpg", api(get_snapshot)),
        Mount("/", StaticFiles(directory=static_dir, html=True)),
    ]
    return Starlette(routes=routes, middleware=[Middleware(NoCache)])
