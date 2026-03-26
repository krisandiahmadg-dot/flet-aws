"""
app/pages/inventory/stock_balance.py
Inventory → Saldo Stok
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional

from app.database import SessionLocal
from app.models import Branch, Warehouse, ProductCategory
from app.services.inventory_service import StockBalanceService
from app.services.auth import AppSession
from app.components.ui import (
    make_dropdown, page_header, search_bar, show_snack,
    empty_state, section_card,
)
from app.utils.theme import Colors, Sizes


def _fmt(n, decimals=2) -> str:
    return f"{n:,.{decimals}f}" if n else "0"


def _stock_level_badge(qty, min_stock) -> ft.Container:
    if min_stock > 0 and qty <= 0:
        color, label = Colors.ERROR,   "Habis"
    elif min_stock > 0 and qty < min_stock:
        color, label = Colors.WARNING, "Rendah"
    else:
        color, label = Colors.SUCCESS, "Normal"
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _build_rows(balances) -> List[ft.DataRow]:
    rows = []
    for sb in balances:
        p  = sb.product
        qty_avail = sb.qty_on_hand - sb.qty_reserved
        nilai     = sb.qty_on_hand * sb.avg_cost

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(p.name if p else "—", size=13,
                        weight=ft.FontWeight.W_500, color=Colors.TEXT_PRIMARY),
                ft.Text(p.code if p else "—", size=11,
                        color=Colors.TEXT_MUTED, font_family="monospace"),
            ])),
            ft.DataCell(ft.Text(
                p.category.name if (p and p.category) else "—",
                size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(sb.branch.name   if sb.branch   else "—",
                        size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(sb.warehouse.name if sb.warehouse else "—",
                        size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(
                sb.lot_number or "—", size=12, color=Colors.TEXT_MUTED)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"{_fmt(sb.qty_on_hand)} {p.uom.code if p and p.uom else ''}",
                        size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(f"Tersedia: {_fmt(qty_avail)}",
                        size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(
                f"Rp {_fmt(sb.avg_cost, 0)}", size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(
                f"Rp {_fmt(nilai, 0)}", size=12,
                color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_500)),
            ft.DataCell(_stock_level_badge(
                sb.qty_on_hand, p.min_stock if p else 0)),
        ]))
    return rows


def _summary_card(label, value, color=None):
    return ft.Container(
        expand=True,
        bgcolor=Colors.BG_CARD,
        border_radius=Sizes.CARD_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.all(16),
        content=ft.Column(spacing=4, controls=[
            ft.Text(label, size=12, color=Colors.TEXT_MUTED),
            ft.Text(str(value), size=22, weight=ft.FontWeight.W_700,
                    color=color or Colors.TEXT_PRIMARY),
        ]),
    )


def StockBalancePage(page, session: AppSession) -> ft.Control:
    search_val   = {"q": ""}
    # Jika user terikat cabang, paksa filter ke cabang tersebut
    _user_branch = getattr(session, "branch_id", None)
    filter_state = {"branch_id": _user_branch, "warehouse_id": None,
                    "category_id": None, "below_min": False}

    # Load filter options
    with SessionLocal() as db:
        branches    = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        warehouses  = db.query(Warehouse)\
            .join(Branch, Warehouse.branch_id == Branch.id)\
            .filter(Branch.company_id == session.company_id,
                    Warehouse.is_active == True).all()
        categories  = db.query(ProductCategory).filter_by(
            company_id=session.company_id).order_by(ProductCategory.name).all()

        br_opts  = [("", "Semua Cabang")] + [(str(b.id), b.name) for b in branches]
        wh_opts  = [("", "Semua Gudang")] + [(str(w.id), w.name) for w in warehouses]
        cat_opts = [("", "Semua Kategori")] + [(str(c.id), c.name) for c in categories]

    def _load():
        with SessionLocal() as db:
            balances = StockBalanceService.get_all(
                db, session.company_id,
                search=search_val["q"],
                branch_id=filter_state["branch_id"],
                warehouse_id=filter_state["warehouse_id"],
                category_id=filter_state["category_id"],
                below_min=filter_state["below_min"],
            )
            # konversi ke plain list dalam session
            return list(balances)

    # Summary cards — dimuat dengan branch filter
    def _load_summary():
        with SessionLocal() as db:
            return StockBalanceService.get_summary(
                db, session.company_id,
                branch_id=filter_state["branch_id"],
            )

    summary_row = ft.Row(spacing=12, controls=[])

    def _rebuild_summary():
        s = _load_summary()
        summary_row.controls = [
            _summary_card("Total SKU",           s["total_sku"]),
            _summary_card("Total Nilai Stok",    f"Rp {s['total_value']:,.0f}"),
            _summary_card("Item di Bawah Minimum", s["below_min"], Colors.WARNING),
            _summary_card("Total Lokasi",        s["total_items"]),
        ]
        try: summary_row.update()
        except: pass

    _rebuild_summary()

    COLS = [
        ft.DataColumn(ft.Text("Produk",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kategori",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang/Gudang",size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Lot",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Qty On Hand",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Avg Cost",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Nilai Stok",   size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    initial = _load()
    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=58, column_spacing=16,
        columns=COLS,
        rows=_build_rows(initial),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada data stok.")],
        scroll=ft.ScrollMode.AUTO,
    )

    # Filter dropdowns
    f_branch   = make_dropdown("Cabang",   br_opts,  str(_user_branch) if _user_branch else "")
    f_branch.disabled = bool(_user_branch)  # user cabang tidak bisa ganti filter cabang
    f_warehouse= make_dropdown("Gudang",   wh_opts,  "")
    f_category = make_dropdown("Kategori", cat_opts, "")
    cb_below   = ft.Checkbox(
        label="Hanya di bawah minimum",
        value=False, active_color=Colors.WARNING,
    )

    def refresh():
        data = _load()
        table.rows = _build_rows(data)
        table_area.controls = [table if data else empty_state("Tidak ada stok ditemukan.")]
        _rebuild_summary()
        try: table_area.update()
        except: pass

    def on_filter(e=None):
        # User terikat cabang tidak bisa ganti filter cabang
        filter_state["branch_id"]    = _user_branch if _user_branch else (
            int(f_branch.value) if f_branch.value else None)
        filter_state["warehouse_id"] = int(f_warehouse.value) if f_warehouse.value else None
        filter_state["category_id"]  = int(f_category.value)  if f_category.value  else None
        filter_state["below_min"]    = cb_below.value
        refresh()

    f_branch.on_select   = on_filter
    f_warehouse.on_select= on_filter
    f_category.on_select = on_filter
    cb_below.on_change   = on_filter

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    filter_row = ft.Row(spacing=12, wrap=True, controls=[
        f_branch, f_warehouse, f_category,
        ft.Container(padding=ft.Padding.only(top=8), content=cb_below),
        ft.Container(
            padding=ft.Padding.only(top=4),
            content=ft.TextButton(
                "Reset Filter",
                style=ft.ButtonStyle(color=Colors.TEXT_MUTED),
                on_click=lambda e: (
                    setattr(f_branch,    "value", ""),
                    setattr(f_warehouse, "value", ""),
                    setattr(f_category,  "value", ""),
                    setattr(cb_below,    "value", False),
                    filter_state.update(
                        branch_id=None, warehouse_id=None,
                        category_id=None, below_min=False),
                    refresh(),
                ),
            ),
        ),
    ])

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=12, controls=[
            page_header("Saldo Stok", "Stok terkini per produk per gudang"),
            summary_row,
            ft.Container(
                bgcolor=Colors.BG_CARD,
                border_radius=Sizes.CARD_RADIUS,
                border=ft.Border.all(1, Colors.BORDER),
                padding=ft.Padding.all(16),
                content=ft.Column(spacing=12, controls=[
                    ft.Row(spacing=12, controls=[
                        search_bar("Cari produk...", on_search),
                    ]),
                    filter_row,
                ]),
            ),
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[table_area]),
            ),
        ]),
    )
