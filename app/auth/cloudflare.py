import json
from functools import lru_cache

import jwt
from fastapi import HTTPException, Depends
from jwt import PyJWKClient
from starlette.requests import Request

from app.utils import get_settings


@lru_cache
def _pyjwk_client(certs_url: str, lifespan: int) -> PyJWKClient:
    """
    Get public keys from the specified URL.

    Args:
        certs_url: URL to fetch the public keys from.
        lifespan: Cache lifespan in seconds.

    Returns:
        A PyJWKClient instance
    """
    return PyJWKClient(
        certs_url,
        lifespan=lifespan,
    )


async def verify_token(request: Request) -> None:
    """
    Validate the Cloudflare CF_Authorization token.

    This is a Cloudflare Zero Trust Access token that is used to authenticate
    users.
    """

    token = request.cookies.get("CF_Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    signing_key = _pyjwk_client(
        get_settings().certs_utl,
        lifespan=get_settings().pyjwk_cache_lifespan,
    ).get_signing_key_from_jwt(token)
    try:
        claims = jwt.decode(
            token,
            key=signing_key,
            audience=get_settings().policy_aud,
            algorithms=["RS256"],
        )
        request.state.jwt_claims = claims
    except:
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_claims(request: Request) -> dict:
    """
    Get JWT claims from the request state.

    Args:
        request: The FastAPI request object.

    Returns:
        The JWT claims if available, otherwise raises an HTTPException.
    """
    if not hasattr(request.state, "jwt_claims"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return request.state.jwt_claims


def allowed_emails() -> set[str]:
    """
    Get the set of allowed emails from the allowlist file.

    Returns:
        A set of emails that are allowed to POST images.
    """
    allowlist_file = get_settings().allowlist_file
    try:
        with open(allowlist_file, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


def email_allowed(request: Request, allowlist: set[str] = Depends(allowed_emails)):
    """
    Is the email allowed on this route?

    Args:
        request: The FastAPI request object.

    """
    if not hasattr(request.state, "jwt_claims"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    claims = request.state.jwt_claims
    email = claims.get("email")

    if not email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if email not in allowlist:
        raise HTTPException(
            status_code=403,
            detail="Forbidden",
        )
