"""
app/pages/login.py
Halaman login — Flet v0.25+
"""

from __future__ import annotations
import flet as ft
from typing import Callable, Tuple

from app.utils.theme import Colors, Sizes


def LoginPage(on_login: Callable[[str, str], None]) -> Tuple[ft.Control, Callable]:
    """
    Returns (control, show_error_fn)
    """

    username_field = ft.TextField(
        label="Username atau Email",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        autofocus=True,
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        color=Colors.TEXT_PRIMARY,
        cursor_color=Colors.ACCENT,
        border_radius=Sizes.BTN_RADIUS,
        height=52,
        width=360,
    )

    password_field = ft.TextField(
        label="Password",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.ACCENT,
        color=Colors.TEXT_PRIMARY,
        cursor_color=Colors.ACCENT,
        border_radius=Sizes.BTN_RADIUS,
        height=52,
        width=360,
    )

    error_text = ft.Text(
        value="",
        color=Colors.ERROR,
        size=13,
        visible=False,
        width=360,
    )

    # Spinner ditaruh di dalam Row bersama tombol, BUKAN Stack
    spinner = ft.ProgressRing(
        width=18, height=18,
        stroke_width=2,
        color=Colors.TEXT_ON_ACCENT,
        visible=False,
    )

    login_btn = ft.Button(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=10,
            controls=[
                spinner,
                ft.Text("Masuk", size=14, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_ON_ACCENT),
            ],
        ),
        width=360,
        height=48,
        bgcolor=Colors.ACCENT,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
            elevation=0,
            overlay_color=Colors.ACCENT_DARK,
        ),
    )

    # ── Helpers ──────────────────────────────────────────────
    def show_error(msg: str):
        error_text.value   = msg
        error_text.visible = bool(msg)
        try:
            error_text.update()
        except Exception:
            pass

    def set_loading(val: bool):
        spinner.visible         = val
        login_btn.disabled      = val
        username_field.disabled = val
        password_field.disabled = val
        try:
            spinner.update()
            login_btn.update()
            username_field.update()
            password_field.update()
        except Exception:
            pass

    def handle_submit(e=None):
        show_error("")
        u = (username_field.value or "").strip()
        p = (password_field.value or "")

        if not u:
            show_error("Username tidak boleh kosong.")
            username_field.focus()
            return
        if not p:
            show_error("Password tidak boleh kosong.")
            password_field.focus()
            return

        set_loading(True)
        try:
            on_login(u, p)
        finally:
            set_loading(False)

    login_btn.on_click       = handle_submit
    password_field.on_submit = handle_submit

    # ── Layout ───────────────────────────────────────────────
    card = ft.Container(
        width=420,
        padding=ft.Padding.symmetric(horizontal=40, vertical=44),
        bgcolor=Colors.BG_CARD,
        border_radius=Sizes.CARD_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=48,
            color=ft.Colors.with_opacity(0.45, "#000000"),
            offset=ft.Offset(0, 12),
        ),
        content=ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            controls=[
                ft.Icon(ft.Icons.HUB_ROUNDED, size=52, color=Colors.ACCENT),
                ft.Container(height=10),
                ft.Text("ERP System", size=26, weight=ft.FontWeight.W_700,
                        color=Colors.TEXT_PRIMARY),
                ft.Container(height=4),
                ft.Text("Masuk ke akun Anda", size=13, color=Colors.TEXT_SECONDARY),
                ft.Container(height=32),
                username_field,
                ft.Container(height=12),
                password_field,
                ft.Container(height=10),
                error_text,
                ft.Container(height=16),
                login_btn,          # <-- langsung, tanpa Stack
                ft.Container(height=24),
                ft.Divider(color=Colors.BORDER, height=1),
                ft.Container(height=12),
                ft.Text(
                    "© 2025 ERP System · Flet + SQLAlchemy",
                    size=11, color=Colors.TEXT_MUTED,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
        ),
    )

    page_ctrl = ft.Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        alignment=ft.Alignment.CENTER,
        content=card,
    )

    return page_ctrl, show_error
