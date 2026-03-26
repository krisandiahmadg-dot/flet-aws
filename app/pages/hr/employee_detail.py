"""
app/pages/hr/employee_detail.py
Halaman Detail Karyawan — info lengkap + riwayat assignment
Flet v0.25+  |  Sesuai model & hr_service terbaru
- EmployeeAssignment.roles  → JSON list of string (nama role)
- UserRole → untuk section Roles Sistem
"""

from __future__ import annotations
from flet import *
import flet as ft
from typing import Optional, List, Callable
from sqlalchemy.orm import joinedload
from app.services.auth import AppSession
from app.database import SessionLocal
from app.models import Employee, EmployeeAssignment, User, UserRole
from app.utils.theme import Sizes, Colors
import datetime as dt


_TYPE_COLOR = {
    "PERMANENT": "#3B82F6",
    "CONTRACT":  "#F59E0B",
    "INTERN":    "#8B5CF6",
    "FREELANCE": "#EC4899",
}


# ─────────────────────────────────────────────────────────────
# Micro-components
# ─────────────────────────────────────────────────────────────

def _badge(label: str, color: str) -> Container:
    return Container(
        padding=Padding.symmetric(horizontal=10, vertical=3),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border=Border.all(1, ft.Colors.with_opacity(0.35, color)),
        content=Text(label, size=10, color=color, weight=FontWeight.W_600),
    )


def _info_item(label: str, value: str, icon: Optional[str] = None) -> Container:
    return Container(
        padding=Padding.symmetric(vertical=9),
        border=Border(bottom=BorderSide(1, Colors.DIVIDER)),
        content=Row(spacing=10, vertical_alignment=CrossAxisAlignment.CENTER, controls=[
            Icon(icon, size=13, color=Colors.TEXT_MUTED) if icon
            else Container(width=13),
            Container(width=140,
                      content=Text(label, size=12, color=Colors.TEXT_SECONDARY)),
            Text(value if value else "—", size=13,
                 color=Colors.TEXT_PRIMARY if value else Colors.TEXT_MUTED,
                 weight=FontWeight.W_500, expand=True),
        ]),
    )


def _section_label(label: str, icon: str) -> Container:
    return Container(
        margin=Margin(0, 20, 0, 8),
        content=Row(spacing=8, controls=[
            Icon(icon, size=13, color=Colors.ACCENT),
            Text(label, size=10, weight=FontWeight.W_700, color=Colors.TEXT_SECONDARY),
            Container(expand=True, height=1, bgcolor=Colors.BORDER,
                      margin=Margin(4, 0, 0, 0)),
        ]),
    )


def _stat_card(label: str, value: str, icon: str, color: str) -> Container:
    return Container(
        expand=True,
        padding=Padding.symmetric(horizontal=16, vertical=12),
        border_radius=Sizes.BTN_RADIUS,
        bgcolor=ft.Colors.with_opacity(0.07, color),
        border=Border.all(1, ft.Colors.with_opacity(0.2, color)),
        content=Column(spacing=4, tight=True, controls=[
            Row(spacing=6, controls=[
                Icon(icon, size=13, color=color),
                Text(label, size=10, color=color, weight=FontWeight.W_600),
            ]),
            Text(value, size=20, weight=FontWeight.W_700, color=Colors.TEXT_PRIMARY),
        ]),
    )


def _work_duration(hire_date) -> str:
    if not hire_date:
        return "—"
    today  = dt.date.today()
    delta  = today - hire_date
    years  = delta.days // 365
    months = (delta.days % 365) // 30
    if years > 0:
        return f"{years}th {months}bl"
    if months > 0:
        return f"{months} bulan"
    return f"{delta.days} hari"


# ─────────────────────────────────────────────────────────────
# Assignment card
# roles diambil langsung dari a.roles (JSON list of string)
# ─────────────────────────────────────────────────────────────
def _assignment_card(a: EmployeeAssignment) -> Container:
    is_active    = a.is_active
    accent_color = Colors.SUCCESS if is_active else Colors.TEXT_MUTED

    branch_name = (f"{a.branch.code} — {a.branch.name}" if a.branch else "—")
    dept_name   = (f"{a.departments.code} — {a.departments.name}" if a.departments else "—")

    # roles → JSON list of string langsung dari kolom
    _roles    = a.roles if isinstance(a.roles, list) else []

    start_str = a.start_date.strftime("%d %b %Y") if a.start_date else "—"
    end_str   = a.end_date.strftime("%d %b %Y")   if a.end_date   else "Sekarang"

    return Container(
        margin=Margin(0, 0, 0, 10),
        padding=Padding.all(16),
        border_radius=Sizes.CARD_RADIUS,
        bgcolor=ft.Colors.with_opacity(0.04 if is_active else 0.02, accent_color),
        border=Border.all(1, ft.Colors.with_opacity(0.3 if is_active else 0.1, accent_color)),
        content=Column(spacing=10, controls=[
            # Header
            Row(
                alignment=MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=CrossAxisAlignment.CENTER,
                controls=[
                    Row(spacing=8, controls=[
                        Container(
                            width=28, height=28, border_radius=14,
                            bgcolor=ft.Colors.with_opacity(0.15, accent_color),
                            alignment=Alignment.CENTER,
                            content=Icon(Icons.ASSIGNMENT_IND_OUTLINED,
                                         size=14, color=accent_color),
                        ),
                        Column(spacing=1, tight=True, controls=[
                            Text(a.code, size=13, weight=FontWeight.W_700,
                                 color=Colors.TEXT_PRIMARY, font_family="monospace"),
                            Text(f"{start_str}  →  {end_str}",
                                 size=10, color=Colors.TEXT_MUTED),
                        ]),
                    ]),
                    _badge("Aktif" if is_active else "Nonaktif", accent_color),
                ],
            ),
            # Info grid
            ResponsiveRow(spacing=4, controls=[
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item("Cabang",     branch_name, Icons.STORE_OUTLINED)),
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item("Departemen", dept_name,   Icons.APARTMENT_OUTLINED)),
                # Roles — badge chips dari JSON list
                Container(
                    col={"xs": 12},
                    content=Container(
                        padding=Padding.symmetric(vertical=8),
                        border=Border(bottom=BorderSide(1, Colors.DIVIDER)),
                        content=Row(spacing=8, vertical_alignment=CrossAxisAlignment.CENTER, controls=[
                            Icon(Icons.SHIELD_OUTLINED, size=13, color=Colors.TEXT_MUTED),
                            Container(width=140,
                                      content=Text("Role", size=12, color=Colors.TEXT_SECONDARY)),
                            Row(
                                wrap=True, spacing=4, run_spacing=4, expand=True,
                                controls=[
                                    Container(
                                        padding=Padding.symmetric(horizontal=8, vertical=2),
                                        border_radius=20,
                                        bgcolor=ft.Colors.with_opacity(0.1, Colors.INFO),
                                        border=Border.all(1, ft.Colors.with_opacity(0.3, Colors.INFO)),
                                        content=Text(r, size=10, color=Colors.INFO,
                                                     weight=FontWeight.W_600),
                                    )
                                    for r in _roles
                                ] if _roles else [Text("—", size=13, color=Colors.TEXT_MUTED)],
                            ),
                        ]),
                    ),
                ),
            ]),
        ]),
    )


# ─────────────────────────────────────────────────────────────
# MAIN: EmployeeDetailPage
# ─────────────────────────────────────────────────────────────
def EmployeeDetailPage(
    page: ft.Page,
    session: AppSession,
    employee: Employee,
    on_back:   Callable,
    on_edit:   Callable,
    on_assign: Callable,
) -> ft.Control:

    # ── Load data via joinedload ──────────────────────────────
    with SessionLocal() as db:
        assignments: List[EmployeeAssignment] = (
            db.query(EmployeeAssignment)
            .options(
                joinedload(EmployeeAssignment.branch),
                joinedload(EmployeeAssignment.departments),
                joinedload(EmployeeAssignment.employee)
                    .joinedload(Employee.user)
                    .joinedload(User.user_roles)
                    .joinedload(UserRole.role),
                joinedload(EmployeeAssignment.employee)
                    .joinedload(Employee.user)
                    .joinedload(User.user_roles)
                    .joinedload(UserRole.branch),
            )
            .filter_by(employee_id=employee.id)
            .order_by(EmployeeAssignment.created_at.desc())
            .all()
        )

        # user_roles untuk section Roles Sistem
        _emp_obj  = assignments[0].employee if assignments else None
        _user_obj = _emp_obj.user if _emp_obj else None
        user_roles: List[UserRole] = _user_obj.user_roles if _user_obj else []

    active_asg = next((a for a in assignments if a.is_active), None)
    total_asg  = len(assignments)
    type_color = _TYPE_COLOR.get(employee.type, Colors.TEXT_MUTED)
    initials   = "".join(w[0].upper() for w in (employee.name or "?").split()[:2])

    # ── Breadcrumb ────────────────────────────────────────────
    breadcrumb = Row(
        spacing=4,
        vertical_alignment=CrossAxisAlignment.CENTER,
        controls=[
            IconButton(
                Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_color=Colors.TEXT_SECONDARY, icon_size=15,
                tooltip="Kembali ke daftar",
                style=ButtonStyle(padding=Padding.all(6)),
                on_click=lambda e: on_back(),
            ),
            Text("Karyawan", size=13, color=Colors.TEXT_SECONDARY),
            Icon(Icons.CHEVRON_RIGHT, size=14, color=Colors.TEXT_MUTED),
            Text(employee.name, size=13, color=Colors.TEXT_PRIMARY,
                 weight=FontWeight.W_600),
        ],
    )

    # ── Profile header card ───────────────────────────────────
    # Roles aktif saat ini (dari assignment aktif — JSON list)
    active_roles_str = (
        ", ".join(active_asg.roles)
        if (active_asg and isinstance(active_asg.roles, list) and active_asg.roles)
        else "Belum ada assignment aktif"
    )

    profile_card = Container(
        padding=Padding.all(24),
        border_radius=Sizes.CARD_RADIUS,
        bgcolor=Colors.BG_CARD,
        border=Border.all(1, Colors.BORDER),
        content=Column(spacing=16, controls=[
            Row(
                spacing=16,
                vertical_alignment=CrossAxisAlignment.START,
                controls=[
                    # Avatar
                    Container(
                        width=64, height=64, border_radius=32,
                        bgcolor=ft.Colors.with_opacity(0.15, type_color),
                        border=Border.all(2, ft.Colors.with_opacity(0.4, type_color)),
                        alignment=Alignment.CENTER,
                        content=Text(initials, size=22, weight=FontWeight.W_700,
                                     color=type_color),
                    ),
                    # Info nama
                    Column(spacing=6, tight=True, expand=True, controls=[
                        Text(employee.name, size=18, weight=FontWeight.W_700,
                             color=Colors.TEXT_PRIMARY),
                        Row(spacing=6, controls=[
                            Container(
                                padding=Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=6,
                                bgcolor=ft.Colors.with_opacity(0.08, Colors.TEXT_MUTED),
                                content=Text(employee.code, size=10,
                                             color=Colors.TEXT_SECONDARY,
                                             font_family="monospace"),
                            ),
                            _badge(employee.type, type_color),
                            _badge("Aktif" if employee.is_active else "Nonaktif",
                                   Colors.SUCCESS if employee.is_active else Colors.ERROR),
                        ]),
                        Row(spacing=6, controls=[
                            Icon(Icons.SHIELD_OUTLINED, size=12, color=Colors.TEXT_MUTED),
                            Text(active_roles_str, size=12, color=Colors.TEXT_SECONDARY),
                        ]),
                        Row(spacing=6, controls=[
                            Icon(Icons.STORE_OUTLINED, size=12, color=Colors.TEXT_MUTED),
                            Text(
                                active_asg.branch.name
                                if (active_asg and active_asg.branch) else "—",
                                size=12, color=Colors.TEXT_SECONDARY,
                            ),
                        ]),
                    ]),
                    # Tombol aksi
                    Column(spacing=8, tight=True, controls=[
                        ft.FilledButton(
                            content=Row(tight=True, spacing=6, controls=[
                                Icon(Icons.EDIT_OUTLINED, size=13,
                                     color=Colors.TEXT_ON_ACCENT),
                                Text("Edit", size=12, color=Colors.TEXT_ON_ACCENT),
                            ]),
                            height=34,
                            style=ButtonStyle(
                                bgcolor=Colors.ACCENT,
                                shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                                elevation=0,
                            ),
                            on_click=lambda e: on_edit(),
                        ),
                        OutlinedButton(
                            content=Row(tight=True, spacing=6, controls=[
                                Icon(Icons.ASSIGNMENT_IND_OUTLINED, size=13,
                                     color=Colors.ACCENT),
                                Text("Assign", size=12, color=Colors.ACCENT),
                            ]),
                            height=34,
                            style=ButtonStyle(
                                shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                                side=BorderSide(1, ft.Colors.with_opacity(0.4, Colors.ACCENT)),
                            ),
                            on_click=lambda e: on_assign(),
                        ),
                    ]),
                ],
            ),
            # Stat cards
            Row(spacing=10, controls=[
                _stat_card("TOTAL ASSIGNMENT", str(total_asg),
                           Icons.ASSIGNMENT_OUTLINED, Colors.INFO),
                _stat_card("MASA KERJA", _work_duration(employee.hire_date),
                           Icons.TIMER_OUTLINED, Colors.WARNING),
                _stat_card("STATUS",
                           "Aktif" if employee.is_active else "Nonaktif",
                           Icons.CIRCLE_OUTLINED,
                           Colors.SUCCESS if employee.is_active else Colors.ERROR),
            ]),
        ]),
    )

    # ── Info card ─────────────────────────────────────────────
    info_card = Container(
        padding=Padding.all(24),
        border_radius=Sizes.CARD_RADIUS,
        bgcolor=Colors.BG_CARD,
        border=Border.all(1, Colors.BORDER),
        content=Column(spacing=0, controls=[

            _section_label("INFORMASI PRIBADI", Icons.PERSON_OUTLINE),
            ResponsiveRow(spacing=0, controls=[
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item("Nama Lengkap", employee.name,
                                             Icons.BADGE_OUTLINED)),
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item("Kode", employee.code,
                                             Icons.TAG_OUTLINED)),
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item("Tipe", employee.type,
                                             Icons.WORK_OUTLINE)),
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item(
                              "Tanggal Lahir",
                              employee.birth_date.strftime("%d %b %Y")
                              if employee.birth_date else "",
                              Icons.CAKE_OUTLINED)),
            ]),

            _section_label("KONTAK", Icons.CONTACTS_OUTLINED),
            ResponsiveRow(spacing=0, controls=[
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item("Telepon", employee.phone or "",
                                             Icons.PHONE_OUTLINED)),
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item("Email", employee.email or "",
                                             Icons.EMAIL_OUTLINED)),
                Container(col={"xs": 12},
                          content=_info_item("Alamat", employee.address or "",
                                             Icons.LOCATION_ON_OUTLINED)),
            ]),

            _section_label("KEPEGAWAIAN", Icons.BUSINESS_CENTER_OUTLINED),
            ResponsiveRow(spacing=0, controls=[
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item(
                              "Tanggal Masuk",
                              employee.hire_date.strftime("%d %b %Y")
                              if employee.hire_date else "",
                              Icons.LOGIN_OUTLINED)),
                Container(col={"xs": 12, "sm": 6},
                          content=_info_item(
                              "Tanggal Keluar",
                              employee.resign_date.strftime("%d %b %Y")
                              if employee.resign_date else "Masih aktif",
                              Icons.LOGOUT_OUTLINED)),
            ]),

            # ── Roles dari user_roles (tabel UserRole) ────────
            _section_label("ROLES SISTEM", Icons.SHIELD_OUTLINED),
            Container(
                padding=Padding.symmetric(vertical=8),
                content=(
                    Row(
                        wrap=True, spacing=6, run_spacing=6,
                        controls=[
                            Container(
                                padding=Padding.symmetric(horizontal=10, vertical=4),
                                border_radius=20,
                                bgcolor=ft.Colors.with_opacity(0.1, Colors.INFO),
                                border=Border.all(1, ft.Colors.with_opacity(0.3, Colors.INFO)),
                                content=Row(spacing=6, tight=True, controls=[
                                    Icon(Icons.SHIELD_OUTLINED, size=11, color=Colors.INFO),
                                    Text(ur.role.name, size=11, color=Colors.INFO,
                                         weight=FontWeight.W_600),
                                    *([ Text(f"· {ur.branch.name}", size=10,
                                            color=Colors.TEXT_MUTED)]
                                      if ur.branch else []),
                                ]),
                            )
                            for ur in user_roles if ur.role
                        ],
                    )
                    if user_roles
                    else Text("Belum ada role yang ditetapkan.",
                              size=12, color=Colors.TEXT_MUTED)
                ),
            ),
        ]),
    )

    # ── Assignment history card ───────────────────────────────
    asg_content = (
        Column(spacing=0, controls=[_assignment_card(a) for a in assignments])
        if assignments else
        Container(
            padding=Padding.symmetric(vertical=40),
            content=Column(
                horizontal_alignment=CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    Icon(Icons.ASSIGNMENT_LATE_OUTLINED, size=40, color=Colors.TEXT_MUTED),
                    Text("Belum ada riwayat assignment.", size=13, color=Colors.TEXT_MUTED),
                    OutlinedButton(
                        content=Row(tight=True, spacing=6, controls=[
                            Icon(Icons.ADD, size=13, color=Colors.ACCENT),
                            Text("Buat Assignment", size=12, color=Colors.ACCENT),
                        ]),
                        height=34,
                        style=ButtonStyle(
                            shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                            side=BorderSide(1, ft.Colors.with_opacity(0.4, Colors.ACCENT)),
                        ),
                        on_click=lambda e: on_assign(),
                    ),
                ],
            ),
        )
    )

    assignment_card = Container(
        padding=Padding.all(24),
        border_radius=Sizes.CARD_RADIUS,
        bgcolor=Colors.BG_CARD,
        border=Border.all(1, Colors.BORDER),
        content=Column(spacing=0, controls=[
            _section_label("RIWAYAT ASSIGNMENT", Icons.HISTORY_OUTLINED),
            asg_content,
        ]),
    )

    # ── Root layout ───────────────────────────────────────────
    return Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        padding=Padding.all(24),
        content=Column(
            expand=True,
            spacing=16,
            scroll=ScrollMode.AUTO,
            controls=[
                breadcrumb,
                profile_card,
                Row(
                    spacing=16,
                    vertical_alignment=CrossAxisAlignment.START,
                    controls=[
                        Container(expand=2, content=info_card),
                        Container(expand=3, content=assignment_card),
                    ],
                ),
            ],
        ),
    )