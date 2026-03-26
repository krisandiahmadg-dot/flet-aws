"""
app/pages/tax/tax_management.py
Manajemen Pajak:
  Tab 1 — Master Tarif Pajak
  Tab 2 — Faktur Pajak (e-Faktur)
  Tab 3 — PPh 21 / PPh 23
  Tab 4 — Laporan Rekap Pajak
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import Branch, Vendor, Employee, Invoice, Customer
from app.services.tax_service import (
    TaxRateService, TaxInvoiceService,
    TaxWithholdingService, TaxReportService,
)
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn, page_header,
    search_bar, confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_TAX_TYPE_OPTS = [
    ("PPN",   "PPN (Pajak Pertambahan Nilai)"),
    ("PPH23", "PPh 23 (Jasa/Vendor)"),
    ("PPH21", "PPh 21 (Karyawan)"),
    ("CUSTOM","Pajak Custom"),
]
_APPLIES_OPTS = [
    ("BOTH",     "Pembelian & Penjualan"),
    ("SALES",    "Penjualan saja"),
    ("PURCHASE", "Pembelian saja"),
]
_FP_STATUS_OPTS = [
    ("DRAFT","Draft"), ("UPLOADED","Di-upload"),
    ("APPROVED","Disetujui"), ("REJECTED","Ditolak"),
]
_FP_STATUS_COLOR = {
    "DRAFT":    Colors.TEXT_MUTED,
    "UPLOADED": Colors.INFO,
    "APPROVED": Colors.SUCCESS,
    "REJECTED": Colors.ERROR,
}
_WH_STATUS_COLOR = {
    "DRAFT": Colors.TEXT_MUTED,
    "FINAL": Colors.SUCCESS,
    "REPORTED": Colors.ACCENT,
}
_MONTHS = ["","Jan","Feb","Mar","Apr","Mei","Jun",
           "Jul","Agu","Sep","Okt","Nov","Des"]

def _badge(status, color_map, label_map=None):
    color = color_map.get(status, Colors.TEXT_MUTED)
    label = label_map.get(status, status) if label_map else status
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


# ══════════════════════════════════════════════════════════════
# TAB 1 — MASTER TARIF PAJAK
# ══════════════════════════════════════════════════════════════
def _tax_rate_form(page, session: AppSession, tr_data: Optional[Dict], on_saved):
    is_edit = tr_data is not None
    d = tr_data or {}

    f_code = make_field("Kode *", d.get("code",""), read_only=is_edit, width=120)
    f_name = make_field("Nama *", d.get("name",""))
    f_type = make_dropdown("Tipe Pajak *", _TAX_TYPE_OPTS, d.get("tax_type","PPN"), width=250)
    f_rate = make_field("Tarif (%) *", str(d.get("rate",11)), width=100,
                        keyboard_type=ft.KeyboardType.NUMBER)
    f_applies = make_dropdown("Berlaku Untuk", _APPLIES_OPTS,
                              d.get("applies_to","BOTH"), width=230)
    sw_inclusive = ft.Switch(label="Harga sudah termasuk pajak",
                             value=d.get("is_inclusive",False), active_color=Colors.ACCENT)
    sw_default   = ft.Switch(label="Jadikan tarif default untuk tipe ini",
                             value=d.get("is_default",False), active_color=Colors.ACCENT)
    sw_active    = ft.Switch(label="Aktif", value=d.get("is_active",True),
                             active_color=Colors.ACCENT)
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def save(e):
        if not f_name.value.strip(): err.value="Nama wajib."; err.visible=True; err.update(); return
        try: rate = float(f_rate.value or 0)
        except ValueError: err.value="Tarif tidak valid."; err.visible=True; err.update(); return

        data = {
            "code": f_code.value, "name": f_name.value,
            "tax_type": f_type.value, "rate": rate,
            "applies_to": f_applies.value,
            "is_inclusive": sw_inclusive.value,
            "is_default":   sw_default.value,
            "is_active":    sw_active.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = TaxRateService.update(db, d["id"], data)
            else:
                ok, msg = TaxRateService.create(db, session.company_id, data)

        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Row(spacing=10, controls=[
                ft.Icon(ft.Icons.PERCENT, color=Colors.ACCENT, size=20),
                ft.Text("Edit Tarif Pajak" if is_edit else "Tambah Tarif Pajak",
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700, size=16),
            ]),
            ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
        ]),
        content=ft.Container(width=500, content=ft.Column(spacing=12, tight=True, controls=[
            err,
            ft.Row(spacing=12, controls=[f_code, f_type]),
            f_name,
            ft.Row(spacing=12, controls=[f_rate, f_applies]),
            sw_inclusive, sw_default,
            sw_active if is_edit else ft.Container(),
        ])),
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
    page.overlay.append(dlg); dlg.open=True; page.update()


def _tax_rate_tab(page, session: AppSession) -> ft.Control:
    type_val = {"v": ""}

    def _load():
        with SessionLocal() as db:
            rates = TaxRateService.get_all(
                db, session.company_id, type_val["v"], active_only=False)
            return [{
                "id":         r.id, "code": r.code, "name": r.name,
                "tax_type":   r.tax_type, "rate": r.rate,
                "applies_to": r.applies_to, "is_inclusive": r.is_inclusive,
                "is_default": r.is_default, "is_active": r.is_active,
            } for r in rates]

    initial = _load()

    _TYPE_COLOR = {"PPN":"#4CAF50","PPH23":"#2196F3","PPH21":"#FF9800","CUSTOM":"#9C27B0"}

    def _build_rows(data, refresh):
        rows = []
        for d in data:
            tc = _TYPE_COLOR.get(d["tax_type"], Colors.TEXT_MUTED)
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(d["code"], size=13, weight=ft.FontWeight.W_700,
                            color=Colors.TEXT_PRIMARY, font_family="monospace"),
                    ft.Text(d["name"], size=11, color=Colors.TEXT_MUTED),
                ])),
                ft.DataCell(ft.Container(
                    content=ft.Text(d["tax_type"], size=11, color=tc, weight=ft.FontWeight.W_600),
                    bgcolor=ft.Colors.with_opacity(0.12, tc), border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                )),
                ft.DataCell(ft.Text(f"{d['rate']}%", size=14, weight=ft.FontWeight.W_700,
                                    color=Colors.ACCENT)),
                ft.DataCell(ft.Text(dict(_APPLIES_OPTS).get(d["applies_to"],""),
                                    size=12, color=Colors.TEXT_SECONDARY)),
                ft.DataCell(ft.Row(spacing=4, controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE if d["is_default"] else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            size=16, color=Colors.SUCCESS if d["is_default"] else Colors.BORDER),
                    ft.Text("Default" if d["is_default"] else "—", size=12,
                            color=Colors.SUCCESS if d["is_default"] else Colors.TEXT_MUTED),
                ])),
                ft.DataCell(ft.Container(
                    content=ft.Text("Aktif" if d["is_active"] else "Nonaktif",
                                    size=11,
                                    color=Colors.SUCCESS if d["is_active"] else Colors.ERROR),
                    bgcolor=ft.Colors.with_opacity(0.12,
                                Colors.SUCCESS if d["is_active"] else Colors.ERROR),
                    border_radius=4, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                )),
                ft.DataCell(ft.Row(spacing=0, controls=[
                    action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                               lambda e, dd=d: _tax_rate_form(page, session, dd, refresh),
                               Colors.INFO),
                    action_btn(ft.Icons.DELETE_OUTLINE, "Nonaktifkan",
                               lambda e, tid=d["id"], n=d["name"]: confirm_dialog(
                                   page, "Nonaktifkan", f"Nonaktifkan tarif '{n}'?",
                                   lambda: _delete_rate(tid, page, refresh)),
                               Colors.ERROR),
                ])),
            ]))
        return rows

    COLS = [
        ft.DataColumn(ft.Text("Kode / Nama", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tarif",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Berlaku",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Default",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]
    table = ft.DataTable(
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=56, column_spacing=16,
        columns=COLS, rows=_build_rows(initial, lambda: None),
    )
    table_area = ft.Column(controls=[table], scroll=ft.ScrollMode.AUTO)

    def refresh():
        data = _load()
        table.rows = _build_rows(data, refresh)
        table_area.controls = [table if data else empty_state("Belum ada tarif pajak.")]
        try: table_area.update()
        except: pass

    def _seed(e):
        with SessionLocal() as db:
            TaxRateService.seed_defaults(db, session.company_id)
        show_snack(page, "Tarif pajak default Indonesia berhasil di-seed.", True)
        refresh()

    def _delete_rate(tid, page, refresh):
        with SessionLocal() as db:
            ok, msg = TaxRateService.delete(db, tid)
        show_snack(page, msg, ok)
        if ok: refresh()

    table.rows = _build_rows(initial, refresh)

    return ft.Column(spacing=12, expand=True, controls=[
        ft.Row(spacing=10, controls=[
            ft.Button(
                content=ft.Row(tight=True, spacing=6, controls=[
                    ft.Icon(ft.Icons.ADD, size=16, color=Colors.TEXT_ON_ACCENT),
                    ft.Text("Tambah Tarif", size=13, color=Colors.TEXT_ON_ACCENT),
                ]),
                bgcolor=Colors.ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
                on_click=lambda e: _tax_rate_form(page, session, None, refresh),
            ),
            ft.TextButton(
                "Seed Default Indonesia",
                style=ft.ButtonStyle(color=Colors.TEXT_MUTED),
                on_click=_seed,
            ),
        ]),
        ft.Container(
            bgcolor=ft.Colors.with_opacity(0.05, Colors.WARNING),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, Colors.WARNING)),
            border_radius=6, padding=ft.Padding.all(10),
            content=ft.Row(spacing=8, controls=[
                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=Colors.WARNING),
                ft.Text(
                    "Tarif pajak digunakan otomatis saat buat SO/Invoice berdasarkan "
                    "pengaturan di master produk dan pelanggan.",
                    size=12, color=Colors.WARNING, expand=True,
                ),
            ]),
        ),
        ft.Container(expand=True, content=ft.ListView(expand=True, controls=[table_area])),
    ])


# ══════════════════════════════════════════════════════════════
# TAB 2 — FAKTUR PAJAK
# ══════════════════════════════════════════════════════════════
def _faktur_form(page, session: AppSession, invoice_id: int,
                  inv_number: str, on_saved):
    f_date = make_field("Tgl Faktur Pajak *", date.today().strftime("%Y-%m-%d"),
                        hint="YYYY-MM-DD", width=160)
    f_npwp = make_field("NPWP Lawan Transaksi", "", hint="00.000.000.0-000.000", width=200)
    f_nama = make_field("Nama Lawan Transaksi", "")
    err    = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def save(e):
        data = {
            "tax_invoice_date": f_date.value,
            "npwp": f_npwp.value.strip() or None,
            "nama": f_nama.value.strip() or None,
        }
        with SessionLocal() as db:
            ok, msg = TaxInvoiceService.create_from_invoice(
                db, session.company_id, session.user_id, invoice_id, data)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Row(spacing=10, controls=[
                ft.Icon(ft.Icons.RECEIPT_LONG, color=Colors.ACCENT, size=20),
                ft.Text(f"Buat Faktur Pajak — {inv_number}",
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700, size=16),
            ]),
            ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
        ]),
        content=ft.Container(width=480, content=ft.Column(spacing=12, tight=True, controls=[
            err, f_date,
            ft.Text("Data Lawan Transaksi (Pelanggan):", size=12,
                    color=Colors.TEXT_MUTED, weight=ft.FontWeight.W_600),
            f_npwp, f_nama,
            ft.Text("NPWP & nama akan diisi otomatis dari master pelanggan jika kosong.",
                    size=11, color=Colors.TEXT_MUTED, italic=True),
        ])),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Buat Faktur", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open=True; page.update()


def _faktur_tab(page, session: AppSession) -> ft.Control:
    month_val = {"v": datetime.now().month}
    year_val  = {"v": datetime.now().year}

    def _load():
        with SessionLocal() as db:
            fps = TaxInvoiceService.get_all(
                db, session.company_id,
                period_month=month_val["v"],
                period_year=year_val["v"],
            )
            return [{
                "id":     fp.id,
                "number": fp.tax_invoice_number,
                "status": fp.status,
                "date":   _fmt_date(fp.tax_invoice_date),
                "inv_number": fp.invoice.invoice_number if fp.invoice else "—",
                "customer":   fp.invoice.customer.name if (fp.invoice and fp.invoice.customer) else "—",
                "npwp":   fp.npwp_lawan or "—",
                "dpp":    fp.dpp,
                "rate":   fp.tax_rate,
                "ppn":    fp.tax_amount,
                "inv_id": fp.invoice_id,
            } for fp in fps]

    # Invoice yang belum punya faktur pajak
    def _load_invoiceable():
        with SessionLocal() as db:
            invs = db.query(Invoice).filter(
                Invoice.company_id == session.company_id,
                Invoice.invoice_type == "SALES",
                Invoice.status.notin_(["CANCELLED","DRAFT"]),
            ).options(joinedload(Invoice.customer)).all()
            # Filter yang belum ada faktur pajak
            from app.models import TaxInvoice
            existing_inv_ids = {
                r[0] for r in
                db.query(TaxInvoice.invoice_id)
                  .filter(TaxInvoice.company_id == session.company_id).all()
            }
            return [(str(inv.id),
                     f"{inv.invoice_number} — {inv.customer.name if inv.customer else '?'}"
                     f" — Rp {inv.total_amount:,.0f}")
                    for inv in invs if inv.id not in existing_inv_ids]

    initial = _load()

    def _build_rows(data, refresh):
        rows = []
        for d in data:
            actions = []
            if d["status"] == "DRAFT":
                actions.append(action_btn(
                    ft.Icons.UPLOAD, "Tandai Upload",
                    lambda e, fid=d["id"]: (
                        _mark_uploaded(fid, page, refresh)),
                    Colors.INFO))
            if d["status"] == "UPLOADED":
                actions.append(action_btn(
                    ft.Icons.CHECK_CIRCLE_OUTLINE, "Setujui",
                    lambda e, fid=d["id"]: (
                        _mark_approved(fid, page, refresh)),
                    Colors.SUCCESS))

            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(d["number"], size=12, weight=ft.FontWeight.W_700,
                            color=Colors.TEXT_PRIMARY, font_family="monospace"),
                    ft.Text(d["date"], size=11, color=Colors.TEXT_MUTED),
                ])),
                ft.DataCell(ft.Text(d["inv_number"], size=12, color=Colors.ACCENT,
                                    font_family="monospace")),
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(d["customer"], size=12, color=Colors.TEXT_SECONDARY),
                    ft.Text(d["npwp"],     size=11, color=Colors.TEXT_MUTED, font_family="monospace"),
                ])),
                ft.DataCell(ft.Text(f"Rp {_fmt(d['dpp'])}", size=12, color=Colors.TEXT_SECONDARY)),
                ft.DataCell(ft.Text(f"{d['rate']}%", size=12, color=Colors.ACCENT)),
                ft.DataCell(ft.Text(f"Rp {_fmt(d['ppn'])}", size=13,
                                    color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600)),
                ft.DataCell(_badge(d["status"], _FP_STATUS_COLOR,
                                   dict(_FP_STATUS_OPTS))),
                ft.DataCell(ft.Row(spacing=0, controls=actions)),
            ]))
        return rows

    COLS = [
        ft.DataColumn(ft.Text("No. Faktur",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Invoice",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Lawan Transaksi", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("DPP",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tarif",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("PPN",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]
    table = ft.DataTable(
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=58, column_spacing=16,
        columns=COLS, rows=_build_rows(initial, lambda: None),
    )
    table_area = ft.Column(controls=[table], scroll=ft.ScrollMode.AUTO)

    # Period filter
    month_opts = [("0","Semua Bulan")] + [(str(i), _MONTHS[i]) for i in range(1,13)]
    year_opts  = [(str(y), str(y)) for y in range(datetime.now().year-2, datetime.now().year+2)]
    f_month    = make_dropdown("Bulan", month_opts, str(month_val["v"]), width=130)
    f_year     = make_dropdown("Tahun", year_opts,  str(year_val["v"]),  width=100)

    def refresh():
        month_val["v"] = int(f_month.value or 0)
        year_val["v"]  = int(f_year.value or datetime.now().year)
        data = _load()
        table.rows = _build_rows(data, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada faktur pajak.")]
        try: table_area.update()
        except: pass

    f_month.on_select = lambda e: refresh()
    f_year.on_select  = lambda e: refresh()

    def _mark_uploaded(fid, page, refresh):
        with SessionLocal() as db:
            ok, msg = TaxInvoiceService.mark_uploaded(db, fid)
        show_snack(page, msg, ok)
        if ok: refresh()

    def _mark_approved(fid, page, refresh):
        with SessionLocal() as db:
            ok, msg = TaxInvoiceService.mark_approved(db, fid)
        show_snack(page, msg, ok)
        if ok: refresh()

    # Dropdown buat faktur dari invoice
    inv_opts_ref = {"opts": _load_invoiceable()}
    f_inv_sel = make_dropdown("Pilih Invoice", inv_opts_ref["opts"], "", width=350)

    def on_create_fp(e):
        if not f_inv_sel.value:
            show_snack(page, "Pilih invoice terlebih dahulu.", False); return
        # Cari nomor invoice
        inv_text = next((t for v,t in inv_opts_ref["opts"] if v == f_inv_sel.value), "")
        inv_number = inv_text.split(" — ")[0] if " — " in inv_text else inv_text
        _faktur_form(page, session, int(f_inv_sel.value), inv_number,
                     lambda: (refresh(), inv_opts_ref.update(
                         {"opts": _load_invoiceable()})))

    table.rows = _build_rows(initial, refresh)

    return ft.Column(spacing=12, expand=True, controls=[
        ft.Row(spacing=12, wrap=True, controls=[
            f_month, f_year,
            ft.Container(width=20),
            f_inv_sel,
            ft.Button(
                content=ft.Row(tight=True, spacing=6, controls=[
                    ft.Icon(ft.Icons.ADD, size=16, color=Colors.TEXT_ON_ACCENT),
                    ft.Text("Buat Faktur Pajak", size=13, color=Colors.TEXT_ON_ACCENT),
                ]),
                bgcolor=Colors.ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
                on_click=on_create_fp,
            ),
        ]),
        ft.Container(expand=True, content=ft.ListView(expand=True, controls=[table_area])),
    ])


# ══════════════════════════════════════════════════════════════
# TAB 3 — PPh 21 / PPh 23
# ══════════════════════════════════════════════════════════════
def _withholding_form(page, session: AppSession, on_saved):
    _user_branch = getattr(session, "branch_id", None)

    with SessionLocal() as db:
        branches = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        vendors  = db.query(Vendor).filter_by(
            company_id=session.company_id, is_active=True).order_by(Vendor.name).all()
        tax_rates = TaxRateService.get_all(db, session.company_id)
        if _user_branch:
            branches = [b for b in branches if b.id == _user_branch]

    br_opts = [(str(b.id), b.name) for b in branches]
    vend_opts = [("","— Pilih Vendor (PPh 23) —")] + [(str(v.id), v.name) for v in vendors]
    pph_type_opts = [("PPH23","PPh 23 (Jasa/Vendor)"), ("PPH21","PPh 21 (Karyawan)")]

    # Filter tarif per tipe
    rate_by_type = {}
    for tr in tax_rates:
        rate_by_type.setdefault(tr.tax_type, []).append((str(tr.id), f"{tr.code} — {tr.rate}%"))

    f_type   = make_dropdown("Tipe PPh *", pph_type_opts, "PPH23")
    f_branch = make_dropdown("Cabang *", br_opts,
                             str(_user_branch) if _user_branch else "",
                             disabled=bool(_user_branch))
    f_month  = make_dropdown("Bulan *",
                             [(str(i), _MONTHS[i]) for i in range(1,13)],
                             str(datetime.now().month), width=120)
    f_year   = make_field("Tahun *", str(datetime.now().year), width=90,
                          keyboard_type=ft.KeyboardType.NUMBER)
    f_vendor = make_dropdown("Vendor (PPh 23)", vend_opts, "")
    f_npwp   = make_field("NPWP", "", width=200, hint="00.000.000.0-000.000")
    f_nama   = make_field("Nama Wajib Pajak", "")
    f_inv_ref= make_field("Referensi Invoice/Kontrak", "", width=200)
    f_bruto  = make_field("Penghasilan Bruto *", "0",
                          keyboard_type=ft.KeyboardType.NUMBER, width=180)
    f_rate   = make_field("Tarif (%) *", "2",
                          keyboard_type=ft.KeyboardType.NUMBER, width=100)
    f_pph    = make_field("PPh Terutang", "0", read_only=True, width=180)
    f_notes  = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=3)
    err      = ft.Text("", color=Colors.ERROR, size=12, visible=False)
    dlg_ref  = {"dlg": None}

    def _recalc(e=None):
        try:
            b = float(f_bruto.value or 0)
            r = float(f_rate.value or 0)
            f_pph.value = str(round(b * r / 100, 0))
            try: f_pph.update()
            except: pass
        except: pass

    f_bruto.on_change = _recalc
    f_rate.on_change  = _recalc

    def on_type_change(e):
        is_pph23 = f_type.value == "PPH23"
        f_vendor.visible = is_pph23
        default_rate = "2" if is_pph23 else "5"
        f_rate.value = default_rate
        _recalc()
        try:
            if dlg_ref["dlg"]: dlg_ref["dlg"].update()
        except: pass

    def on_vendor_select(e):
        if f_vendor.value:
            with SessionLocal() as db:
                v = db.query(Vendor).filter_by(id=int(f_vendor.value)).first()
                if v:
                    f_npwp.value = v.tax_id or ""
                    f_nama.value = v.name or ""
                    try: f_npwp.update(); f_nama.update()
                    except: pass

    f_type.on_select   = on_type_change
    f_vendor.on_select = on_vendor_select

    def save(e):
        if not f_branch.value: err.value="Cabang wajib."; err.visible=True; err.update(); return
        try:
            bruto = float(f_bruto.value or 0)
            rate  = float(f_rate.value or 0)
        except ValueError:
            err.value="Nilai tidak valid."; err.visible=True; err.update(); return
        if bruto <= 0: err.value="Bruto harus > 0."; err.visible=True; err.update(); return

        data = {
            "branch_id": f_branch.value,
            "tax_type":  f_type.value,
            "period_month": f_month.value,
            "period_year":  f_year.value,
            "vendor_id":    f_vendor.value or None,
            "npwp":         f_npwp.value.strip() or None,
            "nama":         f_nama.value.strip() or None,
            "invoice_ref":  f_inv_ref.value.strip() or None,
            "bruto":    bruto, "tax_rate": rate,
            "notes":    f_notes.value,
        }
        with SessionLocal() as db:
            ok, msg = TaxWithholdingService.create(
                db, session.company_id, session.user_id, data)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Row(spacing=10, controls=[
                ft.Icon(ft.Icons.ACCOUNT_BALANCE, color=Colors.ACCENT, size=20),
                ft.Text("Catat PPh Terutang", color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_700, size=16),
            ]),
            ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
        ]),
        content=ft.Container(width=560, height=480, content=ft.Column(
            scroll=ft.ScrollMode.AUTO, spacing=12, controls=[
                err,
                section_card("Informasi", [
                    ft.Row(spacing=12, controls=[f_type, f_branch]),
                    ft.Row(spacing=12, controls=[f_month, f_year]),
                    f_vendor,
                ]),
                section_card("Wajib Pajak", [
                    f_npwp, f_nama, f_inv_ref,
                ]),
                section_card("Perhitungan", [
                    ft.Row(spacing=12, controls=[f_bruto, f_rate, f_pph]),
                    ft.Text("PPh = Bruto × Tarif", size=11,
                            color=Colors.TEXT_MUTED, italic=True),
                ]),
                f_notes,
        ])),
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
    dlg.open = True; page.update()


def _withholding_tab(page, session: AppSession) -> ft.Control:
    type_val  = {"v": ""}
    month_val = {"v": datetime.now().month}
    year_val  = {"v": datetime.now().year}

    def _load():
        with SessionLocal() as db:
            whs = TaxWithholdingService.get_all(
                db, session.company_id,
                tax_type=type_val["v"],
                period_month=month_val["v"],
                period_year=year_val["v"],
            )
            return [{
                "id":      wh.id,
                "number":  wh.wh_number,
                "tax_type":wh.tax_type,
                "period":  f"{_MONTHS[wh.period_month]} {wh.period_year}",
                "nama":    wh.nama or (wh.vendor.name if wh.vendor else "—"),
                "npwp":    wh.npwp or "—",
                "bruto":   wh.bruto,
                "rate":    wh.tax_rate,
                "pph":     wh.tax_amount,
                "status":  wh.status,
                "inv_ref": wh.invoice_ref or "—",
            } for wh in whs]

    initial = _load()

    _TYPE_COLOR = {"PPH23": Colors.INFO, "PPH21": Colors.WARNING}

    def _build_rows(data, refresh):
        rows = []
        for d in data:
            tc = _TYPE_COLOR.get(d["tax_type"], Colors.TEXT_MUTED)
            actions = []
            if d["status"] == "DRAFT":
                actions.append(action_btn(
                    ft.Icons.CHECK_CIRCLE_OUTLINE, "Finalisasi",
                    lambda e, wid=d["id"]: _finalize(wid, page, refresh),
                    Colors.SUCCESS))
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(d["number"], size=12, weight=ft.FontWeight.W_700,
                            color=Colors.TEXT_PRIMARY, font_family="monospace"),
                    ft.Text(d["period"], size=11, color=Colors.TEXT_MUTED),
                ])),
                ft.DataCell(ft.Container(
                    content=ft.Text(d["tax_type"], size=11, color=tc,
                                    weight=ft.FontWeight.W_600),
                    bgcolor=ft.Colors.with_opacity(0.12, tc), border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                )),
                ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                    ft.Text(d["nama"], size=12, color=Colors.TEXT_SECONDARY),
                    ft.Text(d["npwp"], size=11, color=Colors.TEXT_MUTED, font_family="monospace"),
                ])),
                ft.DataCell(ft.Text(d["inv_ref"],  size=12, color=Colors.TEXT_MUTED)),
                ft.DataCell(ft.Text(f"Rp {_fmt(d['bruto'])}", size=12,
                                    color=Colors.TEXT_SECONDARY)),
                ft.DataCell(ft.Text(f"{d['rate']}%", size=12, color=Colors.ACCENT)),
                ft.DataCell(ft.Text(f"Rp {_fmt(d['pph'])}", size=13,
                                    color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600)),
                ft.DataCell(_badge(d["status"], _WH_STATUS_COLOR,
                                   {"DRAFT":"Draft","FINAL":"Final","REPORTED":"Dilaporkan"})),
                ft.DataCell(ft.Row(spacing=0, controls=actions)),
            ]))
        return rows

    COLS = [
        ft.DataColumn(ft.Text("No. Bukpot",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("WP",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Ref",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Bruto",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tarif",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("PPh",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]
    table = ft.DataTable(
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=58, column_spacing=16,
        columns=COLS, rows=_build_rows(initial, lambda: None),
    )
    table_area = ft.Column(controls=[table], scroll=ft.ScrollMode.AUTO)

    type_opts  = [("","Semua"),("PPH23","PPh 23"),("PPH21","PPh 21")]
    month_opts = [("0","Semua")] + [(str(i), _MONTHS[i]) for i in range(1,13)]
    year_opts  = [(str(y), str(y)) for y in range(datetime.now().year-2, datetime.now().year+2)]
    f_type2  = make_dropdown("Tipe",  type_opts,  "",                    width=130)
    f_month2 = make_dropdown("Bulan", month_opts, str(month_val["v"]),   width=120)
    f_year2  = make_dropdown("Tahun", year_opts,  str(year_val["v"]),    width=100)

    def refresh():
        type_val["v"]  = f_type2.value or ""
        month_val["v"] = int(f_month2.value or 0)
        year_val["v"]  = int(f_year2.value or datetime.now().year)
        data = _load()
        table.rows = _build_rows(data, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada data PPh.")]
        try: table_area.update()
        except: pass

    f_type2.on_select  = lambda e: refresh()
    f_month2.on_select = lambda e: refresh()
    f_year2.on_select  = lambda e: refresh()

    def _finalize(wid, page, refresh):
        with SessionLocal() as db:
            ok, msg = TaxWithholdingService.finalize(db, wid)
        show_snack(page, msg, ok)
        if ok: refresh()

    table.rows = _build_rows(initial, refresh)

    return ft.Column(spacing=12, expand=True, controls=[
        ft.Row(spacing=12, wrap=True, controls=[
            ft.Button(
                content=ft.Row(tight=True, spacing=6, controls=[
                    ft.Icon(ft.Icons.ADD, size=16, color=Colors.TEXT_ON_ACCENT),
                    ft.Text("Catat PPh", size=13, color=Colors.TEXT_ON_ACCENT),
                ]),
                bgcolor=Colors.ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
                on_click=lambda e: _withholding_form(page, session, refresh),
            ),
            f_type2, f_month2, f_year2,
        ]),
        ft.Container(expand=True, content=ft.ListView(expand=True, controls=[table_area])),
    ])


# ══════════════════════════════════════════════════════════════
# TAB 4 — LAPORAN REKAP PAJAK
# ══════════════════════════════════════════════════════════════
def _report_tab(page, session: AppSession) -> ft.Control:
    year_val  = {"v": datetime.now().year}
    month_val = {"v": datetime.now().month}
    report_area = ft.Container()

    year_opts  = [(str(y), str(y)) for y in range(datetime.now().year-2, datetime.now().year+2)]
    month_opts = [(str(i), _MONTHS[i]) for i in range(1,13)]
    f_year3  = make_dropdown("Tahun", year_opts,  str(year_val["v"]),  width=100)
    f_month3 = make_dropdown("Bulan", month_opts, str(month_val["v"]), width=120)

    def _generate(e=None):
        y = int(f_year3.value or datetime.now().year)
        m = int(f_month3.value or datetime.now().month)
        year_val["v"]  = y
        month_val["v"] = m

        with SessionLocal() as db:
            ppn  = TaxReportService.ppn_monthly(db, session.company_id, y, m)
            pph  = TaxReportService.pph_monthly(db, session.company_id, y, m)

        def _section_header(title, color):
            return ft.Container(
                bgcolor=ft.Colors.with_opacity(0.08, color),
                border_radius=6, padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                content=ft.Text(title, size=13, color=color, weight=ft.FontWeight.W_700),
            )

        def _row(cols, is_header=False):
            return ft.Row(
                controls=[
                    ft.Container(
                        expand=1 if i == 0 else 0,
                        width=None if i == 0 else 140,
                        content=ft.Text(c, size=12 if not is_header else 11,
                            color=Colors.TEXT_PRIMARY if not is_header else Colors.TEXT_MUTED,
                            weight=ft.FontWeight.W_600 if is_header else ft.FontWeight.W_400,
                        ),
                    )
                    for i, c in enumerate(cols)
                ],
            )

        def _ppn_table(rows, total_dpp, total_ppn, title):
            items = [
                _section_header(title, Colors.SUCCESS),
                _row(["Nomor","Tanggal","Nama / NPWP","DPP","PPN"], is_header=True),
            ]
            for r in rows:
                items.append(_row([
                    r.get("invoice_number", r.get("po_number","")),
                    r.get("date",""),
                    f"{r.get('customer', r.get('vendor',''))}\n{r.get('npwp','')}",
                    f"Rp {_fmt(r['dpp'])}",
                    f"Rp {_fmt(r['ppn'])}",
                ]))
            items.append(ft.Divider(color=Colors.BORDER))
            items.append(ft.Row(controls=[
                ft.Container(expand=True, content=ft.Text(
                    f"TOTAL ({len(rows)} transaksi)",
                    size=12, weight=ft.FontWeight.W_700, color=Colors.TEXT_PRIMARY)),
                ft.Text(f"Rp {_fmt(total_dpp)}", size=12, weight=ft.FontWeight.W_700,
                        width=140, color=Colors.TEXT_PRIMARY),
                ft.Text(f"Rp {_fmt(total_ppn)}", size=13, weight=ft.FontWeight.W_700,
                        width=140, color=Colors.SUCCESS),
            ]))
            return ft.Container(
                border=ft.Border.all(1, Colors.BORDER), border_radius=8,
                padding=ft.Padding.all(12),
                content=ft.Column(spacing=6, controls=items),
            )

        kurang_bayar = ppn["ppn_kurang_bayar"]
        kb_color = Colors.ERROR if kurang_bayar > 0 else Colors.SUCCESS

        report_area.content = ft.Column(spacing=16, controls=[
            # Summary PPN
            ft.Container(
                bgcolor=ft.Colors.with_opacity(0.08, kb_color),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, kb_color)),
                border_radius=8, padding=ft.Padding.all(14),
                content=ft.Row(spacing=20, controls=[
                    ft.Column(spacing=4, controls=[
                        ft.Text("PPN Keluaran", size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Rp {_fmt(ppn['ppn_keluaran']['total_ppn'])}", size=18,
                                weight=ft.FontWeight.W_700, color=Colors.SUCCESS),
                    ]),
                    ft.Text("−", size=22, color=Colors.TEXT_MUTED),
                    ft.Column(spacing=4, controls=[
                        ft.Text("PPN Masukan", size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Rp {_fmt(ppn['ppn_masukan']['total_ppn'])}", size=18,
                                weight=ft.FontWeight.W_700, color=Colors.INFO),
                    ]),
                    ft.Text("=", size=22, color=Colors.TEXT_MUTED),
                    ft.Column(spacing=4, controls=[
                        ft.Text("PPn Kurang/Lebih Bayar", size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Rp {_fmt(abs(kurang_bayar))}", size=22,
                                weight=ft.FontWeight.W_700, color=kb_color),
                        ft.Text("KURANG BAYAR" if kurang_bayar>0 else "LEBIH BAYAR",
                                size=11, color=kb_color, weight=ft.FontWeight.W_700),
                    ]),
                ]),
            ),
            _ppn_table(
                ppn["ppn_keluaran"]["rows"],
                ppn["ppn_keluaran"]["total_dpp"],
                ppn["ppn_keluaran"]["total_ppn"],
                f"PPN Keluaran — {_MONTHS[m]} {y}",
            ),
            _ppn_table(
                ppn["ppn_masukan"]["rows"],
                ppn["ppn_masukan"]["total_dpp"],
                ppn["ppn_masukan"]["total_ppn"],
                f"PPN Masukan — {_MONTHS[m]} {y}",
            ),
            # PPh summary
            _section_header(f"Rekapitulasi PPh — {_MONTHS[m]} {y}", Colors.INFO),
            ft.Container(
                border=ft.Border.all(1, Colors.BORDER), border_radius=8,
                padding=ft.Padding.all(12),
                content=ft.Text(
                    f"Gunakan Tab PPh 21/23 untuk detail. "
                    f"Total PPh dicatat: Rp {_fmt(pph['total_pph'])} "
                    f"dari {len(pph['rows'])} bukti potong.",
                    size=12, color=Colors.TEXT_SECONDARY,
                ),
            ),
        ])
        try: report_area.update()
        except: pass

    f_year3.on_select  = lambda e: _generate()
    f_month3.on_select = lambda e: _generate()
    _generate()

    return ft.Column(spacing=12, expand=True, controls=[
        ft.Row(spacing=12, controls=[
            f_year3, f_month3,
            ft.Button(
                content=ft.Row(tight=True, spacing=6, controls=[
                    ft.Icon(ft.Icons.REFRESH, size=16, color=Colors.TEXT_ON_ACCENT),
                    ft.Text("Generate", size=13, color=Colors.TEXT_ON_ACCENT),
                ]),
                bgcolor=Colors.ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
                on_click=_generate,
            ),
        ]),
        ft.Container(
            expand=True,
            content=ft.ListView(expand=True, controls=[report_area]),
        ),
    ])


# ══════════════════════════════════════════════════════════════
# MAIN PAGE — Tab Container
# ══════════════════════════════════════════════════════════════
def TaxManagementPage(page, session: AppSession) -> ft.Control:
    active_tab = {"idx": 0}

    tab_defs = [
        ("Master Tarif",   ft.Icons.PERCENT,         lambda: _tax_rate_tab(page, session)),
        ("Faktur Pajak",   ft.Icons.RECEIPT_LONG,    lambda: _faktur_tab(page, session)),
        ("PPh 21/23",      ft.Icons.ACCOUNT_BALANCE, lambda: _withholding_tab(page, session)),
        ("Laporan Pajak",  ft.Icons.ASSESSMENT,      lambda: _report_tab(page, session)),
    ]

    tab_bar    = ft.Row(spacing=6)
    content_sw = ft.Container(expand=True)

    def switch_tab(idx):
        active_tab["idx"] = idx
        btns = []
        for i, (label, icon, _) in enumerate(tab_defs):
            is_act = i == idx
            btns.append(ft.Container(
                height=36, padding=ft.Padding.symmetric(horizontal=14),
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=ft.Colors.with_opacity(0.12, Colors.ACCENT) if is_act
                        else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, Colors.ACCENT if is_act else Colors.BORDER),
                ink=True, on_click=lambda e, i=i: switch_tab(i),
                content=ft.Row(tight=True, spacing=6, controls=[
                    ft.Icon(icon, size=14,
                            color=Colors.ACCENT if is_act else Colors.TEXT_MUTED),
                    ft.Text(label, size=12,
                            color=Colors.ACCENT if is_act else Colors.TEXT_SECONDARY,
                            weight=ft.FontWeight.W_600 if is_act else ft.FontWeight.W_400),
                ]),
            ))
        tab_bar.controls = btns
        content_sw.content = tab_defs[idx][2]()
        try:
            tab_bar.update()
            content_sw.update()
        except: pass

    switch_tab(0)

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK, padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=12, controls=[
            page_header("Manajemen Pajak",
                        "PPN · PPh 21 · PPh 23 · Faktur Pajak · Laporan"),
            tab_bar,
            ft.Divider(color=Colors.DIVIDER, height=1),
            content_sw,
        ]),
    )
