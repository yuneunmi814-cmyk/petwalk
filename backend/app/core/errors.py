"""Unified error contract: every failure is `{"error": {"code", "message"}}`.

Status codes are constrained to the set the API spec promises (400/401/403/404/
409/429/500) — validation failures are normalised to 400, not FastAPI's default
422, so clients only ever see the documented set.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Domain error carrying a stable machine code + safe human message."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


_STATUS_CODE = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    429: "rate_limited",
    500: "internal_error",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _on_app_error(_: Request, exc: AppError):
        headers = {"Retry-After": "60"} if exc.code == "rate_limited" else None
        return JSONResponse(
            status_code=exc.status_code, content=_body(exc.code, exc.message), headers=headers
        )

    @app.exception_handler(StarletteHTTPException)
    async def _on_http(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODE.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) else code
        return JSONResponse(status_code=exc.status_code, content=_body(code, message))

    @app.exception_handler(RequestValidationError)
    async def _on_validation(_: Request, exc: RequestValidationError):
        # Surface the first field error so the client knows what to fix.
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = first.get("msg", "validation error")
        return JSONResponse(
            status_code=400, content=_body("validation_error", f"{loc}: {msg}".strip(": "))
        )

    @app.exception_handler(Exception)
    async def _on_unhandled(_: Request, exc: Exception):  # pragma: no cover - safety net
        return JSONResponse(status_code=500, content=_body("internal_error", "Internal server error"))
