"""
app/pages/master/companies.py
Master Data → Perusahaan (dengan upload logo)
Flet v0.25+ pattern: FilePicker dibuat inline, pick_files di-await langsung
"""
from __future__ import annotations
import os
import shutil
import flet as ft
from typing import Optional

from app.database import SessionLocal
from app.models import Company
from app.services.master_service import CompanyService
from app.services.auth import AppSession
from app.pages.master._base import MasterPage
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack,
)
from app.utils.theme import Colors, Sizes

_CURRENCY_OPTS = [
    ("IDR", "IDR - Rupiah"),
    ("USD", "USD - Dollar AS"),
    ("SGD", "SGD - Dollar Singapura"),
    ("MYR", "MYR - Ringgit"),
]

_LOGO_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "logos")
)


def _ensure_logo_dir():
    os.makedirs(_LOGO_DIR, exist_ok=True)


def _save_logo_file(src_path: str, company_code: str) -> str:
    _ensure_logo_dir()
    ext      = os.path.splitext(src_path)[1].lower()
    filename = f"{company_code.upper()}{ext}"
    dst_path = os.path.join(_LOGO_DIR, filename)
    shutil.copy2(src_path, dst_path)
    return dst_path


# ─────────────────────────────────────────────────────────────
# LOGO WIDGET
# ─────────────────────────────────────────────────────────────
def _build_logo_widget(page: ft.Page, initial_path: str,
                       company_code_fn) -> tuple:
    """
    Return (container, get_logo_path_fn)
    Tombol pilih gambar menggunakan async pick_files() langsung —
    tidak perlu page.overlay, tidak perlu run_task.
    """
    logo_path = {"value": initial_path or ""}

    logo_image = ft.Image(
        src=logo_path["value"] if logo_path["value"] else "",
        width=96, height=96,
        fit="contain",
        border_radius=8,
        visible=bool(logo_path["value"]),
    )

    logo_placeholder = ft.Container(
        width=96, height=96,
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.06, Colors.TEXT_PRIMARY),
        border=ft.Border.all(2, Colors.BORDER),
        alignment=ft.Alignment(0, 0),
        visible=not bool(logo_path["value"]),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4,
            controls=[
                ft.Icon(ft.Icons.IMAGE_OUTLINED, size=28, color=Colors.TEXT_MUTED),
                ft.Text("No Logo", size=10, color=Colors.TEXT_MUTED),
            ],
        ),
    )

    path_label = ft.Text(
        os.path.basename(logo_path["value"]) if logo_path["value"] else "Belum ada logo",
        size=11, color=Colors.TEXT_MUTED,
        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        width=200,
    )

    def _update_preview(path: str):
        logo_path["value"] = path
        if path:
            logo_image.src           = path
            logo_image.visible       = True
            logo_placeholder.visible = False
            path_label.value         = os.path.basename(path)
            path_label.color         = Colors.TEXT_SECONDARY
        else:
            logo_image.visible       = False
            logo_placeholder.visible = True
            path_label.value         = "Belum ada logo"
            path_label.color         = Colors.TEXT_MUTED
        try:
            logo_image.update()
            logo_placeholder.update()
            path_label.update()
        except Exception:
            pass

    # ── Async handler — Flet v0.25+ pattern ─────────────────
    async def handle_pick(e):
        # Buat FilePicker baru inline, await langsung
        files = await ft.FilePicker().pick_files(
            dialog_title="Pilih Logo Perusahaan",
            allowed_extensions=["png", "jpg", "jpeg", "gif", "webp", "bmp"],
            file_type=ft.FilePickerFileType.CUSTOM,
            allow_multiple=False,
        )
        if not files:
            return  # dibatalkan user

        src = files[0].path
        if not src:
            show_snack(page, "Path file tidak tersedia (mode web?).", False)
            return

        # Validasi ekstensi
        ext = os.path.splitext(src)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            show_snack(page, "Format tidak didukung. Gunakan PNG/JPG/GIF/WEBP.", False)
            return

        # Validasi ukuran maks 2MB
        if os.path.getsize(src) / (1024 * 1024) > 2:
            show_snack(page, "File terlalu besar. Maks 2 MB.", False)
            return

        code = company_code_fn() or "TEMP"
        try:
            saved = _save_logo_file(src, code)
            _update_preview(saved)
        except Exception as ex:
            show_snack(page, f"Gagal menyimpan logo: {ex}", False)

    btn_pick = ft.Button(
        content=ft.Row(tight=True, spacing=6, controls=[
            ft.Icon(ft.Icons.UPLOAD_FILE, size=14, color=Colors.TEXT_ON_ACCENT),
            ft.Text("Pilih Gambar", size=12, color=Colors.TEXT_ON_ACCENT),
        ]),
        bgcolor=Colors.ACCENT,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
            elevation=0,
        ),
        on_click=lambda e: page.run_task(handle_pick, e),
    )

    btn_remove = ft.Button(
        "Hapus Logo",
        style=ft.ButtonStyle(color=Colors.ERROR),
        on_click=lambda e: _update_preview(""),
    )

    container = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.03, Colors.TEXT_PRIMARY),
        border_radius=Sizes.BTN_RADIUS,
        border=ft.Border.all(1, Colors.BORDER),
        padding=ft.Padding.all(16),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Text("Logo Perusahaan", size=12,
                        color=Colors.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600),
                ft.Row(
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Stack(controls=[logo_placeholder, logo_image]),
                        ft.Column(
                            spacing=8, tight=True,
                            controls=[
                                path_label,
                                ft.Text("PNG, JPG, GIF, WEBP · Maks 2 MB",
                                        size=10, color=Colors.TEXT_MUTED),
                                ft.Row(spacing=8, controls=[btn_pick, btn_remove]),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    )

    return container, lambda: logo_path["value"]


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 company: Optional[Company], on_saved):
    is_edit = company is not None
    c = company

    f_code     = make_field("Kode *",
                            c.code if is_edit else "",
                            hint="Contoh: PT-ABC",
                            read_only=is_edit, width=140)
    f_name     = make_field("Nama Perusahaan *", c.name if is_edit else "")
    f_legal    = make_field("Nama Legal / PT",   c.legal_name or "" if is_edit else "")
    f_tax      = make_field("NPWP",              c.tax_id or "" if is_edit else "", width=200)
    f_phone    = make_field("Telepon",           c.phone or "" if is_edit else "", width=200)
    f_email    = make_field("Email",             c.email or "" if is_edit else "",
                            keyboard_type=ft.KeyboardType.EMAIL)
    f_city     = make_field("Kota",              c.city or "" if is_edit else "", width=180)
    f_province = make_field("Provinsi",          c.province or "" if is_edit else "", width=180)
    f_address  = make_field("Alamat Lengkap",    c.address or "" if is_edit else "",
                            multiline=True, min_lines=2, max_lines=4)
    f_currency = make_dropdown("Mata Uang", _CURRENCY_OPTS,
                               c.currency_code if is_edit else "IDR", width=200)
    f_active   = ft.Switch(
        label="Perusahaan Aktif",
        value=c.is_active if is_edit else True,
        active_color=Colors.ACCENT,
    )

    logo_widget, get_logo_path = _build_logo_widget(
        page,
        initial_path=c.logo_url if is_edit else "",
        company_code_fn=lambda: f_code.value,
    )

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_name.value.strip():
            show_err("Nama perusahaan wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode perusahaan wajib diisi."); return

        data = {
            "code":          f_code.value,
            "name":          f_name.value,
            "legal_name":    f_legal.value,
            "tax_id":        f_tax.value,
            "phone":         f_phone.value,
            "email":         f_email.value,
            "city":          f_city.value,
            "province":      f_province.value,
            "address":       f_address.value,
            "logo_url":      get_logo_path(),
            "currency_code": f_currency.value,
            "is_active":     f_active.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = CompanyService.update(db, c.id, data)
            else:
                ok, msg, _ = CompanyService.create(db, data)

        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.BUSINESS, color=Colors.ACCENT, size=20),
                    ft.Text("Edit Perusahaan" if is_edit else "Tambah Perusahaan",
                            color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=ft.Container(
            width=560, height=580,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO, spacing=14,
                controls=[
                    err,
                    logo_widget,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 4}, content=f_code),
                        ft.Container(col={"xs": 12, "sm": 8}, content=f_name),
                    ]),
                    f_legal,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_tax),
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_phone),
                    ]),
                    f_email,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_city),
                        ft.Container(col={"xs": 12, "sm": 6}, content=f_province),
                    ]),
                    f_address,
                    ft.Row(spacing=16, controls=[f_currency, f_active]),
                ],
            ),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                          on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0,
                ),
                on_click=save),
        ],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# TABLE ROWS
# ─────────────────────────────────────────────────────────────
def _build_rows(companies, page, session, refresh):
    rows = []
    for c in companies:
        logo_ctrl = ft.Image(
            src=c.logo_url, width=32, height=32,
            fit="contain", border_radius=4,
        ) if c.logo_url and os.path.exists(c.logo_url) else ft.Container(
            width=32, height=32, border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.06, Colors.TEXT_PRIMARY),
            alignment=ft.Alignment(0, 0),
            content=ft.Icon(ft.Icons.BUSINESS, size=18, color=Colors.TEXT_MUTED),
        )

        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Row(spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    logo_ctrl,
                    ft.Column(spacing=1, tight=True, controls=[
                        ft.Text(c.name, size=13, weight=ft.FontWeight.W_600,
                                color=Colors.TEXT_PRIMARY),
                        ft.Text(c.legal_name or "—", size=11, color=Colors.TEXT_MUTED),
                    ]),
                ],
            )),
            ft.DataCell(ft.Text(c.code, size=12, color=Colors.TEXT_SECONDARY,
                                font_family="monospace")),
            ft.DataCell(ft.Text(c.tax_id or "—", size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(c.phone or "—", size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(c.email or "—", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(
                f"{c.city or ''} {c.province or ''}".strip() or "—",
                size=12, color=Colors.TEXT_SECONDARY,
            )),
            ft.DataCell(ft.Container(
                content=ft.Text(c.currency_code, size=11,
                                color=Colors.INFO, weight=ft.FontWeight.W_600),
                bgcolor=ft.Colors.with_opacity(0.1, Colors.INFO),
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            )),
            ft.DataCell(status_badge(c.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                           lambda e, co=c: _form_dialog(page, session, co, refresh),
                           Colors.INFO),
                action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                           lambda e, cid=c.id, nm=c.name: confirm_dialog(
                               page, "Hapus Perusahaan", f"Hapus perusahaan '{nm}'?",
                               lambda: _delete(cid, page, refresh)),
                           Colors.ERROR),
            ])),
        ]))
    return rows


def _delete(cid, page, refresh):
    with SessionLocal() as db:
        ok, msg = CompanyService.delete(db, cid)
    show_snack(page, msg, ok)
    if ok: refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def CompaniesPage(page, session: AppSession):
    search_val = {"q": ""}

    with SessionLocal() as db:
        initial = CompanyService.get_all(db, "")

    COLS = [
        ft.DataColumn(ft.Text("Logo / Nama",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kode",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("NPWP",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kontak",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Lokasi",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Mata Uang",    size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Perusahaan",
        subtitle="Kelola data perusahaan (holding dan anak perusahaan)",
        add_label="Tambah Perusahaan",
        search_hint="Cari nama atau kode perusahaan...",
        columns=COLS,
        initial_rows=_build_rows(initial, page, session, lambda: None),
        on_add=lambda: _form_dialog(page, session, None, refresh),
        on_search=lambda e: (
            search_val.update({"q": e.control.value or ""}), refresh()
        ),
        add_icon=ft.Icons.ADD_BUSINESS,
    )

    def refresh():
        with SessionLocal() as db:
            data = CompanyService.get_all(db, search_val["q"])
        set_rows(_build_rows(data, page, session, refresh))

    set_rows(_build_rows(initial, page, session, refresh))
    return ctrl
