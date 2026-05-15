"""
Publish feed photos using Instagram Graph API (Meta).

Requirements (Meta):
- Instagram Professional (Business or Creator) account
- Linked Facebook Page
- App in Meta Developer with instagram_content_publish, pages_show_list, etc.
- Long-lived Page access token

We do NOT support password-based automation (unsupported and unsafe).

Publishing needs a PUBLICLY REACHABLE HTTPS image URL for the photo step:
set IMGUR_CLIENT_ID for anonymous upload, or host the JPEG yourself (S3/CDN/ngrok).

Env:
  META_ACCESS_TOKEN
  INSTAGRAM_BUSINESS_ID   (Instagram user id from Graph)
  IMGUR_CLIENT_ID         (optional, for uploading local JPEG)
"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

GRAPH_VER = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VER}"


def imgur_upload_jpeg(path: Path, client_id: str) -> str:
    data_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    r = requests.post(
        "https://api.imgur.com/3/image",
        headers={"Authorization": f"Client-ID {client_id}"},
        data={"image": data_b64, "type": "base64"},
        timeout=120,
    )
    r.raise_for_status()
    j = r.json()
    if not j.get("success"):
        raise RuntimeError(f"Imgur rejected upload: {j}")
    link = j["data"]["link"]
    if link.startswith("http://"):
        link = "https://" + link[7:]
    return link


def graph_create_photo_container(
    ig_user_id: str,
    access_token: str,
    image_url: str,
    caption: str,
) -> str:
    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media",
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


def graph_wait_container_ready(container_id: str, access_token: str, timeout_s: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = requests.get(
            f"{GRAPH}/{container_id}",
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


def graph_publish_container(ig_user_id: str, container_id: str, access_token: str) -> str:
    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media_publish",
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
) -> dict[str, str]:
    """
    Create + publish IG feed post.
    Provide either ``image_url`` (public HTTPS JPEG/PNG) or ``jpeg_path`` + Imgur Client-ID.
    """
    if image_url:
        public_url = image_url.strip()
    elif jpeg_path is not None and imgur_client_id:
        public_url = imgur_upload_jpeg(jpeg_path, imgur_client_id)
    else:
        raise ValueError(
            "Need a public HTTPS image_url or (jpeg_path + IMGUR_CLIENT_ID). "
            "Instagram Graph does not upload raw files from disk."
        )

    logger.info("Created public image URL for Instagram container step")
    container = graph_create_photo_container(
        instagram_business_id, access_token, public_url, caption
    )
    graph_wait_container_ready(container, access_token)
    pub_id = graph_publish_container(instagram_business_id, container, access_token)
    return {"container_id": container, "instagram_media_id": pub_id, "image_url_used": public_url}
