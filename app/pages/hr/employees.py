"""
app/pages/hr/employees.py
Daftar Karyawan — form dialog + assignment dialog + tombol Detail
Flet v0.25+  |  Sesuai model & hr_service terbaru
"""

from flet import *
import datetime
import flet as ft
from app.services.auth import AppSession
from app.database import SessionLocal
from app.models import Employee, EmployeeAssignment, Branch, Department, Role, User, UserRole
from app.services.hr_service import EmployeeService, EmployeeAssignmentService
from app.utils.theme import Sizes, Colors
from typing import Optional, List
from app.components.ui import (
    make_field, make_dropdown, action_btn,
    status_badge, confirm_dialog, show_snack,
    page_header, search_bar, empty_state, my_date_picker
)

_STATUS_OPTS = [
    ("PERMANENT", "PERMANENT"),
    ("CONTRACT",  "CONTRACT"),
    ("INTERN",    "INTERN"),
    ("FREELANCE", "FREELANCE"),
]

_TYPE_COLOR = {
    "PERMANENT": "#3B82F6",
    "CONTRACT":  "#F59E0B",
    "INTERN":    "#8B5CF6",
    "FREELANCE": "#EC4899",
}


def _type_badge(emp_type: str) -> Container:
    color = _TYPE_COLOR.get(emp_type, Colors.TEXT_MUTED)
    return Container(
        padding=Padding.symmetric(horizontal=8, vertical=2),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border=Border.all(1, ft.Colors.with_opacity(0.3, color)),
        content=Text(emp_type, size=10, color=color, weight=FontWeight.W_600),
    )


def _divider(label: str) -> Container:
    return Container(
        margin=Margin(0, 8, 0, 4),
        content=Row(spacing=8, controls=[
            Text(label, size=10, weight=FontWeight.W_600, color=Colors.TEXT_MUTED),
            Container(expand=True, height=1, bgcolor=Colors.BORDER),
        ]),
    )

# Set Resign
def _resign_form_dialog(page, session, employee: Optional[Employee], on_saved):
    pick_date = my_date_picker(page)
    title     = "Resign Karyawan"
    f_resign    = make_field("Tanggal Resign",
                            hint="DD-MM-YYYY")
    f_resign.prefix_icon = Icons.EXIT_TO_APP_OUTLINED
    # f_resign.on_click = lambda _: pick_date(pick_date(
    #     lambda val: (setattr(f_resign, "value", val), f_resign.update())))
    def resign(e):
        with SessionLocal() as db:
            ok, msg = EmployeeService.set_resignation(db, employee.id, f_resign.value)
        page.pop_dialog()
        show_snack(page, msg, ok)
        if ok: 
            on_saved()
    
    dlg = AlertDialog(
        modal=True,
        bgcolor=Colors.BG_CARD,
        shape=RoundedRectangleBorder(radius=Sizes.CARD_RADIUS),
        title=Row(
            alignment=MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=CrossAxisAlignment.CENTER,
            controls=[
                Row(spacing=12, controls=[
                    Container(
                        width=36, height=36, border_radius=18,
                        bgcolor=ft.Colors.with_opacity(0.12, Colors.ACCENT),
                        alignment=Alignment.CENTER,
                        content=Icon(Icons.PERSON_ADD_OUTLINED,
                            size=18, color=Colors.ACCENT,
                        ),
                    ),
                    Column(spacing=2, tight=True, controls=[
                        Text(title, size=15, weight=FontWeight.W_700,
                             color=Colors.TEXT_PRIMARY),
                        Text("Resign karyawan dan catat tanggal efektif resign",
                             size=11, color=Colors.TEXT_MUTED),
                    ]),
                ]),
                IconButton(Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                           style=ButtonStyle(padding=Padding.all(4)),
                           on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=Container(
            width=480,
            padding=Padding.only(top=4),
            content=Column(
                spacing=10, tight=True,
                scroll=ScrollMode.AUTO,
                controls=[
                    f_resign,
                ],
            ),
        ),
        actions_alignment=MainAxisAlignment.SPACE_BETWEEN,
        actions=[
            Text("* Kolom wajib diisi", size=11, color=Colors.TEXT_MUTED),
            Row(spacing=8, controls=[
                Button("Batal",
                       style=ButtonStyle(color=Colors.TEXT_SECONDARY,
                                         shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS)),
                       on_click=lambda e: (setattr(dlg, "open", False), page.update())),
                Button("Simpan",
                       bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                       style=ButtonStyle(shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                                         elevation=0),
                       on_click=resign),
            ]),
        ],
    )
    page.show_dialog(dlg)



# ─────────────────────────────────────────────────────────────
# FORM DIALOG — Tambah / Edit Employee
# Sesuai create_employee: butuh username + password
# Sesuai update_employee: tidak update username/password
# ─────────────────────────────────────────────────────────────
def _form_dialog(page, session, employee: Optional[Employee], on_saved):
    pick_date = my_date_picker(page)
    is_edit   = employee is not None
    title     = "Edit Karyawan" if is_edit else "Tambah Karyawan Baru"

    f_code     = make_field("Kode *", employee.code if is_edit else "",
                            hint="EMP-001", read_only=is_edit, width=130)
    f_name     = make_field("Nama Lengkap *", employee.name if is_edit else "",
                            hint="cth. Ahmad Fauzi")
    f_type     = make_dropdown("Tipe *", _STATUS_OPTS,
                               employee.type if is_edit else "PERMANENT")
    f_address  = make_field("Alamat", employee.address if is_edit else "",
                            hint="Jl. ...", multiline=True, min_lines=2, max_lines=3)
    f_birth    = make_field("Tanggal Lahir",
                            employee.birth_date.strftime("%d-%m-%Y")
                            if (is_edit and employee.birth_date) else "",
                            hint="DD-MM-YYYY")
    f_birth.prefix_icon = Icons.CAKE_OUTLINED
    f_birth.on_click = lambda _: pick_date(
        lambda val: (setattr(f_birth, "value", val), f_birth.update()))

    f_phone    = make_field("No. Telepon", employee.phone if is_edit else "",
                            hint="+62 812-3456-7890")
    f_phone.prefix_icon  = Icons.PHONE_OUTLINED
    f_phone.input_filter = NumbersOnlyInputFilter()

    f_email    = make_field("Email", employee.email if is_edit else "",
                            hint="john@example.com")
    f_email.prefix_icon = Icons.EMAIL_OUTLINED

    f_hire     = make_field("Tanggal Masuk",
                            employee.hire_date.strftime("%d-%m-%Y")
                            if (is_edit and employee.hire_date) else "",
                            hint="DD-MM-YYYY")
    f_hire.prefix_icon = Icons.LOGIN_OUTLINED
    f_hire.on_click = lambda _: pick_date(
        lambda val: (setattr(f_hire, "value", val), f_hire.update()))

    f_active   = Switch(label="Karyawan Aktif", value=employee.is_active if is_edit else True,
                        active_color=Colors.ACCENT,)

    # ── Field khusus tambah (username + password) ─────────────
    f_username = make_field("Username *", hint="username login sistem")
    f_username.prefix_icon = Icons.PERSON_OUTLINE
    f_password = make_field("Password *", hint="min. 6 karakter", password=True)
    f_password.prefix_icon = Icons.LOCK_OUTLINE

    err_row = Container(
        visible=False,
        padding=Padding.symmetric(horizontal=12, vertical=8),
        border_radius=Sizes.BTN_RADIUS,
        bgcolor=ft.Colors.with_opacity(0.1, Colors.ERROR),
        border=Border.all(1, ft.Colors.with_opacity(0.3, Colors.ERROR)),
        content=Row(spacing=8, controls=[
            Icon(Icons.ERROR_OUTLINE, color=Colors.ERROR, size=14),
            Text("", color=Colors.ERROR, size=12, expand=True),
        ]),
    )

    def show_err(msg):
        err_row.content.controls[1].value = msg
        err_row.visible = bool(msg)
        try: err_row.update()
        except: pass

    def save(e):
        show_err("")
        if not f_name.value.strip():
            show_err("Nama lengkap wajib diisi."); return
        if not is_edit and not f_code.value.strip():
            show_err("Kode karyawan wajib diisi."); return
        if not is_edit and not f_username.value.strip():
            show_err("Username wajib diisi."); return
        if not is_edit and len((f_password.value or "").strip()) < 6:
            show_err("Password minimal 6 karakter."); return
        for tf, fname in [(f_birth, "Tanggal Lahir"), (f_hire, "Tanggal Masuk")]:
            if tf.value.strip():
                try: datetime.datetime.strptime(tf.value.strip(), "%d-%m-%Y")
                except ValueError:
                    show_err(f"Format {fname} harus DD-MM-YYYY."); return

        data = {
            "code":       f_code.value,
            "name":       f_name.value,
            "type":       f_type.value,
            "address":    f_address.value,
            "birth_date": f_birth.value or None,
            "phone":      f_phone.value,
            "email":      f_email.value,
            "hire_date":  f_hire.value or None,
            "is_active":  f_active.value,
            "username":   f_username.value,
            "password":   f_password.value,
        }
        with SessionLocal() as db:
            if is_edit:
                ok, msg = EmployeeService.update_employee(db, employee.id, data)
            else:
                ok, msg, _ = EmployeeService.create_employee(db, session.company_id, data)

        dlg.open = False
        page.update()
        show_snack(page, msg, ok)
        if ok: on_saved()

    # Controls untuk tambah mode — username & password
    account_section = [
        _divider("AKUN SISTEM"),
        ResponsiveRow(spacing=10, controls=[
            Container(col={"xs": 12, "sm": 6}, content=f_username),
            Container(col={"xs": 12, "sm": 6}, content=f_password),
        ]),
    ] if not is_edit else []

    dlg = AlertDialog(
        modal=True,
        bgcolor=Colors.BG_CARD,
        shape=RoundedRectangleBorder(radius=Sizes.CARD_RADIUS),
        title=Row(
            alignment=MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=CrossAxisAlignment.CENTER,
            controls=[
                Row(spacing=12, controls=[
                    Container(
                        width=36, height=36, border_radius=18,
                        bgcolor=ft.Colors.with_opacity(0.12, Colors.ACCENT),
                        alignment=Alignment.CENTER,
                        content=Icon(
                            Icons.BADGE_OUTLINED if is_edit else Icons.PERSON_ADD_OUTLINED,
                            size=18, color=Colors.ACCENT,
                        ),
                    ),
                    Column(spacing=2, tight=True, controls=[
                        Text(title, size=15, weight=FontWeight.W_700,
                             color=Colors.TEXT_PRIMARY),
                        Text(f"ID: {employee.code}" if is_edit else "Isi data karyawan baru",
                             size=11, color=Colors.TEXT_MUTED),
                    ]),
                ]),
                IconButton(Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                           style=ButtonStyle(padding=Padding.all(4)),
                           on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=Container(
            width=480,
            padding=Padding.only(top=4),
            content=Column(
                spacing=10, tight=True,
                scroll=ScrollMode.AUTO,
                controls=[
                    err_row,
                    _divider("IDENTITAS"),
                    ResponsiveRow(spacing=10, controls=[
                        Container(col={"xs": 12, "sm": 4}, content=f_code),
                        Container(col={"xs": 12, "sm": 8}, content=f_name),
                    ]),
                    f_type,
                    _divider("KONTAK"),
                    ResponsiveRow(spacing=10, controls=[
                        Container(col={"xs": 12, "sm": 6}, content=f_phone),
                        Container(col={"xs": 12, "sm": 6}, content=f_email),
                    ]),
                    _divider("KEPEGAWAIAN"),
                    ResponsiveRow(spacing=10, controls=[
                        Container(col={"xs": 12, "sm": 6}, content=f_birth),
                        Container(col={"xs": 12, "sm": 6}, content=f_hire),
                    ]),
                    f_address,
                    *account_section,
                    Container(
                        margin=Margin(0, 4, 0, 0),
                        padding=Padding.symmetric(horizontal=12, vertical=10),
                        border_radius=Sizes.BTN_RADIUS,
                        bgcolor=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
                        border=Border.all(1, Colors.BORDER),
                        content=f_active,
                    ),
                ],
            ),
        ),
        actions_alignment=MainAxisAlignment.SPACE_BETWEEN,
        actions=[
            Text("* Kolom wajib diisi", size=11, color=Colors.TEXT_MUTED),
            Row(spacing=8, controls=[
                Button("Batal",
                       style=ButtonStyle(color=Colors.TEXT_SECONDARY,
                                         shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS)),
                       on_click=lambda e: (setattr(dlg, "open", False), page.update())),
                Button("Simpan" if not is_edit else "Update",
                       bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                       style=ButtonStyle(shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                                         elevation=0),
                       on_click=save),
            ]),
        ],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# ASSIGNMENT DIALOG
# Sesuai EmployeeAssignmentService.assign():
#   - roles  : list of string (nama role) → disimpan di JSON
#   - role_ids: list of int → untuk update UserRole
#   - branch_id, department_id, start_date, end_date, code
# ─────────────────────────────────────────────────────────────
def _assignment_dialog(page, session, employee: Employee, on_saved):
    with SessionLocal() as db:
        branches    = db.query(Branch).filter_by(company_id=session.company_id, is_active=True).all()
        departments = db.query(Department).filter_by(company_id=session.company_id, is_active=True).all()
        roles       = db.query(Role).filter_by(company_id=session.company_id, is_active=True).all()
        # Ambil role_id yang aktif dari UserRole untuk pre-check
        user = db.query(User).filter_by(employee_id=employee.id).first()
        active_role_ids = (
            {ur.role_id for ur in db.query(UserRole).filter_by(user_id=user.id).all()}
            if user else set()
        )
    opt_branch  = [(str(b.id), f"{b.code} — {b.name}") for b in branches]
    opt_dept    = [(str(d.id), f"{d.code} — {d.name}") for d in departments]

    def _tf(label, hint="", icon=None, width=None, value=""):
        return TextField(
            label=label, hint_text=hint, prefix_icon=icon, value=value,
            bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER,
            focused_border_color=Colors.ACCENT, color=Colors.TEXT_PRIMARY,
            cursor_color=Colors.ACCENT, border_radius=Sizes.BTN_RADIUS,
            width=width, height=48, text_size=13,
        )

    def _dd(label, opts, icon=None, hint="— Pilih —"):
        return Dropdown(
            label=label, hint_text=hint,
            options=[dropdown.Option(key=v, text=t) for v, t in opts],
            bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER,
            focused_border_color=Colors.ACCENT, color=Colors.TEXT_PRIMARY,
            border_radius=Sizes.BTN_RADIUS, text_size=13,
        )

    f_code = _tf("Kode Assignment *", hint="ASG-001",
                 icon=Icons.TAG_OUTLINED, width=150,)

    dd_branch = _dd("Cabang", opt_branch, icon=Icons.STORE_OUTLINED, hint="— Pilih Cabang —")

    dd_dept = _dd("Departemen", opt_dept, icon=Icons.APARTMENT_OUTLINED, hint="— Pilih Departemen —")

    f_start = _tf("Mulai", hint="YYYY-MM-DD", icon=Icons.CALENDAR_TODAY_OUTLINED, width=175,
                  value=datetime.date.today().isoformat())
    f_end   = _tf("Berakhir", hint="kosong = selamanya",
                  icon=Icons.EVENT_OUTLINED, width=175,)

    sw_active = Switch(label="Aktif", value=True,
                       active_color=Colors.ACCENT,)

    # ── Role checkboxes — {role.id: Checkbox} ────────────────
    role_checks: dict[int, Checkbox] = {
        r.id: Checkbox(
            label=r.name,
            value=r.id in active_role_ids,
            active_color=Colors.ACCENT,
        )
        for r in roles
    }

    role_col = Column(
        spacing=4,
        controls=list(role_checks.values()),
    )

    err_row = Container(
        visible=False,
        padding=Padding.symmetric(horizontal=12, vertical=8),
        border_radius=Sizes.BTN_RADIUS,
        bgcolor=ft.Colors.with_opacity(0.1, Colors.ERROR),
        border=Border.all(1, ft.Colors.with_opacity(0.3, Colors.ERROR)),
        content=Row(spacing=8, controls=[
            Icon(Icons.ERROR_OUTLINE, color=Colors.ERROR, size=14),
            Text("", color=Colors.ERROR, size=12, expand=True),
        ]),
    )

    def show_err(msg):
        err_row.content.controls[1].value = msg
        err_row.visible = bool(msg)
        try: err_row.update()
        except: pass

    def _validate():
        if not (f_code.value or "").strip():
            return "Kode assignment wajib diisi."
        if len((f_code.value or "").strip()) > 20:
            return "Kode maksimal 20 karakter."
        for tf, fn in [(f_start, "Mulai"), (f_end, "Berakhir")]:
            v = (tf.value or "").strip()
            if v:
                try: datetime.datetime.strptime(v, "%Y-%m-%d")
                except ValueError: return f"Format '{fn}' harus YYYY-MM-DD."
        vs, ve = (f_start.value or "").strip(), (f_end.value or "").strip()
        if vs and ve and vs > ve:
            return "'Berakhir' tidak boleh lebih awal dari 'Mulai'."
        return None

    def save(e):
        show_err("")
        msg = _validate()
        if msg: show_err(msg); return

        data = {
            "code":          f_code.value.strip(),
            "branch_id":     int(dd_branch.value) if dd_branch.value else None,
            "department_id": int(dd_dept.value)   if dd_dept.value   else None,
            # roles: list of string (nama) → disimpan di JSON kolom
            "roles":         [cb.label for rid, cb in role_checks.items() if cb.value],
            # role_ids: list of int → untuk update tabel user_roles
            "role_ids":      [rid for rid, cb in role_checks.items() if cb.value],
            "start_date":    (f_start.value or "").strip() or None,
            "end_date":      (f_end.value   or "").strip() or None,
            "is_active":     sw_active.value,
        }

        try:
            with SessionLocal() as db:
                ok, rmsg = EmployeeAssignmentService.assign(db, employee.id, data)
        except Exception as ex:
            ok, rmsg = False, f"Gagal: {ex}"

        dlg.open = False
        page.update()
        show_snack(page, rmsg, ok)
        if ok and on_saved: on_saved()

    info = Container(
        padding=Padding.symmetric(horizontal=12, vertical=8),
        border_radius=Sizes.BTN_RADIUS,
        bgcolor=ft.Colors.with_opacity(0.08, Colors.INFO),
        border=Border.all(1, ft.Colors.with_opacity(0.3, Colors.INFO)),
        content=Row(spacing=8, controls=[
            Icon(Icons.INFO_OUTLINE, size=13,
                 color=Colors.INFO),
            Text("Assignment baru akan menutup assignment lama secara otomatis.",
                size=11,
                color=Colors.TEXT_SECONDARY,
                expand=True,
            ),
        ]),
    )

    dlg = AlertDialog(
        modal=True, bgcolor=Colors.BG_CARD,
        shape=RoundedRectangleBorder(radius=Sizes.CARD_RADIUS),
        title=Row(
            alignment=MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=CrossAxisAlignment.CENTER,
            controls=[
                Row(spacing=12, controls=[
                    Container(
                        width=36, height=36, border_radius=18,
                        bgcolor=ft.Colors.with_opacity(0.12, Colors.ACCENT),
                        alignment=Alignment.CENTER,
                        content=Icon(Icons.ASSIGNMENT_IND_ROUNDED, size=18, color=Colors.ACCENT),
                    ),
                    Column(spacing=2, tight=True, controls=[
                        Text("Buat Assignment",
                             size=15, weight=FontWeight.W_700, color=Colors.TEXT_PRIMARY),
                        Text(f"{employee.name}  ·  {employee.code}",
                             size=11, color=Colors.TEXT_MUTED),
                    ]),
                ]),
                IconButton(Icons.CLOSE, icon_color=Colors.TEXT_SECONDARY, icon_size=18,
                           style=ButtonStyle(padding=Padding.all(4)),
                           on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            ],
        ),
        content=Container(
            width=480, padding=Padding.only(top=4),
            content=Column(spacing=10, tight=True, scroll=ScrollMode.AUTO, controls=[
                err_row,
                info,
                _divider("IDENTITAS"),
                Row(spacing=10, controls=[f_code, sw_active]),
                _divider("ORGANISASI"),
                ResponsiveRow(spacing=10, controls=[
                    Container(col={"xs": 12, "sm": 6}, content=dd_branch),
                    Container(col={"xs": 12, "sm": 6}, content=dd_dept),
                ]),
                _divider("ROLES SISTEM"),
                Container(
                    padding=Padding.symmetric(horizontal=4),
                    content=role_col,
                ),
                _divider("PERIODE"),
                Row(spacing=10, controls=[f_start, f_end]),
                Container(height=4),
            ]),
        ),
        actions_alignment=MainAxisAlignment.END,
        actions=[
            Button("Batal",
                   style=ButtonStyle(color=Colors.TEXT_SECONDARY,
                                     shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS)),
                   on_click=lambda e: (setattr(dlg, "open", False), page.update())),
            Button("Simpan",
                   bgcolor=Colors.ACCENT, color=Colors.TEXT_ON_ACCENT,
                   style=ButtonStyle(shape=RoundedRectangleBorder(radius=Sizes.BTN_RADIUS),
                                     elevation=0),
                   on_click=save),
        ],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ─────────────────────────────────────────────────────────────
# TABLE ROWS
# ─────────────────────────────────────────────────────────────
def _build_rows(employees: List[Employee], page, session, content_area, refresh):
    rows = []
    for d in employees:
        row_bg = ft.Colors.with_opacity(0.025, Colors.TEXT_PRIMARY) if not d.is_active else None
        initials = "".join(w[0].upper() for w in d.name.split()[:2])

        rows.append(DataRow(
            color=row_bg,
            cells=[
                DataCell(Container(
                    content=Row(spacing=10, vertical_alignment=CrossAxisAlignment.CENTER, controls=[
                        Container(
                            width=32, height=32, border_radius=16,
                            bgcolor=ft.Colors.with_opacity(
                                0.15 if d.is_active else 0.06,
                                _TYPE_COLOR.get(d.type, Colors.ACCENT)),
                            alignment=Alignment.CENTER,
                            content=Text(initials, size=11, weight=FontWeight.W_700,
                                         color=_TYPE_COLOR.get(d.type, Colors.ACCENT)
                                         if d.is_active else Colors.TEXT_MUTED),
                        ),
                        Column(spacing=2, tight=True, controls=[
                            Text(d.name, size=13,
                                 weight=FontWeight.W_600 if d.is_active else FontWeight.W_400,
                                 color=Colors.TEXT_PRIMARY),
                            Text(d.code, size=10, color=Colors.TEXT_MUTED,
                                 font_family="monospace"),
                        ]),
                    ]),
                )),
                DataCell(_type_badge(d.type)),
                DataCell(Text(d.birth_date.strftime("%d %b %Y") if d.birth_date else "—",
                              size=12, color=Colors.TEXT_SECONDARY)),
                DataCell(Text(d.phone or "—", size=12, color=Colors.TEXT_SECONDARY)),
                DataCell(Text(d.email or "—", size=12, color=Colors.TEXT_SECONDARY)),
                DataCell(Text(d.hire_date.strftime("%d %b %Y") if d.hire_date else "—",
                              size=12, color=Colors.TEXT_SECONDARY)),
                DataCell(Text(d.resign_date.strftime("%d %b %Y") if d.resign_date else "—",
                              size=12, color=Colors.TEXT_MUTED)),
                DataCell(status_badge(d.is_active)),
                DataCell(Row(spacing=2, controls=[
                    action_btn(Icons.OPEN_IN_NEW_ROUNDED, "Detail",
                               lambda e, dp=d: _open_detail(dp, page, session, content_area, refresh),
                               Colors.TEXT_SECONDARY),
                    action_btn(Icons.EDIT_OUTLINED, "Edit",
                               lambda e, dp=d: _form_dialog(page, session, dp, refresh),
                               Colors.INFO),
                    action_btn(Icons.ASSIGNMENT_IND_OUTLINED, "Assign",
                               lambda e, dp=d: _assignment_dialog(page, session, dp, refresh),
                               Colors.ACCENT),
                    action_btn(Icons.STOP, "Resign",
                               lambda e, dp=d: _resign_form_dialog(page, session, dp, refresh),
                               Colors.INFO),
                    # action_btn(Icons.DELETE_OUTLINE, "Hapus",
                    #            lambda e, did=d.id, nm=d.name: confirm_dialog(
                    #                page, "Hapus Karyawan", f"Hapus '{nm}'?",
                    #                lambda: _delete(did, page, refresh)),
                    #            Colors.ERROR),
                ])),
            ],
        ))
    return rows


def _open_detail(employee, page, session, content_area, refresh_list):
    from app.pages.hr.employee_detail import EmployeeDetailPage

    def go_back():
        content_area.content = EmployeesPages(page, session, content_area)
        try: content_area.update()
        except: pass

    def go_edit():
        _form_dialog(page, session, employee,
                     on_saved=lambda: _open_detail(employee, page, session,
                                                    content_area, refresh_list))

    def go_assign():
        _assignment_dialog(page, session, employee,
                           on_saved=lambda: _open_detail(employee, page, session,
                                                          content_area, refresh_list))

    content_area.content = EmployeeDetailPage(
        page=page, session=session, employee=employee,
        on_back=go_back, on_edit=go_edit, on_assign=go_assign,
    )
    try: content_area.update()
    except: pass


def _delete(did, page, refresh):
    with SessionLocal() as db:
        ok, msg = EmployeeService.delete_employee(db, did)
    show_snack(page, msg, ok)
    if ok: refresh()


# ─────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────
def EmployeesPages(page, session: AppSession,
                   content_area: Optional[ft.Container] = None) -> ft.Control:
    search_val = {"q": ""}
    _area = content_area or ft.Container(expand=True)

    with SessionLocal() as db:
        initial = EmployeeService.get_all_employees(db, session.company_id)

    COLS = [
        DataColumn(Text("Karyawan",    size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        DataColumn(Text("Tipe",        size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        DataColumn(Text("Tgl. Lahir",  size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        DataColumn(Text("Telepon",     size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        DataColumn(Text("Email",       size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        DataColumn(Text("Tgl. Masuk",  size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        DataColumn(Text("Tgl. Keluar", size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        DataColumn(Text("Status",      size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
        DataColumn(Text("Aksi",        size=12, weight=FontWeight.W_600, color=Colors.TEXT_SECONDARY)),
    ]

    table = DataTable(
        expand=True,
        bgcolor=Colors.BG_CARD,
        border=Border.all(1, Colors.BORDER),
        border_radius=Sizes.CARD_RADIUS,
        horizontal_lines=BorderSide(1, Colors.DIVIDER),
        heading_row_color=ft.Colors.with_opacity(0.04, Colors.TEXT_PRIMARY),
        heading_row_height=44,
        data_row_min_height=56,
        column_spacing=16,
        columns=COLS,
        rows=[],
    )

    table_area = Row(scroll=ScrollMode.AUTO, controls=[])

    def refresh():
        with SessionLocal() as db:
            emps = EmployeeService.get_all_employees(
                db, session.company_id, search_val["q"] or "")
        table.rows = _build_rows(emps, page, session, _area, refresh)
        table_area.controls = [
            table if emps else empty_state("Tidak ada karyawan ditemukan.")
        ]
        try: table_area.update()
        except: pass

    def on_search(e):
        search_val["q"] = e.control.value or ""
        refresh()

    table.rows = _build_rows(initial, page, session, _area, refresh)
    table_area.controls = [table if initial else empty_state("Belum ada karyawan.")]

    total    = len(initial)
    aktif    = sum(1 for e in initial if e.is_active)
    nonaktif = total - aktif

    def _chip(label, count, color):
        return Container(
            padding=Padding.symmetric(horizontal=12, vertical=6),
            border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.08, color),
            border=Border.all(1, ft.Colors.with_opacity(0.2, color)),
            content=Row(spacing=6, tight=True, controls=[
                Container(width=6, height=6, border_radius=3, bgcolor=color),
                Text(f"{label}: {count}", size=11, color=color, weight=FontWeight.W_500),
            ]),
        )

    return Container(
        expand=True,
        bgcolor=Colors.BG_DARK,
        padding=Padding.all(24),
        content=Column(
            expand=True, spacing=0,
            controls=[
                page_header("Karyawan", "Kelola data karyawan perusahaan.",
                            "Tambah Karyawan",
                            on_action=lambda: _form_dialog(page, session, None, refresh),
                            action_icon=Icons.PERSON_ADD_OUTLINED),
                Row(
                    alignment=MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=CrossAxisAlignment.CENTER,
                    controls=[
                        search_bar("Cari nama atau kode...", on_search),
                        Row(spacing=8, controls=[
                            _chip("Total",    total,    Colors.TEXT_SECONDARY),
                            _chip("Aktif",    aktif,    Colors.SUCCESS),
                            _chip("Nonaktif", nonaktif, Colors.ERROR),
                        ]),
                    ],
                ),
                Container(height=16),
                Container(expand=True,
                          content=ListView(expand=True, controls=[table_area])),
            ],
        ),
    )