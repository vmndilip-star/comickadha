"""One error shape everywhere: {code, message}. Messages are written for kids."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorBody


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def not_found(thing: str) -> ApiError:
    return ApiError(404, "not_found", f"We couldn't find that {thing}. It may have been deleted.")


def invalid(message: str) -> ApiError:
    return ApiError(422, "invalid", message)


# Documented on every router so the generated TypeScript knows the error shape.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorBody},
    409: {"model": ErrorBody},
    422: {"model": ErrorBody},
}

FIELD_NAMES = {
    "cast_ids": "cast",
    "character_ids": "characters",
    "background_id": "place",
    "panel_count": "number of panels",
    "studio_step": "step",
    "hair_style": "hair",
    "hair_color": "hair colour",
    "synopsis": "story",
}


def friendly_validation_message(error: dict[str, Any]) -> str:
    """Turns the first Pydantic error into a sentence a kid can act on."""
    names = [
        str(p)
        for p in error.get("loc", ())
        if isinstance(p, str) and p not in ("body", "query", "path")
    ]
    raw = names[-1] if names else "answer"
    field = FIELD_NAMES.get(raw, raw.replace("_", " "))
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}

    if kind == "value_error" and "error" in ctx:
        return str(ctx["error"])
    if kind == "string_too_long":
        return f"The {field} is too long. Keep it under {ctx.get('max_length')} letters."
    if kind == "string_too_short":
        return f"Please give the {field} at least one letter."
    if kind == "missing":
        return f"Please add the {field}."
    if kind in ("literal_error", "enum"):
        return f"Please pick one of the choices for the {field}."
    if kind == "too_long":
        return f"That's too many {field}. The most you can pick is {ctx.get('max_length')}."
    return f"Something about the {field} doesn't look right. Please check it and try again."


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=ErrorBody(code=code, message=message).model_dump()
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        return _error(422, "invalid", friendly_validation_message(errors[0] if errors else {}))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return _error(404, "not_found", "We couldn't find that page.")
        if exc.status_code == 405:
            return _error(405, "not_allowed", "That button doesn't work here.")
        return _error(exc.status_code, "http_error", "Something went wrong. Please try again.")

    @app.exception_handler(Exception)
    async def _server_error(_request: Request, _exc: Exception) -> JSONResponse:
        return _error(
            500, "server_error", "Oops! Something went wrong on our side. Please try again."
        )
