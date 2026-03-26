"""
app/services/commission_service.py

Alur komisi:
  1. Setup skema per partner / customer referral
  2. Saat SO di-invoice/lunas → generate CommissionTransaction otomatis
  3. Admin review → APPROVED
  4. Buat CommissionPayment → semua transaksi APPROVED → PAID
"""
from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.models import (
    CommissionScheme, CommissionTransaction,
    CommissionPayment, CommissionPaymentItem,
    Partner, Customer, SalesOrder, Invoice,
    Company,
)


def _to_float(val, default=0.0):
    try:
        return float(str(val).strip()) if val not in (None, "", "None") else default
    except Exception:
        return default


def _gen_payment_number(db: Session, company_id: int) -> str:
    prefix = f"COMP-{datetime.now().strftime('%Y%m')}-"
    last = db.query(CommissionPayment)\
             .filter(CommissionPayment.payment_number.like(f"{prefix}%"),
                     CommissionPayment.company_id == company_id)\
             .order_by(CommissionPayment.payment_number.desc()).first()
    seq = (int(last.payment_number.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"


def _is_first_so(db: Session, customer_id: int, so_id: int) -> bool:
    """Cek apakah SO ini adalah SO pertama customer."""
    earlier = db.query(SalesOrder)\
                .filter(
                    SalesOrder.customer_id == customer_id,
                    SalesOrder.id != so_id,
                    SalesOrder.status.notin_(["CANCELLED"]),
                ).count()
    return earlier == 0


def _calc_commission(scheme: CommissionScheme, so_amount: float,
                     is_first: bool) -> tuple[float, float, float]:
    """
    Return (commission_from_pct, flat_amount, total)
    """
    # Cek kondisi apply_on
    if scheme.apply_on == "FIRST_SO_ONLY" and not is_first:
        return 0, 0, 0
    if scheme.apply_on == "REPEAT_SO_ONLY" and is_first:
        return 0, 0, 0

    # Cek minimum SO amount
    if scheme.min_so_amount > 0 and so_amount < scheme.min_so_amount:
        return 0, 0, 0

    comm_pct  = 0.0
    comm_flat = 0.0

    if scheme.commission_type in ("PERCENTAGE", "COMBINATION"):
        comm_pct = round(so_amount * scheme.commission_pct / 100, 2)
        if scheme.max_commission_per_so > 0:
            comm_pct = min(comm_pct, scheme.max_commission_per_so)

    if scheme.commission_type in ("FLAT", "COMBINATION"):
        # Flat hanya untuk SO pertama customer (new customer)
        if is_first:
            comm_flat = round(scheme.flat_amount, 2)

    total = round(comm_pct + comm_flat, 2)
    return comm_pct, comm_flat, total


# ─────────────────────────────────────────────────────────────
# SCHEME CRUD
# ─────────────────────────────────────────────────────────────
class CommissionSchemeService:

    @staticmethod
    def get_all(db: Session, company_id: int,
                scheme_for: str = "") -> List[CommissionScheme]:
        q = db.query(CommissionScheme)\
              .filter_by(company_id=company_id)\
              .options(
                  joinedload(CommissionScheme.partner),
                  joinedload(CommissionScheme.ref_customer),
              )
        if scheme_for:
            q = q.filter_by(scheme_for=scheme_for)
        return q.order_by(CommissionScheme.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, scheme_id: int) -> Optional[CommissionScheme]:
        return db.query(CommissionScheme).filter_by(id=scheme_id)\
                 .options(
                     joinedload(CommissionScheme.partner),
                     joinedload(CommissionScheme.ref_customer),
                     joinedload(CommissionScheme.creator),
                 ).first()

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict) -> tuple[bool, str, Optional[CommissionScheme]]:
        scheme = CommissionScheme(
            company_id=company_id,
            scheme_for=data.get("scheme_for", "PARTNER"),
            partner_id=int(data["partner_id"]) if data.get("partner_id") else None,
            referring_customer_id=int(data["referring_customer_id"])
                if data.get("referring_customer_id") else None,
            name=data["name"].strip(),
            description=data.get("description", "").strip() or None,
            commission_type=data.get("commission_type", "PERCENTAGE"),
            commission_pct=_to_float(data.get("commission_pct", 0)),
            max_commission_per_so=_to_float(data.get("max_commission_per_so", 0)),
            flat_amount=_to_float(data.get("flat_amount", 0)),
            apply_on=data.get("apply_on", "ALL_SO"),
            min_so_amount=_to_float(data.get("min_so_amount", 0)),
            valid_from=data.get("valid_from"),
            valid_until=data.get("valid_until"),
            is_active=bool(data.get("is_active", True)),
            created_by=user_id,
        )
        db.add(scheme)
        db.commit()
        return True, f"Skema komisi '{scheme.name}' berhasil dibuat.", scheme

    @staticmethod
    def update(db: Session, scheme_id: int,
               data: Dict) -> tuple[bool, str]:
        scheme = db.query(CommissionScheme).filter_by(id=scheme_id).first()
        if not scheme:
            return False, "Skema tidak ditemukan."
        for field in ["name", "description", "commission_type", "commission_pct",
                      "max_commission_per_so", "flat_amount", "apply_on",
                      "min_so_amount", "valid_from", "valid_until", "is_active"]:
            if field in data:
                val = data[field]
                if field in ("commission_pct", "max_commission_per_so",
                             "flat_amount", "min_so_amount"):
                    val = _to_float(val)
                setattr(scheme, field, val)
        db.commit()
        return True, "Skema berhasil diupdate."

    @staticmethod
    def delete(db: Session, scheme_id: int) -> tuple[bool, str]:
        scheme = db.query(CommissionScheme).filter_by(id=scheme_id).first()
        if not scheme:
            return False, "Skema tidak ditemukan."
        has_tx = db.query(CommissionTransaction)\
                   .filter_by(scheme_id=scheme_id).count()
        if has_tx:
            return False, "Skema tidak bisa dihapus karena sudah ada transaksi komisi."
        db.delete(scheme)
        db.commit()
        return True, "Skema berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# GENERATE COMMISSION  (dipanggil saat SO lunas)
# ─────────────────────────────────────────────────────────────
class CommissionTransactionService:

    @staticmethod
    def generate_for_so(db: Session, so_id: int,
                        invoice_id: Optional[int] = None) -> List[CommissionTransaction]:
        """
        Generate CommissionTransaction untuk satu SO yang baru lunas.
        Dipanggil dari invoice service saat status → PAID.

        Return: list transaksi yang berhasil dibuat.
        """
        so = db.query(SalesOrder).filter_by(id=so_id)\
               .options(joinedload(SalesOrder.customer)).first()
        if not so:
            return []

        customer   = so.customer
        company_id = so.company_id
        so_amount  = so.total_amount or 0
        is_first   = _is_first_so(db, customer.id, so_id)
        today      = date.today()
        created    = []

        # ── Cari skema yang berlaku ───────────────────────────
        # Prioritas: skema spesifik per partner/customer > skema default

        def _find_schemes(scheme_for: str, entity_id: Optional[int]) -> List[CommissionScheme]:
            """Cari skema aktif yang berlaku hari ini."""
            q = db.query(CommissionScheme).filter(
                CommissionScheme.company_id == company_id,
                CommissionScheme.scheme_for == scheme_for,
                CommissionScheme.is_active == True,
                or_(CommissionScheme.valid_from == None,
                    CommissionScheme.valid_from <= today),
                or_(CommissionScheme.valid_until == None,
                    CommissionScheme.valid_until >= today),
            )
            if entity_id:
                # Skema spesifik dulu, lalu default (NULL)
                specific = q.filter(
                    getattr(CommissionScheme,
                            "partner_id" if scheme_for == "PARTNER"
                            else "referring_customer_id") == entity_id
                ).all()
                if specific:
                    return specific
                # Fallback ke default
                return q.filter(
                    getattr(CommissionScheme,
                            "partner_id" if scheme_for == "PARTNER"
                            else "referring_customer_id") == None
                ).all()
            return []

        # ── 1. Komisi untuk PARTNER ───────────────────────────
        if customer.partner_id:
            schemes = _find_schemes("PARTNER", customer.partner_id)
            for scheme in schemes:
                # Cek sudah ada transaksi untuk SO + scheme ini
                exists = db.query(CommissionTransaction).filter_by(
                    so_id=so_id, scheme_id=scheme.id
                ).first()
                if exists:
                    continue

                cp, cf, total = _calc_commission(scheme, so_amount, is_first)
                if total <= 0:
                    continue

                tx = CommissionTransaction(
                    company_id=company_id,
                    scheme_id=scheme.id,
                    recipient_type="PARTNER",
                    partner_id=customer.partner_id,
                    so_id=so_id,
                    customer_id=customer.id,
                    invoice_id=invoice_id,
                    so_amount=so_amount,
                    commission_pct=scheme.commission_pct,
                    commission_from_pct=cp,
                    flat_amount=cf,
                    total_commission=total,
                    status="PENDING",
                    is_first_so=is_first,
                )
                db.add(tx)
                created.append(tx)

        # ── 2. Komisi untuk CUSTOMER REFERRAL ─────────────────
        # Ambil dari customer.referred_by_customer_id jika ada
        # (field ini ada di DDL tapi mungkin belum di ORM — cek)
        ref_cust_id = getattr(customer, "referred_by_customer_id", None)
        if ref_cust_id:
            schemes = _find_schemes("CUSTOMER_REFERRAL", ref_cust_id)
            for scheme in schemes:
                exists = db.query(CommissionTransaction).filter_by(
                    so_id=so_id, scheme_id=scheme.id
                ).first()
                if exists:
                    continue

                cp, cf, total = _calc_commission(scheme, so_amount, is_first)
                if total <= 0:
                    continue

                tx = CommissionTransaction(
                    company_id=company_id,
                    scheme_id=scheme.id,
                    recipient_type="CUSTOMER_REFERRAL",
                    referring_customer_id=ref_cust_id,
                    so_id=so_id,
                    customer_id=customer.id,
                    invoice_id=invoice_id,
                    so_amount=so_amount,
                    commission_pct=scheme.commission_pct,
                    commission_from_pct=cp,
                    flat_amount=cf,
                    total_commission=total,
                    status="PENDING",
                    is_first_so=is_first,
                )
                db.add(tx)
                created.append(tx)

        if created:
            db.commit()
        return created

    @staticmethod
    def get_all(db: Session, company_id: int,
                status: str = "",
                recipient_type: str = "",
                partner_id: Optional[int] = None,
                search: str = "") -> List[CommissionTransaction]:
        q = db.query(CommissionTransaction)\
              .filter_by(company_id=company_id)\
              .options(
                  joinedload(CommissionTransaction.scheme),
                  joinedload(CommissionTransaction.partner),
                  joinedload(CommissionTransaction.ref_customer),
                  joinedload(CommissionTransaction.so),
                  joinedload(CommissionTransaction.customer),
              )
        if status:
            q = q.filter_by(status=status)
        if recipient_type:
            q = q.filter_by(recipient_type=recipient_type)
        if partner_id:
            q = q.filter_by(partner_id=partner_id)
        if search:
            q = q.join(Partner, CommissionTransaction.partner_id == Partner.id,
                       isouter=True)\
                 .join(SalesOrder, CommissionTransaction.so_id == SalesOrder.id)\
                 .filter(or_(
                     Partner.name.ilike(f"%{search}%"),
                     SalesOrder.so_number.ilike(f"%{search}%"),
                 ))
        return q.order_by(CommissionTransaction.created_at.desc()).all()

    @staticmethod
    def approve(db: Session, tx_id: int,
                approver_id: int) -> tuple[bool, str]:
        tx = db.query(CommissionTransaction).filter_by(id=tx_id).first()
        if not tx:
            return False, "Transaksi tidak ditemukan."
        if tx.status != "PENDING":
            return False, f"Status '{tx.status}' tidak bisa di-approve."
        tx.status      = "APPROVED"
        tx.approved_by = approver_id
        tx.approved_at = datetime.utcnow()
        db.commit()
        return True, "Komisi disetujui."

    @staticmethod
    def cancel(db: Session, tx_id: int) -> tuple[bool, str]:
        tx = db.query(CommissionTransaction).filter_by(id=tx_id).first()
        if not tx:
            return False, "Transaksi tidak ditemukan."
        if tx.status == "PAID":
            return False, "Komisi yang sudah dibayar tidak bisa dibatalkan."
        tx.status = "CANCELLED"
        db.commit()
        return True, "Komisi dibatalkan."

    @staticmethod
    def get_summary_by_partner(db: Session, company_id: int) -> List[Dict]:
        """Ringkasan komisi per partner — untuk dashboard."""
        rows = db.query(
            CommissionTransaction.partner_id,
            Partner.name.label("partner_name"),
            func.count(CommissionTransaction.id).label("total_tx"),
            func.sum(CommissionTransaction.total_commission).label("total_amount"),
            func.sum(
                func.case(
                    (CommissionTransaction.status == "PENDING",
                     CommissionTransaction.total_commission), else_=0
                )
            ).label("pending_amount"),
            func.sum(
                func.case(
                    (CommissionTransaction.status == "PAID",
                     CommissionTransaction.total_commission), else_=0
                )
            ).label("paid_amount"),
        ).join(Partner, CommissionTransaction.partner_id == Partner.id,
               isouter=True)\
         .filter(
             CommissionTransaction.company_id == company_id,
             CommissionTransaction.recipient_type == "PARTNER",
         ).group_by(CommissionTransaction.partner_id, Partner.name)\
          .all()

        return [{
            "partner_id":     r.partner_id,
            "partner_name":   r.partner_name or "—",
            "total_tx":       r.total_tx,
            "total_amount":   r.total_amount or 0,
            "pending_amount": r.pending_amount or 0,
            "paid_amount":    r.paid_amount or 0,
        } for r in rows]


# ─────────────────────────────────────────────────────────────
# COMMISSION PAYMENT  (Bayar komisi batch)
# ─────────────────────────────────────────────────────────────
class CommissionPaymentService:

    @staticmethod
    def get_pending(db: Session, company_id: int,
                    recipient_type: str = "PARTNER",
                    partner_id: Optional[int] = None,
                    referring_customer_id: Optional[int] = None
                    ) -> List[CommissionTransaction]:
        """Ambil semua komisi APPROVED yang belum dibayar."""
        q = db.query(CommissionTransaction)\
              .filter(
                  CommissionTransaction.company_id == company_id,
                  CommissionTransaction.status == "APPROVED",
                  CommissionTransaction.recipient_type == recipient_type,
              )\
              .options(
                  joinedload(CommissionTransaction.so),
                  joinedload(CommissionTransaction.customer),
                  joinedload(CommissionTransaction.scheme),
              )
        if partner_id:
            q = q.filter_by(partner_id=partner_id)
        if referring_customer_id:
            q = q.filter_by(referring_customer_id=referring_customer_id)
        return q.order_by(CommissionTransaction.created_at).all()

    @staticmethod
    def create_payment(db: Session, company_id: int, user_id: int,
                       data: Dict,
                       tx_ids: List[int]) -> tuple[bool, str, Optional[CommissionPayment]]:
        """
        Buat pembayaran komisi untuk beberapa transaksi sekaligus.
        tx_ids: list CommissionTransaction.id yang akan dibayar.
        """
        if not tx_ids:
            return False, "Pilih minimal satu komisi.", None

        txs = db.query(CommissionTransaction)\
                .filter(
                    CommissionTransaction.id.in_(tx_ids),
                    CommissionTransaction.company_id == company_id,
                    CommissionTransaction.status == "APPROVED",
                ).all()

        if not txs:
            return False, "Tidak ada transaksi komisi yang valid.", None

        total = sum(tx.total_commission for tx in txs)
        payment_number = _gen_payment_number(db, company_id)

        pmt = CommissionPayment(
            company_id=company_id,
            payment_number=payment_number,
            payment_date=data.get("payment_date") or date.today(),
            recipient_type=data.get("recipient_type", "PARTNER"),
            partner_id=int(data["partner_id"]) if data.get("partner_id") else None,
            referring_customer_id=int(data["referring_customer_id"])
                if data.get("referring_customer_id") else None,
            total_amount=round(total, 2),
            payment_method=data.get("payment_method", "BANK_TRANSFER"),
            reference_number=data.get("reference_number", "").strip() or None,
            notes=data.get("notes", "").strip() or None,
            created_by=user_id,
        )
        db.add(pmt)
        db.flush()

        for tx in txs:
            db.add(CommissionPaymentItem(
                payment_id=pmt.id,
                transaction_id=tx.id,
                amount=tx.total_commission,
            ))
            tx.status  = "PAID"
            tx.paid_at = datetime.utcnow()
            tx.paid_by = user_id

        db.commit()
        return True, f"Pembayaran komisi {payment_number} berhasil. Total: Rp {total:,.0f}", pmt

    @staticmethod
    def get_all(db: Session, company_id: int) -> List[CommissionPayment]:
        return db.query(CommissionPayment)\
                 .filter_by(company_id=company_id)\
                 .options(
                     joinedload(CommissionPayment.partner),
                     joinedload(CommissionPayment.ref_customer),
                     joinedload(CommissionPayment.items)
                         .joinedload(CommissionPaymentItem.transaction)
                         .joinedload(CommissionTransaction.so),
                 )\
                 .order_by(CommissionPayment.created_at.desc()).all()