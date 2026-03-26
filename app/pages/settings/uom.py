"""
app/pages/master/branches.py
Master Data → Cabang
"""
from __future__ import annotations
import flet as ft
from typing import Optional

from app.database import SessionLocal
from app.models import UnitOfMeasure
from app.services.master_service import UOMService
from app.services.auth import AppSession
from app.pages.master._base import MasterPage
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack,
)
from app.utils.theme import Colors, Sizes

_TYPE_OPTS = [
    ("LENGTH",    "LENGTH - Panjang"),
    ("WEIGHT",    "WEIGHT - Berat"),
    ("VOLUME",    "VOLUME - Volume"),
    ("UNIT",      "UNIT - Satuan"),
    ("TIME",      "TIME - Waktu"),
    ("OTHER",     "OTHER - Lainnya"),
]

_TYPE_COLOR = {
    "LENGTH":    Colors.TEXT_HEAD_TITLE,
    "WEIGHT":    Colors.SUCCESS,
    "VOLUME":    Colors.ICON_MENU,
    "UNIT":      Colors.ACCENT,
    "TIME":      Colors.INFO,
    "OTHER":     Colors.WARNING,
}
_TYPE_LABEL = {
    "LENGTH": "Panjang", "WEIGHT": "Berat", "VOLUME": "Volume",
    "UNIT": "Satuan", "TIME": "Waktu", "OTHER": "Lainnya",
}


def _type_badge(branch_type: str) -> ft.Container:
    color = _TYPE_COLOR.get(branch_type, Colors.TEXT_MUTED)
    label = _TYPE_LABEL.get(branch_type, branch_type)
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 uom: Optional[UnitOfMeasure], on_saved):
    is_edit = uom is not None
    b = uom

    f_code     = make_field("Kode *",
                            b.code if is_edit else "",
                            hint="Contoh: UOM-LTH",
                            read_only=is_edit, width=150)
    f_name     = make_field("Nama UOM *",
                            b.name if is_edit else "")
    f_type     = make_dropdown("Tipe *", _TYPE_OPTS,
                               b.uom_type if is_edit else "UNIT",
                               width=210)
    f_active   = ft.Switch(
        label="UOM Aktif",
        value=b.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_name.value.strip():
            show_err("NAMA UOM wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode UOM wajib diisi."); return

        data = {
            "company_id": session.company_id,
            "code":        f_code.value,
            "name":        f_name.value,
            "uom_type":    f_type.value,
            "is_active":   f_active.value,
        }

        with SessionLocal() as db:
            if is_edit:
                ok, msg = UOMService.update(db, b.id, data)
            else:
                ok, msg, _ = UOMService.create(db, data)

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
                        "Edit UOM" if is_edit else "Tambah UOM",
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
                        ft.Container(col={"xs": 12, "sm": 4}, content=f_code),
                        ft.Container(col={"xs": 12, "sm": 8}, content=f_name),
                    ]),
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_type),
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
def _build_rows(uoms, page, session, refresh):
    rows = []
    for u in uoms:
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(u.name, size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
            ])),
            ft.DataCell(ft.Text(u.code, size=12,
                                color=Colors.TEXT_SECONDARY,
                                font_family="monospace")),
            ft.DataCell(_type_badge(u.uom_type)),
            ft.DataCell(status_badge(u.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(
                    ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, br=u: _form_dialog(page, session, br, refresh),
                    Colors.INFO,
                ),
                action_btn(
                    ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, bid=u.id, nm=u.name: confirm_dialog(
                        page, "Hapus UOM",
                        f"Hapus UOM '{nm}'?",
                        lambda: _delete(bid, page, refresh),
                    ),
                    Colors.ERROR,
                ),
            ])),
        ]))
    return rows


def _delete(bid, page, refresh):
    with SessionLocal() as db:
        ok, msg = UOMService.delete(db, bid)
    show_snack(page, msg, ok)
    if ok:
        refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def UOMsPage(page, session: AppSession):
    search_val = {"q": ""}

    with SessionLocal() as db:
        initial = UOMService.get_all(db,  session.company_id,"")

    COLS = [
        ft.DataColumn(ft.Text("Satuan",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kode",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Unit Of Measure (UOM)",
        subtitle="Kelola data unit of measure",
        add_label="Tambah UOM",
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
            data = UOMService.get_all(db, session.company_id, search_val["q"])
        set_rows(_build_rows(data, page, session, refresh))

    set_rows(_build_rows(initial, page, session, refresh))
    return ctrl
