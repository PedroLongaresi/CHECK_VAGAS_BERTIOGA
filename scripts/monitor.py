#!/usr/bin/env python3
"""
Monitor de Vagas - SESC Bertioga - v7
Fix: campos vazios enviados como null no authenticate
"""

import os
import json
import logging
import requests
from datetime import datetime

PORTAL_LOGIN   = "https://portal.sescsp.org.br/meu-perfil/login.action"
PORTAL_REFERER = "https://portal.sescsp.org.br/meu-perfil/bertioga/login?fromUrl=https://reservabertioga.sescsp.org.br/bertioga-web/"
BERTIOGA       = "https://reservabertioga.sescsp.org.br/bertioga-web"
BERTIOGA_HOME  = f"{BERTIOGA}/"
RESERVAS_URL   = f"{BERTIOGA}/#/reserva"

SESC_EMAIL = os.environ["SESC_EMAIL"]
SESC_SENHA = os.environ["SESC_PASSWORD"]
TG_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

FILTRO_MES = os.environ.get("FILTRO_MES", "").lower()
FILTRO_ANO = int(os.environ.get("FILTRO_ANO", "2026"))

MESES_NOMES = {
    1:"janeiro",2:"fevereiro",3:"março",4:"abril",5:"maio",6:"junho",
    7:"julho",8:"agosto",9:"setembro",10:"outubro",11:"novembro",12:"dezembro"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

def telegram_send(msg: str):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
        log.info(f"Telegram: {r.status_code} - {r.text[:200]}")
        r.raise_for_status()
    except Exception as e:
        log.error(f"Falha Telegram: {e}")

def null_if_empty(v):
    """Converte string vazia em None (será serializado como null no JSON)."""
    if v is None or str(v).strip() == "":
        return None
    return v

def criar_sessao() -> requests.Session:
    session = requests.Session()
    session.headers.update({"user-agent": UA, "accept-language": "pt-BR,pt;q=0.9"})

    # Passo 1: Login no portal
    log.info("Passo 1: Login no portal SESC...")
    r1 = session.post(
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
    log.info(f"Login: {r1.status_code} | {r1.text[:200]}")
    dados = r1.json()
    if not dados.get("success"):
        raise Exception(f"Login rejeitado: {r1.text[:200]}")

    # Passo 2: POST authenticate no bertioga
    # Campos vazios/None devem ir como null — o Java valida o formato de nascimento
    log.info("Passo 2: Authenticate no bertioga...")
    payload_auth = {
        "success":         True,
        "id":              str(dados.get("id", "")),
        "nome":            null_if_empty(dados.get("name")),
        "apelido":         null_if_empty(dados.get("nickname")),
        "email":           SESC_EMAIL,
        "matriculado":     None,
        "numeroMatricula": None,
        "cpf":             None,
        "nascimento":      None,   # ← era "" antes, causava o 500
        "genero":          None,
        "pais":            None,
        "estado":          None,
        "cidade":          None,
    }
    log.info(f"Payload: {json.dumps(payload_auth)}")

    r2 = session.post(
        f"{BERTIOGA}/usuario/meu-perfil/authenticate",
        json=payload_auth,
        headers={
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "referer": BERTIOGA_HOME,
        },
        timeout=30,
    )
    log.info(f"Authenticate: {r2.status_code} | {r2.text[:400]}")
    log.info(f"Cookies: { {c.name: c.value[:25] for c in session.cookies} }")

    if r2.status_code not in (200, 201):
        raise Exception(f"Authenticate HTTP {r2.status_code}: {r2.text[:300]}")

    # Passo 3: Confirma sessão
    log.info("Passo 3: Confirmando sessão...")
    r3 = session.get(
        f"{BERTIOGA}/usuario",
        headers={"accept": "application/json, text/plain, */*", "referer": BERTIOGA_HOME},
        timeout=20,
    )
    log.info(f"Usuario: {r3.status_code} | {r3.text[:300]}")
    if r3.status_code == 401:
        raise Exception("Sessão 401 após authenticate.")

    log.info("✅ Sessão autenticada com sucesso!")
    return session

def buscar_periodos(session: requests.Session) -> list:
    vagas = []
    mes_atual = datetime.now().month

    if FILTRO_MES:
        meses = [m for m, nome in MESES_NOMES.items() if FILTRO_MES in nome]
        if not meses:
            meses = list(range(mes_atual, 13))
    else:
        meses = list(range(mes_atual, 13))

    log.info(f"Verificando: {[MESES_NOMES[m] for m in meses]} / {FILTRO_ANO}")
    headers_api = {"accept": "application/json, text/plain, */*", "referer": BERTIOGA_HOME}

    for mes in meses:
        for tipo in ("COMPRA", "SORTEIO"):
            url = f"{BERTIOGA}/periodo/ano/{FILTRO_ANO}/mes/{mes}?tipo={tipo}"
            log.info(f"GET {url}")
            try:
                r = session.get(url, headers=headers_api, timeout=20)
                log.info(f"  {r.status_code} | {r.text[:500]}")
                if r.status_code != 200:
                    continue
                data = r.json()
                periodos = data if isinstance(data, list) else (data.get("periodos") or data.get("data") or [])
                for p in periodos:
                    if not isinstance(p, dict):
                        continue
                    qtd = int(p.get("quantidadeDisponivel") or p.get("vagasDisponiveis") or
                              p.get("vagas") or p.get("disponivel") or p.get("quantidade") or 0)
                    nome = p.get("descricao") or p.get("nome") or p.get("titulo") or f"{MESES_NOMES[mes].capitalize()}/{FILTRO_ANO}"
                    log.info(f"  → {nome} | qtd: {qtd} | tipo: {tipo}")
                    if qtd > 0:
                        vagas.append({"qtd": qtd, "periodo": nome, "tipo": tipo})
            except Exception as e:
                log.warning(f"  Erro: {e}")
    return vagas

def main():
    log.info("=" * 55)
    log.info("Monitor SESC Bertioga v7 iniciando...")
    log.info(f"Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    log.info(f"TELEGRAM_CHAT_ID configurado: '{TG_CHAT_ID}'")
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
        linhas = [f"  • <b>{v['qtd']} vaga(s)</b> [{v['tipo']}] → {v['periodo']}" for v in vagas]
        msg = (
            "🎉 <b>VAGA DISPONÍVEL NO SESC BERTIOGA!</b>\n\n"
            + "\n".join(linhas)
            + f"\n\n🔗 {RESERVAS_URL}\n⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        telegram_send(msg)
        log.info(f"✅ {len(vagas)} período(s) com vagas!")
    else:
        msg = (
            "ℹ️ <b>STATUS DE VAGAS SESC BERTIOGA</b>\n\n"
            "Nenhuma vaga disponível no momento.\n\n"
            f"🔗 {RESERVAS_URL}\n⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        telegram_send(msg)
        log.info("❌ Nenhuma vaga disponível no momento. Notificação enviada.")

if __name__ == "__main__":
    main()