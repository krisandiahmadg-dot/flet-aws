"""
migrate.py
Jalankan sekali untuk menambah kolom/tabel baru ke database yang sudah ada.
Usage: python migrate.py

Script ini AMAN dijalankan berkali-kali (idempotent) —
kolom/tabel yang sudah ada akan di-skip.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app.database import engine, Base
from sqlalchemy import text, inspect

def col_exists(conn, table: str, col: str) -> bool:
    try:
        result = conn.execute(text(
            f"SELECT COUNT(*) FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA = DATABASE() "
            f"AND TABLE_NAME = '{table}' AND COLUMN_NAME = '{col}'"
        ))
        return result.scalar() > 0
    except Exception:
        return False


def table_exists(conn, table: str) -> bool:
    try:
        result = conn.execute(text(
            f"SELECT COUNT(*) FROM information_schema.TABLES "
            f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}'"
        ))
        return result.scalar() > 0
    except Exception:
        return False


def run_if_not_exists(conn, table: str, col: str, alter_sql: str):
    if not col_exists(conn, table, col):
        print(f"  + ADD {table}.{col}")
        conn.execute(text(alter_sql))
    else:
        print(f"  ✓ {table}.{col} sudah ada")


def main():
    is_sqlite = "sqlite" in str(engine.url)

    if is_sqlite:
        print("SQLite mode — menjalankan create_all() untuk tabel baru...")
        # Import semua model agar terdaftar ke Base.metadata
        import app.models  # noqa
        Base.metadata.create_all(bind=engine)
        print("✓ Selesai (SQLite — semua tabel/kolom sudah dihandle create_all)")
        return

    print(f"MySQL mode — migrasi ke: {engine.url}")
    print()

    # Import semua model
    import app.models  # noqa

    with engine.begin() as conn:

        # ── 1. Buat tabel baru yang belum ada ───────────────────
        print("=== 1. Membuat tabel baru (jika belum ada) ===")
        new_tables = [
            "warehouses",
            "purchase_requests",
            "purchase_request_lines",
            "purchase_orders",
            "purchase_order_lines",
            "goods_receipts",
            "goods_receipt_lines",
            "stock_balances",
            "campaigns",
        ]
        for tbl in new_tables:
            if not table_exists(conn, tbl):
                print(f"  + CREATE TABLE {tbl}")
            else:
                print(f"  ✓ {tbl} sudah ada")

        # create_all hanya buat yang belum ada
        Base.metadata.create_all(bind=engine)
        print()

        # ── 2. Tambah kolom baru ke tabel yang sudah ada ────────
        print("=== 2. Menambah kolom baru ===")

        # companies
        run_if_not_exists(conn, "companies", "logo_url",
            "ALTER TABLE companies ADD COLUMN logo_url VARCHAR(255) NULL AFTER tax_id")

        # campaigns
        run_if_not_exists(conn, "campaigns", "target_leads",
            "ALTER TABLE campaigns ADD COLUMN target_leads INT UNSIGNED DEFAULT 0")
        run_if_not_exists(conn, "campaigns", "target_revenue",
            "ALTER TABLE campaigns ADD COLUMN target_revenue DECIMAL(18,2) DEFAULT 0")

        # goods_receipt_lines
        run_if_not_exists(conn, "goods_receipt_lines", "unit_cost",
            "ALTER TABLE goods_receipt_lines ADD COLUMN unit_cost DECIMAL(18,4) DEFAULT 0")

        # products
        run_if_not_exists(conn, "products", "is_purchasable",
            "ALTER TABLE products ADD COLUMN is_purchasable TINYINT(1) DEFAULT 1")
        run_if_not_exists(conn, "products", "is_sellable",
            "ALTER TABLE products ADD COLUMN is_sellable TINYINT(1) DEFAULT 1")
        run_if_not_exists(conn, "products", "is_stockable",
            "ALTER TABLE products ADD COLUMN is_stockable TINYINT(1) DEFAULT 1")

        # branches — pastikan kolom yang dibutuhkan ada
        run_if_not_exists(conn, "branches", "manager_user_id",
            "ALTER TABLE branches ADD COLUMN manager_user_id INT UNSIGNED NULL")

        # departments — relasi branch
        run_if_not_exists(conn, "departments", "branch_id",
            "ALTER TABLE departments ADD COLUMN branch_id INT UNSIGNED NULL, "
            "ADD CONSTRAINT fk_dept_branch_mig FOREIGN KEY (branch_id) REFERENCES branches(id)")

        # purchase_order_lines — kolom qty_received
        run_if_not_exists(conn, "purchase_order_lines", "qty_received",
            "ALTER TABLE purchase_order_lines ADD COLUMN qty_received DECIMAL(18,4) DEFAULT 0")

        # goods_receipt_lines — tambah kolom serial tracking
        run_if_not_exists(conn, "goods_receipt_lines", "serial_numbers_input",
            "ALTER TABLE goods_receipt_lines ADD COLUMN serial_numbers_input TEXT NULL "
            "COMMENT 'JSON array SN yang diinput saat GR'")

        # stock_transfers
        run_if_not_exists(conn, "stock_transfers", "tracking_number",
            "ALTER TABLE stock_transfers ADD COLUMN tracking_number VARCHAR(100) NULL")
        run_if_not_exists(conn, "stock_transfers", "shipping_method",
            "ALTER TABLE stock_transfers ADD COLUMN shipping_method VARCHAR(100) NULL")

        print()
        print("=== Migrasi selesai ✓ ===")


if __name__ == "__main__":
    main()
