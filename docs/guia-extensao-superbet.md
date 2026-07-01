# Guia de Instalação — Extensão Bolão AI Captura Superbet

## 📥 Instalação (Chrome/Edge)

### 1. Abrir Chrome Extensions

```
chrome://extensions/
```

### 2. Ativar Modo Desenvolvedor

No canto **superior direito**, ative o toggle **"Modo do desenvolvedor"**.

### 3. Carregar Extensão

Clique em **"Carregar sem compactação"** (Load unpacked) e selecione a pasta:

```
/Users/amaro/Documents/Cactus/api_noticia/extensions/superbet-capture
```

### 4. Verificar Instalação

A extensão **"Bolão AI — Captura Superbet"** deve aparecer na lista com:
- ✅ Ícone verde
- ✅ Versão 1.7.0
- ✅ ID da extensão

---

## 🔧 Configuração Inicial

### 1. Abrir Popup da Extensão

Clique no **ícone da extensão** no canto do navegador (próximo à barra de endereço).

### 2. Inserir API Key

No popup, cole sua **API Key** do Bolão AI:

```
API Key: [sua-chave-aqui]
Usuário carteira: jamarorn
```

> A API Key é salva automaticamente no `chrome.storage.local`.

### 3. Testar Conexão

Clique em **"Testar conexão com API"** — deve aparecer:

```
✅ API online — modelo WC pronto
```

---

## 🎯 Como Capturar Apostas

### Passo 1: Abrir Minhas Apostas na Superbet

Acesse: https://www.superbet.com/br/apostas/

### Passo 2: Clicar no Ícone da Extensão

O popup mostra:

```
┌─────────────────────────────┐
│  Bolão AI — Captura Superbet │
├─────────────────────────────┤
│  API: ✅ Conectado           │
│  Apostas detectadas: 3       │
├─────────────────────────────┤
│  [Capturar apostas abertas]  │
└─────────────────────────────┘
```

### Passo 3: Capturar

Clique em **"Capturar apostas abertas"**. A extensão:

1. Faz scroll automático para carregar todos os cards
2. Extrai dados de cada aposta (evento, mercado, stake, odd, cashout)
3. Envia para `POST /user/open-bets` na API
4. Mostra notificação: **"3/3 apostas enviadas"**

---

## 📊 Como Usar os Bilhetes Otimizados

### 1. Abrir Painel Ao Vivo

No frontend React (http://localhost:5173), acesse:

```
/ao-vivo/11511115
```

### 2. Tab "Palpites"

Role até a seção **"Bilhetes Otimizados"**:

```
┌─────────────────────────────────────────────────────────┐
│  ⚡ Bilhetes Otimizados [5]                              │
├─────────────────────────────────────────────────────────┤
│  [TEMPO TOTAL] 5 bilhete(s)                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │  4 pernas · Odd 13.19 · EV +265.8% · Prob 19.1% │   │
│  │  ─────────────────────────────────────────────────  │   │
│  │  FORTE  · Marrocos -0.5 · 93% @2.00 · EV +86.4% │   │
│  │  VALOR  · Próximo gol Marrocos · 71% @1.90 · +34%│   │
│  │  VALOR  · Over 2.5 · 59% @2.17 · EV +27.8%       │   │
│  │  VALOR  · Ambos não marcam · 72% @1.60 · +14.6% │   │
│  │  ─────────────────────────────────────────────────  │   │
│  │  💰 Stake R$ 5.00 · Retorno R$ 65.95             │   │
│  │  [Enviar à Superbet] ← CLICA AQUI!               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3. Enviar à Superbet

Clique em **"Enviar à Superbet"**. A extensão:

1. Recebe o bilhete via `postMessage` (frontend_bridge.js)
2. Abre uma nova aba com o evento na Superbet
3. Clica automaticamente nos mercados (ticket_builder.js)
4. Preenche o stake no betslip
5. **Você só confirma a aposta!**

---

## 🔄 Fluxo Completo Visual

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. VOCÊ NA SUPERBET                                                         │
│     superbet.com/br/apostas/                                                │
│     ├─ Aposta 1: Brasil vence · R$ 50 · Odd 2.80                             │
│     └─ Aposta 2: Over 2.5 · R$ 30 · Odd 2.10                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. EXTENSÃO CHROME (content_script.js)                                      │
│     ├─ Detecta cards no DOM                                                 │
│     ├─ Extrai: evento, mercado, stake, odd, cashout                        │
│     └─ Envia POST /user/open-bets                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. BACKEND FASTAPI (localhost:8000)                                         │
│     ├─ Recebe aposta em user_open_bets.json                                  │
│     ├─ Valida guardrails (duplicação, limites)                             │
│     └─ Retorna confirmação                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. PAINEL BOLÃO AI (localhost:5173)                                        │
│     Tab "Minha Aposta":                                                      │
│     ├─ Aposta 1: Brasil vence · R$ 50 · Odd 2.80 · Cashout R$ 35.50        │
│     │   Modelo: 58% · Mercado: 35% · EV: +65% · [Cash-out]                 │
│     └─ Aposta 2: Over 2.5 · R$ 30 · Odd 2.10 · [Manter]                     │
│                                                                             │
│     Tab "Palpites" → Bilhetes Otimizados:                                    │
│     ├─ Bilhete FT: Marrocos -0.5 + Over 2.5 + BTTS · Odd 8.33 · EV +213%   │
│     └─ [Enviar à Superbet] ← CLIQUE AQUI                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. EXTENSÃO MONTA BILHETE NA SUPERBET                                       │
│     ├─ Abre aba superbet.com/br/evento/11511115                              │
│     ├─ Clica em "Marrocos -0.5" (odd 2.00)                                 │
│     ├─ Clica em "Over 2.5" (odd 2.17)                                      │
│     ├─ Clica em "Ambos não marcam" (odd 1.60)                              │
│     ├─ Preenche stake: R$ 5.00                                              │
│     └─ ✅ Bilhete montado! Você só confirma.                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Troubleshooting

### "Extensão não respondeu"

1. Recarregue a extensão em `chrome://extensions/`
2. Recarregue a página da Superbet (F5)
3. Tente novamente

### "Não foi possível acessar a página"

1. Verifique se a URL está em `host_permissions` do `manifest.json`
2. A Superbet mudou de domínio? Atualize o manifest.

### "API offline"

1. Verifique se a API está rodando: `uvicorn api.main:app --reload`
2. Verifique se a API Key está correta
3. Teste: `curl http://localhost:8000/health/live`

### Fallback: Script Python

Se a extensão falhar, use o script de clipboard:

```bash
cd /Users/amaro/Documents/Cactus/api_noticia
source .venv/bin/activate
python scripts/capture_superbet.py --api-key SUA_CHAVE
```

---

## 📋 Checklist de Instalação

- [ ] Extensão carregada em `chrome://extensions/`
- [ ] Modo desenvolvedor ativado
- [ ] API Key configurada no popup
- [ ] Conexão com API testada (✅)
- [ ] Página "Minhas Apostas" da Superbet aberta
- [ ] Captura de apostas testada
- [ ] Painel Ao Vivo do Bolão AI acessível
- [ ] Bilhete otimizado enviado à Superbet

---

## 🎉 Pronto!

Agora você pode:
1. ✅ Capturar apostas automaticamente da Superbet
2. ✅ Monitorar cash-out em tempo real
3. ✅ Receber bilhetes otimizados pelo modelo
4. ✅ Montar bilhetes na Superbet com 1 clique
