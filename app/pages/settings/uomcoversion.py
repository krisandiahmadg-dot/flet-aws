"""
app/pages/master/branches.py
Master Data → Cabang
"""
from __future__ import annotations
import flet as ft
from typing import Optional

from app.database import SessionLocal
from app.models import UOMConversion, UnitOfMeasure
from app.services.master_service import UOMConversionService, UOMService
from app.services.auth import AppSession
from app.pages.master._base import MasterPage
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack,
)
from app.utils.theme import Colors, Sizes



# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 uomConversion: Optional[UOMConversion], on_saved):
    is_edit = uomConversion is not None
    b = uomConversion

    with SessionLocal() as db:
        all_uom = UOMService.get_all(db, session.company_id)
    
    # Parent hanya kategori root (parent_id=None) agar max 2 level
    parent_opts = [("", "— Pilih Satuan —")] + [
        (str(c.id), c.name)
        for c in all_uom
    ]


    f_from     = make_dropdown("Satuan Asal *", parent_opts,
                               b.from_uom_id if is_edit else None,
                               width=210)
    f_factor     = make_field("Berisi *",
                            f"{b.factor:.2f}" if is_edit else "",
                            hint="Isi Dalam Satuan Terkecil",
                            width=150)
    f_to     = make_dropdown("Satuan Tujuan *", parent_opts,
                               b.to_uom_id if is_edit else None,
                               width=210)
    f_active   = ft.Switch(
        label="UOM Conversion Aktif",
        value=b.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_from.value:
            show_err("SATUAN ASAL wajib diisi."); return
        if not f_factor.value.strip():
            show_err("BERISI wajib diisi."); return
        if not f_to.value:
            show_err("SATUAN TUJUAN wajib diisi."); return

        data = {
            "from_uom_id":        f_from.value,
            "to_uom_id":        f_to.value,
            "factor":    f_factor.value,
            "is_active":   f_active.value,
        }

        with SessionLocal() as db:
            if is_edit:
                ok, msg = UOMConversionService.update(db, b.id, data)
            else:
                ok, msg, _ = UOMConversionService.create(db, data)

        dlg.open = False
        page.update()
        show_snack(page, msg, ok)
        if ok:
            on_saved()

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.STORE, color=Colors.ACCENT, size=20),
                    ft.Text(
                        "Edit UOM Conversion" if is_edit else "Tambah UOM Conversion",
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
            width=520,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                controls=[
                    err,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 4}, content=f_from),
                        ft.Container(col={"xs": 12, "sm": 8}, content=f_factor),
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_to),
                    ]),
                    f_active,
                ],
            ),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button(
                "Batal",
                style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                on_click=lambda e: (setattr(dlg, "open", False), page.update()),
            ),
            ft.Button(
                "Simpan",
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
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# TABLE ROWS
# ─────────────────────────────────────────────────────────────
def _build_rows(uomsConversions, page, session, refresh):
    rows = []
    for u in uomsConversions:
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(u.from_uom.name, size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
            ])),
            ft.DataCell(ft.Text(f"{u.factor:.2f}", size=12,
                                color=Colors.TEXT_SECONDARY,
                                font_family="monospace")),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(u.to_uom.name, size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
            ])),
            ft.DataCell(status_badge(u.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(
                    ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, br=u: _form_dialog(page, session, br, refresh),
                    Colors.INFO,
                ),
                action_btn(
                    ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, bid=u.id, nm=u.to_uom.name: confirm_dialog(
                        page, "Hapus UOM Conversion",
                        f"Hapus UOM Conversion '{nm}'?",
                        lambda: _delete(bid, page, refresh),
                    ),
                    Colors.ERROR,
                ),
            ])),
        ]))
    return rows


def _delete(bid, page, refresh):
    with SessionLocal() as db:
        ok, msg = UOMConversionService.delete(db, bid)
    show_snack(page, msg, ok)
    if ok:
        refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def UOMConversionsPage(page, session: AppSession):
    search_val = {"q": ""}


    with SessionLocal() as db:
        initial = UOMConversionService.get_all(db)

    COLS = [
        ft.DataColumn(ft.Text("Satuan",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Factor",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Satuan Tujuan",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Unit Of Measure (UOM)",
        subtitle="Kelola data unit of measure",
        add_label="Tambah UOM Conversion",
        search_hint="Cari nama atau kode UOM...",
        columns=COLS,
        initial_rows=_build_rows(initial, page, session, lambda: None),
        on_add=lambda: _form_dialog(page, session, None, refresh),
        on_search=lambda e: (
            search_val.update({"q": e.control.value or ""}), refresh()
        ),
        add_icon=ft.Icons.ADD_HOME_WORK,
    )

    def refresh():
        with SessionLocal() as db:
            data = UOMConversionService.get_all(db)
        set_rows(_build_rows(data, page, session, refresh))

    set_rows(_build_rows(initial, page, session, refresh))
    return ctrl
