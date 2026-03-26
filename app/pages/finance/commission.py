"""
app/pages/commission/commission.py
Halaman Komisi Referral

Tab:
  1. Skema Komisi   — setup skema per partner/customer
  2. Transaksi      — daftar komisi yang sudah di-generate
  3. Pembayaran     — bayar komisi batch ke partner
"""
from __future__ import annotations
import flet as ft
from typing import Optional, List, Dict
from datetime import date
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import (
    CommissionScheme, CommissionTransaction, CommissionPayment,
    Partner, Customer,
)
from app.services.commission_service import (
    CommissionSchemeService,
    CommissionTransactionService,
    CommissionPaymentService,
)
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    page_header, search_bar, confirm_dialog,
    show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

# ── Konstanta ─────────────────────────────────────────────────
_TYPE_OPTS = [
    ("PERCENTAGE",  "Persentase dari SO (%)"),
    ("FLAT",        "Flat per Customer Baru (Rp)"),
    ("COMBINATION", "Kombinasi (% + Flat)"),
]
_APPLY_OPTS = [
    ("ALL_SO",         "Semua SO"),
    ("FIRST_SO_ONLY",  "Hanya SO Pertama Customer"),
    ("REPEAT_SO_ONLY", "Hanya SO Repeat"),
]
_FOR_OPTS = [
    ("PARTNER",           "Mitra / Partner"),
    ("CUSTOMER_REFERRAL", "Customer Referral"),
]
_TX_STATUS_OPTS = [
    ("PENDING",   "Menunggu Approval"),
    ("APPROVED",  "Disetujui"),
    ("PAID",      "Sudah Dibayar"),
    ("CANCELLED", "Dibatalkan"),
]
_TX_STATUS_COLOR = {
    "PENDING":   Colors.WARNING,
    "APPROVED":  Colors.INFO,
    "PAID":      Colors.SUCCESS,
    "CANCELLED": Colors.ERROR,
}
_PMT_METHOD_OPTS = [
    ("BANK_TRANSFER", "Transfer Bank"),
    ("CASH",          "Tunai"),
    ("OTHER",         "Lainnya"),
]


def _tx_badge(status: str) -> ft.Container:
    color = _TX_STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    label = dict(_TX_STATUS_OPTS).get(status, status)
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _fmt_date(d) -> str:
    if not d: return ""
    try: return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
    except: return ""


def _parse_date(val):
    if not (val or "").strip(): return None
    from datetime import datetime
    try: return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except: return None


# ─────────────────────────────────────────────────────────────
# TAB 1 — SKEMA KOMISI
# ─────────────────────────────────────────────────────────────
def _scheme_form_dialog(page, session: AppSession,
                        scheme_id: Optional[int], on_saved):
    is_edit = scheme_id is not None

    with SessionLocal() as db:
        partners  = db.query(Partner).filter_by(
            company_id=session.company_id, is_active=True).order_by(Partner.name).all()
        customers = db.query(Customer).filter_by(
            company_id=session.company_id, is_active=True).order_by(Customer.name).all()

        p_opts = [("", "— Default (semua partner) —")] + [
            (str(p.id), f"{p.code} — {p.name}") for p in partners]
        c_opts = [("", "— Default (semua customer referral) —")] + [
            (str(c.id), f"{c.code} — {c.name}") for c in customers]

        d = {}
        if is_edit:
            s = CommissionSchemeService.get_by_id(db, scheme_id)
            if s:
                d = {
                    "scheme_for":          s.scheme_for,
                    "partner_id":          str(s.partner_id) if s.partner_id else "",
                    "referring_customer_id": str(s.referring_customer_id) if s.referring_customer_id else "",
                    "name":                s.name,
                    "description":         s.description or "",
                    "commission_type":     s.commission_type,
                    "commission_pct":      str(s.commission_pct),
                    "max_commission_per_so": str(s.max_commission_per_so),
                    "flat_amount":         str(s.flat_amount),
                    "apply_on":            s.apply_on,
                    "min_so_amount":       str(s.min_so_amount),
                    "valid_from":          _fmt_date(s.valid_from),
                    "valid_until":         _fmt_date(s.valid_until),
                    "is_active":           s.is_active,
                }

    f_for   = make_dropdown("Untuk *", _FOR_OPTS, d.get("scheme_for", "PARTNER"))
    f_partner = make_dropdown("Partner", p_opts, d.get("partner_id", ""))
    f_cust  = make_dropdown("Customer Referral", c_opts,
                             d.get("referring_customer_id", ""))
    f_name  = make_field("Nama Skema *", d.get("name", ""))
    f_desc  = make_field("Deskripsi", d.get("description", ""),
                         multiline=True, min_lines=2, max_lines=3)
    f_type  = make_dropdown("Tipe Komisi *", _TYPE_OPTS,
                             d.get("commission_type", "PERCENTAGE"))
    f_pct   = make_field("% Komisi", d.get("commission_pct", "0"),
                          hint="misal: 5 = 5%",
                          keyboard_type=ft.KeyboardType.NUMBER, width=130)
    f_max   = make_field("Maks. Komisi/SO (Rp)", d.get("max_commission_per_so", "0"),
                          hint="0 = tidak ada batas",
                          keyboard_type=ft.KeyboardType.NUMBER, width=160)
    f_flat  = make_field("Flat/Customer Baru (Rp)", d.get("flat_amount", "0"),
                          keyboard_type=ft.KeyboardType.NUMBER, width=160)
    f_apply = make_dropdown("Berlaku Untuk *", _APPLY_OPTS,
                             d.get("apply_on", "ALL_SO"))
    f_min_so = make_field("Min. Nilai SO (Rp)", d.get("min_so_amount", "0"),
                           hint="0 = tidak ada minimum",
                           keyboard_type=ft.KeyboardType.NUMBER, width=160)
    f_vfrom = make_field("Berlaku Dari", d.get("valid_from", ""),
                          hint="YYYY-MM-DD", width=140)
    f_vuntil= make_field("Berlaku Sampai", d.get("valid_until", ""),
                          hint="YYYY-MM-DD", width=140)
    f_active = ft.Switch(label="Aktif", value=d.get("is_active", True),
                         active_color=Colors.ACCENT)

    # Visibility: partner vs customer_referral
    partner_row  = ft.Container(visible=True, content=f_partner)
    customer_row = ft.Container(visible=False, content=f_cust)
    pct_row  = ft.Container(visible=True, content=ft.Row(spacing=10, controls=[f_pct, f_max]))
    flat_row = ft.Container(visible=False, content=f_flat)

    def on_for_change(e):
        partner_row.visible  = f_for.value == "PARTNER"
        customer_row.visible = f_for.value == "CUSTOMER_REFERRAL"
        try: partner_row.update(); customer_row.update()
        except: pass

    def on_type_change(e):
        t = f_type.value
        pct_row.visible  = t in ("PERCENTAGE", "COMBINATION")
        flat_row.visible = t in ("FLAT", "COMBINATION")
        try: pct_row.update(); flat_row.update()
        except: pass

    f_for.on_change  = on_for_change
    f_type.on_change = on_type_change
    # Init visibility
    on_for_change(None)
    on_type_change(None)

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)
    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        show_err("")
        if not f_name.value.strip():
            show_err("Nama skema wajib diisi."); return
        data = {
            "scheme_for":          f_for.value,
            "partner_id":          f_partner.value or None,
            "referring_customer_id": f_cust.value or None,
            "name":                f_name.value.strip(),
            "description":         f_desc.value,
            "commission_type":     f_type.value,
            "commission_pct":      f_pct.value or "0",
            "max_commission_per_so": f_max.value or "0",
            "flat_amount":         f_flat.value or "0",
            "apply_on":            f_apply.value,
            "min_so_amount":       f_min_so.value or "0",
            "valid_from":          _parse_date(f_vfrom.value),
            "valid_until":         _parse_date(f_vuntil.value),
            "is_active":           f_active.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = CommissionSchemeService.update(db, scheme_id, data)
            else:
                ok, msg, _ = CommissionSchemeService.create(
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
                    ft.Icon(ft.Icons.PERCENT, color=Colors.ACCENT, size=20),
                    ft.Text("Edit Skema" if is_edit else "Buat Skema Komisi",
                            color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(
            width=560, height=540,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=12, controls=[
                err,
                section_card("Penerima Komisi", [
                    f_for, partner_row, customer_row,
                ]),
                section_card("Detail Skema", [
                    f_name, f_desc,
                    f_type,
                    pct_row,
                    flat_row,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_apply),
                        ft.Container(col={"xs":12,"sm":6}, content=f_min_so),
                    ]),
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_vfrom),
                        ft.Container(col={"xs":12,"sm":6}, content=f_vuntil),
                    ]),
                    f_active,
                ]),
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                      style=ft.ButtonStyle(
                          shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                          elevation=0),
                      on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


def _scheme_tab(page, session: AppSession) -> ft.Control:
    def _load():
        with SessionLocal() as db:
            return CommissionSchemeService.get_all(db, session.company_id)

    data_ref = {"items": _load()}

    def _build_rows(items):
        rows = []
        for s in items:
            type_label = dict(_TYPE_OPTS).get(s.commission_type, s.commission_type)
            apply_label = dict(_APPLY_OPTS).get(s.apply_on, s.apply_on)
            recipient = (s.partner.name if s.partner else
                         s.ref_customer.name if s.ref_customer else "Default")

            detail_parts = []
            if s.commission_type in ("PERCENTAGE", "COMBINATION"):
                cap = f" (maks Rp {s.max_commission_per_so:,.0f})" if s.max_commission_per_so else ""
                detail_parts.append(f"{s.commission_pct}%{cap}")
            if s.commission_type in ("FLAT", "COMBINATION"):
                detail_parts.append(f"Flat Rp {s.flat_amount:,.0f}")

            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(s.name, size=13, weight=ft.FontWeight.W_600,
                            color=Colors.TEXT_PRIMARY),
                    ft.Text(f"Untuk: {recipient}", size=11, color=Colors.TEXT_MUTED),
                ])),
                ft.DataCell(ft.Text(type_label, size=12, color=Colors.TEXT_SECONDARY)),
                ft.DataCell(ft.Text(" + ".join(detail_parts), size=12,
                                    color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_500)),
                ft.DataCell(ft.Text(apply_label, size=12, color=Colors.TEXT_SECONDARY)),
                ft.DataCell(ft.Container(
                    content=ft.Text("Aktif" if s.is_active else "Nonaktif",
                                    size=11,
                                    color=Colors.SUCCESS if s.is_active else Colors.ERROR,
                                    weight=ft.FontWeight.W_600),
                    bgcolor=ft.Colors.with_opacity(
                        0.12, Colors.SUCCESS if s.is_active else Colors.ERROR),
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                )),
                ft.DataCell(ft.Row(spacing=0, controls=[
                    action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                               lambda e, sid=s.id: _scheme_form_dialog(
                                   page, session, sid, refresh),
                               Colors.INFO),
                    action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                               lambda e, sid=s.id, nm=s.name: confirm_dialog(
                                   page, "Hapus Skema", f"Hapus skema '{nm}'?",
                                   lambda: _delete_scheme(sid)),
                               Colors.ERROR),
                ])),
            ]))
        return rows

    def _delete_scheme(sid):
        with SessionLocal() as db:
            ok, msg = CommissionSchemeService.delete(db, sid)
        show_snack(page, msg, ok)
        if ok: refresh()

    COLS = [
        ft.DataColumn(ft.Text("Nama Skema",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Detail",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Berlaku Utk", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=56, column_spacing=16,
        columns=COLS,
        rows=_build_rows(data_ref["items"]),
    )
    table_wrap = ft.Column(
        controls=[table if data_ref["items"] else empty_state("Belum ada skema komisi.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def refresh():
        data_ref["items"] = _load()
        table.rows = _build_rows(data_ref["items"])
        table_wrap.controls = [
            table if data_ref["items"] else empty_state("Belum ada skema komisi.")
        ]
        try: table_wrap.update()
        except: pass

    table.rows = _build_rows(data_ref["items"])

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK, padding=ft.Padding.all(0),
        content=ft.Column(expand=True, spacing=12, controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    ft.Button(
                        content=ft.Row(tight=True, spacing=6, controls=[
                            ft.Icon(ft.Icons.ADD, size=16, color=Colors.TEXT_ON_ACCENT),
                            ft.Text("Buat Skema", size=13, color=Colors.TEXT_ON_ACCENT,
                                    weight=ft.FontWeight.W_600),
                        ]),
                        bgcolor=Colors.ACCENT,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                            elevation=0),
                        on_click=lambda e: _scheme_form_dialog(page, session, None, refresh),
                    ),
                ],
            ),
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[table_wrap]),
            ),
        ]),
    )


# ─────────────────────────────────────────────────────────────
# TAB 2 — TRANSAKSI KOMISI
# ─────────────────────────────────────────────────────────────
def _transaction_tab(page, session: AppSession) -> ft.Control:
    status_val = {"v": ""}
    search_val = {"q": ""}
    # Checkbox untuk payment selection
    selected_ids: set = set()

    def _load():
        with SessionLocal() as db:
            return CommissionTransactionService.get_all(
                db, session.company_id,
                status=status_val["v"],
                search=search_val["q"],
            )

    data_ref = {"items": _load()}

    def _build_rows(items):
        rows = []
        for tx in items:
            partner_name = (tx.partner.name if tx.partner else
                            tx.ref_customer.name if tx.ref_customer else "—")
            so_num = tx.so.so_number if tx.so else "—"
            cust   = tx.customer.name if tx.customer else "—"

            detail = []
            if tx.commission_from_pct:
                detail.append(f"{tx.commission_pct}% = Rp {tx.commission_from_pct:,.0f}")
            if tx.flat_amount:
                detail.append(f"Flat Rp {tx.flat_amount:,.0f}")

            cb = ft.Checkbox(
                value=tx.id in selected_ids,
                active_color=Colors.ACCENT,
                visible=tx.status == "APPROVED",
                on_change=lambda e, tid=tx.id: (
                    selected_ids.add(tid) if e.control.value
                    else selected_ids.discard(tid)
                ),
            )

            actions = []
            if tx.status == "PENDING":
                actions.append(action_btn(
                    ft.Icons.CHECK_CIRCLE_OUTLINE, "Approve",
                    lambda e, tid=tx.id: _approve(tid),
                    Colors.SUCCESS))
            actions.append(action_btn(
                ft.Icons.CANCEL_OUTLINED, "Batalkan",
                lambda e, tid=tx.id: confirm_dialog(
                    page, "Batalkan Komisi", "Batalkan transaksi komisi ini?",
                    lambda: _cancel_tx(tid)),
                Colors.ERROR) if tx.status in ("PENDING", "APPROVED") else ft.Container())

            rows.append(ft.DataRow(cells=[
                ft.DataCell(cb),
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(partner_name, size=13, weight=ft.FontWeight.W_600,
                            color=Colors.TEXT_PRIMARY),
                    ft.Container(
                        visible=bool(tx.is_first_so),
                        padding=ft.Padding.symmetric(horizontal=6, vertical=1),
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, Colors.SUCCESS),
                        content=ft.Text("Customer Baru", size=9, color=Colors.SUCCESS,
                                        weight=ft.FontWeight.W_600),
                    ),
                ])),
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(so_num, size=12, color=Colors.TEXT_PRIMARY,
                            font_family="monospace"),
                    ft.Text(cust, size=11, color=Colors.TEXT_MUTED),
                ])),
                ft.DataCell(ft.Text(_fmt_date(tx.created_at), size=12,
                                    color=Colors.TEXT_SECONDARY)),
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(f"Rp {tx.total_commission:,.0f}", size=13,
                            color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700),
                    ft.Text(" + ".join(detail), size=10, color=Colors.TEXT_MUTED),
                ])),
                ft.DataCell(_tx_badge(tx.status)),
                ft.DataCell(ft.Row(spacing=0, controls=actions)),
            ]))
        return rows

    def _approve(tid):
        with SessionLocal() as db:
            ok, msg = CommissionTransactionService.approve(
                db, tid, session.user_id)
        show_snack(page, msg, ok)
        if ok: refresh()

    def _cancel_tx(tid):
        with SessionLocal() as db:
            ok, msg = CommissionTransactionService.cancel(db, tid)
        show_snack(page, msg, ok)
        if ok: refresh()

    COLS = [
        ft.DataColumn(ft.Text("✓",          size=12, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Penerima",   size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("SO / Cust.", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tanggal",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Komisi",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=60, column_spacing=16,
        columns=COLS,
        rows=_build_rows(data_ref["items"]),
    )
    table_wrap = ft.Column(
        controls=[table if data_ref["items"] else empty_state("Belum ada transaksi komisi.")],
        scroll=ft.ScrollMode.AUTO,
    )
    filter_area = ft.Container()

    def refresh():
        data_ref["items"] = _load()
        table.rows = _build_rows(data_ref["items"])
        table_wrap.controls = [
            table if data_ref["items"] else empty_state("Belum ada transaksi.")
        ]
        filter_area.content = _filter_bar()
        try: table_wrap.update(); filter_area.update()
        except: pass

    def on_filter(val):
        status_val["v"] = val; refresh()

    def on_search(e):
        search_val["q"] = e.control.value or ""; refresh()

    def _filter_bar():
        filters = [("", "Semua")] + _TX_STATUS_OPTS
        btns = []
        for val, label in filters:
            is_act = status_val["v"] == val
            color  = _TX_STATUS_COLOR.get(val, Colors.TEXT_SECONDARY)
            btns.append(ft.Container(
                height=30, padding=ft.Padding.symmetric(horizontal=12),
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=ft.Colors.with_opacity(0.12, color) if is_act else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, color if is_act else Colors.BORDER),
                on_click=lambda e, v=val: on_filter(v), ink=True,
                content=ft.Text(label, size=12,
                    color=color if is_act else Colors.TEXT_SECONDARY,
                    weight=ft.FontWeight.W_600 if is_act else ft.FontWeight.W_400),
            ))
        return ft.Row(spacing=6, wrap=True, controls=btns)

    def _open_payment_dialog():
        if not selected_ids:
            show_snack(page, "Pilih minimal satu komisi APPROVED.", False)
            return
        _payment_dialog(page, session, list(selected_ids),
                        lambda: (selected_ids.clear(), refresh()))

    filter_area.content = _filter_bar()
    table.rows = _build_rows(data_ref["items"])

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK,
        content=ft.Column(expand=True, spacing=10, controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    filter_area,
                    ft.Button(
                        content=ft.Row(tight=True, spacing=6, controls=[
                            ft.Icon(ft.Icons.PAYMENTS, size=16, color=Colors.TEXT_ON_ACCENT),
                            ft.Text("Bayar Komisi Terpilih", size=13,
                                    color=Colors.TEXT_ON_ACCENT, weight=ft.FontWeight.W_600),
                        ]),
                        bgcolor=Colors.SUCCESS,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                            elevation=0),
                        on_click=lambda e: _open_payment_dialog(),
                    ),
                ],
            ),
            ft.Row(controls=[search_bar("Cari partner / nomor SO...", on_search)]),
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[table_wrap]),
            ),
        ]),
    )


# ─────────────────────────────────────────────────────────────
# PAYMENT DIALOG
# ─────────────────────────────────────────────────────────────
def _payment_dialog(page, session: AppSession,
                    tx_ids: List[int], on_saved):
    with SessionLocal() as db:
        txs = db.query(CommissionTransaction)\
                .filter(CommissionTransaction.id.in_(tx_ids),
                        CommissionTransaction.status == "APPROVED")\
                .options(
                    joinedload(CommissionTransaction.partner),
                    joinedload(CommissionTransaction.so),
                ).all()
        total = sum(tx.total_commission for tx in txs)
        # Ambil info penerima dari tx pertama
        first_tx       = txs[0] if txs else None
        recipient_type = first_tx.recipient_type if first_tx else "PARTNER"
        partner_id     = first_tx.partner_id if first_tx else None
        ref_cust_id    = first_tx.referring_customer_id if first_tx else None

        tx_preview = [{
            "so": tx.so.so_number if tx.so else "—",
            "amount": tx.total_commission,
        } for tx in txs]

    from sqlalchemy.orm import joinedload as _jl

    f_date   = make_field("Tanggal Bayar *", date.today().strftime("%Y-%m-%d"),
                          hint="YYYY-MM-DD", width=160)
    f_method = make_dropdown("Metode Pembayaran", _PMT_METHOD_OPTS, "BANK_TRANSFER")
    f_ref    = make_field("Nomor Referensi / Bukti", "",
                          hint="No. transfer / kuitansi", width=220)
    f_notes  = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=2)

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)
    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    # Preview items
    preview_rows = [
        ft.Container(
            border=ft.Border.all(1, Colors.BORDER), border_radius=4,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(t["so"], size=12, color=Colors.TEXT_SECONDARY,
                            font_family="monospace"),
                    ft.Text(f"Rp {t['amount']:,.0f}", size=12,
                            color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                ],
            ),
        )
        for t in tx_preview
    ]

    def save(e):
        pd = _parse_date(f_date.value)
        if not pd:
            show_err("Tanggal tidak valid."); return
        data = {
            "payment_date":    pd,
            "recipient_type":  recipient_type,
            "partner_id":      partner_id,
            "referring_customer_id": ref_cust_id,
            "payment_method":  f_method.value,
            "reference_number":f_ref.value,
            "notes":           f_notes.value,
        }
        with SessionLocal() as db:
            ok, msg, _ = CommissionPaymentService.create_payment(
                db, session.company_id, session.user_id, data, tx_ids)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok and on_saved: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=2, tight=True, controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Icon(ft.Icons.PAYMENTS, color=Colors.SUCCESS, size=18),
                        ft.Text("Bayar Komisi", color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                    ]),
                    ft.Text(f"{len(tx_ids)} transaksi  ·  Total Rp {total:,.0f}",
                            size=11, color=Colors.TEXT_MUTED),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(
            width=500,
            content=ft.Column(spacing=10, tight=True, controls=[
                err,
                ft.Container(
                    max_height=160,
                    content=ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO,
                                      controls=preview_rows),
                ),
                ft.Divider(height=1, color=Colors.BORDER),
                f_date, f_method, f_ref, f_notes,
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ft.Button(f"Bayar Rp {total:,.0f}",
                      bgcolor=Colors.SUCCESS, color=ft.Colors.WHITE,
                      style=ft.ButtonStyle(
                          shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                          elevation=0),
                      on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


# ─────────────────────────────────────────────────────────────
# TAB 3 — RIWAYAT PEMBAYARAN
# ─────────────────────────────────────────────────────────────
def _payment_tab(page, session: AppSession) -> ft.Control:
    def _load():
        with SessionLocal() as db:
            return CommissionPaymentService.get_all(db, session.company_id)

    items = _load()
    rows  = []
    for pmt in items:
        recipient = (pmt.partner.name if pmt.partner else
                     pmt.ref_customer.name if pmt.ref_customer else "—")
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(pmt.payment_number, size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY, font_family="monospace"),
                ft.Text(_fmt_date(pmt.payment_date), size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(recipient, size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(
                dict(_PMT_METHOD_OPTS).get(pmt.payment_method, pmt.payment_method),
                size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(pmt.reference_number or "—",
                                size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(str(len(pmt.items)), size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(f"Rp {pmt.total_amount:,.0f}", size=13,
                                weight=ft.FontWeight.W_700, color=Colors.SUCCESS)),
        ]))

    COLS = [
        ft.DataColumn(ft.Text("No. Pembayaran", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Penerima",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Metode",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Referensi",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Jml Tx",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Total",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=56, column_spacing=16,
        columns=COLS, rows=rows,
    )

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK,
        content=ft.Column(expand=True, controls=[
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[
                    ft.Column(controls=[
                        table if items else empty_state("Belum ada pembayaran komisi.")
                    ], scroll=ft.ScrollMode.AUTO)
                ]),
            ),
        ]),
    )


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def CommissionPage(page, session: AppSession) -> ft.Control:

    tab_scheme  = _scheme_tab(page, session)
    tab_tx      = _transaction_tab(page, session)
    tab_payment = _payment_tab(page, session)


    tabs = ft.Tabs(
            selected_index=1,
            length=3,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Skema Komisi", icon=ft.Icons.SETTINGS_PHONE),
                            ft.Tab(label="Transaksi Komisi", icon=ft.Icons.SETTINGS),
                            ft.Tab(label="Riwayat Bayar", icon= ft.Icons.PAYMENTS),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            ft.Container(
                                expand=True, padding=ft.Padding.only(top=16), content=tab_scheme),
                            ft.Container(
                                expand=True, padding=ft.Padding.only(top=16), content=tab_tx),
                            ft.Container(
                                expand=True, padding=ft.Padding.only(top=16), content=tab_payment),
                        ],
                    ),
                ],
            ),
        )

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK, padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=0, controls=[
            page_header(
                "Komisi Referral",
                "Kelola skema & pembayaran komisi mitra / customer referral",
            ),
            tabs,
        ]),
    )