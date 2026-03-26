"""
app/services/seeder.py
Buat tabel + seed data awal (company, admin user, roles, menus)
"""

from __future__ import annotations
from sqlalchemy.orm import Session
from app.database import engine, Base
from app.models import Company, Branch, Role, Menu, RoleMenuPermission, User, UserRole, Department, UnitOfMeasure,Warehouse, Vendor, ProductCategory, Product


# ─────────────────────────────────────────────────────────────
# MENU TREE
# WAJIB: parent harus muncul SEBELUM children-nya
# (code, label, icon, route, module, sort_order, parent_code)
# ─────────────────────────────────────────────────────────────
MENU_TREE = [
    # ── Roots (parent_code=None) ──────────────────────────────
    ("DASHBOARD",        "Dashboard",            "dashboard",              "/dashboard",               None,          1,  None),
    ("MASTER",           "Master Data",           "storage",                None,                       None,          2,  None),
    ("HR",               "HR & Karyawan",         "groups",                 None,                       None,          3,  None),
    ("INVENTORY",        "Inventory",             "warehouse",              None,                       None,          4,  None),
    ("PURCHASING",       "Pembelian",             "shopping_cart",          None,                       None,          5,  None),
    ("SALES",            "Penjualan",             "point_of_sale",          None,                       None,          6,  None),
    ("MARKETING",        "Marketing",             "campaign",               None,                       None,          7,  None),
    ("EVALUATION",       "Evaluasi",              "assessment",             None,                       None,          8,  None),
    ("FINANCE",         "Finance",            "finance",               None,                       None,          9,  None),
    ("SETTINGS",         "Pengaturan",            "settings",               None,                       None,          10,  None),

    # ── Master Data children ──────────────────────────────────
    ("MASTER_COMPANY",   "Perusahaan",            "business",               "/master/companies",        "master",      1,  "MASTER"),
    ("MASTER_BRANCH",    "Cabang",                "store",                  "/master/branches",         "master",      2,  "MASTER"),
    ("MASTER_WAREHOUSE", "Gudang",                "warehouse",              "/master/warehouses",       "master",      3,  "MASTER"),
    ("MASTER_PRODUCT",   "Produk",                "inventory_2",            "/master/products",         "master",      3,  "MASTER"),
    ("MASTER_CATEGORY",  "Kategori Produk",       "folder",                 "/master/categories",       "master",      4,  "MASTER"),
    ("MASTER_VENDOR",    "Vendor",                "local_shipping",         "/master/vendors",          "master",      4,  "MASTER"),
    ("MASTER_PARTNER",   "Mitra",                 "handshake",              "/master/partners",         "master",      5,  "MASTER"),
    ("MASTER_CUSTOMER",  "Pelanggan",             "people",                 "/master/customers",        "master",      6,  "MASTER"),
    ("MASTER_DEPT",      "Departemen",            "apartment",              "/master/departments",      "master",      7,  "MASTER"),

    # ── HR children ───────────────────────────────────────────
    ("HR_EMPLOYEE",      "Karyawan",              "badge",                  "/hr/employees",            "hr",          1,  "HR"),
    ("HR_ATTENDANCE",    "Kehadiran",             "event_available",        "/hr/attendance",           "hr",          2,  "HR"),
    ("HR_LEAVE",         "Cuti & Izin",           "beach_access",           "/hr/leave",                "hr",          3,  "HR"),

    # ── Inventory children ────────────────────────────────────
    ("INV_BALANCE",      "Saldo Stok",            "inventory",              "/inventory/balance",       "inventory",   1,  "INVENTORY"),
    ("INV_MOVEMENT",     "Pergerakan Stok",       "swap_horiz",             "/inventory/movement",      "inventory",   2,  "INVENTORY"),
    ("INV_TRANSFER",     "Transfer Cabang",       "sync_alt",               "/inventory/transfer",      "inventory",   3,  "INVENTORY"),
    ("INV_OPNAME",       "Stock Opname",          "checklist",              "/inventory/opname",        "inventory",   4,  "INVENTORY"),

    # ── Purchasing children ───────────────────────────────────
    ("PUR_PR",           "Purchase Request",      "request_page",           "/purchasing/pr",           "purchasing",  1,  "PURCHASING"),
    ("PUR_PO",           "Purchase Order",        "receipt_long",           "/purchasing/po",           "purchasing",  2,  "PURCHASING"),
    ("PUR_GR",           "Penerimaan Barang",     "move_to_inbox",          "/purchasing/gr",           "purchasing",  3,  "PURCHASING"),
    ("PUR_RETURN",        "Purchase Return",      "UNDO",                   "/purchasing/return",       "purchasing",  4,  "PURCHASING"),

    # ── Sales children ────────────────────────────────────────
    ("SALES_SO",         "Sales Order",           "shopping_bag",           "/sales/so",                "sales",       1,  "SALES"),
    ("SALES_DO",         "Pengiriman",            "local_shipping",         "/sales/delivery",          "sales",       2,  "SALES"),
    ("SALES_INV",        "Invoice",               "receipt",                "/sales/invoice",           "sales",       3,  "SALES"),
    ("SALES_PAY",        "Pembayaran",            "payments",               "/sales/payment",           "sales",       4,  "SALES"),

    # ── Marketing children ────────────────────────────────────
    ("MKT_CAMPAIGN",     "Campaign",              "campaign",               "/marketing/campaigns",     "marketing",   1,  "MARKETING"),

    # ── Evaluation children ───────────────────────────────────
    ("EVAL_VENDOR",      "Evaluasi Vendor",       "star",                   "/eval/vendor",             "evaluation",  1,  "EVALUATION"),
    ("EVAL_PARTNER",     "Evaluasi Mitra",        "star_half",              "/eval/partner",            "evaluation",  2,  "EVALUATION"),
    ("EVAL_SALES",       "Evaluasi Sales",        "person_search",          "/eval/sales",              "evaluation",  3,  "EVALUATION"),
    ("EVAL_MARKETING",   "Evaluasi Marketing",    "trending_up",            "/eval/marketing",          "evaluation",  4,  "EVALUATION"),
    ("EVAL_BRANCH",      "Evaluasi Cabang",       "leaderboard",            "/eval/branch",             "evaluation",  5,  "EVALUATION"),

    #-Finance
    ("FIN_CREDIT_NOTE",  "Credit Note",           "receipt_long",           "/finance/credit-note",     "finance",     1,  "FINANCE"),
    ("FIN_COMISSION",     "COMISSION",             "payments",               "/finance/comissions",        "finance",      2,  "FINANCE"),

    # ── Settings children ─────────────────────────────────────
    ("SET_USER",         "Pengguna",              "manage_accounts",        "/settings/users",          "settings",    1,  "SETTINGS"),
    ("SET_ROLE",         "Role & Akses",          "admin_panel_settings",   "/settings/roles",          "settings",    2,  "SETTINGS"),
    ("SET_MENU",         "Menu",                  "menu",                   "/settings/menus",          "settings",    3,  "SETTINGS"),
    ("SET_UOM",          "Unit Of Measure (UOM)",  "scale",                  "/settings/uoms",           "settings",    4,  "SETTINGS"),
    ("SET_UOM_CONVERSION", "UOM Conversion",       "swap_horiz",             "/settings/uom-conversions", "settings",    5,  "SETTINGS"),
     ("SET_TAX",        "Tax Management",       "swap_horiz",             "/tax/tax-management", "settings",    6,  "SETTINGS"),
]


def init_db():
    """Buat semua tabel. Untuk MySQL, jalankan migrate.py secara terpisah."""
    Base.metadata.create_all(bind=engine)


def _seed_menus(db: Session) -> dict[str, int]:
    """
    Insert menu satu per satu dengan urutan parent-first.
    Return code_to_id dict.

    Strategi:
    - Ambil semua menu yang sudah ada dulu
    - Loop MENU_TREE; untuk tiap row, cari parent_id dari code_to_id
    - flush() langsung setelah add agar id tersedia sebelum row berikutnya
    - Jangan gunakan relationship children/parent saat insert —
      set parent_id (FK integer) secara langsung
    """
    # Ambil yang sudah ada
    code_to_id: dict[str, int] = {}
    for m in db.query(Menu).all():
        code_to_id[m.code] = m.id

    for code, label, icon, route, module, sort, parent_code in MENU_TREE:
        if code in code_to_id:
            continue  # sudah ada, skip

        # Pastikan parent sudah ada
        parent_id: int | None = None
        if parent_code:
            parent_id = code_to_id.get(parent_code)
            if parent_id is None:
                raise ValueError(
                    f"Parent '{parent_code}' belum ada saat insert '{code}'. "
                    "Periksa urutan MENU_TREE — parent harus sebelum children."
                )

        # Buat objek Menu dengan SET parent_id integer langsung
        # JANGAN assign .parent = obj agar SQLAlchemy tidak override parent_id
        menu = Menu(
            code=code,
            label=label,
            icon=icon,
            route=route,
            module=module,
            sort_order=sort,
            parent_id=parent_id,     # ← integer FK, bukan relationship
        )
        db.add(menu)
        db.flush()                   # ← dapatkan id sebelum lanjut

        code_to_id[code] = menu.id   # ← simpan id untuk children berikutnya

    return code_to_id


def seed_all(
    db: Session,
    company_name: str = "Harmoni Sejahtera",
    admin_username: str = "a",
    admin_password: str = "a",
    admin_email: str = "admin@company.com",
) -> dict:
    """Seed data awal jika belum ada. Return dict info yang dibuat."""
    created = {}

    # ── 1. Company ────────────────────────────────────────────
    company = db.query(Company).filter_by(code="MAIN").first()
    if not company:
        company = Company(
            code="MAIN",
            name=company_name,
            country="Indonesia",
            currency_code="IDR",
        )
        db.add(company)
        db.flush()
        created["company"] = company.name

    # ── 2. HQ Branch ─────────────────────────────────────────
    branch = db.query(Branch).filter_by(company_id=company.id).first()
    if not branch:
        hq = Branch(
            id=1,
            company_id=company.id,
            code="HQ",
            name="Kantor Pusat",
            branch_type="HQ",
        )
        jkt = Branch(
            id=2,
            company_id=company.id,
            code="CBG-JKT",
            name="Cabang JAKARTA",
            branch_type="BRANCH",
        )

        bks = Branch(
            id=3,
            company_id=company.id,
            code="CBG-BKS",
            name="Cabang Bekasi",
            branch_type="BRANCH",
        )

        db.add_all([hq,jkt,bks])
        db.flush()

    wh = db.query(Warehouse).first()
    if not wh:
        wh = Warehouse(
            branch_id=hq.id,
            code="GDG-PST",
            name="Gudang Pusat",
        )

        wh1 = Warehouse(
            branch_id=jkt.id,
            code="GDG-JKT",
            name="Gudang JAKARTA",
        )

        wh2 = Warehouse(
            branch_id=bks.id,
            code="GDG-BKS",
            name="Gudang Bekasi",
        )
        db.add_all([wh,wh1,wh2])
        db.flush()
    
    ven = db.query(Vendor).filter_by(company_id=company.id).first()
    if not ven:
        ven = Vendor(
            id=1,
            company_id=company.id,
            code="OTC",
            name="OTICON",
            vendor_type="SUPPLIER",
        )
        db.add(ven)
        db.flush()

    dept = db.query(Department).filter_by(company_id=company.id).first()
    if not dept:
        it = Department(
            company_id = company.id,
            branch_id = 1,
            code = "IT",
            name = "Information Technology",
        )
        db.add(it)
        db.flush()

    uom = db.query(UnitOfMeasure).filter_by(company_id=company.id).first()
    if not uom:
        pcs = UnitOfMeasure(
            company_id = company.id,
            code ="PCS",
            name = "PCS",
            uom_type = "VOLUME",
        )
        db.add(pcs)
        db.flush()
    
    cat = db.query(ProductCategory).filter_by(company_id=company.id).first()
    if not cat:
        cat = ProductCategory(
            company_id = company.id,
            code ="ABD",
            name = "ALAT BANTU DENGAR",
        )
        db.add(cat)
        db.flush()
    
    prod = db.query(Product).filter_by(company_id=company.id).first()
    if not prod:
        prod = Product(
            company_id = company.id,
            category_id = cat.id,
            code ="SAF",
            name = "OTICON SAFARI",
            product_type ="GOODS",
            uom_id = pcs.id,
            purchase_uom_id = pcs.id,
            sales_uom_id= pcs.id,
            tracking_type = "SERIAL",
            

        )
        db.add(prod)
        db.flush()
    

    # ── 3. Menus ──────────────────────────────────────────────
    existing_count = db.query(Menu).count()
    code_to_id = _seed_menus(db)
    new_count   = db.query(Menu).count()
    if new_count > existing_count:
        created["menus"] = new_count - existing_count

    # ── 4. Roles ──────────────────────────────────────────────
    admin_role = db.query(Role).filter_by(company_id=company.id, code="ADMIN").first()
    if not admin_role:
        admin_role = Role(
            company_id=company.id,
            code="ADMIN",
            name="Administrator",
            description="Akses penuh ke semua fitur",
            is_system=True,
        )
        db.add(admin_role)
        db.flush()
        created["role_admin"] = admin_role.name

        for menu_id in code_to_id.values():
            db.add(RoleMenuPermission(
                role_id=admin_role.id, menu_id=menu_id,
                can_view=True, can_create=True, can_edit=True,
                can_delete=True, can_approve=True, can_export=True,
            ))

    viewer_role = db.query(Role).filter_by(company_id=company.id, code="VIEWER").first()
    if not viewer_role:
        viewer_role = Role(
            company_id=company.id,
            code="VIEWER",
            name="Viewer",
            description="Hanya bisa melihat data",
            is_system=True,
        )
        db.add(viewer_role)
        db.flush()
        created["role_viewer"] = viewer_role.name

        for menu_id in code_to_id.values():
            db.add(RoleMenuPermission(
                role_id=viewer_role.id, menu_id=menu_id,
                can_view=True,
            ))

    # ── 5. Admin User ─────────────────────────────────────────
    admin_user = db.query(User).filter_by(username=admin_username).first()
    if not admin_user:
        admin_user = User(
            company_id=company.id,
            username=admin_username,
            email=admin_email,
            full_name="Administrator",
        )
        admin_user.set_password(admin_password)
        db.add(admin_user)
        db.flush()
        created["user"] = admin_username

        db.add(UserRole(
            user_id=admin_user.id,
            role_id=admin_role.id,
            branch_id=hq.id,
        ))
    


    db.commit()
    return created
