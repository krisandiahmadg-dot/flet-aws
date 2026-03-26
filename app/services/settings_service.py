"""
app/services/settings_service.py
CRUD operations untuk modul Pengaturan: User, Role, Menu, Permission
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import (
    User, UserRole, Role, RoleMenuPermission,
    Menu, Company, Branch
)


# ─────────────────────────────────────────────────────────────
# USER SERVICE
# ─────────────────────────────────────────────────────────────
class UserService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[User]:
        q = db.query(User).filter_by(company_id=company_id)
        if search:
            s = f"%{search}%"
            q = q.filter(
                (User.username.ilike(s)) |
                (User.email.ilike(s))
            )
        return q.order_by(User.full_name).all()

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter_by(id=user_id).first()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[User]]:
        # Validasi unik
        if db.query(User).filter_by(username=data["username"]).first():
            return False, "Username sudah digunakan.", None
        if db.query(User).filter_by(email=data["email"]).first():
            return False, "Email sudah digunakan.", None

        user = User(
            company_id=company_id,
            username=data["username"].strip(),
            email=data["email"].strip(),
            full_name=data["full_name"].strip(),
            phone=data.get("phone", "").strip() or None,
            is_active=data.get("is_active", True),
        )
        user.set_password(data["password"])
        db.add(user)
        db.flush()

        # Assign roles
        for role_id in data.get("role_ids", []):
            db.add(UserRole(
                user_id=user.id,
                role_id=int(role_id),
                branch_id=data.get("branch_id") or None,
            ))

        db.commit()
        return True, "User berhasil dibuat.", user

    @staticmethod
    def update(db: Session, user_id: int, data: Dict) -> tuple[bool, str]:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return False, "User tidak ditemukan."

        # Cek unik jika berubah
        if data["username"] != user.username:
            if db.query(User).filter_by(username=data["username"]).first():
                return False, "Username sudah digunakan."
        if data["email"] != user.email:
            if db.query(User).filter_by(email=data["email"]).first():
                return False, "Email sudah digunakan."

        user.username  = data["username"].strip()
        user.email     = data["email"].strip()
        user.full_name = data["full_name"].strip()
        user.phone     = data.get("phone", "").strip() or None
        user.is_active = data.get("is_active", True)

        if data.get("password"):
            user.set_password(data["password"])

        # Update roles: hapus lama, insert baru
        db.query(UserRole).filter_by(user_id=user_id).delete()
        for role_id in data.get("role_ids", []):
            db.add(UserRole(
                user_id=user.id,
                role_id=int(role_id),
                branch_id=data.get("branch_id") or None,
            ))

        db.commit()
        return True, "User berhasil diperbarui."

    @staticmethod
    def delete(db: Session, user_id: int) -> tuple[bool, str]:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return False, "User tidak ditemukan."
        db.query(UserRole).filter_by(user_id=user_id).delete()
        db.delete(user)
        db.commit()
        return True, "User berhasil dihapus."

    @staticmethod
    def toggle_active(db: Session, user_id: int) -> tuple[bool, str]:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return False, "User tidak ditemukan."
        user.is_active = not user.is_active
        db.commit()
        status = "diaktifkan" if user.is_active else "dinonaktifkan"
        return True, f"User berhasil {status}."


# ─────────────────────────────────────────────────────────────
# ROLE SERVICE
# ─────────────────────────────────────────────────────────────
class RoleService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[Role]:
        q = db.query(Role).filter_by(company_id=company_id)
        if search:
            q = q.filter(Role.name.ilike(f"%{search}%"))
        return q.order_by(Role.name).all()

    @staticmethod
    def get_by_id(db: Session, role_id: int) -> Optional[Role]:
        return db.query(Role).filter_by(id=role_id).first()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Role]]:
        if db.query(Role).filter_by(company_id=company_id, code=data["code"]).first():
            return False, "Kode role sudah digunakan.", None
        role = Role(
            company_id=company_id,
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            description=data.get("description", "").strip() or None,
            is_active=data.get("is_active", True),
        )
        db.add(role)
        db.commit()
        return True, "Role berhasil dibuat.", role

    @staticmethod
    def update(db: Session, role_id: int, data: Dict) -> tuple[bool, str]:
        role = db.query(Role).filter_by(id=role_id).first()
        if not role:
            return False, "Role tidak ditemukan."
        if role.is_system:
            return False, "Role sistem tidak bisa diubah."
        role.name        = data["name"].strip()
        role.description = data.get("description", "").strip() or None
        role.is_active   = data.get("is_active", True)
        db.commit()
        return True, "Role berhasil diperbarui."

    @staticmethod
    def delete(db: Session, role_id: int) -> tuple[bool, str]:
        role = db.query(Role).filter_by(id=role_id).first()
        if not role:
            return False, "Role tidak ditemukan."
        if role.is_system:
            return False, "Role sistem tidak bisa dihapus."
        user_count = db.query(UserRole).filter_by(role_id=role_id).count()
        if user_count > 0:
            return False, f"Role digunakan oleh {user_count} user, tidak bisa dihapus."
        db.query(RoleMenuPermission).filter_by(role_id=role_id).delete()
        db.delete(role)
        db.commit()
        return True, "Role berhasil dihapus."

    @staticmethod
    def get_permissions(db: Session, role_id: int) -> Dict[int, RoleMenuPermission]:
        """Return {menu_id: RoleMenuPermission}"""
        rows = db.query(RoleMenuPermission).filter_by(role_id=role_id).all()
        return {r.menu_id: r for r in rows}

    @staticmethod
    def save_permissions(db: Session, role_id: int, perms: Dict[int, Dict]) -> tuple[bool, str]:
        """
        perms = {menu_id: {can_view, can_create, can_edit, can_delete, can_approve, can_export}}
        """
        # Hapus semua permission lama
        db.query(RoleMenuPermission).filter_by(role_id=role_id).delete()
        for menu_id, p in perms.items():
            # p bisa berformat {"view": bool} atau {"can_view": bool}
            # normalkan dulu ke format tanpa prefix "can_"
            def _v(key):
                return bool(p.get(key, False) or p.get(f"can_{key}", False))

            if any(_v(k) for k in ["view","create","edit","delete","approve","export"]):
                db.add(RoleMenuPermission(
                    role_id=role_id,
                    menu_id=menu_id,
                    can_view=_v("view"),
                    can_create=_v("create"),
                    can_edit=_v("edit"),
                    can_delete=_v("delete"),
                    can_approve=_v("approve"),
                    can_export=_v("export"),
                ))
        db.commit()
        return True, "Permission berhasil disimpan."


# ─────────────────────────────────────────────────────────────
# MENU SERVICE
# ─────────────────────────────────────────────────────────────
class MenuService:

    @staticmethod
    def get_all_flat(db: Session) -> List[Menu]:
        return db.query(Menu).order_by(Menu.sort_order, Menu.id).all()

    @staticmethod
    def get_roots(db: Session) -> List[Menu]:
        return (db.query(Menu)
                .filter_by(parent_id=None, is_active=True)
                .order_by(Menu.sort_order).all())

    @staticmethod
    def get_by_id(db: Session, menu_id: int) -> Optional[Menu]:
        return db.query(Menu).filter_by(id=menu_id).first()

    @staticmethod
    def create(db: Session, data: Dict) -> tuple[bool, str, Optional[Menu]]:
        if db.query(Menu).filter_by(code=data["code"]).first():
            return False, "Kode menu sudah digunakan.", None
        menu = Menu(
            code=data["code"].strip().upper(),
            label=data["label"].strip(),
            icon=data.get("icon", "").strip() or None,
            route=data.get("route", "").strip() or None,
            module=data.get("module", "").strip() or None,
            sort_order=int(data.get("sort_order", 0)),
            parent_id=int(data["parent_id"]) if data.get("parent_id") else None,
            is_visible=data.get("is_visible", True),
            is_active=data.get("is_active", True),
        )
        db.add(menu)
        db.commit()
        return True, "Menu berhasil dibuat.", menu

    @staticmethod
    def update(db: Session, menu_id: int, data: Dict) -> tuple[bool, str]:
        menu = db.query(Menu).filter_by(id=menu_id).first()
        if not menu:
            return False, "Menu tidak ditemukan."
        menu.label      = data["label"].strip()
        menu.icon       = data.get("icon", "").strip() or None
        menu.route      = data.get("route", "").strip() or None
        menu.module     = data.get("module", "").strip() or None
        menu.sort_order = int(data.get("sort_order", 0))
        menu.parent_id  = int(data["parent_id"]) if data.get("parent_id") else None
        menu.is_visible = data.get("is_visible", True)
        menu.is_active  = data.get("is_active", True)
        db.commit()
        return True, "Menu berhasil diperbarui."

    @staticmethod
    def delete(db: Session, menu_id: int) -> tuple[bool, str]:
        menu = db.query(Menu).filter_by(id=menu_id).first()
        if not menu:
            return False, "Menu tidak ditemukan."
        child_count = db.query(Menu).filter_by(parent_id=menu_id).count()
        if child_count > 0:
            return False, f"Menu memiliki {child_count} sub-menu, hapus sub-menu dulu."
        db.query(RoleMenuPermission).filter_by(menu_id=menu_id).delete()
        db.delete(menu)
        db.commit()
        return True, "Menu berhasil dihapus."

    @staticmethod
    def toggle_visible(db: Session, menu_id: int) -> tuple[bool, str]:
        menu = db.query(Menu).filter_by(id=menu_id).first()
        if not menu:
            return False, "Menu tidak ditemukan."
        menu.is_visible = not menu.is_visible
        db.commit()
        return True, f"Menu {'ditampilkan' if menu.is_visible else 'disembunyikan'}."
