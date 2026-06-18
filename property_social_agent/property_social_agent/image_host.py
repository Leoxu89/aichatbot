"""Make local photos available at public URLs (required for Instagram).

Instagram's Graph API fetches images from a public URL — you cannot upload raw
bytes for an IG post. This module provides pluggable hosts:

- S3Host:        uploads selected photos to an S3-compatible bucket.
- BaseUrlHost:   you already serve photos_root publicly; just map paths to a URL.
- NoOpHost:      returns local file:// URLs (Instagram will be skipped).
"""

from __future__ import annotations

from pathlib import Path

from .config import Config


def build_image_host(cfg: Config):
    host_type = cfg.image_host.get("type", "none")
    if host_type == "s3":
        return S3Host(cfg)
    if host_type == "base_url":
        return BaseUrlHost(cfg)
    return NoOpHost(cfg)


class NoOpHost:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def public_url(self, path: Path) -> str:
        return path.as_uri()

    @property
    def usable_for_instagram(self) -> bool:
        return False


class BaseUrlHost:
    """Maps a local path under photos_root to a configured public base URL."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.base_url = cfg.image_host.get("base_url", "").rstrip("/")
        if not self.base_url:
            raise RuntimeError("image_host.type=base_url requires image_host.base_url in config.yaml")

    def public_url(self, path: Path) -> str:
        rel = path.relative_to(self.cfg.photos_root)
        return f"{self.base_url}/{rel.as_posix()}"

    @property
    def usable_for_instagram(self) -> bool:
        return True


class S3Host:
    """Uploads photos to an S3-compatible bucket and returns their public URLs."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        s = cfg.secrets
        if not s.s3_bucket:
            raise RuntimeError("image_host.type=s3 requires S3_BUCKET and credentials in .env")
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("The 'boto3' package is required for the S3 image host.") from exc
        self._bucket = s.s3_bucket
        self._endpoint = s.s3_endpoint_url or None
        self._client = boto3.client(
            "s3",
            region_name=s.s3_region,
            aws_access_key_id=s.s3_access_key_id or None,
            aws_secret_access_key=s.s3_secret_access_key or None,
            endpoint_url=self._endpoint,
        )

    def public_url(self, path: Path) -> str:
        import mimetypes

        key = f"property-social-agent/{path.name}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._client.upload_file(
            str(path), self._bucket, key,
            ExtraArgs={"ContentType": content_type},
        )
        if self._endpoint:
            return f"{self._endpoint.rstrip('/')}/{self._bucket}/{key}"
        return f"https://{self._bucket}.s3.{self.cfg.secrets.s3_region}.amazonaws.com/{key}"

    @property
    def usable_for_instagram(self) -> bool:
        return True
