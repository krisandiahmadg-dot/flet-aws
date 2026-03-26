"""
app/components/ui.py
Komponen UI reusable: DataTable, Dialog, FormField, Badge, dll.
"""

from __future__ import annotations
import flet as ft
from typing import List, Dict, Any, Callable, Optional
from app.utils.theme import Colors, Sizes
import datetime

def my_date_picker(page: ft.Page):
    # Variabel internal untuk menyimpan siapa yang sedang memanggil picker ini
    current_callback = [None] 

    def handle_change(e: ft.Event[ft.DatePicker]):
        if e.control.value and current_callback[0]:
            # Koreksi 12 jam agar tidak -1 hari
            temp_dt = e.control.value + datetime.timedelta(hours=12)
            final_date = temp_dt.strftime('%d-%m-%Y')
            
            # Panggil fungsi yang sedang aktif
            current_callback[0](final_date)

    today = datetime.datetime.now()
    picker = ft.DatePicker(
        first_date=datetime.datetime(year=today.year - 100, month=1, day=1),
        last_date=datetime.datetime(year=today.year + 5, month=12, day=31),
        on_change=handle_change,
    )
    

    # Kita kembalikan fungsi pembuka yang dinamis
    def open_picker(target_callback):
        current_callback[0] = target_callback
        page.show_dialog(picker)
    
    return open_picker


# ─────────────────────────────────────────────────────────────
# HELPER: field standar
# ─────────────────────────────────────────────────────────────
def make_field(
    label: str,
    value: str = "",
    hint: str = "",
    password: bool = False,
    multiline: bool = False,
    min_lines: int = 1,
    max_lines: int = 1,
    read_only: bool = False,
    width: Optional[float] = None,
    keyboard_type: ft.KeyboardType = ft.KeyboardType.TEXT,
) -> ft.TextField:
    kw: dict = dict(
        label=label,
        value=value,
        hint_text=hint,
        password=password,
        can_reveal_password=password,
        multiline=multiline,
        min_lines=min_lines,
        max_lines=max_lines if multiline else 1,
        read_only=read_only,
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        color=Colors.TEXT_PRIMARY,
        cursor_color=Colors.ACCENT,
        border_radius=Sizes.BTN_RADIUS,
        keyboard_type=keyboard_type,
    )
    if width:
        kw["width"] = width
    return ft.TextField(**kw)


def make_dropdown(
    label: str,
    options: List[tuple],   # [(value, label), ...]
    value: str = "",
    width: Optional[float] = None,
    disabled: bool = False,
) -> ft.Dropdown:
    kw = dict(
        label=label,
        value=value or None,
        disabled=disabled,
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        color=Colors.TEXT_PRIMARY,
        border_radius=Sizes.BTN_RADIUS,
        options=[ft.dropdown.Option(key=v, text=t) for v, t in options],
    )
    if width:
        kw["width"] = width
    return ft.Dropdown(**kw)


# ─────────────────────────────────────────────────────────────
# STATUS BADGE
# ─────────────────────────────────────────────────────────────
def status_badge(active: bool) -> ft.Container:
    color = Colors.SUCCESS if active else Colors.ERROR
    text  = "Aktif" if active else "Nonaktif"
    return ft.Container(
        content=ft.Text(text, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def role_badge(name: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(name, size=11, color=Colors.INFO, weight=ft.FontWeight.W_500),
        bgcolor=ft.Colors.with_opacity(0.1, Colors.INFO),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


# ─────────────────────────────────────────────────────────────
# PAGE HEADER
# ─────────────────────────────────────────────────────────────
def page_header(
    title: str,
    subtitle: str = "",
    action_label: str = "",
    on_action: Optional[Callable] = None,
    action_icon: str = ft.Icons.ADD,
) -> ft.Control:
    right = []
    if action_label and on_action:
        right.append(
            ft.Button(
                content=ft.Row(
                    tight=True, spacing=6,
                    controls=[
                        ft.Icon(action_icon, size=16, color=Colors.TEXT_ON_ACCENT),
                        ft.Text(action_label, size=13, color=Colors.TEXT_ON_ACCENT,
                                weight=ft.FontWeight.W_600),
                    ],
                ),
                bgcolor=Colors.ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0,
                ),
                on_click=lambda e: on_action(),
            )
        )

    return ft.Container(
        padding=ft.Padding.only(bottom=20),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=2, tight=True,
                    controls=[
                        ft.Text(title, size=20, weight=ft.FontWeight.W_700,
                                color=Colors.TEXT_PRIMARY),
                        ft.Text(subtitle, size=13, color=Colors.TEXT_MUTED)
                        if subtitle else ft.Container(),
                    ],
                ),
                ft.Row(spacing=8, controls=right),
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────
# SEARCH BAR
# ─────────────────────────────────────────────────────────────
def search_bar(hint: str, on_change: Callable, width: float = 280) -> ft.TextField:
    return ft.TextField(
        hint_text=hint,
        prefix_icon=ft.Icons.SEARCH,
        on_change=on_change,
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        color=Colors.TEXT_PRIMARY,
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=13),
        cursor_color=Colors.ACCENT,
        border_radius=Sizes.BTN_RADIUS,
        height=40,
        width=width,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
    )


# ─────────────────────────────────────────────────────────────
# ACTION BUTTONS (row di tiap baris tabel)
# ─────────────────────────────────────────────────────────────
def action_btn(
    icon: str,
    tooltip: str,
    on_click: Callable,
    color: str = Colors.TEXT_SECONDARY,
    disabled: bool = False
) -> ft.IconButton:
    return ft.IconButton(
        icon=icon,
        icon_color=color,
        icon_size=18,
        tooltip=tooltip,
        on_click=on_click,
        style=ft.ButtonStyle(padding=ft.Padding.all(4)),
        disabled=disabled
    )


# ─────────────────────────────────────────────────────────────
# CONFIRM DIALOG
# ─────────────────────────────────────────────────────────────
def confirm_dialog(
    page: ft.Page,
    title: str,
    message: str,
    on_confirm: Callable,
    confirm_label: str = "Ya, Lanjutkan",
    confirm_color: str = Colors.ERROR,
):
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(title, color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700),
        content=ft.Text(message, color=Colors.TEXT_SECONDARY, size=14),
        bgcolor=Colors.BG_CARD,
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button(
                "Batal",
                style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                on_click=lambda e: close_dlg(),
            ),
            ft.Button(
                confirm_label,
                bgcolor=confirm_color,
                color=ft.Colors.WHITE,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0,
                ),
                on_click=lambda e: (close_dlg(), on_confirm()),
            ),
        ],
    )

    def close_dlg():
        dlg.open = False
        page.update()

    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# SNACKBAR
# ─────────────────────────────────────────────────────────────
def show_snack(page: ft.Page, message: str, success: bool = True):
    page.show_dialog(ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=Colors.SUCCESS if success else Colors.ERROR,
        duration=3000,
    ))
    page.update()


# ─────────────────────────────────────────────────────────────
# EMPTY STATE
# ─────────────────────────────────────────────────────────────
def empty_state(message: str = "Tidak ada data") -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=60),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Icon(ft.Icons.INBOX, size=48, color=Colors.TEXT_MUTED),
                ft.Text(message, size=14, color=Colors.TEXT_MUTED),
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────
# LOADING SPINNER
# ─────────────────────────────────────────────────────────────
def loading_spinner() -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=60),
        alignment=ft.Alignment(0, 0),
        content=ft.ProgressRing(color=Colors.ACCENT, width=32, height=32, stroke_width=3),
    )


# ─────────────────────────────────────────────────────────────
# SECTION CARD (container untuk grup form)
# ─────────────────────────────────────────────────────────────
def section_card(title: str, controls: List[ft.Control],
                 visible: bool = True) -> ft.Container:
    return ft.Container(
        visible=visible,
        bgcolor=Colors.BG_CARD,
        border_radius=Sizes.CARD_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.all(20),
        content=ft.Column(
            spacing=16,
            controls=[
                ft.Text(title, size=14, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_SECONDARY),
                ft.Divider(height=1, color=Colors.BORDER),
                *controls,
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────
# PERMISSION CHECKBOX ROW
# ─────────────────────────────────────────────────────────────
def perm_checkbox(label: str, value: bool, on_change: Callable) -> ft.Checkbox:
    return ft.Checkbox(
        label=label,
        value=value,
        on_change=on_change,
        active_color=Colors.ACCENT,
        check_color=Colors.TEXT_ON_ACCENT,
    )
