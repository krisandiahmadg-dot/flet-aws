"""
app/pages/purchasing/credit_note.py
Pemantauan Credit Note dari Purchase Return

Menampilkan:
  - Dashboard ringkasan (total CN, nilai, per resolusi)
  - Tabel semua credit note (CREDIT_NOTE + COMBINATION)
  - Detail dialog dengan visualisasi alur mekanisme pengembalian
  - Filter vendor, resolusi, tanggal
"""
from __future__ import annotations
import flet as ft
import json
from typing import Optional, List, Dict
from datetime import date, datetime

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.database import SessionLocal
from app.models import (
    PurchaseReturn, PurchaseReturnLine,
    GoodsReceipt, GoodsReceiptLine,
    PurchaseOrder, Vendor,
)
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    page_header, search_bar,
    show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes


# ─────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────
_RESOLUTION_OPTS = [
    ("", "Semua Resolusi"),
    ("CREDIT_NOTE", "Credit Note"),
    ("COMBINATION", "Kombinasi"),
]
_RESOLUTION_COLOR = {
    "CREDIT_NOTE": Colors.INFO,
    "COMBINATION": Colors.WARNING,
    "REPLACEMENT": Colors.SUCCESS,
}
_RESOLUTION_LABEL = {
    "CREDIT_NOTE": "Credit Note",
    "COMBINATION": "Kombinasi",
    "REPLACEMENT": "Replacement",
}
_STATUS_COLOR = {
    "DRAFT":     Colors.TEXT_MUTED,
    "CONFIRMED": Colors.WARNING,
    "SENT":      Colors.INFO,
    "COMPLETED": Colors.SUCCESS,
    "CANCELLED": Colors.ERROR,
}
_STATUS_LABEL = {
    "DRAFT":     "Draft",
    "CONFIRMED": "Dikonfirmasi",
    "SENT":      "Dikirim",
    "COMPLETED": "Selesai",
    "CANCELLED": "Dibatalkan",
}


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def _fmt_date(d) -> str:
    if not d: return "—"
    try:
        return d.strftime("%d %b %Y") if hasattr(d, "strftime") else str(d)[:10]
    except Exception:
        return "—"


def _fmt_idr(val) -> str:
    try:
        return f"Rp {float(val or 0):,.0f}"
    except Exception:
        return "Rp 0"


def _resolution_badge(resolution: str, size: int = 11) -> ft.Container:
    color = _RESOLUTION_COLOR.get(resolution, Colors.TEXT_MUTED)
    label = _RESOLUTION_LABEL.get(resolution, resolution)
    icon_map = {
        "CREDIT_NOTE": ft.Icons.RECEIPT_OUTLINED,
        "COMBINATION": ft.Icons.TUNE,
        "REPLACEMENT": ft.Icons.SWAP_HORIZ,
    }
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.1, color),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, color)),
        content=ft.Row(spacing=4, tight=True, controls=[
            ft.Icon(icon_map.get(resolution, ft.Icons.HELP_OUTLINE), size=10, color=color),
            ft.Text(label, size=size, color=color, weight=ft.FontWeight.W_600),
        ]),
    )


def _status_dot(status: str) -> ft.Container:
    color = _STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    return ft.Container(
        width=8, height=8, border_radius=4,
        bgcolor=color,
    )


# ─────────────────────────────────────────────────────────────
# QUERY SERVICE (inline — tidak ubah service yang ada)
# ─────────────────────────────────────────────────────────────
def _get_credit_notes(
    db: Session,
    company_id: int,
    search: str = "",
    resolution: str = "",
    vendor_id: Optional[int] = None,
) -> List[PurchaseReturn]:
    """
    Ambil semua return dengan credit note (CREDIT_NOTE atau COMBINATION).
    Hanya yang sudah COMPLETED karena credit note baru ada setelah selesai.
    """
    q = db.query(PurchaseReturn)\
          .filter(
              PurchaseReturn.company_id == company_id,
              PurchaseReturn.status == "COMPLETED",
              PurchaseReturn.resolution.in_(["CREDIT_NOTE", "COMBINATION"]),
          )\
          .options(
              joinedload(PurchaseReturn.vendor),
              joinedload(PurchaseReturn.branch),
              joinedload(PurchaseReturn.warehouse),
              joinedload(PurchaseReturn.gr).joinedload(GoodsReceipt.po),
              joinedload(PurchaseReturn.creator),
              joinedload(PurchaseReturn.confirmer),
              joinedload(PurchaseReturn.completer),
              joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.product),
              joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.uom),
          )

    if resolution:
        q = q.filter(PurchaseReturn.resolution == resolution)
    if vendor_id:
        q = q.filter(PurchaseReturn.vendor_id == vendor_id)
    if search:
        q = q.filter(or_(
            PurchaseReturn.return_number.ilike(f"%{search}%"),
            PurchaseReturn.credit_note_number.ilike(f"%{search}%"),
        ))
    return q.order_by(PurchaseReturn.completed_at.desc()).all()


def _get_summary(db: Session, company_id: int) -> Dict:
    """Statistik ringkasan credit note."""
    rows = db.query(
        PurchaseReturn.resolution,
        func.count(PurchaseReturn.id).label("cnt"),
        func.coalesce(func.sum(PurchaseReturn.credit_note_amount), 0).label("total_cn"),
        func.coalesce(func.sum(PurchaseReturn.total_amount), 0).label("total_return"),
        func.coalesce(func.sum(PurchaseReturn.replacement_qty), 0).label("total_replace"),
    ).filter(
        PurchaseReturn.company_id == company_id,
        PurchaseReturn.status == "COMPLETED",
        PurchaseReturn.resolution.in_(["CREDIT_NOTE", "COMBINATION"]),
    ).group_by(PurchaseReturn.resolution).all()

    summary = {
        "total_count":  0,
        "total_cn_amt": 0.0,
        "total_return": 0.0,
        "cn_count":     0,
        "combo_count":  0,
        "cn_amt":       0.0,
        "combo_cn_amt": 0.0,
        "combo_rep_qty":0.0,
    }
    for r in rows:
        summary["total_count"]  += r.cnt
        summary["total_cn_amt"] += float(r.total_cn)
        summary["total_return"] += float(r.total_return)
        if r.resolution == "CREDIT_NOTE":
            summary["cn_count"] = r.cnt
            summary["cn_amt"]   = float(r.total_cn)
        elif r.resolution == "COMBINATION":
            summary["combo_count"]   = r.cnt
            summary["combo_cn_amt"]  = float(r.total_cn)
            summary["combo_rep_qty"] = float(r.total_replace)
    return summary


def _get_vendors(db: Session, company_id: int) -> List[Vendor]:
    """Ambil daftar vendor yang pernah beri credit note."""
    vendor_ids = db.query(PurchaseReturn.vendor_id)\
                   .filter(
                       PurchaseReturn.company_id == company_id,
                       PurchaseReturn.status == "COMPLETED",
                       PurchaseReturn.resolution.in_(["CREDIT_NOTE", "COMBINATION"]),
                   ).distinct().all()
    ids = [v[0] for v in vendor_ids if v[0]]
    if not ids:
        return []
    return db.query(Vendor).filter(Vendor.id.in_(ids)).order_by(Vendor.name).all()


def _check_replacement_gr(db: Session, return_id: int) -> Optional[GoodsReceipt]:
    """Cek apakah sudah ada GR replacement untuk return ini."""
    return db.query(GoodsReceipt).filter(
        GoodsReceipt.return_id == return_id,
        GoodsReceipt.is_replacement == True,
        GoodsReceipt.status.in_(["DRAFT", "CONFIRMED"]),
    ).first()


# ─────────────────────────────────────────────────────────────
# STATS CARD
# ─────────────────────────────────────────────────────────────
def _stat_card(
    icon: str,
    icon_color: str,
    label: str,
    value: str,
    sub: str = "",
    width: float = 220,
) -> ft.Container:
    return ft.Container(
        width=width, height=100,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        padding=ft.Padding.all(16),
        content=ft.Row(
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=44, height=44, border_radius=22,
                    bgcolor=ft.Colors.with_opacity(0.12, icon_color),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=20, color=icon_color),
                ),
                ft.Column(spacing=2, tight=True, controls=[
                    ft.Text(label, size=11, color=Colors.TEXT_MUTED),
                    ft.Text(value, size=18, weight=ft.FontWeight.W_700,
                            color=Colors.TEXT_PRIMARY),
                    ft.Text(sub, size=10, color=Colors.TEXT_MUTED) if sub else ft.Container(),
                ]),
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────
# MEKANISME ALUR — visual timeline
# ─────────────────────────────────────────────────────────────
def _mechanism_flow(rtn, replacement_gr: Optional[GoodsReceipt]) -> ft.Container:
    """
    Visualisasi alur mekanisme pengembalian:
    Return DRAFT → CONFIRMED → SENT → COMPLETED
    Lalu cabang: Credit Note diterima / GR Replacement / Keduanya
    """
    resolution = rtn.resolution or ""

    # ── Step builder ─────────────────────────────────────────
    def _step(num, title, desc, done: bool, active: bool = False, is_last: bool = False):
        color = Colors.SUCCESS if done else (Colors.ACCENT if active else Colors.TEXT_MUTED)
        icon  = ft.Icons.CHECK_CIRCLE if done else (
            ft.Icons.RADIO_BUTTON_CHECKED if active else ft.Icons.RADIO_BUTTON_UNCHECKED)
        return ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0, width=32,
                    controls=[
                        ft.Container(
                            width=28, height=28, border_radius=14,
                            bgcolor=ft.Colors.with_opacity(0.15, color),
                            border=ft.Border.all(2, color),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, size=14, color=color),
                        ),
                        ft.Container(
                            width=2, height=32,
                            bgcolor=ft.Colors.with_opacity(0.3, Colors.BORDER),
                            visible=not is_last,
                        ),
                    ],
                ),
                ft.Container(width=10),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.only(bottom=14 if not is_last else 0),
                    content=ft.Column(spacing=2, tight=True, controls=[
                        ft.Text(title, size=12, weight=ft.FontWeight.W_600,
                                color=Colors.TEXT_PRIMARY if (done or active) else Colors.TEXT_MUTED),
                        ft.Text(desc, size=11, color=Colors.TEXT_MUTED),
                    ]),
                ),
            ],
        )

    # ── Status flags ─────────────────────────────────────────
    is_draft     = rtn.status in ("DRAFT",)
    is_confirmed = rtn.status in ("CONFIRMED", "SENT", "COMPLETED")
    is_sent      = rtn.status in ("SENT", "COMPLETED")
    is_completed = rtn.status == "COMPLETED"

    steps = [
        _step(1, "Return Dibuat",
              f"No. {rtn.return_number}  ·  {_fmt_date(rtn.return_date)}",
              done=True),
        _step(2, "Dikonfirmasi — Stok Dikurangi",
              f"Oleh: {rtn.confirmer.full_name if rtn.confirmer else '—'}  ·  "
              f"{_fmt_date(rtn.confirmed_at)}",
              done=is_confirmed),
        _step(3, "Dikirim ke Vendor",
              "Barang retur sudah dikirimkan ke pihak vendor",
              done=is_sent),
        _step(4, "Vendor Mengakui Penerimaan",
              f"Selesai: {_fmt_date(rtn.completed_at)}  ·  "
              f"Oleh: {rtn.completer.full_name if rtn.completer else '—'}",
              done=is_completed),
    ]

    # ── Cabang resolusi ───────────────────────────────────────
    resolution_steps = []

    # Credit Note branch
    if resolution in ("CREDIT_NOTE", "COMBINATION"):
        cn_desc = (
            f"No. {rtn.credit_note_number or '—'}  ·  "
            f"{_fmt_idr(rtn.credit_note_amount)}  ·  "
            f"Tgl: {_fmt_date(rtn.credit_note_date)}"
        )
        resolution_steps.append(
            _step(5 if resolution == "CREDIT_NOTE" else "5a",
                  "Credit Note Diterima dari Vendor",
                  cn_desc,
                  done=is_completed,
                  is_last=(resolution == "CREDIT_NOTE")),
        )
        if resolution == "CREDIT_NOTE":
            resolution_steps.append(
                _step("6", "Aplikasikan Credit Note ke PO / Invoice Berikutnya",
                      "Gunakan nilai CN sebagai pengurang tagihan pembelian selanjutnya "
                      "kepada vendor yang sama.",
                      done=False, active=is_completed, is_last=True),
            )

    # Replacement branch
    if resolution in ("REPLACEMENT", "COMBINATION"):
        has_gr    = replacement_gr is not None
        gr_status = replacement_gr.status if has_gr else ""
        gr_desc   = (
            f"GR: {replacement_gr.gr_number}  ·  Status: {gr_status}"
            if has_gr else "Menunggu — buat GR baru dari menu Goods Receipt"
        )
        label = "5b" if resolution == "COMBINATION" else "5"
        resolution_steps.append(
            _step(label,
                  "GR Replacement — Barang Pengganti Diterima",
                  gr_desc,
                  done=has_gr and gr_status == "CONFIRMED",
                  active=has_gr and gr_status == "DRAFT",
                  is_last=resolution == "REPLACEMENT"),
        )

    # Combination footer
    if resolution == "COMBINATION":
        resolution_steps.append(
            _step("6", "Aplikasikan Credit Note + Catat GR Replacement",
                  "Kedua mekanisme dicatat. Pastikan nilai CN & qty replacement sudah benar.",
                  done=False, active=is_completed, is_last=True),
        )

    all_steps = steps + resolution_steps

    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.03, Colors.TEXT_PRIMARY),
        border_radius=Sizes.CARD_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.all(16),
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.ACCOUNT_TREE_OUTLINED,
                            size=14, color=Colors.TEXT_SECONDARY),
                    ft.Text("Alur Mekanisme Pengembalian",
                            size=12, weight=ft.FontWeight.W_700,
                            color=Colors.TEXT_SECONDARY),
                ]),
                ft.Divider(height=14, color=Colors.BORDER),
                *all_steps,
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────
# DETAIL DIALOG
# ─────────────────────────────────────────────────────────────
def _detail_dialog(page, session: AppSession, return_id: int):
    with SessionLocal() as db:
        rtn = db.query(PurchaseReturn).filter_by(id=return_id)\
                .options(
                    joinedload(PurchaseReturn.vendor),
                    joinedload(PurchaseReturn.branch),
                    joinedload(PurchaseReturn.warehouse),
                    joinedload(PurchaseReturn.gr).joinedload(GoodsReceipt.po),
                    joinedload(PurchaseReturn.creator),
                    joinedload(PurchaseReturn.confirmer),
                    joinedload(PurchaseReturn.completer),
                    joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.product),
                    joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.uom),
                    joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.gr_line),
                ).first()
        if not rtn:
            show_snack(page, "Data tidak ditemukan.", False)
            return

        replacement_gr = _check_replacement_gr(db, return_id) if rtn.resolution in ("REPLACEMENT", "COMBINATION") else None

        # Serialize semua data yang butuh akses DB
        vendor_name  = rtn.vendor.name if rtn.vendor else "—"
        vendor_code  = rtn.vendor.code if rtn.vendor else ""
        branch_name  = rtn.branch.name if rtn.branch else "—"
        wh_name      = rtn.warehouse.name if rtn.warehouse else "—"
        gr_number    = rtn.gr.gr_number if rtn.gr else "—"
        po_number    = rtn.gr.po.po_number if (rtn.gr and rtn.gr.po) else "—"
        resolution   = rtn.resolution or ""
        cn_number    = rtn.credit_note_number or "—"
        cn_amount    = rtn.credit_note_amount or 0
        cn_date      = _fmt_date(rtn.credit_note_date)
        rep_qty      = rtn.replacement_qty or 0
        total_amount = rtn.total_amount or 0
        notes_val    = rtn.notes or ""

        lines_data = []
        for ln in (rtn.lines or []):
            sn_list = []
            if ln.serial_numbers:
                try: sn_list = json.loads(ln.serial_numbers)
                except: pass
            lines_data.append({
                "name":  ln.product.name if ln.product else "—",
                "code":  ln.product.code if ln.product else "",
                "uom":   ln.uom.code if ln.uom else "—",
                "qty":   ln.qty_return,
                "cost":  ln.unit_cost,
                "total": ln.qty_return * ln.unit_cost,
                "sn":    sn_list,
                "notes": ln.notes or "",
            })

        # Build mechanism flow (masih dalam db context)
        flow_widget = _mechanism_flow(rtn, replacement_gr)

    # ── Info grid ─────────────────────────────────────────────
    def _info_row(label, value, value_color=None, bold=False):
        return ft.Row(spacing=8, controls=[
            ft.Container(width=130,
                content=ft.Text(label, size=11, color=Colors.TEXT_MUTED)),
            ft.Text(value, size=12,
                color=value_color or Colors.TEXT_PRIMARY,
                weight=ft.FontWeight.W_600 if bold else ft.FontWeight.W_400),
        ])

    info_controls = [
        _info_row("Vendor",       f"{vendor_code}  —  {vendor_name}"),
        _info_row("PO / GR",      f"{po_number}  /  {gr_number}"),
        _info_row("Cabang",       branch_name),
        _info_row("Gudang",       wh_name),
        _info_row("Total Return", _fmt_idr(total_amount),
                  Colors.ERROR, bold=True),
    ]

    # CN info
    cn_controls = []
    if resolution in ("CREDIT_NOTE", "COMBINATION"):
        cn_controls += [
            _info_row("No. Credit Note", cn_number, Colors.INFO, bold=True),
            _info_row("Nilai Credit Note", _fmt_idr(cn_amount), Colors.INFO, bold=True),
            _info_row("Tgl Credit Note",  cn_date),
        ]
    if resolution in ("REPLACEMENT", "COMBINATION"):
        cn_controls.append(
            _info_row("Qty Replacement", f"{int(rep_qty)} unit", Colors.SUCCESS, bold=True)
        )

    # ── Item lines ────────────────────────────────────────────
    line_rows = []
    for i, ld in enumerate(lines_data):
        sn_chips = []
        if ld["sn"]:
            sn_chips = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.08, Colors.ERROR),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.3, Colors.ERROR)),
                    content=ft.Text(sn, size=10, color=Colors.ERROR,
                                    font_family="monospace"),
                )
                for sn in ld["sn"]
            ]
        line_rows.append(ft.Container(
            border=ft.Border.all(1, Colors.BORDER), border_radius=4,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Column(spacing=6, controls=[
                ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(width=24, content=ft.Text(
                            str(i+1), size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(expand=True, content=ft.Column(
                            spacing=1, tight=True, controls=[
                                ft.Text(ld["name"], size=13, color=Colors.TEXT_PRIMARY,
                                        weight=ft.FontWeight.W_500),
                                ft.Text(ld["code"], size=10, color=Colors.TEXT_MUTED,
                                        font_family="monospace"),
                            ])),
                        ft.Container(width=50, content=ft.Text(ld["uom"], size=12, color=Colors.TEXT_SECONDARY)),
                        ft.Container(width=80, content=ft.Text(f"{ld['qty']:,.2f}", size=12, color=Colors.ERROR, weight=ft.FontWeight.W_600)),
                        ft.Container(width=110, content=ft.Text(_fmt_idr(ld["cost"]), size=12, color=Colors.TEXT_SECONDARY)),
                        ft.Container(width=120, content=ft.Text(_fmt_idr(ld["total"]), size=12, color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600)),
                    ]),
                ft.Row(wrap=True, spacing=6, controls=sn_chips) if sn_chips else ft.Container(),
            ]),
        ))

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        shape=ft.RoundedRectangleBorder(radius=Sizes.CARD_RADIUS),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Container(
                            width=40, height=40, border_radius=20,
                            bgcolor=ft.Colors.with_opacity(0.1, Colors.INFO),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED,
                                            size=20, color=Colors.INFO),
                        ),
                        ft.Column(spacing=4, tight=True, controls=[
                            ft.Row(spacing=8, controls=[
                                ft.Text(cn_number if cn_number != "—" else rtn.return_number,
                                        size=16, weight=ft.FontWeight.W_700,
                                        color=Colors.TEXT_PRIMARY),
                                _resolution_badge(resolution, size=11),
                            ]),
                            ft.Row(spacing=12, controls=[
                                ft.Text(f"Return: {rtn.return_number}",
                                        size=11, color=Colors.TEXT_MUTED),
                                ft.Text(f"Vendor: {vendor_name}",
                                        size=11, color=Colors.TEXT_MUTED),
                                ft.Text(_fmt_idr(cn_amount if cn_amount else total_amount),
                                        size=12, color=Colors.INFO,
                                        weight=ft.FontWeight.W_700),
                            ]),
                        ]),
                    ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                    on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(
            width=960, height=540,
            content=ft.Row(
                spacing=14, expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    # ── Kolom kiri: Info + Items ──────────────
                    ft.Container(
                        expand=True,
                        content=ft.Column(
                            scroll=ft.ScrollMode.AUTO, spacing=12,
                            controls=[
                                # Info header
                                ft.Container(
                                    bgcolor=ft.Colors.with_opacity(0.03, Colors.TEXT_PRIMARY),
                                    border_radius=Sizes.BTN_RADIUS,
                                    border=ft.Border.all(1, Colors.BORDER),
                                    padding=ft.Padding.all(14),
                                    content=ft.Column(spacing=8, controls=[
                                        ft.Text("Informasi Return",
                                                size=12, weight=ft.FontWeight.W_700,
                                                color=Colors.TEXT_SECONDARY),
                                        ft.Divider(height=1, color=Colors.BORDER),
                                        *info_controls,
                                    ]),
                                ),
                                # CN / Replacement info
                                ft.Container(
                                    visible=bool(cn_controls),
                                    bgcolor=ft.Colors.with_opacity(0.03, Colors.INFO),
                                    border_radius=Sizes.BTN_RADIUS,
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.25, Colors.INFO)),
                                    padding=ft.Padding.all(14),
                                    content=ft.Column(spacing=8, controls=[
                                        ft.Row(spacing=6, controls=[
                                            ft.Icon(ft.Icons.RECEIPT_OUTLINED,
                                                    size=13, color=Colors.INFO),
                                            ft.Text("Detail Credit Note & Resolusi",
                                                    size=12, weight=ft.FontWeight.W_700,
                                                    color=Colors.INFO),
                                        ]),
                                        ft.Divider(height=1,
                                            color=ft.Colors.with_opacity(0.2, Colors.INFO)),
                                        *cn_controls,
                                    ]),
                                ),
                                # Item table header
                                ft.Container(
                                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                                    border_radius=ft.border_radius.only(
                                        top_left=4, top_right=4),
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                    content=ft.Row(spacing=8, controls=[
                                        ft.Container(width=24),
                                        ft.Container(expand=True, content=ft.Text(
                                            "Produk", size=11, weight=ft.FontWeight.W_600,
                                            color=Colors.TEXT_MUTED)),
                                        ft.Container(width=50, content=ft.Text(
                                            "Sat", size=11, color=Colors.TEXT_MUTED)),
                                        ft.Container(width=80, content=ft.Text(
                                            "Qty", size=11, color=Colors.ERROR,
                                            weight=ft.FontWeight.W_600)),
                                        ft.Container(width=110, content=ft.Text(
                                            "Harga/unit", size=11, color=Colors.TEXT_MUTED)),
                                        ft.Container(width=120, content=ft.Text(
                                            "Subtotal", size=11, weight=ft.FontWeight.W_600,
                                            color=Colors.TEXT_MUTED)),
                                    ]),
                                ),
                                *line_rows,
                                # Total
                                ft.Container(
                                    alignment=ft.Alignment(1, 0),
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                    content=ft.Text(
                                        f"TOTAL RETUR: {_fmt_idr(total_amount)}",
                                        size=13, weight=ft.FontWeight.W_700,
                                        color=Colors.TEXT_PRIMARY),
                                ),
                                # Catatan
                                ft.Container(
                                    visible=bool(notes_val),
                                    bgcolor=ft.Colors.with_opacity(0.03, Colors.TEXT_PRIMARY),
                                    border_radius=4, padding=ft.Padding.all(10),
                                    content=ft.Column(spacing=4, controls=[
                                        ft.Text("Catatan:", size=11,
                                                color=Colors.TEXT_MUTED,
                                                weight=ft.FontWeight.W_600),
                                        ft.Text(notes_val, size=12,
                                                color=Colors.TEXT_SECONDARY),
                                    ]),
                                ),
                            ],
                        ),
                    ),
                    # ── Kolom kanan: Alur mekanisme ───────────
                    ft.Container(
                        width=300,
                        content=ft.Column(
                            scroll=ft.ScrollMode.AUTO,
                            controls=[flow_widget],
                        ),
                    ),
                ],
            ),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Tutup",
                style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                on_click=lambda e: (setattr(dlg, "open", False), page.update())),
        ],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# TABLE ROWS
# ─────────────────────────────────────────────────────────────
def _cn_to_dicts(returns: List[PurchaseReturn]) -> List[Dict]:
    rows = []
    for rtn in returns:
        rows.append({
            "id":            rtn.id,
            "return_number": rtn.return_number,
            "cn_number":     rtn.credit_note_number or "—",
            "cn_amount":     rtn.credit_note_amount or 0,
            "cn_date":       _fmt_date(rtn.credit_note_date),
            "total_amount":  rtn.total_amount or 0,
            "resolution":    rtn.resolution or "",
            "replacement_qty": rtn.replacement_qty or 0,
            "vendor_name":   rtn.vendor.name if rtn.vendor else "—",
            "vendor_code":   rtn.vendor.code if rtn.vendor else "",
            "branch_name":   rtn.branch.name if rtn.branch else "—",
            "return_date":   _fmt_date(rtn.return_date),
            "completed_at":  _fmt_date(rtn.completed_at),
            "item_count":    len(rtn.lines or []),
        })
    return rows


def _build_table_rows(data, page, session, refresh) -> List[ft.DataRow]:
    rows = []
    for d in data:
        resolution = d["resolution"]
        cn_display = ft.Column(spacing=2, tight=True, controls=[
            ft.Text(d["cn_number"], size=12, font_family="monospace",
                    color=Colors.INFO, weight=ft.FontWeight.W_600),
            ft.Text(_fmt_idr(d["cn_amount"]), size=11,
                    color=Colors.TEXT_MUTED),
            ft.Text(f"Tgl: {d['cn_date']}", size=10, color=Colors.TEXT_MUTED)
            if d["cn_date"] != "—" else ft.Container(),
        ])

        replacement_display = ft.Container()
        if resolution in ("REPLACEMENT", "COMBINATION"):
            replacement_display = ft.Container(
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
                bgcolor=ft.Colors.with_opacity(0.08, Colors.SUCCESS),
                content=ft.Text(
                    f"+ {int(d['replacement_qty'])} unit diganti",
                    size=10, color=Colors.SUCCESS,
                    weight=ft.FontWeight.W_600),
            )

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["return_number"], size=12, color=Colors.TEXT_MUTED,
                        font_family="monospace"),
                ft.Text(d["completed_at"], size=10, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["vendor_name"], size=13, color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_500),
                ft.Text(d["vendor_code"], size=10, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(cn_display),
            ft.DataCell(ft.Column(spacing=4, tight=True, controls=[
                _resolution_badge(resolution),
                replacement_display,
            ])),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"{d['item_count']} item", size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(_fmt_idr(d["total_amount"]), size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["branch_name"], size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(ft.Icons.ACCOUNT_TREE_OUTLINED, "Lihat Alur Mekanisme",
                    lambda e, rid=d["id"]: _detail_dialog(page, session, rid),
                    Colors.INFO),
            ])),
        ]))
    return rows


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def CreditNotePage(page, session: AppSession) -> ft.Control:
    search_val     = {"q": ""}
    resolution_val = {"v": ""}
    vendor_val     = {"id": None}

    stats_ref  = ft.Ref[ft.Row]()
    table_ref  = ft.Ref[ft.DataTable]()
    area_ref   = ft.Ref[ft.Column]()
    vendor_dd  = ft.Ref[ft.Dropdown]()

    # ── Initial load ──────────────────────────────────────────
    with SessionLocal() as db:
        summary  = _get_summary(db, session.company_id)
        vendors  = _get_vendors(db, session.company_id)
        initial  = _cn_to_dicts(
            _get_credit_notes(db, session.company_id))

    vendor_opts = [("", "Semua Vendor")] + [
        (str(v.id), v.name) for v in vendors
    ]

    # ── Stats row ─────────────────────────────────────────────
    def _build_stats(s: Dict) -> ft.Row:
        return ft.Row(
            spacing=12, wrap=True,
            controls=[
                _stat_card(
                    ft.Icons.RECEIPT_LONG_OUTLINED, Colors.INFO,
                    "Total Credit Note",
                    str(s["total_count"]) + " CN",
                    _fmt_idr(s["total_cn_amt"]),
                ),
                _stat_card(
                    ft.Icons.RECEIPT_OUTLINED, Colors.INFO,
                    "Pure Credit Note",
                    str(s["cn_count"]) + " CN",
                    _fmt_idr(s["cn_amt"]),
                ),
                _stat_card(
                    ft.Icons.TUNE, Colors.WARNING,
                    "Kombinasi CN + Replacement",
                    str(s["combo_count"]) + " CN",
                    _fmt_idr(s["combo_cn_amt"]),
                ),
                _stat_card(
                    ft.Icons.SWAP_HORIZ, Colors.SUCCESS,
                    "Total Nilai Retur",
                    _fmt_idr(s["total_return"]),
                    f"dari {s['total_count']} return",
                ),
            ],
        )

    stats_row = ft.Row(
        ref=stats_ref, spacing=12, wrap=True,
        controls=_build_stats(summary).controls,
    )

    # ── Table ─────────────────────────────────────────────────
    COLS = [
        ft.DataColumn(ft.Text("No. Return / Selesai",
            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Vendor",
            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Credit Note",
            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Resolusi",
            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item / Total Retur",
            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang",
            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",
            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        ref=table_ref,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=72, column_spacing=16,
        columns=COLS,
        rows=_build_table_rows(initial, page, session, lambda: None),
    )

    table_area = ft.Column(
        ref=area_ref,
        controls=[table if initial else empty_state("Belum ada credit note.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def refresh():
        with SessionLocal() as db:
            s    = _get_summary(db, session.company_id)
            data = _cn_to_dicts(_get_credit_notes(
                db, session.company_id,
                search=search_val["q"],
                resolution=resolution_val["v"],
                vendor_id=vendor_val["id"],
            ))

        # Update stats
        new_stats = _build_stats(s)
        stats_row.controls = new_stats.controls

        # Update table
        table.rows = _build_table_rows(data, page, session, refresh)
        table_area.controls = [
            table if data else empty_state("Tidak ada credit note ditemukan.")
        ]
        try:
            stats_row.update()
            table_area.update()
        except Exception:
            pass

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    def on_resolution_change(e):
        resolution_val["v"] = e.control.value or ""
        refresh()

    def on_vendor_change(e):
        val = e.control.value
        vendor_val["id"] = int(val) if val else None
        refresh()

    # ── Filter bar ────────────────────────────────────────────
    f_resolution = make_dropdown("Resolusi", _RESOLUTION_OPTS, "", width=200)
    f_resolution.on_select = on_resolution_change

    f_vendor = make_dropdown("Vendor", vendor_opts, "", width=260)
    f_vendor.on_select = on_vendor_change

    # ── Info banner ───────────────────────────────────────────
    info_banner = ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        border_radius=Sizes.BTN_RADIUS,
        bgcolor=ft.Colors.with_opacity(0.06, Colors.INFO),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, Colors.INFO)),
        content=ft.Row(spacing=10, controls=[
            ft.Icon(ft.Icons.INFO_OUTLINE, size=15, color=Colors.INFO),
            ft.Text(
                "Halaman ini menampilkan credit note dari vendor yang diterima "
                "melalui proses Purchase Return. Klik ikon alur mekanisme (🌳) "
                "pada setiap baris untuk melihat detail status pengembalian.",
                size=11, color=Colors.INFO, expand=True,
            ),
        ]),
    )

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK, padding=ft.Padding.all(24),
        content=ft.Column(
            expand=True, spacing=0,
            controls=[
                page_header(
                    "Credit Note Monitor",
                    "Pantau credit note & mekanisme pengembalian dari vendor",
                ),
                info_banner,
                ft.Container(height=16),
                stats_row,
                ft.Container(height=16),
                ft.Row(spacing=12, controls=[
                    search_bar("Cari no. return / no. CN...", on_search, width=260),
                    f_resolution,
                    f_vendor,
                ]),
                ft.Container(height=12),
                ft.Container(
                    expand=True,
                    content=ft.ListView(expand=True, controls=[table_area]),
                ),
            ],
        ),
    )