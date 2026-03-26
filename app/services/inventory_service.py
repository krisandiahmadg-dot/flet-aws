"""
app/services/inventory_service.py
Service untuk semua modul Inventory:
- StockBalance  : saldo stok terkini
- StockMovement : pergerakan stok (read-only view dari GR dll)
- StockTransfer : transfer antar cabang
- StockOpname   : stock count / inventory count
"""
from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func, and_

from app.models import (
    StockBalance, Product, Branch, Warehouse,
    ProductCategory, GoodsReceipt, GoodsReceiptLine,
)


def _to_float(val, default=0.0):
    try:
        return float(str(val).strip()) if val not in (None, "", "None") else default
    except: return default


def _to_int(val, default=0):
    try:
        return int(float(str(val).strip())) if val not in (None, "", "None") else default
    except: return default


# ─────────────────────────────────────────────────────────────
# STOCK BALANCE
# ─────────────────────────────────────────────────────────────
class StockBalanceService:

    @staticmethod
    def get_all(db: Session, company_id: int,
                search: str = "",
                branch_id: Optional[int] = None,
                warehouse_id: Optional[int] = None,
                category_id: Optional[int] = None,
                below_min: bool = False) -> List[StockBalance]:

        q = db.query(StockBalance)\
               .join(Product,   StockBalance.product_id   == Product.id)\
               .join(Branch,    StockBalance.branch_id    == Branch.id)\
               .join(Warehouse, StockBalance.warehouse_id == Warehouse.id)\
               .filter(Branch.company_id == company_id)\
               .options(
                   joinedload(StockBalance.product)
                       .joinedload(Product.uom),
                   joinedload(StockBalance.product)
                       .joinedload(Product.category),
                   joinedload(StockBalance.branch),
                   joinedload(StockBalance.warehouse),
               )

        if search:
            q = q.filter(or_(
                Product.name.ilike(f"%{search}%"),
                Product.code.ilike(f"%{search}%"),
            ))
        if branch_id:
            q = q.filter(StockBalance.branch_id == branch_id)
        if warehouse_id:
            q = q.filter(StockBalance.warehouse_id == warehouse_id)
        if category_id:
            q = q.filter(Product.category_id == category_id)
        if below_min:
            q = q.filter(
                StockBalance.qty_on_hand <= Product.min_stock,
                Product.min_stock > 0,
            )

        return q.order_by(Product.name, Branch.name).all()

    @staticmethod
    def get_summary(db: Session, company_id: int,
                    branch_id: Optional[int] = None) -> Dict:
        """Ringkasan: total SKU, total nilai, item under minimum."""
        q = db.query(StockBalance)\
               .join(Branch, StockBalance.branch_id == Branch.id)\
               .join(Product, StockBalance.product_id == Product.id)\
               .filter(Branch.company_id == company_id)
        if branch_id:
            q = q.filter(StockBalance.branch_id == branch_id)
        rows = q.all()

        total_sku    = len(set(r.product_id for r in rows))
        total_value  = sum(r.qty_on_hand * r.avg_cost for r in rows)
        below_min    = sum(1 for r in rows
                          if r.product.min_stock > 0
                          and r.qty_on_hand < r.product.min_stock)
        return {
            "total_sku":   total_sku,
            "total_value": total_value,
            "below_min":   below_min,
            "total_items": len(rows),
        }


# ─────────────────────────────────────────────────────────────
# STOCK TRANSFER
# ─────────────────────────────────────────────────────────────
class StockTransferService:

    @staticmethod
    def get_all(db: Session, company_id: int,
                search: str = "", status: str = "",
                branch_id: Optional[int] = None) -> List:
        from app.models import StockTransfer
        q = db.query(StockTransfer)\
               .filter_by(company_id=company_id)\
               .options(
                   joinedload(StockTransfer.from_branch),
                   joinedload(StockTransfer.to_branch),
                   joinedload(StockTransfer.from_warehouse),
                   joinedload(StockTransfer.to_warehouse),
                   joinedload(StockTransfer.lines)
                       .joinedload(StockTransfer.lines.property.mapper.class_.product),
               )
        if branch_id:
            q = q.filter(or_(
                StockTransfer.from_branch_id == branch_id,
                StockTransfer.to_branch_id == branch_id,
            ))
        if search:
            q = q.filter(StockTransfer.transfer_number.ilike(f"%{search}%"))
        if status:
            q = q.filter_by(status=status)
        return q.order_by(StockTransfer.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, tid: int):
        from app.models import StockTransfer, StockTransferLine
        return db.query(StockTransfer).filter_by(id=tid)\
                 .options(
                     joinedload(StockTransfer.from_branch),
                     joinedload(StockTransfer.to_branch),
                     joinedload(StockTransfer.from_warehouse),
                     joinedload(StockTransfer.to_warehouse),
                     joinedload(StockTransfer.lines)
                         .joinedload(StockTransferLine.product),
                     joinedload(StockTransfer.lines)
                         .joinedload(StockTransferLine.uom),
                 ).first()

    @staticmethod
    def _gen_number(db: Session, company_id: int) -> str:
        from app.models import StockTransfer
        prefix = f"TRF-{datetime.now().strftime('%Y%m')}-"
        last = db.query(StockTransfer)\
                 .filter(StockTransfer.transfer_number.like(f"{prefix}%"),
                         StockTransfer.company_id == company_id)\
                 .order_by(StockTransfer.transfer_number.desc()).first()
        seq = (int(last.transfer_number.split("-")[-1]) + 1) if last else 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict, lines: List[Dict]) -> tuple[bool, str]:
        from app.models import StockTransfer, StockTransferLine
        if not lines:
            return False, "Minimal satu item wajib diisi."

        number = StockTransferService._gen_number(db, company_id)
        tr = StockTransfer(
            company_id=company_id,
            transfer_number=number,
            transfer_date=data.get("transfer_date") or date.today(),
            from_branch_id=int(data["from_branch_id"]),
            from_warehouse_id=int(data["from_warehouse_id"]),
            to_branch_id=int(data["to_branch_id"]),
            to_warehouse_id=int(data["to_warehouse_id"]),
            notes=data.get("notes", "").strip() or None,
            requested_by=user_id,
            status="DRAFT",
        )
        db.add(tr); db.flush()

        for ln in lines:
            db.add(StockTransferLine(
                transfer_id=tr.id,
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_requested=_to_float(ln["qty_requested"]),
                unit_cost=_to_float(ln.get("unit_cost", 0)),
            ))
        db.commit()
        return True, f"Transfer {number} berhasil dibuat."

    @staticmethod
    def confirm_ship(db: Session, tid: int, user_id: int,
                     tracking_number: str = "",
                     shipping_method: str = "") -> tuple[bool, str]:
        """Kirim — kurangi stok asal, simpan nomor resi."""
        from app.models import StockTransfer, StockTransferLine
        tr = db.query(StockTransfer).filter_by(id=tid)\
               .options(joinedload(StockTransfer.lines)).first()
        if not tr or tr.status != "APPROVED":
            return False, "Transfer harus berstatus APPROVED untuk dikirim."

        for ln in tr.lines:
            sb = db.query(StockBalance).filter_by(
                product_id=ln.product_id,
                warehouse_id=tr.from_warehouse_id,
            ).first()
            if not sb or sb.qty_on_hand < ln.qty_requested:
                prod = db.query(Product).filter_by(id=ln.product_id).first()
                return False, f"Stok {prod.name if prod else ''} tidak cukup di gudang asal."
            sb.qty_on_hand = round(sb.qty_on_hand - ln.qty_requested, 4)
            ln.qty_shipped = ln.qty_requested

        tr.status          = "IN_TRANSIT"
        tr.shipped_at      = datetime.utcnow()
        tr.tracking_number = tracking_number or None
        tr.shipping_method = shipping_method or None
        db.commit()
        resi_info = f" Resi: {tracking_number}" if tracking_number else ""
        return True, f"Transfer dikirim. Stok asal dikurangi.{resi_info}"

    @staticmethod
    def confirm_receive(db: Session, tid: int, user_id: int,
                        user_branch_id: Optional[int] = None) -> tuple[bool, str]:
        """Terima — tambah stok tujuan. Validasi cabang user."""
        from app.models import StockTransfer, StockTransferLine
        tr = db.query(StockTransfer).filter_by(id=tid)\
               .options(joinedload(StockTransfer.lines)).first()
        if not tr or tr.status != "IN_TRANSIT":
            return False, "Transfer harus berstatus IN_TRANSIT untuk diterima."
        # Validasi: hanya cabang tujuan yang boleh terima
        if user_branch_id and tr.to_branch_id != user_branch_id:
            return False, "Anda tidak memiliki akses untuk menerima transfer ini (bukan cabang tujuan)."

        for ln in tr.lines:
            sb = db.query(StockBalance).filter_by(
                product_id=ln.product_id,
                warehouse_id=tr.to_warehouse_id,
            ).first()
            qty = ln.qty_shipped or ln.qty_requested
            if sb:
                total_val  = sb.qty_on_hand * sb.avg_cost + qty * ln.unit_cost
                new_qty    = sb.qty_on_hand + qty
                sb.avg_cost    = round(total_val / new_qty, 4) if new_qty > 0 else ln.unit_cost
                sb.qty_on_hand = round(new_qty, 4)
                sb.last_movement_at = datetime.utcnow()
            else:
                db.add(StockBalance(
                    product_id=ln.product_id,
                    warehouse_id=tr.to_warehouse_id,
                    branch_id=tr.to_branch_id,
                    qty_on_hand=round(qty, 4),
                    avg_cost=round(ln.unit_cost, 4),
                    last_movement_at=datetime.utcnow(),
                ))
            ln.qty_received = qty

        tr.status = "COMPLETED"
        tr.received_at = datetime.utcnow()
        db.commit()
        return True, "Transfer diterima. Stok tujuan ditambah."

    @staticmethod
    def approve(db: Session, tid: int, user_id: int) -> tuple[bool, str]:
        from app.models import StockTransfer
        tr = db.query(StockTransfer).filter_by(id=tid).first()
        if not tr or tr.status != "DRAFT":
            return False, "Transfer harus DRAFT untuk disetujui."
        tr.status = "APPROVED"
        tr.approved_by = user_id
        tr.approved_at = datetime.utcnow()
        db.commit()
        return True, "Transfer disetujui."

    @staticmethod
    def cancel(db: Session, tid: int) -> tuple[bool, str]:
        from app.models import StockTransfer
        tr = db.query(StockTransfer).filter_by(id=tid).first()
        if not tr:
            return False, "Transfer tidak ditemukan."
        if tr.status in ("COMPLETED", "IN_TRANSIT"):
            return False, "Transfer yang sudah dikirim/selesai tidak bisa dibatalkan."
        tr.status = "CANCELLED"
        db.commit()
        return True, "Transfer dibatalkan."


# ─────────────────────────────────────────────────────────────
# STOCK OPNAME
# ─────────────────────────────────────────────────────────────
class StockOpnameService:

    @staticmethod
    def _gen_number(db: Session, company_id: int) -> str:
        from app.models import StockOpname
        prefix = f"OPN-{datetime.now().strftime('%Y%m')}-"
        last = db.query(StockOpname)\
                 .filter(StockOpname.opname_number.like(f"{prefix}%"),
                         StockOpname.company_id == company_id)\
                 .order_by(StockOpname.opname_number.desc()).first()
        seq = (int(last.opname_number.split("-")[-1]) + 1) if last else 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def get_all(db: Session, company_id: int,
                search: str = "", status: str = "",
                branch_id: Optional[int] = None) -> List:
        from app.models import StockOpname
        q = db.query(StockOpname).filter_by(company_id=company_id)\
               .options(
                   joinedload(StockOpname.branch),
                   joinedload(StockOpname.warehouse),
               )
        if branch_id:
            q = q.filter(StockOpname.branch_id == branch_id)
        if status:
            q = q.filter_by(status=status)
        return q.order_by(StockOpname.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, oid: int):
        from app.models import StockOpname, StockOpnameLine
        return db.query(StockOpname).filter_by(id=oid)\
                 .options(
                     joinedload(StockOpname.branch),
                     joinedload(StockOpname.warehouse),
                     joinedload(StockOpname.lines)
                         .joinedload(StockOpnameLine.product)
                         .joinedload(Product.uom),
                 ).first()

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict) -> tuple[bool, str]:
        """Buat opname baru + generate lines dari StockBalance di gudang tsb."""
        from app.models import StockOpname, StockOpnameLine

        wh_id = int(data["warehouse_id"])
        br_id = int(data["branch_id"])

        number = StockOpnameService._gen_number(db, company_id)
        opname = StockOpname(
            company_id=company_id,
            branch_id=br_id,
            warehouse_id=wh_id,
            opname_number=number,
            opname_date=data.get("opname_date") or date.today(),
            notes=data.get("notes", "").strip() or None,
            created_by=user_id,
            status="DRAFT",
        )
        db.add(opname); db.flush()

        # Generate lines dari StockBalance
        balances = db.query(StockBalance).filter_by(
            warehouse_id=wh_id, branch_id=br_id
        ).all()

        for sb in balances:
            db.add(StockOpnameLine(
                opname_id=opname.id,
                product_id=sb.product_id,
                lot_number=sb.lot_number,
                qty_system=sb.qty_on_hand,
                qty_physical=sb.qty_on_hand,  # default = sistem, user ubah
                unit_cost=sb.avg_cost,
            ))

        db.commit()
        return True, f"Opname {number} dibuat dengan {len(balances)} item."

    @staticmethod
    def post(db: Session, oid: int, user_id: int) -> tuple[bool, str]:
        """Post opname — update StockBalance sesuai qty fisik."""
        from app.models import StockOpname, StockOpnameLine

        opname = db.query(StockOpname).filter_by(id=oid)\
                   .options(joinedload(StockOpname.lines)).first()
        if not opname:
            return False, "Opname tidak ditemukan."
        if opname.status not in ("COUNTED", "VALIDATED"):
            return False, "Opname harus COUNTED/VALIDATED sebelum di-post."

        for ln in opname.lines:
            sb = db.query(StockBalance).filter_by(
                product_id=ln.product_id,
                warehouse_id=opname.warehouse_id,
                lot_number=ln.lot_number,
            ).first()
            if sb:
                sb.qty_on_hand      = round(ln.qty_physical, 4)
                sb.last_movement_at = datetime.utcnow()
            elif ln.qty_physical > 0:
                db.add(StockBalance(
                    product_id=ln.product_id,
                    branch_id=opname.branch_id,
                    warehouse_id=opname.warehouse_id,
                    lot_number=ln.lot_number,
                    qty_on_hand=round(ln.qty_physical, 4),
                    avg_cost=ln.unit_cost or 0,
                    last_movement_at=datetime.utcnow(),
                ))

        opname.status    = "POSTED"
        opname.posted_by = user_id
        opname.posted_at = datetime.utcnow()
        db.commit()
        return True, f"Opname {opname.opname_number} berhasil di-post. Stok diperbarui."

    @staticmethod
    def update_status(db: Session, oid: int, new_status: str,
                      user_id: int) -> tuple[bool, str]:
        from app.models import StockOpname
        opname = db.query(StockOpname).filter_by(id=oid).first()
        if not opname:
            return False, "Opname tidak ditemukan."
        opname.status = new_status
        if new_status == "VALIDATED":
            opname.validated_by = user_id
        db.commit()
        return True, f"Status opname diubah ke {new_status}."

    @staticmethod
    def update_line_qty(db: Session, line_id: int, qty_physical: float) -> tuple[bool, str]:
        from app.models import StockOpnameLine
        ln = db.query(StockOpnameLine).filter_by(id=line_id).first()
        if not ln:
            return False, "Baris tidak ditemukan."
        ln.qty_physical = round(qty_physical, 4)
        db.commit()
        return True, "Qty fisik diperbarui."
