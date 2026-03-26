from __future__ import annotations
import flet as ft

from app.database import engine, Base, SessionLocal
from app.models import *          # noqa — register semua ORM model
from app.services.seeder  import init_db, seed_all
from app.services.auth    import AuthService, AppSession
from app.utils.theme      import Colors, Sizes, build_theme
from router import get_routes

from app.pages.login       import LoginPage
from app.pages.placeholder import PlaceholderPage
from app.components.sidebar import create_sidebar
from app.components.topbar  import create_topbar


#

# ── Init DB sekali saat modul di-load ────────────────────────
init_db()
with SessionLocal() as _db:
    _info = seed_all(_db)
    if _info:
        print(f"[seed] {_info}")

# ─────────────────────────────────────────────────────────────
def main(page: ft.Page):

    # ── Page setup ───────────────────────────────────────────
    page.title             = "ERP System"
    page.theme_mode        = ft.ThemeMode.DARK
    page.theme             = build_theme(Colors)
    page.bgcolor           = Colors.BG_DARK
    page.padding           = 0
    page.window.min_width  = 900
    page.window.min_height = 600

    # ── App state ────────────────────────────────────────────
    session: AppSession | None = None
    _sidebar: dict | None      = None
    _topbar:  dict | None      = None
    _label_map: dict[str, str] = {}
    ROUTES = {}

    content_area = ft.Container(expand=True, bgcolor=Colors.BG_DARK)


    def _get_page(route: str) -> ft.Control:
        builder = ROUTES.get(route)
        if builder:
            return builder()
        # Fallback → placeholder untuk route yang belum diimplementasi
        label = _label_map.get(route, route.split("/")[-1].replace("_", " ").title())
        return PlaceholderPage(label, route)

    # ── Navigate ─────────────────────────────────────────────
    def navigate(route: str, code: str):
        label = _label_map.get(route, route.split("/")[-1].replace("_", " ").title())

        if _topbar:
            _topbar["set_title"](label)
        if _sidebar:
            _sidebar["set_active"](route, code)

        content_area.content = _get_page(route)
        content_area.update()

    # ── Logout ───────────────────────────────────────────────
    def do_logout():
        nonlocal session, _sidebar, _topbar
        session  = None
        _sidebar = None
        _topbar  = None
        _label_map.clear()
        show_login()

    # ── Login handler ────────────────────────────────────────
    def handle_login(username: str, password: str):
        nonlocal session, _sidebar, _topbar, ROUTES

        with SessionLocal() as db:
            ok, msg, sess = AuthService.login(db, username, password)

        if not ok:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(msg, color=ft.Colors.WHITE),
                bgcolor=Colors.ERROR,
                duration=3000,
            )
            page.snack_bar.open = True
            page.update()
            if hasattr(page, "_login_error_fn"):
                page._login_error_fn(msg)
            return

        session = sess
        ROUTES.update(get_routes(page, session, navigate, content_area))

        def _fill(nodes):
            for n in nodes:
                if n.get("route"):
                    _label_map[n["route"]] = n["label"]
                _fill(n.get("children", []))
        _fill(session.menu_tree)

        show_main()

    # ── Show Login ───────────────────────────────────────────
    def show_login():
        page.controls.clear()
        login_ctrl, error_fn = LoginPage(on_login=handle_login)
        page._login_error_fn = error_fn
        page.add(ft.Container(expand=True, content=login_ctrl))
        page.update()

    def update_app_theme(theme_name: str):
        # 1. Update data warna berdasarkan nama
        Colors.set_mode_by_name(theme_name)
        
        # 2. Sesuaikan ThemeMode Flet (Dark/Light)
        # Ocean, Earth, Light masuk ke LightMode. Purple, Dark masuk ke DarkMode.
        if theme_name in ["dark", "purple"]:
            page.theme_mode = ft.ThemeMode.DARK
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            
        # 3. Re-build & Apply
        page.theme = build_theme(Colors)
        page.bgcolor = Colors.BG_DARK
        page.session.store.set("theme_name", theme_name)
        

        # 4. Deep Refresh
        if session:
            show_main()
        else:
            show_login()

    # Saat start awal:
    initial_theme = page.session.store.get("theme_name") or "light"
    update_app_theme(initial_theme)
    
    # ── Show Main ────────────────────────────────────────────
    def show_main():
        print("ID Cabang",session.branch_id)
        nonlocal _sidebar, _topbar

        _sidebar = create_sidebar(
            menu_tree    = session.menu_tree,
            full_name    = session.full_name,
            company_name = session.company_name,
            on_navigate  = navigate,
            on_logout    = do_logout,
        )
        _topbar = create_topbar(
            page=page,
            on_theme_change=update_app_theme,
            title        = "Dashboard",
            full_name    = session.full_name,
            company_name = session.company_name,
        )

        content_area.content = _get_page("/dashboard")

        layout = ft.Row(
            expand=True,
            spacing=0,
            controls=[
                _sidebar["container"],
                ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        _topbar["container"],
                        content_area,
                    ],
                ),
            ],
        )

        page.controls.clear()
        page.add(layout)
        page.update()

    # ── Start ────────────────────────────────────────────────
    show_login()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets", view=ft.AppView.WEB_BROWSER, port=5000, host="0.0.0.0")
