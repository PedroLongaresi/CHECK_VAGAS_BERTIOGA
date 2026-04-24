#!/usr/bin/env python3
"""
Monitor de Vagas - SESC Bertioga - v5
Endpoints corretos: /periodo/ano/{ano}/mes/{mes}?tipo=COMPRA
SSO: login no portal → handshake no bertioga → JSESSIONID válido
"""

import os
import re
import logging
import requests
from datetime import datetime

# ── Configurações ────────────────────────────────────────────────────────────

PORTAL_LOGIN    = "https://portal.sescsp.org.br/meu-perfil/login.action"
PORTAL_REFERER  = "https://portal.sescsp.org.br/meu-perfil/bertioga/login?fromUrl=https://reservabertioga.sescsp.org.br/bertioga-web/"
# Página que faz o handshake SSO e gera JSESSIONID no domínio bertioga
BERTIOGA_HOME   = "https://reservabertioga.sescsp.org.br/bertioga-web/"
BERTIOGA_API    = "https://reservabertioga.sescsp.org.br/bertioga-web"

RESERVAS_URL    = "https://reservabertioga.sescsp.org.br/bertioga-web/#/reserva"

SESC_EMAIL  = os.environ["SESC_EMAIL"]
SESC_SENHA  = os.environ["SESC_PASSWORD"]
TG_TOKEN    = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID  = os.environ["TELEGRAM_CHAT_ID"]

FILTRO_MES  = os.environ.get("FILTRO_MES", "").lower()
FILTRO_ANO  = int(os.environ.get("FILTRO_ANO", "2026"))

# Meses para monitorar (1=jan ... 12=dez)
# Se FILTRO_MES definido, tenta casar com o nome; senão monitora todos
MESES_NOMES = {
    1:"janeiro",2:"fevereiro",3:"março",4:"abril",5:"maio",6:"junho",
    7:"julho",8:"agosto",9:"setembro",10:"outubro",11:"novembro",12:"dezembro"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)

# ── Telegram ─────────────────────────────────────────────────────────────────

def telegram_send(msg: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TG_CHAT_ID, "text": msg,
            "parse_mode": "HTML", "disable_web_page_preview": True
        }, timeout=15)
        log.info(f"Telegram: {r.status_code} - {r.text[:200]}")
        r.raise_for_status()
    except Exception as e:
        log.error(f"Falha Telegram: {e}")

# ── Autenticação SSO ──────────────────────────────────────────────────────────

def criar_sessao() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "user-agent": UA,
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8",
    })

    # 1. Login AJAX no portal
    log.info("Passo 1: Login AJAX no portal...")
    r = session.post(
        PORTAL_LOGIN,
        data={"email": SESC_EMAIL, "password": SESC_SENHA},
        headers={
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "referer": PORTAL_REFERER,
        },
        timeout=30,
    )
    log.info(f"Login status: {r.status_code} | body: {r.text[:200]}")
    if not r.ok or '"success":true' not in r.text:
        raise Exception(f"Login falhou: {r.text[:200]}")

    portal_cookies = dict(session.cookies)
    log.info(f"Cookies do portal: {list(portal_cookies.keys())}")

    # 2. Acessa o bertioga-web passando os cookies do portal
    # O bertioga valida a sessão via JSESSIONID do portal e cria sua própria sessão
    log.info("Passo 2: Handshake SSO com bertioga-web...")
    r2 = session.get(
        BERTIOGA_HOME,
        headers={"referer": PORTAL_REFERER},
        timeout=30,
        allow_redirects=True,
    )
    log.info(f"Bertioga home status: {r2.status_code} | URL final: {r2.url}")
    log.info(f"Cookies após handshake: {list(session.cookies.keys())}")

    # 3. Acessa o endpoint de usuário para confirmar sessão autenticada
    log.info("Passo 3: Verificando sessão no bertioga...")
    r3 = session.get(
        f"{BERTIOGA_API}/usuario",
        headers={"accept": "application/json, text/plain, */*",
                 "referer": BERTIOGA_HOME},
        timeout=20,
    )
    log.info(f"Usuario status: {r3.status_code} | body: {r3.text[:300]}")

    if r3.status_code == 401:
        # Sessão não transferida — tenta via URL de autenticação explícita do bertioga
        log.info("Sessão não transferida automaticamente. Tentando via /api/authenticate...")
        r4 = session.get(
            f"{BERTIOGA_API}/api/authenticate",
            headers={"accept": "application/json, text/plain, */*",
                     "referer": BERTIOGA_HOME},
            timeout=20,
        )
        log.info(f"Authenticate status: {r4.status_code} | body: {r4.text[:300]}")

    return session

# ── Busca de períodos ─────────────────────────────────────────────────────────

def buscar_periodos(session: requests.Session) -> list:
    vagas = []

    # Determina quais meses verificar
    mes_atual = datetime.now().month
    if FILTRO_MES:
        meses = [m for m, nome in MESES_NOMES.items() if FILTRO_MES in nome]
        if not meses:
            log.warning(f"Mês '{FILTRO_MES}' não reconhecido, verificando todos.")
            meses = list(range(mes_atual, 13))
    else:
        meses = list(range(mes_atual, 13))  # do mês atual até dezembro

    log.info(f"Verificando meses: {[MESES_NOMES[m] for m in meses]}")

    headers_api = {
        "accept": "application/json, text/plain, */*",
        "referer": BERTIOGA_HOME,
    }

    for mes in meses:
        for tipo in ("COMPRA", "SORTEIO"):
            url = f"{BERTIOGA_API}/periodo/ano/{FILTRO_ANO}/mes/{mes}?tipo={tipo}"
            log.info(f"GET {url}")
            try:
                r = session.get(url, headers=headers_api, timeout=20)
                log.info(f"  Status: {r.status_code} | body: {r.text[:400]}")

                if r.status_code != 200:
                    continue

                data = r.json()
                log.info(f"  JSON: {str(data)[:300]}")

                # Processa resposta — pode ser lista ou dict
                periodos = data if isinstance(data, list) else data.get("periodos") or data.get("data") or []

                for p in periodos:
                    if not isinstance(p, dict):
                        continue

                    # Campos possíveis para quantidade disponível
                    qtd = (
                        p.get("quantidadeDisponivel") or
                        p.get("vagasDisponiveis") or
                        p.get("vagas") or
                        p.get("disponivel") or
                        p.get("quantidade") or 0
                    )
                    try:
                        qtd = int(qtd)
                    except Exception:
                        qtd = 0

                    nome = (
                        p.get("descricao") or p.get("nome") or
                        p.get("titulo") or p.get("periodo") or
                        f"{MESES_NOMES[mes].capitalize()}/{FILTRO_ANO}"
                    )

                    log.info(f"  Período: {nome} | disponível: {qtd} | tipo: {tipo}")

                    if qtd > 0:
                        vagas.append({"qtd": qtd, "periodo": nome, "tipo": tipo})

            except Exception as e:
                log.warning(f"  Erro: {e}")

    return vagas

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 55)
    log.info("Monitor SESC Bertioga v5 iniciando...")
    log.info(f"Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    if FILTRO_MES:
        log.info(f"Filtro de mês: {FILTRO_MES}")
    log.info("=" * 55)

    try:
        session = criar_sessao()
        vagas = buscar_periodos(session)
    except Exception as e:
        log.error(f"Erro crítico: {e}")
        telegram_send(f"⚠️ <b>Monitor SESC</b>\nErro: {str(e)[:300]}")
        return

    if vagas:
        linhas = [
            f"  • <b>{v['qtd']} vaga(s)</b> [{v['tipo']}] → {v['periodo']}"
            for v in vagas
        ]
        msg = (
            "🎉 <b>VAGA DISPONÍVEL NO SESC BERTIOGA!</b>\n\n"
            + "\n".join(linhas)
            + f"\n\n🔗 {RESERVAS_URL}\n"
            f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        telegram_send(msg)
        log.info(f"✅ {len(vagas)} período(s) com vagas!")
    else:
        log.info("❌ Nenhuma vaga disponível no momento.")


if __name__ == "__main__":
    main()