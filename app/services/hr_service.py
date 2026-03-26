from __future__ import annotations
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.models import Employee, Product, EmployeeAssignment, User, UserRole

def _to_float(val, default: float = 0.0) -> float:
    """Konversi nilai ke float dengan aman."""
    try:
        return float(str(val).strip().replace(",", ".")) if val not in (None, "", "None") else default
    except (ValueError, TypeError):
        return default

def _to_int(val, default: int = 0) -> int:
    """Konversi nilai ke int dengan aman."""
    try:
        return int(float(str(val).strip().replace(",", "."))) if val not in (None, "", "None") else default
    except (ValueError, TypeError):
        return default

def _to_date(val, default=None):
    """Konversi nilai ke date dengan aman."""
    from datetime import datetime
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y","%d-%m-%Y"):
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except ValueError:
                continue
    return default  
    
class ProductService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "",
                category_id: Optional[int] = None) -> List[Product]:
        q = db.query(Product).filter_by(company_id=company_id).options(joinedload(Product.category), joinedload(Product.uom))
        if search:
            q = q.filter(or_(
                Product.name.ilike(f"%{search}%"),
                Product.code.ilike(f"%{search}%"),
                Product.barcode.ilike(f"%{search}%"),
            ))
        if category_id:
            q = q.filter_by(category_id=category_id)
        return q.order_by(Product.name).all()

    @staticmethod
    def get_by_id(db: Session, product_id: int) -> Optional[Product]:
        return db.query(Product).filter_by(id=product_id).first()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Product]]:
        if db.query(Product).filter_by(
                company_id=company_id, code=data["code"].strip()).first():
            return False, "Kode produk sudah digunakan.", None
        p = Product(
            company_id=company_id,
            code=data["code"].strip(),
            name=data["name"].strip(),
            barcode=data.get("barcode", "").strip() or None,
            description=data.get("description", "").strip() or None,
            product_type=data.get("product_type", "GOODS"),
            tracking_type=data.get("tracking_type", "NONE"),
            category_id=int(data["category_id"]) if data.get("category_id") else None,
            uom_id=int(data["uom_id"]),
            purchase_uom_id=int(data["purchase_uom_id"]) if data.get("purchase_uom_id") else None,
            sales_uom_id=int(data["sales_uom_id"]) if data.get("sales_uom_id") else None,
            standard_cost=_to_float(data.get("standard_cost")),
            sale_price=_to_float(data.get("sale_price")),
            min_sale_price=_to_float(data.get("min_sale_price")),
            min_stock=_to_float(data.get("min_stock")),
            max_stock=_to_float(data.get("max_stock")),
            reorder_point=_to_float(data.get("reorder_point")),
            lead_time_days=_to_int(data.get("lead_time_days")),
            is_purchasable=data.get("is_purchasable", True),
            is_sellable=data.get("is_sellable", True),
            is_stockable=data.get("is_stockable", True),
            is_active=data.get("is_active", True),
        )
        db.add(p)
        db.commit()
        return True, "Produk berhasil dibuat.", p

    @staticmethod
    def update(db: Session, product_id: int, data: Dict) -> tuple[bool, str]:
        p = db.query(Product).filter_by(id=product_id).first()
        if not p:
            return False, "Produk tidak ditemukan."
        p.name           = data["name"].strip()
        p.barcode        = data.get("barcode", "").strip() or None
        p.description    = data.get("description", "").strip() or None
        p.product_type   = data.get("product_type", "GOODS")
        p.tracking_type  = data.get("tracking_type", "NONE")
        p.category_id    = int(data["category_id"]) if data.get("category_id") else None
        p.uom_id         = int(data["uom_id"])
        p.purchase_uom_id= int(data["purchase_uom_id"]) if data.get("purchase_uom_id") else None
        p.sales_uom_id   = int(data["sales_uom_id"]) if data.get("sales_uom_id") else None
        p.standard_cost  = _to_float(data.get("standard_cost"))
        p.sale_price     = _to_float(data.get("sale_price"))
        p.min_sale_price = _to_float(data.get("min_sale_price"))
        p.min_stock      = _to_float(data.get("min_stock"))
        p.max_stock      = _to_float(data.get("max_stock"))
        p.reorder_point  = _to_float(data.get("reorder_point"))
        p.lead_time_days = _to_int(data.get("lead_time_days"))
        p.is_purchasable = data.get("is_purchasable", True)
        p.is_sellable    = data.get("is_sellable", True)
        p.is_stockable   = data.get("is_stockable", True)
        p.is_active      = data.get("is_active", True)
        db.commit()
        return True, "Produk berhasil diperbarui."

    @staticmethod
    def delete(db: Session, product_id: int) -> tuple[bool, str]:
        p = db.query(Product).filter_by(id=product_id).first()
        if not p:
            return False, "Produk tidak ditemukan."
        db.delete(p)
        db.commit()
        return True, "Produk berhasil dihapus."
    

class EmployeeService:
    @staticmethod
    def get_all_employees(db: Session, company_id: int, search: str = "") -> List[Employee]:
        q = db.query(Employee).options(joinedload(Employee.user)).filter_by(company_id=company_id)
        if search:
            q = q.filter(or_(
                Employee.name.ilike(f"%{search}%"),
                Employee.code.ilike(f"%{search}%"),
            ))
        return q.order_by(Employee.name).all()
    
    @staticmethod
    def get_employee_by_id(db: Session, employee_id: int) -> Optional[Employee]:
        return db.query(Employee).filter_by(id=employee_id).first()
    
    @staticmethod
    def create_employee(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Employee]]:
        if db.query(Employee).filter_by(
                company_id=company_id, code=data["code"].strip()).first():
            return False, "Kode karyawan sudah digunakan.", None
        emp = Employee(
            company_id=company_id,
            code=data["code"].strip(),
            name=data["name"].strip(),
            address=data.get("address", "").strip(),
            birth_date = _to_date(data.get("birth_date") if data.get("birth_date") else None),
            type=data["type"],
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            hire_date=_to_date(data.get("hire_date") if data.get("hire_date") else None),
            is_active=data.get("is_active", True),
        )
        db.add(emp)
        db.flush()
        user = User(
            company_id=company_id,
            employee_id=emp.id,
            username=data["username"].strip(),
            email= data.get("email", ""),
            full_name=data["name"].strip(),
            phone=data.get("phone", ""),
            is_active=True
        )
        user.set_password(data["password"].strip())
        db.add(user)

        db.commit()
        return True, "Karyawan berhasil dibuat.", emp
    
    @staticmethod
    def update_employee(db: Session, employee_id: int, data: Dict) -> tuple[bool, str]:
        emp = db.query(Employee).filter_by(id=employee_id).first()
        if not emp:
            return False, "Karyawan tidak ditemukan."
        emp.name       = data["name"].strip()
        emp.address    = data.get("address", "").strip()
        emp.birth_date = _to_date(data.get("birth_date") if data.get("birth_date") else None)
        emp.type       = data["type"]
        emp.email      = data.get("email", "")
        emp.phone      = data.get("phone", "")
        emp.hire_date  = _to_date(data.get("hire_date") if data.get("hire_date") else None)
        emp.is_active  = data.get("is_active", True)

        user = db.query(User).filter_by(employee_id=employee_id).first()
        if user:
            user.is_active = data.get("is_active", True)

        db.commit()
        return True, "Karyawan berhasil diperbarui."
    
    @staticmethod
    def set_resignation(db: Session, employee_id: int, resign_date: str) -> tuple[bool, str]:
        emp = db.query(Employee).filter_by(id=employee_id).first()
        if not emp:
            return False, "Karyawan tidak ditemukan."
        emp.resign_date = _to_date(resign_date)
        emp.is_active = False

        user = db.query(User).filter_by(employee_id=employee_id).first()
        if user:
            user.is_active = False

        db.commit()
        return True, "Status karyawan berhasil diperbarui."
    
    @staticmethod
    def delete_employee(db: Session, employee_id: int) -> tuple[bool, str]:
        emp = db.query(Employee).filter_by(id=employee_id).first()
        if not emp:
            return False, "Karyawan tidak ditemukan."
        db.delete(emp)
        db.commit()
        return True, "Karyawan berhasil dihapus."
    
class EmployeeAssignmentService:
    @staticmethod
    def get_all(db: Session, employee_id: int) -> List[EmployeeAssignment]:
        return (
            db.query(EmployeeAssignment)
            .options(
                joinedload(EmployeeAssignment.employee))
            .filter_by(employee_id=employee_id)
            .all()
        )
    
    @staticmethod
    def assign(db: Session, employee_id: int, data: Dict) -> tuple[bool, str]:
        last_assign = db.query(EmployeeAssignment).filter_by(employee_id=employee_id).order_by(EmployeeAssignment.id.desc()).first()
        if last_assign and last_assign.end_date is None:
            last_assign.end_date = datetime.date.today()
            last_assign.is_active = False

        user = db.query(User).filter_by(employee_id=employee_id).first()
        assign = EmployeeAssignment(
            code = data["code"].strip(),
            employee_id=employee_id,
            roles = data.get("roles", []),
            branch_id=data.get("branch_id"),
            department_id=data.get("department_id"),
            start_date=_to_date(data.get("start_date")) if data.get("start_date") else None,
            end_date=_to_date(data.get("end_date")) if data.get("end_date") else None,
        )

        last_assign = db.query(EmployeeAssignment).filter_by(employee_id=employee_id,is_active=True).first()
        if last_assign:
            last_assign.is_active = False
            last_assign.end_date = func.now()

        db.add(assign)


        delete_roles = db.query(UserRole).filter_by(user_id=user.id).all()
        for dr in delete_roles:
            db.delete(dr)
        
        # Assign roles
        for role_id in data.get("role_ids", []):
            db.add(UserRole(
                user_id=user.id,
                role_id=int(role_id),
                branch_id=data.get("branch_id") or None,
            ))


        db.commit()
        return True, "Assignment berhasil ditugaskan ke cabang."
