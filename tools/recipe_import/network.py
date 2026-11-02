"""Bounded, sequential public HTTP fetching with per-origin robots and pacing."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .urls import public_url, UnsafeURL

USER_AGENT = "RauchskiRecipeImporter/1.0 (+https://github.com/rauchmat/mealplan)"


@dataclass
class FetchResult:
    status: str
    url: str
    html: str = ""
    http_status: int | None = None
    error: str | None = None
    retry_seconds: float | None = None
    headers: dict = field(default_factory=dict)


class FetchFailure(Exception):
    def __init__(self, code, http_status=None, retry_seconds=None):
        self.code, self.http_status, self.retry_seconds = code, http_status, retry_seconds


def retry_delay(value, now=None):
    try:
        number = float(value)
        return max(0, number) if math.isfinite(number) else 3600
    except (TypeError, ValueError):
        try:
            date = parsedate_to_datetime(value)
            return max(0, (date - (now or datetime.now(timezone.utc))).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 3600


class Fetcher:
    def __init__(self, client=None, check_url=public_url, sleep=time.sleep, clock=time.monotonic):
        self.client = client or httpx.Client(timeout=httpx.Timeout(20), follow_redirects=False,
                                             headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        self.check_url = check_url
        self.sleep, self.clock = sleep, clock
        self.last = {}
        self.robots = {}
        self.cooldowns = {}

    def close(self):
        self.client.close()

    def request(self, url, headers=None, delay=2, limit=2_000_000):
        self.check_url(url)  # Recheck DNS at each hop and each retry, including robots.
        host = urlsplit(url).netloc
        if self.cooldowns.get(host, 0) > self.clock():
            raise FetchFailure("rate_limited", 429, self.cooldowns[host] - self.clock())
        remaining = delay - (self.clock() - self.last.get(host, -1e20))
        if remaining > 60:
            raise FetchFailure("crawl_delay", retry_seconds=remaining)
        if remaining > 0:
            self.sleep(remaining)
        try:
            # Stream so untrusted responses cannot fill memory; cookies are never retained.
            self.client.cookies.clear()
            with self.client.stream("GET", url, headers=headers or {}) as response:
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise FetchFailure("response_too_large", response.status_code)
                    chunks.append(chunk)
                body = b"".join(chunks)
                return response.status_code, dict(response.headers), body.decode(response.encoding or "utf-8", errors="replace")
        finally:
            self.last[host] = self.clock()

    def robots_for(self, url):
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin in self.robots:
            return self.robots[origin]
        target = origin + "/robots.txt"
        for _ in range(6):
            status, headers, body = self.request(target, limit=512_000)
            if status in {301, 302, 303, 307, 308}:
                if not headers.get("location"):
                    raise FetchFailure("invalid_redirect", status)
                target = urljoin(target, headers["location"])
                continue
            if status == 429:
                delay = retry_delay(headers.get("retry-after"))
                self.cooldowns[p.netloc] = self.clock() + delay
                raise FetchFailure("rate_limited", status, delay)
            if status in {401, 403}:
                raise FetchFailure("robots_denied", status)
            if status >= 500:
                raise FetchFailure("robots_unavailable", status, 3600)
            if status not in {200, 404, 410}:
                raise FetchFailure("robots_unavailable", status, 3600)
            parser = RobotFileParser()
            parser.parse(body.splitlines() if status == 200 else [])
            self.robots[origin] = parser
            return parser
        raise FetchFailure("redirect_limit")

    def fetch(self, url, conditional=None):
        target = url
        try:
            for _ in range(6):
                target = self.check_url(target)
                robots = self.robots_for(target)
                if not robots.can_fetch(USER_AGENT, target):
                    raise FetchFailure("robots_denied")
                delay = max(2, robots.crawl_delay(USER_AGENT) or 0)
                rate = robots.request_rate(USER_AGENT)
                if rate and rate.requests:
                    delay = max(delay, rate.seconds / rate.requests)
                # Validators belong to the exact URL, never to an unrelated redirect.
                headers = (conditional or {}) if target == url else {}
                for attempt in range(3):
                    try:
                        status, response_headers, body = self.request(target, headers, delay=delay)
                    except httpx.HTTPError:
                        if attempt == 2:
                            raise
                        self.sleep(2 ** (attempt + 1))
                        continue
                    if status < 500 or attempt == 2:
                        break
                    self.sleep(2 ** (attempt + 1))
                if status in {301, 302, 303, 307, 308}:
                    if not response_headers.get("location"):
                        raise FetchFailure("invalid_redirect", status)
                    target = urljoin(target, response_headers["location"])
                    continue
                if status == 304:
                    return FetchResult("not_modified", target, http_status=status, headers=response_headers)
                if status == 429:
                    seconds = retry_delay(response_headers.get("retry-after"))
                    self.cooldowns[urlsplit(target).netloc] = self.clock() + seconds
                    raise FetchFailure("rate_limited", status, seconds)
                if status in {401, 403}:
                    raise FetchFailure("blocked", status)
                if status in {404, 410}:
                    raise FetchFailure("not_found", status)
                if status >= 500:
                    raise FetchFailure("server_error", status, 3600)
                if status != 200:
                    raise FetchFailure("http_error", status)
                if not any(x in response_headers.get("content-type", "").lower() for x in ("text/html", "application/xhtml+xml")):
                    raise FetchFailure("unsupported_content", status)
                return FetchResult("ok", target, body, status, headers=response_headers)
            raise FetchFailure("redirect_limit")
        except UnsafeURL as exc:
            # Do not persist a rejected redirect URL or arbitrary exception text.
            return FetchResult("unsafe_url", url, error=str(exc))
        except FetchFailure as exc:
            return FetchResult(exc.code, target, http_status=exc.http_status, error=exc.code, retry_seconds=exc.retry_seconds)
        except (httpx.HTTPError, OSError):
            return FetchResult("network_error", url, error="network_error", retry_seconds=3600)
