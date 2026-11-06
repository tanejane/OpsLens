"""Explicit browser origins shared by CORS and session CSRF validation."""
import os
from urllib.parse import urlsplit


def configured_frontend_origins():
    raw = os.getenv('OPSLENS_FRONTEND_ORIGINS')
    if raw is None:
        raw = os.getenv('OPSLENS_FRONTEND_ORIGIN', 'http://localhost:3000')
    origins = []
    for value in raw.split(','):
        origin = value.strip()
        parsed = urlsplit(origin)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment or '*' in origin
                or any(c.isspace() for c in origin)):
            raise ValueError('Frontend origins must be explicit http(s) origins without paths or wildcards')
        # Accessing port also validates its syntax/range.
        parsed.port
        origins.append(origin)
    return tuple(dict.fromkeys(origins))
