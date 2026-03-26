"""
app/pages/settings/roles.py
Halaman Pengaturan → Role & Akses (Role CRUD + Permission Matrix)
"""

from __future__ import annotations
import flet as ft
from typing import Optional, List, Dict

from app.database import SessionLocal
from app.models import Role, Menu, RoleMenuPermission
from app.services.settings_service import RoleService, MenuService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, page_header, search_bar,
    status_badge, action_btn, confirm_dialog,
    show_snack, empty_state,
)
from app.utils.theme import Colors, Sizes


# ─────────────────────────────────────────────────────────────
# ROLE FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _role_form_dialog(
    page: ft.Page,
    session: AppSession,
    role: Optional[Role],
    on_saved: callable,
):
    is_edit = role is not None
    title   = "Edit Role" if is_edit else "Tambah Role"

    f_code = make_field(
        "Kode Role *", role.code if is_edit else "",
        hint="Contoh: MANAGER", read_only=is_edit,
    )
    f_name   = make_field("Nama Role *", role.name if is_edit else "")
    f_desc   = make_field("Deskripsi", role.description or "" if is_edit else "",
                          multiline=True, min_lines=2, max_lines=4)
    f_active = ft.Switch(
        label="Role Aktif",
        value=role.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )
    error_text = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def handle_save(e):
        if not f_name.value.strip():
            error_text.value = "Nama role wajib diisi."
            error_text.visible = True
            error_text.update()
            return
        if not is_edit and not f_code.value.strip():
            error_text.value = "Kode role wajib diisi."
            error_text.visible = True
            error_text.update()
            return
        data = {
            "code": f_code.value, "name": f_name.value,
            "description": f_desc.value, "is_active": f_active.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = RoleService.update(db, role.id, data)
            else:
                ok, msg, _ = RoleService.create(db, session.company_id, data)
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
                ft.Text(title, color=Colors.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_700, size=16),
                ft.IconButton(
                    icon=ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                    on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                ),
            ],
        ),
        content=ft.Container(
            width=420,
            content=ft.Column(
                spacing=14, tight=True,
                controls=[error_text, f_code, f_name, f_desc, f_active],
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
                on_click=handle_save,
            ),
        ],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# PERMISSION MATRIX DIALOG
# ─────────────────────────────────────────────────────────────
def _permission_dialog(page: ft.Page, role: Role, on_saved: callable):
    PERM_COLS = ["view", "create", "edit", "delete", "approve", "export"]
    COL_LABEL = {
        "view": "Lihat", "create": "Buat", "edit": "Edit",
        "delete": "Hapus", "approve": "Approve", "export": "Export",
    }

    # ── Load data ────────────────────────────────────────────
    with SessionLocal() as db:
        all_menus_raw = MenuService.get_all_flat(db)
        current_perms = RoleService.get_permissions(db, role.id)
        # Pisahkan root & children, urutkan parent dulu
        roots    = [m for m in all_menus_raw if m.parent_id is None]
        child_of = {}
        for m in all_menus_raw:
            if m.parent_id:
                child_of.setdefault(m.parent_id, []).append(m)
        # Urutan: root → children-nya → root berikutnya
        ordered_menus = []
        for root in sorted(roots, key=lambda x: x.sort_order):
            ordered_menus.append(root)
            for child in sorted(child_of.get(root.id, []), key=lambda x: x.sort_order):
                ordered_menus.append(child)

    # Map: child_menu_id → parent_menu_id
    parent_of: Dict[int, int] = {}
    for m in ordered_menus:
        if m.parent_id is not None:
            parent_of[m.id] = m.parent_id

    # ── State dict: {menu_id: {perm: bool}} ─────────────────
    perm_state: Dict[int, Dict[str, bool]] = {}
    for m in ordered_menus:
        rmp = current_perms.get(m.id)
        perm_state[m.id] = {
            p: (getattr(rmp, f"can_{p}", False) if rmp else False)
            for p in PERM_COLS
        }

    # ── Checkbox registry ────────────────────────────────────
    # cb_reg[menu_id][perm] = ft.Checkbox
    cb_reg: Dict[int, Dict[str, ft.Checkbox]] = {}

    def _set_cb(mid: int, perm: str, val: bool):
        """Helper: set state + update checkbox UI."""
        perm_state[mid][perm] = val
        if mid in cb_reg and perm in cb_reg[mid]:
            cb_reg[mid][perm].value = val
            try: cb_reg[mid][perm].update()
            except: pass

    def _ensure_parent_view(menu_id: int):
        """Jika menu_id adalah child, pastikan parent-nya can_view=True."""
        pid = parent_of.get(menu_id)
        if pid is not None and not perm_state.get(pid, {}).get("view", False):
            _set_cb(pid, "view", True)

    def _on_cb_change(e, menu_id: int, perm: str):
        val = e.control.value
        _set_cb(menu_id, perm, val)

        if val:
            # Centang perm apapun → pastikan view menu ini aktif
            if perm != "view":
                _set_cb(menu_id, "view", True)
            # Centang child → pastikan parent view aktif
            _ensure_parent_view(menu_id)
        else:
            # Uncheck view → uncheck semua perm di baris ini
            if perm == "view":
                for p in PERM_COLS:
                    if p != "view":
                        _set_cb(menu_id, p, False)

    def _make_cb(menu_id: int, perm: str) -> ft.Checkbox:
        cb = ft.Checkbox(
            value=perm_state[menu_id][perm],
            active_color=Colors.ACCENT,
            check_color=Colors.TEXT_ON_ACCENT,
            on_change=lambda e, mid=menu_id, p=perm: _on_cb_change(e, mid, p),
        )
        cb_reg.setdefault(menu_id, {})[perm] = cb
        return cb

    # ── Select/reset helpers ─────────────────────────────────
    def _select_col(perm: str, val: bool):
        """Centang/hapus semua checkbox di satu kolom."""
        for mid in cb_reg:
            _set_cb(mid, perm, val)
        if val:
            # Centang perm apapun → centang view semua baris
            if perm != "view":
                for mid in cb_reg:
                    _set_cb(mid, "view", True)
        else:
            # Uncheck view → uncheck semua perm di semua baris
            if perm == "view":
                for p in PERM_COLS:
                    for mid in cb_reg:
                        _set_cb(mid, p, False)

    def _select_row(menu_id: int, val: bool):
        """Centang/hapus semua perm di satu baris menu."""
        for p in PERM_COLS:
            _set_cb(menu_id, p, val)
        if val:
            # Centang child → centang parent view juga
            _ensure_parent_view(menu_id)

    def _reset_all():
        for p in PERM_COLS:
            _select_col(p, False)

    def _select_all():
        for p in PERM_COLS:
            _select_col(p, True)

    # ── Build DataTable rows ─────────────────────────────────
    dt_rows = []
    for m in ordered_menus:
        is_root  = m.parent_id is None
        indent   = 0 if is_root else 24
        row_bg   = ft.Colors.with_opacity(0.03, Colors.TEXT_PRIMARY) if is_root else None

        # Kolom label menu
        label_cell = ft.DataCell(
            ft.Container(
                padding=ft.Padding.only(left=indent),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(
                            ft.Icons.FOLDER_OUTLINED if is_root else ft.Icons.CHEVRON_RIGHT,
                            size=14,
                            color=Colors.ACCENT if is_root else Colors.TEXT_MUTED,
                        ),
                        ft.Text(
                            m.label,
                            size=13,
                            color=Colors.TEXT_PRIMARY if is_root else Colors.TEXT_SECONDARY,
                            weight=ft.FontWeight.W_600 if is_root else ft.FontWeight.W_400,
                        ),
                    ],
                ),
            )
        )

        # Kolom tombol "Semua" per baris
        row_all_cell = ft.DataCell(
            ft.Button(
                "Semua",
                style=ft.ButtonStyle(
                    color=Colors.ACCENT,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                ),
                on_click=lambda e, mid=m.id: _select_row(mid, True),
            )
        )

        # Kolom checkbox per permission
        perm_cells = [
            ft.DataCell(
                ft.Container(
                    alignment=ft.Alignment(0, 0),
                    content=_make_cb(m.id, p),
                )
            )
            for p in PERM_COLS
        ]

        dt_rows.append(ft.DataRow(
            color=row_bg,
            cells=[label_cell, row_all_cell, *perm_cells],
        ))

    # ── Quick-select toolbar ─────────────────────────────────
    toolbar = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        border_radius=Sizes.BTN_RADIUS,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(
            spacing=0,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("Pilih kolom:", size=12, color=Colors.TEXT_MUTED),
                ft.Container(width=8),
                *[
                    ft.Button(
                        COL_LABEL[p],
                        style=ft.ButtonStyle(
                            color=Colors.INFO,
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        ),
                        on_click=lambda e, p=p: _select_col(p, True),
                    )
                    for p in PERM_COLS
                ],
                ft.Container(
                    width=1, height=20,
                    bgcolor=Colors.BORDER,
                    margin=ft.margin.symmetric(horizontal=8),
                ),
                ft.Button(
                    "Semua",
                    style=ft.ButtonStyle(
                        color=Colors.SUCCESS,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    ),
                    on_click=lambda e: _select_all(),
                ),
                ft.Button(
                    "Reset",
                    style=ft.ButtonStyle(
                        color=Colors.ERROR,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    ),
                    on_click=lambda e: _reset_all(),
                ),
            ],
        ),
    )

    # ── DataTable ────────────────────────────────────────────
    data_table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.05, Colors.TEXT_PRIMARY),
        heading_row_height=42,
        data_row_min_height=44,
        column_spacing=4,
        columns=[
            ft.DataColumn(ft.Text("Menu", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("", size=12)),   # kolom "Semua" per baris
            *[
                ft.DataColumn(
                    ft.Text(COL_LABEL[p], size=11, weight=ft.FontWeight.W_600,
                            color=Colors.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    numeric=True,
                )
                for p in PERM_COLS
            ],
        ],
        rows=dt_rows,
    )

    # ── Save ─────────────────────────────────────────────────
    def handle_save(e):
        with SessionLocal() as db:
            ok, msg = RoleService.save_permissions(db, role.id, perm_state)
        dlg.open = False
        page.update()
        show_snack(page, msg, ok)
        if ok:
            on_saved()

    # ── Dialog ───────────────────────────────────────────────
    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=2, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.SECURITY, color=Colors.ACCENT, size=20),
                        ft.Text(f"Permission — {role.name}",
                                color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                    ]),
                    ft.Text("Centang aksi yang diizinkan untuk setiap menu.",
                            size=11, color=Colors.TEXT_MUTED),
                ]),
                ft.IconButton(
                    icon=ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                    on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                ),
            ],
        ),
        content=ft.Container(
            width=820,
            height=520,
            content=ft.Column(
                spacing=10,
                controls=[
                    toolbar,
                    ft.Container(
                        expand=True,
                        content=ft.ListView(
                            expand=True,
                            controls=[data_table],
                        ),
                    ),
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
                content=ft.Row(
                    tight=True, spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.SAVE_OUTLINED, size=16,
                                color=Colors.TEXT_ON_ACCENT),
                        ft.Text("Simpan Permission", size=13,
                                color=Colors.TEXT_ON_ACCENT,
                                weight=ft.FontWeight.W_600),
                    ],
                ),
                bgcolor=Colors.ACCENT,
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
# ROLE TABLE
# ─────────────────────────────────────────────────────────────
def _build_table(roles: List[Role], page: ft.Page,
                 session: AppSession, on_refresh: callable) -> ft.Control:
    if not roles:
        return empty_state("Tidak ada role ditemukan.")

    rows = []
    for r in roles:
        with SessionLocal() as db:
            perm_count = db.query(RoleMenuPermission).filter_by(role_id=r.id).count()

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=2, tight=True, controls=[
                ft.Row(spacing=8, controls=[
                    ft.Text(r.name, size=13, weight=ft.FontWeight.W_600,
                            color=Colors.TEXT_PRIMARY),
                    ft.Container(
                        content=ft.Text("Sistem", size=10, color=Colors.WARNING),
                        bgcolor=ft.Colors.with_opacity(0.1, Colors.WARNING),
                        border_radius=4,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        visible=r.is_system,
                    ),
                ]),
                ft.Text(r.description or "—", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(
                ft.Text(r.code, size=12, color=Colors.TEXT_SECONDARY,
                        font_family="monospace")
            ),
            ft.DataCell(
                ft.Container(
                    content=ft.Text(f"{perm_count} menu", size=12,
                                    color=Colors.ACCENT if perm_count > 0 else Colors.TEXT_MUTED),
                    bgcolor=ft.Colors.with_opacity(
                        0.1 if perm_count > 0 else 0.04,
                        Colors.ACCENT if perm_count > 0 else Colors.TEXT_MUTED
                    ),
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                )
            ),
            ft.DataCell(status_badge(r.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(
                    ft.Icons.SECURITY, "Atur Permission",
                    lambda e, role=r: _permission_dialog(page, role, on_refresh),
                    Colors.ACCENT,
                ),
                action_btn(
                    ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, role=r: _role_form_dialog(page, session, role, on_refresh),
                    Colors.INFO,
                ),
                action_btn(
                    ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, rid=r.id, name=r.name, sys=r.is_system: (
                        show_snack(page, "Role sistem tidak bisa dihapus.", False)
                        if sys else
                        confirm_dialog(
                            page, "Hapus Role", f"Hapus role '{name}'?",
                            lambda: _delete_role(rid, page, on_refresh),
                        )
                    ),
                    Colors.ERROR,
                ),
            ])),
        ]))

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
            ft.DataColumn(ft.Text("Nama / Deskripsi", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Kode", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Permission", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Status", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Aksi", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
        ],
        rows=rows,
    )


def _delete_role(role_id: int, page: ft.Page, on_refresh: callable):
    with SessionLocal() as db:
        ok, msg = RoleService.delete(db, role_id)
    show_snack(page, msg, ok)
    on_refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def RolesPage(page: ft.Page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}

    with SessionLocal() as db:
        _initial_roles = RoleService.get_all(db, session.company_id, "")
        for r in _initial_roles:
            _ = r.permissions

    list_area = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
        controls=[_build_table(_initial_roles, page, session, lambda: None)],
    )

    def refresh():
        with SessionLocal() as db:
            roles = RoleService.get_all(db, session.company_id, search_val["q"])
            for r in roles:
                _ = r.permissions
        list_area.controls = [_build_table(roles, page, session, refresh)]
        try:
            list_area.update()
        except Exception:
            pass

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    # Patch: ganti on_refresh di _initial_roles agar pakai refresh yang benar
    list_area.controls = [_build_table(_initial_roles, page, session, refresh)]

    return ft.Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                page_header(
                    "Role & Akses",
                    "Kelola role dan hak akses per menu",
                    "Tambah Role",
                    on_action=lambda: _role_form_dialog(page, session, None, refresh),
                    action_icon=ft.Icons.ADD_MODERATOR,
                ),
                ft.Row(controls=[search_bar("Cari nama role...", on_search)]),
                ft.Container(height=16),
                ft.Container(
                    expand=True,
                    content=ft.ListView(expand=True, controls=[list_area]),
                ),
            ],
        ),
    )
