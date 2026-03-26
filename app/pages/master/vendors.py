"""
app/pages/master/vendors.py
Master Data → Vendor + Vendor Products (produk yang dijual vendor)
"""
from __future__ import annotations
import flet as ft
from typing import Optional, List, Dict

from app.database import SessionLocal
from app.models import Vendor, VendorProduct, Product, UnitOfMeasure
from app.services.master_service import VendorService
from app.services.auth import AppSession
from app.pages.master._base import MasterPage
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack, section_card,
)
from app.utils.theme import Colors, Sizes

_VTYPE_OPTS = [
    ("SUPPLIER",     "Supplier"),
    ("MANUFACTURER", "Manufaktur"),
    ("DISTRIBUTOR",  "Distributor"),
    ("SERVICE",      "Jasa"),
]


# ─────────────────────────────────────────────────────────────
# FORM VENDOR (tambah / edit)
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 vendor: Optional[Vendor], on_saved):
    is_edit = vendor is not None
    v = vendor

    f_code    = make_field("Kode *",
                           v.code if is_edit else "",
                           read_only=is_edit, width=140)
    f_name    = make_field("Nama Vendor *", v.name if is_edit else "")
    f_legal   = make_field("Nama Legal", v.legal_name or "" if is_edit else "")
    f_tax     = make_field("NPWP", v.tax_id or "" if is_edit else "", width=200)
    f_type    = make_dropdown("Tipe", _VTYPE_OPTS,
                              v.vendor_type if is_edit else "SUPPLIER", width=180)
    f_phone   = make_field("Telepon", v.phone or "" if is_edit else "", width=200)
    f_email   = make_field("Email", v.email or "" if is_edit else "",
                           keyboard_type=ft.KeyboardType.EMAIL)
    f_city    = make_field("Kota", v.city or "" if is_edit else "", width=180)
    f_province= make_field("Provinsi", v.province or "" if is_edit else "", width=180)
    f_address = make_field("Alamat", v.address or "" if is_edit else "",
                           multiline=True, min_lines=2, max_lines=3)
    f_terms   = make_field("Termin (hari)",
                           str(v.payment_terms_days) if is_edit else "30",
                           keyboard_type=ft.KeyboardType.NUMBER, width=140)
    f_bank    = make_field("Bank", v.bank_name or "" if is_edit else "", width=200)
    f_acc_no  = make_field("No. Rekening", v.bank_account or "" if is_edit else "", width=200)
    f_acc_name= make_field("Atas Nama", v.bank_account_name or "" if is_edit else "")
    f_active  = ft.Switch(label="Aktif",
                          value=v.is_active if is_edit else True,
                          active_color=Colors.ACCENT)
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def save(e):
        if not f_name.value.strip():
            err.value = "Nama wajib diisi."; err.visible = True
            try: err.update()
            except: pass
            return
        if not is_edit and not f_code.value.strip():
            err.value = "Kode wajib diisi."; err.visible = True
            try: err.update()
            except: pass
            return
        data = {
            "code": f_code.value, "name": f_name.value,
            "legal_name": f_legal.value, "tax_id": f_tax.value,
            "vendor_type": f_type.value, "phone": f_phone.value,
            "email": f_email.value, "city": f_city.value,
            "province": f_province.value, "address": f_address.value,
            "payment_terms_days": f_terms.value,
            "bank_name": f_bank.value, "bank_account": f_acc_no.value,
            "bank_account_name": f_acc_name.value,
            "is_active": f_active.value,
        }
        with SessionLocal() as db:
            ok, msg = (VendorService.update(db, vendor.id, data) if is_edit
                       else VendorService.create(db, session.company_id, data)[0:2])
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Row(spacing=10, controls=[
                ft.Icon(ft.Icons.BUSINESS, color=Colors.ACCENT, size=20),
                ft.Text("Edit Vendor" if is_edit else "Tambah Vendor",
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700, size=16),
            ]),
            ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                          icon_size=18,
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
        ]),
        content=ft.Container(width=540, height=520, content=ft.Column(
            scroll=ft.ScrollMode.AUTO, spacing=14,
            controls=[
                err,
                section_card("Informasi Vendor", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":4}, content=f_code),
                        ft.Container(col={"xs":12,"sm":4}, content=f_type),
                        ft.Container(col={"xs":12,"sm":4}, content=f_tax),
                    ]),
                    f_name, f_legal,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_phone),
                        ft.Container(col={"xs":12,"sm":6}, content=f_email),
                    ]),
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_city),
                        ft.Container(col={"xs":12,"sm":6}, content=f_province),
                    ]),
                    f_address,
                    ft.Row(spacing=16, controls=[f_terms, f_active]),
                ]),
                section_card("Rekening Bank", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":5}, content=f_bank),
                        ft.Container(col={"xs":12,"sm":7}, content=f_acc_no),
                    ]),
                    f_acc_name,
                ]),
            ],
        )),
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
    page.overlay.append(dlg); dlg.open = True; page.update()


# ─────────────────────────────────────────────────────────────
# VENDOR PRODUCTS DIALOG
# Kelola produk yang dijual vendor beserta harga & lead time
# ─────────────────────────────────────────────────────────────
def _vendor_products_dialog(page, session: AppSession, vendor_id: int, vendor_name: str):

    def _load() -> List[Dict]:
        with SessionLocal() as db:
            vps = db.query(VendorProduct)\
                    .filter_by(vendor_id=vendor_id)\
                    .options(
                        __import__('sqlalchemy.orm', fromlist=['joinedload'])
                        .joinedload(VendorProduct.product)
                        .joinedload(Product.uom)
                    ).all()
            return [{
                "id":            vp.id,
                "product_id":    vp.product_id,
                "product_name":  vp.product.name if vp.product else "—",
                "product_code":  vp.product.code if vp.product else "—",
                "uom_code":      vp.product.uom.code if (vp.product and vp.product.uom) else "—",
                "vendor_sku":    vp.vendor_sku or "",
                "vendor_price":  vp.vendor_price or 0,
                "min_order_qty": vp.min_order_qty,
                "lead_time_days":vp.lead_time_days,
                "is_preferred":  vp.is_preferred,
            } for vp in vps]

    # ── Sub-form: tambah / edit satu baris vendor product ──
    def _vp_row_form(vp_data: Optional[Dict], on_saved_vp):
        with SessionLocal() as db:
            products = db.query(Product).filter_by(
                company_id=session.company_id,
                is_purchasable=True, is_active=True
            ).order_by(Product.name).all()
            prod_opts = [(str(p.id), f"{p.code} — {p.name}") for p in products]

        f_prod   = make_dropdown("Produk *", prod_opts,
                                 str(vp_data["product_id"]) if vp_data else "")
        f_sku    = make_field("SKU Vendor", vp_data["vendor_sku"] if vp_data else "",
                              hint="Kode produk di vendor", width=160)
        f_price  = make_field("Harga Beli *",
                              str(int(vp_data["vendor_price"])) if vp_data else "0",
                              keyboard_type=ft.KeyboardType.NUMBER, width=160)
        f_moq    = make_field("Min. Order",
                              str(vp_data["min_order_qty"]) if vp_data else "1",
                              keyboard_type=ft.KeyboardType.NUMBER, width=120)
        f_lead   = make_field("Lead Time (hari)",
                              str(vp_data["lead_time_days"]) if vp_data else "0",
                              keyboard_type=ft.KeyboardType.NUMBER, width=140)
        f_pref   = ft.Checkbox(label="Vendor Utama untuk produk ini",
                               value=vp_data["is_preferred"] if vp_data else False,
                               active_color=Colors.ACCENT)
        err2 = ft.Text("", color=Colors.ERROR, size=12, visible=False)

        def do_save(e):
            if not f_prod.value:
                err2.value = "Produk wajib dipilih."; err2.visible = True
                try: err2.update()
                except: pass
                return
            try:
                price = float(f_price.value or 0)
                moq   = float(f_moq.value or 1)
                lead  = int(f_lead.value or 0)
            except ValueError:
                err2.value = "Nilai angka tidak valid."; err2.visible = True
                try: err2.update()
                except: pass
                return

            with SessionLocal() as db:
                if vp_data:  # edit
                    vp = db.query(VendorProduct).filter_by(id=vp_data["id"]).first()
                    if vp:
                        vp.vendor_sku    = f_sku.value.strip() or None
                        vp.vendor_price  = price
                        vp.min_order_qty = moq
                        vp.lead_time_days= lead
                        vp.is_preferred  = f_pref.value
                        if f_pref.value:
                            # Reset preferred lain untuk produk yang sama
                            db.query(VendorProduct)\
                              .filter_by(vendor_id=vendor_id,
                                         product_id=int(f_prod.value))\
                              .filter(VendorProduct.id != vp.id)\
                              .update({"is_preferred": False})
                        db.commit()
                        ok, msg = True, "Produk vendor diperbarui."
                    else:
                        ok, msg = False, "Data tidak ditemukan."
                else:  # tambah
                    exists = db.query(VendorProduct).filter_by(
                        vendor_id=vendor_id, product_id=int(f_prod.value)).first()
                    if exists:
                        ok, msg = False, "Produk sudah terdaftar untuk vendor ini."
                    else:
                        if f_pref.value:
                            db.query(VendorProduct)\
                              .filter_by(vendor_id=vendor_id,
                                         product_id=int(f_prod.value))\
                              .update({"is_preferred": False})
                        vp_new = VendorProduct(
                            vendor_id=vendor_id,
                            product_id=int(f_prod.value),
                            vendor_sku=f_sku.value.strip() or None,
                            vendor_price=price,
                            min_order_qty=moq,
                            lead_time_days=lead,
                            is_preferred=f_pref.value,
                        )
                        db.add(vp_new)
                        db.commit()
                        ok, msg = True, "Produk vendor ditambahkan."

            sub_dlg.open = False; page.update()
            show_snack(page, msg, ok)
            if ok: on_saved_vp()

        sub_dlg = ft.AlertDialog(
            modal=True, bgcolor=Colors.BG_CARD,
            title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text("Edit Produk Vendor" if vp_data else "Tambah Produk Vendor",
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700, size=15),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(sub_dlg,"open",False), page.update())),
            ]),
            content=ft.Container(width=460, content=ft.Column(
                spacing=12, tight=True,
                controls=[
                    err2,
                    f_prod,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_sku),
                        ft.Container(col={"xs":12,"sm":6}, content=f_price),
                    ]),
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":5}, content=f_moq),
                        ft.Container(col={"xs":12,"sm":5}, content=f_lead),
                    ]),
                    f_pref,
                ],
            )),
            actions_alignment=ft.MainAxisAlignment.END,
            actions=[
                ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                              on_click=lambda e: (setattr(sub_dlg,"open",False), page.update())),
                ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                        elevation=0),
                    on_click=do_save),
            ],
        )
        page.overlay.append(sub_dlg); sub_dlg.open = True; page.update()

    # ── Build tabel produk vendor ──
    list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)

    def _rebuild_list():
        data = _load()
        rows = []

        if not data:
            rows.append(ft.Container(
                padding=ft.Padding.all(24),
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=32,
                                color=Colors.TEXT_MUTED),
                        ft.Text("Belum ada produk terdaftar",
                                size=13, color=Colors.TEXT_MUTED),
                    ],
                ),
            ))
        else:
            # Header
            rows.append(ft.Container(
                bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                content=ft.Row(spacing=8, controls=[
                    ft.Container(expand=True,
                        content=ft.Text("Produk", size=11,
                                        color=Colors.TEXT_MUTED, weight=ft.FontWeight.W_600)),
                    ft.Container(width=60,
                        content=ft.Text("UoM", size=11, color=Colors.TEXT_MUTED)),
                    ft.Container(width=80,
                        content=ft.Text("SKU Vendor", size=11, color=Colors.TEXT_MUTED)),
                    ft.Container(width=120,
                        content=ft.Text("Harga Beli", size=11, color=Colors.TEXT_MUTED)),
                    ft.Container(width=80,
                        content=ft.Text("Min. Order", size=11, color=Colors.TEXT_MUTED)),
                    ft.Container(width=80,
                        content=ft.Text("Lead Time", size=11, color=Colors.TEXT_MUTED)),
                    ft.Container(width=30),
                    ft.Container(width=72),
                ]),
            ))
            for d in data:
                rows.append(ft.Container(
                    border=ft.Border.all(1,
                        ft.Colors.with_opacity(0.3, Colors.ACCENT)
                        if d["is_preferred"] else Colors.BORDER),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    bgcolor=ft.Colors.with_opacity(0.02, Colors.ACCENT)
                            if d["is_preferred"] else None,
                    content=ft.Row(spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(expand=True, content=ft.Column(
                                spacing=1, tight=True, controls=[
                                    ft.Row(spacing=6, controls=[
                                        ft.Text(d["product_name"], size=13,
                                                color=Colors.TEXT_PRIMARY,
                                                weight=ft.FontWeight.W_500),
                                        *([ ft.Container(
                                            content=ft.Text("Utama", size=10,
                                                            color=Colors.SUCCESS,
                                                            weight=ft.FontWeight.W_600),
                                            bgcolor=ft.Colors.with_opacity(0.12, Colors.SUCCESS),
                                            border_radius=4,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        )] if d["is_preferred"] else []),
                                    ]),
                                    ft.Text(d["product_code"], size=11,
                                            color=Colors.TEXT_MUTED,
                                            font_family="monospace"),
                                ],
                            )),
                            ft.Container(width=60,
                                content=ft.Text(d["uom_code"], size=12,
                                                color=Colors.TEXT_SECONDARY)),
                            ft.Container(width=80,
                                content=ft.Text(d["vendor_sku"] or "—", size=12,
                                                color=Colors.TEXT_MUTED)),
                            ft.Container(width=120,
                                content=ft.Text(
                                    f"Rp {d['vendor_price']:,.0f}" if d["vendor_price"] else "—",
                                    size=12, color=Colors.TEXT_PRIMARY,
                                    weight=ft.FontWeight.W_500)),
                            ft.Container(width=80,
                                content=ft.Text(f"{d['min_order_qty']:,.0f}",
                                                size=12, color=Colors.TEXT_SECONDARY)),
                            ft.Container(width=80,
                                content=ft.Text(f"{d['lead_time_days']} hari",
                                                size=12, color=Colors.TEXT_SECONDARY)),
                            # Preferred toggle
                            ft.Container(width=30, content=ft.IconButton(
                                icon=ft.Icons.STAR if d["is_preferred"]
                                     else ft.Icons.STAR_BORDER_OUTLINED,
                                icon_color=Colors.WARNING if d["is_preferred"]
                                           else Colors.TEXT_MUTED,
                                icon_size=18,
                                tooltip="Set sebagai vendor utama",
                                on_click=lambda e, vpid=d["id"], pid=d["product_id"]:
                                    _toggle_preferred(vpid, pid),
                                style=ft.ButtonStyle(padding=ft.Padding.all(2)),
                            )),
                            ft.Row(spacing=0, controls=[
                                action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                                    lambda e, dd=d: _vp_row_form(dd, _rebuild_list),
                                    Colors.INFO),
                                action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                                    lambda e, vpid=d["id"], nm=d["product_name"]:
                                        confirm_dialog(page, "Hapus Produk Vendor",
                                            f"Hapus '{nm}' dari vendor ini?",
                                            lambda: _del_vp(vpid)),
                                    Colors.ERROR),
                            ]),
                        ],
                    ),
                ))

        list_col.controls = rows
        try: list_col.update()
        except: pass

    def _toggle_preferred(vp_id: int, product_id: int):
        with SessionLocal() as db:
            vp = db.query(VendorProduct).filter_by(id=vp_id).first()
            if vp:
                new_val = not vp.is_preferred
                if new_val:
                    db.query(VendorProduct)\
                      .filter_by(vendor_id=vendor_id, product_id=product_id)\
                      .filter(VendorProduct.id != vp_id)\
                      .update({"is_preferred": False})
                vp.is_preferred = new_val
                db.commit()
        _rebuild_list()

    def _del_vp(vp_id: int):
        with SessionLocal() as db:
            vp = db.query(VendorProduct).filter_by(id=vp_id).first()
            if vp:
                db.delete(vp); db.commit()
        show_snack(page, "Produk vendor dihapus.", True)
        _rebuild_list()

    _rebuild_list()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Column(spacing=2, tight=True, controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.INVENTORY_2, color=Colors.ACCENT, size=20),
                    ft.Text("Produk Vendor", color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.Text(vendor_name, size=12, color=Colors.TEXT_MUTED),
            ]),
            ft.Row(spacing=8, controls=[
                ft.Button(
                    content=ft.Row(tight=True, spacing=6, controls=[
                        ft.Icon(ft.Icons.ADD, size=14, color=Colors.TEXT_ON_ACCENT),
                        ft.Text("Tambah Produk", size=12, color=Colors.TEXT_ON_ACCENT),
                    ]),
                    bgcolor=Colors.ACCENT,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                        elevation=0),
                    on_click=lambda e: _vp_row_form(None, _rebuild_list),
                ),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ]),
        ]),
        content=ft.Container(
            width=820, height=480,
            content=list_col,
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Tutup", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


# ─────────────────────────────────────────────────────────────
# TABLE ROWS
# ─────────────────────────────────────────────────────────────
def _build_rows(vendors, page, session, refresh):
    rows = []
    for v in vendors:
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(v.name, size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(v.code, size=11, color=Colors.TEXT_MUTED,
                        font_family="monospace"),
            ])),
            ft.DataCell(ft.Text(v.vendor_type, size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(v.tax_id or "—", size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(v.phone or "—", size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(v.email or "—", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(
                f"{v.city or ''} {v.province or ''}".strip() or "—",
                size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(f"{v.payment_terms_days} hari",
                                size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(status_badge(v.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                # Tombol produk vendor
                action_btn(
                    ft.Icons.INVENTORY_2_OUTLINED, "Produk Vendor",
                    lambda e, vid=v.id, vnm=v.name:
                        _vendor_products_dialog(page, session, vid, vnm),
                    Colors.ACCENT,
                ),
                action_btn(
                    ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, vd=v: _form_dialog(page, session, vd, refresh),
                    Colors.INFO,
                ),
                action_btn(
                    ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, vid=v.id, nm=v.name: confirm_dialog(
                        page, "Hapus Vendor", f"Hapus vendor '{nm}'?",
                        lambda: _delete(vid, page, refresh)),
                    Colors.ERROR,
                ),
            ])),
        ]))
    return rows


def _delete(vid, page, refresh):
    with SessionLocal() as db:
        ok, msg = VendorService.delete(db, vid)
    show_snack(page, msg, ok)
    if ok: refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def VendorsPage(page, session: AppSession):
    search_val = {"q": ""}

    with SessionLocal() as db:
        initial = VendorService.get_all(db, session.company_id)

    COLS = [
        ft.DataColumn(ft.Text("Nama / Kode", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("NPWP",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kontak",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kota",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Termin",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Vendor",
        subtitle="Kelola data vendor dan produk yang mereka jual",
        add_label="Tambah Vendor",
        search_hint="Cari nama atau kode vendor...",
        columns=COLS,
        initial_rows=_build_rows(initial, page, session, lambda: None),
        on_add=lambda: _form_dialog(page, session, None, refresh),
        on_search=lambda e: (
            search_val.update({"q": e.control.value or ""}), refresh()
        ),
        add_icon=ft.Icons.ADD_BUSINESS,
    )

    def refresh():
        with SessionLocal() as db:
            data = VendorService.get_all(db, session.company_id, search_val["q"])
        set_rows(_build_rows(data, page, session, refresh))

    set_rows(_build_rows(initial, page, session, refresh))
    return ctrl
