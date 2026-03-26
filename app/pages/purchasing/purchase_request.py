"""
app/pages/purchasing/purchase_request.py
Pembelian → Purchase Request

PENTING: Semua dialog menerima pr_id (int), bukan objek ORM.
Objek di-reload di dalam session lokal masing-masing fungsi.
"""
from __future__ import annotations
import flet as ft
from typing import Optional, List, Dict
from datetime import date

from app.database import SessionLocal
from app.models import (
    PurchaseRequest, PurchaseRequestLine,
    Branch, Department, Product, UnitOfMeasure,
)
from app.services.purchasing_service import PurchaseRequestService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    page_header, search_bar,
    confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS = [
    ("DRAFT",      "Draft"),
    ("SUBMITTED",  "Disubmit"),
    ("APPROVED",   "Disetujui"),
    ("REJECTED",   "Ditolak"),
    ("PO_CREATED", "PO Dibuat"),
    ("CANCELLED",  "Dibatalkan"),
]
_STATUS_COLOR = {
    "DRAFT":      Colors.TEXT_MUTED,
    "SUBMITTED":  Colors.INFO,
    "APPROVED":   Colors.SUCCESS,
    "REJECTED":   Colors.ERROR,
    "PO_CREATED": Colors.ACCENT,
    "CANCELLED":  Colors.TEXT_MUTED,
}


def _pr_badge(status: str) -> ft.Container:
    color = _STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    label = dict(_STATUS_OPTS).get(status, status)
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


def _parse_date(val: str):
    if not (val or "").strip(): return None
    from datetime import datetime
    try: return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except: return None


# ─────────────────────────────────────────────────────────────
# LINE ITEM EDITOR
# ─────────────────────────────────────────────────────────────
class LineItemEditor:
    def __init__(self, page, products: List, uoms: List,
                 initial_lines: List[Dict] = None):
        self.page = page
        self._prod_opts = [(str(p.id), f"{p.code} — {p.name}") for p in products]
        self._uom_opts  = [(str(u.id), f"{u.code} — {u.name}") for u in uoms]
        # Map product_id → {uom_id, standard_cost} untuk auto-fill
        self._prod_map  = {
            str(p.id): {"uom_id": str(p.uom_id), "cost": p.standard_cost or 0}
            for p in products
        }
        self.rows: List[Dict] = []
        self.container = ft.Column(spacing=8)

        for ln in (initial_lines or []):
            self._add_row(
                product_id=str(ln.get("product_id", "")),
                uom_id=str(ln.get("uom_id", "")),
                qty=str(ln.get("qty_requested", "1")),
                price=str(int(ln.get("estimated_price", 0))),
                notes=ln.get("notes", ""),
                line_id=ln.get("id"),
            )
        if not self.rows:
            self._add_row()
        self._rebuild()

    def _add_row(self, product_id="", uom_id="", qty="1",
                 price="0", notes="", line_id=None):
        f_product = make_dropdown("Produk *", self._prod_opts, product_id)
        f_uom     = make_dropdown("Satuan *", self._uom_opts, uom_id, width=140)
        f_qty     = make_field("Qty *", qty,
                               keyboard_type=ft.KeyboardType.NUMBER, width=100)
        f_price   = make_field("Harga Est.", price,
                               keyboard_type=ft.KeyboardType.NUMBER, width=150)
        f_notes   = make_field("Keterangan", notes, width=180)

        row_data = {
            "product": f_product, "uom": f_uom,
            "qty": f_qty, "price": f_price,
            "notes": f_notes, "line_id": line_id,
        }

        def _on_product_change(e, rd=row_data):
            pid = rd["product"].value
            if pid and pid in self._prod_map:
                info = self._prod_map[pid]
                # Auto-fill satuan dasar
                if not rd["uom"].value:
                    rd["uom"].value = info["uom_id"]
                    try: rd["uom"].update()
                    except: pass
                # Auto-fill harga estimasi dari standard_cost
                rd["price"].value = str(int(info["cost"]))
                try: rd["price"].update()
                except: pass

        f_product.on_select = _on_product_change

        def _remove(e, rd=row_data):
            if len(self.rows) > 1:
                self.rows.remove(rd)
                self._rebuild()

        row_data["remove_btn"] = ft.IconButton(
            icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
            icon_color=Colors.ERROR, icon_size=18,
            tooltip="Hapus baris",
            on_click=_remove,
            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
        )
        self.rows.append(row_data)

    def _rebuild(self):
        controls = [
            ft.Container(
                bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                border_radius=ft.border_radius.only(top_left=6, top_right=6),
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                content=ft.Row(spacing=8, controls=[
                    ft.Text("Produk",     size=11, color=Colors.TEXT_MUTED, expand=True),
                    ft.Text("Satuan",     size=11, color=Colors.TEXT_MUTED, width=140),
                    ft.Text("Qty",        size=11, color=Colors.TEXT_MUTED, width=100),
                    ft.Text("Harga Est.", size=11, color=Colors.TEXT_MUTED, width=150),
                    ft.Text("Keterangan", size=11, color=Colors.TEXT_MUTED, width=180),
                    ft.Container(width=36),
                ]),
            )
        ]
        for rd in self.rows:
            controls.append(ft.Container(
                border=ft.Border.all(1, Colors.BORDER),
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(expand=True, content=rd["product"]),
                        rd["uom"], rd["qty"], rd["price"], rd["notes"],
                        rd["remove_btn"],
                    ],
                ),
            ))
        controls.append(ft.Button(
            content=ft.Row(tight=True, spacing=6, controls=[
                ft.Icon(ft.Icons.ADD, size=16, color=Colors.ACCENT),
                ft.Text("Tambah Item", size=13, color=Colors.ACCENT),
            ]),
            on_click=lambda e: (self._add_row(), self._rebuild()),
        ))
        self.container.controls = controls
        try: self.container.update()
        except: pass

    def get_lines(self) -> tuple[bool, str, List[Dict]]:
        lines = []
        for i, rd in enumerate(self.rows):
            if not rd["product"].value:
                return False, f"Baris {i+1}: Produk wajib dipilih.", []
            if not rd["uom"].value:
                return False, f"Baris {i+1}: Satuan wajib dipilih.", []
            try:
                qty = float(rd["qty"].value or 0)
                if qty <= 0:
                    return False, f"Baris {i+1}: Qty harus > 0.", []
            except ValueError:
                return False, f"Baris {i+1}: Qty tidak valid.", []
            lines.append({
                "id":              rd.get("line_id"),
                "product_id":      rd["product"].value,
                "uom_id":          rd["uom"].value,
                "qty_requested":   rd["qty"].value,
                "estimated_price": rd["price"].value or "0",
                "notes":           rd["notes"].value or "",
            })
        return True, "", lines


# ─────────────────────────────────────────────────────────────
# FORM DIALOG — menerima pr_id bukan objek ORM
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 pr_id: Optional[int], on_saved):
    """pr_id=None → tambah baru, pr_id=int → edit"""
    is_edit = pr_id is not None

    # Semua data dimuat dalam SATU session, lalu dikonversi ke plain value
    with SessionLocal() as db:
        branches    = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        departments = db.query(Department).filter_by(
            company_id=session.company_id, is_active=True).order_by(Department.name).all()
        products    = db.query(Product).filter_by(
            company_id=session.company_id, is_purchasable=True,
            is_active=True).order_by(Product.name).all()
        uoms = db.query(UnitOfMeasure).filter_by(is_active=True).all()

        # Ambil nilai default dari PR jika edit
        pr_branch_id   = None
        pr_dept_id     = None
        pr_req_date    = date.today().strftime("%Y-%m-%d")
        pr_need_date   = ""
        pr_notes       = ""
        pr_number_str  = ""
        initial_lines  = []

        if is_edit:
            pr = PurchaseRequestService.get_by_id(db, pr_id)
            if pr:
                pr_branch_id  = str(pr.branch_id) if pr.branch_id else None
                pr_dept_id    = str(pr.department_id) if pr.department_id else ""
                pr_req_date   = _fmt_date(pr.request_date) or pr_req_date
                pr_need_date  = _fmt_date(pr.required_date) or ""
                pr_notes      = pr.notes or ""
                pr_number_str = pr.pr_number
                for ln in (pr.lines or []):
                    initial_lines.append({
                        "id":              ln.id,
                        "product_id":      ln.product_id,
                        "uom_id":          ln.uom_id,
                        "qty_requested":   ln.qty_requested,
                        "estimated_price": ln.estimated_price,
                        "notes":           ln.notes or "",
                    })

        # Konversi ke plain list — SEBELUM session tutup
        br_list   = [(str(b.id), f"{b.name} ({b.branch_type})") for b in branches]
        dept_list = [("", "— Pilih Departemen —")] + [(str(d.id), d.name) for d in departments]
        prod_list = list(products)   # masih ORM tapi hanya butuh .id dan .name/.code
        uom_list  = list(uoms)

    # Dari sini ke bawah: tidak akses relasi ORM lagi
    default_br = pr_branch_id or \
                 (str(session.branch_id) if hasattr(session, "branch_id") and
                  session.branch_id else "")

    f_branch   = make_dropdown("Cabang *", br_list, default_br or "")
    f_dept     = make_dropdown("Departemen", dept_list, pr_dept_id or "")
    f_req_date = make_field("Tanggal Request *", pr_req_date,
                            hint="YYYY-MM-DD", width=180)
    f_req_need = make_field("Dibutuhkan Tgl", pr_need_date,
                            hint="YYYY-MM-DD", width=180)
    f_notes    = make_field("Catatan", pr_notes,
                            multiline=True, min_lines=2, max_lines=3)

    line_editor = LineItemEditor(page, prod_list, uom_list, initial_lines)
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_branch.value:
            show_err("Cabang wajib dipilih."); return
        req_date = _parse_date(f_req_date.value)
        if not req_date:
            show_err("Tanggal request tidak valid. Gunakan YYYY-MM-DD."); return

        valid, errmsg, lines = line_editor.get_lines()
        if not valid:
            show_err(errmsg); return

        data = {
            "branch_id":     f_branch.value,
            "department_id": f_dept.value or None,
            "request_date":  req_date,
            "required_date": _parse_date(f_req_need.value),
            "notes":         f_notes.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = PurchaseRequestService.update(db, pr_id, data, lines)
            else:
                ok, msg, _ = PurchaseRequestService.create(
                    db, session.company_id, session.user_id, data, lines)

        dlg.open = False
        page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    title_str = f"Edit PR — {pr_number_str}" if is_edit else "Buat Purchase Request"

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.REQUEST_PAGE, color=Colors.ACCENT, size=20),
                    ft.Text(title_str, color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=900, height=580,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
                err,
                section_card("Header", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":4}, content=f_branch),
                        ft.Container(col={"xs":12,"sm":4}, content=f_dept),
                    ]),
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":3}, content=f_req_date),
                        ft.Container(col={"xs":12,"sm":3}, content=f_req_need),
                    ]),
                    f_notes,
                ]),
                section_card("Item yang Diminta", [line_editor.container]),
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT,
                color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# DETAIL / APPROVE DIALOG — menerima pr_id
# ─────────────────────────────────────────────────────────────
def _detail_dialog(page, session: AppSession, pr_id: int, on_saved):
    # Load semua data yang dibutuhkan dalam satu session
    with SessionLocal() as db:
        pr = PurchaseRequestService.get_by_id(db, pr_id)
        if not pr:
            show_snack(page, "PR tidak ditemukan.", False)
            return

        # Konversi ke plain value sebelum session tutup
        pr_number    = pr.pr_number
        pr_status    = pr.status
        pr_notes     = pr.notes or ""
        pr_req_date  = _fmt_date(pr.request_date)
        pr_need_date = _fmt_date(pr.required_date)
        req_name     = pr.requester.full_name if pr.requester else "—"

        line_data = []
        for ln in (pr.lines or []):
            line_data.append({
                "id":             ln.id,
                "product_name":   ln.product.name if ln.product else "—",
                "product_code":   ln.product.code if ln.product else "",
                "uom_code":       ln.uom.code if ln.uom else "—",
                "qty_requested":  ln.qty_requested,
                "qty_approved":   ln.qty_approved,
                "estimated_price":ln.estimated_price,
                "notes":          ln.notes or "",
            })

    can_approve = pr_status == "SUBMITTED" and \
                  session.has_perm("PUR_PR", "can_approve")

    # Field qty approve (hanya jika bisa approve)
    approve_fields: Dict[int, ft.TextField] = {}
    if can_approve:
        for ld in line_data:
            approve_fields[ld["id"]] = make_field(
                "", str(ld["qty_requested"]),
                keyboard_type=ft.KeyboardType.NUMBER, width=100,
            )

    f_reject_reason = make_field("Alasan Penolakan", "",
                                  multiline=True, min_lines=2, max_lines=3)
    reject_panel = ft.Container(visible=False, content=f_reject_reason)

    total_est = sum(ld["qty_requested"] * ld["estimated_price"] for ld in line_data)

    # Build line rows dari plain data
    line_rows = []
    for i, ld in enumerate(line_data):
        row_controls = [
            ft.Container(width=30, content=ft.Text(str(i+1), size=12,
                                                    color=Colors.TEXT_MUTED)),
            ft.Container(expand=True, content=ft.Column(spacing=1, tight=True, controls=[
                ft.Text(ld["product_name"], size=13, color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_500),
                ft.Text(ld["product_code"], size=11, color=Colors.TEXT_MUTED,
                        font_family="monospace"),
            ])),
            ft.Container(width=80, content=ft.Text(
                ld["uom_code"], size=12, color=Colors.TEXT_SECONDARY)),
            ft.Container(width=80, content=ft.Text(
                f"{ld['qty_requested']:,.2f}", size=12,
                color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_500)),
        ]
        if can_approve:
            row_controls.append(approve_fields[ld["id"]])
        else:
            row_controls.append(ft.Container(width=100, content=ft.Text(
                f"{ld['qty_approved']:,.2f}" if ld["qty_approved"] else "—",
                size=12, color=Colors.SUCCESS)))
        row_controls.append(ft.Container(width=140, content=ft.Text(
            f"Rp {ld['estimated_price']:,.0f}" if ld["estimated_price"] else "—",
            size=12, color=Colors.TEXT_SECONDARY)))

        line_rows.append(ft.Container(
            border=ft.Border.all(1, Colors.BORDER), border_radius=4,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Row(spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=row_controls),
        ))

    def do_approve(e):
        approved = {lid: float(approve_fields[lid].value or 0)
                    for lid in approve_fields}
        with SessionLocal() as db:
            ok, msg = PurchaseRequestService.approve(
                db, pr_id, session.user_id, approved)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    def do_reject_show(e):
        reject_panel.visible = True
        try: reject_panel.update()
        except: pass

    def do_reject_confirm(e):
        with SessionLocal() as db:
            ok, msg = PurchaseRequestService.reject(
                db, pr_id, session.user_id, f_reject_reason.value)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    actions = [
        ft.Button("Tutup", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
    ]
    if can_approve:
        actions += [
            ft.Button("Tolak",
                bgcolor=Colors.ERROR, color=ft.Colors.WHITE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=do_reject_show),
            ft.Button("Setujui",
                bgcolor=Colors.SUCCESS, color=ft.Colors.WHITE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=do_approve),
        ]

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=4, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.REQUEST_PAGE, color=Colors.ACCENT, size=18),
                        ft.Text(pr_number, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                        _pr_badge(pr_status),
                    ]),
                    ft.Row(spacing=16, controls=[
                        ft.Text(f"Tgl: {pr_req_date}", size=11,
                                color=Colors.TEXT_MUTED),
                        ft.Text(f"Butuh: {pr_need_date or '—'}", size=11,
                                color=Colors.TEXT_MUTED),
                        ft.Text(f"Oleh: {req_name}", size=11,
                                color=Colors.TEXT_MUTED),
                    ]),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=820, height=500,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=10, controls=[
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Row(spacing=8, controls=[
                        ft.Container(width=30),
                        ft.Container(expand=True,
                            content=ft.Text("Produk", size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=80,
                            content=ft.Text("Satuan", size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=80,
                            content=ft.Text("Qty Req", size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=100, content=ft.Text(
                            "Qty Approve" if can_approve else "Qty Disetujui",
                            size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=140,
                            content=ft.Text("Harga Est.", size=11, color=Colors.TEXT_MUTED)),
                    ]),
                ),
                *line_rows,
                ft.Container(
                    alignment=ft.Alignment(1, 0),
                    padding=ft.Padding.only(right=10, top=4),
                    content=ft.Text(
                        f"Total Estimasi: Rp {total_est:,.0f}",
                        size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
                ),
                reject_panel,
                ft.Container(
                    visible=bool(pr_notes),
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=4,
                    padding=ft.Padding.all(10),
                    content=ft.Column(spacing=4, controls=[
                        ft.Text("Catatan:", size=11, color=Colors.TEXT_MUTED,
                                weight=ft.FontWeight.W_600),
                        ft.Text(pr_notes, size=12, color=Colors.TEXT_SECONDARY),
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
# TABLE ROWS — hanya akses atribut scalar, bukan relasi
# ─────────────────────────────────────────────────────────────
def _build_rows(pr_data: List[Dict], page, session, refresh):
    """pr_data: list of dict (plain values, bukan ORM objects)"""
    rows = []
    for d in pr_data:
        actions = [
            action_btn(ft.Icons.VISIBILITY_OUTLINED, "Lihat Detail",
                lambda e, pid=d["id"]: _detail_dialog(page, session, pid, refresh),
                Colors.INFO),
        ]
        if d["status"] == "DRAFT":
            actions += [
                action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, pid=d["id"]: _form_dialog(page, session, pid, refresh),
                    Colors.TEXT_SECONDARY),
                action_btn(ft.Icons.SEND, "Submit",
                    lambda e, pid=d["id"], pno=d["pr_number"]: confirm_dialog(
                        page, "Submit PR",
                        f"Submit PR {pno} untuk persetujuan?",
                        lambda: _submit(pid, page, refresh),
                        "Ya, Submit", Colors.INFO),
                    Colors.ACCENT),
                action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, pid=d["id"], pno=d["pr_number"]: confirm_dialog(
                        page, "Hapus PR", f"Hapus PR {pno}?",
                        lambda: _delete(pid, page, refresh)),
                    Colors.ERROR),
            ]
        if d["status"] == "SUBMITTED" and session.has_perm("PUR_PR", "can_approve"):
            actions.append(action_btn(
                ft.Icons.APPROVAL, "Approve / Reject",
                lambda e, pid=d["id"]: _detail_dialog(page, session, pid, refresh),
                Colors.SUCCESS))
        if d["status"] not in ("PO_CREATED", "CANCELLED"):
            actions.append(action_btn(
                ft.Icons.CANCEL_OUTLINED, "Batalkan",
                lambda e, pid=d["id"], pno=d["pr_number"]: confirm_dialog(
                    page, "Batalkan PR", f"Batalkan PR {pno}?",
                    lambda: _cancel(pid, page, refresh),
                    "Ya, Batalkan", Colors.WARNING),
                Colors.WARNING))

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["pr_number"], size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY, font_family="monospace"),
                ft.Text(d["branch_name"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["request_date"], size=12,
                                color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["required_date"] or "—", size=12,
                                color=Colors.TEXT_SECONDARY if d["required_date"]
                                else Colors.TEXT_MUTED)),
            ft.DataCell(ft.Text(d["requester_name"], size=12,
                                color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"{d['item_count']} item", size=12,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(f"Est. Rp {d['total_est']:,.0f}", size=11,
                        color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(_pr_badge(d["status"])),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def _prs_to_dicts(prs) -> List[Dict]:
    """Konversi ORM objects ke plain dicts di dalam session."""
    result = []
    for pr in prs:
        total_est = sum(
            (ln.qty_requested or 0) * (ln.estimated_price or 0)
            for ln in (pr.lines or [])
        )
        result.append({
            "id":            pr.id,
            "pr_number":     pr.pr_number,
            "status":        pr.status,
            "request_date":  _fmt_date(pr.request_date),
            "required_date": _fmt_date(pr.required_date),
            "branch_name":   pr.branch.name if pr.branch else "—",
            "requester_name":pr.requester.full_name if pr.requester else "—",
            "item_count":    len(pr.lines or []),
            "total_est":     total_est,
            "notes":         pr.notes or "",
        })
    return result


def _submit(pid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PurchaseRequestService.submit(db, pid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _cancel(pid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PurchaseRequestService.cancel(db, pid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _delete(pid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PurchaseRequestService.delete(db, pid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _filter_bar(active_status: Dict, on_filter) -> ft.Control:
    filters = [("", "Semua")] + _STATUS_OPTS
    btns = []
    for val, label in filters:
        is_active = active_status["v"] == val
        color     = _STATUS_COLOR.get(val, Colors.TEXT_SECONDARY)
        btns.append(ft.Container(
            height=32,
            padding=ft.Padding.symmetric(horizontal=12),
            border_radius=Sizes.BTN_RADIUS,
            bgcolor=ft.Colors.with_opacity(0.12, color) if is_active
                    else ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, color if is_active else Colors.BORDER),
            on_click=lambda e, v=val: on_filter(v),
            ink=True,
            content=ft.Text(label, size=12,
                color=color if is_active else Colors.TEXT_SECONDARY,
                weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400),
        ))
    return ft.Row(spacing=6, wrap=True, controls=btns)


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def PurchaseRequestPage(page, session: AppSession) -> ft.Control:
    search_val  = {"q": ""}
    status_val  = {"v": ""}
    filter_area = ft.Container()

    def _load() -> List[Dict]:
        with SessionLocal() as db:
            prs = PurchaseRequestService.get_all(
                db, session.company_id, search_val["q"], status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _prs_to_dicts(prs)   # konversi dalam session

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("No. PR / Cabang",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tgl Request",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Dibutuhkan",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Diminta Oleh",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item / Est. Total", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",            size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",              size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44,
        data_row_min_height=60,
        column_spacing=16,
        columns=COLS,
        rows=_build_rows(initial, page, session, lambda: None),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada Purchase Request.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def refresh():
        data = _load()
        table.rows = _build_rows(data, page, session, refresh)
        table_area.controls = [
            table if data else empty_state("Tidak ada PR ditemukan.")
        ]
        filter_area.content = _filter_bar(status_val, on_filter)
        try:
            table_area.update()
            filter_area.update()
        except Exception:
            pass

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    def on_filter(val: str):
        status_val["v"] = val
        refresh()

    filter_area.content = _filter_bar(status_val, on_filter)
    table.rows = _build_rows(initial, page, session, refresh)

    return ft.Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(
            expand=True, spacing=0,
            controls=[
                page_header(
                    "Purchase Request",
                    "Pengajuan permintaan pembelian barang",
                    "Buat PR Baru",
                    on_action=lambda: _form_dialog(page, session, None, refresh),
                    action_icon=ft.Icons.ADD,
                ),
                ft.Container(padding=ft.Padding.only(bottom=12),
                             content=filter_area),
                ft.Row(controls=[search_bar("Cari nomor PR...", on_search)]),
                ft.Container(height=12),
                ft.Container(
                    expand=True,
                    content=ft.ListView(expand=True, controls=[table_area]),
                ),
            ],
        ),
    )
