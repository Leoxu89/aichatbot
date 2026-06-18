"""Scan a property folder and select the best photos for this week's post."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Config
from .state import State


@dataclass
class Photo:
    path: Path
    score: float = 0.0

    @property
    def name(self) -> str:
        return self.path.name


def find_properties(cfg: Config) -> list[str]:
    """Return the names of property subfolders under photos_root."""
    if not cfg.photos_root.exists():
        raise FileNotFoundError(f"photos_root does not exist: {cfg.photos_root}")
    return sorted(
        p.name for p in cfg.photos_root.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def choose_property(cfg: Config, state: State) -> str:
    """Pick which property to feature based on config + rotation state."""
    properties = find_properties(cfg)
    if not properties:
        raise RuntimeError(f"No property subfolders found under {cfg.photos_root}")

    if cfg.property_selection != "rotate":
        if cfg.property_selection not in properties:
            raise RuntimeError(
                f"Configured property '{cfg.property_selection}' not found under {cfg.photos_root}"
            )
        return cfg.property_selection

    # Rotate: pick the property posted least recently (never-posted first).
    def sort_key(name: str):
        last = state.last_posted_at(name)
        return (last is not None, last or "")

    return sorted(properties, key=sort_key)[0]


def _photo_files(cfg: Config, property_name: str) -> list[Path]:
    folder = cfg.photos_root / property_name
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in cfg.photo_extensions
    )


def _heuristic_score(path: Path) -> float:
    """Score a photo by resolution and sharpness. Higher is better.

    Falls back to 0 if Pillow can't open the file (e.g. unsupported HEIC without
    the right plugin) so it simply ranks last rather than crashing the run.
    """
    try:
        from PIL import Image, ImageFilter, ImageStat
    except ImportError:  # Pillow not installed (e.g. dry-run minimal env)
        return float(path.stat().st_size)  # crude proxy: bigger file ~ higher quality

    try:
        with Image.open(path) as im:
            im = im.convert("L")
            width, height = im.size
            megapixels = (width * height) / 1_000_000
            # Sharpness proxy: variance after an edge filter.
            edges = im.filter(ImageFilter.FIND_EDGES)
            sharpness = ImageStat.Stat(edges).var[0]
            # Landscape-ish images tend to look better in feeds.
            aspect = width / height if height else 1.0
            aspect_bonus = 1.0 if 1.0 <= aspect <= 1.91 else 0.7
            return (megapixels * 10 + sharpness / 100) * aspect_bonus
    except Exception:
        return 0.0


def select_photos(cfg: Config, state: State, property_name: str) -> list[Photo]:
    """Return the top N photos for the property, skipping recently-used ones."""
    files = _photo_files(cfg, property_name)
    if not files:
        raise RuntimeError(f"No photos found in {cfg.photos_root / property_name}")

    reuse_after = int(cfg.selection.get("reuse_after_days", 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=reuse_after)

    fresh: list[Path] = []
    for f in files:
        last = state.photo_last_posted(property_name, f.name)
        if last:
            try:
                if datetime.fromisoformat(last) > cutoff:
                    continue  # used too recently
            except ValueError:
                pass
        fresh.append(f)

    # If everything was recently used, fall back to the full set.
    candidates = fresh or files
    photos = [Photo(path=f, score=_heuristic_score(f)) for f in candidates]
    photos.sort(key=lambda p: p.score, reverse=True)

    n = cfg.photos_per_post
    if cfg.selection.get("mode") == "vision" and cfg.secrets.anthropic_api_key:
        # Keep a generous shortlist for the vision model to refine.
        shortlist = photos[: max(n * 2, n + 2)]
        from .content_generator import rank_photos_with_vision

        ordered = rank_photos_with_vision(cfg, [p.path for p in shortlist])
        if ordered:
            return [Photo(path=p) for p in ordered[:n]]

    return photos[:n]
