"""Configuration loading: merges config.yaml (settings) with .env (secrets)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class Secrets:
    """Secret values sourced from the environment / .env file."""

    anthropic_api_key: str = ""
    meta_access_token: str = ""
    ig_business_account_id: str = ""
    fb_page_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_endpoint_url: str = ""

    @classmethod
    def from_env(cls) -> "Secrets":
        load_dotenv()  # loads .env from cwd if present; no-op otherwise

        def _int(name: str, default: int) -> int:
            raw = os.getenv(name)
            return int(raw) if raw else default

        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            meta_access_token=os.getenv("META_ACCESS_TOKEN", ""),
            ig_business_account_id=os.getenv("IG_BUSINESS_ACCOUNT_ID", ""),
            fb_page_id=os.getenv("FB_PAGE_ID", ""),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=_int("SMTP_PORT", 587),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            imap_host=os.getenv("IMAP_HOST", ""),
            imap_port=_int("IMAP_PORT", 993),
            imap_username=os.getenv("IMAP_USERNAME", ""),
            imap_password=os.getenv("IMAP_PASSWORD", ""),
            s3_bucket=os.getenv("S3_BUCKET", ""),
            s3_region=os.getenv("S3_REGION", "us-east-1"),
            s3_access_key_id=os.getenv("S3_ACCESS_KEY_ID", ""),
            s3_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", ""),
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL", ""),
        )


@dataclass
class Config:
    """Top-level configuration, parsed from config.yaml plus secrets."""

    photos_root: Path
    property_selection: str
    photos_per_post: int
    photo_extensions: list[str]
    copy_filenames: list[str]
    selection: dict[str, Any]
    content: dict[str, Any]
    platforms: dict[str, bool]
    image_host: dict[str, Any]
    approval: dict[str, Any]
    schedule: dict[str, Any]
    secrets: Secrets = field(default_factory=Secrets)

    @classmethod
    def load(cls, config_path: str | Path = "config.yaml") -> "Config":
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Config file not found: {path}. Copy config.example.yaml to config.yaml."
            )
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        return cls(
            photos_root=Path(os.path.expanduser(raw["photos_root"])),
            property_selection=raw.get("property_selection", "rotate"),
            photos_per_post=int(raw.get("photos_per_post", 4)),
            photo_extensions=[e.lower() for e in raw.get("photo_extensions", [".jpg", ".jpeg", ".png"])],
            copy_filenames=raw.get("copy_filenames", ["description.md", "description.txt"]),
            selection=raw.get("selection", {"mode": "heuristic", "reuse_after_days": 90}),
            content=raw.get("content", {}),
            platforms=raw.get("platforms", {"instagram": True, "facebook": True}),
            image_host=raw.get("image_host", {"type": "none"}),
            approval=raw.get("approval", {}),
            schedule=raw.get("schedule", {}),
            secrets=Secrets.from_env(),
        )

    # --- convenience accessors -------------------------------------------------
    @property
    def model(self) -> str:
        return self.content.get("model", "claude-opus-4-8")

    @property
    def instagram_enabled(self) -> bool:
        return bool(self.platforms.get("instagram"))

    @property
    def facebook_enabled(self) -> bool:
        return bool(self.platforms.get("facebook"))
