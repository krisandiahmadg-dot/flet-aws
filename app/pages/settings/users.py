"""
app/pages/settings/users.py
Halaman Pengaturan → Pengguna (User CRUD)
"""

from __future__ import annotations
import flet as ft
from typing import Optional, List

from app.database import SessionLocal
from app.models import User, Role, Branch
from app.services.settings_service import UserService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, page_header, search_bar,
    status_badge, role_badge, action_btn, confirm_dialog,
    show_snack, empty_state, loading_spinner, section_card,
)
from app.utils.theme import Colors, Sizes


# ─────────────────────────────────────────────────────────────
# USER FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _user_form_dialog(
    page: ft.Page,
    session: AppSession,
    user: Optional[User],
    on_saved: callable,
):
    is_edit = user is not None
    title   = "Edit Pengguna" if is_edit else "Tambah Pengguna"

    # Load data reference
    with SessionLocal() as db:
        all_roles    = db.query(Role).filter_by(company_id=session.company_id, is_active=True).all()
        all_branches = db.query(Branch).filter_by(company_id=session.company_id, is_active=True).all()
        current_role_ids = (
            [str(ur.role_id) for ur in user.user_roles] if is_edit and user.user_roles else []
        )
        current_branch_id = (
            str(user.user_roles[0].branch_id) if is_edit and user.user_roles and user.user_roles[0].branch_id else ""
        )

    # Form fields
    f_fullname  = make_field("Nama Lengkap *", user.full_name if is_edit else "")
    f_username  = make_field("Username *", user.username if is_edit else "")
    f_email     = make_field("Email *", user.email if is_edit else "",
                              keyboard_type=ft.KeyboardType.EMAIL)
    f_phone     = make_field("Telepon", user.phone or "" if is_edit else "")
    f_password  = make_field(
        "Password" + (" (kosongkan jika tidak diubah)" if is_edit else " *"),
        password=True,
    )
    f_active    = ft.Switch(
        label="Akun Aktif",
        value=user.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )

    # Role checkboxes
    role_checks: dict[int, ft.Checkbox] = {}
    role_rows = []
    for r in all_roles:
        cb = ft.Checkbox(
            label=r.name,
            value=str(r.id) in current_role_ids,
            active_color=Colors.ACCENT,
            check_color=Colors.TEXT_ON_ACCENT,
        )
        role_checks[r.id] = cb
        role_rows.append(cb)

    # Branch dropdown
    branch_opts = [("", "— Semua Cabang —")] + [(str(b.id), b.name) for b in all_branches]
    f_branch = make_dropdown("Cabang", branch_opts, current_branch_id)

    error_text = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def validate() -> bool:
        errs = []
        if not f_fullname.value.strip():   errs.append("Nama lengkap wajib diisi.")
        if not f_username.value.strip():   errs.append("Username wajib diisi.")
        if not f_email.value.strip():      errs.append("Email wajib diisi.")
        if not is_edit and not f_password.value: errs.append("Password wajib diisi.")
        if errs:
            error_text.value   = errs[0]
            error_text.visible = True
            error_text.update()
            return False
        error_text.visible = False
        error_text.update()
        return True

    def handle_save(e):
        if not validate():
            return
        data = {
            "full_name": f_fullname.value,
            "username":  f_username.value,
            "email":     f_email.value,
            "phone":     f_phone.value,
            "password":  f_password.value,
            "is_active": f_active.value,
            "role_ids":  [str(rid) for rid, cb in role_checks.items() if cb.value],
            "branch_id": f_branch.value or None,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = UserService.update(db, user.id, data)
            else:
                ok, msg, _ = UserService.create(db, session.company_id, data)

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
                ft.Text(title, color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700, size=16),
                ft.IconButton(
                    icon=ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                    on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                ),
            ],
        ),
        content=ft.Container(
            width=480,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=16,
                controls=[
                    error_text,
                    section_card("Informasi Akun", [
                        ft.ResponsiveRow(controls=[
                            ft.Container(col=12, content=f_fullname),
                            ft.Container(col={"xs":12,"sm":6}, content=f_username),
                            ft.Container(col={"xs":12,"sm":6}, content=f_email),
                            ft.Container(col={"xs":12,"sm":6}, content=f_phone),
                            ft.Container(col={"xs":12,"sm":6}, content=f_password),
                        ], spacing=12, run_spacing=12),
                        f_active,
                    ]),
                    section_card("Role & Akses", [
                        ft.Text("Pilih role yang diberikan:", size=12, color=Colors.TEXT_MUTED),
                        ft.Column(spacing=4, controls=role_rows),
                        ft.Divider(height=1, color=Colors.BORDER),
                        f_branch,
                    ]),
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
                bgcolor=Colors.ACCENT,
                color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0,
                ),
                on_click=handle_save,
            ),
        ],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# USER LIST TABLE
# ─────────────────────────────────────────────────────────────
def _build_table(users: List[User], page: ft.Page, session: AppSession, on_refresh: callable) -> ft.Control:
    if not users:
        return empty_state("Tidak ada pengguna ditemukan.")

    rows = []
    for u in users:
        role_names = [ur.role.name for ur in (u.user_roles or []) if ur.role]
        rows.append(
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Column(
                        spacing=2, tight=True,
                        controls=[
                            ft.Text(u.full_name, size=13, weight=ft.FontWeight.W_600,
                                    color=Colors.TEXT_PRIMARY),
                            ft.Text(u.email, size=11, color=Colors.TEXT_MUTED),
                        ],
                    )),
                    ft.DataCell(ft.Text(u.username, size=13, color=Colors.TEXT_SECONDARY,
                                        font_family="monospace")),
                    ft.DataCell(
                        ft.Row(
                            spacing=4,
                            wrap=True,
                            controls=[role_badge(n) for n in role_names] or
                                     [ft.Text("—", size=12, color=Colors.TEXT_MUTED)],
                        )
                    ),
                    ft.DataCell(status_badge(u.is_active)),
                    ft.DataCell(ft.Row(
                        spacing=0,
                        controls=[
                            action_btn(
                                ft.Icons.EDIT_OUTLINED, "Edit",
                                lambda e, usr=u: _user_form_dialog(page, session, usr, on_refresh),
                                Colors.INFO,
                            ),
                            action_btn(
                                ft.Icons.POWER_SETTINGS_NEW,
                                "Nonaktifkan" if u.is_active else "Aktifkan",
                                lambda e, uid=u.id, name=u.full_name: confirm_dialog(
                                    page,
                                    "Ubah Status User",
                                    f"Ubah status akun {name}?",
                                    lambda: _toggle_user(uid, page, on_refresh),
                                    "Ya, Ubah",
                                    Colors.WARNING,
                                ),
                                Colors.WARNING,
                            ),
                            action_btn(
                                ft.Icons.DELETE_OUTLINE, "Hapus",
                                lambda e, uid=u.id, name=u.full_name: confirm_dialog(
                                    page,
                                    "Hapus Pengguna",
                                    f"Hapus pengguna '{name}'? Tindakan ini tidak bisa dibatalkan.",
                                    lambda: _delete_user(uid, page, on_refresh),
                                ),
                                Colors.ERROR,
                            ),
                        ],
                    )),
                ],
            )
        )

    return ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44,
        data_row_min_height=56,
        column_spacing=16,
        columns=[
            ft.DataColumn(ft.Text("Nama / Email", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Username", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Role", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Status", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Aksi", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
        ],
        rows=rows,
    )


def _toggle_user(user_id: int, page: ft.Page, on_refresh: callable):
    with SessionLocal() as db:
        ok, msg = UserService.toggle_active(db, user_id)
    show_snack(page, msg, ok)
    on_refresh()


def _delete_user(user_id: int, page: ft.Page, on_refresh: callable):
    with SessionLocal() as db:
        ok, msg = UserService.delete(db, user_id)
    show_snack(page, msg, ok)
    on_refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def UsersPage(page: ft.Page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}

    # Load data awal sebelum control di-mount
    with SessionLocal() as db:
        _initial_users = UserService.get_all(db, session.company_id, "")
        for u in _initial_users:
            _ = u.user_roles
            for ur in u.user_roles:
                _ = ur.role

    list_area = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
        controls=[_build_table(_initial_users, page, session, lambda: None)],
    )

    def refresh():
        with SessionLocal() as db:
            users = UserService.get_all(db, session.company_id, search_val["q"])
            for u in users:
                _ = u.user_roles
                for ur in u.user_roles:
                    _ = ur.role
        list_area.controls = [_build_table(users, page, session, refresh)]
        try:
            list_area.update()
        except Exception:
            pass

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()


    return ft.Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                page_header(
                    "Pengguna",
                    "Kelola akun dan akses pengguna",
                    "Tambah Pengguna",
                    on_action=lambda: _user_form_dialog(page, session, None, refresh),
                ),
                ft.Row(
                    controls=[search_bar("Cari nama, username, email...", on_search)],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Container(height=16),
                ft.Container(
                    expand=True,
                    content=ft.ListView(
                        expand=True,
                        controls=[list_area],
                    ),
                ),
            ],
        ),
    )
