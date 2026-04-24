#!/usr/bin/env python3
"""
Monitor de Vagas - SESC Bertioga - v4
Login via AJAX direto (sem browser), muito mais leve e confiável.
"""

import os
import re
import logging
import requests
from datetime import datetime

# ── Configurações ────────────────────────────────────────────────────────────

LOGIN_ACTION = "https://portal.sescsp.org.br/meu-perfil/login.action"
LOGIN_REFERER = "https://portal.sescsp.org.br/meu-perfil/bertioga/login?fromUrl=https://reservabertioga.sescsp.org.br/bertioga-web/"
RESERVAS_URL  = "https://reservabertioga.sescsp.org.br/bertioga-web/#/reserva"

# URL da API de períodos (SPA Angular carrega isso em background)
API_PERIODOS = "https://reservabertioga.sescsp.org.br/bertioga-web/rest/periodos"
API_BASE     = "https://reservabertioga.sescsp.org.br/bertioga-web/rest"

SESC_EMAIL  = os.environ["SESC_EMAIL"]
SESC_SENHA  = os.environ["SESC_PASSWORD"]
TG_TOKEN    = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID  = os.environ["TELEGRAM_CHAT_ID"]

FILTRO_MES  = os.environ.get("FILTRO_MES", "").lower()
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
    payload = {"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=15)
        log.info(f"Telegram: {r.status_code} - {r.text[:300]}")
        r.raise_for_status()
    except Exception as e:
        log.error(f"Falha Telegram: {e}")

# ── Sessão autenticada ────────────────────────────────────────────────────────

def criar_sessao() -> requests.Session:
    session = requests.Session()

    headers_login = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
        "referer": LOGIN_REFERER,
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        ),
    }

    log.info("Fazendo login via AJAX...")
    r = session.post(
        LOGIN_ACTION,
        data={"email": SESC_EMAIL, "password": SESC_SENHA},
        headers=headers_login,
        timeout=30,
    )
    log.info(f"Login response: {r.status_code}")
    log.info(f"Login body: {r.text[:400]}")

    if r.status_code != 200:
        raise Exception(f"Login falhou com status {r.status_code}: {r.text[:200]}")

    # Verifica se autenticou — a resposta costuma ter um JSON com sucesso ou redirect
    body = r.text.lower()
    if "senha" in body and "incorret" in body:
        raise Exception("Login falhou — senha incorreta.")
    if "erro" in body and "login" in body:
        raise Exception(f"Login falhou: {r.text[:200]}")

    log.info("Login realizado! Cookies obtidos:")
    for c in session.cookies:
        log.info(f"  {c.name} = {c.value[:30]}...")

    return session

# ── Busca vagas via API ───────────────────────────────────────────────────────

def buscar_vagas(session: requests.Session) -> list:
    vagas = []

    headers_api = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "pt-BR,pt;q=0.9",
        "referer": RESERVAS_URL,
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        ),
    }

    # Tenta buscar a lista de períodos/reservas disponíveis
    endpoints_tentar = [
        f"{API_BASE}/periodos",
        f"{API_BASE}/periodos/disponiveis",
        f"{API_BASE}/reservas/periodos",
        f"{API_BASE}/hospedagem/periodos",
        f"{API_BASE}/distribuicao",
    ]

    for endpoint in endpoints_tentar:
        log.info(f"Tentando endpoint: {endpoint}")
        try:
            r = session.get(endpoint, headers=headers_api, timeout=20)
            log.info(f"  Status: {r.status_code} | Content-Type: {r.headers.get('content-type','')}")
            if r.status_code == 200:
                log.info(f"  Body: {r.text[:500]}")
                try:
                    data = r.json()
                    vagas = processar_json(data)
                    if vagas is not None:
                        log.info(f"  ✅ Endpoint funcionou! {len(vagas)} vaga(s) encontrada(s).")
                        return vagas
                except Exception as e:
                    log.info(f"  Não é JSON válido: {e}")
        except Exception as e:
            log.warning(f"  Erro: {e}")

    log.warning("Nenhum endpoint de API funcionou — veja os logs acima para descobrir a URL correta.")
    return []


def processar_json(data) -> list | None:
    """
    Tenta extrair vagas disponíveis do JSON retornado pela API.
    Retorna lista de vagas ou None se o formato não for reconhecido.
    """
    vagas = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                qtd = (
                    item.get("quantidadeDisponivel")
                    or item.get("vagas")
                    or item.get("disponivel")
                    or item.get("quantidade")
                    or 0
                )
                try:
                    qtd = int(qtd)
                except Exception:
                    qtd = 0

                if qtd > 0:
                    periodo = (
                        item.get("descricao")
                        or item.get("periodo")
                        or item.get("nome")
                        or str(item)[:80]
                    )
                    if FILTRO_MES and FILTRO_MES not in periodo.lower():
                        continue
                    vagas.append({"qtd": qtd, "periodo": periodo})
        return vagas

    if isinstance(data, dict):
        # Tenta chaves comuns
        for chave in ("periodos", "reservas", "itens", "data", "result", "results"):
            if chave in data and isinstance(data[chave], list):
                return processar_json(data[chave])

    return None  # formato desconhecido


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 55)
    log.info("Monitor SESC Bertioga v4 (API direta) iniciando...")
    log.info(f"Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    if FILTRO_MES:
        log.info(f"Filtro de mês: {FILTRO_MES}")
    log.info("=" * 55)

    try:
        session = criar_sessao()
        vagas = buscar_vagas(session)
    except Exception as e:
        log.error(f"Erro crítico: {e}")
        telegram_send(f"⚠️ <b>Monitor SESC</b>\nErro: {str(e)[:300]}")
        return

    if vagas:
        linhas = [f"  • <b>{v['qtd']} vaga(s)</b> → {v['periodo']}" for v in vagas]
        msg = (
            "🎉 <b>VAGA DISPONÍVEL NO SESC BERTIOGA!</b>\n\n"
            + "\n".join(linhas)
            + f"\n\n🔗 {RESERVAS_URL}\n"
            f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        telegram_send(msg)
        log.info(f"✅ {len(vagas)} período(s) com vagas!")
    else:
        log.info("❌ Nenhuma vaga disponível (ou API ainda não mapeada — veja logs).")


if __name__ == "__main__":
    main()