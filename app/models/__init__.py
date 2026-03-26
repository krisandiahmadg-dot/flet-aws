"""
app/models/__init__.py
SQLAlchemy ORM models
"""

from __future__ import annotations
import hashlib, secrets
from datetime import datetime, date as date_type
from typing import Optional, List

from sqlalchemy import (
    Integer, Numeric, String, Text, Boolean, DateTime, Date,
    ForeignKey, SmallInteger, Enum as SAEnum,
    UniqueConstraint, JSON, event, DDL, Computed, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ─────────────────────────────────────────────────────────────
# COMPANY
# ─────────────────────────────────────────────────────────────
class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int]                   = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str]                 = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str]                 = mapped_column(String(150), nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(200))
    tax_id: Mapped[Optional[str]]     = mapped_column(String(50))
    address: Mapped[Optional[str]]    = mapped_column(Text)
    city: Mapped[Optional[str]]       = mapped_column(String(100))
    province: Mapped[Optional[str]]   = mapped_column(String(100))
    country: Mapped[str]              = mapped_column(String(100), default="Indonesia")
    phone: Mapped[Optional[str]]      = mapped_column(String(30))
    email: Mapped[Optional[str]]      = mapped_column(String(100))
    logo_url: Mapped[Optional[str]]    = mapped_column(String(255))
    currency_code: Mapped[str]        = mapped_column(String(10), default="IDR")
    is_active: Mapped[bool]           = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow,
                                                       onupdate=datetime.utcnow)

    branches:   Mapped[List["Branch"]]   = relationship("Branch",   back_populates="company",
                                                         foreign_keys="[Branch.company_id]")
    roles:      Mapped[List["Role"]]     = relationship("Role",     back_populates="company")
    users:      Mapped[List["User"]]     = relationship("User",     back_populates="company",
                                                         foreign_keys="[User.company_id]")
    employees:  Mapped[List["Employee"]] = relationship("Employee", back_populates="company")


# ─────────────────────────────────────────────────────────────
# BRANCH
# ─────────────────────────────────────────────────────────────
class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    code: Mapped[str]                  = mapped_column(String(20), nullable=False)
    name: Mapped[str]                  = mapped_column(String(150), nullable=False)
    branch_type: Mapped[str]           = mapped_column(
        SAEnum("HQ", "BRANCH", "WAREHOUSE", "STORE"), default="BRANCH"
    )
    address: Mapped[Optional[str]]         = mapped_column(Text)
    city: Mapped[Optional[str]]            = mapped_column(String(100))
    phone: Mapped[Optional[str]]           = mapped_column(String(30))
    email: Mapped[Optional[str]]           = mapped_column(String(100))
    manager_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    is_active: Mapped[bool]                = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_branch_code"),)

    company:   Mapped["Company"]          = relationship("Company", back_populates="branches",
                                                          foreign_keys=[company_id])
    manager:   Mapped[Optional["User"]]   = relationship("User", foreign_keys=[manager_user_id])
    employee_assignments: Mapped[List["EmployeeAssignment"]] = relationship("EmployeeAssignment", back_populates="branch")


# ─────────────────────────────────────────────────────────────
# DEPARTMENT
# ─────────────────────────────────────────────────────────────
class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("branches.id"))
    code: Mapped[str]                  = mapped_column(String(20), nullable=False)
    name: Mapped[str]                  = mapped_column(String(150), nullable=False)
    parent_id: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("departments.id"))
    is_active: Mapped[bool]            = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_dept_code"),)

    children:  Mapped[List["Department"]]    = relationship("Department",
                                                             back_populates="parent",
                                                             foreign_keys="[Department.parent_id]")
    parent:    Mapped[Optional["Department"]]= relationship("Department",
                                                             back_populates="children",
                                                             remote_side="Department.id",
                                                             foreign_keys="[Department.parent_id]")
    branch:    Mapped[Optional["Branch"]]       = relationship("Branch",     foreign_keys="[Department.branch_id]")
    employee_assignments: Mapped[List["EmployeeAssignment"]] = relationship("EmployeeAssignment", back_populates="departments")


# ─────────────────────────────────────────────────────────────
# EMPLOYEE
# ─────────────────────────────────────────────────────────────
class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]              = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    code: Mapped[str]                    = mapped_column(String(20), nullable=False)
    name: Mapped[str]               = mapped_column(String(150), nullable=False)
    address: Mapped[Optional[str]]               = mapped_column(Text)
    type: Mapped[str]           = mapped_column(
        SAEnum("PERMANENT", "CONTRACT", "INTERN", "FREELANCE"), default="PERMANENT"
    )

    birth_date: Mapped[Optional[date_type]] = mapped_column(Date)
    phone: Mapped[Optional[str]]         = mapped_column(String(30))
    email: Mapped[Optional[str]]         = mapped_column(String(150))
    hire_date: Mapped[Optional[datetime]]= mapped_column(Date)
    resign_date: Mapped[Optional[datetime]] = mapped_column(Date)
    is_active: Mapped[bool]              = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_emp_code"),)

    # Relasi ke tabel lain
    company:    Mapped["Company"]              = relationship("Company",    back_populates="employees")

    # ONE-TO-ONE ke User (sisi Employee)
    # Satu employee bisa tidak punya user (nullable), tapi kalau punya hanya satu
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="employee",
        foreign_keys="[User.employee_id]",
        uselist=False,   # <-- one-to-one
    )
    employee_assignments: Mapped[List["EmployeeAssignment"]] = relationship("EmployeeAssignment", back_populates="employee")
    


# ─────────────────────────────────────────────────────────────
# ROLE
# ─────────────────────────────────────────────────────────────
class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    code: Mapped[str]                  = mapped_column(String(50), nullable=False)
    name: Mapped[str]                  = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_system: Mapped[bool]            = mapped_column(Boolean, default=False)
    is_active: Mapped[bool]            = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_role_code"),)

    company:     Mapped["Company"]                  = relationship("Company", back_populates="roles")
    permissions: Mapped[List["RoleMenuPermission"]] = relationship("RoleMenuPermission",
                                                                    back_populates="role")

# ─────────────────────────────────────────────────────────────
# EMPLOYEE ASSIGNMENT
# ─────────────────────────────────────────────────────────────
class EmployeeAssignment(Base):
    __tablename__ = "employee_assignments"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int]              = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    branch_id: Mapped[Optional[int]]     = mapped_column(Integer, ForeignKey("branches.id"))
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    roles: Mapped[Optional[list]]     = mapped_column(JSON, default=list) 
    code: Mapped[Optional[str]]          = mapped_column(String(20), nullable=False)
    start_date: Mapped[Optional[datetime]]= mapped_column(Date)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date)
    is_active: Mapped[bool]              = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)

    # Relasi ke tabel lain
    branch:     Mapped[Optional["Branch"]]     = relationship("Branch",     back_populates="employee_assignments", uselist=False)
    departments: Mapped[Optional["Department"]] = relationship("Department", back_populates="employee_assignments")

    employee: Mapped["Employee"] = relationship(
        "Employee",
        foreign_keys=[employee_id],
    )

    # ONE-TO-ONE ke User (sisi Employee)
    # # Satu employee bisa tidak punya user (nullable), tapi kalau punya hanya satu
    # user: Mapped[Optional["User"]] = relationship(
    #     "User",
    #     back_populates="employee",
    #     foreign_keys="[User.employee_id]",
    #     uselist=False,   # <-- one-to-one
    # )




# ─────────────────────────────────────────────────────────────
# MENU (self-referential tree)
# ─────────────────────────────────────────────────────────────
class Menu(Base):
    __tablename__ = "menus"

    id: Mapped[int]                  = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("menus.id"))
    code: Mapped[str]                = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str]               = mapped_column(String(100), nullable=False)
    icon: Mapped[Optional[str]]      = mapped_column(String(80))
    route: Mapped[Optional[str]]     = mapped_column(String(200))
    module: Mapped[Optional[str]]    = mapped_column(String(80))
    sort_order: Mapped[int]          = mapped_column(SmallInteger, default=0)
    is_visible: Mapped[bool]         = mapped_column(Boolean, default=True)
    is_active: Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]     = mapped_column(DateTime, default=datetime.utcnow)

    # Anak-anak menu (One Menu → Many Children)
    children: Mapped[List["Menu"]] = relationship(
        "Menu",
        back_populates="parent",
        cascade="save-update, merge",   # hindari delete-orphan — cukup untuk tree
        order_by="Menu.sort_order",
        foreign_keys="[Menu.parent_id]",
        lazy="select",
    )
    # Induk menu (Many Children → One Parent)
    parent: Mapped[Optional["Menu"]] = relationship(
        "Menu",
        back_populates="children",
        remote_side="Menu.id",
        foreign_keys="[Menu.parent_id]",
        lazy="select",
    )
    permissions: Mapped[List["RoleMenuPermission"]] = relationship(
        "RoleMenuPermission", back_populates="menu"
    )


# ─────────────────────────────────────────────────────────────
# ROLE MENU PERMISSION
# ─────────────────────────────────────────────────────────────
class RoleMenuPermission(Base):
    __tablename__ = "role_menu_permissions"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int]     = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    menu_id: Mapped[int]     = mapped_column(Integer, ForeignKey("menus.id"), nullable=False)
    can_view: Mapped[bool]   = mapped_column(Boolean, default=False)
    can_create: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit: Mapped[bool]   = mapped_column(Boolean, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    can_approve: Mapped[bool]= mapped_column(Boolean, default=False)
    can_export: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("role_id", "menu_id", name="uq_role_menu"),)

    role: Mapped["Role"] = relationship("Role", back_populates="permissions")
    menu: Mapped["Menu"] = relationship("Menu", back_populates="permissions")


# ─────────────────────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int]                          = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]                  = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    # FK ke employees — nullable, karena tidak semua user adalah employee
    employee_id: Mapped[Optional[int]]       = mapped_column(Integer, ForeignKey("employees.id"))
    username: Mapped[str]                    = mapped_column(String(80), nullable=False, unique=True)
    email: Mapped[str]                       = mapped_column(String(150), nullable=False, unique=True)
    password_hash: Mapped[str]               = mapped_column(String(255), nullable=False)
    full_name: Mapped[str]                   = mapped_column(String(150), nullable=False)
    avatar_url: Mapped[Optional[str]]        = mapped_column(String(255))
    phone: Mapped[Optional[str]]             = mapped_column(String(30))
    is_active: Mapped[bool]                  = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]]= mapped_column(DateTime)
    created_at: Mapped[datetime]             = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]             = mapped_column(DateTime, default=datetime.utcnow,
                                                              onupdate=datetime.utcnow)

    company:    Mapped["Company"]          = relationship("Company", back_populates="users",
                                                           foreign_keys=[company_id])
    user_roles: Mapped[List["UserRole"]]   = relationship("UserRole", back_populates="user")


    # ONE-TO-ONE ke Employee (sisi User)
    # uselist=False → akses sebagai user.employee (bukan list)
    employee: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        back_populates="user",
        foreign_keys=[employee_id],
        uselist=False,
    )

    # ── Password helpers ──────────────────────────────────────
    def set_password(self, plain: str) -> None:
        try:
            from passlib.context import CryptContext
            _ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            self.password_hash = _ctx.hash(plain)
        except ImportError:
            salt = secrets.token_hex(16)
            self.password_hash = "sha256$" + salt + "$" + hashlib.sha256(
                (salt + plain).encode()
            ).hexdigest()

    def verify_password(self, plain: str) -> bool:
        if self.password_hash.startswith("sha256$"):
            _, salt, digest = self.password_hash.split("$")
            return hashlib.sha256((salt + plain).encode()).hexdigest() == digest
        try:
            from passlib.context import CryptContext
            _ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return _ctx.verify(plain, self.password_hash)
        except ImportError:
            return False

# ─────────────────────────────────────────────────────────────
# USER ROLES
# ─────────────────────────────────────────────────────────────
class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int]          = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int]          = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    branch_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("branches.id"))
    created_at: Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)

    user:   Mapped["User"]            = relationship("User",   back_populates="user_roles")
    role:   Mapped["Role"]            = relationship("Role")
    branch: Mapped[Optional["Branch"]]= relationship("Branch", foreign_keys=[branch_id])


# ─────────────────────────────────────────────────────────────
# UNIT OF MEASURE
# ─────────────────────────────────────────────────────────────
class UnitOfMeasure(Base):
    __tablename__ = "unit_of_measures"

    id: Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]      = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    code: Mapped[str]            = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str]            = mapped_column(String(80), nullable=False)
    uom_type: Mapped[str]        = mapped_column(
        SAEnum("LENGTH","WEIGHT","VOLUME","UNIT","TIME","OTHER"), default="UNIT"
    )
    is_active: Mapped[bool]      = mapped_column(Boolean, default=True)
    
    
class UOMConversion(Base):
    __tablename__ = "uom_conversions"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_uom_id: Mapped[int]           = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    to_uom_id: Mapped[int]             = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    factor: Mapped[float]              = mapped_column(Numeric(10, 4), nullable=False)
    is_active: Mapped[bool]            = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("from_uom_id", "to_uom_id", name="uq_uom_conversion"),)

    # Menambahkan argumen foreign_keys untuk memperjelas pemetaan
    from_uom: Mapped[Optional["UnitOfMeasure"]] = relationship(
        "UnitOfMeasure", 
        foreign_keys=[from_uom_id]
    )
    
    to_uom: Mapped[Optional["UnitOfMeasure"]] = relationship(
        "UnitOfMeasure", 
        foreign_keys=[to_uom_id]
    )




# ─────────────────────────────────────────────────────────────
# PRODUCT CATEGORY
# ─────────────────────────────────────────────────────────────
class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    parent_id: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("product_categories.id"))
    code: Mapped[str]                  = mapped_column(String(30), nullable=False)
    name: Mapped[str]                  = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool]            = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_cat_code"),)

    children: Mapped[List["ProductCategory"]] = relationship(
        "ProductCategory", back_populates="parent",
        foreign_keys="[ProductCategory.parent_id]",
    )
    parent: Mapped[Optional["ProductCategory"]] = relationship(
        "ProductCategory", back_populates="children",
        remote_side="ProductCategory.id",
        foreign_keys="[ProductCategory.parent_id]",
    )


# ─────────────────────────────────────────────────────────────
# PRODUCT
# ─────────────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]              = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    category_id: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("product_categories.id"))
    code: Mapped[str]                    = mapped_column(String(50), nullable=False)
    barcode: Mapped[Optional[str]]       = mapped_column(String(80))
    name: Mapped[str]                    = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]]   = mapped_column(Text)
    product_type: Mapped[str]            = mapped_column(
        SAEnum("GOODS","SERVICE","BUNDLE"), default="GOODS"
    )
    uom_id: Mapped[int]                  = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    purchase_uom_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("unit_of_measures.id"))
    sales_uom_id: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("unit_of_measures.id"))
    tracking_type: Mapped[str]           = mapped_column(
        SAEnum("NONE","SERIAL","LOT"), default="NONE"
    )
    standard_cost: Mapped[float]         = mapped_column(default=0)
    sale_price: Mapped[float]            = mapped_column(default=0)
    min_sale_price: Mapped[float]        = mapped_column(default=0)
    min_stock: Mapped[float]             = mapped_column(default=0)
    max_stock: Mapped[float]             = mapped_column(default=0)
    reorder_point: Mapped[float]         = mapped_column(default=0)
    lead_time_days: Mapped[int]          = mapped_column(SmallInteger, default=0)
    is_purchasable: Mapped[bool]         = mapped_column(Boolean, default=True)
    is_sellable: Mapped[bool]            = mapped_column(Boolean, default=True)
    is_stockable: Mapped[bool]           = mapped_column(Boolean, default=True)
    is_active: Mapped[bool]              = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow,
                                                          onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_product_code"),)

    category: Mapped[Optional["ProductCategory"]] = relationship("ProductCategory")
    uom:      Mapped["UnitOfMeasure"]             = relationship("UnitOfMeasure", foreign_keys=[uom_id])


# ─────────────────────────────────────────────────────────────
# VENDOR
# ─────────────────────────────────────────────────────────────
class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]              = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    code: Mapped[str]                    = mapped_column(String(30), nullable=False)
    name: Mapped[str]                    = mapped_column(String(200), nullable=False)
    legal_name: Mapped[Optional[str]]    = mapped_column(String(200))
    tax_id: Mapped[Optional[str]]        = mapped_column(String(50))
    vendor_type: Mapped[str]             = mapped_column(
        SAEnum("SUPPLIER","MANUFACTURER","DISTRIBUTOR","SERVICE"), default="SUPPLIER"
    )
    address: Mapped[Optional[str]]       = mapped_column(Text)
    city: Mapped[Optional[str]]          = mapped_column(String(100))
    province: Mapped[Optional[str]]      = mapped_column(String(100))
    country: Mapped[str]                 = mapped_column(String(100), default="Indonesia")
    phone: Mapped[Optional[str]]         = mapped_column(String(30))
    email: Mapped[Optional[str]]         = mapped_column(String(150))
    payment_terms_days: Mapped[int]      = mapped_column(SmallInteger, default=30)
    currency_code: Mapped[str]           = mapped_column(String(10), default="IDR")
    bank_name: Mapped[Optional[str]]     = mapped_column(String(100))
    bank_account: Mapped[Optional[str]]  = mapped_column(String(50))
    bank_account_name: Mapped[Optional[str]] = mapped_column(String(150))
    rating: Mapped[float]                = mapped_column(default=0)
    is_active: Mapped[bool]              = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow,
                                                          onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_vendor_code"),)


# ─────────────────────────────────────────────────────────────
# VENDOR PRODUCT
# ─────────────────────────────────────────────────────────────
class VendorProduct(Base):
    __tablename__ = "vendor_products"

    id: Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int]        = mapped_column(Integer, ForeignKey("vendors.id"), nullable=False)
    product_id: Mapped[int]       = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    vendor_sku: Mapped[Optional[str]] = mapped_column(String(80))
    vendor_price: Mapped[Optional[float]] = mapped_column()
    min_order_qty: Mapped[float]  = mapped_column(default=1)
    lead_time_days: Mapped[int]   = mapped_column(SmallInteger, default=0)
    is_preferred: Mapped[bool]    = mapped_column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("vendor_id", "product_id", name="uq_vp"),)

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])


# ─────────────────────────────────────────────────────────────
# PARTNER
# ─────────────────────────────────────────────────────────────
class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]              = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    code: Mapped[str]                    = mapped_column(String(30), nullable=False)
    name: Mapped[str]                    = mapped_column(String(200), nullable=False)
    partner_type: Mapped[str]            = mapped_column(
        SAEnum("RESELLER","AGENT","REFERRAL","DISTRIBUTOR","AFFILIATE"), default="REFERRAL"
    )
    contact_person: Mapped[Optional[str]] = mapped_column(String(150))
    phone: Mapped[Optional[str]]         = mapped_column(String(30))
    email: Mapped[Optional[str]]         = mapped_column(String(150))
    address: Mapped[Optional[str]]       = mapped_column(Text)
    city: Mapped[Optional[str]]          = mapped_column(String(100))
    commission_pct: Mapped[float]        = mapped_column(default=0)
    rating: Mapped[float]                = mapped_column(default=0)
    is_active: Mapped[bool]              = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_partner_code"),)


# ─────────────────────────────────────────────────────────────
# CAMPAIGN
# ─────────────────────────────────────────────────────────────
class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("branches.id"))
    code: Mapped[str]                  = mapped_column(String(30), nullable=False)
    name: Mapped[str]                  = mapped_column(String(200), nullable=False)
    campaign_type: Mapped[str]         = mapped_column(
        SAEnum("DIGITAL","PRINT","EVENT","EMAIL","SMS","REFERRAL","OTHER"), default="DIGITAL"
    )
    channel: Mapped[Optional[str]]     = mapped_column(String(100))
    start_date: Mapped[Optional[datetime]] = mapped_column(Date)
    end_date: Mapped[Optional[datetime]]   = mapped_column(Date)
    budget: Mapped[float]              = mapped_column(default=0)
    actual_spend: Mapped[float]        = mapped_column(default=0)
    target_leads: Mapped[int]          = mapped_column(Integer, default=0)
    target_revenue: Mapped[float]      = mapped_column(default=0)
    status: Mapped[str]                = mapped_column(
        SAEnum("DRAFT","ACTIVE","PAUSED","COMPLETED","CANCELLED"), default="DRAFT"
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_campaign_code"),)


# ─────────────────────────────────────────────────────────────
# CUSTOMER
# ─────────────────────────────────────────────────────────────
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]              = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[Optional[int]]     = mapped_column(Integer, ForeignKey("branches.id"))
    code: Mapped[str]                    = mapped_column(String(30), nullable=False)
    name: Mapped[str]                    = mapped_column(String(200), nullable=False)
    customer_type: Mapped[str]           = mapped_column(
        SAEnum("INDIVIDUAL","CORPORATE"), default="INDIVIDUAL"
    )
    tax_id: Mapped[Optional[str]]        = mapped_column(String(50))
    phone: Mapped[Optional[str]]         = mapped_column(String(30))
    email: Mapped[Optional[str]]         = mapped_column(String(150))
    address: Mapped[Optional[str]]       = mapped_column(Text)
    city: Mapped[Optional[str]]          = mapped_column(String(100))
    province: Mapped[Optional[str]]      = mapped_column(String(100))
    country: Mapped[str]                 = mapped_column(String(100), default="Indonesia")
    acquisition_source: Mapped[str]      = mapped_column(
        SAEnum("PARTNER","CAMPAIGN","DIRECT","ORGANIC","REFERRAL","OTHER"), default="DIRECT"
    )
    sales_user_id: Mapped[Optional[int]]    = mapped_column(Integer)
    partner_id: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("partners.id"))
    campaign_id: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("campaigns.id"))
    payment_terms_days: Mapped[int]      = mapped_column(SmallInteger, default=0)
    credit_limit: Mapped[float]          = mapped_column(default=0)
    outstanding_balance: Mapped[float]   = mapped_column(default=0)
    is_active: Mapped[bool]              = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow,
                                                          onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_customer_code"),)

    branch:   Mapped[Optional["Branch"]]   = relationship("Branch",   foreign_keys=[branch_id])
    partner:  Mapped[Optional["Partner"]]  = relationship("Partner",  foreign_keys=[partner_id])
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign", foreign_keys=[campaign_id])


# ─────────────────────────────────────────────────────────────
# WAREHOUSE
# ─────────────────────────────────────────────────────────────
class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[int]       = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    code: Mapped[str]            = mapped_column(String(20), nullable=False)
    name: Mapped[str]            = mapped_column(String(150), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool]      = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("branch_id", "code", name="uq_wh_code"),)

    branch: Mapped["Branch"] = relationship("Branch", foreign_keys=[branch_id])


# ─────────────────────────────────────────────────────────────
# PURCHASE REQUEST
# ─────────────────────────────────────────────────────────────
class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]             = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"))
    pr_number: Mapped[str]             = mapped_column(String(30), nullable=False, unique=True)
    request_date: Mapped[datetime]     = mapped_column(Date, nullable=False)
    required_date: Mapped[Optional[datetime]] = mapped_column(Date)
    requested_by: Mapped[int]          = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[str]                = mapped_column(
        SAEnum("DRAFT","SUBMITTED","APPROVED","PARTIAL_PO","REJECTED","PO_CREATED","CANCELLED"),
        default="DRAFT"
    )
    notes: Mapped[Optional[str]]       = mapped_column(Text)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow,
                                                        onupdate=datetime.utcnow)

    branch:      Mapped["Branch"]           = relationship("Branch",     foreign_keys=[branch_id])
    department:  Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[department_id])
    requester:   Mapped["User"]             = relationship("User",       foreign_keys=[requested_by])
    approver:    Mapped[Optional["User"]]   = relationship("User",       foreign_keys=[approved_by])
    lines:       Mapped[List["PurchaseRequestLine"]] = relationship(
        "PurchaseRequestLine", back_populates="pr", cascade="all, delete-orphan"
    )


class PurchaseRequestLine(Base):
    __tablename__ = "purchase_request_lines"

    id: Mapped[int]                  = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[int]               = mapped_column(Integer, ForeignKey("purchase_requests.id"), nullable=False)
    product_id: Mapped[int]          = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    uom_id: Mapped[int]              = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    qty_requested: Mapped[float]     = mapped_column(nullable=False)
    qty_approved: Mapped[float]      = mapped_column(default=0)
    estimated_price: Mapped[float]   = mapped_column(default=0)
    notes: Mapped[Optional[str]]     = mapped_column(Text)

    pr:      Mapped["PurchaseRequest"]  = relationship("PurchaseRequest", back_populates="lines")
    product: Mapped["Product"]          = relationship("Product",         foreign_keys=[product_id])
    uom:     Mapped["UnitOfMeasure"]    = relationship("UnitOfMeasure",   foreign_keys=[uom_id])


# ─────────────────────────────────────────────────────────────
# PURCHASE ORDER
# ─────────────────────────────────────────────────────────────
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]              = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]               = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    pr_id: Mapped[Optional[int]]         = mapped_column(Integer, ForeignKey("purchase_requests.id"))
    po_number: Mapped[str]               = mapped_column(String(30), nullable=False, unique=True)
    vendor_id: Mapped[int]               = mapped_column(Integer, ForeignKey("vendors.id"), nullable=False)
    order_date: Mapped[datetime]         = mapped_column(Date, nullable=False)
    expected_date: Mapped[Optional[datetime]] = mapped_column(Date)
    currency_code: Mapped[str]           = mapped_column(String(10), default="IDR")
    exchange_rate: Mapped[float]         = mapped_column(default=1)
    subtotal: Mapped[float]              = mapped_column(default=0)
    tax_amount: Mapped[float]            = mapped_column(default=0)
    discount_amount: Mapped[float]       = mapped_column(default=0)
    shipping_cost: Mapped[float]         = mapped_column(default=0)
    total_amount: Mapped[float]          = mapped_column(default=0)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(100))
    shipping_method: Mapped[Optional[str]] = mapped_column(String(100))
    warehouse_id: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("warehouses.id"))
    status: Mapped[str]                  = mapped_column(
        SAEnum("DRAFT","SENT","CONFIRMED","PARTIAL","RECEIVED","CANCELLED"),
        default="DRAFT"
    )
    notes: Mapped[Optional[str]]         = mapped_column(Text)
    created_by: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("users.id"))
    approved_by: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow,
                                                          onupdate=datetime.utcnow)

    branch:    Mapped["Branch"]               = relationship("Branch",   foreign_keys=[branch_id])
    vendor:    Mapped["Vendor"]               = relationship("Vendor",   foreign_keys=[vendor_id])
    warehouse: Mapped[Optional["Warehouse"]]  = relationship("Warehouse",foreign_keys=[warehouse_id])
    pr:        Mapped[Optional["PurchaseRequest"]] = relationship("PurchaseRequest", foreign_keys=[pr_id])
    creator:   Mapped[Optional["User"]]       = relationship("User",     foreign_keys=[created_by])
    approver:  Mapped[Optional["User"]]       = relationship("User",     foreign_keys=[approved_by])
    lines:     Mapped[List["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine", back_populates="po", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int]                  = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int]               = mapped_column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    product_id: Mapped[int]          = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    uom_id: Mapped[int]              = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    qty_ordered: Mapped[float]       = mapped_column(nullable=False)
    qty_received: Mapped[float]      = mapped_column(default=0)
    unit_price: Mapped[float]        = mapped_column(nullable=False)
    tax_pct: Mapped[float]           = mapped_column(default=0)
    discount_pct: Mapped[float]      = mapped_column(default=0)
    notes: Mapped[Optional[str]]     = mapped_column(Text)

    po:      Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="lines")
    product: Mapped["Product"]       = relationship("Product",       foreign_keys=[product_id])
    uom:     Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure", foreign_keys=[uom_id])


# ─────────────────────────────────────────────────────────────
# GOODS RECEIPT — updated model (tambahkan ke __init__.py)
# Ganti class GoodsReceipt yang lama dengan ini
# ─────────────────────────────────────────────────────────────
class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[int]                       = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]               = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]                = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    gr_number: Mapped[str]                = mapped_column(String(30), nullable=False, unique=True)
    po_id: Mapped[int]                    = mapped_column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    receipt_date: Mapped[datetime]        = mapped_column(Date, nullable=False)
    warehouse_id: Mapped[int]             = mapped_column(Integer, ForeignKey("warehouses.id"), nullable=False)
    vendor_do_number: Mapped[Optional[str]] = mapped_column(String(80))
    status: Mapped[str]                   = mapped_column(
        SAEnum("DRAFT", "CONFIRMED", "CANCELLED"), default="DRAFT"
    )

    # ── Field baru ────────────────────────────────────────────
    is_replacement: Mapped[bool]          = mapped_column(
        Boolean, default=False,
        comment="True = GR untuk barang pengganti dari purchase return"
    )
    return_id: Mapped[Optional[int]]      = mapped_column(
        Integer, ForeignKey("purchase_returns.id"), nullable=True,
        comment="FK ke purchase_returns jika is_replacement=True"
    )
    # ─────────────────────────────────────────────────────────

    notes: Mapped[Optional[str]]          = mapped_column(Text)
    received_by: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime]          = mapped_column(DateTime, default=datetime.utcnow)

    branch:       Mapped["Branch"]              = relationship("Branch",          foreign_keys=[branch_id])
    po:           Mapped["PurchaseOrder"]       = relationship("PurchaseOrder",   foreign_keys=[po_id])
    warehouse:    Mapped["Warehouse"]           = relationship("Warehouse",       foreign_keys=[warehouse_id])
    receiver:     Mapped[Optional["User"]]      = relationship("User",            foreign_keys=[received_by])
    purchase_return: Mapped[Optional["PurchaseReturn"]] = relationship(
        "PurchaseReturn", foreign_keys=[return_id]
    )
    lines: Mapped[List["GoodsReceiptLine"]] = relationship(
        "GoodsReceiptLine", back_populates="gr", cascade="all, delete-orphan"
    )

# SQLite migration (jalankan sekali):
# ALTER TABLE goods_receipts ADD COLUMN is_replacement INTEGER DEFAULT 0;
# ALTER TABLE goods_receipts ADD COLUMN return_id INTEGER REFERENCES purchase_returns(id);

class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"

    id: Mapped[int]                        = mapped_column(Integer, primary_key=True, autoincrement=True)
    gr_id: Mapped[int]                     = mapped_column(Integer, ForeignKey("goods_receipts.id"), nullable=False)
    pol_id: Mapped[int]                    = mapped_column(Integer, ForeignKey("purchase_order_lines.id"), nullable=False)
    product_id: Mapped[int]                = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    uom_id: Mapped[int]                    = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    qty_received: Mapped[float]            = mapped_column(nullable=False)
    qty_rejected: Mapped[float]            = mapped_column(default=0)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    lot_number: Mapped[Optional[str]]       = mapped_column(String(80))
    expiry_date: Mapped[Optional[datetime]] = mapped_column(Date)
    unit_cost: Mapped[float]               = mapped_column(default=0)
    serial_numbers_input: Mapped[Optional[str]] = mapped_column(Text, comment="JSON array SN")

    gr:      Mapped["GoodsReceipt"]       = relationship("GoodsReceipt", back_populates="lines")
    pol:     Mapped["PurchaseOrderLine"]  = relationship("PurchaseOrderLine", foreign_keys=[pol_id])
    product: Mapped["Product"]            = relationship("Product",          foreign_keys=[product_id])
    uom:     Mapped["UnitOfMeasure"]      = relationship("UnitOfMeasure",    foreign_keys=[uom_id])


# ─────────────────────────────────────────────────────────────
# STOCK BALANCE (Saldo stok per produk per gudang)
# ─────────────────────────────────────────────────────────────
class StockBalance(Base):
    __tablename__ = "stock_balances"

    id: Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int]       = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    branch_id: Mapped[int]        = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    warehouse_id: Mapped[int]     = mapped_column(Integer, ForeignKey("warehouses.id"), nullable=False)
    lot_number: Mapped[Optional[str]] = mapped_column(String(80))
    qty_on_hand: Mapped[float]    = mapped_column(default=0)
    qty_reserved: Mapped[float]   = mapped_column(default=0)
    avg_cost: Mapped[float]       = mapped_column(default=0)
    last_movement_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", "lot_number",
                         name="uq_stock"),
    )

    product:   Mapped["Product"]   = relationship("Product",   foreign_keys=[product_id])
    branch:    Mapped["Branch"]    = relationship("Branch",    foreign_keys=[branch_id])
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[warehouse_id])


# ─────────────────────────────────────────────────────────────
# SERIAL NUMBERS
# ─────────────────────────────────────────────────────────────
class SerialNumber(Base):
    __tablename__ = "serial_numbers"

    id: Mapped[int]                        = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int]                = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    serial_number: Mapped[str]             = mapped_column(String(100), nullable=False)
    lot_number: Mapped[Optional[str]]      = mapped_column(String(80))
    gr_line_id: Mapped[Optional[int]]      = mapped_column(Integer, ForeignKey("goods_receipt_lines.id"))
    current_branch_id: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("branches.id"))
    current_warehouse_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("warehouses.id"))
    status: Mapped[str]                    = mapped_column(
        SAEnum("IN_STOCK","RESERVED","SOLD","RETURNED","DEFECTIVE","LOST"),
        default="IN_STOCK"
    )
    created_at: Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("product_id", "serial_number", name="uq_serial"),)

    product:   Mapped["Product"]            = relationship("Product",   foreign_keys=[product_id])
    gr_line:   Mapped[Optional["GoodsReceiptLine"]] = relationship("GoodsReceiptLine", foreign_keys=[gr_line_id])
    branch:    Mapped[Optional["Branch"]]   = relationship("Branch",    foreign_keys=[current_branch_id])
    warehouse: Mapped[Optional["Warehouse"]]= relationship("Warehouse", foreign_keys=[current_warehouse_id])
    replaced_serial_id: Mapped[Optional[int]]         = mapped_column(Integer, ForeignKey("serial_numbers.id"), nullable=True)


# ─────────────────────────────────────────────────────────────
# STOCK TRANSFER
# ─────────────────────────────────────────────────────────────
class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[int]                  = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]          = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    transfer_number: Mapped[str]     = mapped_column(String(30), nullable=False, unique=True)
    transfer_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    from_branch_id: Mapped[int]      = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    from_warehouse_id: Mapped[int]   = mapped_column(Integer, ForeignKey("warehouses.id"), nullable=False)
    to_branch_id: Mapped[int]        = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    to_warehouse_id: Mapped[int]     = mapped_column(Integer, ForeignKey("warehouses.id"), nullable=False)
    status: Mapped[str]              = mapped_column(
        SAEnum("DRAFT","APPROVED","IN_TRANSIT","COMPLETED","CANCELLED"), default="DRAFT"
    )
    requested_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    approved_by: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    shipped_at: Mapped[Optional[datetime]]  = mapped_column(DateTime)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100))
    shipping_method: Mapped[Optional[str]]  = mapped_column(String(100))
    notes: Mapped[Optional[str]]     = mapped_column(Text)
    created_at: Mapped[datetime]     = mapped_column(DateTime, default=datetime.utcnow)

    from_branch:    Mapped["Branch"]    = relationship("Branch",    foreign_keys=[from_branch_id])
    to_branch:      Mapped["Branch"]    = relationship("Branch",    foreign_keys=[to_branch_id])
    from_warehouse: Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse:   Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[to_warehouse_id])
    lines: Mapped[List["StockTransferLine"]] = relationship(
        "StockTransferLine", back_populates="transfer", cascade="all, delete-orphan"
    )


class StockTransferLine(Base):
    __tablename__ = "stock_transfer_lines"

    id: Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[int]     = mapped_column(Integer, ForeignKey("stock_transfers.id"), nullable=False)
    product_id: Mapped[int]      = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    uom_id: Mapped[int]          = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    lot_number: Mapped[Optional[str]] = mapped_column(String(80))
    qty_requested: Mapped[float] = mapped_column(nullable=False)
    qty_shipped: Mapped[float]   = mapped_column(default=0)
    qty_received: Mapped[float]  = mapped_column(default=0)
    unit_cost: Mapped[float]     = mapped_column(default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    transfer: Mapped["StockTransfer"]    = relationship("StockTransfer", back_populates="lines")
    product:  Mapped["Product"]          = relationship("Product",  foreign_keys=[product_id])
    uom:      Mapped["UnitOfMeasure"]    = relationship("UnitOfMeasure", foreign_keys=[uom_id])


# ─────────────────────────────────────────────────────────────
# STOCK OPNAME
# ─────────────────────────────────────────────────────────────
class StockOpname(Base):
    __tablename__ = "stock_opnames"

    id: Mapped[int]                  = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]          = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]           = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    warehouse_id: Mapped[int]        = mapped_column(Integer, ForeignKey("warehouses.id"), nullable=False)
    opname_number: Mapped[str]       = mapped_column(String(30), nullable=False, unique=True)
    opname_date: Mapped[date_type]   = mapped_column(Date, nullable=False)
    status: Mapped[str]              = mapped_column(
        SAEnum("DRAFT","IN_PROGRESS","COUNTED","VALIDATED","POSTED"), default="DRAFT"
    )
    notes: Mapped[Optional[str]]     = mapped_column(Text)
    created_by: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("users.id"))
    validated_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    posted_by: Mapped[Optional[int]]     = mapped_column(Integer, ForeignKey("users.id"))
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime]     = mapped_column(DateTime, default=datetime.utcnow)

    branch:    Mapped["Branch"]    = relationship("Branch",    foreign_keys=[branch_id])
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[warehouse_id])
    lines: Mapped[List["StockOpnameLine"]] = relationship(
        "StockOpnameLine", back_populates="opname", cascade="all, delete-orphan"
    )


class StockOpnameLine(Base):
    __tablename__ = "stock_opname_lines"

    id: Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    opname_id: Mapped[int]       = mapped_column(Integer, ForeignKey("stock_opnames.id"), nullable=False)
    product_id: Mapped[int]      = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    lot_number: Mapped[Optional[str]] = mapped_column(String(80))
    qty_system: Mapped[float]    = mapped_column(default=0)
    qty_physical: Mapped[float]  = mapped_column(default=0)
    unit_cost: Mapped[float]     = mapped_column(default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    counted_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))

    opname:  Mapped["StockOpname"] = relationship("StockOpname", back_populates="lines")
    product: Mapped["Product"]     = relationship("Product", foreign_keys=[product_id])


# ─────────────────────────────────────────────────────────────
# CUSTOMER / PARTNER ASSIGNMENT HISTORY
# Catat setiap perpindahan cabang, sales PIC, atau alamat
# ─────────────────────────────────────────────────────────────
class CustomerAssignmentHistory(Base):
    __tablename__ = "customer_assignment_history"

    id: Mapped[int]                     = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int]            = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    change_type: Mapped[str]            = mapped_column(
        SAEnum("BRANCH","SALES","ADDRESS","OTHER"), nullable=False
    )
    old_value: Mapped[Optional[str]]    = mapped_column(Text)
    new_value: Mapped[Optional[str]]    = mapped_column(Text)
    notes: Mapped[Optional[str]]        = mapped_column(Text)
    changed_by: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("users.id"))
    changed_at: Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow)

    customer:   Mapped["Customer"] = relationship("Customer", foreign_keys=[customer_id])
    changed_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[changed_by])


class PartnerAssignmentHistory(Base):
    __tablename__ = "partner_assignment_history"

    id: Mapped[int]                     = mapped_column(Integer, primary_key=True, autoincrement=True)
    partner_id: Mapped[int]             = mapped_column(Integer, ForeignKey("partners.id"), nullable=False)
    change_type: Mapped[str]            = mapped_column(
        SAEnum("BRANCH","ADDRESS","OTHER"), nullable=False
    )
    old_value: Mapped[Optional[str]]    = mapped_column(Text)
    new_value: Mapped[Optional[str]]    = mapped_column(Text)
    notes: Mapped[Optional[str]]        = mapped_column(Text)
    changed_by: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("users.id"))
    changed_at: Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow)

    partner:    Mapped["Partner"] = relationship("Partner", foreign_keys=[partner_id])
    changed_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[changed_by])

# ─────────────────────────────────────────────────────────────
# PURCHASE RETURN  (Retur Barang ke Vendor)
# ─────────────────────────────────────────────────────────────
class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"

    id: Mapped[int]                       = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]               = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]                = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    return_number: Mapped[str]            = mapped_column(String(30), nullable=False, unique=True)

    gr_id: Mapped[int]                    = mapped_column(Integer, ForeignKey("goods_receipts.id"), nullable=False)
    vendor_id: Mapped[int]                = mapped_column(Integer, ForeignKey("vendors.id"), nullable=False)
    warehouse_id: Mapped[int]             = mapped_column(Integer, ForeignKey("warehouses.id"), nullable=False)

    return_date: Mapped[date_type]        = mapped_column(Date, nullable=False)
    return_reason: Mapped[str]            = mapped_column(
        SAEnum("DEFECTIVE", "WRONG_ITEM", "EXCESS_QTY", "OTHER"),
        default="DEFECTIVE"
    )
    status: Mapped[str]                   = mapped_column(
        SAEnum("DRAFT", "CONFIRMED", "SENT", "COMPLETED", "CANCELLED"),
        default="DRAFT"
    )

    # ── Resolusi dari vendor ──────────────────────────────────
    # Diisi saat status → COMPLETED
    resolution: Mapped[Optional[str]]     = mapped_column(
        SAEnum("REPLACEMENT", "CREDIT_NOTE", "COMBINATION"),
        nullable=True,
        comment="REPLACEMENT=barang diganti, CREDIT_NOTE=refund/nota kredit, COMBINATION=sebagian keduanya"
    )
    # Untuk REPLACEMENT / COMBINATION: PO akan di-reopen (status → PARTIAL)
    # agar bisa dibuat GR baru
    replacement_qty: Mapped[Optional[float]] = mapped_column(
        default=0,
        comment="Total qty yang akan diganti barang baru oleh vendor"
    )
    # Untuk CREDIT_NOTE / COMBINATION
    credit_note_number: Mapped[Optional[str]]  = mapped_column(String(80),
        comment="Nomor nota kredit dari vendor")
    credit_note_amount: Mapped[Optional[float]] = mapped_column(
        default=0,
        comment="Nilai kredit yang diberikan vendor (Rp)"
    )
    credit_note_date: Mapped[Optional[date_type]] = mapped_column(Date)

    total_amount: Mapped[float]           = mapped_column(default=0)
    notes: Mapped[Optional[str]]          = mapped_column(Text)
    created_by: Mapped[Optional[int]]     = mapped_column(Integer, ForeignKey("users.id"))
    confirmed_by: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("users.id"))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_by: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("users.id"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime]          = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]          = mapped_column(DateTime, default=datetime.utcnow,
                                                           onupdate=datetime.utcnow)

    company:      Mapped["Company"]          = relationship("Company",      foreign_keys=[company_id])
    branch:       Mapped["Branch"]           = relationship("Branch",       foreign_keys=[branch_id])
    gr:           Mapped["GoodsReceipt"]     = relationship("GoodsReceipt", foreign_keys=[gr_id])
    vendor:       Mapped["Vendor"]           = relationship("Vendor",       foreign_keys=[vendor_id])
    warehouse:    Mapped["Warehouse"]        = relationship("Warehouse",    foreign_keys=[warehouse_id])
    creator:      Mapped[Optional["User"]]   = relationship("User",         foreign_keys=[created_by])
    confirmer:    Mapped[Optional["User"]]   = relationship("User",         foreign_keys=[confirmed_by])
    completer:    Mapped[Optional["User"]]   = relationship("User",         foreign_keys=[completed_by])
    lines:        Mapped[List["PurchaseReturnLine"]] = relationship(
        "PurchaseReturnLine", back_populates="purchase_return", cascade="all, delete-orphan"
    )


class PurchaseReturnLine(Base):
    __tablename__ = "purchase_return_lines"

    id: Mapped[int]                       = mapped_column(Integer, primary_key=True, autoincrement=True)
    return_id: Mapped[int]                = mapped_column(Integer, ForeignKey("purchase_returns.id"), nullable=False)
    gr_line_id: Mapped[int]               = mapped_column(Integer, ForeignKey("goods_receipt_lines.id"), nullable=False)
    product_id: Mapped[int]               = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    uom_id: Mapped[int]                   = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)

    qty_return: Mapped[float]             = mapped_column(nullable=False)
    unit_cost: Mapped[float]              = mapped_column(default=0)
    serial_numbers: Mapped[Optional[str]] = mapped_column(Text, comment='JSON ["SN001","SN002"]')
    notes: Mapped[Optional[str]]          = mapped_column(Text)

    purchase_return: Mapped["PurchaseReturn"]    = relationship("PurchaseReturn", back_populates="lines")
    gr_line:         Mapped["GoodsReceiptLine"]  = relationship("GoodsReceiptLine", foreign_keys=[gr_line_id])
    product:         Mapped["Product"]           = relationship("Product",          foreign_keys=[product_id])
    uom:             Mapped["UnitOfMeasure"]      = relationship("UnitOfMeasure",   foreign_keys=[uom_id])



# ─────────────────────────────────────────────────────────────
# TAX RATES
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# TAX RATES — Master tarif pajak
# ─────────────────────────────────────────────────────────────
class TaxRate(Base):
    __tablename__ = "tax_rates"

    id: Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]      = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    code: Mapped[str]            = mapped_column(String(30), nullable=False)
    name: Mapped[str]            = mapped_column(String(150), nullable=False)
    tax_type: Mapped[str]        = mapped_column(
        SAEnum("PPN","PPH21","PPH23","CUSTOM"), nullable=False
    )
    rate: Mapped[float]          = mapped_column(nullable=False, comment="Persentase, misal 11.0")
    is_inclusive: Mapped[bool]   = mapped_column(Boolean, default=False,
                                                  comment="True=harga sudah termasuk pajak")
    applies_to: Mapped[str]      = mapped_column(
        SAEnum("SALES","PURCHASE","BOTH"), default="BOTH"
    )
    is_default: Mapped[bool]     = mapped_column(Boolean, default=False)
    is_active: Mapped[bool]      = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_tax_rate_code"),)

    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])


# ─────────────────────────────────────────────────────────────
# SALES ORDER
# ─────────────────────────────────────────────────────────────
class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]             = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    so_number: Mapped[str]             = mapped_column(String(30), nullable=False, unique=True)
    order_date: Mapped[date_type]      = mapped_column(Date, nullable=False)
    customer_id: Mapped[int]           = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    sales_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    warehouse_id: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("warehouses.id"))
    tax_rate_id: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("tax_rates.id"))
    currency_code: Mapped[str]         = mapped_column(String(10), default="IDR")
    subtotal: Mapped[float]            = mapped_column(default=0)
    discount_amount: Mapped[float]     = mapped_column(default=0)
    tax_amount: Mapped[float]          = mapped_column(default=0)
    shipping_cost: Mapped[float]       = mapped_column(default=0)
    total_amount: Mapped[float]        = mapped_column(default=0)
    shipping_address: Mapped[Optional[str]] = mapped_column(Text)
    shipping_city: Mapped[Optional[str]]    = mapped_column(String(100))
    shipping_method: Mapped[Optional[str]]  = mapped_column(String(100))
    expected_delivery: Mapped[Optional[date_type]] = mapped_column(Date)
    status: Mapped[str]                = mapped_column(
        SAEnum("DRAFT","CONFIRMED","PICKING","PARTIAL_DELIVERED",
               "DELIVERED","INVOICED","CANCELLED"), default="DRAFT"
    )
    payment_status: Mapped[str]        = mapped_column(
        SAEnum("UNPAID","PARTIAL","PAID","REFUNDED"), default="UNPAID"
    )
    notes: Mapped[Optional[str]]       = mapped_column(Text)
    created_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow,
                                                       onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("so_number", name="uq_so_number"),)

    company:    Mapped["Company"]              = relationship("Company",   foreign_keys=[company_id])
    branch:     Mapped["Branch"]               = relationship("Branch",    foreign_keys=[branch_id])
    customer:   Mapped["Customer"]             = relationship("Customer",  foreign_keys=[customer_id])
    sales_user: Mapped[Optional["User"]]       = relationship("User",      foreign_keys=[sales_user_id])
    warehouse:  Mapped[Optional["Warehouse"]]  = relationship("Warehouse", foreign_keys=[warehouse_id])
    tax_rate:   Mapped[Optional["TaxRate"]]    = relationship("TaxRate",   foreign_keys=[tax_rate_id])
    lines:      Mapped[List["SalesOrderLine"]] = relationship(
        "SalesOrderLine", back_populates="so", cascade="all, delete-orphan"
    )


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"

    id: Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    so_id: Mapped[int]           = mapped_column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    product_id: Mapped[int]      = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    uom_id: Mapped[int]          = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    tax_rate_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tax_rates.id"))
    qty_ordered: Mapped[float]   = mapped_column(nullable=False)
    qty_delivered: Mapped[float] = mapped_column(default=0)
    unit_price: Mapped[float]    = mapped_column(nullable=False)
    discount_pct: Mapped[float]  = mapped_column(default=0)
    tax_pct: Mapped[float]       = mapped_column(default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    so:       Mapped["SalesOrder"]          = relationship("SalesOrder", back_populates="lines")
    product:  Mapped["Product"]             = relationship("Product",       foreign_keys=[product_id])
    uom:      Mapped["UnitOfMeasure"]       = relationship("UnitOfMeasure", foreign_keys=[uom_id])
    tax_rate: Mapped[Optional["TaxRate"]]   = relationship("TaxRate",       foreign_keys=[tax_rate_id])


# ─────────────────────────────────────────────────────────────
# DELIVERY ORDER
# ─────────────────────────────────────────────────────────────
class DeliveryOrder(Base):
    __tablename__ = "delivery_orders"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]             = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    do_number: Mapped[str]             = mapped_column(String(30), nullable=False, unique=True)
    so_id: Mapped[int]                 = mapped_column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    delivery_date: Mapped[date_type]   = mapped_column(Date, nullable=False)
    warehouse_id: Mapped[int]          = mapped_column(Integer, ForeignKey("warehouses.id"), nullable=False)
    shipping_method: Mapped[Optional[str]] = mapped_column(String(100))
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100))
    courier: Mapped[Optional[str]]     = mapped_column(String(100))
    shipped_at: Mapped[Optional[datetime]]   = mapped_column(DateTime)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str]                = mapped_column(
        SAEnum("DRAFT","SHIPPED","DELIVERED","RETURNED","CANCELLED"), default="DRAFT"
    )
    notes: Mapped[Optional[str]]       = mapped_column(Text)
    created_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("do_number", name="uq_do_number"),)

    company:   Mapped["Company"]    = relationship("Company",   foreign_keys=[company_id])
    branch:    Mapped["Branch"]     = relationship("Branch",    foreign_keys=[branch_id])
    so:        Mapped["SalesOrder"] = relationship("SalesOrder",foreign_keys=[so_id])
    warehouse: Mapped["Warehouse"]  = relationship("Warehouse", foreign_keys=[warehouse_id])
    lines:     Mapped[List["DeliveryOrderLine"]] = relationship(
        "DeliveryOrderLine", back_populates="do_obj", cascade="all, delete-orphan"
    )


class DeliveryOrderLine(Base):
    __tablename__ = "delivery_order_lines"

    id: Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    do_id: Mapped[int]           = mapped_column(Integer, ForeignKey("delivery_orders.id"), nullable=False)
    sol_id: Mapped[int]          = mapped_column(Integer, ForeignKey("sales_order_lines.id"), nullable=False)
    product_id: Mapped[int]      = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    uom_id: Mapped[int]          = mapped_column(Integer, ForeignKey("unit_of_measures.id"), nullable=False)
    qty_shipped: Mapped[float]   = mapped_column(nullable=False)
    lot_number: Mapped[Optional[str]] = mapped_column(String(80))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    do_obj:  Mapped["DeliveryOrder"]  = relationship("DeliveryOrder", back_populates="lines")
    sol:     Mapped["SalesOrderLine"] = relationship("SalesOrderLine", foreign_keys=[sol_id])
    product: Mapped["Product"]        = relationship("Product",        foreign_keys=[product_id])
    uom:     Mapped["UnitOfMeasure"]  = relationship("UnitOfMeasure",  foreign_keys=[uom_id])


# ─────────────────────────────────────────────────────────────
# INVOICE & PAYMENT
# ─────────────────────────────────────────────────────────────
class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]             = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    invoice_number: Mapped[str]        = mapped_column(String(30), nullable=False, unique=True)
    invoice_type: Mapped[str]          = mapped_column(SAEnum("SALES","PURCHASE","RETURN"), default="SALES")
    invoice_date: Mapped[date_type]    = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date_type]] = mapped_column(Date)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id"))
    so_id: Mapped[Optional[int]]       = mapped_column(Integer, ForeignKey("sales_orders.id"))
    do_id: Mapped[Optional[int]]       = mapped_column(Integer, ForeignKey("delivery_orders.id"))
    tax_rate_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tax_rates.id"))
    efaktur_number: Mapped[Optional[str]]   = mapped_column(String(50))
    efaktur_status: Mapped[Optional[str]]   = mapped_column(
        SAEnum("PENDING","UPLOADED","APPROVED","REJECTED"), default=None
    )
    subtotal: Mapped[float]            = mapped_column(default=0)
    tax_amount: Mapped[float]          = mapped_column(default=0)
    discount_amount: Mapped[float]     = mapped_column(default=0)
    total_amount: Mapped[float]        = mapped_column(default=0)
    paid_amount: Mapped[float]         = mapped_column(default=0)
    status: Mapped[str]                = mapped_column(
        SAEnum("DRAFT","SENT","PARTIAL","PAID","OVERDUE","CANCELLED"), default="DRAFT"
    )
    notes: Mapped[Optional[str]]       = mapped_column(Text)
    created_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("invoice_number", name="uq_invoice_number"),)

    company:   Mapped["Company"]              = relationship("Company",  foreign_keys=[company_id])
    branch:    Mapped["Branch"]               = relationship("Branch",   foreign_keys=[branch_id])
    customer:  Mapped[Optional["Customer"]]   = relationship("Customer", foreign_keys=[customer_id])
    so:        Mapped[Optional["SalesOrder"]] = relationship("SalesOrder", foreign_keys=[so_id])
    do:        Mapped[Optional["DeliveryOrder"]] = relationship("DeliveryOrder", foreign_keys=[do_id])
    tax_rate:  Mapped[Optional["TaxRate"]]    = relationship("TaxRate",  foreign_keys=[tax_rate_id])
    payments:  Mapped[List["Payment"]]        = relationship("Payment",  back_populates="invoice")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]             = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    payment_number: Mapped[str]        = mapped_column(String(30), nullable=False, unique=True)
    payment_date: Mapped[date_type]    = mapped_column(Date, nullable=False)
    payment_type: Mapped[str]          = mapped_column(SAEnum("RECEIVED","SENT"), default="RECEIVED")
    invoice_id: Mapped[int]            = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount: Mapped[float]              = mapped_column(nullable=False)
    payment_method: Mapped[str]        = mapped_column(
        SAEnum("CASH","BANK_TRANSFER","CREDIT_CARD","CHEQUE","OTHER"), default="BANK_TRANSFER"
    )
    reference_number: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]]       = mapped_column(Text)
    confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("payment_number", name="uq_payment_number"),)

    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])
    branch:  Mapped["Branch"]  = relationship("Branch",  foreign_keys=[branch_id])
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")


# ─────────────────────────────────────────────────────────────
# TAX INVOICE (Faktur Pajak / e-Faktur)
# ─────────────────────────────────────────────────────────────
class TaxInvoice(Base):
    __tablename__ = "tax_invoices"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    invoice_id: Mapped[int]            = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False)
    tax_invoice_number: Mapped[str]    = mapped_column(String(50), nullable=False, unique=True)
    tax_invoice_date: Mapped[date_type]= mapped_column(Date, nullable=False)
    tax_type: Mapped[str]              = mapped_column(SAEnum("PPN","PPH23"), default="PPN")
    dpp: Mapped[float]                 = mapped_column(default=0, comment="Dasar Pengenaan Pajak")
    tax_rate: Mapped[float]            = mapped_column(default=11.0)
    tax_amount: Mapped[float]          = mapped_column(default=0)
    npwp_lawan: Mapped[Optional[str]]  = mapped_column(String(20), comment="NPWP pelanggan/vendor")
    nama_lawan: Mapped[Optional[str]]  = mapped_column(String(200))
    status: Mapped[str]                = mapped_column(
        SAEnum("DRAFT","UPLOADED","APPROVED","REJECTED","AMENDED"), default="DRAFT"
    )
    upload_date: Mapped[Optional[date_type]] = mapped_column(Date)
    notes: Mapped[Optional[str]]       = mapped_column(Text)
    created_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])
    invoice: Mapped["Invoice"] = relationship("Invoice", foreign_keys=[invoice_id])


# ─────────────────────────────────────────────────────────────
# TAX WITHHOLDING (PPh 21 / PPh 23)
# ─────────────────────────────────────────────────────────────
class TaxWithholding(Base):
    __tablename__ = "tax_withholdings"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int]             = mapped_column(Integer, ForeignKey("branches.id"), nullable=False)
    wh_number: Mapped[str]             = mapped_column(String(30), nullable=False, unique=True)
    tax_type: Mapped[str]              = mapped_column(SAEnum("PPH21","PPH23"), nullable=False)
    period_year: Mapped[int]           = mapped_column(Integer, nullable=False)
    period_month: Mapped[int]          = mapped_column(Integer, nullable=False)
    # PPh 23: terkait vendor/invoice
    vendor_id: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("vendors.id"))
    invoice_ref: Mapped[Optional[str]] = mapped_column(String(100))
    # PPh 21: terkait karyawan
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.id"))
    npwp: Mapped[Optional[str]]        = mapped_column(String(20))
    nama: Mapped[Optional[str]]        = mapped_column(String(200))
    bruto: Mapped[float]               = mapped_column(default=0, comment="Penghasilan bruto")
    tax_rate: Mapped[float]            = mapped_column(default=0)
    tax_amount: Mapped[float]          = mapped_column(default=0)
    status: Mapped[str]                = mapped_column(
        SAEnum("DRAFT","FINAL","REPORTED"), default="DRAFT"
    )
    notes: Mapped[Optional[str]]       = mapped_column(Text)
    created_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)

    company:  Mapped["Company"]           = relationship("Company",  foreign_keys=[company_id])
    branch:   Mapped["Branch"]            = relationship("Branch",   foreign_keys=[branch_id])
    vendor:   Mapped[Optional["Vendor"]]  = relationship("Vendor",   foreign_keys=[vendor_id])


class CommissionScheme(Base):
    """
    Skema komisi — bisa berbeda per partner.
    Satu partner bisa punya beberapa skema (misal: skema untuk SO pertama
    berbeda dengan SO repeat).
    """
    __tablename__ = "commission_schemes"

    id: Mapped[int]                    = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]            = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)

    # Bisa untuk partner atau customer referral
    scheme_for: Mapped[str]            = mapped_column(
        SAEnum("PARTNER", "CUSTOMER_REFERRAL"),
        default="PARTNER",
        comment="PARTNER = mitra, CUSTOMER_REFERRAL = customer yang refer customer lain"
    )
    partner_id: Mapped[Optional[int]]  = mapped_column(
        Integer, ForeignKey("partners.id"), nullable=True,
        comment="NULL = skema default untuk semua partner"
    )
    referring_customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=True,
        comment="NULL = skema default untuk semua customer referral"
    )

    name: Mapped[str]                  = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # ── Tipe komisi ───────────────────────────────────────────
    commission_type: Mapped[str]       = mapped_column(
        SAEnum("PERCENTAGE", "FLAT", "COMBINATION"),
        default="PERCENTAGE",
        comment="PERCENTAGE=% dari SO, FLAT=nominal per customer, COMBINATION=keduanya"
    )

    # Untuk PERCENTAGE / COMBINATION
    commission_pct: Mapped[float]      = mapped_column(
        default=0,
        comment="% dari total SO (mis: 5.00 = 5%)"
    )
    # Batas maksimal komisi dari persentase (0 = tidak ada batas)
    max_commission_per_so: Mapped[float] = mapped_column(
        default=0,
        comment="Batas maksimal komisi per SO (0 = tidak ada batas)"
    )

    # Untuk FLAT / COMBINATION
    flat_amount: Mapped[float]         = mapped_column(
        default=0,
        comment="Nominal flat per customer baru (Rp)"
    )

    # ── Kondisi berlaku ───────────────────────────────────────
    apply_on: Mapped[str]              = mapped_column(
        SAEnum("ALL_SO", "FIRST_SO_ONLY", "REPEAT_SO_ONLY"),
        default="ALL_SO",
        comment="ALL_SO=semua SO, FIRST_SO_ONLY=hanya SO pertama customer, REPEAT_SO_ONLY=SO repeat"
    )
    min_so_amount: Mapped[float]       = mapped_column(
        default=0,
        comment="Minimum nilai SO agar komisi berlaku (0 = tidak ada minimum)"
    )

    valid_from: Mapped[Optional[date_type]]  = mapped_column(Date)
    valid_until: Mapped[Optional[date_type]] = mapped_column(Date)
    is_active: Mapped[bool]            = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]]  = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow,
                                                        onupdate=datetime.utcnow)

    company:    Mapped["Company"]              = relationship("Company",  foreign_keys=[company_id])
    partner:    Mapped[Optional["Partner"]]    = relationship("Partner",  foreign_keys=[partner_id])
    ref_customer: Mapped[Optional["Customer"]] = relationship("Customer", foreign_keys=[referring_customer_id])
    creator:    Mapped[Optional["User"]]       = relationship("User",     foreign_keys=[created_by])
    transactions: Mapped[List["CommissionTransaction"]] = relationship(
        "CommissionTransaction", back_populates="scheme", cascade="all, delete-orphan"
    )


class CommissionTransaction(Base):
    """
    Catatan komisi per transaksi SO.
    Di-generate otomatis saat SO di-invoice/lunas.
    """
    __tablename__ = "commission_transactions"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]              = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    scheme_id: Mapped[int]               = mapped_column(Integer, ForeignKey("commission_schemes.id"), nullable=False)

    # Siapa yang dapat komisi
    recipient_type: Mapped[str]          = mapped_column(
        SAEnum("PARTNER", "CUSTOMER_REFERRAL"),
        nullable=False,
    )
    partner_id: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("partners.id"))
    referring_customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id"))

    # Transaksi sumber
    so_id: Mapped[int]                   = mapped_column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    customer_id: Mapped[int]             = mapped_column(Integer, ForeignKey("customers.id"), nullable=False,
                                                          comment="Customer yang melakukan SO")
    invoice_id: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("invoices.id"))

    # Nilai komisi
    so_amount: Mapped[float]             = mapped_column(default=0, comment="Nilai SO yang jadi dasar komisi")
    commission_pct: Mapped[float]        = mapped_column(default=0)
    commission_from_pct: Mapped[float]   = mapped_column(default=0, comment="Komisi dari persentase")
    flat_amount: Mapped[float]           = mapped_column(default=0)
    total_commission: Mapped[float]      = mapped_column(default=0, comment="Total komisi = pct + flat")

    # Status pembayaran komisi
    status: Mapped[str]                  = mapped_column(
        SAEnum("PENDING", "APPROVED", "PAID", "CANCELLED"),
        default="PENDING",
        comment="PENDING=belum dibayar, APPROVED=disetujui, PAID=sudah dibayar"
    )
    is_first_so: Mapped[bool]            = mapped_column(Boolean, default=False,
                                                          comment="True jika ini SO pertama customer ini")
    notes: Mapped[Optional[str]]         = mapped_column(Text)
    paid_at: Mapped[Optional[datetime]]  = mapped_column(DateTime)
    paid_by: Mapped[Optional[int]]       = mapped_column(Integer, ForeignKey("users.id"))
    approved_by: Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)

    scheme:       Mapped["CommissionScheme"]    = relationship("CommissionScheme", back_populates="transactions")
    company:      Mapped["Company"]             = relationship("Company",   foreign_keys=[company_id])
    partner:      Mapped[Optional["Partner"]]   = relationship("Partner",   foreign_keys=[partner_id])
    ref_customer: Mapped[Optional["Customer"]]  = relationship("Customer",  foreign_keys=[referring_customer_id])
    so:           Mapped["SalesOrder"]          = relationship("SalesOrder", foreign_keys=[so_id])
    customer:     Mapped["Customer"]            = relationship("Customer",   foreign_keys=[customer_id])
    payer:        Mapped[Optional["User"]]      = relationship("User",       foreign_keys=[paid_by])
    approver:     Mapped[Optional["User"]]      = relationship("User",       foreign_keys=[approved_by])

    __table_args__ = (
        UniqueConstraint("so_id", "scheme_id", name="uq_commission_so_scheme"),
    )


class CommissionPayment(Base):
    """
    Bukti pembayaran komisi (bisa bayar beberapa transaksi sekaligus).
    """
    __tablename__ = "commission_payments"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int]              = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    payment_number: Mapped[str]          = mapped_column(String(30), nullable=False, unique=True)
    payment_date: Mapped[date_type]      = mapped_column(Date, nullable=False)

    recipient_type: Mapped[str]          = mapped_column(SAEnum("PARTNER", "CUSTOMER_REFERRAL"))
    partner_id: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("partners.id"))
    referring_customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id"))

    total_amount: Mapped[float]          = mapped_column(default=0)
    payment_method: Mapped[str]          = mapped_column(
        SAEnum("CASH", "BANK_TRANSFER", "OTHER"), default="BANK_TRANSFER"
    )
    reference_number: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]]         = mapped_column(Text)
    created_by: Mapped[Optional[int]]    = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow)

    company:      Mapped["Company"]             = relationship("Company",  foreign_keys=[company_id])
    partner:      Mapped[Optional["Partner"]]   = relationship("Partner",  foreign_keys=[partner_id])
    ref_customer: Mapped[Optional["Customer"]]  = relationship("Customer", foreign_keys=[referring_customer_id])
    creator:      Mapped[Optional["User"]]      = relationship("User",     foreign_keys=[created_by])
    items: Mapped[List["CommissionPaymentItem"]] = relationship(
        "CommissionPaymentItem", back_populates="payment", cascade="all, delete-orphan"
    )


class CommissionPaymentItem(Base):
    """Link antara CommissionPayment dan CommissionTransaction."""
    __tablename__ = "commission_payment_items"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int]              = mapped_column(Integer, ForeignKey("commission_payments.id"), nullable=False)
    transaction_id: Mapped[int]          = mapped_column(Integer, ForeignKey("commission_transactions.id"), nullable=False)
    amount: Mapped[float]                = mapped_column(nullable=False)

    payment:     Mapped["CommissionPayment"]     = relationship("CommissionPayment", back_populates="items")
    transaction: Mapped["CommissionTransaction"] = relationship("CommissionTransaction")

    __table_args__ = (
        UniqueConstraint("payment_id", "transaction_id", name="uq_cpi"),
    )

# class Invoice(Base):
#     __tablename__ = "invoices"

#     id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
#     company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
#     branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
#     invoice_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
#     invoice_type: Mapped[str] = mapped_column(SAEnum("SALES","PURCHASE","RETURN"), default="SALES")
#     invoice_date: Mapped[datetime] = mapped_column(Date, nullable=False)
#     due_date: Mapped[Optional[datetime]] = mapped_column(Date)
    
#     customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"))
#     vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id"))
#     so_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sales_orders.id"))
#     po_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_orders.id"))
    
#     subtotal: Mapped[float] = mapped_column(default=0)
#     tax_amount: Mapped[float] = mapped_column(default=0)
#     discount_amount: Mapped[float] = mapped_column(default=0)
#     total_amount: Mapped[float] = mapped_column(default=0)
#     paid_amount: Mapped[float] = mapped_column(default=0)
    
#     # Generated Column (Virtual/Stored di DB)
#     outstanding: Mapped[float] = mapped_column(
#         Computed("total_amount - paid_amount")
#     )
    
#     status: Mapped[str] = mapped_column(SAEnum("DRAFT","SENT","PARTIAL","PAID","OVERDUE","CANCELLED"), default="DRAFT")
#     notes: Mapped[Optional[str]] = mapped_column(Text)
#     created_by: Mapped[Optional[int]] = mapped_column()
#     created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

#     # Relationships
#     company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])
#     branch: Mapped["Branch"] = relationship("Branch", foreign_keys=[branch_id])
#     customer: Mapped[Optional["Customer"]] = relationship("Customer", foreign_keys=[customer_id])
#     vendor: Mapped[Optional["Vendor"]] = relationship("Vendor", foreign_keys=[vendor_id])
#     sales_order: Mapped[Optional["SalesOrder"]] = relationship("SalesOrder", foreign_keys=[so_id])
#     purchase_order: Mapped[Optional["PurchaseOrder"]] = relationship("PurchaseOrder", foreign_keys=[po_id])
    
#     payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="invoice")

