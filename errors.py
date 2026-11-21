"""Errors shared by the engine and its helpers."""


class GameError(Exception):
    """A Mini App request that can't be honoured; `code` goes back to the client."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
