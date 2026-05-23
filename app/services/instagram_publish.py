"""
Publish feed photos using Instagram Graph API (Meta).

Requirements (Meta):
- Instagram Professional (Business or Creator) account
- Linked Facebook Page
- App in Meta Developer with instagram_content_publish, pages_show_list, etc.
- Long-lived Page access token

We do NOT support password-based automation (unsupported and unsafe).

Publishing needs a PUBLICLY REACHABLE HTTPS image URL for the photo step. Options:
- **Default anonymous hosts** (`META_PUBLIC_IMAGE_UPLOAD=auto`): tries catbox.moe, then 0x0.st,
  transfer.sh (and optional Imgur via `META_PUBLIC_IMAGE_UPLOAD_ORDER`). No Imgur account required.
- IMGUR_CLIENT_ID: optional Imgur uploads if you pin `imgur` in the order above.
- On **graph.facebook.com** we first try an unpublished Page photo (`META_FACEBOOK_PAGE_ID` or discover).

- INSTAGRAM_SOURCE_IMAGE_URL: bypass — your own HTTPS JPEG URL (CDN, Supabase static, signed URL, …).

- META_GRAPH_MEDIA_BASE: IG media/create/publish host. Use `https://graph.instagram.com/v21.0`
  for Instagram Business Login (“Generate token” in IG API setup). Default is facebook.com Graph.

Env (highlights):
  META_ACCESS_TOKEN           Instagram / Page token depending on META_GRAPH_MEDIA_BASE
  INSTAGRAM_BUSINESS_ID
  META_GRAPH_MEDIA_BASE       optional instagram.com vs facebook.com
  META_PUBLIC_IMAGE_UPLOAD    auto | catbox | 0x0 | transfer_sh | file_io | imgur (comma list also ok)
  META_PUBLIC_IMAGE_UPLOAD_ORDER   override auto-order, e.g. catbox,file_io,0x0
  META_SKIP_FACEBOOK_PAGE_STAGING  true→ skip FB Page unpublished-photo step
  META_FACEBOOK_PAGE_ID
  IMGUR_CLIENT_ID             optional
"""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

GRAPH_VER = "v21.0"
# Facebook-only: Page tie-in + photo uploads (Instagram-login tokens reject these).
FACEBOOK_GRAPH = f"https://graph.facebook.com/{GRAPH_VER}"


def media_graph_root() -> str:
    """
    Host for IG media container + publish. Instagram Login → graph.instagram.com
    Facebook Login / classic Page flows → graph.facebook.com (default).
    """
    explicit = os.getenv("META_GRAPH_MEDIA_BASE", "").strip().rstrip("/")
    return explicit if explicit else FACEBOOK_GRAPH


def is_facebook_media_host(media_root: str) -> bool:
    return "facebook.com" in media_root.lower()


def discover_facebook_page_for_instagram(access_token: str, instagram_business_id: str) -> str | None:
    """Return Facebook Page ``id`` whose linked IG business account matches ``instagram_business_id``."""
    ig_target = str(instagram_business_id).strip()
    next_params: dict[str, Any] = {
        "fields": "id,instagram_business_account",
        "access_token": access_token,
        "limit": "100",
    }
    endpoint = f"{FACEBOOK_GRAPH}/me/accounts"
    while endpoint:
        r = requests.get(endpoint, params=next_params, timeout=60)
        next_params = {}
        payload: dict[str, Any] = r.json()
        if r.status_code >= 400 or "error" in payload:
            logger.warning("Could not read /me/accounts for Page discovery: %s", payload)
            return None
        for row in payload.get("data") or []:
            ig = row.get("instagram_business_account") or {}
            if str(ig.get("id") or "") == ig_target:
                pid = row.get("id")
                if pid:
                    return str(pid)
        paging = payload.get("paging") or {}
        endpoint = paging.get("next") or ""
    return None


def facebook_unpublished_photo_public_url(page_id: str, access_token: str, jpeg_path: Path) -> str:
    """
    Upload JPEG as unpublished Page Photo; return a CDN ``source`` URL for Instagram ``image_url``.

    Requires a token with permission to publish photos on that Page (e.g. pages_manage_posts).
    """
    with jpeg_path.open("rb") as fp:
        r = requests.post(
            f"{FACEBOOK_GRAPH}/{page_id}/photos",
            data={"published": "false", "access_token": access_token},
            files={"source": (jpeg_path.name, fp, "image/jpeg")},
            timeout=120,
        )
    uploaded: dict[str, Any] = r.json()
    if r.status_code >= 400 or "error" in uploaded:
        raise RuntimeError(f"Facebook Page photo upload failed ({r.status_code}): {uploaded}")

    photo_id = uploaded.get("id")
    if not photo_id:
        raise RuntimeError(f"Unexpected Page photo upload response: {uploaded}")

    ur = requests.get(
        f"{FACEBOOK_GRAPH}/{photo_id}",
        params={"fields": "images,width,height,picture", "access_token": access_token},
        timeout=60,
    )
    info: dict[str, Any] = ur.json()
    if ur.status_code >= 400 or "error" in info:
        raise RuntimeError(f"Could not fetch uploaded photo preview ({ur.status_code}): {info}")

    images = info.get("images") or []
    if images:
        best = sorted(
            (img for img in images if isinstance(img, dict) and img.get("source")),
            key=lambda img: int(img.get("width") or 0),
            reverse=True,
        )
        url = best[0].get("source") if best else None
        if url:
            return str(url)

    pic = info.get("picture")
    if isinstance(pic, str) and pic.startswith("http"):
        return pic

    raise RuntimeError(f"Facebook photo missing public image URL fields: {info}")


# --- Anonymous public hosts so Meta can `image_url`-fetch our JPEG ---
_DEFAULT_PUBLIC_UPLOAD_ORDER = ("catbox", "zero_x_zero", "file_io", "transfer_sh")


def _https_url(raw: str) -> str:
    u = raw.strip()
    return "https://" + u[7:] if u.startswith("http://") else u


def _canonical_backend(tag: str) -> str:
    k = tag.strip().lower().replace("-", "_")
    return {"0x0": "zero_x_zero", "oxo": "zero_x_zero"}.get(k, k)


def _parse_backend_order_override() -> list[str]:
    raw = os.getenv("META_PUBLIC_IMAGE_UPLOAD_ORDER", "").strip()
    if not raw:
        return []
    return [_canonical_backend(p) for p in raw.split(",") if p.strip()]


def _catbox_upload_jpeg(path: Path) -> str:
    rb = path.read_bytes()
    if not rb:
        raise ValueError(f"Empty file {path}")
    name = path.name or "card.jpg"
    if not name.lower().endswith((".jpg", ".jpeg")):
        name += ".jpg"
    r = requests.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": (name, rb, "image/jpeg")},
        timeout=240,
    )
    if not r.ok:
        raise RuntimeError(f"catbox HTTP {r.status_code}: {r.text[:400]}")
    url = _https_url(r.text.strip())
    if not url.startswith("https://"):
        raise RuntimeError(f"catbox unexpected body: {r.text[:160]}")
    return url


def _zero_x_zero_upload_jpeg(path: Path) -> str:
    rb = path.read_bytes()
    if not rb:
        raise ValueError(f"Empty file {path}")
    r = requests.post(
        "https://0x0.st",
        files={"file": (path.name or "card.jpg", rb, "image/jpeg")},
        timeout=240,
    )
    if not r.ok:
        raise RuntimeError(f"0x0.st HTTP {r.status_code}: {r.text[:400]}")
    url = _https_url(r.text.strip().split()[0])
    if not url.startswith("https://"):
        raise RuntimeError(f"0x0.st unexpected body: {r.text[:160]}")
    return url


def _transfer_sh_upload_jpeg(path: Path) -> str:
    rb = path.read_bytes()
    if not rb:
        raise ValueError(f"Empty file {path}")
    fname = quote(path.name or "card.jpg", safe="") or "card.jpg"
    r = requests.put(
        f"https://transfer.sh/{fname}",
        data=rb,
        headers={"Content-Type": "image/jpeg"},
        timeout=240,
    )
    if not r.ok:
        raise RuntimeError(f"transfer.sh HTTP {r.status_code}: {r.text[:400]}")
    url = _https_url(r.text.strip().splitlines()[0])
    if not url.startswith("https://"):
        raise RuntimeError(f"transfer.sh unexpected body: {r.text[:160]}")
    return url


def _file_io_upload_jpeg(path: Path) -> str:
    rb = path.read_bytes()
    if not rb:
        raise ValueError(f"Empty file {path}")
    name = path.name or "card.jpg"
    r = requests.post(
        "https://file.io",
        files={"file": (name, rb, "image/jpeg")},
        timeout=240,
    )
    try:
        j: dict[str, Any] = r.json()
    except Exception:
        raise RuntimeError(f"file.io JSON parse failed ({r.status_code}) {r.text[:400]}") from None

    ok = True
    if isinstance(j, dict) and j.get("success") is not None:
        ok = bool(j.get("success"))
    link = j.get("link") if isinstance(j, dict) else None
    if not ok:
        raise RuntimeError(f"file.io rejected ({r.status_code}): {j}")
    if not isinstance(link, str) or not link.startswith("http"):
        raise RuntimeError(f"file.io unexpected ({r.status_code}): {j}")
    return _https_url(link)


def upload_local_jpeg_to_public_https(path: Path, *, imgur_client_id: str | None) -> str:
    """Upload JPEG to anonymous host(s); Meta downloads this URL during container creation."""

    if not path.read_bytes():
        raise ValueError(f"Empty JPEG: {path}")

    mode_raw = os.getenv("META_PUBLIC_IMAGE_UPLOAD", "auto").strip()
    backends: list[str] = []

    explicit_order_cfg = _parse_backend_order_override()
    mode_lower = mode_raw.lower() if mode_raw else "auto"

    if "," in mode_raw:
        backends = [_canonical_backend(p) for p in mode_raw.split(",") if p.strip()]
    elif mode_lower == "auto":
        backends = list(explicit_order_cfg or list(_DEFAULT_PUBLIC_UPLOAD_ORDER))
        if (
            imgur_client_id
            and _normalize_imgur_client_id(imgur_client_id)
            and "imgur" not in backends
            and not explicit_order_cfg
        ):
            backends.append("imgur")
    else:
        backends = [_canonical_backend(mode_raw)]

    uniq: list[str] = []
    for b in backends:
        if b not in uniq:
            uniq.append(b)
    backends = uniq

    errors: list[str] = []

    dispatch = {
        "catbox": _catbox_upload_jpeg,
        "zero_x_zero": _zero_x_zero_upload_jpeg,
        "file_io": _file_io_upload_jpeg,
        "transfer_sh": _transfer_sh_upload_jpeg,
    }

    for name in backends:
        if name == "imgur":
            cid_ok = imgur_client_id and _normalize_imgur_client_id(imgur_client_id)
            if not cid_ok:
                errors.append("imgur skipped — empty IMGUR_CLIENT_ID")
                continue
            try:
                url = imgur_upload_jpeg(path, imgur_client_id)
                logger.info("Public image URL via imgur (%s chars)", len(url))
                return url
            except Exception as exc:
                errors.append(f"imgur: {exc}")
                continue

        fn = dispatch.get(name)
        if fn is None:
            errors.append(f"unknown_backend:{name}")
            continue
        try:
            url = fn(path)
            logger.info("Public image URL via %s", name)
            return url
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    raise RuntimeError(
        "Uploaded JPEG nowhere — all hosts failed. "
        + "Either fix network or set INSTAGRAM_SOURCE_IMAGE_URL to your HTTPS JPEG.\nDetails: "
        + " | ".join(errors)
    )


def _normalize_imgur_client_id(raw: str) -> str:
    """Strip common .env mistakes (quotes, duplicate ``Client-ID`` prefix)."""
    cid = (raw or "").strip()
    for prefix in ("Client-ID ", "client-id ", "CLIENT-ID "):
        if cid.startswith(prefix):
            cid = cid[len(prefix) :].strip()
    if len(cid) >= 2 and (
        (cid.startswith('"') and cid.endswith('"')) or (cid.startswith("'") and cid.endswith("'"))
    ):
        cid = cid[1:-1].strip()
    return cid


def _imgur_post_image(
    headers: dict[str, str],
    *,
    files: dict | None = None,
    data: dict | None = None,
) -> tuple[requests.Response, dict[str, Any]]:
    r = requests.post(
        "https://api.imgur.com/3/image",
        headers=headers,
        files=files,
        data=data,
        timeout=180,
    )
    try:
        j: dict[str, Any] = r.json()
    except Exception:
        snippet = (r.text or "")[:600]
        raise RuntimeError(f"Imgur returned non-JSON (HTTP {r.status_code}): {snippet}") from None
    return r, j


def imgur_upload_jpeg(path: Path, client_id: str) -> str:
    """Upload JPEG to Imgur anonymously; return an ``https`` `i.imgur.com` link."""
    cid = _normalize_imgur_client_id(client_id)
    if not cid:
        raise ValueError("IMGUR_CLIENT_ID is empty.")

    headers: dict[str, str] = {
        "Authorization": f"Client-ID {cid}",
        "Accept": "application/json",
    }

    rb = path.read_bytes()
    if not rb:
        raise ValueError(f"Empty file: {path}")

    multipart_err: str | None = None
    try:
        r1, j1 = _imgur_post_image(headers, files={"image": (path.name, rb, "image/jpeg")})
        ok = bool(j1.get("success")) and isinstance(j1.get("data"), dict) and j1["data"].get("link")
        if ok:
            link = str(j1["data"]["link"])
            if link.startswith("http://"):
                link = "https://" + link[7:]
            return link
        multipart_err = f"HTTP {r1.status_code} multipart: {j1}"
    except requests.RequestException as exc:
        multipart_err = f"multipart request failed: {exc}"

    try:
        data_b64 = base64.b64encode(rb).decode("ascii")
        r2, j2 = _imgur_post_image(
            headers, data={"image": data_b64, "type": "base64"}
        )
        ok2 = bool(j2.get("success")) and isinstance(j2.get("data"), dict) and j2["data"].get("link")
        if ok2:
            link = str(j2["data"]["link"])
            if link.startswith("http://"):
                link = "https://" + link[7:]
            return link
        raise RuntimeError(
            f"Imgur upload failed. multipart: {multipart_err}. fallback_base64 HTTP {r2.status_code}: {j2}"
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Imgur upload failed. multipart: {multipart_err}. base64_fallback: {exc}"
        ) from exc


def graph_create_photo_container(
    media_root: str,
    ig_user_id: str,
    access_token: str,
    image_url: str,
    caption: str,
) -> str:
    r = requests.post(
        f"{media_root}/{ig_user_id}/media",
        params={
            "image_url": image_url[:2048],
            "caption": caption[:2200],
            "access_token": access_token,
        },
        timeout=60,
    )
    payload: dict[str, Any] = r.json()
    if r.status_code >= 400 or "error" in payload:
        raise RuntimeError(f"Create media container failed ({r.status_code}): {payload}")
    cid = payload.get("id")
    if not cid:
        raise RuntimeError(f"No container id in response: {payload}")
    return cid


def graph_wait_container_ready(
    media_root: str,
    container_id: str,
    access_token: str,
    timeout_s: float = 90.0,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = requests.get(
            f"{media_root}/{container_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=30,
        )
        data = r.json()
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Instagram container failed: {data}")
        time.sleep(2.5)
    raise TimeoutError("Timed out waiting for Instagram media container")


def graph_publish_container(
    media_root: str,
    ig_user_id: str,
    container_id: str,
    access_token: str,
) -> str:
    r = requests.post(
        f"{media_root}/{ig_user_id}/media_publish",
        params={"creation_id": container_id, "access_token": access_token},
        timeout=60,
    )
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Publish failed ({r.status_code}): {data}")
    mid = data.get("id")
    if not mid:
        raise RuntimeError(f"No published media id: {data}")
    return mid


def publish_jpeg_feed_post(
    *,
    jpeg_path: Path | None = None,
    caption: str,
    access_token: str,
    instagram_business_id: str,
    imgur_client_id: str | None,
    image_url: str | None = None,
    facebook_page_id: str | None = None,
) -> dict[str, str]:
    """
    Create + publish IG feed post.

    Public ``image_url`` resolution:
      * ``image_url`` / ``INSTAGRAM_SOURCE_IMAGE_URL`` — HTTPS JPEG (you host it).
      * On **Facebook Graph**, try unpublished Page staging first (needs Page token unless skipped).
      * Otherwise ``META_PUBLIC_IMAGE_UPLOAD=auto`` → catbox / 0x0 / file.io / transfer.sh (+ optional Imgur).
    """
    media_root = media_graph_root()
    skip_fb = os.getenv("META_SKIP_FACEBOOK_PAGE_STAGING", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    public_url: str | None

    if image_url:
        public_url = image_url.strip()
    elif jpeg_path is None:
        raise ValueError(
            "Need jpeg_path (local card) unless INSTAGRAM_SOURCE_IMAGE_URL / image_url is set."
        )
    else:
        public_url = None
        if not skip_fb and is_facebook_media_host(media_root):
            page_id = (facebook_page_id or "").strip() or discover_facebook_page_for_instagram(
                access_token, instagram_business_id
            )
            if page_id:
                try:
                    public_url = facebook_unpublished_photo_public_url(page_id, access_token, jpeg_path)
                    logger.info("Public image URL via Facebook Page unpublished upload")
                except Exception as exc:
                    logger.warning("Facebook unpublished Page staging failed; trying anon hosts (%s)", exc)

        if public_url is None:
            public_url = upload_local_jpeg_to_public_https(
                jpeg_path, imgur_client_id=imgur_client_id
            )

    logger.info("Instagram ``image_url`` ready (Media API host=%s)", media_root)
    container = graph_create_photo_container(
        media_root, instagram_business_id, access_token, public_url, caption
    )
    graph_wait_container_ready(media_root, container, access_token)
    pub_id = graph_publish_container(media_root, instagram_business_id, container, access_token)
    return {"container_id": container, "instagram_media_id": pub_id, "image_url_used": public_url}
