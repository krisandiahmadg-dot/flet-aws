"""
app/pages/purchasing/purchase_order.py
Pembelian → Purchase Order

Alur: DRAFT → SENT → CONFIRMED → PARTIAL/RECEIVED
      * CANCELLED dari DRAFT/SENT/CONFIRMED
"""
from __future__ import annotations
import flet as ft
from typing import Optional, List, Dict
from datetime import date

from app.database import SessionLocal
from app.models import (
    PurchaseOrder, PurchaseOrderLine,
    Branch, Vendor, VendorProduct, Warehouse,
    Product, UnitOfMeasure, PurchaseRequest,
)
from app.services.purchasing_service import PurchaseOrderService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    page_header, search_bar,
    confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS = [
    ("DRAFT",     "Draft"),
    ("SENT",      "Dikirim"),
    ("CONFIRMED", "Dikonfirmasi"),
    ("PARTIAL",   "Partial Received"),
    ("RECEIVED",  "Diterima"),
    ("CANCELLED", "Dibatalkan"),
]
_STATUS_COLOR = {
    "DRAFT":     Colors.TEXT_MUTED,
    "SENT":      Colors.INFO,
    "CONFIRMED": Colors.SUCCESS,
    "PARTIAL":   Colors.WARNING,
    "RECEIVED":  Colors.ACCENT,
    "CANCELLED": Colors.ERROR,
}


def _po_badge(status: str) -> ft.Container:
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
# PO LINE EDITOR  (lebih kaya dari PR — ada harga, diskon, pajak)
# ─────────────────────────────────────────────────────────────
class POLineEditor:
    def __init__(self, page, products: List, uoms: List,
                 initial_lines: List[Dict] = None,
                 vendor_prices: Dict = None):
        self.page      = page
        self._prod_opts = [(str(p.id), f"{p.code} — {p.name}") for p in products]
        self._uom_opts  = [(str(u.id), f"{u.code}") for u in uoms]
        # Map product_id → {uom_id, price, tax_pct}
        # Prioritas: vendor_price > standard_cost
        vp = vendor_prices or {}
        self._prod_map = {}
        for p in products:
            pid = str(p.id)
            if pid in vp:
                self._prod_map[pid] = {
                    "uom_id":  str(p.uom_id),
                    "price":   vp[pid].get("price", p.standard_cost or 0),
                    "tax_pct": 0,
                }
            else:
                self._prod_map[pid] = {
                    "uom_id": str(p.uom_id),
                    "price":  p.standard_cost or 0,
                    "tax_pct": 0,
                }
        self.rows: List[Dict] = []
        self.container = ft.Column(spacing=6)
        self.summary_text = ft.Text("", size=12,
                                     color=Colors.TEXT_SECONDARY,
                                     weight=ft.FontWeight.W_600)

        for ln in (initial_lines or []):
            self._add_row(
                product_id=str(ln.get("product_id", "")),
                uom_id=str(ln.get("uom_id", "")),
                qty=str(ln.get("qty_ordered", "1")),
                price=str(int(ln.get("unit_price", 0))),
                disc=str(ln.get("discount_pct", "0")),
                tax=str(ln.get("tax_pct", "0")),
                notes=ln.get("notes", ""),
                line_id=ln.get("id"),
            )
        if not self.rows:
            self._add_row()
        self._rebuild()

    def _add_row(self, product_id="", uom_id="", qty="1",
                 price="0", disc="0", tax="0", notes="", line_id=None):
        f_prod  = make_dropdown("Produk *", self._prod_opts, product_id)
        f_uom   = make_dropdown("UoM *", self._uom_opts, uom_id, width=90)
        f_qty   = make_field("Qty *", qty, keyboard_type=ft.KeyboardType.NUMBER, width=90)
        f_price = make_field("Harga *", price, keyboard_type=ft.KeyboardType.NUMBER, width=140)
        f_disc  = make_field("Disc%", disc, keyboard_type=ft.KeyboardType.NUMBER, width=70)
        f_tax   = make_field("PPN%", tax, keyboard_type=ft.KeyboardType.NUMBER, width=70)
        f_notes = make_field("Ket.", notes, width=140)

        row_data = dict(prod=f_prod, uom=f_uom, qty=f_qty, price=f_price,
                        disc=f_disc, tax=f_tax, notes=f_notes, line_id=line_id)

        def _on_product_change(e, rd=row_data):
            pid = rd["prod"].value
            if pid and pid in self._prod_map:
                info = self._prod_map[pid]
                # Auto-fill satuan
                if not rd["uom"].value:
                    rd["uom"].value = info["uom_id"]
                    try: rd["uom"].update()
                    except: pass
                # Auto-fill harga dari vendor price / standard cost
                rd["price"].value = str(int(info["price"]))
                try: rd["price"].update()
                except: pass
                self._update_summary()

        f_prod.on_select = _on_product_change

        def _on_change(e, rd=row_data):
            self._update_summary()

        for fld in [f_qty, f_price, f_disc, f_tax]:
            fld.on_change = _on_change

        def _remove(e, rd=row_data):
            if len(self.rows) > 1:
                self.rows.remove(rd)
                self._rebuild()
                self._update_summary()

        row_data["remove_btn"] = ft.IconButton(
            icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
            icon_color=Colors.ERROR, icon_size=18,
            tooltip="Hapus baris",
            on_click=_remove,
            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
        )
        self.rows.append(row_data)

    def _update_summary(self):
        total = 0.0
        for rd in self.rows:
            try:
                qty   = float(rd["qty"].value or 0)
                price = float(rd["price"].value or 0)
                disc  = float(rd["disc"].value or 0)
                tax   = float(rd["tax"].value or 0)
                line  = qty * price * (1 - disc/100) * (1 + tax/100)
                total += line
            except Exception:
                pass
        self.summary_text.value = f"Estimasi Total: Rp {total:,.0f}"
        try: self.summary_text.update()
        except: pass

    def _rebuild(self):
        header = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
            border_radius=ft.border_radius.only(top_left=6, top_right=6),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            content=ft.Row(spacing=8, controls=[
                ft.Text("Produk",  size=11, color=Colors.TEXT_MUTED, expand=True),
                ft.Text("UoM",     size=11, color=Colors.TEXT_MUTED, width=90),
                ft.Text("Qty",     size=11, color=Colors.TEXT_MUTED, width=90),
                ft.Text("Harga",   size=11, color=Colors.TEXT_MUTED, width=140),
                ft.Text("Disc%",   size=11, color=Colors.TEXT_MUTED, width=70),
                ft.Text("PPN%",    size=11, color=Colors.TEXT_MUTED, width=70),
                ft.Text("Ket.",    size=11, color=Colors.TEXT_MUTED, width=140),
                ft.Container(width=36),
            ]),
        )
        rows_ctrl = []
        for rd in self.rows:
            rows_ctrl.append(ft.Container(
                border=ft.Border.all(1, Colors.BORDER),
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(expand=True, content=rd["prod"]),
                        rd["uom"], rd["qty"], rd["price"],
                        rd["disc"], rd["tax"], rd["notes"],
                        rd["remove_btn"],
                    ],
                ),
            ))

        self.container.controls = [
            header,
            *rows_ctrl,
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Button(
                        content=ft.Row(tight=True, spacing=6, controls=[
                            ft.Icon(ft.Icons.ADD, size=16, color=Colors.ACCENT),
                            ft.Text("Tambah Item", size=13, color=Colors.ACCENT),
                        ]),
                        on_click=lambda e: (self._add_row(), self._rebuild(),
                                            self._update_summary()),
                    ),
                    self.summary_text,
                ],
            ),
        ]
        self._update_summary()
        try: self.container.update()
        except: pass

    def get_lines(self) -> tuple[bool, str, List[Dict]]:
        lines = []
        for i, rd in enumerate(self.rows):
            if not rd["prod"].value:
                return False, f"Baris {i+1}: Produk wajib dipilih.", []
            if not rd["uom"].value:
                return False, f"Baris {i+1}: Satuan wajib dipilih.", []
            try:
                qty = float(rd["qty"].value or 0)
                if qty <= 0:
                    return False, f"Baris {i+1}: Qty harus > 0.", []
                price = float(rd["price"].value or 0)
                if price < 0:
                    return False, f"Baris {i+1}: Harga tidak boleh negatif.", []
            except ValueError:
                return False, f"Baris {i+1}: Nilai angka tidak valid.", []
            lines.append({
                "id":           rd.get("line_id"),
                "product_id":   rd["prod"].value,
                "uom_id":       rd["uom"].value,
                "qty_ordered":  rd["qty"].value,
                "unit_price":   rd["price"].value or "0",
                "discount_pct": rd["disc"].value or "0",
                "tax_pct":      rd["tax"].value or "0",
                "notes":        rd["notes"].value or "",
            })
        return True, "", lines


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 po_id: Optional[int], on_saved,
                 from_pr_id: Optional[int] = None):
    """po_id=None → buat baru, po_id=int → edit"""
    is_edit = po_id is not None

    with SessionLocal() as db:
        branches  = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        vendors   = db.query(Vendor).filter_by(
            company_id=session.company_id, is_active=True).order_by(Vendor.name).all()
        products  = db.query(Product).filter_by(
            company_id=session.company_id, is_purchasable=True, is_active=True)\
            .order_by(Product.name).all()
        uoms      = db.query(UnitOfMeasure).filter_by(is_active=True).all()
        warehouses= db.query(Warehouse)\
            .join(Branch, Warehouse.branch_id == Branch.id)\
            .filter(Branch.company_id == session.company_id,
                    Warehouse.is_active == True).all()
        # PERBAIKAN: PR masih terbuka = APPROVED atau PARTIAL_PO
        from app.services.purchasing_service import PurchaseOrderService as _POS
        approved_prs = _POS.get_open_prs(db, session.company_id)

        # Nilai default
        d_branch_id  = str(session.branch_id) if hasattr(session,"branch_id") and session.branch_id else ""
        d_vendor_id  = ""
        d_pr_id      = ""
        d_wh_id      = ""
        d_currency   = "IDR"
        d_order_date = date.today().strftime("%Y-%m-%d")
        d_exp_date   = ""
        d_payment    = "30 hari"
        d_ship       = ""
        d_disc       = "0"
        d_ship_cost  = "0"
        d_notes      = ""
        d_po_number  = ""
        initial_lines = []

        if is_edit:
            po = PurchaseOrderService.get_by_id(db, po_id)
            if po:
                d_branch_id  = str(po.branch_id)
                d_vendor_id  = str(po.vendor_id)
                d_pr_id      = str(po.pr_id) if po.pr_id else ""
                d_wh_id      = str(po.warehouse_id) if po.warehouse_id else ""
                d_currency   = po.currency_code
                d_order_date = _fmt_date(po.order_date)
                d_exp_date   = _fmt_date(po.expected_date)
                d_payment    = po.payment_terms or ""
                d_ship       = po.shipping_method or ""
                d_disc       = str(int(po.discount_amount))
                d_ship_cost  = str(int(po.shipping_cost))
                d_notes      = po.notes or ""
                d_po_number  = po.po_number
                for ln in (po.lines or []):
                    initial_lines.append({
                        "id": ln.id, "product_id": ln.product_id,
                        "uom_id": ln.uom_id, "qty_ordered": ln.qty_ordered,
                        "unit_price": ln.unit_price, "discount_pct": ln.discount_pct,
                        "tax_pct": ln.tax_pct, "notes": ln.notes or "",
                    })
        elif from_pr_id:
            from app.services.purchasing_service import PurchaseRequestService
            pr = PurchaseRequestService.get_by_id(db, from_pr_id)
            if pr:
                d_branch_id = str(pr.branch_id) if pr.branch_id else d_branch_id
                d_pr_id     = str(pr.id)
                # PERBAIKAN: hanya load item yang belum penuh masuk PO
                unpo = PurchaseRequestService.get_unpo_lines(db, from_pr_id)
                for ln in unpo:
                    initial_lines.append({
                        "product_id": ln["product_id"],
                        "uom_id":     ln["uom_id"],
                        "qty_ordered": ln["qty_remaining"],
                        "unit_price": ln["estimated_price"] or 0,
                    })

        br_opts  = [(str(b.id), b.name) for b in branches]
        vnd_opts = [(str(v.id), f"{v.code} — {v.name}") for v in vendors]
        wh_opts  = [("", "— Pilih Gudang —")] + [(str(w.id), w.name) for w in warehouses]
        _PR_STATUS_LABEL = {
            "APPROVED":   "Belum ada PO",
            "PARTIAL_PO": "Sebagian di-PO",
        }
        pr_opts  = [("", "— Tanpa Referensi PR —")] + [
            (str(p.id),
             f"{p.pr_number}  [{_PR_STATUS_LABEL.get(p.status, p.status)}]"
             f"  ({len(p.lines or [])} item)")
            for p in approved_prs
        ]
        # Load vendor prices jika vendor sudah dipilih (untuk edit)
        vendor_prices = {}
        if is_edit and d_vendor_id:
            from app.models import VendorProduct
            vps = db.query(VendorProduct)                    .filter_by(vendor_id=int(d_vendor_id))                    .all()
            for vp in vps:
                vendor_prices[str(vp.product_id)] = {
                    "price": vp.vendor_price or 0
                }

        prod_list = list(products)
        uom_list  = list(uoms)

    curr_opts = [("IDR","IDR"), ("USD","USD"), ("SGD","SGD"), ("MYR","MYR")]

    f_branch  = make_dropdown("Cabang *", br_opts, d_branch_id)
    f_vendor  = make_dropdown("Vendor *", vnd_opts, d_vendor_id)
    f_pr_ref  = make_dropdown("Referensi PR", pr_opts, d_pr_id)
    f_wh      = make_dropdown("Gudang Tujuan", wh_opts, d_wh_id)
    f_curr    = make_dropdown("Mata Uang", curr_opts, d_currency, width=100)
    f_order_date = make_field("Tgl Order *", d_order_date,
                              hint="YYYY-MM-DD", width=150)
    f_exp_date= make_field("Estimasi Tiba", d_exp_date,
                           hint="YYYY-MM-DD", width=150)
    f_payment = make_field("Termin Pembayaran", d_payment,
                           hint="Contoh: 30 hari NET", width=200)
    f_ship    = make_field("Metode Pengiriman", d_ship,
                           hint="JNE, TIKI, dll", width=200)
    f_disc    = make_field("Diskon Total (Rp)", d_disc,
                           keyboard_type=ft.KeyboardType.NUMBER, width=160)
    f_ship_cost = make_field("Ongkos Kirim (Rp)", d_ship_cost,
                             keyboard_type=ft.KeyboardType.NUMBER, width=160)
    f_notes   = make_field("Catatan", d_notes,
                           multiline=True, min_lines=2, max_lines=3)

    line_editor = POLineEditor(page, prod_list, uom_list, initial_lines, vendor_prices)
    dlg_ref = {"dlg": None}

    def _on_pr_change(e):
        pr_id = f_pr_ref.value
        if not pr_id:
            return

        # Load PR lines + vendor prices dalam satu session
        with SessionLocal() as db:
            from app.services.purchasing_service import PurchaseRequestService
            from app.models import VendorProduct
            pr = PurchaseRequestService.get_by_id(db, int(pr_id))
            if not pr:
                return

            # Load vendor prices jika vendor sudah dipilih
            vp_map = {}
            if f_vendor.value:
                vps = db.query(VendorProduct)\
                        .filter_by(vendor_id=int(f_vendor.value)).all()
                for vp in vps:
                    vp_map[str(vp.product_id)] = vp.vendor_price or 0

            # PERBAIKAN: hanya ambil item yang belum penuh di-PO
            from app.services.purchasing_service import PurchaseRequestService
            unpo_lines = PurchaseRequestService.get_unpo_lines(db, int(pr_id))

            new_lines = []
            for ln in unpo_lines:
                pid = str(ln["product_id"])
                # Prioritas: vendor_price > estimated_price
                if pid in vp_map and vp_map[pid] > 0:
                    price = vp_map[pid]
                else:
                    price = ln["estimated_price"] or 0

                new_lines.append({
                    "product_id":  ln["product_id"],
                    "uom_id":      ln["uom_id"],
                    "qty_ordered": ln["qty_remaining"],  # sisa qty yang belum di-PO
                    "unit_price":  price,
                })

            if pr.branch_id and not f_branch.value:
                f_branch.value = str(pr.branch_id)
                try: f_branch.update()
                except: pass

        # Update prod_map dengan vendor prices baru
        if vp_map:
            for pid, price in vp_map.items():
                if pid in line_editor._prod_map:
                    line_editor._prod_map[pid]["price"] = price

        # Rebuild baris
        line_editor.rows.clear()
        for ln in new_lines:
            line_editor._add_row(
                product_id=str(ln["product_id"]),
                uom_id=str(ln["uom_id"]),
                qty=str(ln["qty_ordered"]),
                price=str(int(ln["unit_price"])),
            )
        line_editor._rebuild()
        line_editor._update_summary()
        try:
            if dlg_ref["dlg"]:
                dlg_ref["dlg"].update()
        except Exception:
            pass

    f_pr_ref.on_select = _on_pr_change

    def _on_vendor_change(e):
        """Saat vendor diganti, reload vendor prices ke semua baris."""
        vid = f_vendor.value
        if not vid:
            return
        vp_map = {}
        with SessionLocal() as db:
            from app.models import VendorProduct
            vps = db.query(VendorProduct).filter_by(vendor_id=int(vid)).all()
            for vp in vps:
                vp_map[str(vp.product_id)] = vp.vendor_price or 0

        # Update prod_map di editor
        for pid, price in vp_map.items():
            if pid in line_editor._prod_map:
                line_editor._prod_map[pid]["price"] = price

        # Update harga di semua baris yang sudah ada produknya
        for rd in line_editor.rows:
            pid = rd["prod"].value
            if pid and pid in vp_map and vp_map[pid] > 0:
                rd["price"].value = str(int(vp_map[pid]))
            elif pid and pid in line_editor._prod_map:
                rd["price"].value = str(int(line_editor._prod_map[pid]["price"]))

        line_editor._update_summary()
        try:
            if dlg_ref["dlg"]:
                dlg_ref["dlg"].update()
        except Exception:
            pass

    f_vendor.on_select = _on_vendor_change

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_branch.value:
            show_err("Cabang wajib dipilih."); return
        if not f_vendor.value:
            show_err("Vendor wajib dipilih."); return
        order_date = _parse_date(f_order_date.value)
        if not order_date:
            show_err("Tanggal order tidak valid."); return

        valid, errmsg, lines = line_editor.get_lines()
        if not valid:
            show_err(errmsg); return

        data = {
            "branch_id":      f_branch.value,
            "vendor_id":      f_vendor.value,
            "pr_id":          f_pr_ref.value or None,
            "warehouse_id":   f_wh.value or None,
            "currency_code":  f_curr.value,
            "order_date":     order_date,
            "expected_date":  _parse_date(f_exp_date.value),
            "payment_terms":  f_payment.value,
            "shipping_method":f_ship.value,
            "discount_amount":f_disc.value or "0",
            "shipping_cost":  f_ship_cost.value or "0",
            "notes":          f_notes.value,
        }

        with SessionLocal() as db:
            if is_edit:
                ok, msg = PurchaseOrderService.update(db, po_id, data, lines)
            else:
                ok, msg, _ = PurchaseOrderService.create(
                    db, session.company_id, session.user_id, data, lines)

        dlg.open = False
        page.update()
        show_snack(page, msg, ok)
        if ok:
            on_saved()

    title_str = f"Edit PO — {d_po_number}" if is_edit else "Buat Purchase Order"
    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.RECEIPT_LONG, color=Colors.ACCENT, size=20),
                    ft.Text(
                        title_str,
                        color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_700, size=16,
                    ),
                ]),
                ft.IconButton(
                    ft.Icons.CLOSE,
                    icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                    on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                ),
            ],
        ),
        content=ft.Container(
            width=980, height=580,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO, spacing=14,
                controls=[
                    err,
                    section_card("Header PO", [
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs":12,"sm":4}, content=f_branch),
                            ft.Container(col={"xs":12,"sm":5}, content=f_vendor),
                            ft.Container(col={"xs":12,"sm":3}, content=f_curr),
                        ]),
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs":12,"sm":4}, content=f_pr_ref),
                            ft.Container(col={"xs":12,"sm":4}, content=f_wh),
                        ]),
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs":12,"sm":3}, content=f_order_date),
                            ft.Container(col={"xs":12,"sm":3}, content=f_exp_date),
                            ft.Container(col={"xs":12,"sm":4}, content=f_payment),
                            ft.Container(col={"xs":12,"sm":4}, content=f_ship),
                        ]),
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs":12,"sm":4}, content=f_disc),
                            ft.Container(col={"xs":12,"sm":4}, content=f_ship_cost),
                        ]),
                        f_notes,
                    ]),
                    section_card("Item PO", [line_editor.container]),
                ],
            ),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal",
                style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                on_click=lambda e: (setattr(dlg, "open", False), page.update()),
            ),
            ft.Button("Simpan",
                bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0,
                ),
                on_click=save,
            ),
        ],
    )
    page.overlay.append(dlg)
    dlg_ref["dlg"] = dlg
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# DETAIL DIALOG
# ─────────────────────────────────────────────────────────────
def _detail_dialog(page, session: AppSession, po_id: int, on_saved):
    with SessionLocal() as db:
        po_f = PurchaseOrderService.get_by_id(db, po_id)
        if not po_f:
            show_snack(page, "PO tidak ditemukan.", False); return
        po_number  = po_f.po_number
        po_status  = po_f.status
        vendor_name= po_f.vendor.name if po_f.vendor else "—"
        order_date = _fmt_date(po_f.order_date)
        subtotal   = po_f.subtotal
        tax_amount = po_f.tax_amount
        disc_amount= po_f.discount_amount
        ship_cost  = po_f.shipping_cost
        total      = po_f.total_amount
        lines_data = []
        for ln in (po_f.lines or []):
            sub = ln.qty_ordered * ln.unit_price * (1 - ln.discount_pct/100)
            tax = sub * ln.tax_pct / 100
            lines_data.append({
                "product_name": ln.product.name if ln.product else "—",
                "product_code": ln.product.code if ln.product else "",
                "uom_code":     ln.uom.code if ln.uom else "—",
                "qty_ordered":  ln.qty_ordered,
                "unit_price":   ln.unit_price,
                "discount_pct": ln.discount_pct,
                "tax_pct":      ln.tax_pct,
                "line_total":   sub + tax,
            })

    can_confirm = po_status == "SENT" and session.has_perm("PUR_PO", "can_approve")

    line_rows = []
    for i, ld in enumerate(lines_data):
        line_rows.append(ft.Container(
            border=ft.Border.all(1, Colors.BORDER),
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Row(spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(width=28, content=ft.Text(str(i+1), size=12,
                                                            color=Colors.TEXT_MUTED)),
                    ft.Container(expand=True, content=ft.Column(spacing=1, tight=True, controls=[
                        ft.Text(ld["product_name"], size=13,
                                color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_500),
                        ft.Text(ld["product_code"], size=11,
                                color=Colors.TEXT_MUTED, font_family="monospace"),
                    ])),
                    ft.Container(width=60, content=ft.Text(
                        ld["uom_code"], size=12, color=Colors.TEXT_SECONDARY)),
                    ft.Container(width=80, content=ft.Text(
                        f"{ld['qty_ordered']:,.2f}", size=12,
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_500)),
                    ft.Container(width=110, content=ft.Text(
                        f"Rp {ld['unit_price']:,.0f}", size=12,
                        color=Colors.TEXT_SECONDARY)),
                    ft.Container(width=60, content=ft.Text(
                        f"{ld['discount_pct']:.0f}%" if ld["discount_pct"] else "—",
                        size=12, color=Colors.TEXT_MUTED)),
                    ft.Container(width=60, content=ft.Text(
                        f"{ld['tax_pct']:.0f}%" if ld["tax_pct"] else "—",
                        size=12, color=Colors.TEXT_MUTED)),
                    ft.Container(width=130, content=ft.Text(
                        f"Rp {ld['line_total']:,.0f}", size=12,
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600)),
                ],
            ),
        ))

    def do_confirm(e):
        with SessionLocal() as db:
            ok, msg = PurchaseOrderService.confirm(db, po_id, session.user_id)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    actions = [
        ft.Button("Tutup",
            style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
            on_click=lambda e: (setattr(dlg, "open", False), page.update()),
        ),
    ]
    if can_confirm:
        actions.append(ft.Button("Konfirmasi PO",
            bgcolor=Colors.SUCCESS, color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                elevation=0,
            ),
            on_click=do_confirm,
        ))

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=4, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.RECEIPT_LONG, color=Colors.ACCENT, size=18),
                        ft.Text(po_number, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                        _po_badge(po_status),
                    ]),
                    ft.Row(spacing=16, controls=[
                        ft.Text(f"Vendor: {vendor_name}",
                                size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Tgl: {order_date}",
                                size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Total: Rp {total:,.0f}",
                                size=12, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_600),
                    ]),
                ]),
                ft.IconButton(ft.Icons.CLOSE,
                    icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                    on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                ),
            ],
        ),
        content=ft.Container(
            width=860, height=460,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO, spacing=8,
                controls=[
                    # Kolom header
                    ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                        border_radius=4,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        content=ft.Row(spacing=8, controls=[
                            ft.Container(width=28),
                            ft.Container(expand=True,
                                content=ft.Text("Produk", size=11, color=Colors.TEXT_MUTED)),
                            ft.Container(width=60,
                                content=ft.Text("UoM", size=11, color=Colors.TEXT_MUTED)),
                            ft.Container(width=80,
                                content=ft.Text("Qty", size=11, color=Colors.TEXT_MUTED)),
                            ft.Container(width=110,
                                content=ft.Text("Harga", size=11, color=Colors.TEXT_MUTED)),
                            ft.Container(width=60,
                                content=ft.Text("Disc", size=11, color=Colors.TEXT_MUTED)),
                            ft.Container(width=60,
                                content=ft.Text("PPN", size=11, color=Colors.TEXT_MUTED)),
                            ft.Container(width=130,
                                content=ft.Text("Subtotal", size=11,
                                                color=Colors.TEXT_MUTED,
                                                weight=ft.FontWeight.W_600)),
                        ]),
                    ),
                    *line_rows,
                    # Ringkasan biaya
                    ft.Divider(height=1, color=Colors.BORDER),
                    ft.Container(
                        alignment=ft.Alignment(1, 0),
                        padding=ft.Padding.only(right=10),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            spacing=4,
                            controls=[
                                ft.Text(f"Subtotal: Rp {subtotal:,.0f}",
                                        size=12, color=Colors.TEXT_SECONDARY),
                                ft.Text(f"PPN: Rp {tax_amount:,.0f}",
                                        size=12, color=Colors.TEXT_SECONDARY),
                                ft.Text(f"Diskon: -Rp {disc_amount:,.0f}",
                                        size=12, color=Colors.TEXT_SECONDARY),
                                ft.Text(f"Ongkos Kirim: Rp {ship_cost:,.0f}",
                                        size=12, color=Colors.TEXT_SECONDARY),
                                ft.Divider(height=1, color=Colors.BORDER),
                                ft.Text(f"TOTAL: Rp {total:,.0f}",
                                        size=14, weight=ft.FontWeight.W_700,
                                        color=Colors.TEXT_PRIMARY),
                            ],
                        ),
                    ),
                ],
            ),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=actions,
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# TABLE ROWS — pakai plain dicts
# ─────────────────────────────────────────────────────────────
def _build_rows(po_data: List[Dict], page, session, refresh):
    rows = []
    for d in po_data:
        actions = [
            action_btn(ft.Icons.VISIBILITY_OUTLINED, "Detail",
                lambda e, pid=d["id"]: _detail_dialog(page, session, pid, refresh),
                Colors.INFO),
        ]
        if d["status"] == "DRAFT":
            actions += [
                action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, pid=d["id"]: _form_dialog(page, session, pid, refresh),
                    Colors.TEXT_SECONDARY),
                action_btn(ft.Icons.SEND, "Kirim ke Vendor",
                    lambda e, pid=d["id"], pno=d["po_number"]: confirm_dialog(
                        page, "Kirim PO", f"Kirim PO {pno} ke vendor?",
                        lambda: _send(pid, page, refresh),
                        "Ya, Kirim", Colors.INFO),
                    Colors.ACCENT),
                action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, pid=d["id"], pno=d["po_number"]: confirm_dialog(
                        page, "Hapus PO", f"Hapus PO {pno}?",
                        lambda: _delete(pid, page, refresh)),
                    Colors.ERROR),
            ]
        if d["status"] == "SENT" and session.has_perm("PUR_PO", "can_approve"):
            actions.append(action_btn(
                ft.Icons.CHECK_CIRCLE_OUTLINE, "Konfirmasi",
                lambda e, pid=d["id"]: _detail_dialog(page, session, pid, refresh),
                Colors.SUCCESS))
        if d["status"] not in ("RECEIVED", "CANCELLED"):
            actions.append(action_btn(
                ft.Icons.CANCEL_OUTLINED, "Batalkan",
                lambda e, pid=d["id"], pno=d["po_number"]: confirm_dialog(
                    page, "Batalkan PO", f"Batalkan PO {pno}?",
                    lambda: _cancel(pid, page, refresh),
                    "Ya, Batalkan", Colors.WARNING),
                Colors.WARNING))

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["po_number"], size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY, font_family="monospace"),
                ft.Text(d["vendor_name"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["branch_name"], size=12,
                                color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["order_date"], size=12,
                                color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(d["expected_date"] or "—", size=12,
                                color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"{d['item_count']} item", size=12,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(f"Rp {d['total_amount']:,.0f}", size=11,
                        color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(_po_badge(d["status"])),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def _pos_to_dicts(pos) -> List[Dict]:
    result = []
    for po in pos:
        result.append({
            "id":           po.id,
            "po_number":    po.po_number,
            "status":       po.status,
            "vendor_name":  po.vendor.name if po.vendor else "—",
            "branch_name":  po.branch.name if po.branch else "—",
            "order_date":   _fmt_date(po.order_date),
            "expected_date":_fmt_date(po.expected_date),
            "item_count":   len(po.lines or []),
            "total_amount": po.total_amount,
        })
    return result


def _send(pid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PurchaseOrderService.send(db, pid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _cancel(pid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PurchaseOrderService.cancel(db, pid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _delete(pid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PurchaseOrderService.delete(db, pid)
    show_snack(page, msg, ok)
    if ok: refresh()


# ─────────────────────────────────────────────────────────────
# FILTER BAR
# ─────────────────────────────────────────────────────────────
def _filter_bar(active_status: Dict, on_filter) -> ft.Control:
    filters = [("", "Semua")] + _STATUS_OPTS
    btns = []
    for val, label in filters:
        is_act = active_status["v"] == val
        color  = _STATUS_COLOR.get(val, Colors.TEXT_SECONDARY)
        btns.append(ft.Container(
            height=32,
            padding=ft.Padding.symmetric(horizontal=12),
            border_radius=Sizes.BTN_RADIUS,
            bgcolor=ft.Colors.with_opacity(0.12, color) if is_act else ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, color if is_act else Colors.BORDER),
            on_click=lambda e, v=val: on_filter(v),
            ink=True,
            content=ft.Text(label, size=12,
                color=color if is_act else Colors.TEXT_SECONDARY,
                weight=ft.FontWeight.W_600 if is_act else ft.FontWeight.W_400),
        ))
    return ft.Row(spacing=6, wrap=True, controls=btns)


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def PurchaseOrderPage(page, session: AppSession) -> ft.Control:
    search_val  = {"q": ""}
    status_val  = {"v": ""}
    filter_area = ft.Container()

    def _load() -> List[Dict]:
        with SessionLocal() as db:
            pos = PurchaseOrderService.get_all(
                db, session.company_id, search_val["q"], status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _pos_to_dicts(pos)

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("No. PO / Vendor",   size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang",             size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tgl Order",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Est. Tiba",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item / Total",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",             size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",               size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
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
        controls=[table if initial else empty_state("Belum ada Purchase Order.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def refresh():
        data = _load()
        table.rows = _build_rows(data, page, session, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada PO ditemukan.")]
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
            expand=True,
            spacing=0,
            controls=[
                page_header(
                    "Purchase Order",
                    "Kelola pesanan pembelian ke vendor",
                    "Buat PO Baru",
                    on_action=lambda: _form_dialog(page, session, None, refresh),
                    action_icon=ft.Icons.ADD,
                ),
                ft.Container(
                    padding=ft.Padding.only(bottom=12),
                    content=filter_area,
                ),
                ft.Row(controls=[search_bar("Cari nomor PO...", on_search)]),
                ft.Container(height=12),
                ft.Container(
                    expand=True,
                    content=ft.ListView(expand=True, controls=[table_area]),
                ),
            ],
        ),
    )