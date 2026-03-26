"""
app/pages/master/departments.py
HR → Departemen — tree view dengan indent, form tambah/edit
"""
from __future__ import annotations
import flet as ft
from typing import Optional, List

from app.database import SessionLocal
from app.models import Department, Branch
from app.services.master_service import DepartmentService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack,
    page_header, search_bar, empty_state,
)
from app.utils.theme import Colors, Sizes


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 dept: Optional[Department], on_saved):
    is_edit = dept is not None
    d = dept

    with SessionLocal() as db:
        branches = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True
        ).order_by(Branch.name).all()

        all_depts = DepartmentService.get_all(db, session.company_id)

    br_opts = [("", "— Semua Cabang —")] + [
        (str(b.id), f"{b.name} ({b.branch_type})")
        for b in branches
    ]

    # Parent: hanya dept root (parent_id=None), max 2 level
    # Kecualikan diri sendiri saat edit
    parent_opts = [("", "— Tidak Ada (Departemen Utama) —")] + [
        (str(dp.id), dp.name)
        for dp in all_depts
        if dp.parent_id is None and (not is_edit or dp.id != d.id)
    ]

    f_code   = make_field("Kode *",
                          d.code if is_edit else "",
                          hint="Contoh: IT, FIN, MKT",
                          read_only=is_edit, width=140)
    f_name   = make_field("Nama Departemen *",
                          d.name if is_edit else "")
    f_branch = make_dropdown(
        "Cabang",
        br_opts,
        str(d.branch_id) if (is_edit and d.branch_id) else "",
    )
    f_parent = make_dropdown(
        "Induk Departemen",
        parent_opts,
        str(d.parent_id) if (is_edit and d.parent_id) else "",
    )
    f_active = ft.Switch(
        label="Aktif",
        value=d.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_name.value.strip():
            show_err("Nama departemen wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode departemen wajib diisi."); return

        data = {
            "code":      f_code.value,
            "name":      f_name.value,
            "branch_id": f_branch.value or None,
            "parent_id": f_parent.value or None,
            "is_active": f_active.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = DepartmentService.update(db, d.id, data)
            else:
                ok, msg, _ = DepartmentService.create(db, session.company_id, data)

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
                    ft.Icon(ft.Icons.APARTMENT, color=Colors.ACCENT, size=20),
                    ft.Text(
                        "Edit Departemen" if is_edit else "Tambah Departemen",
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
            width=460,
            content=ft.Column(
                spacing=12, tight=True,
                controls=[
                    err,
                    # Kode + Nama
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 4}, content=f_code),
                        ft.Container(col={"xs": 12, "sm": 8}, content=f_name),
                    ]),
                    # Cabang
                    f_branch,
                    # Induk departemen
                    f_parent,
                    # Status
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
# TABLE ROWS — tree view dengan indent
# ─────────────────────────────────────────────────────────────
def _build_rows(depts: List[Department], page, session, refresh):
    rows = []
    for d in depts:
        is_root  = d.parent_id is None
        indent   = 0 if is_root else 20
        row_bg   = ft.Colors.with_opacity(0.025, Colors.TEXT_PRIMARY) if is_root else None

        rows.append(ft.DataRow(
            color=row_bg,
            cells=[
                # Nama dengan indent & icon
                ft.DataCell(ft.Container(
                    padding=ft.Padding.only(left=indent),
                    content=ft.Row(spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                ft.Icons.APARTMENT if is_root else ft.Icons.SUBDIRECTORY_ARROW_RIGHT,
                                size=15,
                                color=Colors.ACCENT if is_root else Colors.TEXT_MUTED,
                            ),
                            ft.Text(
                                d.name,
                                size=13,
                                weight=ft.FontWeight.W_600 if is_root else ft.FontWeight.W_400,
                                color=Colors.TEXT_PRIMARY,
                            ),
                        ],
                    ),
                )),
                # Kode
                ft.DataCell(ft.Text(
                    d.code, size=12,
                    color=Colors.TEXT_SECONDARY,
                    font_family="monospace",
                )),
                # Cabang
                ft.DataCell(ft.Text(
                    getattr(d.branch, "name", None) or "Semua Cabang",
                    size=12,
                    color=Colors.TEXT_SECONDARY if d.branch_id else Colors.TEXT_MUTED,
                )),
                # Induk
                ft.DataCell(ft.Text(
                    getattr(d.parent, "name", None) or "—",
                    size=12,
                    color=Colors.TEXT_SECONDARY if d.parent_id else Colors.TEXT_MUTED,
                )),
                # Status
                ft.DataCell(status_badge(d.is_active)),
                # Aksi
                ft.DataCell(ft.Row(spacing=0, controls=[
                    action_btn(
                        ft.Icons.EDIT_OUTLINED, "Edit",
                        lambda e, dp=d: _form_dialog(page, session, dp, refresh),
                        Colors.INFO,
                    ),
                    action_btn(
                        ft.Icons.DELETE_OUTLINE, "Hapus",
                        lambda e, did=d.id, nm=d.name: confirm_dialog(
                            page,
                            "Hapus Departemen",
                            f"Hapus departemen '{nm}'?",
                            lambda: _delete(did, page, refresh),
                        ),
                        Colors.ERROR,
                    ),
                ])),
            ],
        ))
    return rows


def _delete(did, page, refresh):
    with SessionLocal() as db:
        ok, msg = DepartmentService.delete(db, did)
    show_snack(page, msg, ok)
    if ok:
        refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def DepartmentsPage(page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}

    # Load data awal dengan urutan tree
    with SessionLocal() as db:
        initial = DepartmentService.get_ordered(db, session.company_id)

    COLS = [
        ft.DataColumn(ft.Text("Nama",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kode",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Induk",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",        size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",          size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44,
        data_row_min_height=52,
        column_spacing=16,
        columns=COLS,
        rows=_build_rows(initial, page, session, lambda: None),
    )

    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada departemen.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def refresh():
        with SessionLocal() as db:
            if search_val["q"]:
                # saat search: tampilkan flat, tidak tree
                depts = DepartmentService.get_all(db, session.company_id, search_val["q"])
            else:
                depts = DepartmentService.get_ordered(db, session.company_id)
        table.rows = _build_rows(depts, page, session, refresh)
        table_area.controls = [table if depts else empty_state("Tidak ada departemen ditemukan.")]
        try:
            table_area.update()
        except Exception:
            pass

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    # Patch initial rows dengan refresh yang benar
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
                    "Departemen",
                    "Kelola struktur departemen per cabang",
                    "Tambah Departemen",
                    on_action=lambda: _form_dialog(page, session, None, refresh),
                    action_icon=ft.Icons.ADD,
                ),
                ft.Row(controls=[search_bar("Cari nama atau kode...", on_search)]),
                ft.Container(height=16),
                ft.Container(
                    expand=True,
                    content=ft.ListView(expand=True, controls=[table_area]),
                ),
            ],
        ),
    )
