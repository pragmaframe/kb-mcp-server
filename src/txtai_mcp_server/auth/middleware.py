import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import OAuthSettings
from .validator import GoogleJWTValidator

logger = logging.getLogger(__name__)

PROTECTED_PREFIXES = ("/sse", "/messages")


class BearerTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, validator: GoogleJWTValidator, settings: OAuthSettings):
        super().__init__(app)
        self.validator = validator
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        client = request.client.host if request.client else "unknown"

        logger.debug("auth: %s %s from %s", request.method, path, client)

        # Only protect SSE and messages routes
        if not any(path.startswith(p) for p in PROTECTED_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning(
                "auth: rejected %s %s from %s — no Bearer token (Authorization: %r)",
                request.method, path, client,
                auth_header[:40] if auth_header else "(absent)",
            )
            return self._unauthorized(request)

        token = auth_header[len("Bearer "):]
        try:
            claims = await self.validator.validate(token)
            logger.info(
                "auth: accepted %s %s from %s — sub=%s email=%s",
                request.method, path, client,
                claims.get("sub", "?"), claims.get("email", "?"),
            )
        except Exception as exc:
            logger.warning(
                "auth: rejected %s %s from %s — %s",
                request.method, path, client, exc,
            )
            return self._unauthorized(request)

        return await call_next(request)

    def _unauthorized(self, request: Request) -> Response:
        metadata_url = f"{self.settings.server_domain}/.well-known/oauth-protected-resource"
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": f'Bearer resource_metadata="{metadata_url}"'},
        )
