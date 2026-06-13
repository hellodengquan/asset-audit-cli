from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from .models import Asset, DiffResult, Snapshot

DEFAULT_DATA_DIR = Path.home() / ".asset-audit"
ASSETS_FILE = "assets.json"
SNAPSHOTS_FILE = "snapshots.json"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: list[dict]) -> None:
    _ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class AssetStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.assets_path = self.data_dir / ASSETS_FILE
        self.snapshots_path = self.data_dir / SNAPSHOTS_FILE

    def load_assets(self) -> list[Asset]:
        raw = _read_json(self.assets_path)
        return [Asset.from_dict(d) for d in raw]

    def save_assets(self, assets: list[Asset]) -> None:
        _write_json(self.assets_path, [a.to_dict() for a in assets])

    def add_asset(self, asset: Asset) -> Asset:
        assets = self.load_assets()
        assets.append(asset)
        self.save_assets(assets)
        return asset

    def find_asset(self, asset_id: str) -> Asset | None:
        for a in self.load_assets():
            if a.asset_id == asset_id:
                return a
        return None

    def update_asset(self, asset_id: str, **kwargs) -> Asset | None:
        assets = self.load_assets()
        target: Asset | None = None
        for a in assets:
            if a.asset_id == asset_id:
                target = a
                break
        if target is None:
            return None
        for k, v in kwargs.items():
            if v is not None and hasattr(target, k):
                setattr(target, k, v)
        target.updated_at = datetime.now().isoformat()
        self.save_assets(assets)
        return target

    def delete_asset(self, asset_id: str) -> bool:
        assets = self.load_assets()
        filtered = [a for a in assets if a.asset_id != asset_id]
        if len(filtered) == len(assets):
            return False
        self.save_assets(filtered)
        return True

    def load_snapshots(self) -> list[Snapshot]:
        raw = _read_json(self.snapshots_path)
        return [Snapshot.from_dict(d) for d in raw]

    def save_snapshots(self, snapshots: list[Snapshot]) -> None:
        _write_json(self.snapshots_path, [s.to_dict() for s in snapshots])

    def create_snapshot(self, label: str) -> Snapshot:
        assets = self.load_assets()
        snapshot = Snapshot(
            snapshot_id=uuid.uuid4().hex[:8],
            label=label,
            assets=[a.to_dict() for a in assets],
        )
        snapshots = self.load_snapshots()
        snapshots.append(snapshot)
        self.save_snapshots(snapshots)
        return snapshot

    def find_snapshot(self, snapshot_id: str) -> Snapshot | None:
        for s in self.load_snapshots():
            if s.snapshot_id == snapshot_id:
                return s
        return None

    def diff_snapshots(self, old_id: str, new_id: str) -> DiffResult:
        old_snap = self.find_snapshot(old_id)
        new_snap = self.find_snapshot(new_id)
        if old_snap is None or new_snap is None:
            raise ValueError("快照不存在")

        old_map = {a["asset_id"]: a for a in old_snap.assets}
        new_map = {a["asset_id"]: a for a in new_snap.assets}

        added = [new_map[k] for k in new_map if k not in old_map]
        removed = [old_map[k] for k in old_map if k not in new_map]

        changed: list[dict] = []
        for k in old_map:
            if k in new_map and old_map[k] != new_map[k]:
                changed.append({"asset_id": k, "before": old_map[k], "after": new_map[k]})

        return DiffResult(added=added, removed=removed, changed=changed)
