"""
app/pages/sales/invoice.py
Invoice & Pembayaran
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import Branch, Customer, SalesOrder
from app.services.sales_service import SalesOrderService, InvoiceService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn, page_header,
    search_bar, confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS = [
    ("DRAFT",   "Draft"),
    ("SENT",    "Dikirim"),
    ("PARTIAL", "Sebagian Bayar"),
    ("PAID",    "Lunas"),
    ("OVERDUE", "Jatuh Tempo"),
    ("CANCELLED","Dibatalkan"),
]
_STATUS_COLOR = {
    "DRAFT":    Colors.TEXT_MUTED,
    "SENT":     Colors.INFO,
    "PARTIAL":  Colors.WARNING,
    "PAID":     Colors.SUCCESS,
    "OVERDUE":  Colors.ERROR,
    "CANCELLED":Colors.ERROR,
}
_PAY_METHOD_OPTS = [
    ("BANK_TRANSFER", "Transfer Bank"),
    ("CASH",          "Tunai"),
    ("CREDIT_CARD",   "Kartu Kredit"),
    ("CHEQUE",        "Cek"),
    ("OTHER",         "Lainnya"),
]


def _badge(status):
    color = _STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    label = dict(_STATUS_OPTS).get(status, status)
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
# PAYMENT DIALOG
# ─────────────────────────────────────────────────────────────
def _payment_dialog(page, session: AppSession,
                    inv_id: int, inv_number: str,
                    total: float, paid: float, on_saved):
    outstanding = total - paid
    f_amount  = make_field("Jumlah Bayar *", str(int(outstanding)),
                           keyboard_type=ft.KeyboardType.NUMBER, width=200)
    f_method  = make_dropdown("Metode *", _PAY_METHOD_OPTS, "BANK_TRANSFER")
    f_ref     = make_field("No. Referensi / Bukti Transfer", "", width=220)
    f_date    = make_field("Tgl Bayar *", date.today().strftime("%Y-%m-%d"),
                           hint="YYYY-MM-DD", width=160)
    f_notes   = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=2)
    err       = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        try:
            amt = float(f_amount.value or 0)
        except ValueError:
            show_err("Jumlah tidak valid."); return
        if amt <= 0:
            show_err("Jumlah harus > 0."); return
        if amt > outstanding + 0.01:
            show_err(f"Melebihi sisa tagihan Rp {outstanding:,.0f}."); return

        data = {
            "amount":           amt,
            "payment_method":   f_method.value,
            "reference_number": f_ref.value.strip() or None,
            "payment_date":     f_date.value,
            "notes":            f_notes.value.strip() or None,
        }
        with SessionLocal() as db:
            ok, msg = InvoiceService.add_payment(db, inv_id, session.user_id, data)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=4, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.PAYMENTS, color=Colors.SUCCESS, size=20),
                        ft.Text(f"Catat Pembayaran — {inv_number}",
                                color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                    ]),
                    ft.Row(spacing=16, controls=[
                        ft.Text(f"Total: Rp {_fmt(total)}", size=12,
                                color=Colors.TEXT_SECONDARY),
                        ft.Text(f"Sudah Bayar: Rp {_fmt(paid)}", size=12,
                                color=Colors.SUCCESS),
                        ft.Text(f"Sisa: Rp {_fmt(outstanding)}", size=12,
                                color=Colors.ERROR, weight=ft.FontWeight.W_600),
                    ]),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=520,
            content=ft.Column(spacing=12, tight=True, controls=[
                err,
                ft.Row(spacing=12, controls=[f_amount, f_date]),
                ft.Row(spacing=12, controls=[f_method, f_ref]),
                f_notes,
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Simpan Pembayaran", bgcolor=Colors.SUCCESS,
                color=ft.Colors.WHITE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


# ─────────────────────────────────────────────────────────────
# FORM DIALOG — Buat Invoice dari SO
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession, on_saved):
    _user_branch = getattr(session, "branch_id", None)

    with SessionLocal() as db:
        invoiceable = SalesOrderService.get_invoiceable_sos(
            db, session.company_id, branch_id=_user_branch)
        so_opts = [("", "— Pilih SO —")] + [
            (str(so.id),
             f"{so.so_number} — {so.customer.name if so.customer else '?'}"
             f" — Rp {so.total_amount:,.0f}")
            for so in invoiceable
        ]
        so_map = {str(so.id): so.total_amount for so in invoiceable}

    if not invoiceable:
        show_snack(page, "Tidak ada SO yang siap diinvoice.", False)
        return

    f_so      = make_dropdown("Sales Order *", so_opts, "")
    f_total   = make_field("Total (Rp)", "0", read_only=True, width=200)
    f_date    = make_field("Tgl Invoice *", date.today().strftime("%Y-%m-%d"),
                           hint="YYYY-MM-DD", width=160)
    f_due     = make_field("Tgl Jatuh Tempo",
                           (date.today() + timedelta(days=30)).strftime("%Y-%m-%d"),
                           hint="YYYY-MM-DD", width=160)
    f_notes   = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=3)
    err       = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def on_so_select(e):
        so_id = f_so.value or ""
        if so_id in so_map:
            f_total.value = str(int(so_map[so_id]))
            try: f_total.update()
            except: pass

    f_so.on_select = on_so_select

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_so.value: show_err("SO wajib dipilih."); return
        data = {
            "so_id":        f_so.value,
            "branch_id":    _user_branch or "",
            "invoice_date": f_date.value,
            "due_date":     f_due.value,
            "notes":        f_notes.value,
        }
        with SessionLocal() as db:
            # Ambil branch dari SO jika user adalah HQ
            if not data["branch_id"]:
                so = db.query(SalesOrder).filter_by(id=int(f_so.value)).first()
                if so: data["branch_id"] = str(so.branch_id)
            ok, msg = InvoiceService.create_from_so(
                db, session.company_id, session.user_id, data)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.RECEIPT, color=Colors.ACCENT, size=20),
                    ft.Text("Buat Invoice", color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=560,
            content=ft.Column(spacing=14, tight=True, controls=[
                err,
                section_card("Sumber SO", [
                    f_so,
                    ft.Row(spacing=12, controls=[f_total]),
                ]),
                section_card("Tanggal", [
                    ft.Row(spacing=12, controls=[f_date, f_due]),
                ]),
                f_notes,
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Buat Invoice", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


# ─────────────────────────────────────────────────────────────
# TABLE + PAGE
# ─────────────────────────────────────────────────────────────
def _invs_to_dicts(invs) -> List[Dict]:
    return [{
        "id":             inv.id,
        "number":         inv.invoice_number,
        "status":         inv.status,
        "customer":       inv.customer.name if inv.customer else "—",
        "so_number":      inv.so.so_number  if inv.so       else "—",
        "branch":         inv.branch.name   if inv.branch   else "—",
        "date":           _fmt_date(inv.invoice_date),
        "due_date":       _fmt_date(inv.due_date),
        "total":          inv.total_amount  or 0,
        "paid":           inv.paid_amount   or 0,
        "outstanding":    (inv.total_amount or 0) - (inv.paid_amount or 0),
    } for inv in invs]


def _build_rows(data, page, session, refresh):
    rows = []
    for d in data:
        actions = []
        outstanding = d["outstanding"]

        if d["status"] == "DRAFT":
            actions.append(action_btn(
                ft.Icons.SEND, "Kirim Invoice",
                lambda e, iid=d["id"], n=d["number"]: confirm_dialog(
                    page, "Kirim Invoice", f"Kirim {n} ke pelanggan?",
                    lambda: _send(iid, page, refresh),
                    "Ya, Kirim", Colors.INFO),
                Colors.INFO))
            actions.append(action_btn(
                ft.Icons.CANCEL_OUTLINED, "Batalkan",
                lambda e, iid=d["id"], n=d["number"]: confirm_dialog(
                    page, "Batalkan Invoice", f"Batalkan {n}?",
                    lambda: _cancel(iid, page, refresh),
                    "Ya, Batalkan", Colors.WARNING),
                Colors.WARNING))

        if d["status"] in ("SENT", "PARTIAL") and outstanding > 0.01:
            actions.append(action_btn(
                ft.Icons.PAYMENTS, "Catat Bayar",
                lambda e, iid=d["id"], n=d["number"],
                       tot=d["total"], paid=d["paid"]:
                    _payment_dialog(page, session, iid, n, tot, paid, refresh),
                Colors.SUCCESS))

        outstanding_color = (Colors.ERROR   if outstanding > 0.01 else
                             Colors.SUCCESS if outstanding <= 0    else Colors.TEXT_MUTED)

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["number"], size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY, font_family="monospace"),
                ft.Text(d["date"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["customer"],  size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["so_number"], size=12, color=Colors.ACCENT,
                                font_family="monospace")),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"Rp {_fmt(d['total'])}", size=13,
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_500),
                ft.Text(f"Bayar: Rp {_fmt(d['paid'])}", size=11, color=Colors.SUCCESS),
            ])),
            ft.DataCell(ft.Text(
                f"Rp {_fmt(outstanding)}", size=13,
                color=outstanding_color, weight=ft.FontWeight.W_600)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"JT: {d['due_date']}", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(_badge(d["status"])),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def _send(iid, page, refresh):
    with SessionLocal() as db:
        ok, msg = InvoiceService.send(db, iid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _cancel(iid, page, refresh):
    with SessionLocal() as db:
        ok, msg = InvoiceService.cancel(db, iid)
    show_snack(page, msg, ok)
    if ok: refresh()


def InvoicePage(page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}
    status_val = {"v": ""}
    filter_area = ft.Container()

    def _load():
        with SessionLocal() as db:
            invs = InvoiceService.get_all(
                db, session.company_id, search_val["q"], status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _invs_to_dicts(invs)

    initial = _load()

    # Summary cards
    def _summary():
        data = _load()
        total_inv  = sum(d["total"]       for d in data)
        total_paid = sum(d["paid"]        for d in data)
        total_out  = sum(d["outstanding"] for d in data)
        return ft.Row(spacing=12, controls=[
            _stat("Total Invoice",    f"Rp {_fmt(total_inv)}"),
            _stat("Sudah Diterima",   f"Rp {_fmt(total_paid)}", Colors.SUCCESS),
            _stat("Belum Dibayar",    f"Rp {_fmt(total_out)}",  Colors.ERROR),
            _stat("Jml Invoice",      str(len(data))),
        ])

    def _stat(label, val, color=None):
        return ft.Container(
            expand=True, bgcolor=Colors.BG_CARD,
            border_radius=Sizes.CARD_RADIUS,
            border=ft.Border.all(1, Colors.BORDER),
            padding=ft.Padding.all(14),
            content=ft.Column(spacing=2, controls=[
                ft.Text(label, size=11, color=Colors.TEXT_MUTED),
                ft.Text(val, size=18, weight=ft.FontWeight.W_700,
                        color=color or Colors.TEXT_PRIMARY),
            ]),
        )

    summary_container = ft.Container(content=_summary())

    COLS = [
        ft.DataColumn(ft.Text("No. Invoice",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Pelanggan",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("SO Ref",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Total / Bayar",size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Sisa",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Jatuh Tempo",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=64, column_spacing=16,
        columns=COLS, rows=_build_rows(initial, page, session, lambda: None),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada invoice.")],
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
        table_area.controls = [table if data else empty_state("Tidak ada invoice ditemukan.")]
        filter_area.content = _filter_bar()
        summary_container.content = _summary()
        try:
            table_area.update()
            filter_area.update()
            summary_container.update()
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
        content=ft.Column(expand=True, spacing=12, controls=[
            page_header("Invoice", "Kelola invoice dan pembayaran pelanggan",
                        "Buat Invoice", on_action=lambda: _form_dialog(page, session, refresh),
                        action_icon=ft.Icons.ADD),
            summary_container,
            ft.Container(padding=ft.Padding.only(bottom=4), content=filter_area),
            ft.Row(controls=[search_bar("Cari nomor invoice atau pelanggan...", on_search)]),
            ft.Container(expand=True,
                         content=ft.ListView(expand=True, controls=[table_area])),
        ]),
    )
