"""
app/services/purchasing_service.py
Service untuk modul Pembelian: Purchase Request, Purchase Order, Goods Receipt

PERBAIKAN UTAMA:
  PR status tidak langsung PO_CREATED saat PO pertama dibuat.
  Status PR dihitung dari persentase item yang sudah masuk PO:
    - APPROVED     : belum ada item yang dibuatkan PO
    - PARTIAL_PO   : sebagian item sudah dibuatkan PO (multi-vendor)
    - PO_CREATED   : semua item yang diapprove sudah dibuatkan PO
"""
from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.models import (
    PurchaseRequest, PurchaseRequestLine,
    PurchaseOrder, PurchaseOrderLine,
    Product, UnitOfMeasure, Branch, Department, User,
)


def _to_float(val, default=0.0):
    try:
        return float(str(val).strip().replace(",", ".")) \
               if val not in (None, "", "None") else default
    except Exception:
        return default


def _to_int(val, default=0):
    try:
        return int(float(str(val).strip().replace(",", "."))) \
               if val not in (None, "", "None") else default
    except Exception:
        return default


def _gen_pr_number(db: Session, company_id: int) -> str:
    prefix = f"PR-{datetime.now().strftime('%Y%m')}-"
    last = db.query(PurchaseRequest)\
             .filter(PurchaseRequest.pr_number.like(f"{prefix}%"),
                     PurchaseRequest.company_id == company_id)\
             .order_by(PurchaseRequest.pr_number.desc()).first()
    seq = (int(last.pr_number.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"


def _gen_po_number(db: Session, company_id: int) -> str:
    prefix = f"PO-{datetime.now().strftime('%Y%m')}-"
    last = db.query(PurchaseOrder)\
             .filter(PurchaseOrder.po_number.like(f"{prefix}%"),
                     PurchaseOrder.company_id == company_id)\
             .order_by(PurchaseOrder.po_number.desc()).first()
    seq = (int(last.po_number.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"


# ─────────────────────────────────────────────────────────────
# HELPER: Hitung ulang status PR berdasarkan item yang sudah di-PO
# ─────────────────────────────────────────────────────────────
def _recalc_pr_status(db: Session, pr_id: int) -> None:
    """
    Cek setiap PurchaseRequestLine:
      - Hitung berapa qty_approved yang sudah tercakup di PO lines aktif
        (PO tidak CANCELLED).
      - Jika semua line sudah tercakup penuh → PO_CREATED
      - Jika sebagian sudah tercakup       → PARTIAL_PO
      - Jika belum ada yang tercakup       → APPROVED (tetap terbuka)

    Dipanggil setiap kali PO dibuat, dibatalkan, atau dihapus.
    """
    pr = db.query(PurchaseRequest).filter_by(id=pr_id).first()
    if not pr or pr.status not in ("APPROVED", "PARTIAL_PO", "PO_CREATED"):
        return

    pr_lines = db.query(PurchaseRequestLine).filter_by(pr_id=pr_id).all()
    if not pr_lines:
        return

    total_lines   = len(pr_lines)
    covered_full  = 0   # line yang qty_approved-nya sudah 100% masuk PO
    covered_any   = 0   # line yang sudah ada PO-nya (walaupun partial)

    for prl in pr_lines:
        qty_need = prl.qty_approved or prl.qty_requested  # qty yang harus dibuatkan PO

        # Jumlahkan qty_ordered dari semua PO lines aktif yang merujuk pr_line ini
        # PO lines yang merujuk PR line: product_id sama, po.pr_id == pr_id,
        # po.status tidak CANCELLED
        qty_in_po = db.query(func.coalesce(func.sum(PurchaseOrderLine.qty_ordered), 0))\
                      .join(PurchaseOrder,
                            PurchaseOrder.id == PurchaseOrderLine.po_id)\
                      .filter(
                          PurchaseOrder.pr_id     == pr_id,
                          PurchaseOrder.status    != "CANCELLED",
                          PurchaseOrderLine.product_id == prl.product_id,
                      ).scalar() or 0

        if qty_in_po >= qty_need:
            covered_full += 1
            covered_any  += 1
        elif qty_in_po > 0:
            covered_any  += 1

    # Tentukan status
    if covered_full == total_lines:
        pr.status = "PO_CREATED"
    elif covered_any > 0:
        pr.status = "PARTIAL_PO"
    else:
        pr.status = "APPROVED"

    db.flush()  # commit dilakukan oleh caller


# ─────────────────────────────────────────────────────────────
# PURCHASE REQUEST SERVICE
# ─────────────────────────────────────────────────────────────
class PurchaseRequestService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "",
                status: str = "", branch_id: Optional[int] = None) -> List[PurchaseRequest]:
        q = db.query(PurchaseRequest).filter_by(company_id=company_id)\
              .options(
                  joinedload(PurchaseRequest.branch),
                  joinedload(PurchaseRequest.department),
                  joinedload(PurchaseRequest.requester),
                  joinedload(PurchaseRequest.approver),
                  joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.product),
                  joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.uom),
              )
        if branch_id:
            q = q.filter(PurchaseRequest.branch_id == branch_id)
        if search:
            q = q.filter(or_(
                PurchaseRequest.pr_number.ilike(f"%{search}%"),
                PurchaseRequest.notes.ilike(f"%{search}%"),
            ))
        if status:
            q = q.filter_by(status=status)
        return q.order_by(PurchaseRequest.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, pr_id: int) -> Optional[PurchaseRequest]:
        return db.query(PurchaseRequest).filter_by(id=pr_id)\
                 .options(
                     joinedload(PurchaseRequest.branch),
                     joinedload(PurchaseRequest.requester),
                     joinedload(PurchaseRequest.approver),
                     joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.product),
                     joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.uom),
                 ).first()

    @staticmethod
    def get_open_prs(db: Session, company_id: int) -> List[PurchaseRequest]:
        """
        PR yang masih 'terbuka' = bisa dibuatkan PO baru.
        Status: APPROVED atau PARTIAL_PO.
        """
        return db.query(PurchaseRequest)\
                 .filter(
                     PurchaseRequest.company_id == company_id,
                     PurchaseRequest.status.in_(["APPROVED", "PARTIAL_PO"]),
                 )\
                 .options(
                     joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.product),
                     joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.uom),
                 )\
                 .order_by(PurchaseRequest.request_date.desc()).all()

    @staticmethod
    def get_unpo_lines(db: Session, pr_id: int) -> List[Dict]:
        """
        Kembalikan lines PR yang qty-nya BELUM PENUH masuk PO.
        Digunakan saat user mau buat PO baru dari PR yang sama (beda vendor).

        Return: list of dict {
            pr_line_id, product_id, product_name, product_code,
            uom_id, uom_name,
            qty_approved, qty_in_po, qty_remaining
        }
        """
        pr_lines = db.query(PurchaseRequestLine)\
                     .options(
                         joinedload(PurchaseRequestLine.product),
                         joinedload(PurchaseRequestLine.uom),
                     )\
                     .filter_by(pr_id=pr_id).all()

        result = []
        for prl in pr_lines:
            qty_need = prl.qty_approved or prl.qty_requested

            qty_in_po = db.query(
                func.coalesce(func.sum(PurchaseOrderLine.qty_ordered), 0)
            ).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)\
             .filter(
                 PurchaseOrder.pr_id     == pr_id,
                 PurchaseOrder.status    != "CANCELLED",
                 PurchaseOrderLine.product_id == prl.product_id,
             ).scalar() or 0

            qty_remaining = max(0, qty_need - qty_in_po)

            if qty_remaining > 0:  # hanya tampilkan yang masih kurang
                result.append({
                    "pr_line_id":   prl.id,
                    "product_id":   prl.product_id,
                    "product_name": prl.product.name if prl.product else "—",
                    "product_code": prl.product.code if prl.product else "—",
                    "uom_id":       prl.uom_id,
                    "uom_name":     prl.uom.name if prl.uom else "—",
                    "qty_approved":  qty_need,
                    "qty_in_po":     qty_in_po,
                    "qty_remaining": qty_remaining,
                    "estimated_price": prl.estimated_price or 0,
                })
        return result

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict, lines: List[Dict]) -> tuple[bool, str, Optional[PurchaseRequest]]:
        if not lines:
            return False, "Minimal satu item wajib diisi.", None

        pr_number = _gen_pr_number(db, company_id)
        pr = PurchaseRequest(
            company_id=company_id,
            branch_id=_to_int(data["branch_id"]),
            department_id=_to_int(data["department_id"]) if data.get("department_id") else None,
            pr_number=pr_number,
            request_date=data.get("request_date") or date.today(),
            required_date=data.get("required_date") or None,
            requested_by=user_id,
            notes=data.get("notes", "").strip() or None,
            status="DRAFT",
        )
        db.add(pr)
        db.flush()

        for ln in lines:
            db.add(PurchaseRequestLine(
                pr_id=pr.id,
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_requested=_to_float(ln["qty_requested"]),
                qty_approved=0,
                estimated_price=_to_float(ln.get("estimated_price")),
                notes=ln.get("notes", "").strip() or None,
            ))
        db.commit()
        return True, f"Purchase Request {pr_number} berhasil dibuat.", pr

    @staticmethod
    def update(db: Session, pr_id: int, data: Dict,
               lines: List[Dict]) -> tuple[bool, str]:
        pr = db.query(PurchaseRequest).filter_by(id=pr_id).first()
        if not pr:
            return False, "PR tidak ditemukan."
        if pr.status not in ("DRAFT",):
            return False, f"PR dengan status '{pr.status}' tidak bisa diedit."
        if not lines:
            return False, "Minimal satu item wajib diisi."

        pr.branch_id     = _to_int(data["branch_id"])
        pr.department_id = _to_int(data["department_id"]) if data.get("department_id") else None
        pr.request_date  = data.get("request_date") or date.today()
        pr.required_date = data.get("required_date") or None
        pr.notes         = data.get("notes", "").strip() or None

        db.query(PurchaseRequestLine).filter_by(pr_id=pr_id).delete()
        for ln in lines:
            db.add(PurchaseRequestLine(
                pr_id=pr.id,
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_requested=_to_float(ln["qty_requested"]),
                qty_approved=0,
                estimated_price=_to_float(ln.get("estimated_price")),
                notes=ln.get("notes", "").strip() or None,
            ))
        db.commit()
        return True, "PR berhasil diperbarui."

    @staticmethod
    def submit(db: Session, pr_id: int) -> tuple[bool, str]:
        pr = db.query(PurchaseRequest).filter_by(id=pr_id).first()
        if not pr:
            return False, "PR tidak ditemukan."
        if pr.status != "DRAFT":
            return False, "Hanya PR DRAFT yang bisa disubmit."
        if not pr.lines:
            return False, "PR tidak memiliki item."
        pr.status = "SUBMITTED"
        db.commit()
        return True, f"PR {pr.pr_number} berhasil disubmit."

    @staticmethod
    def approve(db: Session, pr_id: int, approver_id: int,
                approved_lines: Dict[int, float]) -> tuple[bool, str]:
        """approved_lines = {line_id: qty_approved}"""
        pr = db.query(PurchaseRequest).filter_by(id=pr_id).first()
        if not pr:
            return False, "PR tidak ditemukan."
        if pr.status != "SUBMITTED":
            return False, "Hanya PR SUBMITTED yang bisa diapprove."

        for line in pr.lines:
            qty = approved_lines.get(line.id, 0)
            line.qty_approved = max(0, min(float(qty), line.qty_requested))

        pr.status      = "APPROVED"
        pr.approved_by = approver_id
        pr.approved_at = datetime.utcnow()
        db.commit()
        return True, f"PR {pr.pr_number} berhasil diapprove."

    @staticmethod
    def reject(db: Session, pr_id: int, approver_id: int,
               reason: str = "") -> tuple[bool, str]:
        pr = db.query(PurchaseRequest).filter_by(id=pr_id).first()
        if not pr:
            return False, "PR tidak ditemukan."
        if pr.status != "SUBMITTED":
            return False, "Hanya PR SUBMITTED yang bisa direject."
        pr.status      = "REJECTED"
        pr.approved_by = approver_id
        pr.approved_at = datetime.utcnow()
        if reason:
            pr.notes = f"[DITOLAK: {reason}]\n{pr.notes or ''}"
        db.commit()
        return True, f"PR {pr.pr_number} ditolak."

    @staticmethod
    def cancel(db: Session, pr_id: int) -> tuple[bool, str]:
        pr = db.query(PurchaseRequest).filter_by(id=pr_id).first()
        if not pr:
            return False, "PR tidak ditemukan."
        if pr.status in ("PO_CREATED", "CANCELLED"):
            return False, f"PR tidak bisa dibatalkan dari status '{pr.status}'."
        pr.status = "CANCELLED"
        db.commit()
        return True, f"PR {pr.pr_number} dibatalkan."

    @staticmethod
    def delete(db: Session, pr_id: int) -> tuple[bool, str]:
        pr = db.query(PurchaseRequest).filter_by(id=pr_id).first()
        if not pr:
            return False, "PR tidak ditemukan."
        if pr.status != "DRAFT":
            return False, "Hanya PR DRAFT yang bisa dihapus."
        db.query(PurchaseRequestLine).filter_by(pr_id=pr_id).delete()
        db.delete(pr)
        db.commit()
        return True, "PR berhasil dihapus."


# ─────────────────────────────────────────────────────────────
# PURCHASE ORDER SERVICE
# ─────────────────────────────────────────────────────────────
class PurchaseOrderService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "",
                status: str = "", branch_id: Optional[int] = None) -> List:
        q = db.query(PurchaseOrder).filter_by(company_id=company_id)\
              .options(
                  joinedload(PurchaseOrder.branch),
                  joinedload(PurchaseOrder.vendor),
                  joinedload(PurchaseOrder.warehouse),
                  joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.product),
                  joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.uom),
              )
        if branch_id:
            q = q.filter(PurchaseOrder.branch_id == branch_id)
        if search:
            q = q.filter(or_(
                PurchaseOrder.po_number.ilike(f"%{search}%"),
                PurchaseOrder.notes.ilike(f"%{search}%"),
            ))
        if status:
            q = q.filter_by(status=status)
        return q.order_by(PurchaseOrder.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, po_id: int):
        return db.query(PurchaseOrder).filter_by(id=po_id)\
                 .options(
                     joinedload(PurchaseOrder.branch),
                     joinedload(PurchaseOrder.vendor),
                     joinedload(PurchaseOrder.warehouse),
                     joinedload(PurchaseOrder.creator),
                     joinedload(PurchaseOrder.approver),
                     joinedload(PurchaseOrder.pr),
                     joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.product),
                     joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.uom),
                 ).first()

    @staticmethod
    def get_open_prs(db: Session, company_id: int) -> List:
        """
        PR yang masih terbuka (APPROVED atau PARTIAL_PO).
        Digunakan saat buat PO baru untuk memilih PR referensi.
        """
        return db.query(PurchaseRequest)\
                 .filter(
                     PurchaseRequest.company_id == company_id,
                     PurchaseRequest.status.in_(["APPROVED", "PARTIAL_PO"]),
                 )\
                 .order_by(PurchaseRequest.request_date.desc()).all()

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict, lines: List[Dict]) -> tuple[bool, str, Optional[object]]:
        if not lines:
            return False, "Minimal satu item wajib diisi.", None

        po_number = _gen_po_number(db, company_id)

        subtotal = sum(
            _to_float(ln["qty_ordered"]) * _to_float(ln["unit_price"]) *
            (1 - _to_float(ln.get("discount_pct")) / 100)
            for ln in lines
        )
        tax_amount = sum(
            _to_float(ln["qty_ordered"]) * _to_float(ln["unit_price"]) *
            _to_float(ln.get("tax_pct")) / 100
            for ln in lines
        )
        shipping = _to_float(data.get("shipping_cost"))
        discount = _to_float(data.get("discount_amount"))
        total    = subtotal + tax_amount + shipping - discount

        po = PurchaseOrder(
            company_id=company_id,
            branch_id=_to_int(data["branch_id"]),
            pr_id=_to_int(data["pr_id"]) if data.get("pr_id") else None,
            po_number=po_number,
            vendor_id=_to_int(data["vendor_id"]),
            order_date=data.get("order_date") or date.today(),
            expected_date=data.get("expected_date") or None,
            currency_code=data.get("currency_code", "IDR"),
            exchange_rate=_to_float(data.get("exchange_rate"), 1.0),
            subtotal=round(subtotal, 2),
            tax_amount=round(tax_amount, 2),
            discount_amount=round(discount, 2),
            shipping_cost=round(shipping, 2),
            total_amount=round(total, 2),
            payment_terms=data.get("payment_terms", "").strip() or None,
            shipping_method=data.get("shipping_method", "").strip() or None,
            warehouse_id=_to_int(data["warehouse_id"]) if data.get("warehouse_id") else None,
            notes=data.get("notes", "").strip() or None,
            status="DRAFT",
            created_by=user_id,
        )
        db.add(po)
        db.flush()

        for ln in lines:
            db.add(PurchaseOrderLine(
                po_id=po.id,
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_ordered=_to_float(ln["qty_ordered"]),
                unit_price=_to_float(ln["unit_price"]),
                tax_pct=_to_float(ln.get("tax_pct")),
                discount_pct=_to_float(ln.get("discount_pct")),
                notes=ln.get("notes", "").strip() or None,
            ))

        # ── PERBAIKAN: Hitung ulang status PR, jangan langsung PO_CREATED ──
        if po.pr_id:
            db.flush()  # pastikan PO lines sudah masuk sebelum dihitung
            _recalc_pr_status(db, po.pr_id)

        db.commit()
        return True, f"Purchase Order {po_number} berhasil dibuat.", po

    @staticmethod
    def update(db: Session, po_id: int, data: Dict,
               lines: List[Dict]) -> tuple[bool, str]:
        po = db.query(PurchaseOrder).filter_by(id=po_id).first()
        if not po:
            return False, "PO tidak ditemukan."
        if po.status not in ("DRAFT",):
            return False, f"PO '{po.status}' tidak bisa diedit."
        if not lines:
            return False, "Minimal satu item wajib diisi."

        subtotal = sum(
            _to_float(ln["qty_ordered"]) * _to_float(ln["unit_price"]) *
            (1 - _to_float(ln.get("discount_pct")) / 100)
            for ln in lines
        )
        tax_amount = sum(
            _to_float(ln["qty_ordered"]) * _to_float(ln["unit_price"]) *
            _to_float(ln.get("tax_pct")) / 100
            for ln in lines
        )
        shipping = _to_float(data.get("shipping_cost"))
        discount = _to_float(data.get("discount_amount"))
        total    = subtotal + tax_amount + shipping - discount

        pr_id_old = po.pr_id  # simpan sebelum update

        po.branch_id       = _to_int(data["branch_id"])
        po.vendor_id       = _to_int(data["vendor_id"])
        po.order_date      = data.get("order_date") or date.today()
        po.expected_date   = data.get("expected_date") or None
        po.currency_code   = data.get("currency_code", "IDR")
        po.exchange_rate   = _to_float(data.get("exchange_rate"), 1.0)
        po.subtotal        = round(subtotal, 2)
        po.tax_amount      = round(tax_amount, 2)
        po.discount_amount = round(discount, 2)
        po.shipping_cost   = round(shipping, 2)
        po.total_amount    = round(total, 2)
        po.payment_terms   = data.get("payment_terms", "").strip() or None
        po.shipping_method = data.get("shipping_method", "").strip() or None
        po.warehouse_id    = _to_int(data["warehouse_id"]) if data.get("warehouse_id") else None
        po.notes           = data.get("notes", "").strip() or None

        db.query(PurchaseOrderLine).filter_by(po_id=po_id).delete()
        for ln in lines:
            db.add(PurchaseOrderLine(
                po_id=po.id,
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_ordered=_to_float(ln["qty_ordered"]),
                unit_price=_to_float(ln["unit_price"]),
                tax_pct=_to_float(ln.get("tax_pct")),
                discount_pct=_to_float(ln.get("discount_pct")),
                notes=ln.get("notes", "").strip() or None,
            ))

        # Recalc PR status setelah lines berubah
        if pr_id_old:
            db.flush()
            _recalc_pr_status(db, pr_id_old)

        db.commit()
        return True, "PO berhasil diperbarui."

    @staticmethod
    def send(db: Session, po_id: int) -> tuple[bool, str]:
        po = db.query(PurchaseOrder).filter_by(id=po_id).first()
        if not po:
            return False, "PO tidak ditemukan."
        if po.status != "DRAFT":
            return False, "Hanya PO DRAFT yang bisa dikirim."
        po.status = "SENT"
        db.commit()
        return True, f"PO {po.po_number} berhasil dikirim ke vendor."

    @staticmethod
    def confirm(db: Session, po_id: int, approver_id: int) -> tuple[bool, str]:
        po = db.query(PurchaseOrder).filter_by(id=po_id).first()
        if not po:
            return False, "PO tidak ditemukan."
        if po.status != "SENT":
            return False, "Hanya PO SENT yang bisa dikonfirmasi."
        po.status      = "CONFIRMED"
        po.approved_by = approver_id
        po.approved_at = datetime.utcnow()
        db.commit()
        return True, f"PO {po.po_number} dikonfirmasi."

    @staticmethod
    def cancel(db: Session, po_id: int) -> tuple[bool, str]:
        po = db.query(PurchaseOrder).filter_by(id=po_id).first()
        if not po:
            return False, "PO tidak ditemukan."
        if po.status in ("RECEIVED", "CANCELLED"):
            return False, f"PO tidak bisa dibatalkan dari status '{po.status}'."

        pr_id = po.pr_id
        po.status = "CANCELLED"

        # Recalc PR: PO dibatalkan → mungkin item kembali terbuka
        if pr_id:
            db.flush()
            _recalc_pr_status(db, pr_id)

        db.commit()
        return True, f"PO {po.po_number} dibatalkan."

    @staticmethod
    def delete(db: Session, po_id: int) -> tuple[bool, str]:
        po = db.query(PurchaseOrder).filter_by(id=po_id).first()
        if not po:
            return False, "PO tidak ditemukan."
        if po.status != "DRAFT":
            return False, "Hanya PO DRAFT yang bisa dihapus."

        pr_id = po.pr_id
        db.query(PurchaseOrderLine).filter_by(po_id=po_id).delete()
        db.delete(po)

        # Recalc PR: PO dihapus → item kembali terbuka
        if pr_id:
            db.flush()
            _recalc_pr_status(db, pr_id)

        db.commit()
        return True, "PO berhasil dihapus."