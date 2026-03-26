"""
app/pages/inventory/stock_movement.py
Inventory → Pergerakan Stok
History semua mutasi stok: GR, Transfer, Opname Adjustment
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import (
    Branch, Warehouse, Product, ProductCategory,
    GoodsReceipt, GoodsReceiptLine,
    StockTransfer, StockTransferLine,
    StockOpname, StockOpnameLine,
    StockBalance,
)
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, page_header, search_bar,
    empty_state, section_card,
)
from app.utils.theme import Colors, Sizes
from sqlalchemy.orm import joinedload
from sqlalchemy import or_


# ─────────────────────────────────────────────────────────────
# MOVEMENT TYPES & COLORS
# ─────────────────────────────────────────────────────────────
_TYPE_META = {
    "GR":           {"label": "Penerimaan Barang",   "color": Colors.SUCCESS, "icon": ft.Icons.MOVE_TO_INBOX,      "sign": "+"},
    "TRANSFER_OUT": {"label": "Transfer Keluar",      "color": Colors.ERROR,   "icon": ft.Icons.OUTBOX,             "sign": "-"},
    "TRANSFER_IN":  {"label": "Transfer Masuk",       "color": Colors.SUCCESS, "icon": ft.Icons.INBOX,              "sign": "+"},
    "ADJUSTMENT+":  {"label": "Penyesuaian Tambah",  "color": Colors.SUCCESS, "icon": ft.Icons.ADD_CIRCLE_OUTLINE, "sign": "+"},
    "ADJUSTMENT-":  {"label": "Penyesuaian Kurang",  "color": Colors.WARNING, "icon": ft.Icons.REMOVE_CIRCLE_OUTLINE,"sign": "-"},
}


def _type_badge(mv_type: str) -> ft.Container:
    meta  = _TYPE_META.get(mv_type, {"label": mv_type, "color": Colors.TEXT_MUTED, "sign": ""})
    color = meta["color"]
    return ft.Container(
        content=ft.Text(meta["label"], size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _fmt_date(d) -> str:
    if not d: return ""
    try: return d.strftime("%Y-%m-%d %H:%M") if hasattr(d, "strftime") else str(d)[:16]
    except: return ""


def _parse_date(val: str):
    if not (val or "").strip(): return None
    from datetime import datetime
    try: return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except: return None


# ─────────────────────────────────────────────────────────────
# QUERY — kumpulkan semua pergerakan dari berbagai sumber
# ─────────────────────────────────────────────────────────────
def _load_movements(db, company_id: int,
                    search: str = "",
                    branch_id: Optional[int] = None,
                    warehouse_id: Optional[int] = None,
                    mv_type: str = "",
                    date_from: Optional[date] = None,
                    date_to: Optional[date] = None) -> List[Dict]:
    movements = []

    # ── 1. Goods Receipt (CONFIRMED) ──────────────────────────
    q_gr = db.query(GoodsReceiptLine)\
              .join(GoodsReceipt, GoodsReceiptLine.gr_id == GoodsReceipt.id)\
              .join(Branch, GoodsReceipt.branch_id == Branch.id)\
              .filter(
                  Branch.company_id == company_id,
                  GoodsReceipt.status == "CONFIRMED",
              )\
              .options(
                  joinedload(GoodsReceiptLine.gr).joinedload(GoodsReceipt.branch),
                  joinedload(GoodsReceiptLine.gr).joinedload(GoodsReceipt.warehouse),
                  joinedload(GoodsReceiptLine.gr).joinedload(GoodsReceipt.po),
                  joinedload(GoodsReceiptLine.product).joinedload(Product.uom),
              )

    if branch_id:
        q_gr = q_gr.filter(GoodsReceipt.branch_id == branch_id)
    if warehouse_id:
        q_gr = q_gr.filter(GoodsReceipt.warehouse_id == warehouse_id)
    if search:
        q_gr = q_gr.filter(or_(
            Product.name.ilike(f"%{search}%"),
            Product.code.ilike(f"%{search}%"),
        ))

    for ln in q_gr.all():
        gr = ln.gr
        if not gr: continue
        mv_date = gr.created_at
        if date_from and mv_date and mv_date.date() < date_from: continue
        if date_to   and mv_date and mv_date.date() > date_to:   continue
        if mv_type and mv_type != "GR": continue

        qty_net = (ln.qty_received or 0) - (ln.qty_rejected or 0)
        movements.append({
            "date":         mv_date,
            "date_str":     _fmt_date(mv_date),
            "mv_type":      "GR",
            "ref_number":   gr.gr_number,
            "ref_detail":   f"PO: {gr.po.po_number if gr.po else '—'}",
            "product_name": ln.product.name if ln.product else "—",
            "product_code": ln.product.code if ln.product else "",
            "uom_code":     ln.product.uom.code if (ln.product and ln.product.uom) else "—",
            "branch":       gr.branch.name    if gr.branch    else "—",
            "warehouse":    gr.warehouse.name if gr.warehouse else "—",
            "qty":          qty_net,
            "unit_cost":    ln.unit_cost or 0,
            "lot_number":   ln.lot_number or "—",
        })

    # ── 2. Stock Transfer OUT (COMPLETED) ────────────────────
    if not mv_type or mv_type in ("TRANSFER_OUT", "TRANSFER_IN"):
        q_tr = db.query(StockTransferLine)\
                  .join(StockTransfer, StockTransferLine.transfer_id == StockTransfer.id)\
                  .filter(
                      StockTransfer.company_id == company_id,
                      StockTransfer.status == "COMPLETED",
                  )\
                  .options(
                      joinedload(StockTransferLine.transfer)
                          .joinedload(StockTransfer.from_branch),
                      joinedload(StockTransferLine.transfer)
                          .joinedload(StockTransfer.from_warehouse),
                      joinedload(StockTransferLine.transfer)
                          .joinedload(StockTransfer.to_branch),
                      joinedload(StockTransferLine.transfer)
                          .joinedload(StockTransfer.to_warehouse),
                      joinedload(StockTransferLine.product)
                          .joinedload(Product.uom),
                  )

        for ln in q_tr.all():
            tr = ln.transfer
            if not tr: continue
            mv_date = tr.received_at or tr.shipped_at or tr.created_at
            if date_from and mv_date and mv_date.date() < date_from: continue
            if date_to   and mv_date and mv_date.date() > date_to:   continue

            qty = ln.qty_received or ln.qty_shipped or ln.qty_requested

            # Transfer OUT dari gudang asal
            if not mv_type or mv_type == "TRANSFER_OUT":
                if not branch_id or tr.from_branch_id == branch_id:
                    if not warehouse_id or tr.from_warehouse_id == warehouse_id:
                        movements.append({
                            "date":         mv_date,
                            "date_str":     _fmt_date(mv_date),
                            "mv_type":      "TRANSFER_OUT",
                            "ref_number":   tr.transfer_number,
                            "ref_detail":   f"→ {tr.to_branch.name if tr.to_branch else '—'}",
                            "product_name": ln.product.name if ln.product else "—",
                            "product_code": ln.product.code if ln.product else "",
                            "uom_code":     ln.product.uom.code if (ln.product and ln.product.uom) else "—",
                            "branch":       tr.from_branch.name    if tr.from_branch    else "—",
                            "warehouse":    tr.from_warehouse.name if tr.from_warehouse else "—",
                            "qty":          -qty,
                            "unit_cost":    ln.unit_cost or 0,
                            "lot_number":   ln.lot_number or "—",
                        })

            # Transfer IN ke gudang tujuan
            if not mv_type or mv_type == "TRANSFER_IN":
                if not branch_id or tr.to_branch_id == branch_id:
                    if not warehouse_id or tr.to_warehouse_id == warehouse_id:
                        movements.append({
                            "date":         mv_date,
                            "date_str":     _fmt_date(mv_date),
                            "mv_type":      "TRANSFER_IN",
                            "ref_number":   tr.transfer_number,
                            "ref_detail":   f"← {tr.from_branch.name if tr.from_branch else '—'}",
                            "product_name": ln.product.name if ln.product else "—",
                            "product_code": ln.product.code if ln.product else "",
                            "uom_code":     ln.product.uom.code if (ln.product and ln.product.uom) else "—",
                            "branch":       tr.to_branch.name    if tr.to_branch    else "—",
                            "warehouse":    tr.to_warehouse.name if tr.to_warehouse else "—",
                            "qty":          qty,
                            "unit_cost":    ln.unit_cost or 0,
                            "lot_number":   ln.lot_number or "—",
                        })

    # ── 3. Stock Opname Adjustment (POSTED) ──────────────────
    if not mv_type or mv_type in ("ADJUSTMENT+", "ADJUSTMENT-"):
        q_op = db.query(StockOpnameLine)\
                  .join(StockOpname, StockOpnameLine.opname_id == StockOpname.id)\
                  .join(Branch, StockOpname.branch_id == Branch.id)\
                  .filter(
                      Branch.company_id == company_id,
                      StockOpname.status == "POSTED",
                  )\
                  .options(
                      joinedload(StockOpnameLine.opname)
                          .joinedload(StockOpname.branch),
                      joinedload(StockOpnameLine.opname)
                          .joinedload(StockOpname.warehouse),
                      joinedload(StockOpnameLine.product)
                          .joinedload(Product.uom),
                  )

        if branch_id:
            q_op = q_op.filter(StockOpname.branch_id == branch_id)
        if warehouse_id:
            q_op = q_op.filter(StockOpname.warehouse_id == warehouse_id)

        for ln in q_op.all():
            op = ln.opname
            if not op: continue
            diff = (ln.qty_physical or 0) - (ln.qty_system or 0)
            if diff == 0: continue  # tidak ada selisih, skip

            mv_date = op.posted_at or op.created_at
            if date_from and mv_date and mv_date.date() < date_from: continue
            if date_to   and mv_date and mv_date.date() > date_to:   continue

            adj_type = "ADJUSTMENT+" if diff > 0 else "ADJUSTMENT-"
            if mv_type and mv_type != adj_type: continue

            movements.append({
                "date":         mv_date,
                "date_str":     _fmt_date(mv_date),
                "mv_type":      adj_type,
                "ref_number":   op.opname_number,
                "ref_detail":   "Penyesuaian Opname",
                "product_name": ln.product.name if ln.product else "—",
                "product_code": ln.product.code if ln.product else "",
                "uom_code":     ln.product.uom.code if (ln.product and ln.product.uom) else "—",
                "branch":       op.branch.name    if op.branch    else "—",
                "warehouse":    op.warehouse.name if op.warehouse else "—",
                "qty":          diff,
                "unit_cost":    ln.unit_cost or 0,
                "lot_number":   ln.lot_number or "—",
            })

    # Sort by date desc
    movements.sort(key=lambda x: x["date"] or date(2000,1,1), reverse=True)
    return movements


# ─────────────────────────────────────────────────────────────
# BUILD TABLE ROWS
# ─────────────────────────────────────────────────────────────
def _build_rows(movements: List[Dict]) -> List[ft.DataRow]:
    rows = []
    for m in movements:
        meta  = _TYPE_META.get(m["mv_type"], {"color": Colors.TEXT_MUTED, "sign": ""})
        color = meta["color"]
        qty   = m["qty"]
        sign  = "+" if qty > 0 else ""
        nilai = abs(qty) * m["unit_cost"]

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text(m["date_str"], size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(_type_badge(m["mv_type"])),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(m["ref_number"], size=12, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY, font_family="monospace"),
                ft.Text(m["ref_detail"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(m["product_name"], size=13, color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_500),
                ft.Text(m["product_code"], size=11, color=Colors.TEXT_MUTED,
                        font_family="monospace"),
            ])),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(m["branch"],    size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(m["warehouse"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(m["lot_number"], size=12, color=Colors.TEXT_MUTED)),
            ft.DataCell(ft.Text(
                f"{sign}{abs(qty):,.2f} {m['uom_code']}",
                size=13, weight=ft.FontWeight.W_600,
                color=color,
            )),
            ft.DataCell(ft.Text(
                f"Rp {nilai:,.0f}", size=12, color=Colors.TEXT_SECONDARY)),
        ]))
    return rows


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def StockMovementPage(page, session: AppSession) -> ft.Control:
    # Default: 30 hari terakhir
    search_val = {"q": ""}
    _user_branch = getattr(session, "branch_id", None)
    filter_state = {
        "branch_id":    _user_branch,
        "warehouse_id": None,
        "mv_type":      "",
        "date_from":    (date.today() - timedelta(days=30)).strftime("%Y-%m-%d"),
        "date_to":      date.today().strftime("%Y-%m-%d"),
    }

    # Load filter options
    with SessionLocal() as db:
        branches   = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        warehouses = db.query(Warehouse)\
            .join(Branch, Warehouse.branch_id == Branch.id)\
            .filter(Branch.company_id == session.company_id,
                    Warehouse.is_active == True).all()
        br_opts  = [("", "Semua Cabang")]  + [(str(b.id), b.name) for b in branches]
        wh_opts  = [("", "Semua Gudang")]  + [(str(w.id), w.name) for w in warehouses]

    type_opts = [
        ("",             "Semua Tipe"),
        ("GR",           "Penerimaan Barang"),
        ("TRANSFER_IN",  "Transfer Masuk"),
        ("TRANSFER_OUT", "Transfer Keluar"),
        ("ADJUSTMENT+",  "Penyesuaian +"),
        ("ADJUSTMENT-",  "Penyesuaian -"),
    ]

    def _load() -> List[Dict]:
        with SessionLocal() as db:
            return _load_movements(
                db, session.company_id,
                search=search_val["q"],
                branch_id=filter_state["branch_id"],
                warehouse_id=filter_state["warehouse_id"],
                mv_type=filter_state["mv_type"],
                date_from=_parse_date(filter_state["date_from"]),
                date_to=_parse_date(filter_state["date_to"]),
            )

    initial = _load()

    # Summary bar
    def _build_summary(movements: List[Dict]) -> ft.Row:
        total_in  = sum(m["qty"] for m in movements if m["qty"] > 0)
        total_out = sum(abs(m["qty"]) for m in movements if m["qty"] < 0)
        nilai_in  = sum(m["qty"] * m["unit_cost"] for m in movements if m["qty"] > 0)
        return ft.Row(spacing=12, controls=[
            _stat_card("Total Transaksi", str(len(movements))),
            _stat_card("Total Masuk",  f"+{total_in:,.2f}", Colors.SUCCESS),
            _stat_card("Total Keluar", f"-{total_out:,.2f}", Colors.ERROR),
            _stat_card("Nilai Masuk",  f"Rp {nilai_in:,.0f}", Colors.ACCENT),
        ])

    def _stat_card(label, val, color=None):
        return ft.Container(
            expand=True,
            bgcolor=Colors.BG_CARD,
            border_radius=Sizes.CARD_RADIUS,
            border=ft.Border.all(1, Colors.BORDER),
            padding=ft.Padding.all(14),
            content=ft.Column(spacing=2, controls=[
                ft.Text(label, size=11, color=Colors.TEXT_MUTED),
                ft.Text(val, size=18, weight=ft.FontWeight.W_700,
                        color=color or Colors.TEXT_PRIMARY),
            ]),
        )

    summary_ref = {"ctrl": ft.Row(spacing=12, controls=[])}
    summary_ref["ctrl"] = _build_summary(initial)

    COLS = [
        ft.DataColumn(ft.Text("Tanggal",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Referensi",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Produk",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Lokasi",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Lot",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Qty",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Nilai",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

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
        controls=[table if initial else empty_state("Tidak ada pergerakan stok.")],
        scroll=ft.ScrollMode.AUTO,
    )
    summary_container = ft.Container(content=summary_ref["ctrl"])

    # Filter controls
    f_branch    = make_dropdown("Cabang",    br_opts,   str(_user_branch) if _user_branch else "")
    f_branch.disabled = bool(_user_branch)
    f_warehouse = make_dropdown("Gudang",    wh_opts,   "")
    f_type      = make_dropdown("Tipe Mutasi", type_opts, "")
    f_date_from = make_field("Dari Tanggal", filter_state["date_from"],
                             hint="YYYY-MM-DD", width=145)
    f_date_to   = make_field("Sampai",       filter_state["date_to"],
                             hint="YYYY-MM-DD", width=145)

    def refresh():
        data = _load()
        table.rows = _build_rows(data)
        table_area.controls = [table if data else empty_state("Tidak ada pergerakan stok.")]
        summary_container.content = _build_summary(data)
        try:
            table_area.update()
            summary_container.update()
        except Exception:
            pass

    def on_filter(e=None):
        filter_state["branch_id"]    = int(f_branch.value)    if f_branch.value    else None
        filter_state["warehouse_id"] = int(f_warehouse.value) if f_warehouse.value else None
        filter_state["mv_type"]      = f_type.value or ""
        filter_state["date_from"]    = f_date_from.value or ""
        filter_state["date_to"]      = f_date_to.value or ""
        refresh()

    f_branch.on_select    = on_filter
    f_warehouse.on_select = on_filter
    f_type.on_select      = on_filter
    f_date_from.on_change = on_filter
    f_date_to.on_change   = on_filter

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    filter_panel = ft.Container(
        bgcolor=Colors.BG_CARD,
        border_radius=Sizes.CARD_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.all(14),
        content=ft.Column(spacing=10, controls=[
            ft.Row(spacing=12, wrap=True, controls=[
                f_branch, f_warehouse, f_type,
            ]),
            ft.Row(spacing=12, controls=[
                search_bar("Cari produk...", on_search),
                f_date_from,
                ft.Text("s/d", size=12, color=Colors.TEXT_MUTED),
                f_date_to,
                ft.TextButton(
                    "Terapkan",
                    style=ft.ButtonStyle(color=Colors.ACCENT),
                    on_click=on_filter,
                ),
                ft.TextButton(
                    "30 Hari",
                    style=ft.ButtonStyle(color=Colors.TEXT_MUTED),
                    on_click=lambda e: (
                        setattr(f_date_from, "value",
                                (date.today()-timedelta(days=30)).strftime("%Y-%m-%d")),
                        setattr(f_date_to, "value", date.today().strftime("%Y-%m-%d")),
                        on_filter(),
                        f_date_from.update(),
                        f_date_to.update(),
                    ),
                ),
                ft.TextButton(
                    "Bulan Ini",
                    style=ft.ButtonStyle(color=Colors.TEXT_MUTED),
                    on_click=lambda e: (
                        setattr(f_date_from, "value",
                                date.today().strftime("%Y-%m-01")),
                        setattr(f_date_to, "value", date.today().strftime("%Y-%m-%d")),
                        on_filter(),
                        f_date_from.update(),
                        f_date_to.update(),
                    ),
                ),
            ]),
        ]),
    )

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=12, controls=[
            page_header("Pergerakan Stok",
                        "History semua mutasi stok: penerimaan, transfer, penyesuaian"),
            summary_container,
            filter_panel,
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[table_area]),
            ),
        ]),
    )
