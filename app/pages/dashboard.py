"""
app/pages/dashboard.py
Halaman dashboard — stat cards, placeholder chart, quick actions.
"""

from __future__ import annotations
import flet as ft
from app.utils.theme import Colors, Sizes
from app.services.auth import AppSession


def _stat_card(title: str, value: str, icon: str,
               color: str, subtitle: str = "") -> ft.Control:
    return ft.Container(
        width=220,
        height=110,
        bgcolor=Colors.BG_CARD,
        border_radius=Sizes.CARD_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.all(18),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            controls=[
                ft.Container(
                    width=48, height=48,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=24, color=color),
                ),
                ft.Column(
                    spacing=2, tight=True,
                    controls=[
                        ft.Text(title, size=12, color=Colors.TEXT_SECONDARY),
                        ft.Text(value, size=22, weight=ft.FontWeight.W_700,
                                color=Colors.TEXT_PRIMARY),
                        ft.Text(subtitle, size=11, color=Colors.TEXT_MUTED),
                    ],
                ),
            ],
        ),
    )


def _quick_action(label: str, icon: str, route: str,
                  on_navigate) -> ft.Control:
    return ft.Container(
        height=48, width=180,
        border_radius=Sizes.BTN_RADIUS,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.symmetric(horizontal=14),
        on_click=lambda e: on_navigate(route, ""),
        ink=True,
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=18, color=Colors.ACCENT),
                ft.Text(label, size=13, color=Colors.TEXT_PRIMARY),
            ],
        ),
    )


def DashboardPage(session: AppSession, on_navigate) -> ft.Control:
    stats = ft.ResponsiveRow(
        controls=[
            ft.Container(
                col={"xs": 12, "sm": 6, "md": 3},
                content=_stat_card("Total SO Hari Ini", "0",
                                   ft.Icons.SHOPPING_BAG, Colors.ACCENT, "Sales Order"),
            ),
            ft.Container(
                col={"xs": 12, "sm": 6, "md": 3},
                content=_stat_card("PO Pending", "0",
                                   ft.Icons.RECEIPT_LONG, Colors.WARNING, "Purchase Order"),
            ),
            ft.Container(
                col={"xs": 12, "sm": 6, "md": 3},
                content=_stat_card("Stok Menipis", "0",
                                   ft.Icons.WARNING_AMBER, Colors.ERROR, "Di bawah reorder"),
            ),
            ft.Container(
                col={"xs": 12, "sm": 6, "md": 3},
                content=_stat_card("Pelanggan Baru", "0",
                                   ft.Icons.PEOPLE, Colors.INFO, "Bulan ini"),
            ),
        ],
        spacing=16,
        run_spacing=16,
    )

    quick_actions = ft.Column(
        spacing=8,
        controls=[
            ft.Text("Aksi Cepat", size=14, weight=ft.FontWeight.W_600,
                    color=Colors.TEXT_SECONDARY),
            ft.Row(
                wrap=True,
                spacing=10, run_spacing=10,
                controls=[
                    _quick_action("Sales Order Baru", ft.Icons.ADD_SHOPPING_CART,
                                  "/sales/so", on_navigate),
                    _quick_action("Purchase Order",   ft.Icons.ADD_CIRCLE_OUTLINE,
                                  "/purchasing/po", on_navigate),
                    _quick_action("Transfer Stok",    ft.Icons.SYNC_ALT,
                                  "/inventory/transfer", on_navigate),
                    _quick_action("Stock Opname",     ft.Icons.CHECKLIST,
                                  "/inventory/opname", on_navigate),
                ],
            ),
        ],
    )

    # Placeholder chart area
    chart_placeholder = ft.Container(
        height=260,
        bgcolor=Colors.BG_CARD,
        border_radius=Sizes.CARD_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.all(20),
        content=ft.Column(
            controls=[
                ft.Text("Grafik Penjualan (30 Hari Terakhir)",
                        size=14, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
                ft.Container(expand=True,
                             alignment=ft.Alignment.CENTER,
                             content=ft.Column(
                                 horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                 controls=[
                                     ft.Icon(ft.Icons.BAR_CHART, size=48,
                                             color=Colors.TEXT_MUTED),
                                     ft.Text("Data akan muncul setelah transaksi tercatat",
                                             color=Colors.TEXT_MUTED, size=13),
                                 ],
                             )),
            ],
        ),
    )

    return ft.Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(
            spacing=24,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                # Greeting
                ft.Column(
                    spacing=2, tight=True,
                    controls=[
                        ft.Text(
                            f"Selamat datang, {session.full_name} 👋",
                            size=20, weight=ft.FontWeight.W_700,
                            color=Colors.TEXT_PRIMARY,
                        ),
                        ft.Text(
                            f"{session.company_name}  ·  {session.branch_name or 'Semua Cabang'}",
                            size=13, color=Colors.TEXT_MUTED,
                        ),
                    ],
                ),
                stats,
                chart_placeholder,
                quick_actions,
            ],
        ),
    )
