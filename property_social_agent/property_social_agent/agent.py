"""Orchestrator: ties together selection, generation, approval, and posting."""

from __future__ import annotations

from .approval import ApprovalRequest, new_token, request_approval
from .config import Config
from .content_generator import GeneratedContent, generate_content
from .copy_reader import read_copy
from .image_host import build_image_host
from .photo_selector import choose_property, select_photos
from .publishers import FacebookPublisher, InstagramPublisher
from .state import State


def enabled_platforms(cfg: Config) -> list[str]:
    platforms = []
    if cfg.instagram_enabled:
        platforms.append("instagram")
    if cfg.facebook_enabled:
        platforms.append("facebook")
    return platforms


def run_once(cfg: Config, state: State, *, dry_run: bool = False) -> None:
    """Execute one full weekly cycle for a single property."""
    platforms = enabled_platforms(cfg)
    if not platforms:
        print("[agent] No platforms enabled in config; nothing to do.")
        return

    property_name = choose_property(cfg, state)
    print(f"[agent] Featuring property: {property_name}")

    photos = select_photos(cfg, state, property_name)
    print(f"[agent] Selected {len(photos)} photo(s): {', '.join(p.name for p in photos)}")

    raw_copy = read_copy(cfg, property_name)

    if dry_run:
        content = _placeholder_content(property_name, raw_copy)
        print("[agent] (dry-run) Skipping Claude content generation.")
    else:
        content = generate_content(cfg, property_name, raw_copy)

    _print_preview(property_name, platforms, content)

    photo_paths = [p.path for p in photos]

    if dry_run:
        print("[agent] (dry-run) Skipping approval email and posting. Done.")
        return

    token = new_token()
    approved = request_approval(
        cfg,
        ApprovalRequest(
            token=token,
            property_name=property_name,
            photos=photo_paths,
            content=content,
            platforms=platforms,
        ),
    )
    if not approved:
        print("[agent] Not approved — nothing was posted.")
        return

    _post(cfg, platforms, photo_paths, content)
    state.record_post(property_name, [p.name for p in photo_paths])
    state.save()
    print("[agent] Posted and recorded. Done.")


def _post(cfg: Config, platforms: list[str], photos, content: GeneratedContent) -> None:
    image_host = build_image_host(cfg)
    for platform in platforms:
        try:
            if platform == "facebook":
                post_id = FacebookPublisher(cfg).publish(photos, content.caption_for("facebook"))
            else:
                post_id = InstagramPublisher(cfg, image_host).publish(
                    photos, content.caption_for("instagram")
                )
            print(f"[agent] Posted to {platform}: {post_id}")
        except Exception as exc:  # noqa: BLE001 - one platform failing shouldn't kill the other
            print(f"[agent] ERROR posting to {platform}: {exc}")


def _placeholder_content(property_name: str, raw_copy: str) -> GeneratedContent:
    snippet = (raw_copy or f"Featured property: {property_name}").strip().splitlines()[0][:200]
    return GeneratedContent(
        summary=f"(dry-run) {snippet}",
        instagram_caption=f"(dry-run IG caption) {snippet}",
        facebook_caption=f"(dry-run FB caption) {snippet}",
        hashtags=["#realestate", "#forsale", "#dryrun"],
    )


def _print_preview(property_name: str, platforms: list[str], content: GeneratedContent) -> None:
    print("\n" + "=" * 60)
    print(f"PREVIEW — {property_name}  ({', '.join(platforms)})")
    print("-" * 60)
    print("Summary:", content.summary)
    print("\n[Instagram]\n" + content.caption_for("instagram"))
    print("\n[Facebook]\n" + content.caption_for("facebook"))
    print("=" * 60 + "\n")
