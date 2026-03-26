"""
app/services/master_service.py
CRUD untuk Master Data: Company, Branch, ProductCategory, Product,
Vendor, Partner, Customer
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.models import (
    Company, Branch, Department,
    Product, ProductCategory,
    Vendor, VendorProduct,
    Partner, Customer,
    UnitOfMeasure, Campaign, Employee, UOMConversion
)


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

def _to_bool(val, default: bool = False) -> bool:
    """Konversi nilai ke bool dengan aman."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        val = val.strip().lower()
        if val in ("true", "1", "yes", "y"):
            return True
        elif val in ("false", "0", "no", "n"):
            return False
    return default

def _to_str(val, default: str = "") -> str:
    """Konversi nilai ke str dengan aman."""
    try:
        return str(val).strip() if val not in (None, "None") else default
    except (ValueError, TypeError):
        return default

def _to_date(val, default=None):
    """Konversi nilai ke date dengan aman."""
    from datetime import datetime
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except ValueError:
                continue
    return default  


# ─────────────────────────────────────────────────────────────
# UNIT OF MEASURMENT
# ─────────────────────────────────────────────────────────────
class UOMService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[UnitOfMeasure]:
        q = db.query(UnitOfMeasure).filter_by(company_id=company_id)
        if search:
            q = q.filter(or_(
                UnitOfMeasure.name.ilike(f"%{search}%"),
                UnitOfMeasure.code.ilike(f"%{search}%"),
            ))
        return q.order_by(UnitOfMeasure.name).all()

    @staticmethod
    def get_by_id(db: Session, company_id: int, uom_id: int) -> Optional[UnitOfMeasure]:
        return db.query(UnitOfMeasure).filter_by(company_id=company_id, id=uom_id).first()

    @staticmethod
    def create(db: Session, data: Dict) -> tuple[bool, str, Optional[UnitOfMeasure]]:
        if db.query(UnitOfMeasure).filter_by(company_id=data["company_id"], code=data["code"].strip().upper()).first():
            return False, "Kode perusahaan sudah digunakan.", None
        c = UnitOfMeasure(
            company_id=data["company_id"],
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            uom_type=data.get("uom_type", "UNIT"),
            is_active=data.get("is_active", True),
        )
        db.add(c)
        db.commit()
        return True, "UOM berhasil dibuat.", c

    @staticmethod
    def update(db: Session, uom_id: int, data: Dict) -> tuple[bool, str]:
        c = db.query(UnitOfMeasure).filter_by(id=uom_id).first()
        if not c:
            return False, "UOM tidak ditemukan."
        c.name          = data["name"].strip()
        c.uom_type    = data.get("uom_type", "UNIT")
        c.is_active     = data.get("is_active", True)
        db.commit()
        return True, "UOM berhasil diperbarui."

    @staticmethod
    def delete(db: Session, uom_id: int) -> tuple[bool, str]:
        c = db.query(UnitOfMeasure).filter_by(id=uom_id).first()
        if not c:
            return False, "UOM tidak ditemukan."
        db.delete(c)
        db.commit()
        return True, "UOM berhasil dihapus."


class UOMConversionService:

    @staticmethod
    def get_all(db: Session) -> List[UOMConversion]:
        q = db.query(UOMConversion).options(joinedload(UOMConversion.from_uom), joinedload(UOMConversion.to_uom))
        return q.all()

    @staticmethod
    def get_by_id(db: Session, uomConversion_id: int) -> Optional[UOMConversion]:
        q = db.query(UOMConversion).options(joinedload(UOMConversion.from_uom), joinedload(UOMConversion.to_uom))
        return q.filter_by(id=uomConversion_id).first()

    @staticmethod
    def create(db: Session, data: Dict) -> tuple[bool, str, Optional[UOMConversion]]:
        if db.query(UOMConversion).filter_by(from_uom_id=data["from_uom_id"], to_uom_id=data["to_uom_id"]).first():
            return False, "Konversi UOM sudah ada.", None
        c = UOMConversion(
            from_uom_id=data["from_uom_id"] if data.get("from_uom_id") else None,
            to_uom_id=data["to_uom_id"] if data.get("to_uom_id") else None,
            factor=_to_float(data.get("factor"), 1.0),
            is_active=data.get("is_active", True),
        )
        db.add(c)
        db.commit()
        return True, "UOM Conversion berhasil dibuat.", c

    @staticmethod
    def update(db: Session, uomConversion_id: int, data: Dict) -> tuple[bool, str]:
        c = db.query(UOMConversion).filter_by(id=uomConversion_id).first()
        if not c:
            return False, "UOM Conversion tidak ditemukan."
        c.from_uom_id = data.get("from_uom_id")
        c.to_uom_id = data.get("to_uom_id")
        c.factor = _to_float(data.get("factor"), 1.0)
        c.is_active = data.get("is_active", True)
        db.commit()
        return True, "UOM Conversion berhasil diperbarui."

    @staticmethod
    def delete(db: Session, uomConversion_id: int) -> tuple[bool, str]:
        c = db.query(UOMConversion).filter_by(id=uomConversion_id).first()
        if not c:
            return False, "UOM Conversion tidak ditemukan."
        db.delete(c)
        db.commit()
        return True, "UOM Conversion berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# COMPANY
# ─────────────────────────────────────────────────────────────
class CompanyService:

    @staticmethod
    def get_all(db: Session, search: str = "") -> List[Company]:
        q = db.query(Company)
        if search:
            q = q.filter(or_(
                Company.name.ilike(f"%{search}%"),
                Company.code.ilike(f"%{search}%"),
            ))
        return q.order_by(Company.name).all()

    @staticmethod
    def get_by_id(db: Session, company_id: int) -> Optional[Company]:
        return db.query(Company).filter_by(id=company_id).first()

    @staticmethod
    def create(db: Session, data: Dict) -> tuple[bool, str, Optional[Company]]:
        if db.query(Company).filter_by(code=data["code"].strip().upper()).first():
            return False, "Kode perusahaan sudah digunakan.", None
        c = Company(
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            legal_name=data.get("legal_name", "").strip() or None,
            tax_id=data.get("tax_id", "").strip() or None,
            address=data.get("address", "").strip() or None,
            city=data.get("city", "").strip() or None,
            province=data.get("province", "").strip() or None,
            country=data.get("country", "Indonesia").strip() or "Indonesia",
            phone=data.get("phone", "").strip() or None,
            email=data.get("email", "").strip() or None,
            logo_url=data.get("logo_url", "").strip() or None,
            currency_code=data.get("currency_code", "IDR").strip() or "IDR",
            is_active=data.get("is_active", True),
        )
        db.add(c)
        db.commit()
        return True, "Perusahaan berhasil dibuat.", c

    @staticmethod
    def update(db: Session, company_id: int, data: Dict) -> tuple[bool, str]:
        c = db.query(Company).filter_by(id=company_id).first()
        if not c:
            return False, "Perusahaan tidak ditemukan."
        c.name          = data["name"].strip()
        c.legal_name    = data.get("legal_name", "").strip() or None
        c.tax_id        = data.get("tax_id", "").strip() or None
        c.address       = data.get("address", "").strip() or None
        c.city          = data.get("city", "").strip() or None
        c.province      = data.get("province", "").strip() or None
        c.country       = data.get("country", "Indonesia") or "Indonesia"
        c.phone         = data.get("phone", "").strip() or None
        c.email         = data.get("email", "").strip() or None
        c.logo_url      = data.get("logo_url", "").strip() or None
        c.currency_code = data.get("currency_code", "IDR") or "IDR"
        c.is_active     = data.get("is_active", True)
        db.commit()
        return True, "Perusahaan berhasil diperbarui."

    @staticmethod
    def delete(db: Session, company_id: int) -> tuple[bool, str]:
        c = db.query(Company).filter_by(id=company_id).first()
        if not c:
            return False, "Perusahaan tidak ditemukan."
        branch_count = db.query(Branch).filter_by(company_id=company_id).count()
        if branch_count > 0:
            return False, f"Perusahaan memiliki {branch_count} cabang, tidak bisa dihapus."
        db.delete(c)
        db.commit()
        return True, "Perusahaan berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# BRANCH
# ─────────────────────────────────────────────────────────────
class BranchService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[Branch]:
        q = db.query(Branch).filter_by(company_id=company_id)
        if search:
            q = q.filter(or_(
                Branch.name.ilike(f"%{search}%"),
                Branch.code.ilike(f"%{search}%"),
            ))
        return q.order_by(Branch.name).all()

    @staticmethod
    def get_by_id(db: Session, branch_id: int) -> Optional[Branch]:
        return db.query(Branch).filter_by(id=branch_id).first()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Branch]]:
        if db.query(Branch).filter_by(company_id=company_id,
                                       code=data["code"].strip().upper()).first():
            return False, "Kode cabang sudah digunakan.", None
        b = Branch(
            company_id=company_id,
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            branch_type=data.get("branch_type", "BRANCH"),
            address=data.get("address", "").strip() or None,
            city=data.get("city", "").strip() or None,
            phone=data.get("phone", "").strip() or None,
            email=data.get("email", "").strip() or None,
            is_active=data.get("is_active", True),
        )
        db.add(b)
        db.commit()
        return True, "Cabang berhasil dibuat.", b

    @staticmethod
    def update(db: Session, branch_id: int, data: Dict) -> tuple[bool, str]:
        b = db.query(Branch).filter_by(id=branch_id).first()
        if not b:
            return False, "Cabang tidak ditemukan."
        b.name        = data["name"].strip()
        b.branch_type = data.get("branch_type", "BRANCH")
        b.address     = data.get("address", "").strip() or None
        b.city        = data.get("city", "").strip() or None
        b.phone       = data.get("phone", "").strip() or None
        b.email       = data.get("email", "").strip() or None
        b.is_active   = data.get("is_active", True)
        db.commit()
        return True, "Cabang berhasil diperbarui."

    @staticmethod
    def delete(db: Session, branch_id: int) -> tuple[bool, str]:
        b = db.query(Branch).filter_by(id=branch_id).first()
        if not b:
            return False, "Cabang tidak ditemukan."
        db.delete(b)
        db.commit()
        return True, "Cabang berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# PRODUCT CATEGORY
# ─────────────────────────────────────────────────────────────
class ProductCategoryService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[ProductCategory]:
        q = db.query(ProductCategory).filter_by(company_id=company_id)
        if search:
            q = q.filter(ProductCategory.name.ilike(f"%{search}%"))
        return q.order_by(ProductCategory.name).all()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[ProductCategory]]:
        if db.query(ProductCategory).filter_by(
                company_id=company_id, code=data["code"].strip().upper()).first():
            return False, "Kode kategori sudah digunakan.", None
        cat = ProductCategory(
            company_id=company_id,
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            description=data.get("description", "").strip() or None,
            parent_id=int(data["parent_id"]) if data.get("parent_id") else None,
            is_active=data.get("is_active", True),
        )
        db.add(cat)
        db.commit()
        return True, "Kategori berhasil dibuat.", cat

    @staticmethod
    def update(db: Session, cat_id: int, data: Dict) -> tuple[bool, str]:
        cat = db.query(ProductCategory).filter_by(id=cat_id).first()
        if not cat:
            return False, "Kategori tidak ditemukan."
        cat.name        = data["name"].strip()
        cat.description = data.get("description", "").strip() or None
        cat.parent_id   = int(data["parent_id"]) if data.get("parent_id") else None
        cat.is_active   = data.get("is_active", True)
        db.commit()
        return True, "Kategori berhasil diperbarui."

    @staticmethod
    def delete(db: Session, cat_id: int) -> tuple[bool, str]:
        cat = db.query(ProductCategory).filter_by(id=cat_id).first()
        if not cat:
            return False, "Kategori tidak ditemukan."
        prod_count = db.query(Product).filter_by(category_id=cat_id).count()
        if prod_count:
            return False, f"Kategori digunakan {prod_count} produk."
        db.delete(cat)
        db.commit()
        return True, "Kategori berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# PRODUCT
# ─────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────
# VENDOR
# ─────────────────────────────────────────────────────────────
class VendorService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[Vendor]:
        q = db.query(Vendor).filter_by(company_id=company_id)
        if search:
            q = q.filter(or_(
                Vendor.name.ilike(f"%{search}%"),
                Vendor.code.ilike(f"%{search}%"),
            ))
        return q.order_by(Vendor.name).all()

    @staticmethod
    def get_by_id(db: Session, vendor_id: int) -> Optional[Vendor]:
        return db.query(Vendor).filter_by(id=vendor_id).first()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Vendor]]:
        if db.query(Vendor).filter_by(
                company_id=company_id, code=data["code"].strip().upper()).first():
            return False, "Kode vendor sudah digunakan.", None
        v = Vendor(
            company_id=company_id,
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            legal_name=data.get("legal_name", "").strip() or None,
            tax_id=data.get("tax_id", "").strip() or None,
            vendor_type=data.get("vendor_type", "SUPPLIER"),
            address=data.get("address", "").strip() or None,
            city=data.get("city", "").strip() or None,
            province=data.get("province", "").strip() or None,
            country=data.get("country", "Indonesia") or "Indonesia",
            phone=data.get("phone", "").strip() or None,
            email=data.get("email", "").strip() or None,
            payment_terms_days=_to_int(data.get("payment_terms_days"), 30),
            currency_code=data.get("currency_code", "IDR") or "IDR",
            bank_name=data.get("bank_name", "").strip() or None,
            bank_account=data.get("bank_account", "").strip() or None,
            bank_account_name=data.get("bank_account_name", "").strip() or None,
            is_active=data.get("is_active", True),
        )
        db.add(v)
        db.commit()
        return True, "Vendor berhasil dibuat.", v

    @staticmethod
    def update(db: Session, vendor_id: int, data: Dict) -> tuple[bool, str]:
        v = db.query(Vendor).filter_by(id=vendor_id).first()
        if not v:
            return False, "Vendor tidak ditemukan."
        v.name               = data["name"].strip()
        v.legal_name         = data.get("legal_name", "").strip() or None
        v.tax_id             = data.get("tax_id", "").strip() or None
        v.vendor_type        = data.get("vendor_type", "SUPPLIER")
        v.address            = data.get("address", "").strip() or None
        v.city               = data.get("city", "").strip() or None
        v.province           = data.get("province", "").strip() or None
        v.country            = data.get("country", "Indonesia") or "Indonesia"
        v.phone              = data.get("phone", "").strip() or None
        v.email              = data.get("email", "").strip() or None
        v.payment_terms_days = _to_int(data.get("payment_terms_days"), 30)
        v.currency_code      = data.get("currency_code", "IDR") or "IDR"
        v.bank_name          = data.get("bank_name", "").strip() or None
        v.bank_account       = data.get("bank_account", "").strip() or None
        v.bank_account_name  = data.get("bank_account_name", "").strip() or None
        v.is_active          = data.get("is_active", True)
        db.commit()
        return True, "Vendor berhasil diperbarui."

    @staticmethod
    def delete(db: Session, vendor_id: int) -> tuple[bool, str]:
        v = db.query(Vendor).filter_by(id=vendor_id).first()
        if not v:
            return False, "Vendor tidak ditemukan."
        db.delete(v)
        db.commit()
        return True, "Vendor berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# PARTNER
# ─────────────────────────────────────────────────────────────
class PartnerService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[Partner]:
        q = db.query(Partner).filter_by(company_id=company_id)
        if search:
            q = q.filter(or_(
                Partner.name.ilike(f"%{search}%"),
                Partner.code.ilike(f"%{search}%"),
            ))
        return q.order_by(Partner.name).all()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Partner]]:
        if db.query(Partner).filter_by(
                company_id=company_id, code=data["code"].strip().upper()).first():
            return False, "Kode mitra sudah digunakan.", None
        p = Partner(
            company_id=company_id,
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            partner_type=data.get("partner_type", "REFERRAL"),
            contact_person=data.get("contact_person", "").strip() or None,
            phone=data.get("phone", "").strip() or None,
            email=data.get("email", "").strip() or None,
            address=data.get("address", "").strip() or None,
            city=data.get("city", "").strip() or None,
            commission_pct=_to_float(data.get("commission_pct")),
            is_active=data.get("is_active", True),
        )
        db.add(p)
        db.commit()
        return True, "Mitra berhasil dibuat.", p

    @staticmethod
    def update(db: Session, partner_id: int, data: Dict) -> tuple[bool, str]:
        p = db.query(Partner).filter_by(id=partner_id).first()
        if not p:
            return False, "Mitra tidak ditemukan."
        p.name           = data["name"].strip()
        p.partner_type   = data.get("partner_type", "REFERRAL")
        p.contact_person = data.get("contact_person", "").strip() or None
        p.phone          = data.get("phone", "").strip() or None
        p.email          = data.get("email", "").strip() or None
        p.address        = data.get("address", "").strip() or None
        p.city           = data.get("city", "").strip() or None
        p.commission_pct = _to_float(data.get("commission_pct"))
        p.is_active      = data.get("is_active", True)
        db.commit()
        return True, "Mitra berhasil diperbarui."

    @staticmethod
    def delete(db: Session, partner_id: int) -> tuple[bool, str]:
        p = db.query(Partner).filter_by(id=partner_id).first()
        if not p:
            return False, "Mitra tidak ditemukan."
        cust_count = db.query(Customer).filter_by(partner_id=partner_id).count()
        if cust_count:
            return False, f"Mitra digunakan {cust_count} pelanggan."
        db.delete(p)
        db.commit()
        return True, "Mitra berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# CUSTOMER
# ─────────────────────────────────────────────────────────────
class CustomerService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[Customer]:
        q = db.query(Customer).filter_by(company_id=company_id)\
               .options(joinedload(Customer.branch))
        if search:
            q = q.filter(or_(
                Customer.name.ilike(f"%{search}%"),
                Customer.code.ilike(f"%{search}%"),
                Customer.phone.ilike(f"%{search}%"),
                Customer.email.ilike(f"%{search}%"),
            ))
        return q.order_by(Customer.name).all()

    @staticmethod
    def get_by_id(db: Session, customer_id: int) -> Optional[Customer]:
        return db.query(Customer).filter_by(id=customer_id).first()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Customer]]:
        if db.query(Customer).filter_by(
                company_id=company_id, code=data["code"].strip().upper()).first():
            return False, "Kode pelanggan sudah digunakan.", None
        c = Customer(
            company_id=company_id,
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            customer_type=data.get("customer_type", "INDIVIDUAL"),
            tax_id=data.get("tax_id", "").strip() or None,
            phone=data.get("phone", "").strip() or None,
            email=data.get("email", "").strip() or None,
            address=data.get("address", "").strip() or None,
            city=data.get("city", "").strip() or None,
            province=data.get("province", "").strip() or None,
            country=data.get("country", "Indonesia") or "Indonesia",
            acquisition_source=data.get("acquisition_source", "DIRECT"),
            partner_id=int(data["partner_id"]) if data.get("partner_id") else None,
            campaign_id=int(data["campaign_id"]) if data.get("campaign_id") else None,
            branch_id=int(data["branch_id"]) if data.get("branch_id") else None,
            payment_terms_days=_to_int(data.get("payment_terms_days")),
            credit_limit=_to_float(data.get("credit_limit")),
            is_active=data.get("is_active", True),
        )
        db.add(c)
        db.commit()
        return True, "Pelanggan berhasil dibuat.", c

    @staticmethod
    def update(db: Session, customer_id: int, data: Dict) -> tuple[bool, str]:
        c = db.query(Customer).filter_by(id=customer_id).first()
        if not c:
            return False, "Pelanggan tidak ditemukan."
        c.name               = data["name"].strip()
        c.customer_type      = data.get("customer_type", "INDIVIDUAL")
        c.tax_id             = data.get("tax_id", "").strip() or None
        c.phone              = data.get("phone", "").strip() or None
        c.email              = data.get("email", "").strip() or None
        c.address            = data.get("address", "").strip() or None
        c.city               = data.get("city", "").strip() or None
        c.province           = data.get("province", "").strip() or None
        c.country            = data.get("country", "Indonesia") or "Indonesia"
        c.acquisition_source = data.get("acquisition_source", "DIRECT")
        c.partner_id         = int(data["partner_id"]) if data.get("partner_id") else None
        c.campaign_id        = int(data["campaign_id"]) if data.get("campaign_id") else None
        c.branch_id          = int(data["branch_id"]) if data.get("branch_id") else None
        c.payment_terms_days = _to_int(data.get("payment_terms_days"))
        c.credit_limit       = _to_float(data.get("credit_limit"))
        c.is_active          = data.get("is_active", True)
        db.commit()
        return True, "Pelanggan berhasil diperbarui."

    @staticmethod
    def delete(db: Session, customer_id: int) -> tuple[bool, str]:
        c = db.query(Customer).filter_by(id=customer_id).first()
        if not c:
            return False, "Pelanggan tidak ditemukan."
        db.delete(c)
        db.commit()
        return True, "Pelanggan berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# DEPARTMENT
# ─────────────────────────────────────────────────────────────
class DepartmentService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[Department]:
        q = db.query(Department).filter_by(company_id=company_id).\
            options(joinedload(Department.branch), joinedload(Department.parent))
        if search:
            q = q.filter(or_(
                Department.name.ilike(f"%{search}%"),
                Department.code.ilike(f"%{search}%"),
            ))
        return q.order_by(Department.name).all()

    @staticmethod
    def get_ordered(db: Session, company_id: int) -> List[Department]:
        """Ambil semua dept diurutkan: root dulu, lalu children-nya."""
        all_depts = db.query(Department).filter_by(company_id=company_id).\
            options(joinedload(Department.branch), joinedload(Department.parent)).all()
        roots    = [d for d in all_depts if d.parent_id is None]
        child_of = {}
        for d in all_depts:
            if d.parent_id:
                child_of.setdefault(d.parent_id, []).append(d)
        ordered = []
        for r in roots:
            ordered.append(r)
            ordered.extend(child_of.get(r.id, []))
        return ordered

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Department]]:
        if db.query(Department).filter_by(
                company_id=company_id, code=data["code"].strip().upper()).first():
            return False, "Kode departemen sudah digunakan.", None
        d = Department(
            company_id=company_id,
            branch_id=int(data["branch_id"]) if data.get("branch_id") else None,
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            parent_id=int(data["parent_id"]) if data.get("parent_id") else None,
            is_active=data.get("is_active", True),
        )
        db.add(d)
        db.commit()
        return True, "Departemen berhasil dibuat.", d

    @staticmethod
    def update(db: Session, dept_id: int, data: Dict) -> tuple[bool, str]:
        d = db.query(Department).filter_by(id=dept_id).first()
        if not d:
            return False, "Departemen tidak ditemukan."
        # Cegah parent = diri sendiri
        if data.get("parent_id") and int(data["parent_id"]) == dept_id:
            return False, "Departemen tidak bisa menjadi induk dirinya sendiri."
        d.branch_id = int(data["branch_id"]) if data.get("branch_id") else None
        d.name      = data["name"].strip()
        d.parent_id = int(data["parent_id"]) if data.get("parent_id") else None
        d.is_active = data.get("is_active", True)
        db.commit()
        return True, "Departemen berhasil diperbarui."

    @staticmethod
    def delete(db: Session, dept_id: int) -> tuple[bool, str]:
        d = db.query(Department).filter_by(id=dept_id).first()
        if not d:
            return False, "Departemen tidak ditemukan."
        child_count = db.query(Department).filter_by(parent_id=dept_id).count()
        if child_count:
            return False, f"Departemen memiliki {child_count} sub-departemen, hapus sub-dept dulu."
        emp_count = db.query(Employee).filter_by(department_id=dept_id).count()
        if emp_count:
            return False, f"Departemen digunakan oleh {emp_count} karyawan."
        db.delete(d)
        db.commit()
        return True, "Departemen berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# CAMPAIGN
# ─────────────────────────────────────────────────────────────
class CampaignService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List[Campaign]:
        q = db.query(Campaign).filter_by(company_id=company_id)
        if search:
            q = q.filter(or_(
                Campaign.name.ilike(f"%{search}%"),
                Campaign.code.ilike(f"%{search}%"),
            ))
        return q.order_by(Campaign.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, campaign_id: int) -> Optional[Campaign]:
        return db.query(Campaign).filter_by(id=campaign_id).first()

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str, Optional[Campaign]]:
        if db.query(Campaign).filter_by(
                company_id=company_id, code=data["code"].strip().upper()).first():
            return False, "Kode campaign sudah digunakan.", None
        c = Campaign(
            company_id=company_id,
            branch_id=int(data["branch_id"]) if data.get("branch_id") else None,
            code=data["code"].strip().upper(),
            name=data["name"].strip(),
            campaign_type=data.get("campaign_type", "DIGITAL"),
            channel=data.get("channel", "").strip() or None,
            start_date=data.get("start_date") or None,
            end_date=data.get("end_date") or None,
            budget=_to_float(data.get("budget")),
            actual_spend=_to_float(data.get("actual_spend")),
            target_leads=_to_int(data.get("target_leads")),
            target_revenue=_to_float(data.get("target_revenue")),
            status=data.get("status", "DRAFT"),
            description=data.get("description", "").strip() or None,
        )
        db.add(c)
        db.commit()
        return True, "Campaign berhasil dibuat.", c

    @staticmethod
    def update(db: Session, campaign_id: int, data: Dict) -> tuple[bool, str]:
        c = db.query(Campaign).filter_by(id=campaign_id).first()
        if not c:
            return False, "Campaign tidak ditemukan."
        c.branch_id     = int(data["branch_id"]) if data.get("branch_id") else None
        c.name          = data["name"].strip()
        c.campaign_type = data.get("campaign_type", "DIGITAL")
        c.channel       = data.get("channel", "").strip() or None
        c.start_date    = data.get("start_date") or None
        c.end_date      = data.get("end_date") or None
        c.budget        = _to_float(data.get("budget"))
        c.actual_spend  = _to_float(data.get("actual_spend"))
        c.target_leads  = _to_int(data.get("target_leads"))
        c.target_revenue= _to_float(data.get("target_revenue"))
        c.status        = data.get("status", "DRAFT")
        c.description   = data.get("description", "").strip() or None
        db.commit()
        return True, "Campaign berhasil diperbarui."

    @staticmethod
    def delete(db: Session, campaign_id: int) -> tuple[bool, str]:
        c = db.query(Campaign).filter_by(id=campaign_id).first()
        if not c:
            return False, "Campaign tidak ditemukan."
        cust_count = db.query(Customer).filter_by(campaign_id=campaign_id).count()
        if cust_count:
            return False, f"Campaign digunakan oleh {cust_count} pelanggan."
        db.delete(c)
        db.commit()
        return True, "Campaign berhasil dihapus."

    @staticmethod
    def update_status(db: Session, campaign_id: int, status: str) -> tuple[bool, str]:
        c = db.query(Campaign).filter_by(id=campaign_id).first()
        if not c:
            return False, "Campaign tidak ditemukan."
        c.status = status
        db.commit()
        return True, f"Status campaign diubah ke {status}."


# ─────────────────────────────────────────────────────────────
# WAREHOUSE SERVICE
# ─────────────────────────────────────────────────────────────
class WarehouseService:

    @staticmethod
    def get_by_branch(db: Session, branch_id: int) -> List:
        from app.models import Warehouse
        return db.query(Warehouse).filter_by(branch_id=branch_id, is_active=True)\
                 .order_by(Warehouse.name).all()

    @staticmethod
    def get_by_company(db: Session, company_id: int) -> List:
        from app.models import Warehouse, Branch
        return db.query(Warehouse)\
                 .join(Branch, Warehouse.branch_id == Branch.id)\
                 .filter(Branch.company_id == company_id, Warehouse.is_active == True)\
                 .order_by(Warehouse.name).all()

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "") -> List:
        from app.models import Warehouse, Branch
        q = db.query(Warehouse)\
              .join(Branch, Warehouse.branch_id == Branch.id)\
              .filter(Branch.company_id == company_id)\
              .options(joinedload(Warehouse.branch))
        if search:
            q = q.filter(or_(
                Warehouse.name.ilike(f"%{search}%"),
                Warehouse.code.ilike(f"%{search}%"),
            ))
        return q.order_by(Branch.name, Warehouse.name).all()

    @staticmethod
    def get_by_id(db: Session, wh_id: int):
        from app.models import Warehouse
        return db.query(Warehouse).filter_by(id=wh_id)\
                 .options(joinedload(Warehouse.branch)).first()

    @staticmethod
    def create(db: Session, data: Dict) -> tuple[bool, str, Optional[object]]:
        from app.models import Warehouse
        branch_id = int(data["branch_id"])
        code      = data["code"].strip().upper()
        if db.query(Warehouse).filter_by(branch_id=branch_id, code=code).first():
            return False, "Kode gudang sudah digunakan di cabang ini.", None
        wh = Warehouse(
            branch_id=branch_id,
            code=code,
            name=data["name"].strip(),
            address=data.get("address", "").strip() or None,
            is_active=data.get("is_active", True),
        )
        db.add(wh)
        db.commit()
        return True, "Gudang berhasil dibuat.", wh

    @staticmethod
    def update(db: Session, wh_id: int, data: Dict) -> tuple[bool, str]:
        from app.models import Warehouse
        wh = db.query(Warehouse).filter_by(id=wh_id).first()
        if not wh:
            return False, "Gudang tidak ditemukan."
        wh.branch_id = int(data["branch_id"])
        wh.name      = data["name"].strip()
        wh.address   = data.get("address", "").strip() or None
        wh.is_active = data.get("is_active", True)
        db.commit()
        return True, "Gudang berhasil diperbarui."

    @staticmethod
    def delete(db: Session, wh_id: int) -> tuple[bool, str]:
        from app.models import Warehouse, PurchaseOrder
        wh = db.query(Warehouse).filter_by(id=wh_id).first()
        if not wh:
            return False, "Gudang tidak ditemukan."
        po_count = db.query(PurchaseOrder).filter_by(warehouse_id=wh_id).count()
        if po_count:
            return False, f"Gudang digunakan oleh {po_count} Purchase Order."
        db.delete(wh)
        db.commit()
        return True, "Gudang berhasil dihapus."
