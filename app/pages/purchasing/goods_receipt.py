"""
app/pages/purchasing/goods_receipt.py
Pembelian → Penerimaan Barang (GR)
"""
from __future__ import annotations
import flet as ft
from typing import Optional, List, Dict
from datetime import date
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import (
    GoodsReceipt, GoodsReceiptLine,
    PurchaseOrder, PurchaseOrderLine,
    Warehouse, Branch,
)
from app.services.gr_service import GoodsReceiptService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    page_header, search_bar,
    confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS  = [("DRAFT","Draft"),("CONFIRMED","Dikonfirmasi"),("CANCELLED","Dibatalkan")]
_STATUS_COLOR = {"DRAFT": Colors.TEXT_MUTED, "CONFIRMED": Colors.SUCCESS, "CANCELLED": Colors.ERROR}


def _gr_badge(status):
    color = _STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    label = dict(_STATUS_OPTS).get(status, status)
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
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


def _load_po_lines(po_id: int) -> tuple[List[Dict], str, str]:
    """Return (lines, warehouse_id_str, branch_id_str)"""
    with SessionLocal() as db:
        po = db.query(PurchaseOrder).filter_by(id=po_id)\
               .options(
                   joinedload(PurchaseOrder.lines)
                       .joinedload(PurchaseOrderLine.product),
                   joinedload(PurchaseOrder.lines)
                       .joinedload(PurchaseOrderLine.uom),
               ).first()
        if not po:
            return [], "", ""
        lines = []
        for pol in (po.lines or []):
            lines.append({
                "pol_id":        pol.id,
                "product_id":    pol.product_id,
                "product_name":  pol.product.name if pol.product else "—",
                "product_code":  pol.product.code if pol.product else "",
                "tracking_type": pol.product.tracking_type if pol.product else "NONE",
                "uom_id":        pol.uom_id,
                "uom_code":      pol.uom.code if pol.uom else "—",
                "qty_ordered":   pol.qty_ordered,
                "qty_received":  pol.qty_received or 0,
                "unit_price":    pol.unit_price,
            })
        wh_id = str(po.warehouse_id) if po.warehouse_id else ""
        br_id = str(po.branch_id)    if po.branch_id    else ""
    return lines, wh_id, br_id


# ─────────────────────────────────────────────────────────────
# GR LINE TABLE (bukan class, cukup fungsi build)
# ─────────────────────────────────────────────────────────────
def _build_line_table(po_lines: List[Dict], is_replacement: bool = False) -> tuple[ft.Column, List[Dict]]:
    """
    Return (column_control, row_refs)
    row_refs: list of dict berisi field controls per baris
    Jika tracking_type=SERIAL, tampilkan area input nomor seri.
    """
    row_refs = []
    col = ft.Column(spacing=8)

    remaining = [
        ln for ln in po_lines
        if (ln["qty_ordered"] - ln["qty_received"]) > 0.001
    ]

    if not remaining:
        col.controls = [ft.Container(
            padding=ft.Padding.all(20),
            alignment=ft.Alignment(0, 0),
            content=ft.Text("Semua item pada PO ini sudah diterima penuh.",
                            size=13, color=Colors.TEXT_MUTED),
        )]
        return col, row_refs

    # Header
    col.controls.append(ft.Container(
        bgcolor=ft.Colors.with_opacity(0.05, Colors.TEXT_PRIMARY),
        border_radius=ft.border_radius.only(top_left=6, top_right=6),
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        content=ft.Row(spacing=6, controls=[
            ft.Container(width=200,
                content=ft.Text("Produk", size=11, color=Colors.TEXT_MUTED,
                                weight=ft.FontWeight.W_600)),
            ft.Container(width=55,
                content=ft.Text("Satuan",      size=11, color=Colors.TEXT_MUTED)),
            ft.Container(width=80,
                content=ft.Text("Qty PO",      size=11, color=Colors.TEXT_MUTED)),
            ft.Container(width=80,
                content=ft.Text("Sisa",        size=11, color=Colors.WARNING,
                                weight=ft.FontWeight.W_600)),
            ft.Container(width=100,
                content=ft.Text("✓ Diterima",  size=11, color=Colors.SUCCESS,
                                weight=ft.FontWeight.W_600)),
            ft.Container(width=90,
                content=ft.Text("✗ Ditolak",   size=11, color=Colors.ERROR)),
            ft.Container(width=140,
                content=ft.Text("Alasan Tolak",size=11, color=Colors.TEXT_MUTED)),
            ft.Container(width=120,
                content=ft.Text("No. Lot",     size=11, color=Colors.TEXT_MUTED)),
            ft.Container(width=110,
                content=ft.Text("Kadaluarsa",  size=11, color=Colors.TEXT_MUTED)),
            # SN tidak perlu kolom header — tampil sebagai blok di bawah row
        ]),
    ))

    for ln in remaining:
        qty_sisa     = round(ln["qty_ordered"] - ln["qty_received"], 4)
        is_serial    = ln.get("tracking_type") == "SERIAL"

        f_recv   = make_field("", str(qty_sisa),
                              keyboard_type=ft.KeyboardType.NUMBER, width=100)
        f_rej    = make_field("", "0",
                              keyboard_type=ft.KeyboardType.NUMBER, width=90)
        f_reason = make_field("", "", width=140)
        f_lot    = make_field("", "", width=120)
        f_expiry = make_field("", "", hint="YYYY-MM-DD", width=110)

        # ── Area Serial Number ────────────────────────────────
        sn_inputs: List[ft.TextField] = []
        sn_good_inputs: List[ft.TextField] = []
        sn_rej_inputs:  List[ft.TextField] = []
        # Untuk replacement: map SN lama → input SN baru
        sn_replace_inputs: dict = {}  # {sn_lama: TextField_baru}

        sn_good_col = ft.Column(spacing=4, visible=is_serial)
        sn_rej_col  = ft.Column(spacing=4, visible=is_serial)

        sn_old_list = ln.get("sn_old", [])  # SN lama dari return (hanya untuk replacement)

        btn_add_good = ft.TextButton(
            content=ft.Row(tight=True, spacing=4, controls=[
                ft.Icon(ft.Icons.ADD, size=14, color=Colors.SUCCESS),
                ft.Text("Tambah SN Bagus", size=12, color=Colors.SUCCESS),
            ]),
        ) if (is_serial and not is_replacement) else ft.Container()

        btn_add_rej = ft.TextButton(
            content=ft.Row(tight=True, spacing=4, controls=[
                ft.Icon(ft.Icons.ADD, size=14, color=Colors.ERROR),
                ft.Text("Tambah SN Rusak", size=12, color=Colors.ERROR),
            ]),
        ) if (is_serial and not is_replacement) else ft.Container()

        btn_generate = ft.FilledButton(
            content=ft.Row(tight=True, spacing=6, controls=[
                ft.Icon(ft.Icons.PLAYLIST_ADD_ROUNDED, size=15,
                        color=Colors.TEXT_ON_ACCENT),
                ft.Text("Generate Field SN", size=12,
                        color=Colors.TEXT_ON_ACCENT, weight=ft.FontWeight.W_600),
            ]),
            style=ft.ButtonStyle(
                bgcolor=Colors.ACCENT,
                shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                elevation=0,
            ),
        ) if (is_serial and not is_replacement) else ft.Container()

        if is_replacement and is_serial and sn_old_list:
            # Buat pasangan SN lama (label) → SN baru (input) per item
            replace_rows = []
            for sn_lama in sn_old_list:
                f_new_sn = ft.TextField(
                    label=f"Pengganti untuk {sn_lama}",
                    hint_text="Scan / ketik SN baru",
                    bgcolor=Colors.BG_INPUT,
                    border_color=ft.Colors.with_opacity(0.5, Colors.SUCCESS),
                    focused_border_color=Colors.SUCCESS,
                    color=Colors.TEXT_PRIMARY,
                    border_radius=Sizes.BTN_RADIUS,
                    dense=True, height=44,
                )
                sn_replace_inputs[sn_lama] = f_new_sn
                replace_rows.append(ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # SN lama (label)
                        ft.Container(
                            width=160,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.08, Colors.ERROR),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, Colors.ERROR)),
                            content=ft.Row(spacing=6, controls=[
                                ft.Icon(ft.Icons.UNDO, size=12, color=Colors.ERROR),
                                ft.Text(sn_lama, size=12, color=Colors.ERROR,
                                        font_family="monospace",
                                        weight=ft.FontWeight.W_600),
                            ]),
                        ),
                        ft.Icon(ft.Icons.ARROW_FORWARD, size=14, color=Colors.TEXT_MUTED),
                        # SN baru (input)
                        ft.Container(expand=True, content=f_new_sn),
                    ],
                ))

            sn_area = ft.Container(
                visible=True,
                border_radius=6,
                padding=ft.Padding.all(10),
                bgcolor=ft.Colors.with_opacity(0.03, Colors.SUCCESS),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, Colors.SUCCESS)),
                content=ft.Column(spacing=8, controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Icon(ft.Icons.SWAP_HORIZ, size=14, color=Colors.SUCCESS),
                        ft.Text("Pemetaan SN Lama → SN Baru", size=12,
                                color=Colors.SUCCESS, weight=ft.FontWeight.W_600),
                        ft.Text("(SN Lama = dikembalikan ke vendor, SN Baru = masuk stok)",
                                size=10, color=Colors.TEXT_MUTED),
                    ]),
                    *replace_rows,
                ]),
            )
        else:
            sn_area = ft.Container(
                visible=is_serial,
                border_radius=6,
                content=ft.Column(spacing=8, controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(spacing=6, controls=[
                                    ft.Icon(ft.Icons.QR_CODE_2, size=14, color=Colors.ACCENT),
                                    ft.Text(
                                        "Isi qty diterima & ditolak dulu, lalu klik Generate.",
                                        size=11, color=Colors.TEXT_MUTED,
                                    ),
                                ]),
                                btn_generate,
                            ],
                        ),
                    ),
                    ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Container(
                                expand=True,
                                bgcolor=ft.Colors.with_opacity(0.03, Colors.SUCCESS),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, Colors.SUCCESS)),
                                border_radius=6,
                                padding=ft.Padding.all(10),
                                content=ft.Column(spacing=6, controls=[
                                    ft.Row(spacing=8, controls=[
                                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=14,
                                                color=Colors.SUCCESS),
                                        ft.Text("SN Bagus (Masuk Stok)", size=12,
                                                color=Colors.SUCCESS, weight=ft.FontWeight.W_600),
                                    ]),
                                    sn_good_col,
                                    btn_add_good,
                                ]),
                            ),
                            ft.Container(
                                expand=True,
                                bgcolor=ft.Colors.with_opacity(0.03, Colors.ERROR),
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, Colors.ERROR)),
                                border_radius=6,
                                padding=ft.Padding.all(10),
                                content=ft.Column(spacing=6, controls=[
                                    ft.Row(spacing=8, controls=[
                                        ft.Icon(ft.Icons.CANCEL_OUTLINED, size=14,
                                                color=Colors.ERROR),
                                        ft.Text("SN Rusak (Tidak Masuk Stok)", size=12,
                                                color=Colors.ERROR, weight=ft.FontWeight.W_600),
                                    ]),
                                    sn_rej_col,
                                    btn_add_rej,
                                ]),
                            ),
                        ],
                    ),
                ]),
            )
        def _check_sn_limit(sgc=sn_good_col, sgi=sn_good_inputs,
                             src=sn_rej_col,  sri=sn_rej_inputs,
                             fr=f_recv, fj=f_rej,
                             bg=btn_add_good, br=btn_add_rej):
            """Disable tombol jika SN sudah cukup sesuai qty."""
            if not is_serial:
                return
            try:
                max_good = int(float(fr.value or 0)) - int(float(fj.value or 0))
                max_rej  = int(float(fj.value or 0))
            except ValueError:
                return
            max_good = max(0, max_good)
            max_rej  = max(0, max_rej)

            for btn, si, max_q, ok_color in [
                (bg, sgi, max_good, Colors.SUCCESS),
                (br, sri, max_rej,  Colors.ERROR),
            ]:
                if btn is None or not hasattr(btn, "content"):
                    continue
                at_limit = len(si) >= max_q
                btn.disabled = at_limit
                btn.content.controls[1].color = Colors.TEXT_MUTED if at_limit else ok_color
                btn.content.controls[0].color = Colors.TEXT_MUTED if at_limit else ok_color
                try: btn.update()
                except: pass

        # Tombol Generate SN — muncul setelah user isi qty diterima & ditolak
        def _generate_sn(e,
                         sgc=sn_good_col, sgi=sn_good_inputs,
                         src=sn_rej_col,  sri=sn_rej_inputs,
                         fr=f_recv, fj=f_rej,
                         chk=_check_sn_limit if is_serial else None):
            try:
                n_good = max(0, int(float(fr.value or 0)) - int(float(fj.value or 0)))
                n_rej  = max(0, int(float(fj.value or 0)))
            except ValueError:
                return

            # Reset kedua kolom
            sgi.clear(); sgc.controls.clear()
            sri.clear(); src.controls.clear()

            for _ in range(n_good):
                _add_sn_field(sgc, sgi, prefix="Bagus")
            for _ in range(n_rej):
                _add_sn_field(src, sri, prefix="Rusak")

            if chk: chk()
            try: sn_area.update()
            except: pass

        if is_serial:
            btn_generate.on_click = _generate_sn
            btn_add_good.on_click = lambda e, sc=sn_good_col, si=sn_good_inputs, chk=_check_sn_limit: (
                _add_sn_field(sc, si, prefix="Bagus"), chk()
            )
            btn_add_rej.on_click = lambda e, sc=sn_rej_col, si=sn_rej_inputs, chk=_check_sn_limit: (
                _add_sn_field(sc, si, prefix="Rusak"), chk()
            )

        rr = {
            "pol_id":           ln["pol_id"],
            "product_id":       ln["product_id"],
            "uom_id":           ln["uom_id"],
            "tracking_type":    ln.get("tracking_type", "NONE"),
            "qty_remaining":    qty_sisa,
            "unit_price":       ln["unit_price"],
            "product_name":     ln["product_name"],
            "f_recv":           f_recv,
            "f_rej":            f_rej,
            "f_reason":         f_reason,
            "f_lot":            f_lot,
            "f_expiry":         f_expiry,
            "sn_inputs":        sn_inputs,
            "sn_good_inputs":   sn_good_inputs,
            "sn_rej_inputs":    sn_rej_inputs,
            "sn_replace_inputs":sn_replace_inputs,  # {sn_lama: TextField_baru}
            "is_replacement":   is_replacement,
        }
        row_refs.append(rr)

        col.controls.append(ft.Container(
            border=ft.Border.all(1,
                ft.Colors.with_opacity(0.4, Colors.ACCENT) if is_serial else Colors.BORDER),
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Column(spacing=6, controls=[
                ft.Row(spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(width=200, content=ft.Column(
                            spacing=1, tight=True, controls=[
                                ft.Row(spacing=6, controls=[
                                    ft.Text(ln["product_name"], size=13,
                                            color=Colors.TEXT_PRIMARY,
                                            weight=ft.FontWeight.W_500,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            max_lines=1),
                                    *([ ft.Container(
                                        content=ft.Text("SERIAL", size=10,
                                                        color=Colors.ACCENT,
                                                        weight=ft.FontWeight.W_600),
                                        bgcolor=ft.Colors.with_opacity(0.1, Colors.ACCENT),
                                        border_radius=4,
                                        padding=ft.Padding.symmetric(horizontal=5, vertical=2),
                                    )] if is_serial else []),
                                ]),
                                ft.Text(ln["product_code"], size=11,
                                        color=Colors.TEXT_MUTED,
                                        font_family="monospace"),
                            ],
                        )),
                        ft.Container(width=55,
                            content=ft.Text(ln["uom_code"], size=12,
                                            color=Colors.TEXT_SECONDARY)),
                        ft.Container(width=80,
                            content=ft.Text(f"{ln['qty_ordered']:,.2f}", size=12,
                                            color=Colors.TEXT_SECONDARY)),
                        ft.Container(width=80,
                            content=ft.Text(f"{qty_sisa:,.2f}", size=12,
                                            color=Colors.WARNING,
                                            weight=ft.FontWeight.W_600)),
                        f_recv, f_rej, f_reason, f_lot, f_expiry,
                    ],
                ),
                # Area SN — hanya tampil jika SERIAL
                sn_area,
            ]),
        ))

    return col, row_refs


def _add_sn_field(sn_col: ft.Column, sn_inputs: list, prefix: str = "SN"):
    """Tambah satu field input serial number. prefix = 'Bagus' atau 'Rusak'."""
    idx         = len(sn_inputs) + 1
    color_map   = {"Bagus": Colors.SUCCESS, "Rusak": Colors.ERROR}
    border_color= color_map.get(prefix, Colors.ACCENT)
    tf  = ft.TextField(
        label=f"{prefix} #{idx}",
        hint_text="Scan atau ketik nomor seri",
        bgcolor=Colors.BG_INPUT,
        border_color=ft.Colors.with_opacity(0.5, border_color),
        focused_border_color=border_color,
        color=Colors.TEXT_PRIMARY,
        border_radius=Sizes.BTN_RADIUS,
        dense=True,
        height=42,
    )
    sn_inputs.append(tf)
    sn_col.controls.append(tf)
    try: sn_col.update()
    except: pass


def _validate_lines(row_refs: List[Dict]) -> tuple[bool, str, List[Dict]]:
    import json
    lines = []
    for i, rr in enumerate(row_refs):
        try:
            recv = float(rr["f_recv"].value or 0)
            rej  = float(rr["f_rej"].value  or 0)
        except ValueError:
            return False, f"Baris {i+1}: Qty tidak valid.", []
        if recv < 0 or rej < 0:
            return False, f"Baris {i+1}: Qty tidak boleh negatif.", []
        # recv sudah termasuk yang ditolak — rej adalah bagian dari recv
        if recv > rr["qty_remaining"] + 0.001:
            return False, (f"Baris {i+1} ({rr['product_name']}): "
                           f"Qty diterima ({recv:,.2f}) melebihi sisa "
                           f"({rr['qty_remaining']:,.2f})."), []
        if rej > recv + 0.001:
            return False, (f"Baris {i+1} ({rr['product_name']}): "
                           f"Qty ditolak ({rej:,.2f}) tidak boleh melebihi "
                           f"qty diterima ({recv:,.2f})."), []
        if recv == 0 and rej == 0:
            continue

        # Validasi & kumpulkan Serial Numbers
        sn_good_list    = []
        sn_rej_list     = []
        sn_replace_map  = {}  # {sn_lama: sn_baru}

        if rr.get("tracking_type") == "SERIAL":
            if rr.get("is_replacement") and rr.get("sn_replace_inputs"):
                # Mode replacement: validasi setiap SN baru
                for sn_lama, tf in rr["sn_replace_inputs"].items():
                    sn_baru = (tf.value or "").strip()
                    if not sn_baru:
                        return False, (
                            f"Baris {i+1}: SN pengganti untuk '{sn_lama}' belum diisi."
                        ), []
                    if sn_baru in sn_replace_map.values():
                        return False, f"Baris {i+1}: SN '{sn_baru}' duplikat.", []
                    sn_replace_map[sn_lama] = sn_baru
                    sn_good_list.append(sn_baru)
            else:
                # Mode normal: validasi SN bagus & rusak
                net_recv = recv - rej
                for j, tf in enumerate(rr.get("sn_good_inputs", [])):
                    sn_val = (tf.value or "").strip()
                    if not sn_val:
                        return False, (f"Baris {i+1}: SN Bagus #{j+1} belum diisi."), []
                    if sn_val in sn_good_list or sn_val in sn_rej_list:
                        return False, f"Baris {i+1}: SN '{sn_val}' duplikat.", []
                    sn_good_list.append(sn_val)

                for j, tf in enumerate(rr.get("sn_rej_inputs", [])):
                    sn_val = (tf.value or "").strip()
                    if not sn_val:
                        return False, (f"Baris {i+1}: SN Rusak #{j+1} belum diisi."), []
                    if sn_val in sn_good_list or sn_val in sn_rej_list:
                        return False, f"Baris {i+1}: SN '{sn_val}' duplikat.", []
                    sn_rej_list.append(sn_val)

                if len(sn_good_list) != int(net_recv):
                    return False, (
                        f"Baris {i+1}: Jumlah SN Bagus ({len(sn_good_list)}) "
                        f"harus sama dengan net diterima ({int(net_recv)})."
                    ), []
                if len(sn_rej_list) != int(rej):
                    return False, (
                        f"Baris {i+1}: Jumlah SN Rusak ({len(sn_rej_list)}) "
                        f"harus sama dengan qty ditolak ({int(rej)})."
                    ), []

        # Simpan sebagai JSON — format berbeda untuk normal vs replacement
        sn_payload = None
        if sn_replace_map:
            # Format replacement: {"replacement": {"SN_LAMA": "SN_BARU"}}
            sn_payload = json.dumps({"replacement": sn_replace_map})
        elif sn_good_list or sn_rej_list:
            # Format normal: {"good": [...], "rejected": [...]}
            sn_payload = json.dumps({"good": sn_good_list, "rejected": sn_rej_list})

        lines.append({
            "pol_id":            rr["pol_id"],
            "product_id":        rr["product_id"],
            "uom_id":            rr["uom_id"],
            "qty_received":      recv,
            "qty_rejected":      rej,
            "rejection_reason":  rr["f_reason"].value or "",
            "lot_number":        rr["f_lot"].value or "",
            "expiry_date":       _parse_date(rr["f_expiry"].value),
            "unit_cost":         rr["unit_price"],
            "serial_numbers_input": sn_payload,
        })
    if not lines:
        return False, "Tidak ada item yang diterima (qty semua nol).", []
    return True, "", lines


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession, gr_id: Optional[int], on_saved,
                 is_replacement_mode: bool = False):
    is_edit = gr_id is not None

    with SessionLocal() as db:
        # PO normal
        confirmed_pos = GoodsReceiptService.get_confirmed_pos(db, session.company_id)
        # PO dari return (replacement)
        replacement_entries = GoodsReceiptService.get_replacement_pos(db, session.company_id)

        warehouses = db.query(Warehouse)\
            .join(Branch, Warehouse.branch_id == Branch.id)\
            .filter(Branch.company_id == session.company_id,
                    Warehouse.is_active == True).all()

        # Opts PO normal
        normal_po_opts = []
        for po in confirmed_pos:
            sisa = sum(
                max(0, (ln.qty_ordered or 0) - (ln.qty_received or 0))
                for ln in (po.lines or [])
            )
            # Skip PO yang sudah tidak ada sisa (double check)
            if sisa <= 0.001:
                continue
            status_label = {
                "CONFIRMED": "Belum ada GR",
                "PARTIAL":   "Penerimaan sebagian",
            }.get(po.status, po.status)
            normal_po_opts.append((
                str(po.id),
                f"{po.po_number} — {po.vendor.name if po.vendor else '—'}"
                f"  [{status_label}]  sisa {sisa:,.0f}"
            ))

        # Opts PO replacement — label tampilkan nomor return
        replace_po_opts = []
        replace_po_map  = {}  # po_id → return_id
        for entry in replacement_entries:
            po  = entry["po"]
            rtn = entry["return"]
            qty_return = sum(ln.qty_return for ln in rtn.lines)
            replace_po_opts.append((
                str(po.id),
                f"{po.po_number} — {po.vendor.name if po.vendor else '—'}"
                f"  [Pengganti {rtn.return_number}]  qty {qty_return:,.0f}"
            ))
            replace_po_map[str(po.id)] = rtn.id

        wh_opts = [(str(w.id), f"{w.name} ({w.branch.name if w.branch else '—'})")
                   for w in warehouses]

        d_po_id     = ""
        d_wh_id     = ""
        d_br_id     = str(session.branch_id) if hasattr(session, "branch_id") and session.branch_id else ""
        d_date      = date.today().strftime("%Y-%m-%d")
        d_do_number = ""
        d_notes     = ""
        d_gr_number = ""
        init_po_lines: List[Dict] = []

        if is_edit:
            gr = GoodsReceiptService.get_by_id(db, gr_id)
            if gr:
                d_po_id     = str(gr.po_id)
                d_wh_id     = str(gr.warehouse_id)
                d_br_id     = str(gr.branch_id)
                d_date      = _fmt_date(gr.receipt_date)
                d_do_number = gr.vendor_do_number or ""
                d_notes     = gr.notes or ""
                d_gr_number = gr.gr_number
                po = gr.po
                for pol in (po.lines if po else []):
                    init_po_lines.append({
                        "pol_id":       pol.id,
                        "product_id":   pol.product_id,
                        "product_name": pol.product.name if pol.product else "—",
                        "product_code": pol.product.code if pol.product else "",
                        "uom_id":       pol.uom_id,
                        "uom_code":     pol.uom.code if pol.uom else "—",
                        "qty_ordered":  pol.qty_ordered,
                        "qty_received": pol.qty_received or 0,
                        "unit_price":   pol.unit_price,
                    })

    # State
    state = {
        "br_id":        d_br_id,
        "row_refs":     [],
        "is_replacement": is_replacement_mode,
        "return_id":    None,
    }

    # ── Toggle Normal vs Replacement ─────────────────────────
    mode_tabs = ft.Container(
        visible=not is_edit,
        padding=ft.Padding.only(bottom=8),
        content=ft.Row(spacing=0, controls=[
            ft.Container(
                height=34,
                padding=ft.Padding.symmetric(horizontal=16),
                border_radius=ft.border_radius.only(top_left=8, bottom_left=8),
                bgcolor=Colors.ACCENT if not state["is_replacement"] else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, Colors.ACCENT),
                on_click=lambda e: _switch_mode(False),
                ink=True,
                content=ft.Text("Penerimaan Normal", size=12,
                    color=Colors.TEXT_ON_ACCENT if not state["is_replacement"] else Colors.ACCENT,
                    weight=ft.FontWeight.W_600),
            ),
            ft.Container(
                height=34,
                padding=ft.Padding.symmetric(horizontal=16),
                border_radius=ft.border_radius.only(top_right=8, bottom_right=8),
                bgcolor=Colors.WARNING if state["is_replacement"] else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, Colors.WARNING),
                on_click=lambda e: _switch_mode(True),
                ink=True,
                content=ft.Text("Penerimaan Pengganti (Return)", size=12,
                    color=Colors.TEXT_ON_ACCENT if state["is_replacement"] else Colors.WARNING,
                    weight=ft.FontWeight.W_600),
            ),
        ]),
    )

    cur_po_opts = replace_po_opts if state["is_replacement"] else normal_po_opts

    # Fields
    f_po   = make_dropdown(
        "Purchase Order *" if not state["is_replacement"] else "PO Pengganti *",
        cur_po_opts, d_po_id
    )
    f_wh   = make_dropdown("Gudang Tujuan *",  wh_opts, d_wh_id)
    f_date = make_field("Tanggal Terima *", d_date, hint="YYYY-MM-DD", width=160)
    f_do   = make_field("No. Surat Jalan Vendor", d_do_number,
                        hint="Nomor DO dari vendor", width=220)
    f_notes= make_field("Catatan", d_notes, multiline=True, min_lines=2, max_lines=3)

    # Area tabel lines — diisi saat PO dipilih
    lines_area = ft.Column(spacing=6)
    dlg_ref    = {"dlg": None}  # ref ke dialog setelah dibuat

    def _refresh_lines(po_lines: List[Dict]):
        table, row_refs = _build_line_table(po_lines, is_replacement=state["is_replacement"])
        state["row_refs"] = row_refs
        lines_area.controls = [table]
        # Update dialog root — lebih reliable dari update child
        try:
            if dlg_ref["dlg"]:
                dlg_ref["dlg"].update()
            else:
                lines_area.update()
        except Exception:
            pass

    # Load awal jika edit
    if is_edit and init_po_lines:
        _refresh_lines(init_po_lines)

    def _switch_mode(replacement: bool):
        state["is_replacement"] = replacement
        state["return_id"]      = None
        f_po.label   = "PO Pengganti *" if replacement else "Purchase Order *"
        f_po.options = [ft.dropdown.Option(key=v, text=t)
                        for v, t in (replace_po_opts if replacement else normal_po_opts)]
        f_po.value   = None
        lines_area.controls = []
        state["row_refs"]    = []
        # Update tab warna
        normal_tab     = mode_tabs.content.controls[0]
        replace_tab    = mode_tabs.content.controls[1]
        normal_tab.bgcolor  = Colors.ACCENT if not replacement else ft.Colors.TRANSPARENT
        replace_tab.bgcolor = Colors.WARNING if replacement else ft.Colors.TRANSPARENT
        normal_tab.content.color  = Colors.TEXT_ON_ACCENT if not replacement else Colors.ACCENT
        replace_tab.content.color = Colors.TEXT_ON_ACCENT if replacement else Colors.WARNING
        try:
            mode_tabs.update()
            f_po.update()
            lines_area.update()
        except: pass

    def on_po_change(e):
        if not f_po.value:
            return
        # Set return_id jika mode replacement
        if state["is_replacement"] and f_po.value in replace_po_map:
            state["return_id"] = replace_po_map[f_po.value]
        else:
            state["return_id"] = None

        po_lines, wh_id, br_id = _load_po_lines(int(f_po.value))

        # Untuk replacement: filter hanya produk dari return lines
        # dan sertakan SN lama (RETURNED) per produk
        if state["is_replacement"] and state["return_id"]:
            import json as _json
            with SessionLocal() as db:
                from app.models import PurchaseReturnLine, GoodsReceiptLine as GRLine
                ret_lines = db.query(PurchaseReturnLine)                               .filter_by(return_id=state["return_id"]).all()
                # {product_id: {"qty": float, "sn_old": [...]}}
                ret_map = {}
                for rl in ret_lines:
                    sn_old = []
                    if rl.serial_numbers:
                        try: sn_old = _json.loads(rl.serial_numbers)
                        except: pass
                    ret_map[rl.product_id] = {
                        "qty":    rl.qty_return,
                        "sn_old": sn_old,
                    }
            filtered = []
            for ln in po_lines:
                if ln["product_id"] in ret_map:
                    ln = dict(ln)
                    entry = ret_map[ln["product_id"]]
                    # qty_sisa = qty_return (bukan dari POL)
                    ln["qty_received"] = ln["qty_ordered"] - entry["qty"]
                    ln["sn_old"]       = entry["sn_old"]  # SN lama untuk ditampilkan
                    filtered.append(ln)
            po_lines = filtered

        if wh_id and not f_wh.value:
            f_wh.value = wh_id
            try: f_wh.update()
            except: pass
        if br_id:
            state["br_id"] = br_id
        _refresh_lines(po_lines)

    f_po.on_select = on_po_change

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_po.value:
            show_err("Purchase Order wajib dipilih."); return
        if not f_wh.value:
            show_err("Gudang tujuan wajib dipilih."); return
        if not state["br_id"]:
            show_err("Cabang tidak terdeteksi. Pilih PO dahulu."); return
        recv_date = _parse_date(f_date.value)
        if not recv_date:
            show_err("Tanggal tidak valid."); return

        valid, errmsg, lines = _validate_lines(state["row_refs"])
        if not valid:
            show_err(errmsg); return

        data = {
            "branch_id":        state["br_id"],
            "po_id":            f_po.value,
            "warehouse_id":     f_wh.value,
            "receipt_date":     recv_date,
            "vendor_do_number": f_do.value,
            "notes":            f_notes.value,
            "is_replacement":   state["is_replacement"],
            "return_id":        state["return_id"],
        }

        with SessionLocal() as db:
            ok, msg, _ = GoodsReceiptService.create(
                db, session.company_id, session.user_id, data, lines)

        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    title = f"Edit GR — {d_gr_number}" if is_edit else "Buat Penerimaan Barang"

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.MOVE_TO_INBOX, color=Colors.ACCENT, size=20),
                    ft.Text(title, color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=1100, height=560,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
                err,
                section_card("Header Penerimaan", [
                    mode_tabs,
                    f_po,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":5}, content=f_wh),
                        ft.Container(col={"xs":12,"sm":3}, content=f_date),
                        ft.Container(col={"xs":12,"sm":4}, content=f_do),
                    ]),
                    f_notes,
                ]),
                section_card("Item Diterima", [
                    ft.Text("Pilih PO di atas untuk memuat daftar item.",
                            size=12, color=Colors.TEXT_MUTED,
                            visible=len(state["row_refs"]) == 0),
                    lines_area,
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
# DETAIL DIALOG
# ─────────────────────────────────────────────────────────────
def _detail_dialog(page, session: AppSession, gr_id: int, on_saved):
    with SessionLocal() as db:
        gr = GoodsReceiptService.get_by_id(db, gr_id)
        if not gr:
            show_snack(page, "GR tidak ditemukan.", False); return

        gr_number   = gr.gr_number
        gr_status   = gr.status
        po_number   = gr.po.po_number if gr.po else "—"
        vendor_name = gr.po.vendor.name if (gr.po and gr.po.vendor) else "—"
        wh_name     = gr.warehouse.name if gr.warehouse else "—"
        recv_date   = _fmt_date(gr.receipt_date)
        do_number   = gr.vendor_do_number or "—"
        notes_val   = gr.notes or ""

        lines_data = [{
            "product_name":    ln.product.name if ln.product else "—",
            "product_code":    ln.product.code if ln.product else "",
            "uom_code":        ln.uom.code if ln.uom else "—",
            "qty_received":    ln.qty_received,
            "qty_rejected":    ln.qty_rejected,
            "rejection_reason":ln.rejection_reason or "",
            "lot_number":      ln.lot_number or "—",
            "expiry_date":     _fmt_date(ln.expiry_date) or "—",
            "unit_cost":       ln.unit_cost or 0,
        } for ln in (gr.lines or [])]

    line_rows = []
    for i, ld in enumerate(lines_data):
        net = ld["qty_received"] - ld["qty_rejected"]
        line_rows.append(ft.Container(
            border=ft.Border.all(1, Colors.BORDER), border_radius=4,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Row(spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(width=28,
                        content=ft.Text(str(i+1), size=12, color=Colors.TEXT_MUTED)),
                    ft.Container(expand=True, content=ft.Column(spacing=1, tight=True, controls=[
                        ft.Text(ld["product_name"], size=13, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_500),
                        ft.Text(ld["product_code"], size=11, color=Colors.TEXT_MUTED,
                                font_family="monospace"),
                    ])),
                    ft.Container(width=55,
                        content=ft.Text(ld["uom_code"], size=12, color=Colors.TEXT_SECONDARY)),
                    ft.Container(width=90,
                        content=ft.Text(f"{ld['qty_received']:,.2f}", size=12,
                                        color=Colors.SUCCESS, weight=ft.FontWeight.W_600)),
                    ft.Container(width=80,
                        content=ft.Text(
                            f"{ld['qty_rejected']:,.2f}" if ld["qty_rejected"] else "—",
                            size=12, color=Colors.ERROR)),
                    ft.Container(width=90,
                        content=ft.Text(f"{net:,.2f}", size=12,
                                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600)),
                    ft.Container(width=110,
                        content=ft.Text(f"Rp {ld['unit_cost']:,.0f}", size=12,
                                        color=Colors.TEXT_SECONDARY)),
                    ft.Container(width=110,
                        content=ft.Text(ld["lot_number"], size=12, color=Colors.TEXT_MUTED)),
                    ft.Container(width=100,
                        content=ft.Text(ld["expiry_date"], size=12, color=Colors.TEXT_MUTED)),
                ],
            ),
        ))

    def do_confirm(e):
        with SessionLocal() as db:
            ok, msg = GoodsReceiptService.confirm(db, gr_id)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    actions = [
        ft.Button("Tutup", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                  on_click=lambda e: (setattr(dlg,"open",False), page.update())),
    ]
    if gr_status == "DRAFT":
        actions.append(ft.Button(
            "Konfirmasi & Update Stok",
            bgcolor=Colors.SUCCESS, color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                elevation=0),
            on_click=do_confirm,
        ))

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=4, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.MOVE_TO_INBOX, color=Colors.ACCENT, size=18),
                        ft.Text(gr_number, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                        _gr_badge(gr_status),
                    ]),
                    ft.Row(spacing=16, controls=[
                        ft.Text(f"PO: {po_number}",     size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Vendor: {vendor_name}",size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Gudang: {wh_name}",   size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Tgl: {recv_date}",    size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"DO: {do_number}",     size=11, color=Colors.TEXT_MUTED),
                    ]),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=900, height=480,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8, controls=[
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Row(spacing=8, controls=[
                        ft.Container(width=28),
                        ft.Container(expand=True,
                            content=ft.Text("Produk", size=11, color=Colors.TEXT_MUTED,
                                            weight=ft.FontWeight.W_600)),
                        ft.Container(width=55,  content=ft.Text("Satuan",    size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=90,  content=ft.Text("Diterima",  size=11, color=Colors.SUCCESS, weight=ft.FontWeight.W_600)),
                        ft.Container(width=80,  content=ft.Text("Ditolak",   size=11, color=Colors.ERROR)),
                        ft.Container(width=90,  content=ft.Text("Net Masuk", size=11, color=Colors.TEXT_MUTED, weight=ft.FontWeight.W_600)),
                        ft.Container(width=110, content=ft.Text("Harga/unit", size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=110, content=ft.Text("No. Lot",   size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=100, content=ft.Text("Kadaluarsa",size=11, color=Colors.TEXT_MUTED)),
                    ]),
                ),
                *line_rows,
                ft.Container(
                    visible=bool(notes_val),
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=4, padding=ft.Padding.all(10),
                    content=ft.Column(spacing=4, controls=[
                        ft.Text("Catatan:", size=11, color=Colors.TEXT_MUTED,
                                weight=ft.FontWeight.W_600),
                        ft.Text(notes_val, size=12, color=Colors.TEXT_SECONDARY),
                    ]),
                ),
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=actions,
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


# ─────────────────────────────────────────────────────────────
# TABLE + MAIN PAGE
# ─────────────────────────────────────────────────────────────
def _grs_to_dicts(grs) -> List[Dict]:
    result = []
    for gr in grs:
        result.append({
            "id":            gr.id,
            "gr_number":     gr.gr_number,
            "status":        gr.status,
            "is_replacement":gr.is_replacement,
            "po_number":     gr.po.po_number if gr.po else "—",
            "vendor_name":   gr.po.vendor.name if (gr.po and gr.po.vendor) else "—",
            "warehouse_name":gr.warehouse.name if gr.warehouse else "—",
            "receipt_date":  _fmt_date(gr.receipt_date),
            "do_number":     gr.vendor_do_number or "—",
            "item_count":    len(gr.lines or []),
            "total_recv":    sum(ln.qty_received for ln in (gr.lines or [])),
        })
    return result


def _build_rows(gr_data, page, session, refresh):
    rows = []
    for d in gr_data:
        actions = [
            action_btn(ft.Icons.VISIBILITY_OUTLINED, "Detail",
                lambda e, gid=d["id"]: _detail_dialog(page, session, gid, refresh),
                Colors.INFO),
        ]
        if d["status"] == "DRAFT":
            actions += [
                action_btn(ft.Icons.CHECK_CIRCLE_OUTLINE, "Konfirmasi",
                    lambda e, gid=d["id"], gno=d["gr_number"]: confirm_dialog(
                        page, "Konfirmasi GR",
                        f"Konfirmasi {gno}? Stok akan diperbarui.",
                        lambda: _confirm(gid, page, refresh),
                        "Ya, Konfirmasi", Colors.SUCCESS),
                    Colors.SUCCESS),
                action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, gid=d["id"], gno=d["gr_number"]: confirm_dialog(
                        page, "Hapus GR", f"Hapus {gno}?",
                        lambda: _delete(gid, page, refresh)),
                    Colors.ERROR),
                action_btn(ft.Icons.CANCEL_OUTLINED, "Batalkan",
                    lambda e, gid=d["id"], gno=d["gr_number"]: confirm_dialog(
                        page, "Batalkan GR", f"Batalkan {gno}?",
                        lambda: _cancel(gid, page, refresh),
                        "Ya, Batalkan", Colors.WARNING),
                    Colors.WARNING),
            ]

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Row(spacing=6, tight=True, controls=[
                    ft.Text(d["gr_number"], size=13, weight=ft.FontWeight.W_600,
                            color=Colors.TEXT_PRIMARY, font_family="monospace"),
                    ft.Container(
                        visible=bool(d.get("is_replacement")),
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                        bgcolor=ft.Colors.with_opacity(0.12, Colors.WARNING),
                        content=ft.Text("PENGGANTI", size=9,
                                        color=Colors.WARNING, weight=ft.FontWeight.W_700),
                    ),
                ]),
                ft.Text(d["po_number"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["vendor_name"],   size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["warehouse_name"],size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["receipt_date"],  size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"{d['item_count']} item", size=12, color=Colors.TEXT_PRIMARY),
                ft.Text(f"Total: {d['total_recv']:,.0f}", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(_gr_badge(d["status"])),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def _confirm(gid, page, refresh):
    with SessionLocal() as db:
        ok, msg = GoodsReceiptService.confirm(db, gid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _cancel(gid, page, refresh):
    with SessionLocal() as db:
        ok, msg = GoodsReceiptService.cancel(db, gid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _delete(gid, page, refresh):
    with SessionLocal() as db:
        ok, msg = GoodsReceiptService.delete(db, gid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _filter_bar(active_status, on_filter):
    filters = [("","Semua")] + _STATUS_OPTS
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


def GoodsReceiptPage(page, session: AppSession) -> ft.Control:
    search_val  = {"q": ""}
    status_val  = {"v": ""}
    filter_area = ft.Container()

    def _load():
        with SessionLocal() as db:
            grs = GoodsReceiptService.get_all(
                db, session.company_id, search_val["q"], status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _grs_to_dicts(grs)

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("No. GR / PO",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Vendor",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Gudang",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tgl Terima",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item / Qty",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=60, column_spacing=16,
        columns=COLS,
        rows=_build_rows(initial, page, session, lambda: None),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada penerimaan barang.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def refresh():
        data = _load()
        table.rows = _build_rows(data, page, session, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada GR ditemukan.")]
        filter_area.content = _filter_bar(status_val, on_filter)
        try: table_area.update(); filter_area.update()
        except: pass

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    def on_filter(val):
        status_val["v"] = val
        refresh()

    filter_area.content = _filter_bar(status_val, on_filter)
    table.rows = _build_rows(initial, page, session, refresh)

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=0, controls=[
            page_header(
                "Penerimaan Barang",
                "Catat penerimaan barang dari Purchase Order",
                "Buat GR Baru",
                on_action=lambda: _form_dialog(page, session, None, refresh),
                action_icon=ft.Icons.ADD,
            ),
            ft.Container(
                padding=ft.Padding.only(bottom=8),
                content=ft.Row(spacing=8, controls=[
                    ft.TextButton(
                        content=ft.Row(tight=True, spacing=6, controls=[
                            ft.Icon(ft.Icons.SWAP_HORIZ, size=14, color=Colors.WARNING),
                            ft.Text("Terima Barang Pengganti (Return)",
                                    size=12, color=Colors.WARNING),
                        ]),
                        on_click=lambda e: _form_dialog(
                            page, session, None, refresh,
                            is_replacement_mode=True),
                    ),
                ]),
            ),
            ft.Container(padding=ft.Padding.only(bottom=12), content=filter_area),
            ft.Row(controls=[search_bar("Cari nomor GR atau surat jalan...", on_search)]),
            ft.Container(height=12),
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[table_area]),
            ),
        ]),
    )