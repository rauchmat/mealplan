"""Conservative URL identity and public destination checks."""
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class UnsafeURL(ValueError):
    pass


def clean_url(value: str) -> str:
    if not isinstance(value, str) or re.search(r"[\s\x00-\x1f\x7f]", value):
        raise UnsafeURL("invalid_url")
    try:
        p = urlsplit(value)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            raise UnsafeURL("invalid_url")
        if p.port not in {None, 80 if p.scheme == "http" else 443}:
            raise UnsafeURL("nonstandard_port")
        host = p.hostname.encode("idna").decode().lower().rstrip(".")
        if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
            raise UnsafeURL("private_host")
        try:
            if not ipaddress.ip_address(host).is_global:
                raise UnsafeURL("private_address")
        except ValueError as exc:
            if isinstance(exc, UnsafeURL):
                raise
        query = []
        for key, val in parse_qsl(p.query, keep_blank_values=True):
            if key.lower().startswith("utm_") or key.lower() in {"fbclid", "igsh", "igshid", "gclid", "si", "_r", "_t", "share_app_id", "share_iid", "sender_device"}:
                continue
            if re.search(r"token|auth|session|email|phone|password|signature|invite|user_?id|sender", key, re.I) or "@" in val:
                raise UnsafeURL("sensitive_query")
            query.append((key, val))
        netloc = f"[{host}]" if ":" in host else host
        path = p.path or "/"
        # A social post's identity does not depend on the shared URL's query.
        if host in {"instagram.com", "www.instagram.com"}:
            host = "www.instagram.com"
            netloc = host
            if re.match(r"^/(?:p|reel|tv)/[^/]+/?$", path):
                path = path.rstrip("/") + "/"
                query = []
        if host in {"tiktok.com", "www.tiktok.com"} and re.match(r"^/@[^/]+/video/\d+/?$", path):
            netloc = "www.tiktok.com"
            path = path.rstrip("/")
            query = []
        return urlunsplit((p.scheme, netloc, path, urlencode(sorted(query)), ""))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, UnsafeURL):
            raise
        raise UnsafeURL("invalid_url") from exc


def public_url(value: str, resolver=socket.getaddrinfo) -> str:
    url = clean_url(value)
    p = urlsplit(url)
    addresses = resolver(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise UnsafeURL("private_address")
    return url


def platform(url: str) -> str:
    host = urlsplit(url).hostname or ""
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "instagram"
    if host == "tiktok.com" or host.endswith(".tiktok.com"):
        return "tiktok"
    return "website"
