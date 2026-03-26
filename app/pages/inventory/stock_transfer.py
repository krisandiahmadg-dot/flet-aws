"""
app/pages/inventory/stock_transfer.py
Inventory → Transfer Antar Cabang
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional
from datetime import date

from app.database import SessionLocal
from app.models import (
    Branch, Warehouse, Product, UnitOfMeasure, StockBalance,
)
from app.services.inventory_service import StockTransferService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn, page_header,
    search_bar, confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS = [
    ("DRAFT",      "Draft"),
    ("APPROVED",   "Disetujui"),
    ("IN_TRANSIT", "Dalam Pengiriman"),
    ("COMPLETED",  "Selesai"),
    ("CANCELLED",  "Dibatalkan"),
]
_STATUS_COLOR = {
    "DRAFT":      Colors.TEXT_MUTED,
    "APPROVED":   Colors.INFO,
    "IN_TRANSIT": Colors.WARNING,
    "COMPLETED":  Colors.SUCCESS,
    "CANCELLED":  Colors.ERROR,
}


def _badge(status):
    color = _STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    label = dict(_STATUS_OPTS).get(status, status)
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _fmt_date(d):
    if not d: return ""
    try: return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
    except: return ""


def _parse_date(val):
    if not (val or "").strip(): return None
    from datetime import datetime
    try: return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except: return None


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession, on_saved):
    with SessionLocal() as db:
        branches   = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        warehouses = db.query(Warehouse)\
            .join(Branch, Warehouse.branch_id == Branch.id)\
            .filter(Branch.company_id == session.company_id,
                    Warehouse.is_active == True).all()
        products   = db.query(Product).filter_by(
            company_id=session.company_id, is_stockable=True,
            is_active=True).order_by(Product.name).all()
        uoms       = db.query(UnitOfMeasure).filter_by(is_active=True).all()

        br_opts  = [(str(b.id), b.name) for b in branches]
        # Map branch_id → list of (wh_id, wh_name) untuk filter
        wh_by_branch: dict = {}
        for w in warehouses:
            bid = str(w.branch_id)
            wh_by_branch.setdefault(bid, []).append((str(w.id), w.name))
        all_wh_opts = [(str(w.id), w.name) for w in warehouses]

        prod_opts= [(str(p.id), f"{p.code} — {p.name}") for p in products]
        uom_opts = [(str(u.id), u.code) for u in uoms]
        prod_map = {str(p.id): {"uom_id": str(p.uom_id)} for p in products}

    f_from_br = make_dropdown("Dari Cabang *",  br_opts, "")
    f_from_wh = make_dropdown("Dari Gudang *",  [("", "— Pilih cabang dulu —")], "")
    f_to_br   = make_dropdown("Ke Cabang *",    br_opts, "")
    f_to_wh   = make_dropdown("Ke Gudang *",    [("", "— Pilih cabang dulu —")], "")
    f_date    = make_field("Tanggal Transfer *",
                           date.today().strftime("%Y-%m-%d"),
                           hint="YYYY-MM-DD", width=160)
    f_notes   = make_field("Catatan", "",
                           multiline=True, min_lines=2, max_lines=3)

    def _filter_wh(branch_id: str, wh_dd: ft.Dropdown, label: str):
        """Update options gudang sesuai cabang yang dipilih."""
        opts = wh_by_branch.get(branch_id, []) if branch_id else []
        wh_dd.options = [
            ft.dropdown.Option(key=v, text=t)
            for v, t in (opts if opts else [("", f"— Tidak ada gudang di cabang ini —")])
        ]
        wh_dd.value = opts[0][0] if len(opts) == 1 else None
        try: wh_dd.update()
        except: pass

    def on_from_br(e):
        _filter_wh(f_from_br.value, f_from_wh, "Dari Gudang *")

    def on_to_br(e):
        _filter_wh(f_to_br.value, f_to_wh, "Ke Gudang *")

    f_from_br.on_select = on_from_br
    f_to_br.on_select   = on_to_br

    # Line items — dinamis
    line_rows: List[Dict] = []
    lines_col = ft.Column(spacing=6)
    dlg_ref   = {"dlg": None}

    def _rebuild_lines():
        ctrls = []
        if not line_rows:
            ctrls.append(ft.Text("Belum ada item.", size=12, color=Colors.TEXT_MUTED))
        else:
            for i, lr in enumerate(line_rows):
                idx = i
                ctrls.append(ft.Container(
                    border=ft.Border.all(1, Colors.BORDER), border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Row(spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(expand=True, content=lr["f_prod"]),
                            lr["f_uom"], lr["f_qty"],
                            ft.IconButton(
                                icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                icon_color=Colors.ERROR, icon_size=18,
                                on_click=lambda e, i=idx: (
                                    line_rows.pop(i), _rebuild_lines()
                                ),
                                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                            ),
                        ],
                    ),
                ))
        lines_col.controls = ctrls
        try:
            if dlg_ref["dlg"]: dlg_ref["dlg"].update()
        except: pass

    def _add_line(e=None):
        f_prod = make_dropdown("Produk *", prod_opts, "")
        f_uom  = make_dropdown("UoM",      uom_opts, "", width=90)
        f_qty  = make_field("Qty *", "1",
                            keyboard_type=ft.KeyboardType.NUMBER, width=100)

        def _on_prod(e, fp=f_prod, fu=f_uom):
            if fp.value and fp.value in prod_map:
                fu.value = prod_map[fp.value]["uom_id"]
                try: fu.update()
                except: pass

        f_prod.on_select = _on_prod
        line_rows.append({"f_prod": f_prod, "f_uom": f_uom, "f_qty": f_qty})
        _rebuild_lines()

    _add_line()

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_from_br.value or not f_to_br.value:
            show_err("Cabang asal dan tujuan wajib dipilih."); return
        if not f_from_wh.value or not f_to_wh.value:
            show_err("Gudang asal dan tujuan wajib dipilih."); return
        if f_from_wh.value == f_to_wh.value:
            show_err("Gudang asal dan tujuan tidak boleh sama."); return
        tr_date = _parse_date(f_date.value)
        if not tr_date:
            show_err("Tanggal tidak valid."); return

        lines = []
        for i, lr in enumerate(line_rows):
            if not lr["f_prod"].value:
                show_err(f"Baris {i+1}: Produk wajib dipilih."); return
            try:
                qty = float(lr["f_qty"].value or 0)
                if qty <= 0:
                    show_err(f"Baris {i+1}: Qty harus > 0."); return
            except ValueError:
                show_err(f"Baris {i+1}: Qty tidak valid."); return

            # Cek stok asal
            with SessionLocal() as db:
                sb = db.query(StockBalance).filter_by(
                    product_id=int(lr["f_prod"].value),
                    warehouse_id=int(f_from_wh.value),
                ).first()
                avail = sb.qty_on_hand if sb else 0
            if qty > avail + 0.001:
                show_err(f"Baris {i+1}: Stok tidak cukup (tersedia {avail:,.2f})."); return

            # Ambil avg_cost dari StockBalance
            with SessionLocal() as db:
                sb = db.query(StockBalance).filter_by(
                    product_id=int(lr["f_prod"].value),
                    warehouse_id=int(f_from_wh.value),
                ).first()
                cost = sb.avg_cost if sb else 0

            lines.append({
                "product_id":   lr["f_prod"].value,
                "uom_id":       lr["f_uom"].value or lr["f_prod"].value,
                "qty_requested":qty,
                "unit_cost":    cost,
            })

        if not lines:
            show_err("Minimal satu item."); return

        data = {
            "transfer_date":    tr_date,
            "from_branch_id":   f_from_br.value,
            "from_warehouse_id":f_from_wh.value,
            "to_branch_id":     f_to_br.value,
            "to_warehouse_id":  f_to_wh.value,
            "notes":            f_notes.value,
        }
        with SessionLocal() as db:
            ok, msg = StockTransferService.create(
                db, session.company_id, session.user_id, data, lines)

        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.SYNC_ALT, color=Colors.ACCENT, size=20),
                    ft.Text("Transfer Stok Antar Cabang",
                            color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=860, height=540,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
                err,
                section_card("Rute Transfer", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=ft.Column(spacing=8, controls=[
                            ft.Text("ASAL", size=11, color=Colors.TEXT_MUTED,
                                    weight=ft.FontWeight.W_600),
                            f_from_br, f_from_wh,
                        ])),
                        ft.Container(col={"xs":12,"sm":6}, content=ft.Column(spacing=8, controls=[
                            ft.Text("TUJUAN", size=11, color=Colors.TEXT_MUTED,
                                    weight=ft.FontWeight.W_600),
                            f_to_br, f_to_wh,
                        ])),
                    ]),
                    ft.Row(spacing=16, controls=[f_date]),
                    f_notes,
                ]),
                section_card("Item Transfer", [
                    lines_col,
                    ft.TextButton(
                        content=ft.Row(tight=True, spacing=6, controls=[
                            ft.Icon(ft.Icons.ADD, size=16, color=Colors.ACCENT),
                            ft.Text("Tambah Item", size=13, color=Colors.ACCENT),
                        ]),
                        on_click=_add_line,
                    ),
                ]),
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg)
    dlg_ref["dlg"] = dlg
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# TABLE + PAGE
# ─────────────────────────────────────────────────────────────
def _trf_to_dicts(transfers) -> List[Dict]:
    result = []
    for t in transfers:
        result.append({
            "id":             t.id,
            "number":         t.transfer_number,
            "status":         t.status,
            "from_branch_id": t.from_branch_id,
            "to_branch_id":   t.to_branch_id,
            "from_branch":    t.from_branch.name    if t.from_branch    else "—",
            "from_wh":        t.from_warehouse.name if t.from_warehouse else "—",
            "to_branch":      t.to_branch.name      if t.to_branch      else "—",
            "to_wh":          t.to_warehouse.name   if t.to_warehouse   else "—",
            "date":           _fmt_date(t.transfer_date),
            "item_count":     len(t.lines or []),
            "tracking_number":t.tracking_number or "—",
            "shipping_method":t.shipping_method or "—",
        })
    return result


def _can_act(session, branch_id: int) -> bool:
    """User bisa aksi jika superadmin (branch_id=None) atau branch_id cocok."""
    if not getattr(session, "branch_id", None):
        return True  # superadmin / tidak terikat cabang
    return session.branch_id == branch_id


def _build_rows(data, page, session, refresh):
    rows = []
    for d in data:
        actions = []

        # DRAFT: hanya cabang pengirim atau superadmin yang bisa setujui/batalkan
        if d["status"] == "DRAFT":
            is_from_branch = _can_act(session, d["from_branch_id"])
            if is_from_branch and session.has_perm("INV_TRANSFER", "can_approve"):
                actions.append(action_btn(
                    ft.Icons.CHECK_CIRCLE_OUTLINE, "Setujui",
                    lambda e, tid=d["id"], n=d["number"]: confirm_dialog(
                        page, "Setujui Transfer", f"Setujui {n}?",
                        lambda: _approve(tid, page, refresh),
                        "Ya, Setujui", Colors.SUCCESS),
                    Colors.SUCCESS))
            if is_from_branch:
                actions.append(action_btn(
                    ft.Icons.CANCEL_OUTLINED, "Batalkan",
                    lambda e, tid=d["id"], n=d["number"]: confirm_dialog(
                        page, "Batalkan", f"Batalkan {n}?",
                        lambda: _cancel(tid, page, refresh),
                        "Ya, Batalkan", Colors.WARNING),
                    Colors.WARNING))

        # APPROVED: hanya cabang pengirim yang bisa kirim
        if d["status"] == "APPROVED":
            if _can_act(session, d["from_branch_id"]):
                actions.append(action_btn(
                    ft.Icons.LOCAL_SHIPPING, "Kirim",
                    lambda e, tid=d["id"], n=d["number"]:
                        _ship_dialog(page, tid, n, refresh),
                    Colors.INFO))

        # IN_TRANSIT: hanya cabang TUJUAN yang bisa terima
        if d["status"] == "IN_TRANSIT":
            if _can_act(session, d["to_branch_id"]):
                actions.append(action_btn(
                    ft.Icons.MOVE_TO_INBOX, "Terima",
                    lambda e, tid=d["id"], n=d["number"]: confirm_dialog(
                        page, "Terima Barang",
                        f"Konfirmasi penerimaan {n}? Stok tujuan akan bertambah.",
                        lambda: _receive(tid, page, session, refresh),
                        "Ya, Terima", Colors.SUCCESS),
                    Colors.SUCCESS))

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text(d["number"], size=13, weight=ft.FontWeight.W_600,
                                color=Colors.TEXT_PRIMARY, font_family="monospace")),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["from_branch"], size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(d["from_wh"],    size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["to_branch"], size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(d["to_wh"],    size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["date"],       size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(f"{d['item_count']} item", size=12, color=Colors.TEXT_PRIMARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["tracking_number"], size=12,
                        color=Colors.TEXT_PRIMARY if d["tracking_number"] != "—"
                              else Colors.TEXT_MUTED,
                        font_family="monospace"),
                ft.Text(d["shipping_method"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(_badge(d["status"])),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def _approve(tid, page, refresh):
    with SessionLocal() as db:
        ok, msg = StockTransferService.approve(db, tid, page.session_id if hasattr(page,"session_id") else 0)
    show_snack(page, msg, ok)
    if ok: refresh()


def _ship_dialog(page, tid: int, tr_number: str, refresh):
    """Dialog input nomor resi sebelum kirim."""
    f_courier = make_field("Kurir / Ekspedisi", "",
                           hint="JNE, TIKI, SiCepat, dll", width=200)
    f_resi    = make_field("Nomor Resi *", "",
                           hint="Masukkan nomor resi pengiriman")
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def do_ship(e):
        if not f_resi.value.strip():
            err.value = "Nomor resi wajib diisi."; err.visible = True
            try: err.update()
            except: pass
            return
        with SessionLocal() as db:
            ok, msg = StockTransferService.confirm_ship(
                db, tid, 0,
                tracking_number=f_resi.value.strip(),
                shipping_method=f_courier.value.strip() or None,
            )
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: refresh()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.LOCAL_SHIPPING, color=Colors.INFO, size=20),
                    ft.Text(f"Kirim — {tr_number}",
                            color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=420,
            content=ft.Column(spacing=14, tight=True, controls=[
                ft.Text(
                    "Masukkan informasi pengiriman. Stok gudang asal akan dikurangi "
                    "setelah konfirmasi.",
                    size=12, color=Colors.TEXT_MUTED,
                ),
                err,
                f_courier,
                f_resi,
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Konfirmasi Kirim",
                bgcolor=Colors.INFO, color=ft.Colors.WHITE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=do_ship),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


def _receive(tid, page, session, refresh):
    with SessionLocal() as db:
        ok, msg = StockTransferService.confirm_receive(
            db, tid, session.user_id,
            user_branch_id=getattr(session, "branch_id", None),
        )
    show_snack(page, msg, ok)
    if ok: refresh()


def _cancel(tid, page, refresh):
    with SessionLocal() as db:
        ok, msg = StockTransferService.cancel(db, tid)
    show_snack(page, msg, ok)
    if ok: refresh()


def StockTransferPage(page, session: AppSession) -> ft.Control:
    search_val  = {"q": ""}
    status_val  = {"v": ""}
    filter_area = ft.Container()

    def _load():
        with SessionLocal() as db:
            trs = StockTransferService.get_all(
                db, session.company_id, search_val["q"], status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _trf_to_dicts(trs)

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("No. Transfer",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Dari",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Ke",            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tanggal",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Resi",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=58, column_spacing=16,
        columns=COLS,
        rows=_build_rows(initial, page, session, lambda: None),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada transfer stok.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def _filter_bar():
        filters = [("","Semua")] + _STATUS_OPTS
        btns = []
        for val, label in filters:
            is_act = status_val["v"] == val
            color  = _STATUS_COLOR.get(val, Colors.TEXT_SECONDARY)
            btns.append(ft.Container(
                height=32, padding=ft.Padding.symmetric(horizontal=12),
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=ft.Colors.with_opacity(0.12, color) if is_act else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, color if is_act else Colors.BORDER),
                on_click=lambda e, v=val: on_filter(v), ink=True,
                content=ft.Text(label, size=12,
                    color=color if is_act else Colors.TEXT_SECONDARY,
                    weight=ft.FontWeight.W_600 if is_act else ft.FontWeight.W_400),
            ))
        return ft.Row(spacing=6, wrap=True, controls=btns)

    filter_area.content = _filter_bar()

    def refresh():
        data = _load()
        table.rows = _build_rows(data, page, session, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada transfer ditemukan.")]
        filter_area.content = _filter_bar()
        try: table_area.update(); filter_area.update()
        except: pass

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    def on_filter(val):
        status_val["v"] = val
        refresh()

    table.rows = _build_rows(initial, page, session, refresh)

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=0, controls=[
            page_header(
                "Transfer Stok",
                "Pindah stok antar cabang / gudang",
                "Buat Transfer",
                on_action=lambda: _form_dialog(page, session, refresh),
                action_icon=ft.Icons.ADD,
            ),
            ft.Container(padding=ft.Padding.only(bottom=12), content=filter_area),
            ft.Row(controls=[search_bar("Cari nomor transfer...", on_search)]),
            ft.Container(height=12),
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[table_area]),
            ),
        ]),
    )
