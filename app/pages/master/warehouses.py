"""
app/pages/master/warehouses.py
Master Data → Gudang — CRUD per cabang
"""
from __future__ import annotations
import flet as ft
from typing import Optional, List, Dict

from app.database import SessionLocal
from app.models import Branch, Warehouse
from app.services.master_service import WarehouseService
from app.services.auth import AppSession
from app.pages.master._base import MasterPage
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack,
)
from app.utils.theme import Colors, Sizes


# ─────────────────────────────────────────────────────────────
# FORM DIALOG
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession,
                 wh_id: Optional[int], on_saved):
    is_edit = wh_id is not None

    with SessionLocal() as db:
        branches = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True
        ).order_by(Branch.name).all()
        br_list = [(str(b.id), f"{b.name} ({b.branch_type})") for b in branches]

        # Nilai default
        d_branch  = str(session.branch_id) if hasattr(session, "branch_id") \
                    and session.branch_id else ""
        d_code    = ""
        d_name    = ""
        d_address = ""
        d_active  = True

        if is_edit:
            wh = WarehouseService.get_by_id(db, wh_id)
            if wh:
                d_branch  = str(wh.branch_id)
                d_code    = wh.code
                d_name    = wh.name
                d_address = wh.address or ""
                d_active  = wh.is_active

    f_branch  = make_dropdown("Cabang *", br_list, d_branch)
    f_code    = make_field("Kode *", d_code,
                           hint="Contoh: GDG-JKT",
                           read_only=is_edit, width=150)
    f_name    = make_field("Nama Gudang *", d_name)
    f_address = make_field("Alamat / Lokasi", d_address,
                           multiline=True, min_lines=2, max_lines=3)
    f_active  = ft.Switch(
        label="Gudang Aktif",
        value=d_active,
        active_color=Colors.ACCENT,
    )
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_branch.value:
            show_err("Cabang wajib dipilih."); return
        if not f_name.value.strip():
            show_err("Nama gudang wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode gudang wajib diisi."); return

        data = {
            "branch_id": f_branch.value,
            "code":      f_code.value,
            "name":      f_name.value,
            "address":   f_address.value,
            "is_active": f_active.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = WarehouseService.update(db, wh_id, data)
            else:
                ok, msg, _ = WarehouseService.create(db, data)

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
                    ft.Icon(ft.Icons.WAREHOUSE, color=Colors.ACCENT, size=20),
                    ft.Text(
                        "Edit Gudang" if is_edit else "Tambah Gudang",
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
            width=460,
            content=ft.Column(
                spacing=12, tight=True,
                controls=[
                    err,
                    f_branch,
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs": 12, "sm": 4}, content=f_code),
                        ft.Container(col={"xs": 12, "sm": 8}, content=f_name),
                    ]),
                    f_address,
                    f_active,
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
# TABLE ROWS — pakai plain dicts
# ─────────────────────────────────────────────────────────────
def _wh_to_dicts(warehouses) -> List[Dict]:
    return [{
        "id":          wh.id,
        "code":        wh.code,
        "name":        wh.name,
        "branch_name": wh.branch.name if wh.branch else "—",
        "branch_type": wh.branch.branch_type if wh.branch else "",
        "address":     wh.address or "—",
        "is_active":   wh.is_active,
    } for wh in warehouses]


_BTYPE_COLOR = {
    "HQ":        Colors.ACCENT,
    "BRANCH":    Colors.INFO,
    "WAREHOUSE": Colors.WARNING,
    "STORE":     Colors.SUCCESS,
}
_BTYPE_LABEL = {
    "HQ": "Pusat", "BRANCH": "Cabang",
    "WAREHOUSE": "Gudang", "STORE": "Toko",
}


def _build_rows(wh_data: List[Dict], page, session, refresh):
    rows = []
    for d in wh_data:
        color = _BTYPE_COLOR.get(d["branch_type"], Colors.TEXT_MUTED)
        label = _BTYPE_LABEL.get(d["branch_type"], d["branch_type"])

        rows.append(ft.DataRow(cells=[
            # Nama + Kode
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["name"], size=13, weight=ft.FontWeight.W_600,
                        color=Colors.TEXT_PRIMARY),
                ft.Text(d["code"], size=11, color=Colors.TEXT_MUTED,
                        font_family="monospace"),
            ])),
            # Cabang
            ft.DataCell(ft.Row(spacing=8, controls=[
                ft.Container(
                    content=ft.Text(label, size=11, color=color,
                                    weight=ft.FontWeight.W_500),
                    bgcolor=ft.Colors.with_opacity(0.1, color),
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                ),
                ft.Text(d["branch_name"], size=12, color=Colors.TEXT_SECONDARY),
            ])),
            # Alamat
            ft.DataCell(ft.Text(
                d["address"], size=12, color=Colors.TEXT_SECONDARY,
                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
            )),
            # Status
            ft.DataCell(status_badge(d["is_active"])),
            # Aksi
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(
                    ft.Icons.EDIT_OUTLINED, "Edit",
                    lambda e, wid=d["id"]: _form_dialog(page, session, wid, refresh),
                    Colors.INFO,
                ),
                action_btn(
                    ft.Icons.DELETE_OUTLINE, "Hapus",
                    lambda e, wid=d["id"], nm=d["name"]: confirm_dialog(
                        page, "Hapus Gudang",
                        f"Hapus gudang '{nm}'?",
                        lambda: _delete(wid, page, refresh),
                    ),
                    Colors.ERROR,
                ),
            ])),
        ]))
    return rows


def _delete(wid, page, refresh):
    with SessionLocal() as db:
        ok, msg = WarehouseService.delete(db, wid)
    show_snack(page, msg, ok)
    if ok:
        refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def WarehousesPage(page, session: AppSession) -> ft.Control:
    search_val = {"q": ""}

    def _load() -> List[Dict]:
        with SessionLocal() as db:
            whs = WarehouseService.get_all(db, session.company_id, search_val["q"])
            return _wh_to_dicts(whs)

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("Nama / Kode", size=12, weight=ft.FontWeight.W_600,
                               color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang",      size=12, weight=ft.FontWeight.W_600,
                               color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Alamat",      size=12, weight=ft.FontWeight.W_600,
                               color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",      size=12, weight=ft.FontWeight.W_600,
                               color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",        size=12, weight=ft.FontWeight.W_600,
                               color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Gudang",
        subtitle="Kelola data gudang per cabang",
        add_label="Tambah Gudang",
        search_hint="Cari nama atau kode gudang...",
        columns=COLS,
        initial_rows=_build_rows(initial, page, session, lambda: None),
        on_add=lambda: _form_dialog(page, session, None, refresh),
        on_search=lambda e: (
            search_val.update({"q": e.control.value or ""}), refresh()
        ),
        add_icon=ft.Icons.ADD_HOME_WORK,
    )

    def refresh():
        data = _load()
        set_rows(_build_rows(data, page, session, refresh))

    set_rows(_build_rows(initial, page, session, refresh))
    return ctrl
