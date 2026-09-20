"""Shared utility functions for protocol simulations."""

import hashlib
from datetime import datetime, timezone


def _get_simulated_ip(domain: str) -> str:
    """Generate a consistent simulated IPv4 address for a domain name."""
    hash_val = int(hashlib.md5(domain.encode()).hexdigest()[:8], 16)
    octets = [
        104 + (hash_val % 50),
        (hash_val >> 8) % 250 + 1,
        (hash_val >> 16) % 250 + 1,
        (hash_val >> 24) % 250 + 1,
    ]
    return f"{octets[0]}.{octets[1]}.{octets[2]}.{octets[3]}"


def _get_http_date() -> str:
    """Return RFC 1123 compliant date string."""
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
