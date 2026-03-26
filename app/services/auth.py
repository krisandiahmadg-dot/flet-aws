"""
app/services/auth.py
Login, logout, session state, dan query menu berdasarkan role user.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from app.models import User, UserRole, Role, Menu, RoleMenuPermission


# ─────────────────────────────────────────────────────────────
# Session State (in-memory, per Flet app instance)
# ─────────────────────────────────────────────────────────────
@dataclass
class AppSession:
    """State yang disimpan setelah login berhasil."""
    user_id: int
    username: str
    full_name: str
    company_id: int
    company_name: str
    role_codes: List[str]          = field(default_factory=list)
    branch_id: Optional[int]       = None
    branch_name: Optional[str]     = None
    permissions: Dict[str, Dict]   = field(default_factory=dict)
    # {menu_code: {can_view, can_create, can_edit, can_delete, can_approve, can_export}}
    menu_tree: List[Dict]          = field(default_factory=list)
    logged_in_at: datetime         = field(default_factory=datetime.utcnow)

    def has_perm(self, menu_code: str, perm: str = "can_view") -> bool:
        return self.permissions.get(menu_code, {}).get(perm, False)


# ─────────────────────────────────────────────────────────────
# AUTH SERVICE
# ─────────────────────────────────────────────────────────────
class AuthService:

    @staticmethod
    def login(db: Session, username: str, password: str) -> tuple[bool, str, Optional[AppSession]]:
        """
        Returns (success, message, session|None)
        """
        user: Optional[User] = (
            db.query(User)
            .filter(
                (User.username == username.strip()) | (User.email == username.strip())
            )
            .first()
        )

        if not user:
            return False, "Username atau email tidak ditemukan.", None

        if not user.is_active:
            return False, "Akun Anda dinonaktifkan. Hubungi administrator.", None

        if not user.verify_password(password):
            return False, "Password salah.", None

        # Update last login
        user.last_login_at = datetime.utcnow()
        db.commit()

        # Load roles
        user_roles = (
            db.query(UserRole)
            .filter_by(user_id=user.id)
            .all()
        )
        role_ids  = [ur.role_id for ur in user_roles]
        role_codes= [ur.role.code for ur in user_roles]

        # Jika ada satu UserRole dengan branch_id=NULL → user HQ, akses semua cabang
        # Jika semua UserRole punya branch_id → user terikat cabang tertentu
        has_null_branch = any(ur.branch_id is None for ur in user_roles)
        if has_null_branch:
            branch_id   = None   # HQ / superadmin — tidak terikat cabang
            branch_name = None
        else:
            # Ambil cabang dari role pertama (bisa dikembangkan multi-branch)
            branch_id   = user_roles[0].branch_id if user_roles else None
            branch_name = user_roles[0].branch.name if (user_roles and user_roles[0].branch) else None

        # Permissions: ambil semua RoleMenuPermission untuk role user
        perms_rows = (
            db.query(RoleMenuPermission, Menu)
            .join(Menu, RoleMenuPermission.menu_id == Menu.id)
            .filter(RoleMenuPermission.role_id.in_(role_ids))
            .all()
        )

        permissions: Dict[str, Dict] = {}
        for rmp, menu in perms_rows:
            code = menu.code
            if code not in permissions:
                permissions[code] = {
                    "can_view": False, "can_create": False,
                    "can_edit": False, "can_delete": False,
                    "can_approve": False, "can_export": False,
                }
            # OR logic — jika ada satu role yang bisa, maka bisa
            permissions[code]["can_view"]   |= rmp.can_view
            permissions[code]["can_create"] |= rmp.can_create
            permissions[code]["can_edit"]   |= rmp.can_edit
            permissions[code]["can_delete"] |= rmp.can_delete
            permissions[code]["can_approve"]|= rmp.can_approve
            permissions[code]["can_export"] |= rmp.can_export

        # Build menu tree (hanya yang can_view=True)
        menu_tree = AuthService._build_menu_tree(db, permissions)

        session = AppSession(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            company_id=user.company_id,
            company_name=user.company.name,
            role_codes=role_codes,
            branch_id=branch_id,
            branch_name=branch_name,
            permissions=permissions,
            menu_tree=menu_tree,
        )

        return True, f"Selamat datang, {user.full_name}!", session

    @staticmethod
    def _build_menu_tree(db: Session, permissions: Dict) -> List[Dict]:
        """Bangun tree menu yang boleh diakses user."""
        all_menus = (
            db.query(Menu)
            .filter_by(is_active=True, is_visible=True, parent_id=None)
            .order_by(Menu.sort_order)
            .all()
        )

        def serialize(menu: Menu) -> Optional[Dict]:
            children = []
            for child in sorted(menu.children or [], key=lambda m: m.sort_order):
                if not child.is_active or not child.is_visible:
                    continue
                if not permissions.get(child.code, {}).get("can_view", False):
                    continue
                s = serialize(child)
                if s:
                    children.append(s)

            # Tampilkan parent jika dia punya child yg visible atau punya route sendiri
            has_access = permissions.get(menu.code, {}).get("can_view", False)
            if not has_access and not children:
                return None

            return {
                "id": menu.id,
                "code": menu.code,
                "label": menu.label,
                "icon": menu.icon,
                "route": menu.route,
                "children": children,
            }

        result = []
        for m in all_menus:
            node = serialize(m)
            if node:
                result.append(node)
        return result
