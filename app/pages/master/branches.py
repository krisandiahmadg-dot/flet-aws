"""
app/pages/master/branches.py
Master Data → Cabang
"""
from __future__ import annotations
import flet as ft
from typing import Optional

from app.database import SessionLocal
from app.models import Branch, Company
from app.services.master_service import BranchService
from app.services.auth import AppSession
from app.pages.master._base import MasterPage
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack,
)
from app.utils.theme import Colors, Sizes

_TYPE_OPTS = [
    ("HQ",        "HQ - Kantor Pusat"),
    ("BRANCH",    "Branch - Cabang"),
    ("STORE",     "Store - Toko"),
]
_TYPE_COLOR = {
    "HQ":        Colors.ACCENT,
    "BRANCH":    Colors.INFO,
    "STORE":     Colors.SUCCESS,
}
_TYPE_LABEL = {
    "HQ": "Kantor Pusat", "BRANCH": "Cabang","STORE": "Toko",
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
                 branch: Optional[Branch], on_saved):
    is_edit = branch is not None
    b = branch

    with SessionLocal() as db:
        companies = db.query(Company).filter_by(is_active=True).order_by(Company.name).all()

    co_opts = [(str(c.id), c.name) for c in companies]

    f_company  = make_dropdown(
        "Perusahaan *", co_opts,
        str(b.company_id) if is_edit else str(session.company_id),
    )
    f_code     = make_field("Kode *",
                            b.code if is_edit else "",
                            hint="Contoh: CBG-JKT",
                            read_only=is_edit, width=150)
    f_name     = make_field("Nama Cabang *",
                            b.name if is_edit else "")
    f_type     = make_dropdown("Tipe *", _TYPE_OPTS,
                               b.branch_type if is_edit else "BRANCH",
                               width=210)
    f_phone    = make_field("Telepon",
                            b.phone or "" if is_edit else "",
                            width=200)
    f_email    = make_field("Email",
                            b.email or "" if is_edit else "",
                            keyboard_type=ft.KeyboardType.EMAIL)
    f_city     = make_field("Kota",
                            b.city or "" if is_edit else "",
                            width=200)
    f_address  = make_field("Alamat",
                            b.address or "" if is_edit else "",
                            multiline=True, min_lines=2, max_lines=3)
    f_active   = ft.Switch(
        label="Cabang Aktif",
        value=b.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_company.value:
            show_err("Perusahaan wajib dipilih."); return
        if not f_name.value.strip():
            show_err("Nama cabang wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode cabang wajib diisi."); return

        data = {
            "code":        f_code.value,
            "name":        f_name.value,
            "branch_type": f_type.value,
            "phone":       f_phone.value,
            "email":       f_email.value,
            "city":        f_city.value,
            "address":     f_address.value,
            "is_active":   f_active.value,
        }
        company_id = int(f_company.value)

        with SessionLocal() as db:
            if is_edit:
                ok, msg = BranchService.update(db, b.id, data)
            else:
                ok, msg, _ = BranchService.create(db, company_id, data)

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
                        "Edit Cabang" if is_edit else "Tambah Cabang",
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
                    f_company,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 4}, content=f_code),
                        ft.Container(col={"xs": 12, "sm": 8}, content=f_name),
                    ]),
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_type),
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_city),
                    ]),
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_phone),
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_email),
                    ]),
                    f_address,
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
def _build_rows(branches, page, session, refresh):
    rows = []
    for b in branches:
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(b.name, size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(b.city or "—", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(b.code, size=12,
                                color=Colors.TEXT_SECONDARY,
                                font_family="monospace")),
            ft.DataCell(_type_badge(b.branch_type)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(b.phone or "—", size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(b.email or "—", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(status_badge(b.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(
                    ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, br=b: _form_dialog(page, session, br, refresh),
                    Colors.INFO,
                ),
                action_btn(
                    ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, bid=b.id, nm=b.name: confirm_dialog(
                        page, "Hapus Cabang",
                        f"Hapus cabang '{nm}'?",
                        lambda: _delete(bid, page, refresh),
                    ),
                    Colors.ERROR,
                ),
            ])),
        ]))
    return rows


def _delete(bid, page, refresh):
    with SessionLocal() as db:
        ok, msg = BranchService.delete(db, bid)
    show_snack(page, msg, ok)
    if ok:
        refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def BranchesPage(page, session: AppSession):
    search_val = {"q": ""}

    with SessionLocal() as db:
        initial = BranchService.get_all(db, session.company_id, "")

    COLS = [
        ft.DataColumn(ft.Text("Nama / Kota",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kode",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kontak",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Cabang",
        subtitle="Kelola data cabang, gudang, dan toko",
        add_label="Tambah Cabang",
        search_hint="Cari nama atau kode cabang...",
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
            data = BranchService.get_all(db, session.company_id, search_val["q"])
        set_rows(_build_rows(data, page, session, refresh))

    set_rows(_build_rows(initial, page, session, refresh))
    return ctrl
