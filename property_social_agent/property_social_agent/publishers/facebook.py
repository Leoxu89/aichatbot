"""Publish a multi-photo post to a Facebook Page via the Meta Graph API.

Facebook lets us upload photo bytes directly (unpublished), then create a single
feed post that attaches them — so no public image host is needed for Facebook.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Config

GRAPH = "https://graph.facebook.com/v21.0"


class FacebookPublisher:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.token = cfg.secrets.meta_access_token
        self.page_id = cfg.secrets.fb_page_id

    def _check(self) -> None:
        if not self.token or not self.page_id:
            raise RuntimeError("Facebook publishing needs META_ACCESS_TOKEN and FB_PAGE_ID (.env).")

    def publish(self, photos: list[Path], caption: str) -> str:
        """Upload photos and create one Page post. Returns the new post ID."""
        import requests

        self._check()

        # 1. Upload each photo unpublished; collect media IDs.
        media_ids: list[str] = []
        for photo in photos:
            with photo.open("rb") as fh:
                resp = requests.post(
                    f"{GRAPH}/{self.page_id}/photos",
                    data={"published": "false", "access_token": self.token},
                    files={"source": fh},
                    timeout=120,
                )
            resp.raise_for_status()
            media_ids.append(resp.json()["id"])

        # 2. Create the feed post attaching the uploaded media.
        attached = {f"attached_media[{i}]": f'{{"media_fbid":"{mid}"}}' for i, mid in enumerate(media_ids)}
        resp = requests.post(
            f"{GRAPH}/{self.page_id}/feed",
            data={"message": caption, "access_token": self.token, **attached},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["id"]
