"""Public image discovery and bounded downloads for workflow steps."""
from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from .. import __version__


MAX_WEB_HTML_BYTES = 2 * 1024 * 1024
MAX_WEB_IMAGE_BYTES = 12 * 1024 * 1024


def _is_forbidden_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str.strip("[]"))
    except ValueError:
        return True
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_forbidden_ip(str(ip.ipv4_mapped))
    return False


def validate_public_url(raw_url: str, *, resolve_dns: bool = True) -> str:
    """Validate that a URL is public HTTP(S) and does not point to internal/private networks."""
    url = str(raw_url or "").strip()
    if not url or len(url) > 2048 or any(ch in url for ch in ("\r", "\n", "\t")):
        raise ValueError("URL 格式无效")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("仅支持 http:// 或 https:// 公开链接")
    host = parsed.hostname.lower().strip(".")
    if host in {"localhost", "localhost.localdomain", "host.docker.internal", "gateway.docker.internal"} or host.endswith(
        (".local", ".internal", ".localhost")
    ):
        raise ValueError(f"安全拦截：禁止访问本地或内网地址 ({host})")
    # Check if host is a literal IP
    try:
        ipaddress.ip_address(host.strip("[]"))
        is_literal_ip = True
    except ValueError:
        is_literal_ip = False
    if is_literal_ip and _is_forbidden_ip(host):
        raise ValueError(f"安全拦截：禁止访问内网/回环 IP ({host})")
    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(f"无法解析域名 {host}：{exc}") from exc
        if not infos:
            raise ValueError(f"域名 {host} 无有效解析记录")
        for info in infos:
            addr = info[4][0]
            if _is_forbidden_ip(addr):
                raise ValueError(f"安全拦截：{host} 解析到受限地址 ({addr})")
    return url


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        joined = urllib.parse.urljoin(req.full_url, newurl)
        validate_public_url(joined, resolve_dns=True)
        return super().redirect_request(req, fp, code, msg, headers, joined)


def fetch_public_bytes(url: str, *, max_bytes: int, timeout: int = 25, accept: str = "*/*") -> tuple[bytes, str, str]:
    clean = validate_public_url(url, resolve_dns=True)
    req = urllib.request.Request(
        clean,
        headers={
            "User-Agent": f"DrawStudio/{__version__}",
            "Accept": accept,
        },
    )
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    with opener.open(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        validate_public_url(final_url, resolve_dns=False)
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"远端文件超过限制（>{max_bytes // 1048576} MB）")
            chunks.append(chunk)
    return b"".join(chunks), ctype, final_url


def image_extension(data: bytes) -> str | None:
    if len(data) < 32:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return None


class PageImageExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self.text_parts: list[str] = []
        self.images: list[dict[str, str]] = []
        self._seen_urls: set[str] = set()

    def _add_image(self, raw_url: str, alt: str = "", source: str = "img") -> None:
        u = str(raw_url or "").strip()
        if not u or u.startswith(("data:", "javascript:", "blob:")):
            return
        full = urllib.parse.urljoin(self.base_url, u)
        low = full.lower()
        if not low.startswith(("http://", "https://")):
            return
        if any(bad in low for bad in (".svg", ".ico", "favicon", "sprite", "1x1", "pixel.gif", "blank.gif")):
            return
        if full in self._seen_urls:
            return
        self._seen_urls.add(full)
        self.images.append({"url": full, "alt": (alt or "").strip()[:160], "source": source})

    @staticmethod
    def _best_from_srcset(srcset: str) -> str:
        best_url, best_w = "", -1
        for part in srcset.split(","):
            tokens = part.strip().split()
            if not tokens:
                continue
            u = tokens[0]
            w = 0
            if len(tokens) > 1 and tokens[1].endswith("w"):
                try:
                    w = int(tokens[1][:-1])
                except ValueError:
                    w = 0
            if w >= best_w:
                best_w = w
                best_url = u
        return best_url

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        ad = {k.lower(): (v or "") for k, v in attrs}
        if t in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if t == "title":
            self._in_title = True
        elif t == "meta":
            prop = (ad.get("property") or ad.get("name") or "").lower()
            if prop in {"og:image", "twitter:image", "twitter:image:src"} and ad.get("content"):
                self._add_image(ad["content"], alt=self.title or prop, source="meta")
        elif t == "img":
            alt = ad.get("alt") or ad.get("title") or ""
            src = (
                ad.get("data-original")
                or ad.get("data-src")
                or ad.get("data-lazy-src")
                or self._best_from_srcset(ad.get("srcset") or "")
                or ad.get("src")
                or ""
            )
            self._add_image(src, alt=alt, source="img")
        elif t == "a":
            href = ad.get("href") or ""
            if re.search(r"\.(?:png|jpe?g|webp)(?:\?|$)", href, re.I):
                self._add_image(href, alt=ad.get("title") or "", source="link")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif t == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        txt = " ".join(data.split())
        if not txt:
            return
        if self._in_title:
            self.title = (self.title + " " + txt).strip()[:200]
        elif len(self.text_parts) < 120:
            self.text_parts.append(txt[:200])


def search_wikimedia_images(query: str, limit: int = 10) -> list[dict[str, str]]:
    """Query Wikimedia Commons public API (no API key, no CAPTCHA, reliable thumbnails)."""
    q = str(query or "").strip()
    if not q:
        return []
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",  # File:
        "gsrsearch": f"{q} filetype:bitmap",
        "gsrlimit": str(max(4, min(20, limit))),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1280",
    })
    url = f"https://commons.wikimedia.org/w/api.php?{params}"
    raw, _, _ = fetch_public_bytes(url, max_bytes=MAX_WEB_HTML_BYTES, timeout=25, accept="application/json")
    data = json.loads(raw.decode("utf-8", errors="replace"))
    pages = (data.get("query") or {}).get("pages") or {}
    out: list[dict[str, str]] = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        ii = infos[0]
        mime = str(ii.get("mime") or "").lower()
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        img_url = str(ii.get("thumburl") or ii.get("url") or "").strip()
        if not img_url:
            continue
        title = str(page.get("title") or "").replace("File:", "").strip()
        desc = ""
        ext = ii.get("extmetadata") or {}
        if isinstance(ext.get("ImageDescription"), dict):
            desc = re.sub(r"<[^>]+>", " ", str(ext["ImageDescription"].get("value") or ""))
            desc = html.unescape(" ".join(desc.split()))[:180]
        out.append({
            "url": img_url,
            "alt": f"{title} — {desc}".strip(" —")[:200],
            "page_url": str(ii.get("descriptionurl") or url),
            "source": "wikimedia",
        })
    return out
