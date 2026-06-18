"""Read the property's 'copy'/description file from its folder."""

from __future__ import annotations

from pathlib import Path

from .config import Config


def read_copy(cfg: Config, property_name: str) -> str:
    """Return the raw text of the property's description file.

    Looks for the first matching filename from cfg.copy_filenames in the
    property folder. Supports .txt/.md directly and .pdf via pypdf.
    Returns an empty string (with a warning printed) if none is found.
    """
    folder = cfg.photos_root / property_name
    for name in cfg.copy_filenames:
        candidate = folder / name
        if candidate.exists():
            return _read_file(candidate)

    print(f"[warn] No copy file found in {folder}. Looked for: {cfg.copy_filenames}")
    return ""


def _read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"[warn] pypdf not installed; cannot read {path.name}. Run: pip install pypdf")
        return ""
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
