"""
app/components/sidebar.py
Sidebar navigasi dinamis — Flet v0.25+ (tanpa UserControl, tanpa ft.Tooltip)
ft.Tooltip tidak support content= di v0.25+, pakai tooltip= di Container/IconButton
"""

from __future__ import annotations
import flet as ft
from typing import Callable, List, Dict, Optional

from app.utils.theme import Colors, Sizes, get_icon


def create_sidebar(
    menu_tree: List[Dict],
    full_name: str,
    company_name: str,
    on_navigate: Callable[[str, str], None],
    on_logout: Callable[[], None],
    initial_route: str = "/dashboard",
) -> dict:

    state = {
        "expanded":     True,
        "active_route": initial_route,
        "active_code":  "",
        "group_open":   {},
    }

    root = ft.Container(
        bgcolor=Colors.BG_SIDEBAR,
        border=ft.Border.only(right=ft.BorderSide(1, Colors.BORDER)),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
    )

    def rebuild():
        w = Sizes.SIDEBAR_W if state["expanded"] else Sizes.SIDEBAR_W_RAIL
        root.width = w
        root.content = ft.Column(
            spacing=0,
            expand=True,
            controls=[
                _build_header(),
                ft.Divider(height=1, color=Colors.BORDER),
                ft.Container(
                    expand=True,
                    content=ft.ListView(
                        expand=True,
                        spacing=2,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=8),
                        controls=_build_menu_items(),
                    ),
                ),
                ft.Divider(height=1, color=Colors.BORDER),
                _build_user_panel(),
            ],
        )
        try:
            root.update()
        except Exception:
            pass

    # ── Header ───────────────────────────────────────────────
    def _build_header():
        if state["expanded"]:
            return ft.Container(
                height=Sizes.TOPBAR_H,
                padding=ft.Padding.symmetric(horizontal=16),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.HUB_ROUNDED, color=Colors.LOGO, size=24),
                                ft.Column(
                                    spacing=0, tight=True,
                                    controls=[
                                        ft.Text("ERP System", size=14,
                                                weight=ft.FontWeight.W_700,
                                                color=Colors.TEXT_HEAD_TITLE),
                                        ft.Text(company_name, size=10,
                                                color=Colors.TEXT_SUB_TITLE,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                                width=130),
                                    ],
                                ),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.MENU_OPEN,
                            icon_color=Colors.ICON_MENU,
                            icon_size=18,
                            tooltip="Perkecil sidebar",
                            on_click=lambda e: toggle_collapse(),
                            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                        ),
                    ],
                ),
            )
        else:
            return ft.Container(
                height=Sizes.TOPBAR_H,
                alignment=ft.Alignment.CENTER,
                content=ft.IconButton(
                    icon=ft.Icons.MENU,
                    icon_color=Colors.TEXT_MENU,
                    icon_size=20,
                    tooltip="Perluas sidebar",
                    on_click=lambda e: toggle_collapse(),
                ),
            )

    # ── Menu ─────────────────────────────────────────────────
    def _build_menu_items():
        controls = []
        for group in menu_tree:
            controls.extend(_build_group(group))
        return controls

    def _build_group(group: Dict):
        children = group.get("children", [])
        code  = group["code"]
        icon  = get_icon(group.get("icon", ""))
        label = group["label"]
        route = group.get("route")

        if not children:
            return [_build_leaf(code, label, icon, route)]

        if code not in state["group_open"]:
            state["group_open"][code] = True
        is_open = state["group_open"][code]

        def _toggle(e, c=code):
            state["group_open"][c] = not state["group_open"].get(c, True)
            rebuild()

        if state["expanded"]:
            header = ft.Container(
                height=38,
                border_radius=Sizes.BTN_RADIUS,
                padding=ft.Padding.symmetric(horizontal=8),
                on_click=_toggle,
                ink=True,
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(icon, size=18, color=Colors.ICON_MENU),
                        ft.Text(label, size=13, color=Colors.TEXT_MENU,
                                weight=ft.FontWeight.W_500, expand=True),
                        ft.Icon(
                            ft.Icons.EXPAND_LESS if is_open else ft.Icons.EXPAND_MORE,
                            size=16, color=Colors.ICON_MENU,
                        ),
                    ],
                ),
            )
        else:
            # Rail mode — tooltip via property Container, bukan ft.Tooltip
            header = ft.Container(
                height=38, width=48,
                border_radius=Sizes.BTN_RADIUS,
                alignment=ft.Alignment.CENTER,
                on_click=_toggle,
                ink=True,
                tooltip=label,
                content=ft.Icon(icon, size=20, color=Colors.ICON_MENU),
            )

        result = [header]
        if is_open and state["expanded"]:
            for child in children:
                result.append(
                    _build_leaf(
                        child["code"], child["label"],
                        get_icon(child.get("icon", "")),
                        child.get("route", ""),
                        indent=True,
                    )
                )
        return result

    def _build_leaf(code, label, icon, route, indent=False):
        is_active  = (code == state["active_code"]) or \
                     (bool(route) and route == state["active_route"])
        bg_color   = Colors.BG_HOVER       if is_active else ft.Colors.TRANSPARENT
        txt_color  = Colors.ACCENT         if is_active else Colors.TEXT_MENU
        icon_color = Colors.ACCENT         if is_active else Colors.ICON_MENU

        def _click(e, r=route, c=code):
            if r:
                on_navigate(r, c)

        if state["expanded"]:
            left_pad = 28 if indent else 8
            return ft.Container(
                height=36,
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=bg_color,
                padding=ft.Padding.only(left=left_pad, right=8),
                on_click=_click,
                ink=True,
                content=ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=3, height=20, border_radius=2,
                            bgcolor=Colors.ACCENT if is_active else ft.Colors.TRANSPARENT,
                        ) if indent else ft.Container(width=0),
                        ft.Icon(icon, size=16, color=icon_color, animate_size=200,),
                        ft.Text(label, size=13, color=txt_color,
                                weight=ft.FontWeight.W_500 if is_active else ft.FontWeight.W_400,),
                    ],
                ),
            )
        else:
            # Rail mode — tooltip via property, bukan ft.Tooltip
            return ft.Container(
                height=36, width=48,
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=bg_color,
                alignment=ft.Alignment.CENTER,
                on_click=_click,
                ink=True,
                tooltip=label,
                content=ft.Icon(icon, size=18, color=icon_color),
            )

    # ── User Panel ───────────────────────────────────────────
    def _build_user_panel():
        avatar = ft.Container(
            width=32, height=32, border_radius=16,
            bgcolor=Colors.ACCENT,
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                full_name[0].upper() if full_name else "?",
                size=14, weight=ft.FontWeight.W_700,
                color=Colors.TEXT_ON_ACCENT,
            ),
        )
        if state["expanded"]:
            return ft.Container(
                height=60,
                padding=ft.Padding.symmetric(horizontal=12),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                avatar,
                                ft.Column(
                                    spacing=0, tight=True,
                                    controls=[
                                        ft.Text(full_name, size=13,
                                                weight=ft.FontWeight.W_600,
                                                color=Colors.TEXT_HEAD_TITLE),
                                        ft.Text("Online", size=11, color=Colors.SUCCESS),
                                    ],
                                ),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.LOGOUT,
                            icon_color=Colors.ICON_MENU,
                            icon_size=18,
                            tooltip="Keluar",
                            on_click=lambda e: on_logout(),
                        ),
                    ],
                ),
            )
        else:
            return ft.Container(
                height=60,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    controls=[
                        avatar,
                        ft.IconButton(
                            icon=ft.Icons.LOGOUT,
                            icon_color=Colors.ICON_MENU,
                            icon_size=14,
                            tooltip="Keluar",
                            on_click=lambda e: on_logout(),
                            style=ft.ButtonStyle(padding=ft.Padding.all(2)),
                        ),
                    ],
                ),
            )

    # ── Public API ───────────────────────────────────────────
    def set_active(route: str, code: str):
        state["active_route"] = route
        state["active_code"]  = code
        rebuild()

    def toggle_collapse():
        state["expanded"] = not state["expanded"]
        rebuild()

    rebuild()

    return {
        "container":       root,
        "set_active":      set_active,
        "toggle_collapse": toggle_collapse,
    }
