from contextvars import ContextVar, Token
from typing import Optional

request_id_ctx: ContextVar[str] = ContextVar("request_id_ctx", default="")


def get_request_id() -> str:
    """
    Returns the current correlation request ID for the active asynchronous task.
    If untracked, returns 'req_untracked'.
    """
    req_id = request_id_ctx.get()
    return req_id if req_id else "req_untracked"


def set_request_id(request_id: str) -> Token[str]:
    """
    Binds a correlation request ID to the active async context.
    Returns a ContextVar Token that MUST be passed to reset_request_id in a finally block.
    """
    return request_id_ctx.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """
    Safely resets the request ID context variable to prevent leakage between requests.
    """
    request_id_ctx.reset(token)
