"""Persistent run state: which photos/properties were posted and when.

Stored as a small JSON file so the agent can avoid reusing photos, rotate
between properties, and remember pending approvals across restarts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class State:
    path: Path
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path = "agent_state.json") -> "State":
        p = Path(path)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            data = {"properties": {}, "last_run": None}
        return cls(path=p, data=data)

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    # --- property rotation -----------------------------------------------------
    def last_posted_at(self, property_name: str) -> str | None:
        return self.data["properties"].get(property_name, {}).get("last_posted_at")

    def record_post(self, property_name: str, photo_names: list[str]) -> None:
        prop = self.data["properties"].setdefault(
            property_name, {"posted_photos": {}, "last_posted_at": None}
        )
        ts = _now_iso()
        prop["last_posted_at"] = ts
        for name in photo_names:
            prop["posted_photos"][name] = ts
        self.data["last_run"] = ts

    def photo_last_posted(self, property_name: str, photo_name: str) -> str | None:
        prop = self.data["properties"].get(property_name, {})
        return prop.get("posted_photos", {}).get(photo_name)
