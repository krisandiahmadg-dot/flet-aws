"""
app/pages/inventory/stock_opname.py
Inventory → Stock Opname (Hitung Fisik)
"""
from __future__ import annotations
import flet as ft
from typing import List, Dict, Optional
from datetime import date

from app.database import SessionLocal
from app.models import Branch, Warehouse
from app.services.inventory_service import StockOpnameService
from app.services.auth import AppSession
from app.components.ui import (
    make_field, make_dropdown, action_btn, page_header,
    search_bar, confirm_dialog, show_snack, empty_state, section_card,
)
from app.utils.theme import Colors, Sizes

_STATUS_OPTS = [
    ("DRAFT",       "Draft"),
    ("IN_PROGRESS", "Dalam Hitung"),
    ("COUNTED",     "Selesai Hitung"),
    ("VALIDATED",   "Divalidasi"),
    ("POSTED",      "Di-post"),
]
_STATUS_COLOR = {
    "DRAFT":       Colors.TEXT_MUTED,
    "IN_PROGRESS": Colors.WARNING,
    "COUNTED":     Colors.INFO,
    "VALIDATED":   Colors.ACCENT,
    "POSTED":      Colors.SUCCESS,
}


def _badge(status):
    color = _STATUS_COLOR.get(status, Colors.TEXT_MUTED)
    label = dict(_STATUS_OPTS).get(status, status)
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=4, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def _fmt_date(d):
    if not d: return ""
    try: return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
    except: return ""


def _parse_date(val):
    if not (val or "").strip(): return None
    from datetime import datetime
    try: return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except: return None


# ─────────────────────────────────────────────────────────────
# FORM DIALOG — buat opname baru
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session: AppSession, on_saved):
    _user_branch = getattr(session, "branch_id", None)

    with SessionLocal() as db:
        branches   = db.query(Branch).filter_by(
            company_id=session.company_id, is_active=True).order_by(Branch.name).all()
        warehouses = db.query(Warehouse)\
            .join(Branch, Warehouse.branch_id == Branch.id)\
            .filter(Branch.company_id == session.company_id,
                    Warehouse.is_active == True).all()

        # Jika user terikat cabang, filter hanya cabang tersebut
        if _user_branch:
            branches = [b for b in branches if b.id == _user_branch]

        br_opts = [(str(b.id), b.name) for b in branches]
        # Map branch_id → list warehouse options
        wh_by_branch = {}
        for w in warehouses:
            bid = str(w.branch_id)
            wh_by_branch.setdefault(bid, []).append((str(w.id), w.name))

    # Default cabang untuk user terikat cabang
    default_br = str(_user_branch) if _user_branch else ""

    f_branch = make_dropdown("Cabang *", br_opts, default_br,
                             disabled=bool(_user_branch))
    f_wh     = make_dropdown("Gudang *",
                             [("", "— Pilih cabang dulu —")], "")
    f_date   = make_field("Tanggal Opname *",
                          date.today().strftime("%Y-%m-%d"),
                          hint="YYYY-MM-DD", width=160)
    f_notes  = make_field("Catatan", "", multiline=True, min_lines=2, max_lines=3)
    err      = ft.Text("", color=Colors.ERROR, size=12, visible=False)

    def _filter_wh(branch_id: str):
        opts = wh_by_branch.get(branch_id, [])
        f_wh.options = [
            ft.dropdown.Option(key=v, text=t)
            for v, t in (opts if opts else [("", "— Tidak ada gudang —")])
        ]
        f_wh.value = opts[0][0] if len(opts) == 1 else None
        try: f_wh.update()
        except: pass

    def on_branch_select(e):
        _filter_wh(f_branch.value or "")

    f_branch.on_select = on_branch_select

    # Auto-filter gudang jika user terikat cabang
    if default_br:
        _filter_wh(default_br)

    def show_err(msg):
        err.value = msg; err.visible = True
        try: err.update()
        except: pass

    def save(e):
        if not f_branch.value:
            show_err("Cabang wajib dipilih."); return
        if not f_wh.value:
            show_err("Gudang wajib dipilih."); return
        opname_date = _parse_date(f_date.value)
        if not opname_date:
            show_err("Tanggal tidak valid."); return

        data = {
            "branch_id":    f_branch.value,
            "warehouse_id": f_wh.value,
            "opname_date":  opname_date,
            "notes":        f_notes.value,
        }
        with SessionLocal() as db:
            ok, msg = StockOpnameService.create(
                db, session.company_id, session.user_id, data)

        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.CHECKLIST, color=Colors.ACCENT, size=20),
                    ft.Text("Buat Stock Opname", color=Colors.TEXT_PRIMARY,
                            weight=ft.FontWeight.W_700, size=16),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=460,
            content=ft.Column(spacing=12, tight=True, controls=[
                ft.Text(
                    "Opname akan di-generate otomatis berdasarkan saldo stok "
                    "saat ini di gudang yang dipilih.",
                    size=12, color=Colors.TEXT_MUTED,
                ),
                err,
                f_branch, f_wh, f_date, f_notes,
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=[
            ft.Button("Batal", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                      on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ft.Button("Buat Opname", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                    elevation=0),
                on_click=save),
        ],
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


# ─────────────────────────────────────────────────────────────
# DETAIL / COUNT DIALOG
# ─────────────────────────────────────────────────────────────
def _detail_dialog(page, session: AppSession, opname_id: int, on_saved):
    with SessionLocal() as db:
        opname = StockOpnameService.get_by_id(db, opname_id)
        if not opname:
            show_snack(page, "Opname tidak ditemukan.", False); return

        op_number  = opname.opname_number
        op_status  = opname.status
        op_branch_id = opname.branch_id
        br_name    = opname.branch.name if opname.branch else "—"
        wh_name    = opname.warehouse.name if opname.warehouse else "—"
        op_date    = _fmt_date(opname.opname_date)

        lines_data = []
        for ln in (opname.lines or []):
            lines_data.append({
                "id":           ln.id,
                "product_name": ln.product.name if ln.product else "—",
                "product_code": ln.product.code if ln.product else "",
                "uom_code":     ln.product.uom.code if (ln.product and ln.product.uom) else "—",
                "lot_number":   ln.lot_number or "—",
                "qty_system":   ln.qty_system,
                "qty_physical": ln.qty_physical,
                "unit_cost":    ln.unit_cost,
            })

    # Cek akses: user hanya bisa input opname cabangnya sendiri
    _user_branch = getattr(session, "branch_id", None)
    _is_own_branch = (not _user_branch) or (_user_branch == op_branch_id)

    can_count    = op_status in ("DRAFT", "IN_PROGRESS", "COUNTED") and _is_own_branch
    can_validate = op_status == "COUNTED" and session.has_perm("INV_OPNAME", "can_approve") and _is_own_branch
    can_post     = op_status == "VALIDATED" and session.has_perm("INV_OPNAME", "can_approve") and _is_own_branch

    # Build baris — jika bisa count, tampilkan field input qty fisik
    count_fields: Dict[int, ft.TextField] = {}
    line_rows = []
    for i, ld in enumerate(lines_data):
        selisih = ld["qty_physical"] - ld["qty_system"]
        selisih_color = Colors.SUCCESS if selisih >= 0 else Colors.ERROR

        if can_count:
            f_phys = make_field(
                "", str(ld["qty_physical"]),
                keyboard_type=ft.KeyboardType.NUMBER, width=110,
            )
            count_fields[ld["id"]] = f_phys
            phys_ctrl = f_phys
        else:
            phys_ctrl = ft.Text(
                f"{ld['qty_physical']:,.2f}", size=12,
                color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.W_600,
            )

        line_rows.append(ft.Container(
            border=ft.Border.all(1, Colors.BORDER), border_radius=4,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Row(spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(width=28, content=ft.Text(str(i+1), size=12, color=Colors.TEXT_MUTED)),
                    ft.Container(expand=True, content=ft.Column(spacing=1, tight=True, controls=[
                        ft.Text(ld["product_name"], size=13, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_500),
                        ft.Text(ld["product_code"], size=11, color=Colors.TEXT_MUTED,
                                font_family="monospace"),
                    ])),
                    ft.Container(width=55, content=ft.Text(ld["uom_code"], size=12,
                                                            color=Colors.TEXT_SECONDARY)),
                    ft.Container(width=80, content=ft.Text(ld["lot_number"], size=12,
                                                            color=Colors.TEXT_MUTED)),
                    ft.Container(width=90, content=ft.Text(
                        f"{ld['qty_system']:,.2f}", size=12, color=Colors.TEXT_SECONDARY)),
                    ft.Container(width=110, content=phys_ctrl),
                    ft.Container(width=90, content=ft.Text(
                        f"{selisih:+,.2f}", size=12,
                        color=selisih_color, weight=ft.FontWeight.W_600,
                    )),
                ],
            ),
        ))

    def do_save_count(e):
        with SessionLocal() as db:
            for line_id, tf in count_fields.items():
                try:
                    qty = float(tf.value or 0)
                except ValueError:
                    qty = 0
                StockOpnameService.update_line_qty(db, line_id, qty)
            StockOpnameService.update_status(
                db, opname_id, "COUNTED", session.user_id)
        dlg.open = False; page.update()
        show_snack(page, "Hasil hitung disimpan.", True)
        on_saved()

    def do_validate(e):
        with SessionLocal() as db:
            ok, msg = StockOpnameService.update_status(
                db, opname_id, "VALIDATED", session.user_id)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    def do_post(e):
        with SessionLocal() as db:
            ok, msg = StockOpnameService.post(db, opname_id, session.user_id)
        dlg.open = False; page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    actions = [
        ft.Button("Tutup", style=ft.ButtonStyle(color=Colors.TEXT_SECONDARY),
                  on_click=lambda e: (setattr(dlg,"open",False), page.update())),
    ]
    if can_count:
        actions.append(ft.Button(
            "Simpan Hitung", bgcolor=Colors.INFO, color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
            on_click=do_save_count))
    if can_validate:
        actions.append(ft.Button(
            "Validasi", bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
            on_click=do_validate))
    if can_post:
        actions.append(ft.Button(
            "Post ke Stok", bgcolor=Colors.SUCCESS, color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=Sizes.BTN_RADIUS), elevation=0),
            on_click=do_post))

    dlg = ft.AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(spacing=4, tight=True, controls=[
                    ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.CHECKLIST, color=Colors.ACCENT, size=18),
                        ft.Text(op_number, color=Colors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_700, size=16),
                        _badge(op_status),
                    ]),
                    ft.Row(spacing=16, controls=[
                        ft.Text(f"Gudang: {br_name} / {wh_name}",
                                size=11, color=Colors.TEXT_MUTED),
                        ft.Text(f"Tgl: {op_date}", size=11, color=Colors.TEXT_MUTED),
                    ]),
                ]),
                ft.IconButton(ft.Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                              on_click=lambda e: (setattr(dlg,"open",False), page.update())),
            ],
        ),
        content=ft.Container(
            width=820, height=500,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8, controls=[
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Row(spacing=8, controls=[
                        ft.Container(width=28),
                        ft.Container(expand=True,
                            content=ft.Text("Produk", size=11, color=Colors.TEXT_MUTED,
                                            weight=ft.FontWeight.W_600)),
                        ft.Container(width=55,  content=ft.Text("Satuan",  size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=80,  content=ft.Text("Lot",     size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=90,  content=ft.Text("Sistem",  size=11, color=Colors.TEXT_MUTED)),
                        ft.Container(width=110, content=ft.Text("Fisik",   size=11, color=Colors.SUCCESS,
                                                                 weight=ft.FontWeight.W_600)),
                        ft.Container(width=90,  content=ft.Text("Selisih", size=11, color=Colors.TEXT_MUTED,
                                                                 weight=ft.FontWeight.W_600)),
                    ]),
                ),
                *line_rows,
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    content=ft.Text(
                        "Input qty fisik pada kolom 'Fisik', lalu klik 'Simpan Hitung'."
                        if can_count else
                        "Untuk mengubah qty, opname harus berstatus Draft/In Progress/Counted.",
                        size=12, color=Colors.TEXT_MUTED,
                        italic=True,
                    ),
                ),
            ]),
        ),
        actions_alignment=ft.MainAxisAlignment.END,
        actions=actions,
    )
    page.overlay.append(dlg); dlg.open = True; page.update()


# ─────────────────────────────────────────────────────────────
# TABLE + PAGE
# ─────────────────────────────────────────────────────────────
def _opnames_to_dicts(opnames) -> List[Dict]:
    return [{
        "id":        o.id,
        "number":    o.opname_number,
        "status":    o.status,
        "branch":    o.branch.name    if o.branch    else "—",
        "warehouse": o.warehouse.name if o.warehouse else "—",
        "date":      _fmt_date(o.opname_date),
        "item_count":len(o.lines or []),
    } for o in opnames]


def _build_rows(data, page, session, refresh):
    rows = []
    for d in data:
        actions = [
            action_btn(ft.Icons.VISIBILITY_OUTLINED, "Detail / Hitung",
                lambda e, oid=d["id"]: _detail_dialog(page, session, oid, refresh),
                Colors.INFO),
        ]
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text(d["number"], size=13, weight=ft.FontWeight.W_600,
                                color=Colors.TEXT_PRIMARY, font_family="monospace")),
            ft.DataCell(ft.Column(spacing=1, tight=True, controls=[
                ft.Text(d["branch"],    size=12, color=Colors.TEXT_SECONDARY),
                ft.Text(d["warehouse"], size=11, color=Colors.TEXT_MUTED),
            ])),
            ft.DataCell(ft.Text(d["date"], size=12, color=Colors.TEXT_SECONDARY)),
            ft.DataCell(ft.Text(f"{d['item_count']} item", size=12, color=Colors.TEXT_PRIMARY)),
            ft.DataCell(_badge(d["status"])),
            ft.DataCell(ft.Row(spacing=0, controls=actions)),
        ]))
    return rows


def StockOpnamePage(page, session: AppSession) -> ft.Control:
    status_val  = {"v": ""}
    filter_area = ft.Container()

    def _load():
        with SessionLocal() as db:
            ops = StockOpnameService.get_all(
                db, session.company_id, status=status_val["v"],
                branch_id=getattr(session, "branch_id", None))
            return _opnames_to_dicts(ops)

    initial = _load()

    COLS = [
        ft.DataColumn(ft.Text("No. Opname",   size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Cabang/Gudang",size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Tanggal",      size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Item",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Status",       size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        ft.DataColumn(ft.Text("Aksi",         size=12, weight=ft.FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = ft.DataTable(
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=ft.BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44, data_row_min_height=58, column_spacing=16,
        columns=COLS,
        rows=_build_rows(initial, page, session, lambda: None),
    )
    table_area = ft.Column(
        controls=[table if initial else empty_state("Belum ada stock opname.")],
        scroll=ft.ScrollMode.AUTO,
    )

    def _filter_bar():
        filters = [("","Semua")] + _STATUS_OPTS
        btns = []
        for val, label in filters:
            is_act = status_val["v"] == val
            color  = _STATUS_COLOR.get(val, Colors.TEXT_SECONDARY)
            btns.append(ft.Container(
                height=32, padding=ft.Padding.symmetric(horizontal=12),
                border_radius=Sizes.BTN_RADIUS,
                bgcolor=ft.Colors.with_opacity(0.12, color) if is_act else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, color if is_act else Colors.BORDER),
                on_click=lambda e, v=val: on_filter(v), ink=True,
                content=ft.Text(label, size=12,
                    color=color if is_act else Colors.TEXT_SECONDARY,
                    weight=ft.FontWeight.W_600 if is_act else ft.FontWeight.W_400),
            ))
        return ft.Row(spacing=6, wrap=True, controls=btns)

    filter_area.content = _filter_bar()

    def refresh():
        data = _load()
        table.rows = _build_rows(data, page, session, refresh)
        table_area.controls = [table if data else empty_state("Tidak ada opname ditemukan.")]
        filter_area.content = _filter_bar()
        try: table_area.update(); filter_area.update()
        except: pass

    def on_filter(val):
        status_val["v"] = val
        refresh()

    table.rows = _build_rows(initial, page, session, refresh)

    return ft.Container(
        expand=True, bgcolor=Colors.BG_DARK,
        padding=ft.Padding.all(24),
        content=ft.Column(expand=True, spacing=0, controls=[
            page_header(
                "Stock Opname",
                "Hitung fisik stok dan rekonsiliasi dengan sistem",
                "Buat Opname",
                on_action=lambda: _form_dialog(page, session, refresh),
                action_icon=ft.Icons.ADD,
            ),
            ft.Container(padding=ft.Padding.only(bottom=12), content=filter_area),
            ft.Container(height=12),
            ft.Container(
                expand=True,
                content=ft.ListView(expand=True, controls=[table_area]),
            ),
        ]),
    )
