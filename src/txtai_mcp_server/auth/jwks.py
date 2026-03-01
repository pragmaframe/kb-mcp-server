import asyncio
import logging

import httpx
import jwt
from cachetools import TTLCache

logger = logging.getLogger(__name__)

GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"


class JWKSCache:
    def __init__(self, ttl: int = 300):
        self._cache: TTLCache = TTLCache(maxsize=16, ttl=ttl)
        self._lock = asyncio.Lock()

    async def get_key(self, kid: str):
        if kid in self._cache:
            return self._cache[kid]

        async with self._lock:
            # Re-check after acquiring lock (another coroutine may have fetched)
            if kid in self._cache:
                return self._cache[kid]

            logger.debug("Fetching JWKS from Google")
            async with httpx.AsyncClient() as client:
                resp = await client.get(GOOGLE_JWKS_URI, timeout=10.0)
                resp.raise_for_status()
                jwks = resp.json()

            for jwk in jwks.get("keys", []):
                k = jwk.get("kid")
                if k:
                    self._cache[k] = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)

            if kid not in self._cache:
                raise ValueError(f"kid '{kid}' not found in Google JWKS")

            return self._cache[kid]
