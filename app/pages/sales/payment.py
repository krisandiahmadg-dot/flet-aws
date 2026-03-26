"""
app/pages/sales/payment.py
Pembayaran — daftar semua penerimaan, catat bayar baru,
ringkasan per metode pembayaran.
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import Branch, Invoice, Customer
from app.services.sales_service import (
    InvoiceService, PaymentService,
)
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn, page_header,
    search_bar, confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_METHOD_OPTS = [
    ("BANK_TRANSFER", "Transfer Bank"),
    ("CASH",          "Tunai"),
    ("CREDIT_CARD",   "Kartu Kredit"),
    ("CHEQUE",        "Cek / Giro"),
    ("OTHER",         "Lainnya"),
]
_METHOD_COLOR = {
    "BANK_TRANSFER": Colors.INFO,
    "CASH":          Colors.SUCCESS,
    "CREDIT_CARD":   Colors.ACCENT,
    "CHEQUE":        Colors.WARNING,
    "OTHER":         Colors.TEXT_MUTED,
}
_METHOD_ICON = {
    "BANK_TRANSFER": ft.Icons.ACCOUNT_BALANCE,
    "CASH":          ft.Icons.PAYMENTS,
    "CREDIT_CARD":   ft.Icons.CREDIT_CARD,
    "CHEQUE":        ft.Icons.DESCRIPTION,
    "OTHER":         ft.Icons.MORE_HORIZ,
}


def _method_badge(method: str) -> ft.Container:
    color = _METHOD_COLOR.get(method, Colors.TEXT_MUTED)
    label = dict(_METHOD_OPTS).get(method, method)
    icon  = _METHOD_ICON.get(method, ft.Icons.PAYMENTS)
    return ft.Container(
        content=ft.Row(tight=True, spacing=4, controls=[
            ft.Icon(icon, size=12, color=color),
            ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        ]),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _fmt(n, dec=0): return f"{n:,.{dec}f}" if n else "0"
def _fmt_date(d):
    if not d: return ""
    try: return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
    except: return ""

def _parse_date(val) -> Optional[date]:
    if not (val or "").strip(): return None
    try: return date.fromisoformat(val.strip())
    except: return None


# ─────────────────────────────────────────────────────────────
# CATAT PEMBAYARAN BARU (dari daftar invoice belum lunas)
# ─────────────────────────────────────────────────────────────
def _new_payment_dialog(page, session: AppSession, on_saved,
                         preselect_inv_id: Optional[int] = None):
    _user_branch = getattr(session, "branch_id", None)

    with SessionLocal() as db:
        # Invoice belum lunas
        unpaid_invs = db.query(Invoice).filter(
            Invoice.company_id == session.company_id,
            Invoice.status.in_(["SENT", "PARTIAL", "OVERDUE"]),
        ).options(
            __import__('sqlalchemy.orm', fromlist=['joinedload'])
            .joinedload(Invoice.customer)
        ).order_by(Invoice.invoice_date.desc()).all()

        if _user_branch:
            unpaid_invs = [i for i in unpaid_invs if i.branch_id == _user_branch]

        inv_opts = [("", "— Pilih Invoice —")] + [
            (str(inv.id),
             f"{inv.invoice_number}  —  "
             f"{inv.customer.name if inv.customer else '?'}"
             f"  —  Sisa Rp {(inv.total_amount - inv.paid_amount):,.0f}")
            for inv in unpaid_invs
        ]
        inv_map = {
            str(inv.id): {
                "total":       inv.total_amount,
                "paid":        inv.paid_amount,
                "outstanding": inv.total_amount - inv.paid_amount,
                "customer":    inv.customer.name if inv.customer else "—",
                "inv_number":  inv.invoice_number,
            }
            for inv in unpaid_invs
        }

    if not unpaid_invs:
        show_snack(page, "Tidak ada invoice yang menunggu pembayaran.", False)
        return

    default_inv = str(preselect_inv_id) if preselect_inv_id else ""

    f_inv    = make_dropdown("Invoice *", inv_opts, default_inv)
    f_amount = make_field("Jumlah Bayar *", "",
                          keyboard_type=ft.KeyboardType.NUMBER, width=200)
    f_method = make_dropdown("Metode Bayar *", _METHOD_OPTS, "BANK_TRANSFER")
    f_ref    = make_field("No. Referensi / Bukti", "",
                          hint="No. transfer, no. cek, dll", width=230)
    f_date   = make_field("Tanggal Bayar *", date.today().strftime("%Y-%m-%d"),
                          hint="YYYY-MM-DD", width=160)
    f_notes  = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=2)
    err      = ft.Text("", color=Colors.ERROR, size=12, visible=False)
    dlg_ref  = {"dlg": None}

    # Info card yang update saat invoice dipilih
    info_card = ft.Container(
        visible=False,
        bgcolor=ft.Colors.with_opacity(0.05, Colors.ACCENT),
        border_radius=6,
        padding=ft.Padding.all(12),
        content=ft.Row(spacing=20, controls=[]),
    )

    def _update_info():
        inv_id = f_inv.value or ""
        if inv_id not in inv_map:
            info_card.visible = False
            try: info_card.update()
            except: pass
            return
        d = inv_map[inv_id]
        info_card.visible = True
        info_card.content = ft.Row(spacing=20, wrap=True, controls=[
            ft.Column(spacing=2, tight=True, controls=[
                ft.Text("Pelanggan", size=10, color=Colors.TEXT_MUTED),
                ft.Text(d["customer"], size=13, color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_600),
            ]),
            ft.Column(spacing=2, tight=True, controls=[
                ft.Text("Total Invoice", size=10, color=Colors.TEXT_MUTED),
                ft.Text(f"Rp {_fmt(d['total'])}", size=13, color=Colors.TEXT_SECONDARY),
            ]),
            ft.Column(spacing=2, tight=True, controls=[
                ft.Text("Sudah Dibayar", size=10, color=Colors.TEXT_MUTED),
                ft.Text(f"Rp {_fmt(d['paid'])}", size=13, color=Colors.SUCCESS),
            ]),
            ft.Column(spacing=2, tight=True, controls=[
                ft.Text("Sisa Tagihan", size=10, color=Colors.TEXT_MUTED),
                ft.Text(f"Rp {_fmt(d['outstanding'])}", size=14,
                        color=Colors.ERROR, weight=ft.FontWeight.W_700),
            ]),
        ])
        # Auto-fill jumlah = sisa tagihan
        if not f_amount.value or float(f_amount.value or 0) == 0:
            f_amount.value = str(int(d["outstanding"]))
        try:
            info_card.update()
            f_amount.update()
        except: pass

    def on_inv_select(e):
        _update_info()

    f_inv.on_select = on_inv_select

    # Auto-update info jika preselect
    if default_inv and default_inv in inv_map:
        f_amount.value = str(int(inv_map[default_inv]["outstanding"]))

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_inv.value: show_err("Invoice wajib dipilih."); return
        try:
            amt = float(f_amount.value or 0)
        except ValueError:
            show_err("Jumlah tidak valid."); return
        if amt <= 0:
            show_err("Jumlah harus > 0."); return

        inv_id = f_inv.value
        if inv_id in inv_map:
            outstanding = inv_map[inv_id]["outstanding"]
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
            ok, msg = InvoiceService.add_payment(
                db, int(f_inv.value), session.user_id, data)

        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.PAYMENTS, color=Colors.SUCCESS, size=20),
                    ft.Text("Catat Pembayaran", color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=580,
            content=ft.Column(spacing=14, tight=True, controls=[
                err,
                f_inv,
                info_card,
                section_card("Detail Pembayaran", [
                    ft.Row(spacing=12, controls=[f_amount, f_date]),
                    ft.Row(spacing=12, controls=[f_method, f_ref]),
                    f_notes,
                ]),
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
    page.overlay.append(dlg)
    dlg_ref["dlg"] = dlg
    dlg.open = True
    # Trigger info card jika preselect
    if default_inv:
        _update_info()
    page.update()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def PaymentPage(page, session: AppSession) -> ft.Control:
    _user_branch = getattr(session, "branch_id", None)

    search_val = {"q": ""}
    filter_state = {
        "method":    "",
        "date_from": (date.today() - timedelta(days=30)).strftime("%Y-%m-%d"),
        "date_to":   date.today().strftime("%Y-%m-%d"),
    }

    def _load() -> List[Dict]:
        with SessionLocal() as db:
            pays = PaymentService.get_all(
                db, session.company_id,
                search=search_val["q"],
                method=filter_state["method"],
                date_from=_parse_date(filter_state["date_from"]),
                date_to=_parse_date(filter_state["date_to"]),
                branch_id=_user_branch,
            )
            return [{
                "id":         p.id,
                "number":     p.payment_number,
                "date":       _fmt_date(p.payment_date),
                "method":     p.payment_method,
                "amount":     p.amount,
                "inv_number": p.invoice.invoice_number if p.invoice else "—",
                "customer":   (p.invoice.customer.name
                               if (p.invoice and p.invoice.customer) else "—"),
                "so_number":  (p.invoice.so.so_number
                               if (p.invoice and p.invoice.so) else "—"),
                "reference":  p.reference_number or "—",
                "notes":      p.notes or "",
                "branch":     p.branch.name if p.branch else "—",
            } for p in pays]

    def _load_summary() -> Dict:
        with SessionLocal() as db:
            return PaymentService.get_summary(
                db, session.company_id,
                date_from=_parse_date(filter_state["date_from"]),
                date_to=_parse_date(filter_state["date_to"]),
                branch_id=_user_branch,
            )

    initial      = _load()
    init_summary = _load_summary()

    # ── Summary cards ─────────────────────────────────────────
    def _build_summary(s: Dict) -> ft.Row:
        method_labels = dict(_METHOD_OPTS)
        method_ctrls  = []
        for method, total in s.get("by_method", {}).items():
            color = _METHOD_COLOR.get(method, Colors.TEXT_MUTED)
            icon  = _METHOD_ICON.get(method, ft.Icons.PAYMENTS)
            method_ctrls.append(ft.Container(
                expand=True,
                bgcolor=Colors.BG_CARD,
                border_radius=Sizes.CARD_RADIUS,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, color)),
                padding=ft.Padding.all(12),
                content=ft.Column(spacing=4, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Icon(icon, size=14, color=color),
                        ft.Text(method_labels.get(method, method),
                                size=11, color=color),
                    ]),
                    ft.Text(f"Rp {_fmt(total)}", size=16,
                            weight=ft.FontWeight.W_700, color=Colors.TEXT_PRIMARY),
                ]),
            ))

        total_card = ft.Container(
            expand=True,
            bgcolor=Colors.BG_CARD,
            border_radius=Sizes.CARD_RADIUS,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.4, Colors.SUCCESS)),
            padding=ft.Padding.all(14),
            content=ft.Column(spacing=4, controls=[
                ft.Text("Total Diterima", size=11, color=Colors.TEXT_MUTED),
                ft.Text(f"Rp {_fmt(s.get('total', 0))}", size=22,
                        weight=ft.FontWeight.W_700, color=Colors.SUCCESS),
                ft.Text(f"{s.get('count', 0)} transaksi",
                        size=11, color=Colors.TEXT_MUTED),
            ]),
        )

        return ft.Row(spacing=12, wrap=True,
                      controls=[total_card] + method_ctrls)

    summary_container = ft.Container(content=_build_summary(init_summary))

    # ── Table ─────────────────────────────────────────────────
    def _build_rows(data, refresh):
        rows = []
        for d in data:
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(d["number"], size=12, weight=ft.FontWeight.W_700,
                            color=Colors.TEXT_PRIMARY, font_family="monospace"),
                    ft.Text(d["date"], size=11, color=Colors.TEXT_MUTED),
                ])),
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(d["customer"], size=13, color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_500),
                    ft.Text(d["so_number"], size=11, color=Colors.TEXT_MUTED,
                            font_family="monospace"),
                ])),
                ft.DataCell(ft.Text(d["inv_number"], size=12, color=Colors.ACCENT,
                                    font_family="monospace")),
                ft.DataCell(_method_badge(d["method"])),
                ft.DataCell(ft.Text(d["reference"], size=12, color=Colors.TEXT_MUTED,
                                    font_family="monospace")),
                ft.DataCell(ft.Text(
                    f"Rp {_fmt(d['amount'])}", size=14,
                    weight=ft.FontWeight.W_700, color=Colors.SUCCESS,
                )),
                ft.DataCell(ft.Text(d["branch"], size=11, color=Colors.TEXT_MUTED)),
                ft.DataCell(ft.Row(spacing=0, controls=[
                    action_btn(
                        ft.Icons.CANCEL_OUTLINED, "Batalkan",
                        lambda e, pid=d["id"], n=d["number"]: confirm_dialog(
                            page, "Batalkan Pembayaran",
                            f"Batalkan {n}? Ini akan mengurangi paid_amount invoice.",
                            lambda: _void(pid, page, refresh),
                            "Ya, Batalkan", Colors.ERROR),
                        Colors.ERROR,
                    ),
                ])),
            ]))
        return rows

    COLS = [
        ft.DataColumn(ft.Text("No. Bayar",   size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Pelanggan",   size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Invoice",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Metode",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Referensi",   size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Jumlah",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=58, column_spacing=16,
        columns=COLS,
        rows=_build_rows(initial, lambda: None),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada pembayaran.")],
        scroll=ft.ScrollMode.AUTO,
    )

    # ── Filter ────────────────────────────────────────────────
    method_filter_opts = [("", "Semua Metode")] + _METHOD_OPTS
    f_method_filter = make_dropdown("Metode", method_filter_opts, "", width=180)
    f_date_from     = make_field("Dari", filter_state["date_from"],
                                 hint="YYYY-MM-DD", width=145)
    f_date_to       = make_field("Sampai", filter_state["date_to"],
                                 hint="YYYY-MM-DD", width=145)

    def refresh():
        data = _load()
        summ = _load_summary()
        table.rows = _build_rows(data, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada pembayaran.")]
        summary_container.content = _build_summary(summ)
        try:
            table_area.update()
            summary_container.update()
        except: pass

    def on_filter(e=None):
        filter_state["method"]    = f_method_filter.value or ""
        filter_state["date_from"] = f_date_from.value or ""
        filter_state["date_to"]   = f_date_to.value   or ""
        refresh()

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    f_method_filter.on_select = on_filter
    f_date_from.on_change     = on_filter
    f_date_to.on_change       = on_filter

    def _void(pid, page, refresh):
        with SessionLocal() as db:
            ok, msg = PaymentService.void(db, pid, session.user_id)
        show_snack(page, msg, ok)
        if ok: refresh()

    table.rows = _build_rows(initial, refresh)

    filter_panel = ft.Container(
        bgcolor=Colors.BG_CARD,
        border_radius=Sizes.CARD_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.all(14),
        content=ft.Row(spacing=12, wrap=True, controls=[
            search_bar("Cari no. bayar / referensi...", on_search),
            f_method_filter,
            f_date_from,
            ft.Text("s/d", size=12, color=Colors.TEXT_MUTED),
            f_date_to,
            ft.TextButton("30 Hari", style=ft.ButtonStyle(color=Colors.TEXT_MUTED),
                on_click=lambda e: (
                    setattr(f_date_from, "value",
                            (date.today()-timedelta(days=30)).strftime("%Y-%m-%d")),
                    setattr(f_date_to, "value", date.today().strftime("%Y-%m-%d")),
                    on_filter(), f_date_from.update(), f_date_to.update(),
                )),
            ft.TextButton("Bulan Ini", style=ft.ButtonStyle(color=Colors.TEXT_MUTED),
                on_click=lambda e: (
                    setattr(f_date_from, "value",
                            date.today().strftime("%Y-%m-01")),
                    setattr(f_date_to, "value", date.today().strftime("%Y-%m-%d")),
                    on_filter(), f_date_from.update(), f_date_to.update(),
                )),
        ]),
    )

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK, padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=12, controls=[
            page_header(
                "Pembayaran",
                "Riwayat penerimaan pembayaran dari pelanggan",
                "Catat Pembayaran",
                on_action=lambda: _new_payment_dialog(page, session, refresh),
                action_icon=ft.Icons.ADD,
            ),
            summary_container,
            filter_panel,
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[table_area]),
            ),
        ]),
    )
