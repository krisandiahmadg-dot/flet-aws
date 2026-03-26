"""
app/services/tax_service.py
Service untuk manajemen pajak:
  - TaxRate     : master tarif pajak
  - TaxInvoice  : faktur pajak / e-Faktur
  - TaxWithholding : PPh 21 & PPh 23
  - TaxReport   : laporan rekap pajak bulanan
"""
from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func, and_

from app.models import (
    TaxRate, TaxInvoice, TaxWithholding,
    Invoice, SalesOrder, Customer, Vendor, Employee,
    Company, Branch,
)


def _to_float(val, default=0.0):
    try: return float(str(val).strip()) if val not in (None,"","None") else default
    except: return default


def _to_int(val, default=0):
    try: return int(float(str(val).strip())) if val not in (None,"","None") else default
    except: return default


def _to_date(val) -> Optional[date]:
    if not val or not str(val).strip(): return None
    try: return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except: return None


# ─────────────────────────────────────────────────────────────
# TAX RATE SERVICE
# ─────────────────────────────────────────────────────────────
class TaxRateService:

    @staticmethod
    def get_all(db: Session, company_id: int,
                tax_type: str = "", active_only: bool = True) -> List[TaxRate]:
        q = db.query(TaxRate).filter_by(company_id=company_id)
        if active_only:
            q = q.filter_by(is_active=True)
        if tax_type:
            q = q.filter_by(tax_type=tax_type)
        return q.order_by(TaxRate.tax_type, TaxRate.rate).all()

    @staticmethod
    def get_default(db: Session, company_id: int,
                    tax_type: str = "PPN",
                    applies_to: str = "SALES") -> Optional[TaxRate]:
        """Ambil tarif default untuk tipe pajak tertentu."""
        tr = db.query(TaxRate).filter_by(
            company_id=company_id, tax_type=tax_type,
            is_default=True, is_active=True,
        ).first()
        if not tr:
            tr = db.query(TaxRate).filter(
                TaxRate.company_id == company_id,
                TaxRate.tax_type == tax_type,
                TaxRate.is_active == True,
                TaxRate.applies_to.in_([applies_to, "BOTH"]),
            ).first()
        return tr

    @staticmethod
    def create(db: Session, company_id: int, data: Dict) -> tuple[bool, str]:
        code = (data.get("code") or "").strip().upper()
        if not code:
            return False, "Kode wajib diisi."
        if db.query(TaxRate).filter_by(company_id=company_id, code=code).first():
            return False, f"Kode {code} sudah digunakan."

        # Jika is_default=True, hapus default lama untuk tipe yang sama
        if data.get("is_default"):
            db.query(TaxRate).filter_by(
                company_id=company_id,
                tax_type=data.get("tax_type"),
                is_default=True,
            ).update({"is_default": False})

        tr = TaxRate(
            company_id=company_id,
            code=code,
            name=data.get("name", "").strip(),
            tax_type=data.get("tax_type", "PPN"),
            rate=_to_float(data.get("rate", 11)),
            is_inclusive=bool(data.get("is_inclusive", False)),
            applies_to=data.get("applies_to", "BOTH"),
            is_default=bool(data.get("is_default", False)),
            is_active=True,
        )
        db.add(tr); db.commit()
        return True, f"Tarif pajak {code} berhasil ditambahkan."

    @staticmethod
    def update(db: Session, tr_id: int, data: Dict) -> tuple[bool, str]:
        tr = db.query(TaxRate).filter_by(id=tr_id).first()
        if not tr: return False, "Tarif tidak ditemukan."

        if data.get("is_default") and not tr.is_default:
            db.query(TaxRate).filter_by(
                company_id=tr.company_id,
                tax_type=tr.tax_type,
                is_default=True,
            ).update({"is_default": False})

        tr.name        = data.get("name", tr.name).strip()
        tr.rate        = _to_float(data.get("rate", tr.rate))
        tr.is_inclusive= bool(data.get("is_inclusive", tr.is_inclusive))
        tr.applies_to  = data.get("applies_to", tr.applies_to)
        tr.is_default  = bool(data.get("is_default", tr.is_default))
        tr.is_active   = bool(data.get("is_active", tr.is_active))
        db.commit()
        return True, f"Tarif {tr.code} diperbarui."

    @staticmethod
    def delete(db: Session, tr_id: int) -> tuple[bool, str]:
        tr = db.query(TaxRate).filter_by(id=tr_id).first()
        if not tr: return False, "Tarif tidak ditemukan."
        tr.is_active = False
        db.commit()
        return True, f"Tarif {tr.code} dinonaktifkan."

    @staticmethod
    def seed_defaults(db: Session, company_id: int):
        """Seed tarif pajak default Indonesia jika belum ada."""
        defaults = [
            {"code":"PPN11",   "name":"PPN 11%",              "tax_type":"PPN",   "rate":11.0, "applies_to":"BOTH",     "is_default":True},
            {"code":"PPN0",    "name":"PPN 0% (Ekspor)",       "tax_type":"PPN",   "rate":0.0,  "applies_to":"SALES",    "is_default":False},
            {"code":"PPH23_2", "name":"PPh 23 Jasa 2%",        "tax_type":"PPH23", "rate":2.0,  "applies_to":"PURCHASE", "is_default":True},
            {"code":"PPH23_15","name":"PPh 23 Dividen/Bunga 15%","tax_type":"PPH23","rate":15.0,"applies_to":"PURCHASE", "is_default":False},
            {"code":"PPH21",   "name":"PPh 21 Karyawan",       "tax_type":"PPH21", "rate":5.0,  "applies_to":"PURCHASE", "is_default":True},
        ]
        for d in defaults:
            exists = db.query(TaxRate).filter_by(
                company_id=company_id, code=d["code"]).first()
            if not exists:
                db.add(TaxRate(company_id=company_id, **d))
        db.commit()


# ─────────────────────────────────────────────────────────────
# TAX INVOICE (Faktur Pajak)
# ─────────────────────────────────────────────────────────────
class TaxInvoiceService:

    @staticmethod
    def _gen_number(db: Session, company_id: int) -> str:
        prefix = f"FP-{datetime.now().strftime('%Y%m')}-"
        last = db.query(TaxInvoice)\
                 .filter(TaxInvoice.tax_invoice_number.like(f"{prefix}%"),
                         TaxInvoice.company_id == company_id)\
                 .order_by(TaxInvoice.tax_invoice_number.desc()).first()
        seq = (int(last.tax_invoice_number.split("-")[-1]) + 1) if last else 1
        return f"{prefix}{seq:06d}"

    @staticmethod
    def get_all(db: Session, company_id: int,
                tax_type: str = "", status: str = "",
                period_month: int = 0, period_year: int = 0) -> List[TaxInvoice]:
        q = db.query(TaxInvoice).filter_by(company_id=company_id)\
               .options(
                   joinedload(TaxInvoice.invoice)
                       .joinedload(Invoice.customer),
               )
        if tax_type: q = q.filter_by(tax_type=tax_type)
        if status:   q = q.filter_by(status=status)
        if period_year:
            q = q.filter(func.strftime('%Y', TaxInvoice.tax_invoice_date) == str(period_year))
        if period_month:
            q = q.filter(func.strftime('%m', TaxInvoice.tax_invoice_date) == f'{period_month:02d}')
        return q.order_by(TaxInvoice.tax_invoice_date.desc()).all()

    @staticmethod
    def create_from_invoice(db: Session, company_id: int, user_id: int,
                             invoice_id: int, data: Dict) -> tuple[bool, str]:
        inv = db.query(Invoice).filter_by(id=invoice_id)\
                .options(joinedload(Invoice.customer),
                         joinedload(Invoice.tax_rate)).first()
        if not inv:
            return False, "Invoice tidak ditemukan."

        # Cek belum ada faktur untuk invoice ini
        existing = db.query(TaxInvoice).filter_by(invoice_id=invoice_id).first()
        if existing:
            return False, f"Faktur pajak sudah ada: {existing.tax_invoice_number}."

        tax_rate_val = inv.tax_rate.rate if inv.tax_rate else 11.0
        dpp          = inv.subtotal
        tax_amount   = round(dpp * tax_rate_val / 100, 2)
        number       = TaxInvoiceService._gen_number(db, company_id)

        cust = inv.customer
        ti = TaxInvoice(
            company_id=company_id,
            invoice_id=invoice_id,
            tax_invoice_number=number,
            tax_invoice_date=_to_date(data.get("tax_invoice_date")) or date.today(),
            tax_type="PPN",
            dpp=dpp,
            tax_rate=tax_rate_val,
            tax_amount=tax_amount,
            npwp_lawan=data.get("npwp") or (cust.tax_id if cust else None),
            nama_lawan=data.get("nama") or (cust.name  if cust else None),
            status="DRAFT",
            created_by=user_id,
        )
        db.add(ti); db.commit()
        return True, f"Faktur pajak {number} dibuat. DPP Rp {dpp:,.0f}, PPN Rp {tax_amount:,.0f}."

    @staticmethod
    def mark_uploaded(db: Session, ti_id: int) -> tuple[bool, str]:
        ti = db.query(TaxInvoice).filter_by(id=ti_id).first()
        if not ti: return False, "Faktur tidak ditemukan."
        if ti.status != "DRAFT": return False, "Hanya faktur DRAFT yang bisa di-upload."
        ti.status      = "UPLOADED"
        ti.upload_date = date.today()
        db.commit()
        return True, f"Faktur {ti.tax_invoice_number} ditandai sudah di-upload."

    @staticmethod
    def mark_approved(db: Session, ti_id: int) -> tuple[bool, str]:
        ti = db.query(TaxInvoice).filter_by(id=ti_id).first()
        if not ti: return False, "Faktur tidak ditemukan."
        ti.status = "APPROVED"
        db.commit()
        return True, f"Faktur {ti.tax_invoice_number} disetujui."


# ─────────────────────────────────────────────────────────────
# TAX WITHHOLDING (PPh 21 & PPh 23)
# ─────────────────────────────────────────────────────────────
class TaxWithholdingService:

    @staticmethod
    def _gen_number(db: Session, company_id: int, tax_type: str) -> str:
        prefix = f"WH-{tax_type}-{datetime.now().strftime('%Y%m')}-"
        last = db.query(TaxWithholding)\
                 .filter(TaxWithholding.wh_number.like(f"{prefix}%"),
                         TaxWithholding.company_id == company_id)\
                 .order_by(TaxWithholding.wh_number.desc()).first()
        seq = (int(last.wh_number.split("-")[-1]) + 1) if last else 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def get_all(db: Session, company_id: int,
                tax_type: str = "", period_year: int = 0,
                period_month: int = 0) -> List[TaxWithholding]:
        q = db.query(TaxWithholding).filter_by(company_id=company_id)\
               .options(
                   joinedload(TaxWithholding.vendor),
                   joinedload(TaxWithholding.branch),
               )
        if tax_type:     q = q.filter_by(tax_type=tax_type)
        if period_year:  q = q.filter_by(period_year=period_year)
        if period_month: q = q.filter_by(period_month=period_month)
        return q.order_by(TaxWithholding.created_at.desc()).all()

    @staticmethod
    def create(db: Session, company_id: int, user_id: int,
               data: Dict) -> tuple[bool, str]:
        tax_type = data.get("tax_type", "PPH23")
        bruto    = _to_float(data.get("bruto", 0))
        rate     = _to_float(data.get("tax_rate", 2))
        if bruto <= 0: return False, "Nilai bruto harus > 0."

        number = TaxWithholdingService._gen_number(db, company_id, tax_type)
        wh = TaxWithholding(
            company_id=company_id,
            branch_id=int(data["branch_id"]),
            wh_number=number,
            tax_type=tax_type,
            period_year=_to_int(data.get("period_year", datetime.now().year)),
            period_month=_to_int(data.get("period_month", datetime.now().month)),
            vendor_id=_to_int(data.get("vendor_id")) or None,
            employee_id=_to_int(data.get("employee_id")) or None,
            invoice_ref=data.get("invoice_ref", "").strip() or None,
            npwp=data.get("npwp", "").strip() or None,
            nama=data.get("nama", "").strip() or None,
            bruto=bruto,
            tax_rate=rate,
            tax_amount=round(bruto * rate / 100, 2),
            notes=data.get("notes", "").strip() or None,
            status="DRAFT",
            created_by=user_id,
        )
        db.add(wh); db.commit()
        return True, (f"{tax_type} {number} dibuat. "
                      f"Bruto Rp {bruto:,.0f} × {rate}% = Rp {wh.tax_amount:,.0f}.")

    @staticmethod
    def finalize(db: Session, wh_id: int) -> tuple[bool, str]:
        wh = db.query(TaxWithholding).filter_by(id=wh_id).first()
        if not wh: return False, "Tidak ditemukan."
        if wh.status != "DRAFT": return False, "Hanya DRAFT yang bisa difinalisasi."
        wh.status = "FINAL"
        db.commit()
        return True, f"{wh.wh_number} difinalisasi."


# ─────────────────────────────────────────────────────────────
# TAX REPORT — Rekap pajak bulanan
# ─────────────────────────────────────────────────────────────
class TaxReportService:

    @staticmethod
    def ppn_monthly(db: Session, company_id: int,
                    year: int, month: int) -> Dict:
        """Rekap PPN Keluaran (penjualan) dan PPN Masukan (pembelian)."""
        from app.models import PurchaseOrder, PurchaseOrderLine

        # PPN Keluaran — dari invoice penjualan bulan ini
        invoices = db.query(Invoice).filter(
            Invoice.company_id == company_id,
            Invoice.invoice_type == "SALES",
            Invoice.status.notin_(["CANCELLED", "DRAFT"]),
            func.strftime('%Y', Invoice.invoice_date) == str(year),
            func.strftime('%m', Invoice.invoice_date) == f'{month:02d}',
        ).options(joinedload(Invoice.customer)).all()

        ppn_keluar_rows = []
        total_dpp_keluar = 0.0
        total_ppn_keluar = 0.0
        for inv in invoices:
            dpp = inv.subtotal or 0
            ppn = inv.tax_amount or 0
            total_dpp_keluar += dpp
            total_ppn_keluar += ppn
            ppn_keluar_rows.append({
                "invoice_number": inv.invoice_number,
                "date":    inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else "",
                "customer":inv.customer.name if inv.customer else "—",
                "npwp":    inv.customer.tax_id if inv.customer else "—",
                "dpp":     dpp,
                "ppn":     ppn,
            })

        # PPN Masukan — dari faktur pajak masukan (purchase)
        # Untuk sederhananya: ambil dari PO yang RECEIVED bulan ini
        pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.status == "RECEIVED",
            func.strftime('%Y', PurchaseOrder.order_date) == str(year),
            func.strftime('%m', PurchaseOrder.order_date) == f'{month:02d}',
        ).options(joinedload(PurchaseOrder.vendor)).all()

        ppn_masuk_rows = []
        total_dpp_masuk = 0.0
        total_ppn_masuk = 0.0
        for po in pos:
            dpp = po.subtotal or 0
            ppn = po.tax_amount or 0
            total_dpp_masuk += dpp
            total_ppn_masuk += ppn
            ppn_masuk_rows.append({
                "po_number":po.po_number,
                "date":     po.order_date.strftime("%Y-%m-%d") if po.order_date else "",
                "vendor":   po.vendor.name if po.vendor else "—",
                "npwp":     po.vendor.tax_id if po.vendor else "—",
                "dpp":      dpp,
                "ppn":      ppn,
            })

        return {
            "year":  year, "month": month,
            "ppn_keluaran": {
                "rows":      ppn_keluar_rows,
                "total_dpp": total_dpp_keluar,
                "total_ppn": total_ppn_keluar,
            },
            "ppn_masukan": {
                "rows":      ppn_masuk_rows,
                "total_dpp": total_dpp_masuk,
                "total_ppn": total_ppn_masuk,
            },
            "ppn_kurang_bayar": round(total_ppn_keluar - total_ppn_masuk, 2),
        }

    @staticmethod
    def pph_monthly(db: Session, company_id: int,
                    year: int, month: int, tax_type: str = "") -> Dict:
        """Rekap PPh 21 / PPh 23 bulan tertentu."""
        whs = TaxWithholdingService.get_all(
            db, company_id, tax_type=tax_type,
            period_year=year, period_month=month)

        rows = []
        total_bruto = 0.0
        total_pph   = 0.0
        for wh in whs:
            total_bruto += wh.bruto
            total_pph   += wh.tax_amount
            rows.append({
                "number":    wh.wh_number,
                "tax_type":  wh.tax_type,
                "nama":      wh.nama or (wh.vendor.name if wh.vendor else "—"),
                "npwp":      wh.npwp or "—",
                "invoice_ref":wh.invoice_ref or "—",
                "bruto":     wh.bruto,
                "rate":      wh.tax_rate,
                "pph":       wh.tax_amount,
                "status":    wh.status,
            })
        return {
            "year": year, "month": month, "tax_type": tax_type,
            "rows":        rows,
            "total_bruto": total_bruto,
            "total_pph":   total_pph,
        }
