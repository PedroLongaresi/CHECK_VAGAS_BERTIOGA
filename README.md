# 🏖️ Monitor de Vagas – SESC Bertioga

Monitora automaticamente vagas de hospedagem no SESC Bertioga e envia alertas pelo **Telegram** quando houver disponibilidade.

Roda de graça no **GitHub Actions** a cada 15 minutos.

---

## 📁 Estrutura

```
sesc-monitor/
├── .github/
│   └── workflows/
│       └── monitor.yml       ← Agendamento automático (GitHub Actions)
├── scripts/
│   └── monitor.py            ← Script principal de monitoramento
├── requirements.txt
└── README.md
```

---

## 🚀 Como configurar (passo a passo)

### 1️⃣ Criar bot no Telegram

1. Abra o Telegram e busque por **@BotFather**
2. Envie `/newbot` e siga as instruções
3. Anote o **token** gerado (ex: `7123456789:AAFxxx...`)
4. Inicie uma conversa com seu bot (clique em "Start")
5. Acesse essa URL para pegar seu `chat_id`:
   ```
   https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
   ```
   Procure pelo campo `"id"` dentro de `"chat"` – esse é o seu `TELEGRAM_CHAT_ID`.

---

### 2️⃣ Criar repositório no GitHub

1. Acesse [github.com](https://github.com) → **New repository**
2. Nome sugerido: `sesc-monitor`
3. Marque como **Private** (recomendado, pois terá suas credenciais)
4. Clique em **Create repository**

---

### 3️⃣ Enviar os arquivos

No terminal (Windows: use Git Bash ou PowerShell):

```bash
git init
git add .
git commit -m "Monitor SESC Bertioga"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/sesc-monitor.git
git push -u origin main
```

---

### 4️⃣ Configurar os Secrets no GitHub

No repositório → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Nome               | Valor                          |
|--------------------|--------------------------------|
| `SESC_EMAIL`       | pedrolongaresi@hotmail.com     |
| `SESC_PASSWORD`    | sua senha do SESC              |
| `TELEGRAM_TOKEN`   | token do seu bot               |
| `TELEGRAM_CHAT_ID` | seu chat ID do Telegram        |

---

### 5️⃣ (Opcional) Filtrar por mês

Em **Settings** → **Secrets and variables** → **Actions** → aba **Variables** → **New repository variable**

| Nome         | Valor exemplo |
|--------------|---------------|
| `FILTRO_MES` | `julho`       |

Deixe em branco para monitorar todos os meses.

---

### 6️⃣ Ativar e testar

1. Vá em **Actions** no repositório
2. Clique no workflow **Monitor SESC Bertioga**
3. Clique em **Run workflow** para testar manualmente
4. Veja os logs – se tudo certo, você receberá mensagem no Telegram quando houver vaga!

---

## ⏰ Horário de funcionamento

O monitor roda **a cada 15 minutos das 7h às 23h45 (horário de Brasília)**.
Fora desse horário fica pausado para economizar os minutos gratuitos do GitHub Actions.

O plano gratuito do GitHub oferece **2.000 minutos/mês** – mais do que suficiente.

---

## 📬 Exemplo de notificação

```
🎉 VAGA DISPONÍVEL NO SESC BERTIOGA!

  • 3 vaga(s) → Julho 2026 | Chalé Standard

🔗 Clique aqui para reservar agora
⏰ Verificado em: 23/04/2026 14:30
```

Quando **não há vagas**, o script fica silencioso (não envia mensagem).

---

## 🛠️ Rodando localmente (opcional)

```bash
pip install playwright requests
playwright install chromium

export SESC_EMAIL="seu@email.com"
export SESC_PASSWORD="sua_senha"
export TELEGRAM_TOKEN="seu_token"
export TELEGRAM_CHAT_ID="seu_chat_id"

python scripts/monitor.py
```
