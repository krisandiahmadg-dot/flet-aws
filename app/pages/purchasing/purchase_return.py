"""
app/pages/purchasing/purchase_return.py
Pembelian → Retur ke Vendor

Alur: DRAFT → CONFIRMED → SENT → COMPLETED (isi resolusi)
"""
from __future__ import annotations
import flet as ft
import json
from typing import Optional, List, Dict
from datetime import date

from app.database import SessionLocal
from app.models import PurchaseReturn, PurchaseReturnLine, GoodsReceipt, Warehouse, Branch
from app.services.purchase_return_service import PurchaseReturnService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    page_header, search_bar,
    confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS = [
    ("DRAFT",     "Draft"),
    ("CONFIRMED", "Dikonfirmasi"),
    ("SENT",      "Dikirim ke Vendor"),
    ("COMPLETED", "Selesai"),
    ("CANCELLED", "Dibatalkan"),
]
_STATUS_COLOR = {
    "DRAFT":     Colors.TEXT_MUTED,
    "CONFIRMED": Colors.WARNING,
    "SENT":      Colors.INFO,
    "COMPLETED": Colors.SUCCESS,
    "CANCELLED": Colors.ERROR,
}
_REASON_OPTS = [
    ("DEFECTIVE",  "Barang Rusak / Cacat"),
    ("WRONG_ITEM", "Barang Salah"),
    ("EXCESS_QTY", "Kelebihan Qty"),
    ("OTHER",      "Lainnya"),
]
_RESOLUTION_OPTS = [
    ("REPLACEMENT", "Barang Diganti (Replacement)"),
    ("CREDIT_NOTE", "Credit Note / Refund"),
    ("COMBINATION", "Kombinasi (Sebagian Diganti + Credit Note)"),
]
_RESOLUTION_COLOR = {
    "REPLACEMENT": Colors.SUCCESS,
    "CREDIT_NOTE": Colors.INFO,
    "COMBINATION": Colors.WARNING,
}
_RESOLUTION_ICON = {
    "REPLACEMENT": ft.Icons.SWAP_HORIZ,
    "CREDIT_NOTE": ft.Icons.RECEIPT_OUTLINED,
    "COMBINATION": ft.Icons.TUNE,
}


def _rtn_badge(status: str) -> ft.Container:
    color = _STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    label = dict(_STATUS_OPTS).get(status, status)
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _resolution_badge(resolution: str) -> ft.Container:
    if not resolution:
        return ft.Container()
    color = _RESOLUTION_COLOR.get(resolution, Colors.TEXT_MUTED)
    label = dict(_RESOLUTION_OPTS).get(resolution, resolution)
    icon  = _RESOLUTION_ICON.get(resolution, ft.Icons.HELP_OUTLINE)
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.1, color),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, color)),
        content=ft.Row(spacing=6, tight=True, controls=[
            ft.Icon(icon, size=12, color=color),
            ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        ]),
    )


def _fmt_date(d) -> str:
    if not d: return ""
    try: return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
    except: return ""


def _parse_date(val: str):
    if not (val or "").strip(): return None
    from datetime import datetime
    try: return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except: return None


# ─────────────────────────────────────────────────────────────
# DIALOG RESOLUSI — muncul saat klik "Vendor Sudah Terima"
# ─────────────────────────────────────────────────────────────
def _resolution_dialog(page, session: AppSession,
                       return_id: int, return_number: str,
                       total_qty: float, total_amount: float,
                       on_saved):
    """
    Dialog untuk mengisi resolusi dari vendor:
      REPLACEMENT  → isi qty pengganti
      CREDIT_NOTE  → isi nomor & nilai credit note
      COMBINATION  → isi keduanya
    """

    f_resolution   = make_dropdown("Resolusi Vendor *", _RESOLUTION_OPTS, "REPLACEMENT")
    f_replace_qty  = make_field(
        "Qty Pengganti *",
        str(int(total_qty)),
        hint=f"maks {int(total_qty)}",
        keyboard_type=ft.KeyboardType.NUMBER,
        width=160,
    )
    f_cn_number    = make_field("No. Credit Note *", "", hint="CN/2024/001", width=200)
    f_cn_amount    = make_field(
        "Nilai Credit Note *",
        str(int(total_amount)),
        hint="Rp",
        keyboard_type=ft.KeyboardType.NUMBER,
        width=160,
    )
    f_cn_date      = make_field("Tgl Credit Note", _fmt_date(date.today()),
                                hint="YYYY-MM-DD", width=160)

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    # ── Visibility per resolusi ───────────────────────────────
    replace_section = ft.Container(
        visible=True,
        content=ft.Column(spacing=8, controls=[
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=ft.Colors.with_opacity(0.06, Colors.SUCCESS),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, Colors.SUCCESS)),
                content=ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.SWAP_HORIZ, size=14, color=Colors.SUCCESS),
                    ft.Text(
                        "PO akan di-reopen ke PARTIAL → buat GR baru untuk barang pengganti.",
                        size=11, color=Colors.SUCCESS, expand=True,
                    ),
                ]),
            ),
            f_replace_qty,
        ]),
    )

    credit_section = ft.Container(
        visible=False,
        content=ft.Column(spacing=8, controls=[
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=ft.Colors.with_opacity(0.06, Colors.INFO),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.25, Colors.INFO)),
                content=ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.RECEIPT_OUTLINED, size=14, color=Colors.INFO),
                    ft.Text(
                        "Credit note akan dicatat sebagai tagihan ke vendor.",
                        size=11, color=Colors.INFO, expand=True,
                    ),
                ]),
            ),
            ft.Row(spacing=10, controls=[f_cn_number, f_cn_amount, f_cn_date]),
        ]),
    )

    dlg_ref = {"dlg": None}

    def on_resolution_change(e):
        res = f_resolution.value
        replace_section.visible = res in ("REPLACEMENT", "COMBINATION")
        credit_section.visible  = res in ("CREDIT_NOTE", "COMBINATION")
        try:
            if dlg_ref["dlg"]:
                dlg_ref["dlg"].update()
        except: pass

    f_resolution.on_select = on_resolution_change

    def save(e):
        show_err("")
        res = f_resolution.value
        if not res:
            show_err("Resolusi wajib dipilih."); return

        data: Dict = {"resolution": res}

        if res in ("REPLACEMENT", "COMBINATION"):
            try:
                rqty = float(f_replace_qty.value or 0)
            except ValueError:
                show_err("Qty pengganti tidak valid."); return
            if rqty <= 0:
                show_err("Qty pengganti harus > 0."); return
            if rqty > total_qty + 0.001:
                show_err(f"Qty pengganti tidak boleh > total diretur ({int(total_qty)})."); return
            data["replacement_qty"] = rqty

        if res in ("CREDIT_NOTE", "COMBINATION"):
            if not f_cn_number.value.strip():
                show_err("Nomor credit note wajib diisi."); return
            try:
                cn_amt = float(f_cn_amount.value or 0)
            except ValueError:
                show_err("Nilai credit note tidak valid."); return
            if cn_amt <= 0:
                show_err("Nilai credit note harus > 0."); return
            data["credit_note_number"] = f_cn_number.value.strip()
            data["credit_note_amount"] = cn_amt
            data["credit_note_date"]   = f_cn_date.value or ""

        with SessionLocal() as db:
            ok, msg = PurchaseReturnService.complete(db, return_id, session.user_id, data)

        dlg.open = False
        page.update()
        show_snack(page, msg, ok)
        if ok and on_saved: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        shape=ft.RoundedRectangleBorder(radius=Sizes.CARD_RADIUS),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Container(
                        width=36, height=36, border_radius=18,
                        bgcolor=ft.Colors.with_opacity(0.12, Colors.SUCCESS),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.HANDSHAKE_OUTLINED,
                                        size=18, color=Colors.SUCCESS),
                    ),
                    ft.Column(spacing=2, tight=True, controls=[
                        ft.Text("Resolusi dari Vendor", size=15,
                                weight=ft.FontWeight.W_700, color=Colors.TEXT_PRIMARY),
                        ft.Text(f"{return_number}  ·  Total Rp {total_amount:,.0f}",
                                size=11, color=Colors.TEXT_MUTED),
                    ]),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(
            width=520,
            padding=ft.Padding.only(top=4),
            content=ft.Column(spacing=12, tight=True, controls=[
                err,
                f_resolution,
                replace_section,
                credit_section,
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal",
                      style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ft.Button("Simpan Resolusi",
                      bgcolor=Colors.SUCCESS, color=ft.Colors.WHITE,
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
# FORM DIALOG — Buat Return Baru
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession, on_saved):
    with SessionLocal() as db:
        returnable_grs = PurchaseReturnService.get_returnable_grs(db, session.company_id)
        warehouses = db.query(Warehouse)\
            .join(Branch, Warehouse.branch_id == Branch.id)\
            .filter(Branch.company_id == session.company_id,
                    Warehouse.is_active == True).all()

        gr_opts = []
        for gr in returnable_grs:
            # Hitung total qty_rejected yang belum habis di-return
            total_returnable = sum(
                max(0, (grl.qty_rejected or 0))
                for grl in (gr.lines or [])
            )
            if total_returnable <= 0:
                continue  # skip GR yang tidak ada item ditolak
            gr_opts.append((
                str(gr.id),
                f"{gr.gr_number}  —  "
                f"{gr.po.vendor.name if (gr.po and gr.po.vendor) else '?'}"
                f"  ({_fmt_date(gr.receipt_date)})"
            ))
        wh_opts = [(str(w.id), f"{w.name}") for w in warehouses]

    if not gr_opts:
        show_snack(page, "Tidak ada GR yang bisa diretur saat ini.", False)
        return

    state = {"br_id": "", "row_refs": []}

    f_gr     = make_dropdown("GR Sumber *", gr_opts, "")
    f_wh     = make_dropdown("Gudang *", wh_opts, "")
    f_reason = make_dropdown("Alasan Retur *", _REASON_OPTS, "DEFECTIVE")
    f_date   = make_field("Tanggal Retur *",
                          date.today().strftime("%Y-%m-%d"),
                          hint="YYYY-MM-DD", width=160)
    f_notes  = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=3)

    lines_area = ft.Column(spacing=6)
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)
    dlg_ref = {"dlg": None}

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def _build_lines(reject_lines: List[Dict]):
        row_refs = []
        controls = []

        if not reject_lines:
            controls.append(ft.Container(
                padding=ft.Padding.all(20),
                content=ft.Text(
                    "GR ini tidak memiliki item rusak / ditolak yang bisa diretur.",
                    size=12, color=Colors.TEXT_MUTED),
            ))
            lines_area.controls = controls
            state["row_refs"] = []
            try:
                if dlg_ref["dlg"]: dlg_ref["dlg"].update()
            except: pass
            return

        controls.append(ft.Container(
            bgcolor=ft.Colors.with_opacity(0.05, Colors.TEXT_PRIMARY),
            border_radius=ft.border_radius.only(top_left=6, top_right=6),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            content=ft.Row(spacing=6, controls=[
                ft.Container(width=200, content=ft.Text(
                    "Produk", size=11, color=Colors.TEXT_MUTED, weight=ft.FontWeight.W_600)),
                ft.Container(width=60, content=ft.Text("Satuan", size=11, color=Colors.TEXT_MUTED)),
                ft.Container(width=90, content=ft.Text("Ditolak", size=11, color=Colors.ERROR, weight=ft.FontWeight.W_600)),
                ft.Container(width=90, content=ft.Text("Sdh Diretur", size=11, color=Colors.TEXT_MUTED)),
                ft.Container(width=100, content=ft.Text("Qty Retur *", size=11, color=Colors.WARNING, weight=ft.FontWeight.W_600)),
                ft.Container(width=120, content=ft.Text("Harga/unit", size=11, color=Colors.TEXT_MUTED)),
                ft.Container(width=140, content=ft.Text("Catatan", size=11, color=Colors.TEXT_MUTED)),
            ]),
        ))

        for ln in reject_lines:
            is_serial   = ln.get("tracking_type") == "SERIAL"
            f_qty       = make_field("", str(ln["qty_returnable"]),
                                     keyboard_type=ft.KeyboardType.NUMBER, width=100)
            f_line_note = make_field("", ln.get("rejection_reason", ""), width=140)

            sn_checks: List[ft.Checkbox] = []
            sn_area = ft.Container(visible=False)
            if is_serial and ln.get("sn_defective"):
                sn_checks = [
                    ft.Checkbox(
                        label=sn, value=True,
                        active_color=Colors.ERROR,
                        label_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=12),
                        data=sn,
                    )
                    for sn in ln["sn_defective"]
                ]
                sn_area = ft.Container(
                    visible=True,
                    margin=ft.Margin(0, 4, 0, 0),
                    padding=ft.Padding.all(10),
                    bgcolor=ft.Colors.with_opacity(0.03, Colors.ERROR),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.3, Colors.ERROR)),
                    border_radius=6,
                    content=ft.Column(spacing=6, controls=[
                        ft.Row(spacing=8, controls=[
                            ft.Icon(ft.Icons.QR_CODE_2, size=13, color=Colors.ERROR),
                            ft.Text("Pilih SN yang diretur:", size=11,
                                    color=Colors.ERROR, weight=ft.FontWeight.W_600),
                        ]),
                        ft.Row(wrap=True, spacing=8, controls=sn_checks),
                    ]),
                )

            rr = {
                "gr_line_id":     ln["gr_line_id"],
                "product_id":     ln["product_id"],
                "uom_id":         ln["uom_id"],
                "unit_cost":      ln["unit_cost"],
                "tracking_type":  ln.get("tracking_type", "NONE"),
                "qty_returnable": ln["qty_returnable"],
                "product_name":   ln["product_name"],
                "f_qty":          f_qty,
                "f_note":         f_line_note,
                "sn_checks":      sn_checks,
            }
            row_refs.append(rr)

            controls.append(ft.Container(
                border=ft.Border.all(1,
                    ft.Colors.with_opacity(0.4, Colors.ERROR) if is_serial else Colors.BORDER),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                content=ft.Column(spacing=4, controls=[
                    ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(width=200, content=ft.Column(
                                spacing=1, tight=True, controls=[
                                    ft.Text(ln["product_name"], size=13,
                                            color=Colors.TEXT_PRIMARY,
                                            weight=ft.FontWeight.W_500,
                                            overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                                    ft.Text(ln["product_code"], size=10,
                                            color=Colors.TEXT_MUTED, font_family="monospace"),
                                ],
                            )),
                            ft.Container(width=60, content=ft.Text(
                                ln["uom_code"], size=12, color=Colors.TEXT_SECONDARY)),
                            ft.Container(width=90, content=ft.Text(
                                f"{ln['qty_rejected']:,.2f}", size=12,
                                color=Colors.ERROR, weight=ft.FontWeight.W_600)),
                            ft.Container(width=90, content=ft.Text(
                                f"{ln['qty_returned']:,.2f}", size=12,
                                color=Colors.TEXT_MUTED)),
                            f_qty,
                            ft.Container(width=120, content=ft.Text(
                                f"Rp {ln['unit_cost']:,.0f}", size=12,
                                color=Colors.TEXT_SECONDARY)),
                            f_line_note,
                        ],
                    ),
                    sn_area,
                ]),
            ))

        state["row_refs"] = row_refs
        lines_area.controls = controls
        try:
            if dlg_ref["dlg"]: dlg_ref["dlg"].update()
            else: lines_area.update()
        except: pass

    def on_gr_change(e):
        if not f_gr.value: return
        with SessionLocal() as db:
            reject_lines = PurchaseReturnService.get_rejected_lines(db, int(f_gr.value))
            gr = db.query(GoodsReceipt).filter_by(id=int(f_gr.value)).first()
            if gr:
                state["br_id"] = str(gr.branch_id)
                if not f_wh.value:
                    f_wh.value = str(gr.warehouse_id)
                    try: f_wh.update()
                    except: pass
        _build_lines(reject_lines)

    f_gr.on_select = on_gr_change

    def save(e):
        show_err("")
        if not f_gr.value:   show_err("GR wajib dipilih."); return
        if not f_wh.value:   show_err("Gudang wajib dipilih."); return
        if not state["br_id"]: show_err("Cabang tidak terdeteksi."); return
        ret_date = _parse_date(f_date.value)
        if not ret_date:     show_err("Tanggal tidak valid."); return
        if not state["row_refs"]: show_err("Tidak ada item yang bisa diretur."); return

        lines = []
        for i, rr in enumerate(state["row_refs"]):
            try:
                qty = float(rr["f_qty"].value or 0)
            except ValueError:
                show_err(f"Baris {i+1}: Qty tidak valid."); return
            if qty <= 0: continue
            if qty > rr["qty_returnable"] + 0.001:
                show_err(
                    f"Baris {i+1} ({rr['product_name']}): "
                    f"Qty ({qty:,.2f}) melebihi yang bisa diretur ({rr['qty_returnable']:,.2f})."
                ); return
            sn_list = [cb.data for cb in rr["sn_checks"] if cb.value]
            if rr["tracking_type"] == "SERIAL" and rr["sn_checks"]:
                if len(sn_list) != int(qty):
                    show_err(
                        f"Baris {i+1}: Jumlah SN ({len(sn_list)}) "
                        f"harus sama dengan qty retur ({int(qty)})."
                    ); return
            lines.append({
                "gr_line_id":     rr["gr_line_id"],
                "product_id":     rr["product_id"],
                "uom_id":         rr["uom_id"],
                "qty_return":     qty,
                "unit_cost":      rr["unit_cost"],
                "serial_numbers": sn_list,
                "notes":          rr["f_note"].value or "",
            })

        if not lines: show_err("Tidak ada item yang di-retur."); return

        data = {
            "branch_id":    state["br_id"],
            "gr_id":        f_gr.value,
            "warehouse_id": f_wh.value,
            "return_date":  ret_date,
            "return_reason":f_reason.value or "DEFECTIVE",
            "notes":        f_notes.value,
        }

        with SessionLocal() as db:
            ok, msg, _ = PurchaseReturnService.create(
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
                    ft.Icon(ft.Icons.UNDO, color=Colors.ERROR, size=20),
                    ft.Text("Buat Return ke Vendor", color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(
            width=1000, height=560,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
                err,
                section_card("Header Return", [
                    f_gr,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 4}, content=f_wh),
                        ft.Container(col={"xs": 12, "sm": 3}, content=f_date),
                        ft.Container(col={"xs": 12, "sm": 5}, content=f_reason),
                    ]),
                    f_notes,
                ]),
                section_card("Item yang Diretur", [
                    ft.Text("Pilih GR di atas untuk memuat item rusak.",
                            size=12, color=Colors.TEXT_MUTED,
                            visible=len(state["row_refs"]) == 0),
                    lines_area,
                ]),
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ft.Button("Simpan Return",
                      bgcolor=Colors.ERROR, color=ft.Colors.WHITE,
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
# DETAIL DIALOG
# ─────────────────────────────────────────────────────────────
def _detail_dialog(page, session: AppSession, return_id: int, on_saved):
    with SessionLocal() as db:
        rtn = PurchaseReturnService.get_by_id(db, return_id)
        if not rtn:
            show_snack(page, "Return tidak ditemukan.", False); return

        rtn_number   = rtn.return_number
        rtn_status   = rtn.status
        resolution   = rtn.resolution or ""
        vendor_name  = rtn.vendor.name if rtn.vendor else "—"
        gr_number    = rtn.gr.gr_number if rtn.gr else "—"
        ret_date     = _fmt_date(rtn.return_date)
        reason_label = dict(_REASON_OPTS).get(rtn.return_reason, rtn.return_reason)
        total        = rtn.total_amount
        notes_val    = rtn.notes or ""
        replace_qty  = rtn.replacement_qty or 0
        cn_number    = rtn.credit_note_number or ""
        cn_amount    = rtn.credit_note_amount or 0
        cn_date      = _fmt_date(rtn.credit_note_date)

        lines_data = []
        for ln in (rtn.lines or []):
            sn_list = []
            if ln.serial_numbers:
                try: sn_list = json.loads(ln.serial_numbers)
                except: pass
            lines_data.append({
                "product_name": ln.product.name if ln.product else "—",
                "product_code": ln.product.code if ln.product else "",
                "uom_name":     ln.uom.name if ln.uom else "—",
                "qty_return":   ln.qty_return,
                "unit_cost":    ln.unit_cost,
                "line_total":   ln.qty_return * ln.unit_cost,
                "serial_numbers": sn_list,
                "notes":        ln.notes or "",
            })

    can_confirm  = rtn_status == "DRAFT"
    can_send     = rtn_status == "CONFIRMED"
    can_complete = rtn_status == "SENT"

    # ── Line rows ─────────────────────────────────────────────
    line_rows = []
    for i, ld in enumerate(lines_data):
        sn_row = ft.Container(visible=False)
        if ld["serial_numbers"]:
            sn_row = ft.Container(
                visible=True,
                margin=ft.Margin(32, 2, 0, 0),
                content=ft.Row(wrap=True, spacing=6, controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        border_radius=20,
                        bgcolor=ft.Colors.with_opacity(0.1, Colors.ERROR),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, Colors.ERROR)),
                        content=ft.Text(sn, size=10, color=Colors.ERROR, font_family="monospace"),
                    )
                    for sn in ld["serial_numbers"]
                ]),
            )
        line_rows.append(ft.Container(
            border=ft.Border.all(1, Colors.BORDER), border_radius=4,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Column(spacing=4, controls=[
                ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                    ft.Container(width=28, content=ft.Text(
                        str(i+1), size=12, color=Colors.TEXT_MUTED)),
                    ft.Container(expand=True, content=ft.Column(spacing=1, tight=True, controls=[
                        ft.Text(ld["product_name"], size=13, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_500),
                        ft.Text(ld["product_code"], size=11, color=Colors.TEXT_MUTED,
                                font_family="monospace"),
                    ])),
                    ft.Container(width=60, content=ft.Text(ld["uom_name"], size=12, color=Colors.TEXT_SECONDARY)),
                    ft.Container(width=80, content=ft.Text(f"{ld['qty_return']:,.2f}", size=12, color=Colors.ERROR, weight=ft.FontWeight.W_600)),
                    ft.Container(width=120, content=ft.Text(f"Rp {ld['unit_cost']:,.0f}", size=12, color=Colors.TEXT_SECONDARY)),
                    ft.Container(width=130, content=ft.Text(f"Rp {ld['line_total']:,.0f}", size=12, color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600)),
                    ft.Container(expand=True, content=ft.Text(ld["notes"], size=11, color=Colors.TEXT_MUTED)),
                ]),
                sn_row,
            ]),
        ))

    # ── Resolusi card (hanya jika sudah COMPLETED) ────────────
    resolution_card = ft.Container(visible=False)
    if resolution:
        res_color = _RESOLUTION_COLOR.get(resolution, Colors.TEXT_MUTED)
        res_controls = [
            ft.Row(spacing=8, controls=[
                _resolution_badge(resolution),
            ]),
        ]
        if resolution in ("REPLACEMENT", "COMBINATION"):
            res_controls.append(ft.Row(spacing=6, controls=[
                ft.Icon(ft.Icons.SWAP_HORIZ, size=13, color=Colors.SUCCESS),
                ft.Text(f"Qty pengganti: {int(replace_qty)} unit",
                        size=12, color=Colors.TEXT_PRIMARY),
                ft.Text("→ PO sudah di-reopen, buat GR baru untuk menerima pengganti.",
                        size=11, color=Colors.TEXT_MUTED),
            ]))
        if resolution in ("CREDIT_NOTE", "COMBINATION"):
            res_controls.append(ft.Row(spacing=6, controls=[
                ft.Icon(ft.Icons.RECEIPT_OUTLINED, size=13, color=Colors.INFO),
                ft.Text(f"Credit Note: {cn_number}", size=12, color=Colors.TEXT_PRIMARY),
                ft.Text(f"  Rp {cn_amount:,.0f}", size=12, color=Colors.INFO,
                        weight=ft.FontWeight.W_600),
                ft.Text(f"  ({cn_date})", size=11, color=Colors.TEXT_MUTED),
            ]))

        resolution_card = ft.Container(
            visible=True,
            padding=ft.Padding.all(14),
            border_radius=Sizes.BTN_RADIUS,
            bgcolor=ft.Colors.with_opacity(0.05, res_color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, res_color)),
            content=ft.Column(spacing=8, controls=res_controls),
        )

    def do_confirm(e):
        with SessionLocal() as db:
            ok, msg = PurchaseReturnService.confirm(db, return_id, session.user_id)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    def do_send(e):
        with SessionLocal() as db:
            ok, msg = PurchaseReturnService.send(db, return_id)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    def do_complete(e):
        # Hitung total qty return
        total_qty = sum(ld["qty_return"] for ld in lines_data)
        dlg.open = False; page.update()
        # Buka dialog resolusi
        _resolution_dialog(page, session, return_id, rtn_number,
                           total_qty, total, on_saved)

    actions = [
        ft.Button("Tutup", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                  on_click=lambda e: (setattr(dlg, "open", False), page.update())),
    ]
    if can_confirm:
        actions.append(ft.Button("Konfirmasi Return",
            bgcolor=Colors.WARNING, color=ft.Colors.WHITE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
            on_click=do_confirm))
    if can_send:
        actions.append(ft.Button("Kirim ke Vendor",
            bgcolor=Colors.INFO, color=ft.Colors.WHITE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
            on_click=do_send))
    if can_complete:
        actions.append(ft.Button("Vendor Sudah Terima →",
            bgcolor=Colors.SUCCESS, color=ft.Colors.WHITE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
            on_click=do_complete))

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=4, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.UNDO, color=Colors.ERROR, size=18),
                        ft.Text(rtn_number, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                        _rtn_badge(rtn_status),
                    ]),
                    ft.Row(spacing=16, controls=[
                        ft.Text(f"Vendor: {vendor_name}", size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"GR: {gr_number}",       size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Tgl: {ret_date}",       size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Alasan: {reason_label}",size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Total: Rp {total:,.0f}",size=12,
                                color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600),
                    ]),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(
            width=920, height=480,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8, controls=[
                # Header tabel
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Row(spacing=8, controls=[
                        ft.Container(width=28),
                        ft.Container(expand=True, content=ft.Text("Produk", size=11, color=Colors.TEXT_MUTED, weight=ft.FontWeight.W_600)),
                        ft.Container(width=60,  content=ft.Text("Satuan",    size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=80,  content=ft.Text("Qty Retur", size=11, color=Colors.ERROR, weight=ft.FontWeight.W_600)),
                        ft.Container(width=120, content=ft.Text("Harga/unit",size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=130, content=ft.Text("Subtotal",  size=11, color=Colors.TEXT_MUTED, weight=ft.FontWeight.W_600)),
                        ft.Container(expand=True, content=ft.Text("Catatan", size=11, color=Colors.TEXT_MUTED)),
                    ]),
                ),
                *line_rows,
                ft.Divider(height=1, color=Colors.BORDER),
                ft.Container(
                    alignment=ft.Alignment(1, 0), padding=ft.Padding.only(right=10),
                    content=ft.Text(f"TOTAL: Rp {total:,.0f}", size=14,
                                    weight=ft.FontWeight.W_700, color=Colors.TEXT_PRIMARY),
                ),
                resolution_card,
                ft.Container(
                    visible=bool(notes_val),
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=4, padding=ft.Padding.all(10),
                    content=ft.Column(spacing=4, controls=[
                        ft.Text("Catatan:", size=11, color=Colors.TEXT_MUTED, weight=ft.FontWeight.W_600),
                        ft.Text(notes_val, size=12, color=Colors.TEXT_SECONDARY),
                    ]),
                ),
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=actions,
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# TABLE
# ─────────────────────────────────────────────────────────────
def _rtns_to_dicts(rtns) -> List[Dict]:
    return [{
        "id":            rtn.id,
        "return_number": rtn.return_number,
        "status":        rtn.status,
        "resolution":    rtn.resolution or "",
        "vendor_name":   rtn.vendor.name if rtn.vendor else "—",
        "gr_number":     rtn.gr.gr_number if rtn.gr else "—",
        "branch_name":   rtn.branch.name if rtn.branch else "—",
        "return_date":   _fmt_date(rtn.return_date),
        "item_count":    len(rtn.lines or []),
        "total_amount":  rtn.total_amount,
    } for rtn in rtns]


def _build_rows(rtn_data, page, session, refresh):
    rows = []
    for d in rtn_data:
        actions = [
            action_btn(ft.Icons.VISIBILITY_OUTLINED, "Detail",
                lambda e, rid=d["id"]: _detail_dialog(page, session, rid, refresh),
                Colors.INFO),
        ]
        if d["status"] == "DRAFT":
            actions.append(action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                lambda e, rid=d["id"], rno=d["return_number"]: confirm_dialog(
                    page, "Hapus Return", f"Hapus {rno}?",
                    lambda: _delete(rid, page, refresh)),
                Colors.ERROR))
        if d["status"] not in ("COMPLETED", "CANCELLED"):
            actions.append(action_btn(ft.Icons.CANCEL_OUTLINED, "Batalkan",
                lambda e, rid=d["id"], rno=d["return_number"]: confirm_dialog(
                    page, "Batalkan Return", f"Batalkan {rno}?",
                    lambda: _cancel(rid, page, refresh),
                    "Ya, Batalkan", Colors.WARNING),
                Colors.WARNING))

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["return_number"], size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY, font_family="monospace"),
                ft.Text(d["gr_number"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["vendor_name"],  size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["branch_name"],  size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["return_date"],  size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"{d['item_count']} item", size=12, color=Colors.TEXT_PRIMARY),
                ft.Text(f"Rp {d['total_amount']:,.0f}", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Column(spacing=4, tight=True, controls=[
                _rtn_badge(d["status"]),
                _resolution_badge(d["resolution"]) if d["resolution"] else ft.Container(),
            ])),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def _cancel(rid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PurchaseReturnService.cancel(db, rid)
    show_snack(page, msg, ok); 
    if ok: refresh()


def _delete(rid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PurchaseReturnService.delete(db, rid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _filter_bar(active_status, on_filter):
    filters = [("", "Semua")] + _STATUS_OPTS
    btns = []
    for val, label in filters:
        is_act = active_status["v"] == val
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


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def PurchaseReturnPage(page, session: AppSession) -> ft.Control:
    search_val  = {"q": ""}
    status_val  = {"v": ""}
    filter_area = ft.Container()

    def _load():
        with SessionLocal() as db:
            rtns = PurchaseReturnService.get_all(
                db, session.company_id, search_val["q"], status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _rtns_to_dicts(rtns)

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("No. Return / GR", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Vendor",           size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang",           size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tgl Return",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item / Total",     size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status / Resolusi",size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",             size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=64, column_spacing=16,
        columns=COLS,
        rows=_build_rows(initial, page, session, lambda: None),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada purchase return.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def refresh():
        data = _load()
        table.rows = _build_rows(data, page, session, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada return.")]
        filter_area.content = _filter_bar(status_val, on_filter)
        try: table_area.update(); filter_area.update()
        except: pass

    def on_search(e):
        search_val["q"] = e.control.value or ""; refresh()

    def on_filter(val):
        status_val["v"] = val; refresh()

    filter_area.content = _filter_bar(status_val, on_filter)
    table.rows = _build_rows(initial, page, session, refresh)

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK, padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=0, controls=[
            page_header("Purchase Return",
                        "Retur barang rusak / tidak sesuai ke vendor",
                        "Buat Return Baru",
                        on_action=lambda: _form_dialog(page, session, refresh),
                        action_icon=ft.Icons.UNDO),
            ft.Container(padding=ft.Padding.only(bottom=12), content=filter_area),
            ft.Row(controls=[search_bar("Cari nomor return...", on_search)]),
            ft.Container(height=12),
            ft.Container(expand=True,
                         content=ft.ListView(expand=True, controls=[table_area])),
        ]),
    )