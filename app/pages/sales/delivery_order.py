"""
app/pages/sales/delivery_order.py
Delivery Order — DO
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional
from datetime import date

from app.database import SessionLocal
from app.models import Branch, Warehouse, SalesOrder, SalesOrderLine, Product, UnitOfMeasure
from app.services.sales_service import SalesOrderService, DeliveryOrderService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn, page_header,
    search_bar, confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS = [
    ("DRAFT",     "Draft"),
    ("SHIPPED",   "Dikirim"),
    ("DELIVERED", "Diterima"),
    ("RETURNED",  "Dikembalikan"),
    ("CANCELLED", "Dibatalkan"),
]
_STATUS_COLOR = {
    "DRAFT":     Colors.TEXT_MUTED,
    "SHIPPED":   Colors.INFO,
    "DELIVERED": Colors.SUCCESS,
    "RETURNED":  Colors.WARNING,
    "CANCELLED": Colors.ERROR,
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


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession, on_saved):
    _user_branch = getattr(session, "branch_id", None)

    with SessionLocal() as db:
        branches   = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        warehouses = db.query(Warehouse)\
            .join(Branch, Warehouse.branch_id == Branch.id)\
            .filter(Branch.company_id == session.company_id, Warehouse.is_active == True).all()

        if _user_branch:
            branches = [b for b in branches if b.id == _user_branch]

        wh_by_branch = {}
        for w in warehouses:
            wh_by_branch.setdefault(str(w.branch_id), []).append((str(w.id), w.name))

        confirmed_sos = SalesOrderService.get_confirmed_sos(
            db, session.company_id, branch_id=_user_branch)

        br_opts = [(str(b.id), b.name) for b in branches]
        so_opts = [("", "— Pilih SO —")] + [
            (str(so.id),
             f"{so.so_number} — {so.customer.name if so.customer else '?'}")
            for so in confirmed_sos
        ]
        # Map so_id → lines data untuk auto-fill
        so_lines_map: Dict[str, List[Dict]] = {}
        for so in confirmed_sos:
            lines = []
            for ln in (so.lines or []):
                sisa = round((ln.qty_ordered or 0) - (ln.qty_delivered or 0), 4)
                if sisa <= 0: continue
                lines.append({
                    "sol_id":      str(ln.id),
                    "product_id":  str(ln.product_id),
                    "product_name":ln.product.name if ln.product else "—",
                    "product_code":ln.product.code if ln.product else "",
                    "uom_id":      str(ln.uom_id),
                    "uom_code":    ln.uom.code if ln.uom else "—",
                    "qty_ordered": ln.qty_ordered,
                    "qty_delivered": ln.qty_delivered or 0,
                    "qty_sisa":    sisa,
                })
            if lines:
                so_lines_map[str(so.id)] = lines

    if not confirmed_sos:
        show_snack(page, "Tidak ada SO yang siap dikirim.", False)
        return

    dlg_ref = {"dlg": None}

    f_branch  = make_dropdown("Cabang *", br_opts,
                              str(_user_branch) if _user_branch else "", disabled=bool(_user_branch))
    f_wh      = make_dropdown("Gudang *", [("", "— Pilih cabang dulu —")], "")
    f_so      = make_dropdown("SO *", so_opts, "")
    f_date    = make_field("Tgl Pengiriman *", date.today().strftime("%Y-%m-%d"),
                           hint="YYYY-MM-DD", width=160)
    f_courier = make_field("Kurir", "", hint="JNE, TIKI, dll", width=160)
    f_method  = make_field("Metode", "", width=160)
    f_notes   = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=3)
    err       = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    # Lines container — auto-generated dari SO
    lines_col = ft.Column(spacing=6)
    line_fields: List[Dict] = []  # {sol_id, product_id, uom_id, qty_sisa, f_qty, f_lot}

    def _filter_wh(branch_id):
        opts = wh_by_branch.get(branch_id, [])
        f_wh.options = [ft.dropdown.Option(key=v, text=t)
                        for v, t in (opts or [("", "— Tidak ada gudang —")])]
        f_wh.value = opts[0][0] if len(opts) == 1 else None
        try: f_wh.update()
        except: pass

    f_branch.on_select = lambda e: _filter_wh(f_branch.value or "")
    if _user_branch:
        _filter_wh(str(_user_branch))

    def on_so_select(e):
        so_id = f_so.value or ""
        line_fields.clear()
        if not so_id or so_id not in so_lines_map:
            lines_col.controls = [ft.Text("Pilih SO untuk melihat item.",
                                          size=12, color=Colors.TEXT_MUTED)]
            try:
                if dlg_ref["dlg"]: dlg_ref["dlg"].update()
            except: pass
            return

        rows = []
        for ln in so_lines_map[so_id]:
            f_qty = make_field("Qty Kirim *", str(ln["qty_sisa"]),
                               keyboard_type=ft.KeyboardType.NUMBER, width=100)
            f_lot = make_field("Lot/Batch", "", width=120)
            line_fields.append({
                "sol_id":     ln["sol_id"],
                "product_id": ln["product_id"],
                "uom_id":     ln["uom_id"],
                "qty_sisa":   ln["qty_sisa"],
                "f_qty":      f_qty,
                "f_lot":      f_lot,
            })
            rows.append(ft.Container(
                border=ft.Border.all(1, Colors.BORDER), border_radius=4,
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                content=ft.Row(spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(expand=True, content=ft.Column(
                            spacing=1, tight=True, controls=[
                                ft.Text(ln["product_name"], size=13,
                                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_500),
                                ft.Text(ln["product_code"], size=11,
                                        color=Colors.TEXT_MUTED, font_family="monospace"),
                            ]
                        )),
                        ft.Container(width=50, content=ft.Text(
                            ln["uom_code"], size=12, color=Colors.TEXT_SECONDARY)),
                        ft.Container(width=90, content=ft.Text(
                            f"Sisa: {ln['qty_sisa']:,.2f}", size=12, color=Colors.WARNING)),
                        f_qty,
                        f_lot,
                    ],
                ),
            ))
        lines_col.controls = rows
        try:
            if dlg_ref["dlg"]: dlg_ref["dlg"].update()
        except: pass

    f_so.on_select = on_so_select
    lines_col.controls = [ft.Text("Pilih SO untuk melihat item.",
                                   size=12, color=Colors.TEXT_MUTED)]

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_branch.value: show_err("Cabang wajib dipilih."); return
        if not f_wh.value:     show_err("Gudang wajib dipilih."); return
        if not f_so.value:     show_err("SO wajib dipilih."); return
        if not line_fields:    show_err("Tidak ada item dari SO ini."); return

        lines = []
        for i, lf in enumerate(line_fields):
            try:
                qty = float(lf["f_qty"].value or 0)
            except ValueError:
                show_err(f"Baris {i+1}: Qty tidak valid."); return
            if qty <= 0: continue
            if qty > lf["qty_sisa"] + 0.001:
                show_err(f"Baris {i+1}: Qty ({qty:,.2f}) melebihi sisa ({lf['qty_sisa']:,.2f})."); return
            lines.append({
                "sol_id":     lf["sol_id"],
                "product_id": lf["product_id"],
                "uom_id":     lf["uom_id"],
                "qty_shipped": qty,
                "lot_number":  lf["f_lot"].value.strip() or None,
            })

        if not lines:
            show_err("Semua qty 0. Isi minimal satu item."); return

        data = {
            "branch_id":      f_branch.value,
            "warehouse_id":   f_wh.value,
            "so_id":          f_so.value,
            "delivery_date":  f_date.value,
            "courier":        f_courier.value,
            "shipping_method":f_method.value,
            "notes":          f_notes.value,
        }
        with SessionLocal() as db:
            ok, msg = DeliveryOrderService.create(
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
                    ft.Icon(ft.Icons.LOCAL_SHIPPING, color=Colors.ACCENT, size=20),
                    ft.Text("Buat Delivery Order", color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=900, height=560,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
                err,
                section_card("Informasi DO", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":4}, content=f_branch),
                        ft.Container(col={"xs":12,"sm":4}, content=f_wh),
                        ft.Container(col={"xs":12,"sm":4}, content=f_so),
                    ]),
                    ft.Row(spacing=12, controls=[f_date, f_courier, f_method]),
                    f_notes,
                ]),
                section_card("Item Pengiriman", [lines_col]),
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
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
def _dos_to_dicts(dos) -> List[Dict]:
    return [{
        "id":       do.id,
        "number":   do.do_number,
        "status":   do.status,
        "so_number":do.so.so_number   if do.so else "—",
        "customer": do.so.customer.name if (do.so and do.so.customer) else "—",
        "branch":   do.branch.name    if do.branch    else "—",
        "warehouse":do.warehouse.name if do.warehouse else "—",
        "date":     _fmt_date(do.delivery_date),
        "courier":  do.courier or "—",
        "items":    len(do.lines or []),
    } for do in dos]


def _build_rows(data, page, session, refresh):
    rows = []
    for d in data:
        actions = []
        if d["status"] == "DRAFT":
            actions.append(action_btn(
                ft.Icons.LOCAL_SHIPPING, "Kirim",
                lambda e, did=d["id"], n=d["number"]: confirm_dialog(
                    page, "Konfirmasi Kirim", f"Kirim {n}?",
                    lambda: _ship(did, page, refresh),
                    "Ya, Kirim", Colors.INFO),
                Colors.INFO))
            actions.append(action_btn(
                ft.Icons.CANCEL_OUTLINED, "Batalkan",
                lambda e, did=d["id"], n=d["number"]: confirm_dialog(
                    page, "Batalkan DO", f"Batalkan {n}?",
                    lambda: _cancel(did, page, refresh),
                    "Ya, Batalkan", Colors.WARNING),
                Colors.WARNING))
        if d["status"] == "SHIPPED":
            actions.append(action_btn(
                ft.Icons.CHECK_CIRCLE_OUTLINE, "Konfirmasi Diterima",
                lambda e, did=d["id"], n=d["number"]: confirm_dialog(
                    page, "Konfirmasi Diterima", f"{n} sudah diterima pelanggan?",
                    lambda: _deliver(did, page, refresh),
                    "Ya, Diterima", Colors.SUCCESS),
                Colors.SUCCESS))

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["number"], size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY, font_family="monospace"),
                ft.Text(d["date"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["so_number"], size=12, color=Colors.ACCENT,
                                font_family="monospace")),
            ft.DataCell(ft.Text(d["customer"],  size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["branch"],   size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(d["warehouse"],size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["courier"],   size=12, color=Colors.TEXT_MUTED)),
            ft.DataCell(ft.Text(f"{d['items']} item", size=12)),
            ft.DataCell(_badge(d["status"])),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def _ship(did, page, refresh):
    with SessionLocal() as db:
        ok, msg = DeliveryOrderService.ship(db, did)
    show_snack(page, msg, ok)
    if ok: refresh()


def _deliver(did, page, refresh):
    with SessionLocal() as db:
        ok, msg = DeliveryOrderService.deliver(db, did)
    show_snack(page, msg, ok)
    if ok: refresh()


def _cancel(did, page, refresh):
    with SessionLocal() as db:
        ok, msg = DeliveryOrderService.cancel(db, did)
    show_snack(page, msg, ok)
    if ok: refresh()


def DeliveryOrderPage(page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}
    status_val = {"v": ""}
    filter_area = ft.Container()

    def _load():
        with SessionLocal() as db:
            dos = DeliveryOrderService.get_all(
                db, session.company_id, search_val["q"], status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _dos_to_dicts(dos)

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("No. DO",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("SO Ref",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Pelanggan", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Dari",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kurir",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=58, column_spacing=16,
        columns=COLS, rows=_build_rows(initial, page, session, lambda: None),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada Delivery Order.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def _filter_bar():
        filters = [("", "Semua")] + _STATUS_OPTS
        btns = []
        for val, label in filters:
            is_act = status_val["v"] == val
            color  = _STATUS_COLOR.get(val, Colors.TEXT_SECONDARY)
            btns.append(ft.Container(
                height=32, padding=ft.Padding.symmetric(horizontal=12),
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=ft.Colors.with_opacity(0.12, color) if is_act else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, color if is_act else Colors.BORDER),
                ink=True, on_click=lambda e, v=val: on_filter(v),
                content=ft.Text(label, size=12,
                    color=color if is_act else Colors.TEXT_SECONDARY,
                    weight=ft.FontWeight.W_600 if is_act else ft.FontWeight.W_400),
            ))
        return ft.Row(spacing=6, wrap=True, controls=btns)

    filter_area.content = _filter_bar()

    def refresh():
        data = _load()
        table.rows = _build_rows(data, page, session, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada DO ditemukan.")]
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
        expand=True, bgcolor=Colors.BG_DARK, padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=0, controls=[
            page_header("Delivery Order", "Kelola pengiriman barang ke pelanggan",
                        "Buat DO", on_action=lambda: _form_dialog(page, session, refresh),
                        action_icon=ft.Icons.ADD),
            ft.Container(padding=ft.Padding.only(bottom=12), content=filter_area),
            ft.Row(controls=[search_bar("Cari nomor DO...", on_search)]),
            ft.Container(height=12),
            ft.Container(expand=True,
                         content=ft.ListView(expand=True, controls=[table_area])),
        ]),
    )
