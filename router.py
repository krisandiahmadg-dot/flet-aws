import flet as ft
from app.pages.dashboard import DashboardPage
from app.pages.master.companies import CompaniesPage
from app.pages.master.branches import BranchesPage
from app.pages.master.warehouses import WarehousesPage
from app.pages.marketing.campaigns import CampaignsPage
from app.pages.purchasing.purchase_request import PurchaseRequestPage
from app.pages.purchasing.purchase_order import PurchaseOrderPage
from app.pages.purchasing.goods_receipt import GoodsReceiptPage
from app.pages.purchasing.purchase_return import PurchaseReturnPage
from app.pages.inventory.stock_balance import StockBalancePage
from app.pages.inventory.stock_transfer import StockTransferPage
from app.pages.inventory.stock_opname import StockOpnamePage
from app.pages.inventory.stock_movement import StockMovementPage
from app.pages.master.products import ProductsPage
from app.pages.master.vendors import VendorsPage
from app.pages.master.partners_customers import PartnersPage, CustomersPage
from app.pages.hr.employees import EmployeesPages
from app.pages.master.departments import DepartmentsPage
from app.pages.settings.users import UsersPage
from app.pages.settings.roles import RolesPage
from app.pages.settings.menus import MenusPage
from app.pages.settings.uom import UOMsPage
from app.pages.settings.uomcoversion import UOMConversionsPage
from app.pages.finance.credit_note import CreditNotePage
from app.pages.sales.sales_order import SalesOrderPage
from app.pages.finance.commission import CommissionPage
from app.pages.sales.delivery_order import DeliveryOrderPage
from app.pages.sales.invoice import InvoicePage
from app.pages.tax.tax_management import TaxManagementPage
from app.pages.sales.payment import PaymentPage

def get_routes(page: ft.Page, session, navigate_fn, content_area):
    """
    Mengembalikan dictionary route yang dipetakan ke lambda builder.
    """
    return {
        "/dashboard":           lambda: DashboardPage(session, navigate_fn),
        # Master Data
        "/master/companies":    lambda: CompaniesPage(page, session),
        "/master/branches":     lambda: BranchesPage(page, session),
        "/master/warehouses":   lambda: WarehousesPage(page, session),
        
        "/marketing/campaigns": lambda: CampaignsPage(page, session),
        "/purchasing/pr":       lambda: PurchaseRequestPage(page, session),
        "/purchasing/po":       lambda: PurchaseOrderPage(page, session),
        "/purchasing/gr":       lambda: GoodsReceiptPage(page, session),
        "/purchasing/return":   lambda: PurchaseReturnPage(page, session),
        "/inventory/balance":   lambda: StockBalancePage(page, session),
        "/inventory/transfer":  lambda: StockTransferPage(page, session),
        "/inventory/opname":    lambda: StockOpnamePage(page, session),
        "/inventory/movement":  lambda: StockMovementPage(page, session),
        "/master/products":     lambda: ProductsPage(page, session),
        "/master/categories":   lambda: ProductsPage(page, session, tab=1),
        "/master/vendors":      lambda: VendorsPage(page, session),
        "/master/partners":     lambda: PartnersPage(page, session),
        "/master/customers":    lambda: CustomersPage(page, session),
        "/hr/employees":        lambda: EmployeesPages(page, session, content_area),
        "/master/departments":  lambda: DepartmentsPage(page, session),
        "/hr/employee-assignment": lambda: DepartmentsPage(page, session),
        "/settings/users":      lambda: UsersPage(page, session),
        "/settings/roles":      lambda: RolesPage(page, session),
        "/settings/menus":      lambda: MenusPage(page, session),
        "/settings/uoms":       lambda: UOMsPage(page, session),
        "/settings/uom-conversions": lambda: UOMConversionsPage(page, session),
        "/finance/credit-note": lambda: CreditNotePage(page, session),
        "/sales/so":            lambda: SalesOrderPage(page, session),
        "/finance/comissions":  lambda: CommissionPage(page, session),
        "/sales/delivery":      lambda: DeliveryOrderPage(page, session),
        "/sales/invoice":       lambda: InvoicePage(page,session),
        "/sales/payment":       lambda: PaymentPage(page,session),
        "/tax/tax-management":  lambda: TaxManagementPage(page,session)
    }