"""Claude-powered content generation: summarize copy + write social captions.

Uses the Anthropic Python SDK (`anthropic`). Model is configurable; defaults to
claude-opus-4-8. All network calls are skipped automatically in dry-run mode
(handled by the caller) and degrade gracefully if the SDK isn't installed.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config

# Image media types the Claude vision API accepts.
_VISION_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@dataclass
class GeneratedContent:
    summary: str
    instagram_caption: str
    facebook_caption: str
    hashtags: list[str] = field(default_factory=list)

    def caption_for(self, platform: str) -> str:
        base = self.instagram_caption if platform == "instagram" else self.facebook_caption
        tags = " ".join(self.hashtags)
        return f"{base}\n\n{tags}".strip()


def _client(cfg: Config):
    """Construct an Anthropic client, raising a clear error if unconfigured."""
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The 'anthropic' package is required. Run: pip install anthropic") from exc
    if not cfg.secrets.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env).")
    return anthropic.Anthropic(api_key=cfg.secrets.anthropic_api_key)


_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "instagram_caption": {"type": "string"},
        "facebook_caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "instagram_caption", "facebook_caption", "hashtags"],
    "additionalProperties": False,
}


def generate_content(cfg: Config, property_name: str, raw_copy: str) -> GeneratedContent:
    """Summarize the property copy and produce IG + FB captions via Claude."""
    client = _client(cfg)
    content_cfg = cfg.content
    hashtags_cfg = content_cfg.get("hashtags", {})
    n_tags = int(hashtags_cfg.get("count", 10))
    always = hashtags_cfg.get("always_include", [])

    system = (
        "You are a real-estate social media copywriter. You write platform-ready "
        "captions from a property's raw listing copy. Respond ONLY with the requested JSON."
    )
    prompt = f"""Property folder: {property_name}

Brand voice / instructions:
{content_cfg.get('brand_voice', 'Professional and warm.')}

Raw property copy:
\"\"\"
{raw_copy or '(no description provided — write a tasteful generic caption based on the folder name)'}
\"\"\"

Produce:
1. summary: a 1-2 sentence internal summary of the property's standout features.
2. instagram_caption: an Instagram caption in the brand voice. End with this call to action: "{content_cfg.get('call_to_action', '')}"
3. facebook_caption: a slightly longer Facebook caption (Facebook allows more text) in the same voice, with the same call to action.
4. hashtags: exactly {n_tags} relevant hashtags as an array of strings (each starting with #). Always include these: {always}. Do not put hashtags inside the captions; keep them only in this array.
"""

    response = client.messages.create(
        model=cfg.model,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": _CONTENT_SCHEMA}},
    )
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    data = json.loads(text)
    return GeneratedContent(
        summary=data["summary"],
        instagram_caption=data["instagram_caption"],
        facebook_caption=data["facebook_caption"],
        hashtags=data.get("hashtags", []),
    )


def rank_photos_with_vision(cfg: Config, photos: list[Path]) -> list[Path]:
    """Ask Claude to rank a shortlist of photos by social-media appeal.

    Returns the photos reordered best-first. On any failure (unsupported formats,
    API error) returns an empty list so the caller falls back to heuristics.
    """
    usable: list[Path] = []
    blocks: list[dict] = []
    for p in photos:
        media_type, _ = mimetypes.guess_type(p.name)
        if media_type not in _VISION_MEDIA_TYPES:
            continue  # API can't view HEIC etc.; skip from vision ranking
        try:
            data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
        except OSError:
            continue
        idx = len(usable)
        usable.append(p)
        blocks.append({"type": "text", "text": f"Image {idx}: {p.name}"})
        blocks.append(
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
        )

    if len(usable) < 2:
        return []  # nothing meaningful to rank

    blocks.append(
        {
            "type": "text",
            "text": (
                "Rank these property photos from most to least appealing for a real-estate "
                "social media post (favor sharp, well-lit, attractive shots; a strong exterior "
                "or hero shot first). Respond ONLY with JSON matching the schema: an array "
                "'order' of the image indices, best first."
            ),
        }
    )

    schema = {
        "type": "object",
        "properties": {"order": {"type": "array", "items": {"type": "integer"}}},
        "required": ["order"],
        "additionalProperties": False,
    }

    try:
        client = _client(cfg)
        response = client.messages.create(
            model=cfg.model,
            max_tokens=500,
            messages=[{"role": "user", "content": blocks}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next((b.text for b in response.content if b.type == "text"), "{}")
        order = json.loads(text).get("order", [])
    except Exception as exc:  # noqa: BLE001 - vision is best-effort
        print(f"[warn] Vision ranking failed ({exc}); falling back to heuristic scoring.")
        return []

    ranked = [usable[i] for i in order if 0 <= i < len(usable)]
    # Append any usable photos the model omitted, preserving them.
    ranked += [p for p in usable if p not in ranked]
    return ranked
