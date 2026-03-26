"""
app/pages/master/partners.py
app/pages/master/customers.py  (digabung dalam satu file, dipisah class)
"""
from __future__ import annotations
import flet as ft
from typing import Optional

from app.database import SessionLocal
from app.models import Partner, Customer, Branch, Campaign
from app.services.master_service import PartnerService, CustomerService
from app.services.auth import AppSession
from app.pages.master._base import MasterPage
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack, section_card,
)
from app.utils.theme import Colors, Sizes

# ═══════════════════════════════════════════════════════════════
# PARTNERS
# ═══════════════════════════════════════════════════════════════
_PTYPE_OPTS = [
    ("RESELLER","Reseller"), ("AGENT","Agen"),
    ("REFERRAL","Referral"), ("DISTRIBUTOR","Distributor"),
    ("AFFILIATE","Affiliate"),
]


def _partner_form(page, session: AppSession, partner: Optional[Partner], on_saved):
    is_edit = partner is not None
    p = partner

    f = {
        "code":    make_field("Kode *", p.code if is_edit else "", read_only=is_edit, width=140),
        "name":    make_field("Nama Mitra *", p.name if is_edit else ""),
        "type":    make_dropdown("Tipe", _PTYPE_OPTS,
                                 p.partner_type if is_edit else "REFERRAL", width=180),
        "contact": make_field("Kontak Person", p.contact_person or "" if is_edit else "", width=220),
        "phone":   make_field("Telepon", p.phone or "" if is_edit else "", width=200),
        "email":   make_field("Email", p.email or "" if is_edit else "",
                              keyboard_type=ft.KeyboardType.EMAIL),
        "city":    make_field("Kota", p.city or "" if is_edit else "", width=200),
        "address": make_field("Alamat", p.address or "" if is_edit else "",
                              multiline=True, min_lines=2, max_lines=3),
        "comm":    make_field("Komisi (%)", str(p.commission_pct) if is_edit else "0",
                              keyboard_type=ft.KeyboardType.NUMBER, width=140),
        "active":  ft.Switch(label="Aktif", value=p.is_active if is_edit else True,
                             active_color=Colors.ACCENT),
    }
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def save(e):
        if not f["name"].value.strip():
            err.value = "Nama wajib diisi."; err.visible = True; err.update(); return
        if not is_edit and not f["code"].value.strip():
            err.value = "Kode wajib diisi."; err.visible = True; err.update(); return
        data = {
            "code": f["code"].value, "name": f["name"].value,
            "partner_type": f["type"].value, "contact_person": f["contact"].value,
            "phone": f["phone"].value, "email": f["email"].value,
            "city": f["city"].value, "address": f["address"].value,
            "commission_pct": f["comm"].value, "is_active": f["active"].value,
        }
        with SessionLocal() as db:
            ok, msg = (PartnerService.update(db, partner.id, data) if is_edit
                       else PartnerService.create(db, session.company_id, data)[0:2])
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Text("Edit Mitra" if is_edit else "Tambah Mitra",
                    color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700, size=16),
            ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
        ]),
        content=ft.Container(width=480, content=ft.Column(
            scroll=ft.ScrollMode.AUTO, spacing=12,
            controls=[
                err,
                ft.ResponsiveRow(spacing=12, controls=[
                    ft.Container(col={"xs":12,"sm":4}, content=f["code"]),
                    ft.Container(col={"xs":12,"sm":8}, content=f["name"]),
                ]),
                ft.ResponsiveRow(spacing=12, controls=[
                    ft.Container(col={"xs":12,"sm":6}, content=f["type"]),
                    ft.Container(col={"xs":12,"sm":6}, content=f["contact"]),
                ]),
                ft.ResponsiveRow(spacing=12, controls=[
                    ft.Container(col={"xs":12,"sm":6}, content=f["phone"]),
                    ft.Container(col={"xs":12,"sm":6}, content=f["email"]),
                ]),
                ft.ResponsiveRow(spacing=12, controls=[
                    ft.Container(col={"xs":12,"sm":6}, content=f["city"]),
                    ft.Container(col={"xs":12,"sm":6}, content=f["comm"]),
                ]),
                f["address"],
                f["active"],
            ],
        )),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


def _partner_rows(partners, page, session, refresh):
    rows = []
    for p in partners:
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(p.name, size=13, weight=ft.FontWeight.W_600, color=Colors.TEXT_PRIMARY),
                ft.Text(p.code, size=11, color=Colors.TEXT_MUTED, font_family="monospace"),
            ])),
            ft.DataCell(ft.Text(p.partner_type, size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(p.contact_person or "—", size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(p.phone or "—", size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(f"{p.commission_pct:.1f}%", size=12, color=Colors.ACCENT)),
            ft.DataCell(status_badge(p.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(ft.Icons.SWAP_HORIZ, "Pindahkan / Reassign",
                           lambda e, pid=p.id, nm=p.name:
                               _reassign_partner_dialog(page, session, pid, nm, refresh),
                           Colors.ACCENT),
                action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                           lambda e, pt=p: _partner_form(page, session, pt, refresh), Colors.INFO),
                action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                           lambda e, pid=p.id, nm=p.name: confirm_dialog(
                               page, "Hapus Mitra", f"Hapus '{nm}'?",
                               lambda: _del_partner(pid, page, refresh)), Colors.ERROR),
            ])),
        ]))
    return rows


def _del_partner(pid, page, refresh):
    with SessionLocal() as db:
        ok, msg = PartnerService.delete(db, pid)
    show_snack(page, msg, ok)
    if ok: refresh()


def PartnersPage(page, session: AppSession):
    search_val = {"q": ""}
    with SessionLocal() as db:
        initial = PartnerService.get_all(db, session.company_id)

    COLS = [
        ft.DataColumn(ft.Text("Nama / Kode", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kontak", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Telepon", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Komisi", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Mitra", subtitle="Kelola data mitra / referral pelanggan",
        add_label="Tambah Mitra", search_hint="Cari nama atau kode...",
        columns=COLS, initial_rows=_partner_rows(initial, page, session, lambda: None),
        on_add=lambda: _partner_form(page, session, None, refresh),
        on_search=lambda e: (search_val.update({"q": e.control.value or ""}), refresh()),
        add_icon=ft.Icons.HANDSHAKE,
    )

    def refresh():
        with SessionLocal() as db:
            data = PartnerService.get_all(db, session.company_id, search_val["q"])
        set_rows(_partner_rows(data, page, session, refresh))

    set_rows(_partner_rows(initial, page, session, refresh))
    return ctrl


# ═══════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════
_CTYPE_OPTS  = [("INDIVIDUAL","Perorangan"),("CORPORATE","Perusahaan")]
_SOURCE_OPTS = [
    ("DIRECT","Langsung"), 
    ("CAMPAIGN","Campaign"), ("ORGANIC","Organik"),
    ("REFERRAL","Referral"), ("OTHER","Lainnya"),
]


def _customer_form(page, session: AppSession, customer: Optional[Customer], on_saved):
    is_edit = customer is not None
    c = customer

    with SessionLocal() as db:
        branches  = db.query(Branch).filter_by(company_id=session.company_id, is_active=True).all()
        partners  = PartnerService.get_all(db, session.company_id)
        campaigns = db.query(Campaign).filter_by(company_id=session.company_id).all()
    part_opts = [("","— Tanpa Mitra —")]  + [(str(p.id), p.name) for p in partners]
    camp_opts = [("","— Tanpa Campaign —")] + [(str(cm.id), cm.name) for cm in campaigns]

    f = {
        "code":     make_field("Kode *", c.code if is_edit else "", read_only=is_edit, width=140),
        "name":     make_field("Nama *", c.name if is_edit else ""),
        "type":     make_dropdown("Tipe", _CTYPE_OPTS,
                                  c.customer_type if is_edit else "INDIVIDUAL", width=180),
        "tax_id":   make_field("NPWP", c.tax_id or "" if is_edit else "", width=200),
        "phone":    make_field("Telepon", c.phone or "" if is_edit else "", width=200),
        "email":    make_field("Email", c.email or "" if is_edit else "",
                               keyboard_type=ft.KeyboardType.EMAIL),
        "city":     make_field("Kota", c.city or "" if is_edit else "", width=180),
        "province": make_field("Provinsi", c.province or "" if is_edit else "", width=180),
        "address":  make_field("Alamat", c.address or "" if is_edit else "",
                               multiline=True, min_lines=2, max_lines=3),
        "source":   make_dropdown("Sumber Akuisisi", _SOURCE_OPTS,
                                  c.acquisition_source if is_edit else "DIRECT", width=200),
        "partner":  make_dropdown("Mitra", part_opts,
                                  str(c.partner_id) if (is_edit and c.partner_id) else "", disabled=True),
        "campaign": make_dropdown("Campaign", camp_opts,
                                  str(c.campaign_id) if (is_edit and c.campaign_id) else "", disabled=True),
        "terms":    make_field("Termin (hari)", str(c.payment_terms_days) if is_edit else "0",
                               keyboard_type=ft.KeyboardType.NUMBER, width=140),
        "credit":   make_field("Limit Kredit", str(int(c.credit_limit)) if is_edit else "0",
                               keyboard_type=ft.KeyboardType.NUMBER, width=180),
        "active":   ft.Switch(label="Aktif", value=c.is_active if is_edit else True,
                              active_color=Colors.ACCENT),
    }
    def activate_source(source):
        if source == "REFERRAL":
            f["partner"].disabled = False
            f["campaign"].disabled = True
        elif source == "CAMPAIGN":
            f["partner"].disabled = True
            f["campaign"].disabled = False
        else:
            f["partner"].disabled = True
            f["campaign"].disabled = True

    f["source"].on_select = lambda e:activate_source(f["source"].value)
    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def save(e):
        if not f["name"].value.strip():
            err.value = "Nama wajib diisi."; err.visible = True; err.update(); return
        if not is_edit and not f["code"].value.strip():
            err.value = "Kode wajib diisi."; err.visible = True; err.update(); return
        data = {
            "code": f["code"].value, "name": f["name"].value,
            "customer_type": f["type"].value, "tax_id": f["tax_id"].value,
            "phone": f["phone"].value, "email": f["email"].value,
            "city": f["city"].value, "province": f["province"].value,
            "address": f["address"].value, "branch_id": session.branch_id,
            "acquisition_source": f["source"].value,
            "partner_id": f["partner"].value, "campaign_id": f["campaign"].value,
            "payment_terms_days": f["terms"].value, "credit_limit": f["credit"].value,
            "is_active": f["active"].value,
        }
        with SessionLocal() as db:
            ok, msg = (CustomerService.update(db, customer.id, data) if is_edit
                       else CustomerService.create(db, session.company_id, data)[0:2])
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.Text("Edit Pelanggan" if is_edit else "Tambah Pelanggan",
                    color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_700, size=16),
            ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
        ]),
        content=ft.Container(width=560, height=540, content=ft.Column(
            scroll=ft.ScrollMode.AUTO, spacing=14,
            controls=[
                err,
                section_card("Data Pelanggan", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":4}, content=f["code"]),
                        ft.Container(col={"xs":12,"sm":4}, content=f["type"]),
                        ft.Container(col={"xs":12,"sm":4}, content=f["tax_id"]),
                    ]),
                    f["name"],
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f["phone"]),
                        ft.Container(col={"xs":12,"sm":6}, content=f["email"]),
                    ]),
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f["city"]),
                        ft.Container(col={"xs":12,"sm":6}, content=f["province"]),
                    ]),
                    f["address"],
                    f["active"],
                ]),
                section_card("Akuisisi", [
                    f["source"],
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f["partner"]),
                        ft.Container(col={"xs":12,"sm":6}, content=f["campaign"]),
                    ]),
                ]),
                section_card("Kredit", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":5}, content=f["terms"]),
                        ft.Container(col={"xs":12,"sm":7}, content=f["credit"]),
                    ]),
                ]),
            ],
        )),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                          on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


_SOURCE_LABEL = {"DIRECT":"Langsung","CAMPAIGN":"Campaign",
                 "ORGANIC":"Organik","REFERRAL":"Referral","OTHER":"Lainnya"}
_SOURCE_COLOR = {"DIRECT": Colors.TEXT_MUTED,
                 "CAMPAIGN": Colors.INFO, "ORGANIC": Colors.SUCCESS,
                 "REFERRAL": Colors.WARNING, "OTHER": Colors.TEXT_MUTED}


def _source_badge(src):
    color = _SOURCE_COLOR.get(src, Colors.TEXT_MUTED)
    return ft.Container(
        content=ft.Text(_SOURCE_LABEL.get(src, src), size=11, color=color),
        bgcolor=ft.Colors.with_opacity(0.1, color),
        border_radius=4,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _customer_rows(customers, page, session, refresh):
    rows = []
    for c in customers:
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(c.name, size=13, weight=ft.FontWeight.W_600, color=Colors.TEXT_PRIMARY),
                ft.Text(c.code, size=11, color=Colors.TEXT_MUTED, font_family="monospace"),
            ])),
            ft.DataCell(ft.Text(c.customer_type, size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(c.phone or "—", size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(c.email or "—", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(c.city or "—", size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(c.branch.name if c.branch else "—", size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(_source_badge(c.acquisition_source)),
            ft.DataCell(ft.Text(
                f"Rp {c.credit_limit:,.0f}" if c.credit_limit else "—",
                size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(status_badge(c.is_active)),
            ft.DataCell(ft.Row(spacing=0, controls=[
                action_btn(ft.Icons.SWAP_HORIZ, "Pindahkan / Reassign",
                           lambda e, cid=c.id, nm=c.name:
                               _reassign_customer_dialog(page, session, cid, nm, refresh),
                           Colors.ACCENT),
                action_btn(ft.Icons.EDIT_OUTLINED, "Edit",
                           lambda e, cu=c: _customer_form(page, session, cu, refresh), Colors.INFO),
                action_btn(ft.Icons.DELETE_OUTLINE, "Hapus",
                           lambda e, cid=c.id, nm=c.name: confirm_dialog(
                               page, "Hapus Pelanggan", f"Hapus '{nm}'?",
                               lambda: _del_customer(cid, page, refresh)), Colors.ERROR),
            ])),
        ]))
    return rows


def _del_customer(cid, page, refresh):
    with SessionLocal() as db:
        ok, msg = CustomerService.delete(db, cid)
    show_snack(page, msg, ok)
    if ok: refresh()


def CustomersPage(page, session: AppSession):
    search_val = {"q": ""}
    with SessionLocal() as db:
        initial = CustomerService.get_all(db, session.company_id)

    COLS = [
        ft.DataColumn(ft.Text("Nama / Kode",  size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tipe",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kontak",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Kota / Cabang",size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Sumber",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Limit Kredit", size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    ctrl, set_rows = MasterPage(
        title="Pelanggan", subtitle="Kelola data pelanggan",
        add_label="Tambah Pelanggan", search_hint="Cari nama, kode, telepon...",
        columns=COLS, initial_rows=_customer_rows(initial, page, session, lambda: None),
        on_add=lambda: _customer_form(page, session, None, refresh),
        on_search=lambda e: (search_val.update({"q": e.control.value or ""}), refresh()),
        add_icon=ft.Icons.PERSON_ADD,
    )

    def refresh():
        with SessionLocal() as db:
            data = CustomerService.get_all(db, session.company_id, search_val["q"])
        set_rows(_customer_rows(data, page, session, refresh))

    set_rows(_customer_rows(initial, page, session, refresh))
    return ctrl


# ═══════════════════════════════════════════════════════════════
# REASSIGN DIALOG — Pelanggan & Mitra
# ═══════════════════════════════════════════════════════════════

def _reassign_partner_dialog(page, session: AppSession,
                              partner_id: int, partner_name: str, on_saved):
    """Dialog pindah alamat mitra + history."""
    from app.models import Partner, PartnerAssignmentHistory

    with SessionLocal() as db:
        p = db.query(Partner).filter_by(id=partner_id).first()
        if not p:
            show_snack(page, "Mitra tidak ditemukan.", False); return
        cur_city    = p.city or ""
        cur_address = p.address or ""
        cur_contact = p.contact_person or ""
        cur_phone   = p.phone or ""
        cur_email   = p.email or ""

    def _load_history():
        with SessionLocal() as db:
            rows = db.query(PartnerAssignmentHistory)                     .filter_by(partner_id=partner_id)                     .order_by(PartnerAssignmentHistory.changed_at.desc())                     .limit(20).all()
            return [{
                "change_type": r.change_type,
                "old_value":   r.old_value or "—",
                "new_value":   r.new_value or "—",
                "notes":       r.notes or "",
                "changed_by":  r.changed_by_user.full_name if r.changed_by_user else "System",
                "changed_at":  r.changed_at.strftime("%Y-%m-%d %H:%M") if r.changed_at else "",
            } for r in rows]

    f_city    = make_field("Kota Baru", cur_city, width=200)
    f_address = make_field("Alamat Baru", cur_address,
                           multiline=True, min_lines=2, max_lines=3)
    f_contact = make_field("Kontak Person", cur_contact, width=220)
    f_phone   = make_field("Telepon", cur_phone, width=200)
    f_email   = make_field("Email", cur_email,
                           keyboard_type=ft.KeyboardType.EMAIL)
    f_notes   = make_field("Alasan / Catatan", "",
                           multiline=True, min_lines=2, max_lines=3)
    err       = ft.Text("", color=Colors.ERROR, size=12, visible=False)
    dlg_ref   = {"dlg": None}

    hist_col  = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)

    def _rebuild_history():
        rows = _load_history()
        _TYPE_COLOR = {"ADDRESS": Colors.WARNING, "OTHER": Colors.TEXT_MUTED}
        if not rows:
            hist_col.controls = [ft.Container(
                padding=ft.Padding.all(20), alignment=ft.Alignment(0,0),
                content=ft.Text("Belum ada history.", size=13, color=Colors.TEXT_MUTED),
            )]
        else:
            hist_col.controls = [
                ft.Container(
                    border=ft.Border.all(1, Colors.BORDER), border_radius=6,
                    padding=ft.Padding.all(12),
                    content=ft.Row(spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Container(
                                content=ft.Text(r["change_type"], size=11,
                                    color=_TYPE_COLOR.get(r["change_type"], Colors.TEXT_MUTED),
                                    weight=ft.FontWeight.W_600),
                                bgcolor=ft.Colors.with_opacity(0.1,
                                    _TYPE_COLOR.get(r["change_type"], Colors.TEXT_MUTED)),
                                border_radius=4,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            ),
                            ft.Column(spacing=2, expand=True, controls=[
                                ft.Row(spacing=8, controls=[
                                    ft.Text(r["old_value"], size=12, color=Colors.ERROR),
                                    ft.Icon(ft.Icons.ARROW_FORWARD, size=14, color=Colors.TEXT_MUTED),
                                    ft.Text(r["new_value"], size=12, color=Colors.SUCCESS,
                                            weight=ft.FontWeight.W_600),
                                ]),
                                ft.Text(r["notes"], size=11, color=Colors.TEXT_MUTED,
                                        visible=bool(r["notes"]), italic=True),
                            ]),
                            ft.Column(spacing=1, controls=[
                                ft.Text(r["changed_at"], size=11, color=Colors.TEXT_MUTED),
                                ft.Text(r["changed_by"], size=11, color=Colors.TEXT_MUTED),
                            ]),
                        ],
                    ),
                ) for r in rows
            ]
        try:
            if dlg_ref["dlg"]: dlg_ref["dlg"].update()
        except: pass

    _rebuild_history()

    tab_state   = {"active": "edit"}
    tab_content = ft.Container()

    def _show_tab(name):
        tab_state["active"] = name
        if name == "edit":
            tab_content.content = ft.Column(spacing=12, controls=[
                err,
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=6, padding=ft.Padding.all(10),
                    content=ft.Column(spacing=2, controls=[
                        ft.Text("Data Saat Ini", size=11, color=Colors.TEXT_MUTED,
                                weight=ft.FontWeight.W_600),
                        ft.Row(spacing=16, wrap=True, controls=[
                            ft.Text(f"Kota: {cur_city or '—'}", size=12, color=Colors.TEXT_SECONDARY),
                            ft.Text(f"Kontak: {cur_contact or '—'}", size=12, color=Colors.TEXT_SECONDARY),
                        ]),
                    ]),
                ),
                section_card("Perbarui Kontak", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_contact),
                        ft.Container(col={"xs":12,"sm":6}, content=f_phone),
                    ]),
                    f_email,
                ]),
                section_card("Perbarui Alamat", [
                    f_city, f_address,
                ]),
                f_notes,
            ])
        else:
            _rebuild_history()
            tab_content.content = ft.Container(height=360, content=hist_col)
        try:
            if dlg_ref["dlg"]: dlg_ref["dlg"].update()
        except: pass

    _show_tab("edit")

    def save(e):
        changed = False
        histories = []
        with SessionLocal() as db:
            p = db.query(Partner).filter_by(id=partner_id).first()
            if not p: return
            notes_val = f_notes.value.strip()

            new_city = f_city.value.strip()
            new_addr = f_address.value.strip()
            if new_city != (p.city or "") or new_addr != (p.address or ""):
                old_loc = p.city or "—"
                new_loc = new_city or "—"
                histories.append(PartnerAssignmentHistory(
                    partner_id=partner_id, change_type="ADDRESS",
                    old_value=old_loc, new_value=new_loc,
                    notes=notes_val, changed_by=session.user_id,
                ))
                p.city    = new_city or None
                p.address = new_addr or None
                changed   = True

            new_contact = f_contact.value.strip()
            new_phone   = f_phone.value.strip()
            new_email   = f_email.value.strip()
            if (new_contact != (p.contact_person or "") or
                new_phone   != (p.phone or "") or
                new_email   != (p.email or "")):
                old_c = p.contact_person or "—"
                histories.append(PartnerAssignmentHistory(
                    partner_id=partner_id, change_type="OTHER",
                    old_value=old_c, new_value=new_contact or "—",
                    notes=notes_val or "Update kontak",
                    changed_by=session.user_id,
                ))
                p.contact_person = new_contact or None
                p.phone          = new_phone   or None
                p.email          = new_email   or None
                changed = True

            if not changed:
                show_snack(page, "Tidak ada perubahan.", False); return
            for h in histories: db.add(h)
            db.commit()

        dlg.open = False; page.update()
        show_snack(page, f"{partner_name} berhasil diperbarui. {len(histories)} perubahan dicatat.", True)
        on_saved()

    def _tab_btn(label, name, icon):
        is_act = tab_state["active"] == name
        return ft.Container(
            height=36, padding=ft.Padding.symmetric(horizontal=14),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.1, Colors.ACCENT) if is_act else ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, Colors.ACCENT if is_act else Colors.BORDER),
            ink=True, on_click=lambda e, n=name: _show_tab(n),
            content=ft.Row(tight=True, spacing=6, controls=[
                ft.Icon(icon, size=14,
                        color=Colors.ACCENT if is_act else Colors.TEXT_MUTED),
                ft.Text(label, size=12,
                        color=Colors.ACCENT if is_act else Colors.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600 if is_act else ft.FontWeight.W_400),
            ]),
        )

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=4, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.HANDSHAKE, color=Colors.ACCENT, size=18),
                        ft.Text(partner_name, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                    ]),
                    ft.Row(spacing=6, controls=[
                        _tab_btn("Perbarui Data", "edit",    ft.Icons.EDIT_OUTLINED),
                        _tab_btn("History",       "history", ft.Icons.HISTORY),
                    ]),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(width=560, height=440,
                             content=ft.Column(scroll=ft.ScrollMode.AUTO,
                                               controls=[tab_content])),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Tutup", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Simpan", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg)
    dlg_ref["dlg"] = dlg
    dlg.open = True
    page.update()


def _reassign_customer_dialog(page, session: AppSession,
                               customer_id: int, customer_name: str, on_saved):
    """Dialog untuk pindah cabang, sales PIC, atau alamat pelanggan."""
    from app.models import (
        Customer, CustomerAssignmentHistory, Branch, User
    )

    with SessionLocal() as db:
        c = db.query(Customer).filter_by(id=customer_id).first()
        if not c:
            show_snack(page, "Pelanggan tidak ditemukan.", False); return

        branches = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        sales_users = db.query(User).filter_by(
            company_id=session.company_id, is_active=True).order_by(User.full_name).all()

        # Current values
        cur_branch_id   = c.branch_id
        cur_sales_id    = c.sales_user_id
        cur_city        = c.city or ""
        cur_province    = c.province or ""
        cur_address     = c.address or ""

        br_opts = [("", "— Tidak Ada —")] + [(str(b.id), b.name) for b in branches]
        sales_opts = [("", "— Tidak Ada —")] + [
            (str(u.id), u.full_name) for u in sales_users
        ]
        cur_branch_name = next((b.name for b in branches if b.id == cur_branch_id), "—")
        cur_sales_name  = next((u.full_name for u in sales_users if u.id == cur_sales_id), "—")

    # Load history dalam session terpisah
    def _load_history():
        with SessionLocal() as db:
            rows = db.query(CustomerAssignmentHistory)\
                     .filter_by(customer_id=customer_id)\
                     .order_by(CustomerAssignmentHistory.changed_at.desc())\
                     .limit(20).all()
            return [{
                "change_type": r.change_type,
                "old_value":   r.old_value or "—",
                "new_value":   r.new_value or "—",
                "notes":       r.notes or "",
                "changed_by":  r.changed_by_user.full_name if r.changed_by_user else "System",
                "changed_at":  r.changed_at.strftime("%Y-%m-%d %H:%M") if r.changed_at else "",
            } for r in rows]

    # ── Tab Reassign ──
    f_branch   = make_dropdown("Cabang Baru", br_opts,
                               str(cur_branch_id) if cur_branch_id else "")
    f_sales    = make_dropdown("Sales PIC Baru", sales_opts,
                               str(cur_sales_id) if cur_sales_id else "")
    f_city     = make_field("Kota Baru", cur_city, width=200)
    f_province = make_field("Provinsi Baru", cur_province, width=200)
    f_address  = make_field("Alamat Baru", cur_address,
                            multiline=True, min_lines=2, max_lines=3)
    f_notes    = make_field("Alasan / Catatan Perpindahan", "",
                            multiline=True, min_lines=2, max_lines=3)

    err = ft.Text("", color=Colors.ERROR, size=12, visible=False)
    dlg_ref = {"dlg": None}

    # ── Tab History ──
    hist_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)

    def _rebuild_history():
        rows = _load_history()
        _TYPE_LABEL = {"BRANCH": "Pindah Cabang", "SALES": "Ganti Sales",
                       "ADDRESS": "Pindah Alamat", "OTHER": "Lainnya"}
        _TYPE_COLOR = {"BRANCH": Colors.ACCENT, "SALES": Colors.INFO,
                       "ADDRESS": Colors.WARNING, "OTHER": Colors.TEXT_MUTED}

        if not rows:
            hist_col.controls = [ft.Container(
                padding=ft.Padding.all(20),
                alignment=ft.Alignment(0, 0),
                content=ft.Text("Belum ada history perpindahan.", size=13,
                                color=Colors.TEXT_MUTED),
            )]
        else:
            hist_col.controls = [
                ft.Container(
                    border=ft.Border.all(1, Colors.BORDER), border_radius=6,
                    padding=ft.Padding.all(12),
                    content=ft.Row(spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Container(
                                content=ft.Container(
                                    content=ft.Text(
                                        _TYPE_LABEL.get(r["change_type"], r["change_type"]),
                                        size=11, color=_TYPE_COLOR.get(r["change_type"], Colors.TEXT_MUTED),
                                        weight=ft.FontWeight.W_600,
                                    ),
                                    bgcolor=ft.Colors.with_opacity(
                                        0.12, _TYPE_COLOR.get(r["change_type"], Colors.TEXT_MUTED)),
                                    border_radius=4,
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                ),
                            ),
                            ft.Column(spacing=2, expand=True, controls=[
                                ft.Row(spacing=8, controls=[
                                    ft.Text(r["old_value"], size=12, color=Colors.ERROR,
                                            weight=ft.FontWeight.W_500),
                                    ft.Icon(ft.Icons.ARROW_FORWARD, size=14,
                                            color=Colors.TEXT_MUTED),
                                    ft.Text(r["new_value"], size=12, color=Colors.SUCCESS,
                                            weight=ft.FontWeight.W_600),
                                ]),
                                ft.Text(r["notes"], size=11, color=Colors.TEXT_MUTED,
                                        visible=bool(r["notes"]), italic=True),
                            ]),
                            ft.Column(spacing=1, controls=[
                                ft.Text(r["changed_at"], size=11, color=Colors.TEXT_MUTED),
                                ft.Text(r["changed_by"], size=11, color=Colors.TEXT_MUTED),
                            ]),
                        ],
                    ),
                )
                for r in rows
            ]
        try:
            if dlg_ref["dlg"]: dlg_ref["dlg"].update()
        except: pass

    _rebuild_history()

    def save(e):
        changed = False
        histories = []

        with SessionLocal() as db:
            c = db.query(Customer).filter_by(id=customer_id).first()
            if not c:
                show_snack(page, "Pelanggan tidak ditemukan.", False); return

            notes_val = f_notes.value.strip()

            # Cek perubahan cabang
            new_br = int(f_branch.value) if f_branch.value else None
            if new_br != c.branch_id:
                old_name = cur_branch_name
                new_name = next((b.name for b in db.query(Branch).filter_by(id=new_br).all()),
                                "—") if new_br else "—"
                histories.append(CustomerAssignmentHistory(
                    customer_id=customer_id, change_type="BRANCH",
                    old_value=old_name, new_value=new_name,
                    notes=notes_val, changed_by=session.user_id,
                ))
                c.branch_id = new_br
                changed = True

            # Cek perubahan sales
            new_sales = int(f_sales.value) if f_sales.value else None
            if new_sales != c.sales_user_id:
                old_s = cur_sales_name
                new_s = next((u.full_name for u in db.query(User).filter_by(id=new_sales).all()),
                             "—") if new_sales else "—"
                histories.append(CustomerAssignmentHistory(
                    customer_id=customer_id, change_type="SALES",
                    old_value=old_s, new_value=new_s,
                    notes=notes_val, changed_by=session.user_id,
                ))
                c.sales_user_id = new_sales
                changed = True

            # Cek perubahan alamat
            new_city = f_city.value.strip()
            new_prov = f_province.value.strip()
            new_addr = f_address.value.strip()
            if new_city != (c.city or "") or new_prov != (c.province or "") \
               or new_addr != (c.address or ""):
                old_loc = f"{c.city or ''}, {c.province or ''}".strip(", ")
                new_loc = f"{new_city}, {new_prov}".strip(", ")
                histories.append(CustomerAssignmentHistory(
                    customer_id=customer_id, change_type="ADDRESS",
                    old_value=old_loc or "—", new_value=new_loc or "—",
                    notes=notes_val, changed_by=session.user_id,
                ))
                c.city     = new_city or None
                c.province = new_prov or None
                c.address  = new_addr or None
                changed = True

            if not changed:
                show_snack(page, "Tidak ada perubahan yang disimpan.", False); return

            for h in histories:
                db.add(h)
            db.commit()

        dlg.open = False; page.update()
        show_snack(page, f"Data {customer_name} berhasil diperbarui. {len(histories)} perubahan dicatat.", True)
        on_saved()

    # ── Tab container ──
    tab_state   = {"active": "reassign"}
    tab_content = ft.Container()

    def _show_tab(name):
        tab_state["active"] = name
        if name == "reassign":
            tab_content.content = ft.Column(spacing=12, controls=[
                err,
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=6, padding=ft.Padding.all(10),
                    content=ft.Column(spacing=2, controls=[
                        ft.Text("Data Saat Ini", size=11, color=Colors.TEXT_MUTED,
                                weight=ft.FontWeight.W_600),
                        ft.Row(spacing=16, wrap=True, controls=[
                            ft.Text(f"Cabang: {cur_branch_name}", size=12,
                                    color=Colors.TEXT_SECONDARY),
                            ft.Text(f"Sales: {cur_sales_name}", size=12,
                                    color=Colors.TEXT_SECONDARY),
                            ft.Text(f"Kota: {cur_city or '—'}", size=12,
                                    color=Colors.TEXT_SECONDARY),
                        ]),
                    ]),
                ),
                section_card("Pindah Cabang / Ganti Sales", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":6}, content=f_branch),
                        ft.Container(col={"xs":12,"sm":6}, content=f_sales),
                    ]),
                ]),
                section_card("Perbarui Alamat", [
                    ft.ResponsiveRow(spacing=12, controls=[
                        ft.Container(col={"xs":12,"sm":5}, content=f_city),
                        ft.Container(col={"xs":12,"sm":5}, content=f_province),
                    ]),
                    f_address,
                ]),
                f_notes,
            ])
        else:
            _rebuild_history()
            tab_content.content = ft.Container(
                height=360,
                content=hist_col,
            )
        try:
            if dlg_ref["dlg"]: dlg_ref["dlg"].update()
        except: pass

    _show_tab("reassign")

    def _tab_btn(label, name, icon):
        is_act = tab_state["active"] == name
        return ft.Container(
            height=36, padding=ft.Padding.symmetric(horizontal=14),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.1, Colors.ACCENT) if is_act
                    else ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, Colors.ACCENT if is_act else Colors.BORDER),
            ink=True,
            on_click=lambda e, n=name: _show_tab(n),
            content=ft.Row(tight=True, spacing=6, controls=[
                ft.Icon(icon, size=14,
                        color=Colors.ACCENT if is_act else Colors.TEXT_MUTED),
                ft.Text(label, size=12,
                        color=Colors.ACCENT if is_act else Colors.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600 if is_act else ft.FontWeight.W_400),
            ]),
        )

    tab_bar = ft.Row(spacing=6, controls=[
        _tab_btn("Pindahkan / Perbarui", "reassign", ft.Icons.SWAP_HORIZ),
        _tab_btn("History Perpindahan",  "history",  ft.Icons.HISTORY),
    ])

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=4, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.SWAP_HORIZ, color=Colors.ACCENT, size=18),
                        ft.Text(customer_name, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                    ]),
                    tab_bar,
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY,
                              icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(width=620, height=460,
                             content=ft.Column(scroll=ft.ScrollMode.AUTO,
                                               controls=[tab_content])),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Tutup", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Simpan Perubahan", bgcolor=Colors.ACCENT,
                color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg)
    dlg_ref["dlg"] = dlg
    dlg.open = True
    page.update()
