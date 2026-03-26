"""
app/components/topbar.py
Top bar — Flet v0.25+ (tanpa UserControl)
"""

from __future__ import annotations
import flet as ft
from app.utils.theme import Colors, Sizes, build_theme # Import build_theme juga


def create_topbar(
    page: ft.Page,
    on_theme_change = None,  # Callback saat tema berubah: fn(is_dark: bool)
    title: str = "Dashboard",
    full_name: str = "",
    company_name: str = "",
) -> dict:
    """
    Mengembalikan dict:
      - 'container': ft.Container (root control)
      - 'set_title' : fn(title, subtitle="")
    """
    def ThemeSwitcher(page: ft.Page, on_change: callable):
    # Definisi warna representatif untuk setiap tema
        theme_options = [
            {"name": "light",  "color": "#FFD200", "tip": "Sunshine (Default)"},
            {"name": "dark",   "color": "#000000", "tip": "Midnight Teal"},
            {"name": "ocean",  "color": "#0EA5E9", "tip": "Ocean Breeze"},
            {"name": "purple", "color": "#A855F7", "tip": "Cyber Purple"},
            {"name": "earth",  "color": "#D97706", "tip": "Terracotta"},
        ]

        def handle_click(mode_name):
            page.session.store.set("theme_name", mode_name)
            on_change(mode_name)

        return ft.Row(
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=24,
                    height=24,
                    border_radius=12,
                    bgcolor=opt["color"],
                    tooltip=opt["tip"],
                    on_click=lambda e, m=opt["name"]: handle_click(m),
                    border=ft.border.all(2, Colors.BORDER if page.session.store.get("theme_name") != opt["name"] else Colors.ACCENT),
                    animate=ft.Animation(300, ft.AnimationCurve.DECELERATE),
                ) for opt in theme_options
            ]
        )
    
    switcher = ThemeSwitcher(page, on_change=on_theme_change)



    title_text    = ft.Text(title, size=16, weight=ft.FontWeight.W_600,
                            color=Colors.TEXT_PRIMARY)
    subtitle_text = ft.Text(company_name, size=11, color=Colors.TEXT_MUTED)

    container = ft.Container(
        height=Sizes.TOPBAR_H,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.only(bottom=ft.BorderSide(1, Colors.BORDER)),
        padding=ft.Padding.symmetric(horizontal=24),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                # Tombol Ganti Tema (Ceria / Dark)
                
                ft.Column(
                    spacing=0, tight=True,
                    controls=[title_text, subtitle_text], alignment=ft.Alignment.CENTER
                ),
                switcher,
                ft.Row(
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.SEARCH,
                            icon_color=Colors.TEXT_SECONDARY,
                            icon_size=20,
                            tooltip="Pencarian",
                        ),
                        ft.IconButton(
                            icon=ft.Icons.NOTIFICATIONS_NONE,
                            icon_color=Colors.TEXT_SECONDARY,
                            icon_size=20,
                            tooltip="Notifikasi",
                        ),
                        ft.Container(width=8),
                        ft.Container(
                            width=34, height=34,
                            border_radius=17,
                            bgcolor=Colors.ACCENT,
                            alignment=ft.Alignment.CENTER,
                            tooltip=full_name,
                            content=ft.Text(
                                full_name[0].upper() if full_name else "?",
                                size=14, weight=ft.FontWeight.W_700,
                                color=Colors.TEXT_ON_ACCENT,
                            ),
                        ),
                    ],
                ),
            ],
        ),
    )

    def set_title(new_title: str, subtitle: str = ""):
        title_text.value    = new_title
        subtitle_text.value = subtitle or company_name
        try:
            title_text.update()
            subtitle_text.update()
        except Exception:
            pass



    return {
        "container": container,
        "set_title":  set_title,
    }

