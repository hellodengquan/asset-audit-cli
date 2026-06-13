from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from asset_audit_cli.models import Asset, AssetStatus, AnomalyType
from asset_audit_cli.store import AssetStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield AssetStore(data_dir=Path(tmp_dir))


def _make_asset(asset_id, name, category, location, status=AssetStatus.IN_USE, anomaly=None):
    return Asset(
        asset_id=asset_id,
        name=name,
        category=category,
        location=location,
        status=status,
        anomaly=anomaly,
    )


class TestSingleCategoryAllHits:
    def test_单类别全部命中_新增移除变更异常都有(self, store):
        a1 = _make_asset("a001", "笔记本1", "笔记本", "3F", AssetStatus.IN_USE)
        a2 = _make_asset("a002", "笔记本2", "笔记本", "3F", AssetStatus.IDLE)
        a3 = _make_asset("a003", "笔记本3", "笔记本", "3F", AssetStatus.IN_USE)

        store.add_asset(a1)
        store.add_asset(a2)
        store.add_asset(a3)
        snap_old = store.create_snapshot("old")

        store.delete_asset("a003")
        store.add_asset(_make_asset("a004", "笔记本4", "笔记本", "4F", AssetStatus.IN_USE))
        store.update_asset("a002", anomaly=AnomalyType.DAMAGED, anomaly_note="外壳摔裂")

        snap_new = store.create_snapshot("new")

        summaries = store.summarize_diff_by_category(snap_old.snapshot_id, snap_new.snapshot_id)

        assert len(summaries) == 1
        s = summaries[0]
        assert s.category == "笔记本"
        assert s.total_count == 3
        assert s.anomaly_count == 1
        assert s.added_count == 1
        assert s.removed_count == 1
        assert s.changed_count == 1
        assert s.net_change == 0


class TestMultiCategoryMixed:
    def test_跨类别混合差异(self, store):
        n1 = _make_asset("n001", "笔记本1", "笔记本", "3F")
        n2 = _make_asset("n002", "笔记本2", "笔记本", "3F")
        m1 = _make_asset("m001", "显示器1", "显示器", "3F")
        m2 = _make_asset("m002", "显示器2", "显示器", "3F")
        o1 = _make_asset("o001", "投影仪", "办公设备", "5F")

        store.add_asset(n1)
        store.add_asset(n2)
        store.add_asset(m1)
        store.add_asset(m2)
        store.add_asset(o1)
        snap_old = store.create_snapshot("old")

        store.add_asset(_make_asset("n003", "笔记本3", "笔记本", "4F"))
        store.delete_asset("m002")
        store.update_asset("n001", anomaly=AnomalyType.MISSING)
        store.update_asset("m001", location="4F")
        store.add_asset(_make_asset("p001", "打印机", "办公设备", "4F"))
        store.delete_asset("o001")

        snap_new = store.create_snapshot("new")

        summaries = store.summarize_diff_by_category(snap_old.snapshot_id, snap_new.snapshot_id)

        summary_map = {s.category: s for s in summaries}

        assert len(summary_map) == 3

        nb = summary_map["笔记本"]
        assert nb.total_count == 3
        assert nb.anomaly_count == 1
        assert nb.added_count == 1
        assert nb.removed_count == 0
        assert nb.changed_count == 1
        assert nb.net_change == 1

        xs = summary_map["显示器"]
        assert xs.total_count == 1
        assert xs.anomaly_count == 0
        assert xs.added_count == 0
        assert xs.removed_count == 1
        assert xs.changed_count == 1
        assert xs.net_change == -1

        bg = summary_map["办公设备"]
        assert bg.total_count == 1
        assert bg.anomaly_count == 0
        assert bg.added_count == 1
        assert bg.removed_count == 1
        assert bg.changed_count == 0
        assert bg.net_change == 0


class TestEmptyDiff:
    def test_空差异返回0(self, store):
        a1 = _make_asset("a001", "笔记本1", "笔记本", "3F")
        a2 = _make_asset("a002", "显示器1", "显示器", "3F")

        store.add_asset(a1)
        store.add_asset(a2)
        snap_old = store.create_snapshot("old")
        snap_new = store.create_snapshot("new")

        summaries = store.summarize_diff_by_category(snap_old.snapshot_id, snap_new.snapshot_id)

        summary_map = {s.category: s for s in summaries}
        assert len(summary_map) == 2

        nb = summary_map["笔记本"]
        assert nb.total_count == 1
        assert nb.anomaly_count == 0
        assert nb.added_count == 0
        assert nb.removed_count == 0
        assert nb.changed_count == 0
        assert nb.net_change == 0

        xs = summary_map["显示器"]
        assert xs.total_count == 1
        assert xs.anomaly_count == 0
        assert xs.added_count == 0
        assert xs.removed_count == 0
        assert xs.changed_count == 0
        assert xs.net_change == 0
