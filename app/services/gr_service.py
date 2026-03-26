"""
app/services/gr_service.py
Service untuk Goods Receipt (Penerimaan Barang dari PO)
- Saat GR dikonfirmasi: update qty_received di PO lines + update StockBalance
"""
from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.models import (
    GoodsReceipt, GoodsReceiptLine,
    PurchaseOrder, PurchaseOrderLine,
    PurchaseReturn, PurchaseReturnLine,
    StockBalance, Warehouse, Branch, SerialNumber,
)


def _to_float(val, default=0.0):
    try:
        return float(str(val).strip()) if val not in (None, "", "None") else default
    except (ValueError, TypeError):
        return default


def _to_int(val, default=0):
    try:
        return int(float(str(val).strip())) if val not in (None, "", "None") else default
    except (ValueError, TypeError):
        return default


def _gen_gr_number(db: Session, company_id: int) -> str:
    prefix = f"GR-{datetime.now().strftime('%Y%m')}-"
    last = db.query(GoodsReceipt)\
             .filter(GoodsReceipt.gr_number.like(f"{prefix}%"),
                     GoodsReceipt.company_id == company_id)\
             .order_by(GoodsReceipt.gr_number.desc()).first()
    seq = (int(last.gr_number.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"


def _update_stock(db: Session, product_id: int, warehouse_id: int,
                  branch_id: int, qty: float, unit_cost: float,
                  lot_number: Optional[str] = None):
    """Update StockBalance dengan metode weighted average cost."""
    sb = db.query(StockBalance).filter_by(
        product_id=product_id,
        warehouse_id=warehouse_id,
        lot_number=lot_number,
    ).first()

    if sb:
        # Weighted average cost
        total_val   = sb.qty_on_hand * sb.avg_cost + qty * unit_cost
        new_qty     = sb.qty_on_hand + qty
        sb.avg_cost = round(total_val / new_qty, 4) if new_qty > 0 else unit_cost
        sb.qty_on_hand = round(new_qty, 4)
        sb.last_movement_at = datetime.utcnow()
    else:
        sb = StockBalance(
            product_id=product_id,
            warehouse_id=warehouse_id,
            branch_id=branch_id,
            lot_number=lot_number,
            qty_on_hand=round(qty, 4),
            qty_reserved=0,
            avg_cost=round(unit_cost, 4),
            last_movement_at=datetime.utcnow(),
        )
        db.add(sb)


class GoodsReceiptService:

    @staticmethod
    def get_all(db: Session, company_id: int, search: str = "",
                status: str = "", branch_id: Optional[int] = None) -> List[GoodsReceipt]:
        q = db.query(GoodsReceipt).filter_by(company_id=company_id)\
              .options(
                  joinedload(GoodsReceipt.branch),
                  joinedload(GoodsReceipt.warehouse),
                  joinedload(GoodsReceipt.po).joinedload(PurchaseOrder.vendor),
                  joinedload(GoodsReceipt.receiver),
                  joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.product),
                  joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.uom),
              )
        if branch_id:
            q = q.filter(GoodsReceipt.branch_id == branch_id)
        if search:
            q = q.filter(or_(
                GoodsReceipt.gr_number.ilike(f"%{search}%"),
                GoodsReceipt.vendor_do_number.ilike(f"%{search}%"),
            ))
        if status:
            q = q.filter_by(status=status)
        return q.order_by(GoodsReceipt.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, gr_id: int) -> Optional[GoodsReceipt]:
        return db.query(GoodsReceipt).filter_by(id=gr_id)\
                 .options(
                     joinedload(GoodsReceipt.branch),
                     joinedload(GoodsReceipt.warehouse),
                     joinedload(GoodsReceipt.po).joinedload(PurchaseOrder.vendor),
                     joinedload(GoodsReceipt.receiver),
                     joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.product),
                     joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.uom),
                     joinedload(GoodsReceipt.lines).joinedload(GoodsReceiptLine.pol),
                 ).first()

    @staticmethod
    def get_confirmed_pos(db: Session, company_id: int) -> List[PurchaseOrder]:
        # Exclude PO yang sudah punya GR berstatus DRAFT
        # (masih dalam proses input, belum dikonfirmasi)
        # GR CONFIRMED boleh ada lagi → artinya penerimaan partial, masih bisa GR baru
        # Ambil po_id yang punya GR DRAFT sebagai list Python
        # Hindari scalar_subquery karena notin_() + NULL di SQLite = bug semua kosong
        draft_po_ids = [
            row[0] for row in
            db.query(GoodsReceipt.po_id)
              .filter(GoodsReceipt.status == "DRAFT",
                      GoodsReceipt.po_id.isnot(None))
              .all()
        ]

        q = db.query(PurchaseOrder)\
              .filter(
                  PurchaseOrder.company_id == company_id,
                  PurchaseOrder.status.in_(["CONFIRMED", "PARTIAL"]),
              )
        if draft_po_ids:
            q = q.filter(PurchaseOrder.id.notin_(draft_po_ids))
        pos = q\
                 .options(
                     joinedload(PurchaseOrder.vendor),
                     joinedload(PurchaseOrder.branch),
                     joinedload(PurchaseOrder.warehouse),
                     joinedload(PurchaseOrder.lines)
                         .joinedload(PurchaseOrderLine.product),
                     joinedload(PurchaseOrder.lines)
                         .joinedload(PurchaseOrderLine.uom),
                 )\
                 .order_by(PurchaseOrder.order_date.desc()).all()

        # Filter final: hanya PO yang masih punya sisa qty belum diterima
        def _has_remaining(po) -> bool:
            return any(
                round((ln.qty_ordered or 0) - (ln.qty_received or 0), 4) > 0.001
                for ln in (po.lines or [])
            )
        return [po for po in pos if _has_remaining(po)]

    @staticmethod
    def get_replacement_pos(db: Session, company_id: int) -> list:
        """
        PO yang butuh GR replacement:
        - Ada Purchase Return COMPLETED dengan resolution REPLACEMENT/COMBINATION
        - PO status PARTIAL (sudah di-reopen oleh return service)
        - Belum ada GR replacement DRAFT untuk return ini
        """
        from sqlalchemy import text as _text

        # Return yang sudah selesai dan butuh replacement
        completed_returns = db.query(PurchaseReturn)                              .filter(
                                  PurchaseReturn.company_id == company_id,
                                  PurchaseReturn.status == "COMPLETED",
                                  PurchaseReturn.resolution.in_(["REPLACEMENT", "COMBINATION"]),
                              ).all()

        result = []
        for rtn in completed_returns:
            # Cek apakah sudah ada GR replacement DRAFT untuk return ini
            existing_gr = db.query(GoodsReceipt).filter(
                GoodsReceipt.return_id == rtn.id,
                GoodsReceipt.is_replacement == True,
                GoodsReceipt.status.in_(["DRAFT", "CONFIRMED"]),  # ← keduanya di-exclude
            ).first()
            
            if existing_gr:
                continue  # sudah ada GR replacement yang sedang berjalan

            # Ambil PO
            gr_obj = db.query(GoodsReceipt).filter_by(id=rtn.gr_id).first()
            if not gr_obj:
                continue
            po = db.query(PurchaseOrder)                   .options(
                       joinedload(PurchaseOrder.vendor),
                       joinedload(PurchaseOrder.branch),
                       joinedload(PurchaseOrder.warehouse),
                       joinedload(PurchaseOrder.lines)
                           .joinedload(PurchaseOrderLine.product),
                       joinedload(PurchaseOrder.lines)
                           .joinedload(PurchaseOrderLine.uom),
                   ).filter_by(id=gr_obj.po_id).first()
            if not po:
                continue

            result.append({
                "po":       po,
                "return":   rtn,
                "return_id": rtn.id,
            })
        return result

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict, lines: List[Dict]) -> tuple[bool, str, Optional[GoodsReceipt]]:
        if not lines:
            return False, "Minimal satu item wajib diisi.", None

        gr_number      = _gen_gr_number(db, company_id)
        is_replacement = bool(data.get("is_replacement", False))
        return_id      = int(data["return_id"]) if data.get("return_id") else None

        gr = GoodsReceipt(
            company_id=company_id,
            branch_id=int(data["branch_id"]),
            gr_number=gr_number,
            po_id=int(data["po_id"]),
            receipt_date=data.get("receipt_date") or date.today(),
            warehouse_id=int(data["warehouse_id"]),
            vendor_do_number=data.get("vendor_do_number", "").strip() or None,
            is_replacement=is_replacement,
            return_id=return_id,
            notes=data.get("notes", "").strip() or None,
            received_by=user_id,
            status="DRAFT",
        )
        db.add(gr)
        db.flush()

        for ln in lines:
            grl = GoodsReceiptLine(
                gr_id=gr.id,
                pol_id=int(ln["pol_id"]),
                product_id=int(ln["product_id"]),
                uom_id=int(ln["uom_id"]),
                qty_received=_to_float(ln["qty_received"]),
                qty_rejected=_to_float(ln.get("qty_rejected", 0)),
                rejection_reason=ln.get("rejection_reason", "").strip() or None,
                lot_number=ln.get("lot_number", "").strip() or None,
                expiry_date=ln.get("expiry_date") or None,
                unit_cost=_to_float(ln.get("unit_cost", 0)),
                serial_numbers_input=ln.get("serial_numbers_input"),
            )
            db.add(grl)

        db.commit()
        return True, f"Goods Receipt {gr_number} berhasil dibuat.", gr

    @staticmethod
    def confirm(db: Session, gr_id: int) -> tuple[bool, str]:
        """
        Konfirmasi GR:
        1. Update qty_received di PO lines
        2. Update status PO (PARTIAL / RECEIVED)
        3. Update StockBalance (weighted avg cost)
        """
        gr = db.query(GoodsReceipt).filter_by(id=gr_id)\
                .options(
                    joinedload(GoodsReceipt.lines),
                ).first()

        if not gr:
            return False, "GR tidak ditemukan."
        if gr.status != "DRAFT":
            return False, f"GR berstatus '{gr.status}' tidak bisa dikonfirmasi."

        # Load PO terpisah — hindari identity map conflict dengan joinedload chain
        from sqlalchemy import text as _text
        po = db.query(PurchaseOrder).filter_by(id=gr.po_id).first()

        for grl in gr.lines:
            qty_ok = grl.qty_received - grl.qty_rejected

            if grl.pol_id:
                # Ambil unit_price dari POL
                pol = db.query(PurchaseOrderLine).filter_by(id=grl.pol_id).first()
                if pol:
                    grl.unit_cost = pol.unit_price

                # GR normal DAN replacement → keduanya update qty_received POL
                # Replacement = pemenuhan kembali atas qty yang rusak
                db.execute(
                    _text("UPDATE purchase_order_lines "
                          "SET qty_received = MAX(0, COALESCE(qty_received,0) + :delta) "
                          "WHERE id = :pol_id"),
                    {"delta": qty_ok, "pol_id": grl.pol_id}
                )

            # Buat SerialNumber records untuk produk SERIAL
            unit_cost_val = grl.unit_cost or 0
            if qty_ok > 0:
                _update_stock(
                    db,
                    product_id=grl.product_id,
                    warehouse_id=gr.warehouse_id,
                    branch_id=gr.branch_id,
                    qty=qty_ok,
                    unit_cost=unit_cost_val,
                    lot_number=grl.lot_number,
                )
                # Ambil SN dari kolom JSON jika ada
                import json
                from app.models import Product as ProdModel
                prod = db.query(ProdModel).filter_by(id=grl.product_id).first()
                if prod and prod.tracking_type == "SERIAL":
                    try:
                        raw = json.loads(grl.serial_numbers_input or "{}")
                    except Exception:
                        raw = {}

                    # Format GR normal: {"good":[...], "rejected":[...]}
                    # Format GR replacement: {"replacement": {"SN_LAMA": "SN_BARU", ...}}
                    # Format lama (flat list): ["SN001",...]
                    if isinstance(raw, list):
                        sn_good_list    = raw
                        sn_rej_list     = []
                        sn_replace_map  = {}  # {sn_lama: sn_baru}
                    elif "replacement" in raw:
                        sn_replace_map  = raw.get("replacement", {})
                        sn_good_list    = list(sn_replace_map.values())
                        sn_rej_list     = []
                    else:
                        sn_good_list    = raw.get("good", [])
                        sn_rej_list     = raw.get("rejected", [])
                        sn_replace_map  = {}

                    # SN Bagus / Pengganti → IN_STOCK (masuk stok)
                    for sn_val in sn_good_list:
                        sn_val = str(sn_val).strip()
                        if not sn_val:
                            continue
                        exists = db.query(SerialNumber).filter_by(
                            product_id=grl.product_id,
                            serial_number=sn_val,
                        ).first()
                        if not exists:
                            # Cari replaced_serial_id jika ini GR replacement
                            replaced_id = None
                            if sn_replace_map:
                                # Cari SN lama yang digantikan SN ini
                                sn_lama = next(
                                    (k for k, v in sn_replace_map.items() if v == sn_val),
                                    None
                                )
                                if sn_lama:
                                    old_sn = db.query(SerialNumber).filter_by(
                                        product_id=grl.product_id,
                                        serial_number=sn_lama,
                                    ).first()
                                    if old_sn:
                                        replaced_id = old_sn.id

                            db.add(SerialNumber(
                                product_id=grl.product_id,
                                serial_number=sn_val,
                                lot_number=grl.lot_number,
                                gr_line_id=grl.id,
                                current_branch_id=gr.branch_id,
                                current_warehouse_id=gr.warehouse_id,
                                status="IN_STOCK",
                                replaced_serial_id=replaced_id,
                            ))

                    # SN Rusak → DEFECTIVE (tidak masuk stok)
                    for sn_val in sn_rej_list:
                        sn_val = str(sn_val).strip()
                        if not sn_val:
                            continue
                        exists = db.query(SerialNumber).filter_by(
                            product_id=grl.product_id,
                            serial_number=sn_val,
                        ).first()
                        if not exists:
                            db.add(SerialNumber(
                                product_id=grl.product_id,
                                serial_number=sn_val,
                                lot_number=grl.lot_number,
                                gr_line_id=grl.id,
                                current_branch_id=gr.branch_id,
                                current_warehouse_id=gr.warehouse_id,
                                status="DEFECTIVE",
                            ))

        db.flush()
        db.expire_all()

        # Cek status PO untuk semua GR — normal maupun replacement
        # Replacement juga penuhi PO (ganti barang rusak = penuhi sisa)
        po_lines = db.query(PurchaseOrderLine).filter_by(po_id=po.id).all()
        all_received = all(
            round(ln.qty_received or 0, 2) >= round(ln.qty_ordered, 2)
            for ln in po_lines
        )
        any_received = any((ln.qty_received or 0) > 0 for ln in po_lines)
        if all_received:
            po.status = "RECEIVED"
        elif any_received:
            po.status = "PARTIAL"

        gr.status = "CONFIRMED"
        db.commit()
        rtn_info = " (Barang Pengganti)" if gr.is_replacement else ""
        return True, f"GR {gr.gr_number}{rtn_info} dikonfirmasi. Stok diperbarui."

    @staticmethod
    def cancel(db: Session, gr_id: int) -> tuple[bool, str]:
        gr = db.query(GoodsReceipt).filter_by(id=gr_id).first()
        if not gr:
            return False, "GR tidak ditemukan."
        if gr.status == "CONFIRMED":
            return False, "GR yang sudah dikonfirmasi tidak bisa dibatalkan."
        gr.status = "CANCELLED"
        db.commit()
        return True, f"GR {gr.gr_number} dibatalkan."

    @staticmethod
    def delete(db: Session, gr_id: int) -> tuple[bool, str]:
        gr = db.query(GoodsReceipt).filter_by(id=gr_id).first()
        if not gr:
            return False, "GR tidak ditemukan."
        if gr.status != "DRAFT":
            return False, "Hanya GR DRAFT yang bisa dihapus."
        db.query(GoodsReceiptLine).filter_by(gr_id=gr_id).delete()
        db.delete(gr)
        db.commit()
        return True, "GR berhasil dihapus."