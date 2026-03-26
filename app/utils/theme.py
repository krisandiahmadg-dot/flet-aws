"""
app/utils/theme.py
Konstanta warna, ukuran, dan style untuk tampilan Flet yang konsisten.
"""

import flet as ft

# class ThemeColors:
    # def __init__(self, mode="light"):
    #     self.set_theme(mode)
    
    # def set_theme(self, mode):
    #     if mode == "dark":
    #         # Background
    #         BG_DARK        = "#0D1117"   # body / page background
    #         BG_SIDEBAR     = "#161B22"   # navigation rail / drawer
    #         BG_CARD        = "#1C2333"   # card / panel
    #         BG_INPUT       = "#21262D"   # text field background
    #         BG_HOVER       = "#2D3748"   # hover state

    #         # Accent
    #         ACCENT         = "#00C896"   # teal-green primary action
    #         ACCENT_DARK    = "#00A07A"   # hover accent
    #         ACCENT_LIGHT   = "#E6FFF8"   # accent text on dark

    #         # Text
    #         TEXT_PRIMARY   = "#E6EDF3"
    #         TEXT_SECONDARY = "#8B949E"
    #         TEXT_MUTED     = "#484F58"
    #         TEXT_ON_ACCENT = "#0D1117"

    #         # Status
    #         SUCCESS  = "#3FB950"
    #         WARNING  = "#D29922"
    #         ERROR    = "#F85149"
    #         INFO     = "#388BFD"

    #         # Border
    #         BORDER   = "#30363D"
    #         DIVIDER  = "#21262D"
    #     else:
    #         # Background
    #         BG_DARK       = "#F8FAFC"   # body / page background
    #         BG_SIDEBAR     = "#FFFFFF"   # navigation rail / drawer
    #         BG_CARD        = "#FFFFFF"   # card / panel
    #         BG_INPUT       = "#F1F5F9"   # text field background
    #         BG_HOVER       = "#E2E8F0"   # hover state

    #         # Accent (Cheerful Yellow)
    #         ACCENT         = "#FFD200"   # bright yellow primary action
    #         ACCENT_DARK    = "#E6BC00"   # hover accent
    #         ACCENT_LIGHT   = "#FFF9E6"   # soft highlight

    #         # Text
    #         TEXT_PRIMARY   = "#1E293B"
    #         TEXT_SECONDARY = "#64748B"
    #         TEXT_MUTED     = "#94A3B8"
    #         TEXT_ON_ACCENT = "#422006"

    #         # Status
    #         SUCCESS  = "#22C55E"
    #         WARNING  = "#FB923C"
    #         ERROR    = "#F43F5E"
    #         INFO     = "#0EA5E9"

    #         # Border
    #         BORDER   = "#E2E8F0"
    #         DIVIDER  = "#F1F5F9"
    
# colors = ThemeColors(mode="light")
# ─────────────────────────────────────────────────────────────
# COLOR PALETTE  (dark navy + teal accent)
# ─────────────────────────────────────────────────────────────
# class Colors:
#     # # Background
#     # BG_DARK        = "#0D1117"   # body / page background
#     # BG_SIDEBAR     = "#161B22"   # navigation rail / drawer
#     # BG_CARD        = "#1C2333"   # card / panel
#     # BG_INPUT       = "#21262D"   # text field background
#     # BG_HOVER       = "#2D3748"   # hover state

#     # # Accent
#     # ACCENT         = "#00C896"   # teal-green primary action
#     # ACCENT_DARK    = "#00A07A"   # hover accent
#     # ACCENT_LIGHT   = "#E6FFF8"   # accent text on dark

#     # # Text
#     # TEXT_PRIMARY   = "#E6EDF3"
#     # TEXT_SECONDARY = "#8B949E"
#     # TEXT_MUTED     = "#484F58"
#     # TEXT_ON_ACCENT = "#0D1117"

#     # # Status
#     # SUCCESS  = "#3FB950"
#     # WARNING  = "#D29922"
#     # ERROR    = "#F85149"
#     # INFO     = "#388BFD"

#     # # Border
#     # BORDER   = "#30363D"
#     # DIVIDER  = "#21262D"
#     # Background
#     BG_DARK       = "#F8FAFC"   # body / page background
#     BG_SIDEBAR     = "#FFFFFF"   # navigation rail / drawer
#     BG_CARD        = "#FFFFFF"   # card / panel
#     BG_INPUT       = "#F1F5F9"   # text field background
#     BG_HOVER       = "#E2E8F0"   # hover state

#     # Accent (Cheerful Yellow)
#     ACCENT         = "#FFD200"   # bright yellow primary action
#     ACCENT_DARK    = "#E6BC00"   # hover accent
#     ACCENT_LIGHT   = "#FFF9E6"   # soft highlight

#     # Text
#     TEXT_PRIMARY   = "#1E293B"
#     TEXT_SECONDARY = "#64748B"
#     TEXT_MUTED     = "#94A3B8"
#     TEXT_ON_ACCENT = "#422006"

#     # Status
#     SUCCESS  = "#22C55E"
#     WARNING  = "#FB923C"
#     ERROR    = "#F43F5E"
#     INFO     = "#0EA5E9"

#     # Border
#     BORDER   = "#E2E8F0"
#     DIVIDER  = "#F1F5F9"


class Sizes:
    SIDEBAR_W       = 240
    SIDEBAR_W_RAIL  = 64   # collapsed
    TOPBAR_H        = 56
    BORDER_RADIUS   = 10
    CARD_RADIUS     = 12
    BTN_RADIUS      = 8


# ─────────────────────────────────────────────────────────────
# FLET THEME
# ─────────────────────────────────────────────────────────────
class ColorPalette:
    def __init__(self):
        # Default: Tema Ceria (Light)
        self.set_dark_mode()

    def set_light_mode(self):
        self.LOGO           = "#FFFFFF"  # Ruby Red
        self.TEXT_HEAD_TITLE = "#FFFFFF"  # Hitam Tajam
        self.TEXT_SUB_TITLE = "#E6E6E6"  # Abu-abu Gelap (Soft Black)
        self.ICON_MENU      = "#E6E6E6"
        self.TEXT_MENU      = "#E6E6E6"
        self.BG_DARK        = "#FFF1F2"  # Rose sangat lembut
        self.BG_SIDEBAR     = "#A5566C"  # Deep Crimson (Kontras dengan Teks Sidebar)
        self.TEXT_HEAD_TITLE = "#FFFFFF"  # Hitam Tajam
        self.TEXT_SUB_TITLE = "#E6E6E6"  # Abu-abu Gelap (Soft Black)
        self.ICON_MENU      = "#E6E6E6"
        self.TEXT_MENU      = "#E6E6E6"
        self.BG_CARD        = "#FFFFFF"
        self.BG_INPUT       = "#FFE4E6"
        self.BG_HOVER       = "#FCE7F3"
        self.ACCENT         = "#E11D48"  # Ruby Red
        self.ACCENT_DARK    = "#9F1239"
        self.ACCENT_LIGHT   = "#FDA4AF"
        self.TEXT_PRIMARY   = "#000000"  # Hitam Tajam
        self.TEXT_SECONDARY = "#121213"  # Abu-abu Gelap (Soft Black)
        self.TEXT_MUTED     = "#9F1239"
        self.TEXT_ON_ACCENT = "#FFFFFF"
        self.TEXT_SIDEBAR   = "#FFFFFF"  # Kontras dengan BG_SIDEBAR
        self.ICON_SIDEBAR   = "#FB7185"
        self.SUCCESS        = "#10B981"
        self.WARNING        = "#F59E0B"
        self.ERROR          = "#E11D48"
        self.INFO           = "#2563EB"
        self.BORDER         = "#FECDD3"
        self.DIVIDER        = "#FFE4E6"

    def set_dark_mode(self):
        """Tema Midnight Teal (Gelap Standar)"""
        self.LOGO           = "#FFFFFF"  # Ruby Red
        self.TEXT_HEAD_TITLE = "#FFFFFF"  # Hitam Tajam
        self.TEXT_SUB_TITLE = "#E6E6E6"  # Abu-abu Gelap (Soft Black)
        self.ICON_MENU      = "#E6E6E6"
        self.TEXT_MENU      = "#E6E6E6"
        self.BG_DARK        = "#0D1117"
        self.BG_SIDEBAR     = "#161B22"
        self.BG_CARD        = "#1C2128"
        self.BG_INPUT       = "#21262D"
        self.BG_HOVER       = "#2D333B"
        self.ACCENT         = "#00C896"
        self.ACCENT_DARK    = "#00A07A"
        self.ACCENT_LIGHT   = "#E6FFF8"
        self.TEXT_PRIMARY   = "#F0F6FC"  # Putih Off-White
        self.TEXT_SECONDARY = "#8B949E"
        self.TEXT_MUTED     = "#484F58"
        self.TEXT_ON_ACCENT = "#0D1117"
        self.TEXT_SIDEBAR   = "#C9D1D9"  # Teks Terang di Sidebar Gelap
        self.ICON_SIDEBAR   = "#8B949E"
        self.SUCCESS        = "#3FB950"
        self.WARNING        = "#D29922"
        self.ERROR          = "#F85149"
        self.INFO           = "#388BFD"
        self.BORDER         = "#30363D"
        self.DIVIDER        = "#21262D"

    def set_ocean_mode(self):
        """Tema Ocean Blue (Cerah & Profesional)"""
        self.LOGO           = "#F0FDF4"  # Emerald Dark
        self.TEXT_HEAD_TITLE = "#FFFFFF"  # Hitam Hijau Pekat
        self.TEXT_SUB_TITLE  = "#E6E6E6"  # Soft Black
        self.ICON_MENU       = "#CBCECA"
        self.TEXT_MENU       = "#A4FFE2"
        self.BG_DARK         = "#F0F9FF"  # Biru Pucat Sangat Soft
        self.BG_SIDEBAR      = "#0F172A"  # Navy Gelap (Kontras dengan Sidebar Text)
        self.BG_CARD         = "#FFFFFF"
        self.BG_INPUT        = "#E0F2FE"
        self.BG_HOVER        = "#F1F5F9"
        self.ACCENT          = "#3B82F6"  # Blue Accent
        self.ACCENT_DARK     = "#1D4ED8"
        self.ACCENT_LIGHT    = "#DBEAFE"
        self.TEXT_PRIMARY    = "#000000"  # Hitam Murni
        self.TEXT_SECONDARY  = "#334155"  # Hitam Soft
        self.TEXT_MUTED      = "#94A3B8"
        self.TEXT_ON_ACCENT  = "#FFFFFF"
        self.TEXT_SIDEBAR    = "#F8FAFC"  # Putih Kristal
        self.ICON_SIDEBAR    = "#94A3B8"
        self.SUCCESS         = "#10B981"
        self.WARNING         = "#F59E0B"
        self.ERROR           = "#EF4444"
        self.INFO            = "#3B82F6"
        self.BORDER          = "#E2E8F0"
        self.DIVIDER         = "#F1F5F9"

    def set_purple_mode(self):
        """Tema Nature Green (Segar & Nyaman)"""
        self.LOGO           = "#F0FDF4"  # Emerald Dark
        self.TEXT_HEAD_TITLE = "#FFFFFF"  # Hitam Hijau Pekat
        self.TEXT_SUB_TITLE  = "#E6E6E6"  # Soft Black
        self.ICON_MENU       = "#CBCECA"
        self.TEXT_MENU       = "#A4FFE2"
        self.BG_DARK         = "#F0FDF4"  # Mint Putih Sangat Soft
        self.BG_SIDEBAR      = "#064E3B"  # Dark Green (Hampir Hitam)
        self.BG_CARD         = "#FFFFFF"
        self.BG_INPUT        = "#DCFCE7"
        self.BG_HOVER        = "#F0FDF4"
        self.ACCENT          = "#10B981"  # Emerald
        self.ACCENT_DARK     = "#047857"
        self.ACCENT_LIGHT    = "#D1FAE5"
        self.TEXT_PRIMARY    = "#000000"  # Hitam Murni
        self.TEXT_SECONDARY  = "#1F2937"  # Abu-abu Sangat Gelap
        self.TEXT_MUTED      = "#6B7280"
        self.TEXT_ON_ACCENT  = "#FFFFFF"
        self.TEXT_SIDEBAR    = "#F0FDF4"  # Putih Hijau Pucat
        self.ICON_SIDEBAR    = "#A7F3D0"
        self.SUCCESS         = "#059669"
        self.WARNING         = "#D97706"
        self.ERROR           = "#DC2626"
        self.INFO            = "#0284C7"
        self.BORDER          = "#D1FAE5"
        self.DIVIDER         = "#F0FDF4"

    def set_earth_mode(self):
        """Tema Graphite Modern (Minimalis)"""
        self.LOGO           = "#E60A0A"  # Hitam Murni
        self.TEXT_HEAD_TITLE = "#FFFFFF"  # Hitam Tajam
        self.TEXT_SUB_TITLE  = "#DFDFDF"  # Abu-abu Gelap
        self.ICON_MENU       = "#07C400"
        self.TEXT_MENU       = "#EEEEEE"
        self.BG_DARK         = "#F9FAFB"  # Putih Abu-abu Sangat Soft
        self.BG_SIDEBAR      = "#111827"  # Slate Black
        self.BG_CARD         = "#FFFFFF"
        self.BG_INPUT        = "#F3F4F6"
        self.BG_HOVER        = "#E5E7EB"
        self.ACCENT          = "#374151"  # Graphite Gray
        self.ACCENT_DARK     = "#111827"
        self.ACCENT_LIGHT    = "#F3F4F6"
        self.TEXT_PRIMARY    = "#000000"  # Hitam Murni
        self.TEXT_SECONDARY  = "#374151"  # Charcoal Soft
        self.TEXT_MUTED      = "#9CA3AF"
        self.TEXT_ON_ACCENT  = "#FFFFFF"
        self.TEXT_SIDEBAR    = "#FFFFFF"  # Putih Murni
        self.ICON_SIDEBAR    = "#9CA3AF"
        self.SUCCESS         = "#10B981"
        self.WARNING         = "#F59E0B"
        self.ERROR           = "#E11D48"
        self.INFO            = "#2563EB"
        self.BORDER          = "#E5E7EB"
        self.DIVIDER         = "#F3F4F6"
    
    def set_mode_by_name(self, name: str):
        if name == "ocean": self.set_ocean_mode()
        elif name == "purple": self.set_purple_mode()
        elif name == "earth": self.set_earth_mode()
        elif name == "dark": self.set_dark_mode()
        else: self.set_light_mode()

# Buat instance tunggal
Colors = ColorPalette()

def build_theme(colors_obj: ColorPalette) -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=colors_obj.ACCENT,
        color_scheme=ft.ColorScheme(
            primary=colors_obj.ACCENT,
            on_primary=colors_obj.TEXT_ON_ACCENT,
            surface=colors_obj.BG_CARD,
            on_surface=colors_obj.TEXT_PRIMARY,
            secondary=colors_obj.INFO,
            error=colors_obj.ERROR,
        ),
        text_theme=ft.TextTheme(
            body_large=ft.TextStyle(color=colors_obj.TEXT_PRIMARY, size=14),
            body_medium=ft.TextStyle(color=colors_obj.TEXT_PRIMARY, size=13),
            title_medium=ft.TextStyle(
                color=colors_obj.TEXT_PRIMARY, size=16, weight=ft.FontWeight.W_600
            ),
            label_large=ft.TextStyle(color=colors_obj.TEXT_PRIMARY, size=13),
        ),
        visual_density=ft.Theme.visual_density,
    )


# ─────────────────────────────────────────────────────────────
# ICON MAP — string → ft.Icons constant
# ─────────────────────────────────────────────────────────────
_ICON_MAP: dict[str, str] = {
    "dashboard":           ft.Icons.DASHBOARD,
    "storage":             ft.Icons.STORAGE,
    "business":            ft.Icons.BUSINESS,
    "store":               ft.Icons.STORE,
    "apartment":           ft.Icons.APARTMENT,
    "inventory_2":         ft.Icons.INVENTORY_2,
    "inventory":           ft.Icons.INVENTORY,
    "local_shipping":      ft.Icons.LOCAL_SHIPPING,
    "handshake":           ft.Icons.HANDSHAKE,
    "people":              ft.Icons.PEOPLE,
    "warehouse":           ft.Icons.WAREHOUSE,
    "swap_horiz":          ft.Icons.SWAP_HORIZ,
    "sync_alt":            ft.Icons.SYNC_ALT,
    "checklist":           ft.Icons.CHECKLIST,
    "shopping_cart":       ft.Icons.SHOPPING_CART,
    "request_page":        ft.Icons.REQUEST_PAGE,
    "receipt_long":        ft.Icons.RECEIPT_LONG,
    "move_to_inbox":       ft.Icons.MOVE_TO_INBOX,
    "point_of_sale":       ft.Icons.POINT_OF_SALE,
    "shopping_bag":        ft.Icons.SHOPPING_BAG,
    "receipt":             ft.Icons.RECEIPT,
    "payments":            ft.Icons.PAYMENTS,
    "campaign":            ft.Icons.CAMPAIGN,
    "assessment":          ft.Icons.ASSESSMENT,
    "star":                ft.Icons.STAR,
    "star_half":           ft.Icons.STAR_HALF,
    "person_search":       ft.Icons.PERSON_SEARCH,
    "trending_up":         ft.Icons.TRENDING_UP,
    "leaderboard":         ft.Icons.LEADERBOARD,
    "settings":            ft.Icons.SETTINGS,
    "manage_accounts":     ft.Icons.MANAGE_ACCOUNTS,
    "admin_panel_settings":ft.Icons.ADMIN_PANEL_SETTINGS,
    "menu":                ft.Icons.MENU,
    "logout":              ft.Icons.LOGOUT,
    "person":              ft.Icons.PERSON,
    "chevron_right":       ft.Icons.CHEVRON_RIGHT,
    "expand_less":         ft.Icons.EXPAND_LESS,
    "expand_more":         ft.Icons.EXPAND_MORE,
    # HR
    "groups":              ft.Icons.GROUPS,
    "badge":               ft.Icons.BADGE,
    "event_available":     ft.Icons.EVENT_AVAILABLE,
    "beach_access":        ft.Icons.BEACH_ACCESS,
}


def get_icon(name: str) -> str:
    """Konversi nama string dari DB ke ft.Icons constant."""
    return _ICON_MAP.get((name or "").lower(), ft.Icons.CIRCLE)


