"""
app/services/purchase_return_service.py
Service untuk Purchase Return (Retur Barang ke Vendor)

Alur:
  DRAFT → CONFIRMED → SENT → COMPLETED (dengan resolusi)

Resolusi saat COMPLETED:
  REPLACEMENT  → PO di-reopen (PARTIAL) agar bisa GR baru
  CREDIT_NOTE  → catat nomor & nilai credit note dari vendor
  COMBINATION  → sebagian replacement + sebagian credit note
"""
from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Dict
import json

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.models import (
    PurchaseReturn, PurchaseReturnLine,
    GoodsReceipt, GoodsReceiptLine,
    PurchaseOrder, PurchaseOrderLine,
    StockBalance, SerialNumber,
    Branch, Vendor, Warehouse,
    Product, UnitOfMeasure,
)


def _to_float(val, default=0.0):
    try:
        return float(str(val).strip()) if val not in (None, "", "None") else default
    except Exception:
        return default


def _to_date(val):
    if not val: return None
    if hasattr(val, "year"): return val
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _gen_return_number(db: Session, company_id: int) -> str:
    prefix = f"RTN-{datetime.now().strftime('%Y%m')}-"
    last = db.query(PurchaseReturn)\
             .filter(PurchaseReturn.return_number.like(f"{prefix}%"),
                     PurchaseReturn.company_id == company_id)\
             .order_by(PurchaseReturn.return_number.desc()).first()
    seq = (int(last.return_number.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"


class PurchaseReturnService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "",
                status: str = "", branch_id: Optional[int] = None) -> List[PurchaseReturn]:
        q = db.query(PurchaseReturn)\
              .filter_by(company_id=company_id)\
              .options(
                  joinedload(PurchaseReturn.branch),
                  joinedload(PurchaseReturn.vendor),
                  joinedload(PurchaseReturn.warehouse),
                  joinedload(PurchaseReturn.gr),
                  joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.product),
                  joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.uom),
              )
        if branch_id:
            q = q.filter(PurchaseReturn.branch_id == branch_id)
        if search:
            q = q.filter(or_(
                PurchaseReturn.return_number.ilike(f"%{search}%"),
                PurchaseReturn.credit_note_number.ilike(f"%{search}%"),
            ))
        if status:
            q = q.filter_by(status=status)
        return q.order_by(PurchaseReturn.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, return_id: int) -> Optional[PurchaseReturn]:
        return db.query(PurchaseReturn).filter_by(id=return_id)\
                 .options(
                     joinedload(PurchaseReturn.branch),
                     joinedload(PurchaseReturn.vendor),
                     joinedload(PurchaseReturn.warehouse),
                     joinedload(PurchaseReturn.gr).joinedload(GoodsReceipt.po),
                     joinedload(PurchaseReturn.creator),
                     joinedload(PurchaseReturn.confirmer),
                     joinedload(PurchaseReturn.completer),
                     joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.product),
                     joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.uom),
                     joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.gr_line),
                 ).first()

    @staticmethod
    def get_returnable_grs(db: Session, company_id: int) -> List[GoodsReceipt]:
        # Pakai list Python bukan scalar_subquery — hindari notin_+NULL bug di SQLite
        active_return_gr_ids = [
            row[0] for row in
            db.query(PurchaseReturn.gr_id)
              .filter(PurchaseReturn.status.in_(["DRAFT", "CONFIRMED", "SENT"]),
                      PurchaseReturn.gr_id.isnot(None))
              .all()
        ]

        q = db.query(GoodsReceipt)\
              .filter(
                  GoodsReceipt.company_id == company_id,
                  GoodsReceipt.status == "CONFIRMED",
              )
        if active_return_gr_ids:
            q = q.filter(GoodsReceipt.id.notin_(active_return_gr_ids))
        all_grs = q\
                 .options(
                     joinedload(GoodsReceipt.po).joinedload(PurchaseOrder.vendor),
                     joinedload(GoodsReceipt.branch),
                     joinedload(GoodsReceipt.warehouse),
                     joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.product),
                     joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.uom),
                 )\
                 .order_by(GoodsReceipt.receipt_date.desc()).all()

        # Filter final: hanya GR yang masih punya item bisa di-return
        # (ada qty_rejected yang belum habis di-return)
        result = []
        for gr in all_grs:
            for grl in (gr.lines or []):
                if (grl.qty_rejected or 0) <= 0:
                    continue
                already = db.query(
                    func.coalesce(func.sum(PurchaseReturnLine.qty_return), 0)
                ).join(PurchaseReturn,
                       PurchaseReturn.id == PurchaseReturnLine.return_id)\
                 .filter(
                     PurchaseReturnLine.gr_line_id == grl.id,
                     PurchaseReturn.status.notin_(["CANCELLED"]),
                 ).scalar() or 0
                if round(grl.qty_rejected - already, 4) > 0.001:
                    result.append(gr)
                    break  # cukup satu line yang masih bisa return
        return result

    @staticmethod
    def get_rejected_lines(db: Session, gr_id: int) -> List[Dict]:
        gr = db.query(GoodsReceipt).filter_by(id=gr_id)\
               .options(
                   joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.product),
                   joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.uom),
               ).first()
        if not gr:
            return []

        result = []
        for grl in (gr.lines or []):
            if (grl.qty_rejected or 0) <= 0:
                continue

            already_returned = db.query(
                func.coalesce(func.sum(PurchaseReturnLine.qty_return), 0)
            ).join(PurchaseReturn,
                   PurchaseReturn.id == PurchaseReturnLine.return_id)\
             .filter(
                 PurchaseReturnLine.gr_line_id == grl.id,
                 PurchaseReturn.status.notin_(["CANCELLED"]),
             ).scalar() or 0

            qty_returnable = round(grl.qty_rejected - already_returned, 4)
            if qty_returnable <= 0:
                continue

            sn_defective = []
            if grl.serial_numbers_input:
                try:
                    raw = json.loads(grl.serial_numbers_input)
                    if isinstance(raw, dict):
                        sn_defective = raw.get("rejected", [])
                except Exception:
                    pass

            result.append({
                "gr_line_id":       grl.id,
                "product_id":       grl.product_id,
                "product_name":     grl.product.name if grl.product else "—",
                "product_code":     grl.product.code if grl.product else "",
                "tracking_type":    grl.product.tracking_type if grl.product else "NONE",
                "uom_id":           grl.uom_id,
                "uom_name":         grl.uom.name if grl.uom else "—",
                "uom_code":         grl.uom.code if grl.uom else "—",
                "qty_rejected":     grl.qty_rejected,
                "qty_returned":     already_returned,
                "qty_returnable":   qty_returnable,
                "unit_cost":        grl.unit_cost or 0,
                "rejection_reason": grl.rejection_reason or "",
                "lot_number":       grl.lot_number or "",
                "sn_defective":     sn_defective,
            })
        return result

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict, lines: List[Dict]) -> tuple[bool, str, Optional[PurchaseReturn]]:
        if not lines:
            return False, "Minimal satu item wajib diisi.", None

        gr = db.query(GoodsReceipt).filter_by(id=int(data["gr_id"])).first()
        if not gr or gr.status != "CONFIRMED":
            return False, "GR tidak ditemukan atau belum CONFIRMED.", None

        po = db.query(PurchaseOrder).filter_by(id=gr.po_id).first()
        if not po or not po.vendor_id:
            return False, "Vendor tidak ditemukan dari PO.", None

        return_number = _gen_return_number(db, company_id)
        total = sum(_to_float(ln["qty_return"]) * _to_float(ln.get("unit_cost", 0))
                    for ln in lines)

        rtn = PurchaseReturn(
            company_id=company_id,
            branch_id=int(data["branch_id"]),
            return_number=return_number,
            gr_id=int(data["gr_id"]),
            vendor_id=po.vendor_id,
            warehouse_id=int(data["warehouse_id"]),
            return_date=_to_date(data.get("return_date")) or date.today(),
            return_reason=data.get("return_reason", "DEFECTIVE"),
            status="DRAFT",
            total_amount=round(total, 2),
            notes=data.get("notes", "").strip() or None,
            created_by=user_id,
        )
        db.add(rtn)
        db.flush()

        for ln in lines:
            sn_list = ln.get("serial_numbers", [])
            db.add(PurchaseReturnLine(
                return_id=rtn.id,
                gr_line_id=int(ln["gr_line_id"]),
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_return=_to_float(ln["qty_return"]),
                unit_cost=_to_float(ln.get("unit_cost", 0)),
                serial_numbers=json.dumps(sn_list) if sn_list else None,
                notes=ln.get("notes", "").strip() or None,
            ))

        db.commit()
        return True, f"Purchase Return {return_number} berhasil dibuat.", rtn

    @staticmethod
    def confirm(db: Session, return_id: int, confirmer_id: int) -> tuple[bool, str]:
        """
        Konfirmasi retur:
        - Kurangi StockBalance untuk produk non-serial
        - SerialNumber → RETURNED
        - Status → CONFIRMED
        """
        rtn = db.query(PurchaseReturn).filter_by(id=return_id)\
                .options(
                    joinedload(PurchaseReturn.lines).joinedload(PurchaseReturnLine.product),
                ).first()
        if not rtn:
            return False, "Return tidak ditemukan."
        if rtn.status != "DRAFT":
            return False, f"Return berstatus '{rtn.status}' tidak bisa dikonfirmasi."

        for line in rtn.lines:
            prod = line.product

            if prod and prod.tracking_type == "NONE":
                sb = db.query(StockBalance).filter_by(
                    product_id=line.product_id,
                    warehouse_id=rtn.warehouse_id,
                ).first()
                if sb:
                    sb.qty_on_hand      = max(0, round(sb.qty_on_hand - line.qty_return, 4))
                    sb.last_movement_at = datetime.utcnow()

            if prod and prod.tracking_type == "SERIAL":
                sn_list = []
                if line.serial_numbers:
                    try: sn_list = json.loads(line.serial_numbers)
                    except: pass
                for sn_val in sn_list:
                    sn_obj = db.query(SerialNumber).filter_by(
                        product_id=line.product_id,
                        serial_number=str(sn_val).strip(),
                    ).first()
                    if sn_obj:
                        sn_obj.status = "RETURNED"

        rtn.status       = "CONFIRMED"
        rtn.confirmed_by = confirmer_id
        rtn.confirmed_at = datetime.utcnow()
        db.commit()
        return True, f"Return {rtn.return_number} dikonfirmasi. Siap dikirim ke vendor."

    @staticmethod
    def send(db: Session, return_id: int) -> tuple[bool, str]:
        rtn = db.query(PurchaseReturn).filter_by(id=return_id).first()
        if not rtn:
            return False, "Return tidak ditemukan."
        if rtn.status != "CONFIRMED":
            return False, "Hanya return CONFIRMED yang bisa dikirim."
        rtn.status = "SENT"
        db.commit()
        return True, f"Return {rtn.return_number} ditandai sudah dikirim ke vendor."

    @staticmethod
    def complete(db: Session, return_id: int, user_id: int,
                 resolution_data: Dict) -> tuple[bool, str]:
        """
        Selesaikan return dengan resolusi dari vendor.

        resolution_data = {
            "resolution":          "REPLACEMENT" | "CREDIT_NOTE" | "COMBINATION",
            "replacement_qty":     float  (untuk REPLACEMENT / COMBINATION)
            "credit_note_number":  str    (untuk CREDIT_NOTE / COMBINATION)
            "credit_note_amount":  float  (untuk CREDIT_NOTE / COMBINATION)
            "credit_note_date":    str YYYY-MM-DD
        }

        Efek samping:
          REPLACEMENT / COMBINATION → PO di-reopen ke PARTIAL
          agar bisa dibuat GR baru untuk barang pengganti
        """
        rtn = db.query(PurchaseReturn).filter_by(id=return_id)\
                .options(
                    joinedload(PurchaseReturn.gr),
                    joinedload(PurchaseReturn.lines),
                ).first()
        if not rtn:
            return False, "Return tidak ditemukan."
        if rtn.status != "SENT":
            return False, "Hanya return SENT yang bisa di-complete."

        resolution = resolution_data.get("resolution", "")
        if resolution not in ("REPLACEMENT", "CREDIT_NOTE", "COMBINATION"):
            return False, "Resolusi tidak valid. Pilih REPLACEMENT, CREDIT_NOTE, atau COMBINATION."

        # ── Validasi per resolusi ─────────────────────────────
        if resolution in ("CREDIT_NOTE", "COMBINATION"):
            if not resolution_data.get("credit_note_number", "").strip():
                return False, "Nomor credit note wajib diisi."
            if _to_float(resolution_data.get("credit_note_amount", 0)) <= 0:
                return False, "Nilai credit note harus > 0."

        if resolution in ("REPLACEMENT", "COMBINATION"):
            if _to_float(resolution_data.get("replacement_qty", 0)) <= 0:
                return False, "Qty pengganti harus > 0."

        # ── Simpan resolusi ───────────────────────────────────
        rtn.resolution          = resolution
        rtn.replacement_qty     = _to_float(resolution_data.get("replacement_qty", 0))
        rtn.credit_note_number  = resolution_data.get("credit_note_number", "").strip() or None
        rtn.credit_note_amount  = _to_float(resolution_data.get("credit_note_amount", 0))
        rtn.credit_note_date    = _to_date(resolution_data.get("credit_note_date"))
        rtn.status              = "COMPLETED"
        rtn.completed_by        = user_id
        rtn.completed_at        = datetime.utcnow()

        # ── Reopen PO jika ada barang pengganti ──────────────
        # REPLACEMENT atau COMBINATION → vendor akan kirim barang baru
        # PO perlu di-reopen ke PARTIAL agar bisa dibuat GR baru
        if resolution in ("REPLACEMENT", "COMBINATION"):
            # Cukup reopen PO ke PARTIAL — qty_received TIDAK dikurangi di sini
            # Pengurangan terjadi saat GR replacement dikonfirmasi (is_replacement=True)
            gr_obj = db.query(GoodsReceipt).filter_by(id=rtn.gr_id).first()
            po_id  = gr_obj.po_id if gr_obj else None
            if po_id:
                from sqlalchemy import text as _text
                # Set PO ke PARTIAL agar muncul di dropdown GR
                db.execute(
                    _text("UPDATE purchase_orders SET status='PARTIAL' "
                          "WHERE id = :po_id AND status IN ('RECEIVED','PARTIAL')"),
                    {"po_id": po_id}
                )
                db.flush()

        db.commit()

        # ── Pesan ringkasan ───────────────────────────────────
        msg_parts = [f"Return {rtn.return_number} selesai."]
        if resolution == "REPLACEMENT":
            msg_parts.append(
                f"PO di-reopen → buat GR baru untuk {rtn.replacement_qty:,.0f} unit pengganti."
            )
        elif resolution == "CREDIT_NOTE":
            msg_parts.append(
                f"Credit note {rtn.credit_note_number} "
                f"senilai Rp {rtn.credit_note_amount:,.0f} dicatat."
            )
        elif resolution == "COMBINATION":
            msg_parts.append(
                f"PO di-reopen untuk {rtn.replacement_qty:,.0f} unit pengganti. "
                f"Credit note {rtn.credit_note_number} "
                f"senilai Rp {rtn.credit_note_amount:,.0f} dicatat."
            )
        return True, " ".join(msg_parts)

    @staticmethod
    def cancel(db: Session, return_id: int) -> tuple[bool, str]:
        rtn = db.query(PurchaseReturn).filter_by(id=return_id).first()
        if not rtn:
            return False, "Return tidak ditemukan."
        if rtn.status in ("COMPLETED", "CANCELLED"):
            return False, f"Return tidak bisa dibatalkan dari status '{rtn.status}'."
        rtn.status = "CANCELLED"
        db.commit()
        return True, f"Return {rtn.return_number} dibatalkan."

    @staticmethod
    def delete(db: Session, return_id: int) -> tuple[bool, str]:
        rtn = db.query(PurchaseReturn).filter_by(id=return_id).first()
        if not rtn:
            return False, "Return tidak ditemukan."
        if rtn.status != "DRAFT":
            return False, "Hanya return DRAFT yang bisa dihapus."
        db.query(PurchaseReturnLine).filter_by(return_id=return_id).delete()
        db.delete(rtn)
        db.commit()
        return True, "Return berhasil dihapus."