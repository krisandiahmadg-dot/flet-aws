"""
app/pages/sales/sales_order.py
Sales Order — SO
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional
from datetime import date

from app.database import SessionLocal
from app.models import Branch, Warehouse, Customer, Product, UnitOfMeasure, User
from app.services.tax_service import TaxRateService
from app.services.sales_service import SalesOrderService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn, page_header,
    search_bar, confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS = [
    ("DRAFT",             "Draft"),
    ("CONFIRMED",         "Dikonfirmasi"),
    ("PICKING",           "Picking"),
    ("PARTIAL_DELIVERED", "Sebagian Terkirim"),
    ("DELIVERED",         "Terkirim"),
    ("INVOICED",          "Diinvoice"),
    ("CANCELLED",         "Dibatalkan"),
]
_STATUS_COLOR = {
    "DRAFT":             Colors.TEXT_MUTED,
    "CONFIRMED":         Colors.INFO,
    "PICKING":           Colors.WARNING,
    "PARTIAL_DELIVERED": Colors.WARNING,
    "DELIVERED":         Colors.SUCCESS,
    "INVOICED":          Colors.ACCENT,
    "CANCELLED":         Colors.ERROR,
}
_PAY_COLOR = {
    "UNPAID":  Colors.ERROR,
    "PARTIAL": Colors.WARNING,
    "PAID":    Colors.SUCCESS,
    "REFUNDED":Colors.TEXT_MUTED,
}


def _badge(status, color_map=_STATUS_COLOR, label_map=None):
    color = color_map.get(status, Colors.TEXT_MUTED)
    label = (dict(_STATUS_OPTS).get(status, status) if label_map is None
             else label_map.get(status, status))
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _fmt(n, dec=0): return f"{n:,.{dec}f}" if n else "0"
def _fmt_date(d):
    if not d: return ""
    try: return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
    except: return ""


# ─────────────────────────────────────────────────────────────
# LINE EDITOR
# ─────────────────────────────────────────────────────────────
class SOLineEditor:
    def __init__(self, prod_opts, uom_opts, prod_map, dlg_ref):
        self._prod_opts = prod_opts
        self._uom_opts  = uom_opts
        self._prod_map  = prod_map
        self._dlg_ref   = dlg_ref
        self.rows: List[Dict] = []
        self.col  = ft.Column(spacing=6)
        self.summary_text = ft.Text("", size=12, color=Colors.TEXT_SECONDARY,
                                    weight=ft.FontWeight.W_600)

    def _add_row(self, product_id="", uom_id="", qty="1",
                 price="0", disc="0", tax="0", notes=""):
        f_prod  = make_dropdown("Produk *", self._prod_opts, product_id)
        f_uom   = make_dropdown("UoM",      self._uom_opts,  uom_id, width=90)
        f_qty   = make_field("Qty *",   qty,   keyboard_type=ft.KeyboardType.NUMBER, width=90)
        f_price = make_field("Harga *", price, keyboard_type=ft.KeyboardType.NUMBER, width=140)
        f_disc  = make_field("Disc%",   disc,  keyboard_type=ft.KeyboardType.NUMBER, width=70)
        f_tax   = make_field("PPN%",    tax,   keyboard_type=ft.KeyboardType.NUMBER, width=70)
        f_notes = make_field("Ket.",    notes, width=120)

        rd = dict(prod=f_prod, uom=f_uom, qty=f_qty, price=f_price,
                  disc=f_disc, tax=f_tax, notes=f_notes)

        def on_prod(e, r=rd):
            pid = r["prod"].value
            if pid and pid in self._prod_map:
                info = self._prod_map[pid]
                if not r["uom"].value:
                    r["uom"].value = info["uom_id"]
                    try: r["uom"].update()
                    except: pass
                r["price"].value = str(int(info.get("price", 0)))
                try: r["price"].update()
                except: pass
            self._update_summary()

        f_prod.on_select = on_prod
        for fld in [f_qty, f_price, f_disc, f_tax]:
            fld.on_change = lambda e: self._update_summary()

        self.rows.append(rd)
        self._rebuild()

    def _rebuild(self):
        ctrls = []
        for i, rd in enumerate(self.rows):
            idx = i
            ctrls.append(ft.Container(
                border=ft.Border.all(1, Colors.BORDER), border_radius=4,
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                content=ft.Row(spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(expand=True, content=rd["prod"]),
                        rd["uom"], rd["qty"], rd["price"],
                        rd["disc"], rd["tax"], rd["notes"],
                        ft.IconButton(
                            icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                            icon_color=Colors.ERROR, icon_size=18,
                            on_click=lambda e, i=idx: self._remove(i),
                            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                        ),
                    ],
                ),
            ))
        self.col.controls = ctrls or [
            ft.Text("Belum ada item.", size=12, color=Colors.TEXT_MUTED)
        ]
        try:
            if self._dlg_ref["dlg"]: self._dlg_ref["dlg"].update()
        except: pass

    def _remove(self, i):
        self.rows.pop(i)
        self._rebuild()
        self._update_summary()

    def _update_summary(self):
        subtotal = 0.0
        tax_total = 0.0
        for rd in self.rows:
            try:
                q = float(rd["qty"].value or 0)
                p = float(rd["price"].value or 0)
                d = float(rd["disc"].value or 0)
                t = float(rd["tax"].value or 0)
                line_sub = q * p * (1 - d / 100)
                subtotal  += line_sub
                tax_total += line_sub * t / 100
            except: pass
        total = subtotal + tax_total
        self.summary_text.value = (
            f"Subtotal: Rp {subtotal:,.0f}  +  "
            f"PPN: Rp {tax_total:,.0f}  =  "
            f"Total: Rp {total:,.0f}"
        )
        try: self.summary_text.update()
        except: pass

    def validate_and_collect(self) -> tuple[bool, str, List[Dict]]:
        if not self.rows:
            return False, "Minimal satu item.", []
        lines = []
        for i, rd in enumerate(self.rows):
            if not rd["prod"].value:
                return False, f"Baris {i+1}: Produk wajib dipilih.", []
            try:
                qty = float(rd["qty"].value or 0)
                if qty <= 0: return False, f"Baris {i+1}: Qty harus > 0.", []
                price = float(rd["price"].value or 0)
                if price < 0: return False, f"Baris {i+1}: Harga tidak valid.", []
            except ValueError:
                return False, f"Baris {i+1}: Nilai tidak valid.", []
            lines.append({
                "product_id":  rd["prod"].value,
                "uom_id":      rd["uom"].value or rd["prod"].value,
                "qty_ordered": qty,
                "unit_price":  price,
                "discount_pct":float(rd["disc"].value or 0),
                "tax_pct":     float(rd["tax"].value or 0),
                "notes":       rd["notes"].value or "",
            })
        return True, "", lines


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
        customers  = db.query(Customer).filter_by(
            company_id=session.company_id, is_active=True).order_by(Customer.name).all()
        products   = db.query(Product).filter_by(
            company_id=session.company_id, is_sellable=True, is_active=True).order_by(Product.name).all()
        uoms       = db.query(UnitOfMeasure).filter_by(is_active=True).all()
        sales_users= db.query(User).filter_by(
            company_id=session.company_id, is_active=True).order_by(User.full_name).all()
        tax_rates  = TaxRateService.get_all(
            db, session.company_id, tax_type="PPN", active_only=True)
        default_tax= TaxRateService.get_default(db, session.company_id, "PPN", "SALES")

        if _user_branch:
            branches = [b for b in branches if b.id == _user_branch]

        wh_by_branch = {}
        for w in warehouses:
            wh_by_branch.setdefault(str(w.branch_id), []).append((str(w.id), w.name))

        tax_opts = [("", "— Tanpa Pajak —")] + [
            (str(tr.id), f"{tr.code} — {tr.rate}%  {'[Default]' if tr.is_default else ''}")
            for tr in tax_rates
        ]
        default_tax_val = str(default_tax.id) if default_tax else ""

        br_opts   = [(str(b.id), b.name) for b in branches]
        cust_opts = [("", "— Pilih Pelanggan —")] + [(str(c.id), c.name) for c in customers]
        prod_opts = [(str(p.id), f"{p.code} — {p.name}") for p in products]
        uom_opts  = [(str(u.id), u.code) for u in uoms]
        sales_opts= [("", "— Tidak Ada —")] + [(str(u.id), u.full_name) for u in sales_users]
        prod_map  = {
            str(p.id): {
                "uom_id": str(p.uom_id),
                "price":  p.sale_price or 0,
            } for p in products
        }

    dlg_ref  = {"dlg": None}
    f_branch = make_dropdown("Cabang *", br_opts,
                             str(_user_branch) if _user_branch else "", disabled=bool(_user_branch))
    f_wh     = make_dropdown("Gudang", [("", "— Pilih cabang dulu —")], "")
    f_cust   = make_dropdown("Pelanggan *", cust_opts, "")
    f_sales  = make_dropdown("Sales", sales_opts, "")
    f_tax_rate = make_dropdown("Tarif Pajak", tax_opts, default_tax_val, width=220)
    f_date   = make_field("Tgl Order *", date.today().strftime("%Y-%m-%d"),
                          hint="YYYY-MM-DD", width=160)
    f_exp    = make_field("Est. Pengiriman", "", hint="YYYY-MM-DD", width=160)
    f_ship_method = make_field("Metode Kirim", "", width=160)
    f_ship_addr   = make_field("Alamat Kirim", "", multiline=True, min_lines=2, max_lines=3)
    f_ship_city   = make_field("Kota Tujuan", "", width=200)
    f_notes       = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=3)
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    # Build tax rate map untuk lookup rate dari id
    tax_rate_map = {str(tr.id): tr.rate for tr in tax_rates}

    def _filter_wh(branch_id):
        opts = wh_by_branch.get(branch_id, [])
        f_wh.options = [ft.dropdown.Option(key=v, text=t)
                        for v, t in (opts or [("", "— Tidak ada gudang —")])]
        f_wh.value = opts[0][0] if len(opts) == 1 else None
        try: f_wh.update()
        except: pass

    def on_tax_rate_select(e):
        """Saat tarif pajak dipilih, terapkan ke semua baris."""
        tid = f_tax_rate.value or ""
        rate = tax_rate_map.get(tid, 0.0)
        for rd in line_editor.rows:
            rd["tax"].value = str(rate)
            try: rd["tax"].update()
            except: pass
        line_editor._update_summary()

    f_branch.on_select    = lambda e: _filter_wh(f_branch.value or "")
    f_tax_rate.on_select  = on_tax_rate_select
    if _user_branch:
        _filter_wh(str(_user_branch))
    # Terapkan default tax ke baris pertama saat form dibuka
    if default_tax_val and default_tax:
        pass  # akan diterapkan setelah line_editor dibuat

    line_editor = SOLineEditor(prod_opts, uom_opts, prod_map, dlg_ref)
    line_editor._add_row()
    # Terapkan default tarif pajak ke baris pertama
    if default_tax:
        for rd in line_editor.rows:
            rd["tax"].value = str(default_tax.rate)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_branch.value: show_err("Cabang wajib dipilih."); return
        if not f_cust.value:   show_err("Pelanggan wajib dipilih."); return

        ok_l, msg_l, lines = line_editor.validate_and_collect()
        if not ok_l: show_err(msg_l); return

        data = {
            "branch_id":       f_branch.value,
            "customer_id":     f_cust.value,
            "sales_user_id":   f_sales.value or None,
            "warehouse_id":    f_wh.value or None,
            "tax_rate_id":     f_tax_rate.value or None,
            "order_date":      f_date.value,
            "expected_delivery": f_exp.value,
            "shipping_method": f_ship_method.value,
            "shipping_address":f_ship_addr.value,
            "shipping_city":   f_ship_city.value,
            "notes":           f_notes.value,
        }
        with SessionLocal() as db:
            ok, msg = SalesOrderService.create(db, session.company_id, session.user_id, data, lines)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.SHOPPING_BAG, color=Colors.ACCENT, size=20),
                    ft.Text("Buat Sales Order", color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=960, height=560,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
                err,
                section_card("Informasi SO", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":4}, content=f_branch),
                        ft.Container(col={"xs":12,"sm":4}, content=f_cust),
                        ft.Container(col={"xs":12,"sm":4}, content=f_sales),
                    ]),
                    ft.Row(spacing=12, wrap=True, controls=[
                        f_date, f_wh, f_ship_method, f_tax_rate,
                    ]),
                    ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.05, Colors.ACCENT),
                        border_radius=4, padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        content=ft.Row(spacing=6, controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=Colors.ACCENT),
                            ft.Text(
                                "Tarif pajak akan diterapkan otomatis ke semua item. "
                                "Bisa diubah per-baris di kolom PPN%.",
                                size=11, color=Colors.ACCENT,
                            ),
                        ]),
                    ),
                ]),
                section_card("Pengiriman", [
                    ft.Row(spacing=12, controls=[f_ship_city, f_exp]),
                    f_ship_addr,
                ]),
                section_card("Item Pesanan", [
                    line_editor.col,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.TextButton(
                                content=ft.Row(tight=True, spacing=6, controls=[
                                    ft.Icon(ft.Icons.ADD, size=16, color=Colors.ACCENT),
                                    ft.Text("Tambah Item", size=13, color=Colors.ACCENT),
                                ]),
                                on_click=lambda e: line_editor._add_row(),
                            ),
                            line_editor.summary_text,
                        ],
                    ),
                ]),
                f_notes,
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
# TABLE
# ─────────────────────────────────────────────────────────────
def _sos_to_dicts(sos) -> List[Dict]:
    return [{
        "id":            so.id,
        "number":        so.so_number,
        "status":        so.status,
        "payment_status":so.payment_status,
        "customer":      so.customer.name if so.customer else "—",
        "branch":        so.branch.name   if so.branch   else "—",
        "date":          _fmt_date(so.order_date),
        "total":         so.total_amount or 0,
        "item_count":    len(so.lines or []),
    } for so in sos]


def _build_rows(data, page, session, refresh):
    rows = []
    for d in data:
        actions = []
        if d["status"] == "DRAFT":
            actions.append(action_btn(
                ft.Icons.CHECK_CIRCLE_OUTLINE, "Konfirmasi",
                lambda e, sid=d["id"], n=d["number"]: confirm_dialog(
                    page, "Konfirmasi SO", f"Konfirmasi {n}?",
                    lambda: _confirm(sid, page, session, refresh),
                    "Ya, Konfirmasi", Colors.SUCCESS),
                Colors.SUCCESS))
            actions.append(action_btn(
                ft.Icons.CANCEL_OUTLINED, "Batalkan",
                lambda e, sid=d["id"], n=d["number"]: confirm_dialog(
                    page, "Batalkan SO", f"Batalkan {n}?",
                    lambda: _cancel(sid, page, refresh),
                    "Ya, Batalkan", Colors.WARNING),
                Colors.WARNING))

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["number"], size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY, font_family="monospace"),
                ft.Text(d["date"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["customer"], size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["branch"],   size=12, color=Colors.TEXT_MUTED)),
            ft.DataCell(ft.Text(f"{d['item_count']} item", size=12)),
            ft.DataCell(ft.Text(f"Rp {_fmt(d['total'])}", size=12,
                                color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_500)),
            ft.DataCell(_badge(d["status"])),
            ft.DataCell(_badge(d["payment_status"], _PAY_COLOR,
                               {"UNPAID":"Belum Bayar","PARTIAL":"Sebagian",
                                "PAID":"Lunas","REFUNDED":"Refund"})),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def _confirm(sid, page, session, refresh):
    with SessionLocal() as db:
        ok, msg = SalesOrderService.confirm(db, sid, session.user_id)
    show_snack(page, msg, ok)
    if ok: refresh()


def _cancel(sid, page, refresh):
    with SessionLocal() as db:
        ok, msg = SalesOrderService.cancel(db, sid)
    show_snack(page, msg, ok)
    if ok: refresh()


def SalesOrderPage(page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}
    status_val = {"v": ""}
    filter_area = ft.Container()

    def _load():
        with SessionLocal() as db:
            sos = SalesOrderService.get_all(
                db, session.company_id, search_val["q"], status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _sos_to_dicts(sos)

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("No. SO",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Pelanggan",   size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Total",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Pembayaran",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
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
        controls=[table if initial else empty_state("Belum ada Sales Order.")],
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
        table_area.controls = [table if data else empty_state("Tidak ada SO ditemukan.")]
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
            page_header("Sales Order", "Kelola pesanan penjualan",
                        "Buat SO", on_action=lambda: _form_dialog(page, session, refresh),
                        action_icon=ft.Icons.ADD),
            ft.Container(padding=ft.Padding.only(bottom=12), content=filter_area),
            ft.Row(controls=[search_bar("Cari nomor SO atau pelanggan...", on_search)]),
            ft.Container(height=12),
            ft.Container(expand=True,
                         content=ft.ListView(expand=True, controls=[table_area])),
        ]),
    )
