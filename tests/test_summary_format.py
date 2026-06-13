from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from asset_audit_cli.main import app
from asset_audit_cli.models import Asset, AssetStatus, AnomalyType
from asset_audit_cli.store import AssetStore

runner = CliRunner()


def _make_asset(asset_id, name, category, location, status=AssetStatus.IN_USE, anomaly=None):
    return Asset(
        asset_id=asset_id,
        name=name,
        category=category,
        location=location,
        status=status,
        anomaly=anomaly,
    )


@pytest.fixture
def tmp_store():
    with tempfile.TemporaryDirectory() as tmp_dir:
        data_dir = Path(tmp_dir) / "audit"
        store = AssetStore(data_dir=data_dir)
        with patch("asset_audit_cli.main.store", store):
            yield store


class TestSummaryFormatTextDefault:
    def test_默认text格式_与现有逻辑一致(self, tmp_store):
        s = tmp_store
        s.add_asset(_make_asset("a001", "笔记本1", "笔记本", "3F"))
        s.add_asset(_make_asset("a002", "显示器1", "显示器", "3F"))
        snap_old = s.create_snapshot("old")

        s.add_asset(_make_asset("a003", "笔记本2", "笔记本", "4F"))
        s.update_asset("a002", anomaly=AnomalyType.MISSING)
        snap_new = s.create_snapshot("new")

        result = runner.invoke(app, ["summary", snap_old.snapshot_id, snap_new.snapshot_id, "-g", "category"])

        assert result.exit_code == 0, result.output
        assert "笔记本" in result.output
        assert "显示器" in result.output
        assert "资产数" in result.output
        assert "异常数" in result.output
        assert "净增减" in result.output
        assert "合计" in result.output
        assert "{" not in result.output.strip().splitlines()[-1]


class TestSummaryFormatJson:
    def test_json格式合法且字段完整(self, tmp_store):
        s = tmp_store
        s.add_asset(_make_asset("a001", "笔记本1", "笔记本", "3F"))
        s.add_asset(_make_asset("a002", "笔记本2", "笔记本", "3F"))
        s.add_asset(_make_asset("a003", "显示器1", "显示器", "3F"))
        snap_old = s.create_snapshot("old")

        s.add_asset(_make_asset("a004", "笔记本3", "笔记本", "4F"))
        s.delete_asset("a003")
        s.update_asset("a002", anomaly=AnomalyType.DAMAGED)
        snap_new = s.create_snapshot("new")

        result = runner.invoke(
            app,
            ["summary", snap_old.snapshot_id, snap_new.snapshot_id, "-g", "category", "-f", "json"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)

        assert "categories" in payload
        assert isinstance(payload["categories"], list)

        by_name = {c["name"]: c for c in payload["categories"]}
        assert set(by_name.keys()) == {"笔记本", "显示器"}

        nb = by_name["笔记本"]
        assert set(nb.keys()) == {"name", "total", "anomalies", "net_delta"}
        assert nb["name"] == "笔记本"
        assert nb["total"] == 3
        assert nb["anomalies"] == 1
        assert nb["net_delta"] == 1

        xs = by_name["显示器"]
        assert xs["name"] == "显示器"
        assert xs["total"] == 0
        assert xs["anomalies"] == 0
        assert xs["net_delta"] == -1

    def test_json模式无差异返回空数组(self, tmp_store):
        s = tmp_store
        s.add_asset(_make_asset("a001", "笔记本1", "笔记本", "3F"))
        snap_old = s.create_snapshot("old")
        snap_new = s.create_snapshot("new")

        result = runner.invoke(
            app,
            ["summary", snap_old.snapshot_id, snap_new.snapshot_id, "-g", "category", "-f", "json"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)

        assert "categories" in payload
        assert isinstance(payload["categories"], list)
        assert len(payload["categories"]) == 1

        nb = payload["categories"][0]
        assert nb["name"] == "笔记本"
        assert nb["total"] == 1
        assert nb["anomalies"] == 0
        assert nb["net_delta"] == 0

    def test_json模式无资产_返回空categories(self, tmp_store):
        s = tmp_store
        snap_old = s.create_snapshot("old")
        snap_new = s.create_snapshot("new")

        result = runner.invoke(
            app,
            ["summary", snap_old.snapshot_id, snap_new.snapshot_id, "-g", "category", "-f", "json"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload == {"categories": []}
