# 🔐 GitHub Secrets - SESC Bertioga Monitor

## Como adicionar os Secrets no GitHub

Acesse: `Configurações do Repositório → Secrets and variables → Actions → New repository secret`

---

## Secrets a adicionar (um por um):

### 1️⃣ SESC_EMAIL
```
pedrolongaresi@hotmail.com
```

### 2️⃣ SESC_PASSWORD
```
sua senha do SESC
```

### 3️⃣ TELEGRAM_TOKEN
```
token do seu bot
```

### 4️⃣ TELEGRAM_CHAT_ID
```
seu chat ID do Telegram
```

---

## Formato de Arquivo .env (uso local)
Se quiser testar localmente, crie um arquivo `.env`:

```env
SESC_EMAIL=pedrolongaresi@hotmail.com
SESC_PASSWORD=sua senha do SESC
TELEGRAM_TOKEN=token do seu bot
TELEGRAM_CHAT_ID=seu chat ID do Telegram
```

---

## ✅ Checklist de Configuração

- [ ] Adicionar `SESC_EMAIL` no GitHub Secrets
- [ ] Adicionar `SESC_PASSWORD` no GitHub Secrets
- [ ] Adicionar `TELEGRAM_TOKEN` no GitHub Secrets
- [ ] Adicionar `TELEGRAM_CHAT_ID` no GitHub Secrets
- [ ] Testar o webhook do GitHub Actions manualmente

