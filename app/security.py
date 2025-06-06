import json
import time

import jwt
import jwt.algorithms
import requests
from fastapi import HTTPException
from starlette.requests import Request

from app.utils import get_settings

_certs_cache = {}


def _parse_max_age(cache_control: str) -> int | None:
    if not cache_control:
        return None
    for part in cache_control.split(","):
        if "max-age" in part:
            try:
                return int(part.split("=")[1].strip())
            except:
                pass
    return None


# basically copied from Cloudflare's Flask example
def _get_public_keys(certs_url: str) -> list:
    """
    Get public keys from the specified URL.

    Args:
        certs_url: URL to fetch the public keys from.

    Returns:
        List of public keys.
    """
    now = time.time()
    cache_entry = _certs_cache.get(certs_url)
    if cache_entry:
        expires, keys = cache_entry
        if now < expires:
            return keys

    try:
        r = requests.get(certs_url, timeout=5)
        r.raise_for_status()
        jwk_set = r.json()

        cache_control = r.headers.get("Cache-Control", "")
        max_age = _parse_max_age(cache_control)
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    public_keys = []
    for key_dict in jwk_set.get("keys", []):
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_dict))
        public_keys.append(public_key)
    if not public_keys:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    # Cache the keys for max_age seconds from now
    # Or default to 14400 seconds (4 hours) if max_age is None - default from Cloudflare
    expires = now + (max_age if max_age is not None else 14400)
    _certs_cache[certs_url] = (expires, public_keys)

    return public_keys


def verify_token(request: Request):
    if not get_settings().require_cloudflare_zero_access:
        return

    token = request.cookies.get("CF_Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    keys = _get_public_keys(get_settings().certs_utl)
    for key in keys:
        try:
            jwt.decode(
                token, key=key, audience=get_settings().policy_aud, algorithms=["RS256"]
            )
            return
        except:
            pass
    raise HTTPException(status_code=401, detail="Unauthorized")
