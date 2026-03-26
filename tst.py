import sqlite3

# 1. Koneksi ke database (ganti 'database_anda.db' dengan file milikmu)
conn = sqlite3.connect('erp_dev.db')
cursor = conn.cursor()

try:
    # 2. Menjalankan perintah SQL untuk menambah kolom
    cursor.execute("drop table invoices")
    cursor.execute("drop table delivery_order_lines")
    cursor.execute("drop table delivery_orders")
    cursor.execute("drop table sales_order_lines")
    cursor.execute("drop table sales_orders")

    
    # 3. Simpan perubahan
    conn.commit()
    print("Kolom 'courier' berhasil ditambahkan!")

except sqlite3.OperationalError:
    # Menangani error jika kolom ternyata sudah ada
    print("Error: Kolom mungkin sudah ada atau terjadi kesalahan pada tabel.")

finally:
    # 4. Tutup koneksi
    conn.close()