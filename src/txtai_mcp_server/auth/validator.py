import logging

import httpx
import jwt

from .config import OAuthSettings
from .jwks import JWKSCache

logger = logging.getLogger(__name__)

GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleJWTValidator:
    def __init__(self, settings: OAuthSettings, jwks_cache: JWKSCache):
        self.settings = settings
        self.jwks_cache = jwks_cache

    async def validate(self, token: str) -> dict:
        # Detect token type: JWTs have exactly 3 dot-separated segments.
        # Google access tokens are opaque strings — route those to userinfo.
        if token.count(".") == 2:
            return await self._validate_id_token(token)
        else:
            logger.debug("Token is not a JWT — validating via userinfo endpoint")
            return await self._validate_access_token(token)

    async def _validate_id_token(self, token: str) -> dict:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise ValueError("JWT missing 'kid' header")

        public_key = await self.jwks_cache.get_key(kid)

        claims = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=self.settings.google_client_id,
            options={"require": ["exp", "iss", "aud", "email"]},
        )

        if claims["iss"] not in GOOGLE_ISSUERS:
            raise ValueError(f"Untrusted issuer: {claims['iss']}")

        self._check_email(claims.get("email", ""))
        return claims

    async def _validate_access_token(self, token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )

        if resp.status_code != 200:
            raise ValueError(
                f"Userinfo endpoint returned {resp.status_code}: {resp.text[:200]}"
            )

        claims = resp.json()
        logger.debug("Userinfo claims: %s", {k: claims.get(k) for k in ("sub", "email", "hd")})

        self._check_email(claims.get("email", ""))
        return claims

    def _check_email(self, email: str) -> None:
        if not email.endswith(f"@{self.settings.allowed_email_domain}"):
            raise ValueError(f"Email domain not allowed: {email}")
