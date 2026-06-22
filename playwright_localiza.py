from pathlib import Path
from urllib.parse import urljoin
import requests

from playwright.sync_api import sync_playwright

DOWNLOADS_DIR = Path("output/downloads")
SCREENSHOTS_DIR = Path("output/screenshots")
REPORTS_DIR = Path("output/reports")

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_direct_pdf(url, fallback_name="arquivo.pdf"):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    filename = url.split("/")[-1].split("?")[0].strip()
    if not filename.lower().endswith(".pdf"):
        filename = fallback_name

    path = DOWNLOADS_DIR / filename
    path.write_bytes(response.content)
    return path


def main():
    found_files = []
    identified = []
    available_years = set()
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=2000)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            page.goto("https://ri.localiza.com/", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            page.screenshot(path=str(SCREENSHOTS_DIR / "01_home.png"), full_page=True)

            for text in ["Aceitar", "Accept", "OK", "Fechar", "Close", "Continuar", "Entendi"]:
                try:
                    btn = page.get_by_text(text, exact=False)
                    if btn.count() > 0:
                        btn.first.click(timeout=2000)
                        page.wait_for_timeout(3000)
                except Exception:
                    pass

            try:
                menu = page.get_by_text("Informações aos Acionistas", exact=False)
                if menu.count() > 0:
                    menu.first.scroll_into_view_if_needed()
                    page.wait_for_timeout(2000)
                    menu.first.click(timeout=5000)
                    page.wait_for_timeout(5000)
                else:
                    for selector in [
                        "button[aria-label*='menu' i]",
                        "button[aria-label*='Menu' i]",
                        ".menu-toggle",
                        ".hamburger",
                        ".navbar-toggler"
                    ]:
                        if page.locator(selector).count() > 0:
                            page.locator(selector).first.click(timeout=3000)
                            page.wait_for_timeout(5000)
                            break

                    menu = page.get_by_text("Informações aos Acionistas", exact=False)
                    if menu.count() > 0:
                        menu.first.click(timeout=5000)
                        page.wait_for_timeout(5000)
            except Exception as e:
                errors.append(f"Erro ao abrir menu principal: {e}")

            page.screenshot(path=str(SCREENSHOTS_DIR / "02_menu.png"), full_page=True)

            try:
                central = page.get_by_text("Central de Resultados", exact=False)
                if central.count() > 0:
                    central.first.scroll_into_view_if_needed()
                    page.wait_for_timeout(2000)
                    central.first.click(timeout=5000)
                    page.wait_for_timeout(6000)
            except Exception as e:
                errors.append(f"Erro ao abrir Central de Resultados: {e}")

            page.screenshot(path=str(SCREENSHOTS_DIR / "03_central_resultados.png"), full_page=True)

            try:
                body_text = page.locator("body").inner_text(timeout=10000)
            except Exception:
                body_text = ""

            for year in ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018"]:
                if year in body_text:
                    available_years.add(year)

            try:
                y2026 = page.get_by_text("2026", exact=False)
                if y2026.count() > 0:
                    y2026.first.scroll_into_view_if_needed()
                    page.wait_for_timeout(2000)
                    y2026.first.click(timeout=3000)
                    page.wait_for_timeout(5000)
            except Exception:
                pass

            page.screenshot(path=str(SCREENSHOTS_DIR / "04_ano_2026.png"), full_page=True)

            links = page.locator("a")
            total = links.count()

            for i in range(total):
                try:
                    link = links.nth(i)
                    text = (link.inner_text() or "").strip()
                    href = link.get_attribute("href") or ""
                    absolute_href = urljoin(page.url, href)
                    mix = f"{text} {href}".lower()

                    is_candidate = (
                        ("divulgação" in mix and "resultado" in mix)
                        or ("resultado" in mix and ".pdf" in mix)
                        or ("release" in mix and ".pdf" in mix)
                    )

                    if is_candidate:
                        identified.append((text if text else "Sem texto", absolute_href))

                        try:
                            link.scroll_into_view_if_needed()
                            page.wait_for_timeout(2000)

                            with page.expect_download(timeout=12000) as download_info:
                                link.click(timeout=5000)

                            download = download_info.value
                            save_path = DOWNLOADS_DIR / download.suggested_filename
                            download.save_as(str(save_path))
                            found_files.append(str(save_path))
                            page.wait_for_timeout(3000)
                            continue
                        except Exception:
                            pass

                        if ".pdf" in absolute_href.lower():
                            try:
                                pdf_path = save_direct_pdf(
                                    absolute_href,
                                    fallback_name=f"localiza_resultado_{i}.pdf"
                                )
                                found_files.append(str(pdf_path))
                                page.wait_for_timeout(3000)
                            except Exception as e:
                                errors.append(f"Erro no download direto: {e}")

                except Exception:
                    continue

            page.screenshot(path=str(SCREENSHOTS_DIR / "05_final.png"), full_page=True)

            # Pausa final para você ver o resultado antes de fechar
            page.wait_for_timeout(10000)

        finally:
            browser.close()

    report = REPORTS_DIR / "relatorio_playwright.txt"
    with report.open("w", encoding="utf-8") as f:
        f.write("RELATÓRIO DE EXECUÇÃO\n\n")
        f.write(f"Quantidade de PDFs baixados: {len(found_files)}\n\n")

        f.write("Arquivos identificados:\n")
        for name, href in identified:
            f.write(f"- {name} | {href}\n")
        if not identified:
            f.write("- Nenhum item identificado\n")

        f.write("\nArquivos baixados:\n")
        for file in found_files:
            f.write(f"- {file}\n")
        if not found_files:
            f.write("- Nenhum arquivo baixado\n")

        f.write("\nAnos disponíveis:\n")
        for year in sorted(available_years, reverse=True):
            f.write(f"- {year}\n")
        if not available_years:
            f.write("- Nenhum ano identificado\n")

        f.write("\nErros:\n")
        for err in errors:
            f.write(f"- {err}\n")
        if not errors:
            f.write("- Nenhum erro crítico\n")

    print("Execução finalizada.")
    print(f"Relatório: {report}")


if __name__ == "__main__":
    main()