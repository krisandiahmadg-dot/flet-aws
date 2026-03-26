"""
app/services/sales_service.py
Service untuk modul Penjualan:
  SalesOrder, DeliveryOrder, Invoice, Payment
"""
from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.models import (
    SalesOrder, SalesOrderLine,
    DeliveryOrder, DeliveryOrderLine,
    Invoice, Payment,
    Customer, Branch, Warehouse, Product, UnitOfMeasure, User,
    StockBalance,
)


def _to_float(val, default=0.0):
    try:
        return float(str(val).strip()) if val not in (None, "", "None") else default
    except: return default


def _to_int(val, default=0):
    try:
        return int(float(str(val).strip())) if val not in (None, "", "None") else default
    except: return default


def _to_date(val) -> Optional[date]:
    if not val or not str(val).strip(): return None
    try: return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except: return None


# ─────────────────────────────────────────────────────────────
# SALES ORDER
# ─────────────────────────────────────────────────────────────
class SalesOrderService:

    @staticmethod
    def _gen_number(db: Session, company_id: int) -> str:
        prefix = f"SO-{datetime.now().strftime('%Y%m')}-"
        last = db.query(SalesOrder)\
                 .filter(SalesOrder.so_number.like(f"{prefix}%"),
                         SalesOrder.company_id == company_id)\
                 .order_by(SalesOrder.so_number.desc()).first()
        seq = (int(last.so_number.split("-")[-1]) + 1) if last else 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def get_all(db: Session, company_id: int,
                search: str = "", status: str = "",
                branch_id: Optional[int] = None) -> List[SalesOrder]:
        q = db.query(SalesOrder).filter_by(company_id=company_id)\
               .options(
                   joinedload(SalesOrder.customer),
                   joinedload(SalesOrder.branch),
                   joinedload(SalesOrder.sales_user),
                   joinedload(SalesOrder.lines).joinedload(SalesOrderLine.product),
               )
        if branch_id:
            q = q.filter(SalesOrder.branch_id == branch_id)
        if search:
            q = q.filter(or_(
                SalesOrder.so_number.ilike(f"%{search}%"),
                Customer.name.ilike(f"%{search}%"),
            ))
        if status:
            q = q.filter(SalesOrder.status == status)
        return q.order_by(SalesOrder.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, so_id: int) -> Optional[SalesOrder]:
        return db.query(SalesOrder).filter_by(id=so_id)\
                 .options(
                     joinedload(SalesOrder.customer),
                     joinedload(SalesOrder.branch),
                     joinedload(SalesOrder.warehouse),
                     joinedload(SalesOrder.lines).joinedload(SalesOrderLine.product)
                         .joinedload(Product.uom),
                     joinedload(SalesOrder.lines).joinedload(SalesOrderLine.uom),
                 ).first()

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict, lines: List[Dict]) -> tuple[bool, str]:
        if not lines:
            return False, "Minimal satu item wajib diisi."

        number = SalesOrderService._gen_number(db, company_id)
        so = SalesOrder(
            company_id=company_id,
            branch_id=int(data["branch_id"]),
            so_number=number,
            order_date=_to_date(data.get("order_date")) or date.today(),
            customer_id=int(data["customer_id"]),
            sales_user_id=_to_int(data.get("sales_user_id")) or None,
            warehouse_id=_to_int(data.get("warehouse_id")) or None,
            shipping_address=data.get("shipping_address", "").strip() or None,
            shipping_city=data.get("shipping_city", "").strip() or None,
            shipping_method=data.get("shipping_method", "").strip() or None,
            expected_delivery=_to_date(data.get("expected_delivery")),
            notes=data.get("notes", "").strip() or None,
            created_by=user_id,
            status="DRAFT",
        )
        db.add(so); db.flush()

        subtotal = 0.0
        for ln in lines:
            qty   = _to_float(ln["qty_ordered"])
            price = _to_float(ln["unit_price"])
            disc  = _to_float(ln.get("discount_pct", 0))
            tax   = _to_float(ln.get("tax_pct", 0))
            line_subtotal = qty * price * (1 - disc / 100)
            subtotal += line_subtotal
            db.add(SalesOrderLine(
                so_id=so.id,
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_ordered=qty,
                unit_price=price,
                discount_pct=disc,
                tax_pct=tax,
                notes=ln.get("notes", "").strip() or None,
            ))

        # Hitung pajak: dari tax_rate_id SO, atau rata-rata dari lines
        tax_total = 0.0
        tax_rate_id = _to_int(data.get("tax_rate_id")) or None
        if tax_rate_id:
            from app.models import TaxRate
            tr = db.query(TaxRate).filter_by(id=tax_rate_id).first()
            if tr:
                so.tax_rate_id = tax_rate_id
                tax_total = subtotal * tr.rate / 100
        else:
            # Hitung dari tax_pct per baris
            for ln_data, ln_obj in zip(lines, so.lines if hasattr(so, '_sa_instance_state') else []):
                pass
            tax_total = sum(
                _to_float(ln.get("qty_ordered")) *
                _to_float(ln.get("unit_price")) *
                (1 - _to_float(ln.get("discount_pct", 0)) / 100) *
                _to_float(ln.get("tax_pct", 0)) / 100
                for ln in lines
            )
        so.subtotal     = round(subtotal, 2)
        so.tax_amount   = round(tax_total, 2)
        so.total_amount = round(subtotal + tax_total, 2)
        db.commit()
        return True, f"SO {number} berhasil dibuat."

    @staticmethod
    def confirm(db: Session, so_id: int, user_id: int) -> tuple[bool, str]:
        so = db.query(SalesOrder).filter_by(id=so_id).first()
        if not so or so.status != "DRAFT":
            return False, "SO harus DRAFT untuk dikonfirmasi."
        so.status = "CONFIRMED"
        so.approved_by = user_id
        so.approved_at = datetime.utcnow()
        db.commit()
        return True, f"SO {so.so_number} dikonfirmasi."

    @staticmethod
    def cancel(db: Session, so_id: int) -> tuple[bool, str]:
        so = db.query(SalesOrder).filter_by(id=so_id).first()
        if not so:
            return False, "SO tidak ditemukan."
        if so.status not in ("DRAFT", "CONFIRMED"):
            return False, "Hanya SO DRAFT/CONFIRMED yang bisa dibatalkan."
        so.status = "CANCELLED"
        db.commit()
        return True, f"SO {so.so_number} dibatalkan."

    @staticmethod
    def get_confirmed_sos(db: Session, company_id: int,
                          branch_id: Optional[int] = None) -> List[SalesOrder]:
        """SO yang bisa dibuat DO — status CONFIRMED atau PARTIAL_DELIVERED."""
        q = db.query(SalesOrder)\
               .filter(
                   SalesOrder.company_id == company_id,
                   SalesOrder.status.in_(["CONFIRMED", "PICKING", "PARTIAL_DELIVERED"]),
               )\
               .options(
                   joinedload(SalesOrder.customer),
                   joinedload(SalesOrder.lines).joinedload(SalesOrderLine.product),
                   joinedload(SalesOrder.lines).joinedload(SalesOrderLine.uom),
               )
        if branch_id:
            q = q.filter(SalesOrder.branch_id == branch_id)
        sos = q.order_by(SalesOrder.created_at.desc()).all()

        # Hanya SO yang masih punya sisa qty belum dikirim
        def _has_remaining(so):
            return any(
                round((ln.qty_ordered or 0) - (ln.qty_delivered or 0), 4) > 0.001
                for ln in (so.lines or [])
            )
        return [so for so in sos if _has_remaining(so)]

    @staticmethod
    def get_invoiceable_sos(db: Session, company_id: int,
                            branch_id: Optional[int] = None) -> List[SalesOrder]:
        """SO yang sudah delivered tapi belum/sebagian diinvoice."""
        q = db.query(SalesOrder)\
               .filter(
                   SalesOrder.company_id == company_id,
                   SalesOrder.status.in_(["DELIVERED", "PARTIAL_DELIVERED", "CONFIRMED",
                                          "PICKING"]),
                   SalesOrder.payment_status.in_(["UNPAID", "PARTIAL"]),
               )\
               .options(
                   joinedload(SalesOrder.customer),
                   joinedload(SalesOrder.lines).joinedload(SalesOrderLine.product),
               )
        if branch_id:
            q = q.filter(SalesOrder.branch_id == branch_id)
        return q.order_by(SalesOrder.created_at.desc()).all()


# ─────────────────────────────────────────────────────────────
# DELIVERY ORDER
# ─────────────────────────────────────────────────────────────
class DeliveryOrderService:

    @staticmethod
    def _gen_number(db: Session, company_id: int) -> str:
        prefix = f"DO-{datetime.now().strftime('%Y%m')}-"
        last = db.query(DeliveryOrder)\
                 .filter(DeliveryOrder.do_number.like(f"{prefix}%"),
                         DeliveryOrder.company_id == company_id)\
                 .order_by(DeliveryOrder.do_number.desc()).first()
        seq = (int(last.do_number.split("-")[-1]) + 1) if last else 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def get_all(db: Session, company_id: int,
                search: str = "", status: str = "",
                branch_id: Optional[int] = None) -> List[DeliveryOrder]:
        q = db.query(DeliveryOrder).filter_by(company_id=company_id)\
               .options(
                   joinedload(DeliveryOrder.so).joinedload(SalesOrder.customer),
                   joinedload(DeliveryOrder.branch),
                   joinedload(DeliveryOrder.warehouse),
                   joinedload(DeliveryOrder.lines).joinedload(DeliveryOrderLine.product),
               )
        if branch_id:
            q = q.filter(DeliveryOrder.branch_id == branch_id)
        if search:
            q = q.filter(DeliveryOrder.do_number.ilike(f"%{search}%"))
        if status:
            q = q.filter(DeliveryOrder.status == status)
        return q.order_by(DeliveryOrder.created_at.desc()).all()

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict, lines: List[Dict]) -> tuple[bool, str]:
        if not lines:
            return False, "Minimal satu item wajib diisi."

        so_id = _to_int(data["so_id"])
        so = db.query(SalesOrder).filter_by(id=so_id)\
               .options(joinedload(SalesOrder.lines)).first()
        if not so:
            return False, "SO tidak ditemukan."

        number = DeliveryOrderService._gen_number(db, company_id)
        do = DeliveryOrder(
            company_id=company_id,
            branch_id=int(data["branch_id"]),
            do_number=number,
            so_id=so_id,
            delivery_date=_to_date(data.get("delivery_date")) or date.today(),
            warehouse_id=int(data["warehouse_id"]),
            shipping_method=data.get("shipping_method", "").strip() or None,
            courier=data.get("courier", "").strip() or None,
            notes=data.get("notes", "").strip() or None,
            created_by=user_id,
            status="DRAFT",
        )
        db.add(do); db.flush()

        for ln in lines:
            sol_id  = _to_int(ln["sol_id"])
            qty     = _to_float(ln["qty_shipped"])
            if qty <= 0: continue

            db.add(DeliveryOrderLine(
                do_id=do.id,
                sol_id=sol_id,
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_shipped=qty,
                lot_number=ln.get("lot_number", "").strip() or None,
            ))

            # Update qty_delivered di SO line
            sol = db.query(SalesOrderLine).filter_by(id=sol_id).first()
            if sol:
                sol.qty_delivered = round((sol.qty_delivered or 0) + qty, 4)

        # Update SO status
        db.flush()
        so_lines = db.query(SalesOrderLine).filter_by(so_id=so_id).all()
        all_delivered = all(
            round((l.qty_delivered or 0), 2) >= round(l.qty_ordered, 2)
            for l in so_lines
        )
        any_delivered = any((l.qty_delivered or 0) > 0 for l in so_lines)
        if all_delivered:
            so.status = "DELIVERED"
        elif any_delivered:
            so.status = "PARTIAL_DELIVERED"
        else:
            so.status = "PICKING"

        db.commit()
        return True, f"DO {number} berhasil dibuat."

    @staticmethod
    def ship(db: Session, do_id: int) -> tuple[bool, str]:
        do = db.query(DeliveryOrder).filter_by(id=do_id).first()
        if not do or do.status != "DRAFT":
            return False, "DO harus DRAFT untuk dikirim."
        do.status    = "SHIPPED"
        do.shipped_at = datetime.utcnow()
        db.commit()
        return True, f"DO {do.do_number} dikirim."

    @staticmethod
    def deliver(db: Session, do_id: int) -> tuple[bool, str]:
        do = db.query(DeliveryOrder).filter_by(id=do_id).first()
        if not do or do.status != "SHIPPED":
            return False, "DO harus SHIPPED untuk dikonfirmasi diterima."
        do.status       = "DELIVERED"
        do.delivered_at = datetime.utcnow()
        db.commit()
        return True, f"DO {do.do_number} dikonfirmasi diterima."

    @staticmethod
    def cancel(db: Session, do_id: int) -> tuple[bool, str]:
        do = db.query(DeliveryOrder)\
               .filter_by(id=do_id)\
               .options(joinedload(DeliveryOrder.lines)).first()
        if not do:
            return False, "DO tidak ditemukan."
        if do.status not in ("DRAFT",):
            return False, "Hanya DO DRAFT yang bisa dibatalkan."

        # Rollback qty_delivered di SO lines
        for ln in (do.lines or []):
            sol = db.query(SalesOrderLine).filter_by(id=ln.sol_id).first()
            if sol:
                sol.qty_delivered = max(0, round((sol.qty_delivered or 0) - ln.qty_shipped, 4))

        # Revert SO status
        so = db.query(SalesOrder)\
               .options(joinedload(SalesOrder.lines))\
               .filter_by(id=do.so_id).first()
        if so:
            any_del = any((l.qty_delivered or 0) > 0 for l in (so.lines or []))
            so.status = "PARTIAL_DELIVERED" if any_del else "CONFIRMED"

        do.status = "CANCELLED"
        db.commit()
        return True, f"DO {do.do_number} dibatalkan."


# ─────────────────────────────────────────────────────────────
# INVOICE
# ─────────────────────────────────────────────────────────────
class InvoiceService:

    @staticmethod
    def _gen_number(db: Session, company_id: int) -> str:
        prefix = f"INV-{datetime.now().strftime('%Y%m')}-"
        last = db.query(Invoice)\
                 .filter(Invoice.invoice_number.like(f"{prefix}%"),
                         Invoice.company_id == company_id)\
                 .order_by(Invoice.invoice_number.desc()).first()
        seq = (int(last.invoice_number.split("-")[-1]) + 1) if last else 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def get_all(db: Session, company_id: int,
                search: str = "", status: str = "",
                branch_id: Optional[int] = None) -> List[Invoice]:
        q = db.query(Invoice).filter_by(company_id=company_id)\
               .options(
                   joinedload(Invoice.customer),
                   joinedload(Invoice.so),
                   joinedload(Invoice.branch),
                   joinedload(Invoice.payments),
               )
        if branch_id:
            q = q.filter(Invoice.branch_id == branch_id)
        if search:
            q = q.filter(or_(
                Invoice.invoice_number.ilike(f"%{search}%"),
                Customer.name.ilike(f"%{search}%"),
            ))
        if status:
            q = q.filter(Invoice.status == status)
        return q.order_by(Invoice.created_at.desc()).all()

    @staticmethod
    def create_from_so(db: Session, company_id: int, user_id: int,
                       data: Dict) -> tuple[bool, str]:
        so_id = _to_int(data.get("so_id"))
        so = db.query(SalesOrder).filter_by(id=so_id)\
               .options(joinedload(SalesOrder.lines)).first()
        if not so:
            return False, "SO tidak ditemukan."

        number = InvoiceService._gen_number(db, company_id)

        subtotal = sum(
            (ln.qty_ordered * ln.unit_price * (1 - (ln.discount_pct or 0) / 100))
            for ln in (so.lines or [])
        )
        # Pakai tax_rate dari SO jika ada, fallback ke sum tax per baris
        if so.tax_rate:
            tax = subtotal * so.tax_rate.rate / 100
        else:
            tax = sum(
                (ln.qty_ordered * ln.unit_price * (1 - (ln.discount_pct or 0) / 100))
                * (ln.tax_pct or 0) / 100
                for ln in (so.lines or [])
            )
        total    = subtotal + tax

        inv = Invoice(
            company_id=company_id,
            branch_id=int(data.get("branch_id") or so.branch_id),
            invoice_number=number,
            invoice_type="SALES",
            invoice_date=_to_date(data.get("invoice_date")) or date.today(),
            due_date=_to_date(data.get("due_date")),
            customer_id=so.customer_id,
            so_id=so_id,
            subtotal=round(subtotal, 2),
            tax_amount=round(tax, 2),
            total_amount=round(total, 2),
            paid_amount=0,
            notes=data.get("notes", "").strip() or None,
            created_by=user_id,
            status="DRAFT",
        )
        db.add(inv); db.flush()

        # Update SO status ke INVOICED jika belum
        so.status = "INVOICED"
        db.commit()
        return True, f"Invoice {number} berhasil dibuat."

    @staticmethod
    def send(db: Session, inv_id: int) -> tuple[bool, str]:
        inv = db.query(Invoice).filter_by(id=inv_id).first()
        if not inv or inv.status != "DRAFT":
            return False, "Invoice harus DRAFT untuk dikirim."
        inv.status = "SENT"
        db.commit()
        return True, f"Invoice {inv.invoice_number} dikirim ke pelanggan."

    @staticmethod
    def cancel(db: Session, inv_id: int) -> tuple[bool, str]:
        inv = db.query(Invoice).filter_by(id=inv_id).first()
        if not inv or inv.status in ("PAID", "CANCELLED"):
            return False, "Invoice tidak bisa dibatalkan."
        # Revert SO status
        if inv.so_id:
            so = db.query(SalesOrder).filter_by(id=inv.so_id).first()
            if so and so.status == "INVOICED":
                so.status = "DELIVERED"
        inv.status = "CANCELLED"
        db.commit()
        return True, f"Invoice {inv.invoice_number} dibatalkan."

    @staticmethod
    def add_payment(db: Session, inv_id: int, user_id: int,
                    data: Dict) -> tuple[bool, str]:
        inv = db.query(Invoice).filter_by(id=inv_id).first()
        if not inv:
            return False, "Invoice tidak ditemukan."
        if inv.status in ("PAID", "CANCELLED"):
            return False, "Invoice sudah lunas atau dibatalkan."

        amount = _to_float(data.get("amount", 0))
        outstanding = inv.total_amount - inv.paid_amount
        if amount <= 0:
            return False, "Jumlah bayar harus > 0."
        if amount > outstanding + 0.01:
            return False, f"Jumlah bayar melebihi sisa tagihan (Rp {outstanding:,.0f})."

        # Gen payment number
        prefix = f"PAY-{datetime.now().strftime('%Y%m')}-"
        last = db.query(Payment)\
                 .filter(Payment.payment_number.like(f"{prefix}%"),
                         Payment.company_id == inv.company_id)\
                 .order_by(Payment.payment_number.desc()).first()
        seq = (int(last.payment_number.split("-")[-1]) + 1) if last else 1
        pay_number = f"{prefix}{seq:04d}"

        pay = Payment(
            company_id=inv.company_id,
            branch_id=inv.branch_id,
            payment_number=pay_number,
            payment_date=_to_date(data.get("payment_date")) or date.today(),
            payment_type="RECEIVED",
            invoice_id=inv_id,
            amount=amount,
            payment_method=data.get("payment_method", "BANK_TRANSFER"),
            reference_number=data.get("reference_number", "").strip() or None,
            notes=data.get("notes", "").strip() or None,
            created_by=user_id,
        )
        db.add(pay); db.flush()

        inv.paid_amount = round(inv.paid_amount + amount, 2)
        if inv.paid_amount >= inv.total_amount - 0.01:
            inv.status = "PAID"
            # Update SO payment_status
            if inv.so_id:
                so = db.query(SalesOrder).filter_by(id=inv.so_id).first()
                if so: so.payment_status = "PAID"
        else:
            inv.status = "PARTIAL"
            if inv.so_id:
                so = db.query(SalesOrder).filter_by(id=inv.so_id).first()
                if so: so.payment_status = "PARTIAL"

        db.commit()
        return True, f"Pembayaran {pay_number} Rp {amount:,.0f} berhasil dicatat."


# ─────────────────────────────────────────────────────────────
# PAYMENT SERVICE
# ─────────────────────────────────────────────────────────────
class PaymentService:

    @staticmethod
    def get_all(db: Session, company_id: int,
                search: str = "",
                method: str = "",
                date_from: Optional[date] = None,
                date_to:   Optional[date] = None,
                branch_id: Optional[int]  = None) -> List[Payment]:
        q = db.query(Payment).filter_by(company_id=company_id)\
               .options(
                   joinedload(Payment.invoice)
                       .joinedload(Invoice.customer),
                   joinedload(Payment.invoice)
                       .joinedload(Invoice.so),
                   joinedload(Payment.branch),
               )
        if branch_id:
            q = q.filter(Payment.branch_id == branch_id)
        if method:
            q = q.filter(Payment.payment_method == method)
        if date_from:
            q = q.filter(Payment.payment_date >= date_from)
        if date_to:
            q = q.filter(Payment.payment_date <= date_to)
        if search:
            q = q.filter(or_(
                Payment.payment_number.ilike(f"%{search}%"),
                Payment.reference_number.ilike(f"%{search}%"),
            ))
        return q.order_by(Payment.payment_date.desc(),
                          Payment.created_at.desc()).all()

    @staticmethod
    def get_summary(db: Session, company_id: int,
                    date_from: Optional[date] = None,
                    date_to:   Optional[date] = None,
                    branch_id: Optional[int]  = None) -> Dict:
        q = db.query(Payment).filter_by(company_id=company_id)
        if branch_id:
            q = q.filter(Payment.branch_id == branch_id)
        if date_from:
            q = q.filter(Payment.payment_date >= date_from)
        if date_to:
            q = q.filter(Payment.payment_date <= date_to)
        payments = q.all()

        total    = sum(p.amount for p in payments)
        by_method: Dict[str, float] = {}
        for p in payments:
            by_method[p.payment_method] = by_method.get(p.payment_method, 0) + p.amount

        return {
            "total":     total,
            "count":     len(payments),
            "by_method": by_method,
        }

    @staticmethod
    def void(db: Session, pay_id: int, user_id: int) -> tuple[bool, str]:
        """Batalkan pembayaran — kurangi paid_amount invoice."""
        pay = db.query(Payment).filter_by(id=pay_id)\
                .options(joinedload(Payment.invoice)).first()
        if not pay:
            return False, "Pembayaran tidak ditemukan."
        if pay.invoice and pay.invoice.status == "PAID":
            return False, "Invoice sudah lunas, tidak bisa dibatalkan."

        inv = pay.invoice
        if inv:
            inv.paid_amount = max(0, round(inv.paid_amount - pay.amount, 2))
            outstanding = inv.total_amount - inv.paid_amount
            if outstanding <= 0.01:
                inv.status = "PAID"
            elif inv.paid_amount > 0.01:
                inv.status = "PARTIAL"
            else:
                inv.status = "SENT"

        db.delete(pay)
        db.commit()
        return True, f"Pembayaran {pay.payment_number} dibatalkan."
