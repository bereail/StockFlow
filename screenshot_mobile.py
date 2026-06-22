"""Captura screenshots en viewport mobile (390x844 ~ iPhone 14)."""
import os, time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
OUT  = r"C:\Users\bsolohaga\Desktop\bere\GIT\stockTonerDesktop\screenshots"
os.makedirs(OUT, exist_ok=True)

MOBILE = {"viewport": {"width": 390, "height": 844}}

PAGES = [
    ("login",      "/accounts/login/",      False),
    ("dashboard",  "/",                     True),
    ("toner",      "/toner/",               True),
    ("pcs",        "/pcs/",                 True),
    ("articulos",  "/articulos/",           True),
    ("impresoras", "/impresoras/",          True),
    ("servicios",  "/servicios/",           True),
    ("movimientos","/movimientos/",         True),
    ("prestamos",  "/prestamos/",           True),
    ("pendientes", "/pendientes/",          True),
    ("reparaciones","/reparaciones/",       True),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(**MOBILE)
    page = ctx.new_page()

    # 1. Login
    page.goto(f"{BASE}/accounts/login/")
    page.wait_for_load_state("domcontentloaded")
    page.fill('input[name="username"]', "bere")
    page.fill('input[name="password"]', "***REMOVED***")
    page.click('button[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.4)

    for name, path, need_auth in PAGES:
        try:
            page.goto(f"{BASE}{path}")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(0.3)
            page.screenshot(path=f"{OUT}/{name}.png", full_page=False)
            print(f"  OK  {name}")
        except Exception as e:
            print(f"  ERR {name}: {e}")

    # Screenshot con el nav mobile abierto
    page.goto(f"{BASE}/toner/")
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.2)
    page.click("#nav-toggle")
    time.sleep(0.4)
    page.screenshot(path=f"{OUT}/nav_mobile_abierto.png", full_page=False)
    print("  OK  nav_mobile_abierto")

    # Scroll abajo para ver las cards "Más secciones"
    page.evaluate("document.getElementById('mobile-nav').scrollTop = 400")
    time.sleep(0.3)
    page.screenshot(path=f"{OUT}/nav_mas_seccion.png", full_page=False)
    print("  OK  nav_mas_seccion")

    browser.close()

print("\nListo — capturas en:", OUT)
