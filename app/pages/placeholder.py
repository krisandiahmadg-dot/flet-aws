"""
app/pages/placeholder.py
Halaman placeholder untuk menu yang belum diimplementasi.
"""

import flet as ft
from app.utils.theme import Colors, Sizes


def PlaceholderPage(title: str, route: str) -> ft.Control:
    return ft.Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=16,
            controls=[
                ft.Container(
                    width=80, height=80,
                    border_radius=20,
                    bgcolor=ft.Colors.with_opacity(0.08, Colors.ACCENT),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.CONSTRUCTION, size=40, color=Colors.ACCENT),
                ),
                ft.Text(title, size=22, weight=ft.FontWeight.W_700,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(f"Halaman {route} sedang dalam pengembangan.",
                        size=14, color=Colors.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    bgcolor=ft.Colors.with_opacity(0.06, Colors.ACCENT),
                    border_radius=6,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, Colors.ACCENT)),
                    content=ft.Text(
                        f"Route: {route}",
                        size=12,
                        color=Colors.ACCENT,
                        font_family="monospace",
                    ),
                ),
            ],
        ),
    )
