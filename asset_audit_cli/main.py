from __future__ import annotations

from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .models import AnomalyType, Asset, AssetStatus
from .store import AssetStore

app = typer.Typer(help="小型资产盘点 CLI 工具")
console = Console()
store = AssetStore()


class GroupBy(str, Enum):
    CATEGORY = "category"


def _status_style(status: str) -> str:
    colors = {
        "in_use": "green",
        "idle": "yellow",
        "repair": "red",
        "retired": "dim",
    }
    return f"[{colors.get(status, 'white')}]{status}[/]"


def _anomaly_style(atype: str | None) -> str:
    if atype is None:
        return "[dim]-[/]"
    colors = {
        "missing": "bold red",
        "damaged": "red",
        "misplaced": "yellow",
        "mismatch": "magenta",
        "other": "cyan",
    }
    return f"[{colors.get(atype, 'white')}]{atype}[/]"


@app.command()
def register(
    name: str = typer.Option(..., "--name", "-n", help="资产名称"),
    category: str = typer.Option(..., "--category", "-c", help="资产类别"),
    location: str = typer.Option(..., "--location", "-l", help="存放位置"),
    status: AssetStatus = typer.Option(AssetStatus.IN_USE, "--status", "-s", help="资产状态"),
    tags: Optional[list[str]] = typer.Option(None, "--tag", "-t", help="标签（可多次指定）"),
):
    asset = Asset(
        asset_id=Asset.new_id(),
        name=name,
        category=category,
        location=location,
        status=status,
        tags=tags or [],
    )
    store.add_asset(asset)
    console.print(f"[green]✔ 资产已登记[/] ID: [bold]{asset.asset_id}[/]")


@app.command(name="list")
def list_assets(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="按类别筛选"),
    status: Optional[AssetStatus] = typer.Option(None, "--status", "-s", help="按状态筛选"),
    anomaly_only: bool = typer.Option(False, "--anomaly-only", "-a", help="仅显示异常资产"),
):
    assets = store.load_assets()
    if category:
        assets = [a for a in assets if a.category == category]
    if status:
        assets = [a for a in assets if a.status == status]
    if anomaly_only:
        assets = [a for a in assets if a.anomaly is not None]

    if not assets:
        console.print("[dim]暂无资产记录[/]")
        return

    table = Table(title="资产清单", show_lines=True)
    table.add_column("ID", style="bold")
    table.add_column("名称")
    table.add_column("类别")
    table.add_column("位置")
    table.add_column("状态")
    table.add_column("异常")
    table.add_column("标签")

    for a in assets:
        table.add_row(
            a.asset_id,
            a.name,
            a.category,
            a.location,
            _status_style(a.status.value),
            _anomaly_style(a.anomaly.value if a.anomaly else None),
            ", ".join(a.tags) if a.tags else "-",
        )
    console.print(table)


@app.command()
def mark(
    asset_id: str = typer.Argument(..., help="资产 ID"),
    anomaly: AnomalyType = typer.Option(..., "--type", help="异常类型"),
    note: str = typer.Option("", "--note", help="异常备注"),
):
    result = store.update_asset(asset_id, anomaly=anomaly, anomaly_note=note)
    if result is None:
        console.print(f"[red]✘ 未找到资产 {asset_id}[/]")
        raise typer.Exit(code=1)
    console.print(f"[yellow]⚠ 资产 {asset_id} 已标记异常: {anomaly.value}[/]")


@app.command()
def unmark(
    asset_id: str = typer.Argument(..., help="资产 ID"),
):
    result = store.update_asset(asset_id, anomaly=None, anomaly_note="")
    if result is None:
        console.print(f"[red]✘ 未找到资产 {asset_id}[/]")
        raise typer.Exit(code=1)
    console.print(f"[green]✔ 资产 {asset_id} 异常标记已清除[/]")


@app.command()
def snapshot(
    label: str = typer.Option(..., "--label", "-l", help="快照标签"),
):
    snap = store.create_snapshot(label)
    console.print(f"[green]✔ 快照已创建[/] ID: [bold]{snap.snapshot_id}[/]  标签: {label}")


@app.command(name="snapshots")
def list_snapshots():
    snapshots = store.load_snapshots()
    if not snapshots:
        console.print("[dim]暂无快照[/]")
        return

    table = Table(title="快照列表")
    table.add_column("快照ID", style="bold")
    table.add_column("标签")
    table.add_column("资产数")
    table.add_column("创建时间")
    for s in snapshots:
        table.add_row(s.snapshot_id, s.label, str(len(s.assets)), s.created_at)
    console.print(table)


@app.command()
def diff(
    old_id: str = typer.Argument(..., help="旧快照 ID"),
    new_id: str = typer.Argument(..., help="新快照 ID"),
):
    try:
        result = store.diff_snapshots(old_id, new_id)
    except ValueError as e:
        console.print(f"[red]✘ {e}[/]")
        raise typer.Exit(code=1)

    if not result.has_changes:
        console.print("[green]两个快照无差异[/]")
        return

    if result.added:
        table = Table(title=f"新增资产 ({len(result.added)})", show_lines=True)
        table.add_column("ID", style="bold")
        table.add_column("名称")
        table.add_column("类别")
        table.add_column("位置")
        for a in result.added:
            table.add_row(a["asset_id"], a["name"], a["category"], a["location"])
        console.print(table)

    if result.removed:
        table = Table(title=f"移除资产 ({len(result.removed)})", show_lines=True)
        table.add_column("ID", style="bold")
        table.add_column("名称")
        table.add_column("类别")
        table.add_column("位置")
        for a in result.removed:
            table.add_row(a["asset_id"], a["name"], a["category"], a["location"])
        console.print(table)

    if result.changed:
        table = Table(title=f"变更资产 ({len(result.changed)})", show_lines=True)
        table.add_column("ID", style="bold")
        table.add_column("字段")
        table.add_column("旧值")
        table.add_column("新值")
        for c in result.changed:
            before = c["before"]
            after = c["after"]
            all_keys = set(before.keys()) | set(after.keys())
            for k in sorted(all_keys):
                if k in ("created_at", "updated_at"):
                    continue
                bv = before.get(k)
                av = after.get(k)
                if bv != av:
                    table.add_row(c["asset_id"], k, str(bv), str(av))
        console.print(table)

    console.print(
        f"\n[bold]差异摘要[/]: "
        f"[green]+{len(result.added)}[/]  "
        f"[red]-{len(result.removed)}[/]  "
        f"[yellow]~{len(result.changed)}[/]"
    )


@app.command()
def summary(
    old_id: str = typer.Argument(..., help="旧快照 ID"),
    new_id: str = typer.Argument(..., help="新快照 ID"),
    group_by: Optional[GroupBy] = typer.Option(None, "--group-by", "-g", help="分组维度"),
):
    try:
        diff_result = store.diff_snapshots(old_id, new_id)
    except ValueError as e:
        console.print(f"[red]✘ {e}[/]")
        raise typer.Exit(code=1)

    if group_by == GroupBy.CATEGORY:
        summaries = store.summarize_diff_by_category(old_id, new_id)
        if not summaries:
            console.print("[dim]暂无类别数据[/]")
            return
        for s in summaries:
            table = Table(
                title=f"[bold]{s.category}[/]  "
                f"资产数: [cyan]{s.total_count}[/]  "
                f"异常数: [yellow]{s.anomaly_count}[/]  "
                f"净增减: [green]{s.net_change:+d}[/]",
                show_header=True,
            )
            table.add_column("指标")
            table.add_column("数值", justify="right")
            table.add_row("资产总数", str(s.total_count))
            table.add_row("异常数量", str(s.anomaly_count))
            table.add_row("新增", f"[green]+{s.added_count}[/]")
            table.add_row("移除", f"[red]-{s.removed_count}[/]")
            table.add_row("变更", f"[yellow]~{s.changed_count}[/]")
            table.add_row("净增减", f"[bold]{s.net_change:+d}[/]")
            console.print(table)

        total_added = sum(s.added_count for s in summaries)
        total_removed = sum(s.removed_count for s in summaries)
        total_changed = sum(s.changed_count for s in summaries)
        console.print(
            f"\n[bold]合计[/]: "
            f"[green]+{total_added}[/]  "
            f"[red]-{total_removed}[/]  "
            f"[yellow]~{total_changed}[/]"
        )
    else:
        if not diff_result.has_changes:
            console.print("[green]两个快照无差异[/]")
            return
        console.print(
            f"[bold]差异摘要[/]: "
            f"[green]+{len(diff_result.added)}[/] 新增  "
            f"[red]-{len(diff_result.removed)}[/] 移除  "
            f"[yellow]~{len(diff_result.changed)}[/] 变更"
        )


@app.command()
def delete(
    asset_id: str = typer.Argument(..., help="资产 ID"),
):
    if store.delete_asset(asset_id):
        console.print(f"[green]✔ 资产 {asset_id} 已删除[/]")
    else:
        console.print(f"[red]✘ 未找到资产 {asset_id}[/]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
