"""
app/pages/master/_base.py
Base pattern untuk semua halaman master data:
  MasterPage(title, columns, rows, on_add, on_search) → ft.Control

Semua halaman master pakai pola yang sama:
  Header (judul + tombol tambah) → Search bar → DataTable
"""

from __future__ import annotations
import flet as ft
from typing import List, Callable, Optional
from app.components.ui import page_header, search_bar, empty_state
from app.utils.theme import Colors, Sizes


def MasterPage(
    title: str,
    subtitle: str,
    add_label: str,
    search_hint: str,
    columns: List[ft.DataColumn],
    initial_rows: List[ft.DataRow],
    on_add: Callable,
    on_search: Callable,
    add_icon: str = ft.Icons.ADD,
    info_banner: Optional[ft.Control] = None,
) -> tuple[ft.Control, Callable]:
    """
    Return (control, set_rows_fn)
    set_rows_fn(rows) — dipanggil untuk refresh tabel
    """

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44,
        data_row_min_height=56,
        column_spacing=16,
        columns=columns,
        rows=initial_rows,
    )

    table_area = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
        controls=[table if initial_rows else empty_state()],
    )

    def set_rows(rows: List[ft.DataRow]):
        table.rows = rows
        table_area.controls = [table if rows else empty_state()]
        try:
            table_area.update()
        except Exception:
            pass

    ctrl = ft.Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                page_header(title, subtitle, add_label,
                            on_action=on_add, action_icon=add_icon),
                *([ info_banner ] if info_banner else []),
                ft.Row(controls=[search_bar(search_hint, on_search)]),
                ft.Container(height=16),
                ft.Container(
                    expand=True,
                    content=ft.ListView(expand=True, controls=[table_area]),
                ),
            ],
        ),
    )

    return ctrl, set_rows
