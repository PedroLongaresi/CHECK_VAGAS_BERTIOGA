#!/usr/bin/env python3
"""
Monitor de Vagas - SESC Bertioga
Verifica disponibilidade de hospedagem e notifica via Telegram
"""

import os
import sys
import time
import json
import logging
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Configurações ────────────────────────────────────────────────────────────

LOGIN_URL   = "https://portal.sescsp.org.br/meu-perfil/bertioga/login?fromUrl=https://reservabertioga.sescsp.org.br/bertioga-web/#/login"
RESERVAS_URL = "https://reservabertioga.sescsp.org.br/bertioga-web/#/reserva"

SESC_EMAIL  = os.environ["SESC_EMAIL"]
SESC_SENHA  = os.environ["SESC_PASSWORD"]
TG_TOKEN    = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID  = os.environ["TELEGRAM_CHAT_ID"]

# Filtros opcionais (deixe vazio "" para não filtrar)
FILTRO_MES  = os.environ.get("FILTRO_MES", "")   # ex: "julho", "agosto"
FILTRO_ANO  = os.environ.get("FILTRO_ANO", "2026")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Telegram ─────────────────────────────────────────────────────────────────

def telegram_send(msg: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        log.info("Mensagem enviada ao Telegram com sucesso.")
    except Exception as e:
        log.error(f"Falha ao enviar Telegram: {e}")

# ── Monitor principal ─────────────────────────────────────────────────────────

def run_check():
    vagas_encontradas = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        try:
            # ── 1. Login ──────────────────────────────────────────────────
            log.info("Abrindo página de login...")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_selector("#logEmail", timeout=20_000)

            page.fill("#logEmail", SESC_EMAIL)
            page.fill("#logPassword", SESC_SENHA)
            page.click("#btnLogin")

            # Aguarda redirecionamento pós-login
            page.wait_for_url("**/bertioga-web/**", timeout=30_000)
            log.info("Login realizado com sucesso.")

            # ── 2. Navega para Reservas ───────────────────────────────────
            log.info("Navegando para página de reservas...")
            page.goto(RESERVAS_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)  # SPA precisa de tempo para renderizar

            # ── 3. Seleciona ano 2026 (se necessário) ────────────────────
            if FILTRO_ANO:
                try:
                    ano_btn = page.locator(f"span:text('{FILTRO_ANO}')").first
                    if ano_btn.is_visible():
                        ano_btn.click()
                        page.wait_for_timeout(2000)
                        log.info(f"Ano {FILTRO_ANO} selecionado.")
                except Exception:
                    log.warning("Botão de ano não encontrado, continuando...")

            # ── 4. Coleta todos os botões "Disponíveis" ───────────────────
            page.wait_for_timeout(2000)

            # Botões com texto "Disponíveis (N)"
            btns = page.locator("button:has-text('Disponíveis')").all()
            log.info(f"Botões 'Disponíveis' encontrados: {len(btns)}")

            for btn in btns:
                try:
                    texto = btn.inner_text().strip()
                    log.info(f"  → {texto}")

                    # Extrai o número entre parênteses
                    import re
                    match = re.search(r"\((\d+)\)", texto)
                    if match:
                        qtd = int(match.group(1))
                        if qtd > 0:
                            # Tenta pegar contexto do período (elemento pai)
                            periodo = ""
                            try:
                                container = btn.locator("xpath=ancestor::div[contains(@class,'periodo')]").first
                                periodo = container.inner_text()[:120].strip().replace("\n", " | ")
                            except Exception:
                                pass

                            # Filtro por mês
                            if FILTRO_MES and FILTRO_MES.lower() not in periodo.lower():
                                log.info(f"    Vaga fora do mês filtrado ({FILTRO_MES}), ignorando.")
                                continue

                            vagas_encontradas.append({
                                "qtd": qtd,
                                "periodo": periodo or texto,
                            })
                            log.info(f"    ✅ {qtd} vaga(s) disponível(is)!")
                except Exception as e:
                    log.warning(f"Erro ao processar botão: {e}")

        except PlaywrightTimeout as e:
            log.error(f"Timeout: {e}")
            telegram_send(
                "⚠️ <b>Monitor SESC</b>\n"
                "Timeout ao carregar a página. Verifique se o site está no ar."
            )
        except Exception as e:
            log.error(f"Erro inesperado: {e}")
            telegram_send(
                f"⚠️ <b>Monitor SESC</b>\nErro inesperado: {str(e)[:200]}"
            )
        finally:
            browser.close()

    return vagas_encontradas


def main():
    log.info("=" * 55)
    log.info("Monitor SESC Bertioga iniciando...")
    log.info(f"Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    if FILTRO_MES:
        log.info(f"Filtro de mês: {FILTRO_MES}")
    log.info("=" * 55)

    vagas = run_check()

    if vagas:
        linhas = []
        for v in vagas:
            linhas.append(f"  • <b>{v['qtd']} vaga(s)</b> → {v['periodo']}")

        msg = (
            "🎉 <b>VAGA DISPONÍVEL NO SESC BERTIOGA!</b>\n\n"
            + "\n".join(linhas)
            + f"\n\n🔗 <a href='{RESERVAS_URL}'>Clique aqui para reservar agora</a>\n"
            f"⏰ Verificado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        telegram_send(msg)
        log.info(f"✅ {len(vagas)} período(s) com vagas encontrados!")
    else:
        log.info("❌ Nenhuma vaga disponível no momento.")
        # Silencioso quando não há vagas (não envia mensagem)


if __name__ == "__main__":
    main()
