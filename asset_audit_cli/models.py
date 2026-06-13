from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AssetStatus(str, Enum):
    IN_USE = "in_use"
    IDLE = "idle"
    REPAIR = "repair"
    RETIRED = "retired"


class AnomalyType(str, Enum):
    MISSING = "missing"
    DAMAGED = "damaged"
    MISPLACED = "misplaced"
    MISMATCH = "mismatch"
    OTHER = "other"


@dataclass
class Asset:
    asset_id: str
    name: str
    category: str
    location: str
    status: AssetStatus = AssetStatus.IN_USE
    anomaly: AnomalyType | None = None
    anomaly_note: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:8]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "asset_id": self.asset_id,
            "name": self.name,
            "category": self.category,
            "location": self.location,
            "status": self.status.value,
            "anomaly": self.anomaly.value if self.anomaly else None,
            "anomaly_note": self.anomaly_note,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Asset:
        return cls(
            asset_id=d["asset_id"],
            name=d["name"],
            category=d["category"],
            location=d["location"],
            status=AssetStatus(d["status"]),
            anomaly=AnomalyType(d["anomaly"]) if d.get("anomaly") else None,
            anomaly_note=d.get("anomaly_note", ""),
            tags=d.get("tags", []),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


@dataclass
class Snapshot:
    snapshot_id: str
    label: str
    assets: list[dict[str, Any]]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "label": self.label,
            "assets": self.assets,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Snapshot:
        return cls(
            snapshot_id=d["snapshot_id"],
            label=d["label"],
            assets=d["assets"],
            created_at=d.get("created_at", ""),
        )


@dataclass
class DiffResult:
    added: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    changed: list[dict[str, Any]]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
        }
