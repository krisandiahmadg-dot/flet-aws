"""
app/pages/marketing/campaigns.py
Marketing → Campaign — CRUD lengkap dengan status management
"""
from __future__ import annotations
import flet as ft
from typing import Optional
from datetime import datetime

from app.database import SessionLocal
from app.models import Campaign, Branch
from app.services.master_service import CampaignService
from app.services.auth import AppSession
from app.pages.master._base import MasterPage
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    confirm_dialog, show_snack, section_card,
)
from app.utils.theme import Colors, Sizes

_TYPE_OPTS = [
    ("DIGITAL",  "Digital"),
    ("PRINT",    "Cetak / Print"),
    ("EVENT",    "Event / Pameran"),
    ("EMAIL",    "Email Marketing"),
    ("SMS",      "SMS / WhatsApp"),
    ("REFERRAL", "Referral"),
    ("OTHER",    "Lainnya"),
]

_STATUS_OPTS = [
    ("DRAFT",     "Draft"),
    ("ACTIVE",    "Aktif"),
    ("PAUSED",    "Dijeda"),
    ("COMPLETED", "Selesai"),
    ("CANCELLED", "Dibatalkan"),
]

_STATUS_COLOR = {
    "DRAFT":     Colors.TEXT_MUTED,
    "ACTIVE":    Colors.SUCCESS,
    "PAUSED":    Colors.WARNING,
    "COMPLETED": Colors.INFO,
    "CANCELLED": Colors.ERROR,
}

_STATUS_NEXT = {
    "DRAFT":     [("ACTIVE", "Aktifkan")],
    "ACTIVE":    [("PAUSED", "Jeda"), ("COMPLETED", "Selesaikan")],
    "PAUSED":    [("ACTIVE", "Lanjutkan"), ("CANCELLED", "Batalkan")],
    "COMPLETED": [],
    "CANCELLED": [],
}


def _status_badge(status: str) -> ft.Container:
    color = _STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    label = dict(_STATUS_OPTS).get(status, status)
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _type_badge(t: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(dict(_TYPE_OPTS).get(t, t), size=11,
                        color=Colors.TEXT_SECONDARY),
        bgcolor=ft.Colors.with_opacity(0.06, Colors.TEXT_PRIMARY),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 campaign: Optional[Campaign], on_saved):
    is_edit = campaign is not None
    c = campaign

    with SessionLocal() as db:
        branches = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True
        ).order_by(Branch.name).all()

    br_opts = [("", "— Semua Cabang —")] + [
        (str(b.id), b.name) for b in branches
    ]

    # Helper format tanggal
    def _fmt_date(d) -> str:
        if not d:
            return ""
        if isinstance(d, str):
            return d[:10]
        return d.strftime("%Y-%m-%d")

    f_code    = make_field("Kode *",
                           c.code if is_edit else "",
                           hint="Contoh: CAMP-2025-01",
                           read_only=is_edit, width=180)
    f_name    = make_field("Nama Campaign *", c.name if is_edit else "")
    f_type    = make_dropdown("Tipe *", _TYPE_OPTS,
                              c.campaign_type if is_edit else "DIGITAL", width=200)
    f_channel = make_field("Channel / Platform",
                           c.channel or "" if is_edit else "",
                           hint="Instagram, Google Ads, dll")
    f_branch  = make_dropdown("Cabang", br_opts,
                              str(c.branch_id) if (is_edit and c.branch_id) else "")
    f_status  = make_dropdown("Status", _STATUS_OPTS,
                              c.status if is_edit else "DRAFT", width=160)
    f_start   = make_field("Tanggal Mulai",
                           _fmt_date(c.start_date) if is_edit else "",
                           hint="YYYY-MM-DD", width=180)
    f_end     = make_field("Tanggal Selesai",
                           _fmt_date(c.end_date) if is_edit else "",
                           hint="YYYY-MM-DD", width=180)
    f_budget  = make_field("Budget (Rp)",
                           str(int(c.budget)) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=200)
    f_spend   = make_field("Realisasi (Rp)",
                           str(int(c.actual_spend)) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=200)
    f_leads   = make_field("Target Leads",
                           str(c.target_leads) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=160)
    f_revenue = make_field("Target Revenue (Rp)",
                           str(int(c.target_revenue)) if is_edit else "0",
                           keyboard_type=ft.KeyboardType.NUMBER, width=200)
    f_desc    = make_field("Deskripsi",
                           c.description or "" if is_edit else "",
                           multiline=True, min_lines=2, max_lines=4)

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def _parse_date(val: str):
        val = (val or "").strip()
        if not val:
            return None
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            return None

    def save(e):
        if not f_name.value.strip():
            show_err("Nama campaign wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode campaign wajib diisi."); return

        start = _parse_date(f_start.value)
        end   = _parse_date(f_end.value)
        if f_start.value.strip() and not start:
            show_err("Format tanggal mulai salah. Gunakan YYYY-MM-DD."); return
        if f_end.value.strip() and not end:
            show_err("Format tanggal selesai salah. Gunakan YYYY-MM-DD."); return
        if start and end and end < start:
            show_err("Tanggal selesai tidak boleh sebelum tanggal mulai."); return

        data = {
            "code":           f_code.value,
            "name":           f_name.value,
            "campaign_type":  f_type.value,
            "channel":        f_channel.value,
            "branch_id":      f_branch.value or None,
            "status":         f_status.value,
            "start_date":     start,
            "end_date":       end,
            "budget":         f_budget.value or "0",
            "actual_spend":   f_spend.value or "0",
            "target_leads":   f_leads.value or "0",
            "target_revenue": f_revenue.value or "0",
            "description":    f_desc.value,
        }

        with SessionLocal() as db:
            if is_edit:
                ok, msg = CampaignService.update(db, c.id, data)
            else:
                ok, msg, _ = CampaignService.create(db, session.company_id, data)

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
                    ft.Icon(ft.Icons.CAMPAIGN, color=Colors.ACCENT, size=20),
                    ft.Text(
                        "Edit Campaign" if is_edit else "Tambah Campaign",
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
            width=560, height=540,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=14,
                controls=[
                    err,
                    section_card("Informasi Campaign", [
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs": 12, "sm": 5}, content=f_code),
                            ft.Container(col={"xs": 12, "sm": 7}, content=f_name),
                        ]),
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs": 12, "sm": 5}, content=f_type),
                            ft.Container(col={"xs": 12, "sm": 7}, content=f_channel),
                        ]),
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs": 12, "sm": 7}, content=f_branch),
                            ft.Container(col={"xs": 12, "sm": 5}, content=f_status),
                        ]),
                        f_desc,
                    ]),
                    section_card("Jadwal", [
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs": 12, "sm": 6}, content=f_start),
                            ft.Container(col={"xs": 12, "sm": 6}, content=f_end),
                        ]),
                    ]),
                    section_card("Anggaran & Target", [
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs": 12, "sm": 6}, content=f_budget),
                            ft.Container(col={"xs": 12, "sm": 6}, content=f_spend),
                        ]),
                        ft.ResponsiveRow(spacing=12, controls=[
                            ft.Container(col={"xs": 12, "sm": 5}, content=f_leads),
                            ft.Container(col={"xs": 12, "sm": 7}, content=f_revenue),
                        ]),
                    ]),
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
# TABLE ROWS
# ─────────────────────────────────────────────────────────────
def _build_rows(campaigns, page, session, refresh):
    rows = []
    for c in campaigns:

        # Progress bar budget
        budget_pct = min((c.actual_spend / c.budget * 100) if c.budget > 0 else 0, 100)
        budget_color = Colors.ERROR if budget_pct > 90 else \
                       Colors.WARNING if budget_pct > 70 else Colors.SUCCESS

        # Tombol ubah status
        status_btns = []
        for next_status, next_label in _STATUS_NEXT.get(c.status, []):
            status_btns.append(
                action_btn(
                    ft.Icons.PLAY_ARROW if next_status == "ACTIVE"
                    else ft.Icons.PAUSE if next_status == "PAUSED"
                    else ft.Icons.CHECK_CIRCLE if next_status == "COMPLETED"
                    else ft.Icons.CANCEL,
                    next_label,
                    lambda e, cid=c.id, ns=next_status, nl=next_label: confirm_dialog(
                        page,
                        "Ubah Status Campaign",
                        f"Ubah status campaign ke '{nl}'?",
                        lambda: _change_status(cid, ns, page, refresh),
                        nl,
                        Colors.WARNING,
                    ),
                    _STATUS_COLOR.get(next_status, Colors.TEXT_SECONDARY),
                )
            )

        rows.append(ft.DataRow(cells=[
            # Nama + Kode
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(c.name, size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(c.code, size=11, color=Colors.TEXT_MUTED,
                        font_family="monospace"),
            ])),
            # Tipe
            ft.DataCell(_type_badge(c.campaign_type)),
            # Channel
            ft.DataCell(ft.Text(c.channel or "—", size=12,
                                color=Colors.TEXT_SECONDARY)),
            # Jadwal
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(
                    str(c.start_date)[:10] if c.start_date else "—",
                    size=12, color=Colors.TEXT_SECONDARY,
                ),
                ft.Text(
                    str(c.end_date)[:10] if c.end_date else "—",
                    size=11, color=Colors.TEXT_MUTED,
                ),
            ])),
            # Budget + progress
            ft.DataCell(ft.Column(spacing=4, tight=True, controls=[
                ft.Text(
                    f"Rp {c.budget:,.0f}" if c.budget else "—",
                    size=12, color=Colors.TEXT_PRIMARY,
                ),
                ft.Container(
                    width=120, height=4,
                    border_radius=2,
                    bgcolor=ft.Colors.with_opacity(0.15, budget_color),
                    content=ft.Container(
                        width=budget_pct * 1.2,  # max ~120px
                        bgcolor=budget_color,
                        border_radius=2,
                    ),
                    visible=c.budget > 0,
                ),
                ft.Text(
                    f"{budget_pct:.0f}% terpakai",
                    size=10, color=Colors.TEXT_MUTED,
                    visible=c.budget > 0,
                ),
            ])),
            # Status
            ft.DataCell(_status_badge(c.status)),
            # Aksi
            ft.DataCell(ft.Row(spacing=0, controls=[
                *status_btns,
                action_btn(
                    ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, cp=c: _form_dialog(page, session, cp, refresh),
                    Colors.INFO,
                ),
                action_btn(
                    ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, cid=c.id, nm=c.name: confirm_dialog(
                        page, "Hapus Campaign", f"Hapus campaign '{nm}'?",
                        lambda: _delete(cid, page, refresh),
                    ),
                    Colors.ERROR,
                ),
            ])),
        ]))
    return rows


def _change_status(cid, status, page, refresh):
    with SessionLocal() as db:
        ok, msg = CampaignService.update_status(db, cid, status)
    show_snack(page, msg, ok)
    if ok:
        refresh()


def _delete(cid, page, refresh):
    with SessionLocal() as db:
        ok, msg = CampaignService.delete(db, cid)
    show_snack(page, msg, ok)
    if ok:
        refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def CampaignsPage(page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}

    with SessionLocal() as db:
        initial = CampaignService.get_all(db, session.company_id)

    COLS = [
        ft.DataColumn(ft.Text("Nama / Kode",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Channel",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Jadwal",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Budget",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Campaign",
        subtitle="Kelola kampanye marketing dan promosi",
        add_label="Tambah Campaign",
        search_hint="Cari nama atau kode campaign...",
        columns=COLS,
        initial_rows=_build_rows(initial, page, session, lambda: None),
        on_add=lambda: _form_dialog(page, session, None, refresh),
        on_search=lambda e: (
            search_val.update({"q": e.control.value or ""}), refresh()
        ),
        add_icon=ft.Icons.ADD_CHART,
    )

    def refresh():
        with SessionLocal() as db:
            data = CampaignService.get_all(db, session.company_id, search_val["q"])
        set_rows(_build_rows(data, page, session, refresh))

    set_rows(_build_rows(initial, page, session, refresh))
    return ctrl
