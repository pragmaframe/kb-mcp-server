from starlette.responses import JSONResponse
from starlette.routing import Route

from .config import OAuthSettings


def make_protected_resource_route(settings: OAuthSettings) -> Route:
    async def handler(request):
        return JSONResponse({
            "resource": settings.server_domain,
            "authorization_servers": ["https://accounts.google.com"],
            "scopes_supported": ["openid", "email"],
        })

    return Route(
        "/.well-known/oauth-protected-resource",
        endpoint=handler,
        methods=["GET"],
    )
