"""
app/pages/settings/menus.py
Halaman Pengaturan → Menu (Menu tree CRUD)
"""

from __future__ import annotations
import flet as ft
from typing import Optional, List

from app.database import SessionLocal
from app.models import Menu
from app.services.settings_service import MenuService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, page_header, search_bar,
    status_badge, action_btn, confirm_dialog,
    show_snack, empty_state,
)
from app.utils.theme import Colors, Sizes, get_icon


# ─────────────────────────────────────────────────────────────
# MENU FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _menu_form_dialog(
    page: ft.Page,
    menu: Optional[Menu],
    on_saved: callable,
):
    is_edit = menu is not None
    title   = "Edit Menu" if is_edit else "Tambah Menu"

    with SessionLocal() as db:
        all_menus = MenuService.get_all_flat(db)

    # Parent options — hanya menu root (parent_id=None) boleh jadi parent
    parent_opts = [("", "— Tidak Ada (Root) —")]
    for m in all_menus:
        if m.parent_id is None and (not is_edit or m.id != menu.id):
            parent_opts.append((str(m.id), m.label))

    f_code     = make_field("Kode Menu *", menu.code if is_edit else "",
                             hint="Contoh: MASTER_PRODUCT", read_only=is_edit)
    f_label    = make_field("Label *", menu.label if is_edit else "")
    f_icon     = make_field("Icon", menu.icon or "" if is_edit else "",
                             hint="Contoh: inventory_2")
    f_route    = make_field("Route", menu.route or "" if is_edit else "",
                             hint="Contoh: /master/products")
    f_module   = make_field("Module", menu.module or "" if is_edit else "",
                             hint="Contoh: master")
    f_sort     = make_field("Urutan", str(menu.sort_order) if is_edit else "0",
                             keyboard_type=ft.KeyboardType.NUMBER, width=120)
    f_parent   = make_dropdown("Parent Menu", parent_opts,
                               str(menu.parent_id) if (is_edit and menu.parent_id) else "")
    f_visible  = ft.Switch(
        label="Tampilkan di Menu",
        value=menu.is_visible if is_edit else True,
        active_color=Colors.ACCENT,
    )
    f_active   = ft.Switch(
        label="Aktif",
        value=menu.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )

    # Preview icon
    icon_preview = ft.Container(
        width=40, height=40,
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.1, Colors.ACCENT),
        alignment=ft.Alignment(0, 0),
        content=ft.Icon(get_icon(menu.icon if is_edit else ""), size=20, color=Colors.ACCENT),
    )

    def on_icon_change(e):
        icon_preview.content = ft.Icon(get_icon(e.control.value), size=20, color=Colors.ACCENT)
        try: icon_preview.update()
        except: pass

    f_icon.on_change = on_icon_change

    error_text = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def handle_save(e):
        if not f_label.value.strip():
            error_text.value   = "Label menu wajib diisi."
            error_text.visible = True
            error_text.update()
            return
        if not is_edit and not f_code.value.strip():
            error_text.value   = "Kode menu wajib diisi."
            error_text.visible = True
            error_text.update()
            return

        data = {
            "code":       f_code.value,
            "label":      f_label.value,
            "icon":       f_icon.value,
            "route":      f_route.value,
            "module":     f_module.value,
            "sort_order": f_sort.value or "0",
            "parent_id":  f_parent.value or None,
            "is_visible": f_visible.value,
            "is_active":  f_active.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = MenuService.update(db, menu.id, data)
            else:
                ok, msg, _ = MenuService.create(db, data)

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
            width=500,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                controls=[
                    error_text,
                    ft.ResponsiveRow(controls=[
                        ft.Container(col={"xs":12,"sm":9}, content=f_code),
                        ft.Container(col={"xs":12,"sm":3},
                                     content=ft.Column(
                                         horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                         spacing=4,
                                         controls=[
                                             ft.Text("Preview", size=11, color=Colors.TEXT_MUTED),
                                             icon_preview,
                                         ],
                                     )),
                    ], spacing=12),
                    f_label,
                    ft.ResponsiveRow(controls=[
                        ft.Container(col={"xs":12,"sm":8}, content=f_icon),
                        ft.Container(col={"xs":12,"sm":4}, content=f_sort),
                    ], spacing=12),
                    f_route,
                    ft.ResponsiveRow(controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_module),
                        ft.Container(col={"xs":12,"sm":6}, content=f_parent),
                    ], spacing=12),
                    ft.Row(spacing=24, controls=[f_visible, f_active]),
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
# MENU TREE TABLE
# ─────────────────────────────────────────────────────────────
def _build_tree_table(menus: List[Menu], page: ft.Page, on_refresh: callable) -> ft.Control:
    if not menus:
        return empty_state("Tidak ada menu.")

    rows = []
    # Pisahkan root dan children
    roots    = [m for m in menus if m.parent_id is None]
    children = {m.id: [] for m in roots}
    for m in menus:
        if m.parent_id and m.parent_id in children:
            children[m.parent_id].append(m)

    def make_row(m: Menu, is_child: bool = False) -> ft.DataRow:
        indent = 20 if is_child else 0
        icon_name = get_icon(m.icon or "")

        return ft.DataRow(
            color=ft.Colors.with_opacity(0.02, Colors.TEXT_PRIMARY) if not is_child else None,
            cells=[
                ft.DataCell(ft.Container(
                    padding=ft.Padding.only(left=indent),
                    content=ft.Row(spacing=8, controls=[
                        ft.Icon(
                            icon_name,
                            size=16,
                            color=Colors.ACCENT if not is_child else Colors.TEXT_SECONDARY,
                        ),
                        ft.Column(spacing=1, tight=True, controls=[
                            ft.Text(m.label, size=13,
                                    weight=ft.FontWeight.W_600 if not is_child else ft.FontWeight.W_400,
                                    color=Colors.TEXT_PRIMARY),
                            ft.Text(m.code, size=10, color=Colors.TEXT_MUTED,
                                    font_family="monospace"),
                        ]),
                    ]),
                )),
                ft.DataCell(ft.Text(m.route or "—", size=12, color=Colors.TEXT_SECONDARY,
                                     font_family="monospace")),
                ft.DataCell(ft.Text(m.module or "—", size=12, color=Colors.TEXT_MUTED)),
                ft.DataCell(ft.Text(str(m.sort_order), size=12, color=Colors.TEXT_MUTED)),
                ft.DataCell(ft.Row(spacing=4, controls=[
                    ft.Container(
                        content=ft.Text(
                            "Tampil" if m.is_visible else "Tersembunyi",
                            size=11,
                            color=Colors.SUCCESS if m.is_visible else Colors.TEXT_MUTED,
                        ),
                        bgcolor=ft.Colors.with_opacity(
                            0.1, Colors.SUCCESS if m.is_visible else Colors.TEXT_MUTED
                        ),
                        border_radius=4,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                    ),
                    status_badge(m.is_active),
                ])),
                ft.DataCell(ft.Row(spacing=0, controls=[
                    action_btn(
                        ft.Icons.EDIT_OUTLINED, "Edit",
                        lambda e, menu=m: _menu_form_dialog(page, menu, on_refresh),
                        Colors.INFO,
                    ),
                    action_btn(
                        ft.Icons.VISIBILITY if not m.is_visible else ft.Icons.VISIBILITY_OFF,
                        "Tampilkan" if not m.is_visible else "Sembunyikan",
                        lambda e, mid=m.id: _toggle_visible(mid, page, on_refresh),
                        Colors.TEXT_SECONDARY,
                    ),
                    action_btn(
                        ft.Icons.DELETE_OUTLINE, "Hapus",
                        lambda e, mid=m.id, lbl=m.label: confirm_dialog(
                            page,
                            "Hapus Menu",
                            f"Hapus menu '{lbl}'?",
                            lambda: _delete_menu(mid, page, on_refresh),
                        ),
                        Colors.ERROR,
                    ),
                ])),
            ],
        )

    for root in sorted(roots, key=lambda m: m.sort_order):
        rows.append(make_row(root, is_child=False))
        for child in sorted(children.get(root.id, []), key=lambda m: m.sort_order):
            rows.append(make_row(child, is_child=True))

    return ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44,
        data_row_min_height=52,
        column_spacing=16,
        columns=[
            ft.DataColumn(ft.Text("Label / Kode", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Route", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Module", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Sort", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY), numeric=True),
            ft.DataColumn(ft.Text("Tampil / Aktif", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
            ft.DataColumn(ft.Text("Aksi", size=12, weight=ft.FontWeight.W_600,
                                   color=Colors.TEXT_SECONDARY)),
        ],
        rows=rows,
    )


def _toggle_visible(menu_id: int, page: ft.Page, on_refresh: callable):
    with SessionLocal() as db:
        ok, msg = MenuService.toggle_visible(db, menu_id)
    show_snack(page, msg, ok)
    on_refresh()


def _delete_menu(menu_id: int, page: ft.Page, on_refresh: callable):
    with SessionLocal() as db:
        ok, msg = MenuService.delete(db, menu_id)
    show_snack(page, msg, ok)
    on_refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def MenusPage(page: ft.Page, session: AppSession) -> ft.Control:
    # Load data awal sebelum control di-mount
    with SessionLocal() as db:
        _initial_menus = MenuService.get_all_flat(db)

    list_area = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
        controls=[_build_tree_table(_initial_menus, page, lambda: None)],
    )

    def refresh():
        with SessionLocal() as db:
            menus = MenuService.get_all_flat(db)
        list_area.controls = [_build_tree_table(menus, page, refresh)]
        try:
            list_area.update()
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
                page_header(
                    "Manajemen Menu",
                    "Kelola struktur menu navigasi",
                    "Tambah Menu",
                    on_action=lambda: _menu_form_dialog(page, None, refresh),
                    action_icon=ft.Icons.ADD,
                ),
                ft.Container(
                    padding=ft.Padding.only(bottom=16),
                    content=ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.06, Colors.INFO),
                        border_radius=Sizes.BTN_RADIUS,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, Colors.INFO)),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        content=ft.Row(spacing=8, controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=Colors.INFO),
                            ft.Text(
                                "Perubahan menu akan terlihat setelah user logout dan login kembali.",
                                size=12, color=Colors.INFO,
                            ),
                        ]),
                    ),
                ),
                ft.Container(
                    expand=True,
                    content=ft.ListView(expand=True, controls=[list_area]),
                ),
            ],
        ),
    )
