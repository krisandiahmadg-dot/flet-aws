# ERP System — Flet + SQLAlchemy

Aplikasi ERP desktop/web dengan Python, Flet, dan SQLAlchemy.

## Struktur Proyek

```
erp_app/
├── main.py                     # Entry point
├── requirements.txt
├── .env.example                # Copy ke .env dan sesuaikan
│
└── app/
    ├── database.py             # Engine, session, Base
    ├── models/
    │   └── __init__.py         # ORM models (Company, User, Role, Menu, dll)
    ├── services/
    │   ├── auth.py             # Login, session, menu tree builder
    │   └── seeder.py           # Init DB + seed data awal
    ├── utils/
    │   └── theme.py            # Warna, ukuran, icon map
    ├── components/
    │   ├── sidebar.py          # Sidebar navigasi dinamis
    │   └── topbar.py           # Top bar
    └── pages/
        ├── login.py            # Halaman login
        ├── dashboard.py        # Dashboard dengan stat cards
        └── placeholder.py      # Placeholder untuk halaman belum dibuat
```

## Instalasi

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Konfigurasi database
cp .env.example .env
# Edit .env sesuai kebutuhan

# Default: SQLite (USE_SQLITE=true) — tidak perlu MySQL untuk development
# Untuk MySQL: set USE_SQLITE=false dan isi DB_* credentials

# 3. Jalankan
flet run main.py              # Desktop window
flet run --web main.py        # Browser (http://localhost:8550)
flet run --web --port 8080 main.py
```

## Login Default

| Username | Password   |
|----------|------------|
| `admin`  | `Admin@123` |

## Fitur Saat Ini

### ✅ Login
- Autentikasi username/email + password
- Password bcrypt (fallback sha256 jika passlib tidak terinstall)
- Validasi input + pesan error
- Loading state saat proses login

### ✅ Sidebar Dinamis
- Menu tree dari database berdasarkan role user
- Grup collapsible (buka/tutup per group)
- Active state highlight
- Mode expanded ↔ mini (icon only) — klik tombol menu
- User info + logout di bagian bawah

### ✅ Top Bar
- Judul halaman dinamis
- Avatar user
- Ikon notifikasi & pencarian (placeholder)

### ✅ Dashboard
- Stat cards (SO hari ini, PO pending, stok menipis, pelanggan baru)
- Area grafik (placeholder)
- Quick action buttons

### ✅ Database
- SQLite untuk development (otomatis)
- MySQL untuk production (konfigurasi .env)
- Auto-create tabel saat startup
- Seed data: company, branch, roles (admin+viewer), 35 menu, user admin

### ✅ RBAC
- Role-based menu visibility
- Permission per menu: view, create, edit, delete, approve, export
- User bisa punya multi role di cabang berbeda

## Menambah Halaman Baru

1. Buat file di `app/pages/nama_halaman.py`
2. Register route di `main.py` dalam fungsi `navigate()`
3. Menu otomatis muncul dari database

## Koneksi MySQL (Production)

Edit `.env`:
```env
USE_SQLITE=false
DB_HOST=localhost
DB_PORT=3306
DB_NAME=erp_db
DB_USER=root
DB_PASSWORD=yourpassword
```

Buat database MySQL dulu:
```sql
CREATE DATABASE erp_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Kemudian jalankan DDL dari `erp_ddl.sql` atau biarkan SQLAlchemy auto-create (tanpa DDL lengkap).
