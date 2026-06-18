"""Zero-setup demo: generates sample photos + copy, shows the web approval
dashboard, and simulates posting. Needs no API keys, accounts, or real folders.

Run with:  python -m property_social_agent demo
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .approval import ApprovalRequest
from .content_generator import GeneratedContent

_SAMPLE_COPY = """# Seaside Cottage — 12 Harbour Lane

Light-filled 3-bedroom cottage steps from the water. Renovated kitchen with
quartz counters, original hardwood floors, a wood-burning fireplace, and a
west-facing deck made for sunsets. Two-car garage and a fenced garden.
"""

# (filename, RGB fill, label drawn on the image)
_SAMPLE_PHOTOS = [
    ("01-exterior.jpg", (70, 110, 150), "Exterior"),
    ("02-kitchen.jpg", (180, 150, 110), "Kitchen"),
    ("03-living.jpg", (150, 120, 130), "Living room"),
    ("04-deck.jpg", (110, 150, 130), "Deck at sunset"),
]

_DEMO_CONTENT = GeneratedContent(
    summary="Renovated 3-bed seaside cottage with quartz kitchen, hardwood floors, fireplace, and a sunset deck.",
    instagram_caption=(
        "Coastal living, reimagined. This light-filled 3-bedroom cottage sits steps "
        "from the water, with a renovated quartz kitchen, original hardwood floors, "
        "and a west-facing deck built for sunsets.\n\n"
        "DM us or visit the link in bio to book a private showing."
    ),
    facebook_caption=(
        "Just listed — Seaside Cottage at 12 Harbour Lane. A light-filled 3-bedroom "
        "home steps from the water: renovated kitchen with quartz counters, original "
        "hardwood floors, a wood-burning fireplace, and a west-facing deck made for "
        "sunsets. Two-car garage and a fenced garden round it out.\n\n"
        "DM us or visit the link in bio to book a private showing."
    ),
    hashtags=[
        "#realestate", "#forsale", "#seasidecottage", "#coastalliving",
        "#justlisted", "#homeforsale", "#dreamhome", "#oceanview",
        "#realtor", "#openhouse", "#propertyforsale", "#waterfront",
    ],
)


def _make_sample_photos(folder: Path) -> list[Path]:
    from PIL import Image, ImageDraw

    paths: list[Path] = []
    for name, color, label in _SAMPLE_PHOTOS:
        img = Image.new("RGB", (1200, 800), color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([30, 30, 1170, 770], outline=(255, 255, 255), width=4)
        draw.text((60, 60), f"Seaside Cottage\n{label}", fill=(255, 255, 255))
        path = folder / name
        img.save(path, "JPEG", quality=85)
        paths.append(path)
    return paths


def run_demo(port: int = 8000, open_browser: bool = True) -> bool:
    """Run the full preview + web-approval flow on sample data. Returns approved?"""
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("The demo needs Pillow. Run: pip install -r requirements.txt")
        return False

    tmp = Path(tempfile.mkdtemp(prefix="psa-demo-"))
    prop = tmp / "seaside-cottage"
    prop.mkdir(parents=True)
    (prop / "description.md").write_text(_SAMPLE_COPY, encoding="utf-8")
    photos = _make_sample_photos(prop)

    print("[demo] Generated a sample property (no real folders or accounts used).")
    print(f"[demo] Sample files are in: {prop}")

    from .webapp import run_web_approval

    req = ApprovalRequest(
        token="demo",
        property_name="seaside-cottage",
        photos=photos,
        content=_DEMO_CONTENT,
        platforms=["instagram", "facebook"],
    )
    decision = run_web_approval(req, port=port, open_browser=open_browser)

    if decision.approved:
        print("\n[demo] APPROVED ✓  In a real run this would now post to Instagram + Facebook.")
        print("\n--- Final Instagram caption ---")
        print(decision.content.caption_for("instagram"))
    else:
        print("\n[demo] Rejected — nothing would be posted.")
    return decision.approved
