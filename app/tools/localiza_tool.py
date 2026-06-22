from typing import Type
import requests
from urllib.parse import urljoin

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from playwright.sync_api import sync_playwright

from app.logger import info, success, warning, error, step
from app.utils import ensure_dirs, SCREENSHOTS_DIR, DOWNLOADS_DIR, save_report, timestamp


class LocalizaToolInput(BaseModel):
    instruction: str = Field(..., description="Instrução completa da tarefa")


class LocalizaResultsDownloadTool(BaseTool):
    name: str = "Localiza Results PDF Downloader"
    description: str = (
        "Acessa o site de RI da Localiza, procura PDFs de Divulgação de Resultados "
        "de 2026 e baixa os arquivos."
    )
    args_schema: Type[BaseModel] = LocalizaToolInput

    def _run(self, instruction: str) -> str:
        ensure_dirs()

        found_files = []
        identified_items = []
        available_years = set()
        strategy_logs = []
        errors = []
        screenshots = []

        def snap(page, label):
            try:
                file_path = SCREENSHOTS_DIR / f"{timestamp()}_{label}.png"
                page.screenshot(path=str(file_path), full_page=True)
                screenshots.append(str(file_path))
                info(f"Screenshot salva: {file_path}")
            except Exception as ex:
                errors.append(f"Falha ao salvar screenshot '{label}': {ex}")

        def close_popups(page):
            popup_texts = [
                "Aceitar", "Accept", "OK", "Fechar", "Close",
                "Continuar", "Entendi", "Permitir", "Concordo"
            ]
            for text in popup_texts:
                try:
                    btn = page.get_by_text(text, exact=False)
                    if btn.count() > 0:
                        btn.first.click(timeout=2000)
                        info(f"Popup/botão tratado: {text}")
                        page.wait_for_timeout(1500)
                except Exception:
                    pass

        def try_click_by_text(page, options):
            for text in options:
                try:
                    locator = page.get_by_text(text, exact=False)
                    if locator.count() > 0:
                        locator.first.scroll_into_view_if_needed()
                        page.wait_for_timeout(1000)
                        locator.first.click(timeout=5000)
                        return True, f"Clicou em '{text}'"
                except Exception:
                    continue
            return False, f"Não encontrou: {options}"

        def download_direct_pdf(url, fallback_name="arquivo.pdf"):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").lower()
                filename = url.split("/")[-1].split("?")[0].strip()

                if not filename.lower().endswith(".pdf"):
                    filename = fallback_name

                if "pdf" not in content_type and not filename.lower().endswith(".pdf"):
                    raise RuntimeError("A URL não retornou um conteúdo PDF válido.")

                path = DOWNLOADS_DIR / filename
                path.write_bytes(response.content)
                return path
            except Exception as ex:
                raise RuntimeError(f"Falha no download direto: {ex}")

        try:
            with sync_playwright() as p:
                step("Abrindo navegador")
                browser = p.chromium.launch(
                    headless=False,
                    slow_mo=1000
                )

                context = browser.new_context(accept_downloads=True)
                page = context.new_page()

                step("Acessando o site da Localiza RI")
                page.goto(
                    "https://ri.localiza.com/",
                    timeout=30000,
                    wait_until="domcontentloaded"
                )
                page.wait_for_timeout(4000)
                close_popups(page)
                page.wait_for_timeout(2000)
                snap(page, "home")

                step("Estratégia 1: navegar pelo menu principal")
                ok, msg = try_click_by_text(page, ["Informações aos Acionistas"])
                strategy_logs.append(f"Estratégia 1A: {msg}")
                page.wait_for_timeout(3000)
                snap(page, "menu_informacoes_acionistas")

                if not ok:
                    warning("Tentando abrir menu mobile")
                    for selector in [
                        "button[aria-label*='menu' i]",
                        "button[aria-label*='Menu' i]",
                        ".menu-toggle",
                        ".hamburger",
                        ".navbar-toggler"
                    ]:
                        try:
                            if page.locator(selector).count() > 0:
                                page.locator(selector).first.click(timeout=3000)
                                page.wait_for_timeout(3000)
                                snap(page, "menu_mobile_aberto")
                                break
                        except Exception:
                            pass

                    ok, msg = try_click_by_text(page, ["Informações aos Acionistas"])
                    strategy_logs.append(f"Estratégia 1B: {msg}")
                    page.wait_for_timeout(3000)
                    snap(page, "menu_informacoes_acionistas_mobile")

                ok2, msg2 = try_click_by_text(page, ["Central de Resultados"])
                strategy_logs.append(f"Estratégia 1C: {msg2}")
                page.wait_for_timeout(5000)
                snap(page, "central_resultados")

                step("Estratégia 2: mapear anos disponíveis")
                try:
                    body_text = page.locator("body").inner_text(timeout=10000)
                except Exception:
                    body_text = ""

                for token in ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018"]:
                    if token in body_text:
                        available_years.add(token)

                try:
                    y = page.get_by_text("2026", exact=False)
                    if y.count() > 0:
                        y.first.scroll_into_view_if_needed()
                        page.wait_for_timeout(1000)
                        y.first.click(timeout=3000)
                        page.wait_for_timeout(3000)
                        strategy_logs.append("Estratégia 2A: seção 2026 clicada/expandida")
                    else:
                        strategy_logs.append("Estratégia 2A: ano 2026 não visível")
                except Exception:
                    strategy_logs.append("Estratégia 2A: ano 2026 não clicável")

                snap(page, "ano_2026")

                step("Estratégia 3: varredura de links candidatos")
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
                            identified_items.append({
                                "name": text if text else "Sem texto visível",
                                "href": absolute_href if href else "não capturada"
                            })

                            try:
                                link.scroll_into_view_if_needed()
                                page.wait_for_timeout(1000)

                                with page.expect_download(timeout=12000) as download_info:
                                    link.click(timeout=5000)

                                download = download_info.value
                                save_path = DOWNLOADS_DIR / download.suggested_filename
                                download.save_as(str(save_path))
                                found_files.append(str(save_path))
                                success(f"Download concluído: {save_path.name}")
                                page.wait_for_timeout(2000)
                                continue

                            except Exception:
                                pass

                            if ".pdf" in absolute_href.lower():
                                try:
                                    pdf_path = download_direct_pdf(
                                        absolute_href,
                                        fallback_name=f"localiza_resultado_{i}.pdf"
                                    )
                                    found_files.append(str(pdf_path))
                                    success(f"Download direto concluído: {pdf_path.name}")
                                    page.wait_for_timeout(1500)
                                except Exception as ex:
                                    errors.append(str(ex))

                    except Exception:
                        continue

                strategy_logs.append("Estratégia 3: varredura finalizada")
                snap(page, "final")

                page.wait_for_timeout(5000)
                browser.close()

        except Exception as ex:
            errors.append(f"Erro geral na automação: {ex}")
            error(str(ex))

        status = "Sucesso" if found_files else "Sucesso Parcial" if identified_items else "Falha"

        report_lines = []
        report_lines.append("# Relatório de Execução da Automação")
        report_lines.append("")
        report_lines.append("## 1. Status da tarefa")
        report_lines.append(f"- **Status:** {status}")
        report_lines.append("")
        report_lines.append("## 2. Estratégias utilizadas")
        if strategy_logs:
            for item in strategy_logs:
                report_lines.append(f"- {item}")
        else:
            report_lines.append("- Nenhuma estratégia foi registrada.")
        report_lines.append("")
        report_lines.append("## 3. Arquivos identificados")
        if identified_items:
            for item in identified_items:
                report_lines.append(f"- {item['name']} | {item['href']}")
        else:
            report_lines.append("- Nenhum item identificado.")
        report_lines.append("")
        report_lines.append("## 4. Arquivos baixados")
        if found_files:
            for file in found_files:
                report_lines.append(f"- {file}")
        else:
            report_lines.append("- Nenhum arquivo foi baixado.")
        report_lines.append("")
        report_lines.append("## 5. Anos observados na página")
        if available_years:
            for year in sorted(available_years, reverse=True):
                report_lines.append(f"- {year}")
        else:
            report_lines.append("- Nenhum ano identificado.")
        report_lines.append("")
        report_lines.append("## 6. Evidências capturadas")
        if screenshots:
            for shot in screenshots:
                report_lines.append(f"- {shot}")
        else:
            report_lines.append("- Nenhuma screenshot foi registrada.")
        report_lines.append("")
        report_lines.append("## 7. Erros e observações")
        if errors:
            for err in errors:
                report_lines.append(f"- {err}")
        else:
            report_lines.append("- Nenhum erro crítico registrado.")
        report_lines.append("")
        report_lines.append("## 8. Considerações finais")
        report_lines.append(
            "- Este relatório foi gerado automaticamente com base na navegação no site de Relações com Investidores da Localiza."
        )
        report_lines.append(
            "- O objetivo principal foi verificar a existência e realizar o download dos documentos PDF de Divulgação de Resultados referentes ao ano de 2026."
        )

        report = "\n".join(report_lines)
        report_file = save_report(report)
        success(f"Relatório salvo em: {report_file}")

        return report
