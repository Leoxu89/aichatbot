"""Publish to Instagram via the Meta Graph API.

Instagram requires images to be fetched from PUBLIC URLs (see image_host.py).
Flow: create a media container per image -> (for >1) a carousel container ->
publish. A single image publishes its container directly.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Config

GRAPH = "https://graph.facebook.com/v21.0"


class InstagramPublisher:
    def __init__(self, cfg: Config, image_host):
        self.cfg = cfg
        self.image_host = image_host
        self.token = cfg.secrets.meta_access_token
        self.ig_id = cfg.secrets.ig_business_account_id

    def _check(self) -> None:
        if not self.token or not self.ig_id:
            raise RuntimeError(
                "Instagram publishing needs META_ACCESS_TOKEN and IG_BUSINESS_ACCOUNT_ID (.env)."
            )
        if not getattr(self.image_host, "usable_for_instagram", False):
            raise RuntimeError(
                "Instagram requires a public image host. Set image_host.type to 's3' or 'base_url'."
            )

    def publish(self, photos: list[Path], caption: str) -> str:
        import requests

        self._check()
        urls = [self.image_host.public_url(p) for p in photos]

        if len(urls) == 1:
            container_id = self._create_container(requests, image_url=urls[0], caption=caption)
            return self._publish_container(requests, container_id)

        # Carousel: child containers first, then a parent carousel container.
        children: list[str] = []
        for url in urls:
            children.append(self._create_container(requests, image_url=url, is_carousel_item=True))
        parent = self._create_carousel(requests, children, caption)
        return self._publish_container(requests, parent)

    # --- helpers --------------------------------------------------------------
    def _create_container(self, requests, image_url: str, caption: str = "", is_carousel_item: bool = False) -> str:
        data = {"image_url": image_url, "access_token": self.token}
        if is_carousel_item:
            data["is_carousel_item"] = "true"
        else:
            data["caption"] = caption
        resp = requests.post(f"{GRAPH}/{self.ig_id}/media", data=data, timeout=120)
        resp.raise_for_status()
        return resp.json()["id"]

    def _create_carousel(self, requests, children: list[str], caption: str) -> str:
        resp = requests.post(
            f"{GRAPH}/{self.ig_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": caption,
                "access_token": self.token,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _publish_container(self, requests, container_id: str) -> str:
        resp = requests.post(
            f"{GRAPH}/{self.ig_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.token},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["id"]
