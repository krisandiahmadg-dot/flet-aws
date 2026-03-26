"""
app/pages/master/products.py
Master Data → Produk & Kategori (dua tab dalam satu halaman)
"""
from __future__ import annotations
import flet as ft
from typing import Optional, List

from app.database import SessionLocal
from app.models import Product, ProductCategory, UnitOfMeasure
from app.services.master_service import ProductService, ProductCategoryService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack,
    page_header, search_bar, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_PROD_TYPE_OPTS = [
    ("GOODS",   "Barang"),
    ("SERVICE", "Jasa"),
    ("BUNDLE",  "Bundle / Paket"),
]
_TRACKING_OPTS = [
    ("NONE",   "Tanpa Serial / Lot"),
    ("SERIAL", "Serial Number (per unit)"),
    ("LOT",    "Lot / Batch"),
]
_TRACKING_COLOR = {"NONE": Colors.TEXT_MUTED, "SERIAL": Colors.ACCENT, "LOT": Colors.INFO}
_TRACKING_LABEL = {"NONE": "No Serial", "SERIAL": "Serial", "LOT": "Lot/Batch"}


def _tracking_badge(t: str) -> ft.Container:
    color = _TRACKING_COLOR.get(t, Colors.TEXT_MUTED)
    return ft.Container(
        content=ft.Text(_TRACKING_LABEL.get(t, t), size=11, color=color,
                        weight=ft.FontWeight.W_500),
        bgcolor=ft.Colors.with_opacity(0.1, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


# ═══════════════════════════════════════════════════════════════
# KATEGORI PRODUK
# ═══════════════════════════════════════════════════════════════
def _cat_form_dialog(page, session: AppSession,
                     cat: Optional[ProductCategory], on_saved):
    is_edit = cat is not None

    with SessionLocal() as db:
        all_cats = ProductCategoryService.get_all(db, session.company_id)

    # Parent hanya kategori root (parent_id=None) agar max 2 level
    parent_opts = [("", "— Tidak Ada (Kategori Utama) —")] + [
        (str(c.id), c.name)
        for c in all_cats
        if c.parent_id is None and (not is_edit or c.id != cat.id)
    ]

    f_code   = make_field("Kode *",
                          cat.code if is_edit else "",
                          hint="Contoh: ELK", read_only=is_edit, width=140)
    f_name   = make_field("Nama Kategori *",
                          cat.name if is_edit else "")
    f_desc   = make_field("Deskripsi",
                          cat.description or "" if is_edit else "",
                          multiline=True, min_lines=2, max_lines=3)
    f_parent = make_dropdown("Induk Kategori", parent_opts,
                             str(cat.parent_id) if (is_edit and cat.parent_id) else "")
    f_active = ft.Switch(
        label="Aktif",
        value=cat.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_name.value.strip():
            show_err("Nama kategori wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode kategori wajib diisi."); return

        data = {
            "code":        f_code.value,
            "name":        f_name.value,
            "description": f_desc.value,
            "parent_id":   f_parent.value or None,
            "is_active":   f_active.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = ProductCategoryService.update(db, cat.id, data)
            else:
                ok, msg, _ = ProductCategoryService.create(db, session.company_id, data)

        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.FOLDER, color=Colors.ACCENT, size=20),
                    ft.Text("Edit Kategori" if is_edit else "Tambah Kategori",
                            color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(
            width=420,
            content=ft.Column(
                spacing=12, tight=True,
                controls=[err, ft.ResponsiveRow(spacing=12, controls=[
                    ft.Container(col={"xs": 12, "sm": 4}, content=f_code),
                    ft.Container(col={"xs": 12, "sm": 8}, content=f_name),
                ]), f_parent, f_desc, f_active],
            ),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                          on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                                     elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


def _build_cat_rows(cats, page, session, refresh):
    rows = []
    for c in cats:
        is_parent = c.parent_id is None
        rows.append(ft.DataRow(
            color=ft.Colors.with_opacity(0.02, Colors.TEXT_PRIMARY) if is_parent else None,
            cells=[
                ft.DataCell(ft.Container(
                    padding=ft.Padding.only(left=0 if is_parent else 20),
                    content=ft.Row(spacing=8, controls=[
                        ft.Icon(ft.Icons.FOLDER if is_parent else ft.Icons.FOLDER_OPEN,
                                size=16,
                                color=Colors.ACCENT if is_parent else Colors.TEXT_MUTED),
                        ft.Text(c.name, size=13,
                                weight=ft.FontWeight.W_600 if is_parent else ft.FontWeight.W_400,
                                color=Colors.TEXT_PRIMARY),
                    ]),
                )),
                ft.DataCell(ft.Text(c.code, size=12,
                                    color=Colors.TEXT_SECONDARY,
                                    font_family="monospace")),
                ft.DataCell(ft.Text(c.description or "—", size=12,
                                    color=Colors.TEXT_MUTED)),
                ft.DataCell(status_badge(c.is_active)),
                ft.DataCell(ft.Row(spacing=0, controls=[
                    action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                               lambda e, ct=c: _cat_form_dialog(page, session, ct, refresh),
                               Colors.INFO),
                    action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                               lambda e, cid=c.id, nm=c.name: confirm_dialog(
                                   page, "Hapus Kategori", f"Hapus kategori '{nm}'?",
                                   lambda: _del_cat(cid, page, refresh)),
                               Colors.ERROR),
                ])),
            ],
        ))
    return rows


def _del_cat(cid, page, refresh):
    with SessionLocal() as db:
        ok, msg = ProductCategoryService.delete(db, cid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _build_cat_tab(page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}

    with SessionLocal() as db:
        all_cats = ProductCategoryService.get_all(db, session.company_id)
        # Urutkan: parent dulu, kemudian children-nya
        roots    = [c for c in all_cats if c.parent_id is None]
        child_of = {}
        for c in all_cats:
            if c.parent_id:
                child_of.setdefault(c.parent_id, []).append(c)
        ordered = []
        for r in sorted(roots, key=lambda x: x.name):
            ordered.append(r)
            ordered.extend(sorted(child_of.get(r.id, []), key=lambda x: x.name))

    CAT_COLS = [
        ft.DataColumn(ft.Text("Nama", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kode", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Deskripsi", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    cat_table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44,
        data_row_min_height=48,
        column_spacing=16,
        columns=CAT_COLS,
        rows=_build_cat_rows(ordered, page, session, lambda: None),
    )
    cat_area = ft.Column(controls=[cat_table], scroll=ft.ScrollMode.AUTO)

    def refresh_cats():
        with SessionLocal() as db:
            cats = ProductCategoryService.get_all(db, session.company_id)
        roots_r = [c for c in cats if c.parent_id is None]
        child_r = {}
        for c in cats:
            if c.parent_id:
                child_r.setdefault(c.parent_id, []).append(c)
        ordered_r = []
        for r in sorted(roots_r, key=lambda x: x.name):
            ordered_r.append(r)
            ordered_r.extend(sorted(child_r.get(r.id, []), key=lambda x: x.name))
        cat_table.rows = _build_cat_rows(ordered_r, page, session, refresh_cats)
        cat_area.controls = [cat_table if ordered_r else empty_state("Belum ada kategori.")]
        try: cat_area.update()
        except: pass

    def on_search_cat(e):
        search_val["q"] = e.control.value or ""
        with SessionLocal() as db:
            cats = ProductCategoryService.get_all(db, session.company_id, search_val["q"])
        cat_table.rows = _build_cat_rows(cats, page, session, refresh_cats)
        cat_area.controls = [cat_table if cats else empty_state()]
        try: cat_area.update()
        except: pass

    # Patch initial dengan refresh yang benar
    cat_table.rows = _build_cat_rows(ordered, page, session, refresh_cats)

    return ft.Column(
        expand=True,
        spacing=12,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    search_bar("Cari nama atau kode kategori...", on_search_cat, width=280),
                    ft.Button(
                        content=ft.Row(tight=True, spacing=6, controls=[
                            ft.Icon(ft.Icons.CREATE_NEW_FOLDER, size=16,
                                    color=Colors.TEXT_ON_ACCENT),
                            ft.Text("Tambah Kategori", size=13,
                                    color=Colors.TEXT_ON_ACCENT,
                                    weight=ft.FontWeight.W_600),
                        ]),
                        bgcolor=Colors.ACCENT,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                            elevation=0,
                        ),
                        on_click=lambda e: _cat_form_dialog(page, session, None, refresh_cats),
                    ),
                ],
            ),
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[cat_area]),
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════
# PRODUK
# ═══════════════════════════════════════════════════════════════
def _prod_form_dialog(page, session: AppSession,
                      product: Optional[Product], on_saved):
    is_edit = product is not None
    p = product

    with SessionLocal() as db:
        categories = ProductCategoryService.get_all(db, session.company_id)
        uoms       = db.query(UnitOfMeasure).filter_by(is_active=True).all()

    cat_opts = [("", "— Tanpa Kategori —")] + [
        (str(c.id), f"{'  └ ' if c.parent_id else ''}{c.name}")
        for c in categories
    ]
    uom_opts  = [(str(u.id), f"{u.code} — {u.name}") for u in uoms]
    uom_opts2 = [("", "— Sama dg satuan dasar —")] + uom_opts

    f_code    = make_field("Kode *", p.code if is_edit else "",
                           hint="Contoh: PRD-001", read_only=is_edit, width=160)
    f_barcode = make_field("Barcode", p.barcode or "" if is_edit else "", width=180)
    f_name    = make_field("Nama Produk *", p.name if is_edit else "")
    f_desc    = make_field("Deskripsi", p.description or "" if is_edit else "",
                           multiline=True, min_lines=2, max_lines=3)
    _init_is_service = (p.product_type if is_edit else "GOODS") == "SERVICE"

    f_type    = make_dropdown("Tipe", _PROD_TYPE_OPTS,
                              p.product_type if is_edit else "GOODS", width=160)
    f_track   = make_dropdown("Tracking Serial", _TRACKING_OPTS,
                              p.tracking_type if is_edit else "NONE",
                              disabled=_init_is_service)
    f_cat     = make_dropdown("Kategori", cat_opts,
                              str(p.category_id) if (is_edit and p.category_id) else "")
    f_uom     = make_dropdown("Satuan Dasar *", uom_opts,
                              str(p.uom_id) if is_edit else "")
    f_puom    = make_dropdown("Satuan Beli", uom_opts2,
                              str(p.purchase_uom_id) if (is_edit and p.purchase_uom_id) else "")
    f_suom    = make_dropdown("Satuan Jual", uom_opts2,
                              str(p.sales_uom_id) if (is_edit and p.sales_uom_id) else "")
    f_cost    = make_field("HPP / Harga Beli",
                           str(int(p.standard_cost)) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=180)
    f_price   = make_field("Harga Jual",
                           str(int(p.sale_price)) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=180)
    f_minprc  = make_field("Harga Min",
                           str(int(p.min_sale_price)) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=180)
    f_minst   = make_field("Stok Min",
                           str(p.min_stock) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=120)
    f_maxst   = make_field("Stok Max",
                           str(p.max_stock) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=120)
    f_reorder = make_field("Reorder Point",
                           str(p.reorder_point) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=140)
    f_lead    = make_field("Lead Time (hari)",
                           str(p.lead_time_days) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=140)

    cb_buy    = ft.Checkbox(label="Bisa Dibeli",
                            value=p.is_purchasable if is_edit else True,
                            active_color=Colors.ACCENT)
    cb_sell   = ft.Checkbox(label="Bisa Dijual",
                            value=p.is_sellable if is_edit else True,
                            active_color=Colors.ACCENT)
    cb_stock  = ft.Checkbox(label="Pantau Stok",
                            value=p.is_stockable if is_edit else True,
                            disabled=_init_is_service,
                            active_color=Colors.ACCENT)
    sw_active = ft.Switch(label="Aktif",
                          value=p.is_active if is_edit else True,
                          active_color=Colors.ACCENT)

    # Section stok — visible=False langsung di konstruktor jika SERVICE
    is_service_init = (f_type.value == "SERVICE")
    stock_card = section_card("Stok & Pengadaan", [
        ft.ResponsiveRow(spacing=12, controls=[
            ft.Container(col={"xs":12,"sm":3}, content=f_minst),
            ft.Container(col={"xs":12,"sm":3}, content=f_maxst),
            ft.Container(col={"xs":12,"sm":3}, content=f_reorder),
            ft.Container(col={"xs":12,"sm":3}, content=f_lead),
        ]),
    ], visible=not is_service_init)

    def _on_type_change(e):
        is_service = f_type.value == "SERVICE"
        if is_service:
            cb_stock.value  = False
            f_track.value   = "NONE"
            f_minst.value   = "0"
            f_maxst.value   = "0"
            f_reorder.value = "0"
        cb_stock.disabled  = is_service
        f_track.disabled   = is_service
        stock_card.visible = not is_service
        try:
            cb_stock.update()
            f_track.update()
            stock_card.update()
        except Exception:
            pass

    f_type.on_select = _on_type_change

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_name.value.strip():
            show_err("Nama produk wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode produk wajib diisi."); return
        if not f_uom.value:
            show_err("Satuan dasar wajib dipilih."); return

        data = {
            "code":           f_code.value,
            "name":           f_name.value,
            "barcode":        f_barcode.value,
            "description":    f_desc.value,
            "product_type":   f_type.value,
            "tracking_type":  f_track.value,
            "category_id":    f_cat.value or None,
            "uom_id":         f_uom.value,
            "purchase_uom_id":f_puom.value or None,
            "sales_uom_id":   f_suom.value or None,
            "standard_cost":  f_cost.value or "0",
            "sale_price":     f_price.value or "0",
            "min_sale_price": f_minprc.value or "0",
            "min_stock":      f_minst.value or "0",
            "max_stock":      f_maxst.value or "0",
            "reorder_point":  f_reorder.value or "0",
            "lead_time_days": f_lead.value or "0",
            "is_purchasable": cb_buy.value,
            "is_sellable":    cb_sell.value,
            "is_stockable":   cb_stock.value,
            "is_active":      sw_active.value,
        }

        with SessionLocal() as db:
            if is_edit:
                ok, msg = ProductService.update(db, p.id, data)
            else:
                ok, msg, _ = ProductService.create(db, session.company_id, data)

        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.INVENTORY_2, color=Colors.ACCENT, size=20),
                    ft.Text("Edit Produk" if is_edit else "Tambah Produk",
                            color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(width=580, height=560, content=ft.Column(
            scroll=ft.ScrollMode.AUTO, spacing=14,
            controls=[
                err,
                section_card("Informasi Produk", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":4}, content=f_code),
                        ft.Container(col={"xs":12,"sm":4}, content=f_barcode),
                        ft.Container(col={"xs":12,"sm":4}, content=f_type),
                    ]),
                    f_name,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_cat),
                        ft.Container(col={"xs":12,"sm":6}, content=f_track),
                    ]),
                    f_desc,
                    ft.Row(spacing=20, controls=[cb_buy, cb_sell, cb_stock, sw_active]),
                ]),
                section_card("Satuan", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":4}, content=f_uom),
                        ft.Container(col={"xs":12,"sm":4}, content=f_puom),
                        ft.Container(col={"xs":12,"sm":4}, content=f_suom),
                    ]),
                ]),
                section_card("Harga", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":4}, content=f_cost),
                        ft.Container(col={"xs":12,"sm":4}, content=f_price),
                        ft.Container(col={"xs":12,"sm":4}, content=f_minprc),
                    ]),
                ]),
                stock_card,
            ],
        )),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                          on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                                     elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


def _build_prod_rows(products, page, session, refresh):
    rows = []
    for p in products:
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(p.name, size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(p.code, size=11, color=Colors.TEXT_MUTED,
                        font_family="monospace"),
            ])),
            ft.DataCell(ft.Text(
                p.category.name if p.category else "—",
                size=12, color=Colors.TEXT_SECONDARY,
            )),
            ft.DataCell(ft.Text(
                p.uom.code if p.uom else "—",
                size=12, color=Colors.TEXT_SECONDARY,
            )),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(f"Rp {p.sale_price:,.0f}", size=12,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(f"HPP: Rp {p.standard_cost:,.0f}", size=11,
                        color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(_tracking_badge(p.tracking_type)),
            ft.DataCell(status_badge(p.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                           lambda e, pr=p: _prod_form_dialog(page, session, pr, refresh),
                           Colors.INFO),
                action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                           lambda e, pid=p.id, nm=p.name: confirm_dialog(
                               page, "Hapus Produk", f"Hapus produk '{nm}'?",
                               lambda: _del_prod(pid, page, refresh)),
                           Colors.ERROR),
            ])),
        ]))
    return rows


def _del_prod(pid, page, refresh):
    with SessionLocal() as db:
        ok, msg = ProductService.delete(db, pid)
    show_snack(page, msg, ok)
    if ok: refresh()


def _build_prod_tab(page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}

    with SessionLocal() as db:
        initial = ProductService.get_all(db, session.company_id)

    PROD_COLS = [
        ft.DataColumn(ft.Text("Nama / Kode", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kategori",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Satuan",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Harga",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tracking",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    prod_table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44,
        data_row_min_height=56,
        column_spacing=16,
        columns=PROD_COLS,
        rows=_build_prod_rows(initial, page, session, lambda: None),
    )
    prod_area = ft.Column(controls=[prod_table if initial else empty_state()],
                          scroll=ft.ScrollMode.AUTO)

    def refresh_prods():
        with SessionLocal() as db:
            data = ProductService.get_all(db, session.company_id, search_val["q"])
        prod_table.rows = _build_prod_rows(data, page, session, refresh_prods)
        prod_area.controls = [prod_table if data else empty_state()]
        try: prod_area.update()
        except: pass

    def on_search_prod(e):
        search_val["q"] = e.control.value or ""
        refresh_prods()

    # Patch
    prod_table.rows = _build_prod_rows(initial, page, session, refresh_prods)

    return ft.Column(
        expand=True,
        spacing=12,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    search_bar("Cari nama, kode, barcode...", on_search_prod, width=300),
                    ft.Button(
                        content=ft.Row(tight=True, spacing=6, controls=[
                            ft.Icon(ft.Icons.ADD_BOX, size=16, color=Colors.TEXT_ON_ACCENT),
                            ft.Text("Tambah Produk", size=13,
                                    color=Colors.TEXT_ON_ACCENT,
                                    weight=ft.FontWeight.W_600),
                        ]),
                        bgcolor=Colors.ACCENT,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                            elevation=0,
                        ),
                        on_click=lambda e: _prod_form_dialog(page, session, None, refresh_prods),
                    ),
                ],
            ),
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[prod_area]),
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════
# MAIN PAGE — dua tab: Produk | Kategori
# ═══════════════════════════════════════════════════════════════
def ProductsPage(page, session: AppSession, tab: int = 0) -> ft.Control:
    # Buat konten kedua tab
    tab_produk   = _build_prod_tab(page, session)
    tab_kategori = _build_cat_tab(page, session)

    # State tab aktif
    active = {"tab": tab}

    # Konten area — hanya satu yang visible
    content_produk   = ft.Container(expand=True, visible=(tab == 0), content=tab_produk)
    content_kategori = ft.Container(expand=True, visible=(tab == 1), content=tab_kategori)

    # Tab button helpers
    def _tab_btn(label, index):
        is_active = active["tab"] == index
        return ft.Container(
            height=40,
            padding=ft.Padding.symmetric(horizontal=20),
            border=ft.Border.only(
                bottom=ft.BorderSide(2, Colors.ACCENT if is_active else ft.Colors.TRANSPARENT)
            ),
            on_click=lambda e, i=index: _switch(i),
            ink=True,
            content=ft.Text(
                label,
                size=13,
                weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
                color=Colors.TEXT_PRIMARY if is_active else Colors.TEXT_SECONDARY,
            ),
        )

    btn_produk   = _tab_btn("Produk", 0)
    btn_kategori = _tab_btn("Kategori", 1)

    tab_bar = ft.Container(
        border=ft.Border.only(bottom=ft.BorderSide(1, Colors.BORDER)),
        content=ft.Row(spacing=0, controls=[btn_produk, btn_kategori]),
    )

    tab_bar_row = ft.Column(controls=[tab_bar], spacing=0)

    def _switch(index: int):
        active["tab"] = index
        # Update visibility konten
        content_produk.visible   = (index == 0)
        content_kategori.visible = (index == 1)
        # Rebuild tombol tab
        tab_bar.content = ft.Row(spacing=0, controls=[
            _tab_btn("Produk", 0),
            _tab_btn("Kategori", 1),
        ])
        try:
            content_produk.update()
            content_kategori.update()
            tab_bar.update()
        except Exception:
            pass

    return ft.Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                # Header
                ft.Container(
                    padding=ft.Padding.only(bottom=12),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(spacing=2, tight=True, controls=[
                                ft.Text("Produk & Kategori",
                                        size=20, weight=ft.FontWeight.W_700,
                                        color=Colors.TEXT_PRIMARY),
                                ft.Text("Kelola data produk, barang, dan kategorinya",
                                        size=13, color=Colors.TEXT_MUTED),
                            ]),
                        ],
                    ),
                ),
                # Custom tab bar
                tab_bar,
                ft.Container(height=16),
                # Konten tab
                content_produk,
                content_kategori,
            ],
        ),
    )
