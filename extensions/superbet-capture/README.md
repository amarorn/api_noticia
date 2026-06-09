# Bolão AI — Extensão Captura Superbet

> Extraia suas apostas abertas da Superbet automaticamente para o painel **Ao Vivo** do Bolão AI.

## Como funciona

1. Você abre a página **Minhas Apostas** da Superbet (https://www.superbet.com/br/apostas/).
2. Clica no ícone da extensão no canto do navegador.
3. A extensão escaneia os cards de aposta visíveis na página, extrai:
   - Nome do evento
   - Ticket code (ex: `892P-1YINSZ`)
   - Mercado e palpite
   - Stake e odd total
   - Ganho potencial
   - Cash-out disponível (se visível)
4. Envia tudo para a API local (`http://127.0.0.1:8000/user/open-bets`).
5. As apostas aparecem automaticamente na tela `/ao-vivo/:eventId` do Bolão AI.

## Instalação (Chrome/Edge)

1. **Gere os ícones** (ou copie placeholders):
   ```bash
   cd extensions/superbet-capture
   # Substitua por ícones reais (16x16, 48x48, 128x128 PNG)
   touch icon16.png icon48.png icon128.png
   ```

2. **Abra o Chrome** e vá em: `chrome://extensions/`

3. **Ative o modo desenvolvedor** (toggle no canto superior direito).

4. **Clique em "Carregar sem compactação"** e selecione a pasta `extensions/superbet-capture`.

5. **Pronto!** A extensão aparece no canto do navegador.

## Uso

1. Acesse **Minhas Apostas** na Superbet.
2. Clique no ícone da extensão.
3. Cole sua **API Key** do Bolão AI (apenas na primeira vez — ela fica salva).
4. Clique em **"Capturar apostas abertas"**.
5. As apostas são enviadas e aparecem no painel ao vivo.

## Fallback: Script de clipboard

Se a extensão não funcionar (mudança de DOM da Superbet), use o script Python:

```bash
cd api_noticia
source .venv/bin/activate

# 1. Copie o texto do card da aposta na Superbet (Ctrl+C)
# 2. Rode:
python3 scripts/capture_superbet.py --api-key SUA_CHAVE
```

## Se der erro "Não foi possível acessar a página"

Isso acontece quando o `content_script` não conseguiu injetar na aba. Causas comuns:

1. **A URL da Superbet mudou** — o `matches` do `manifest.json` não cobria a página atual.
2. **A página foi aberta antes da extensão** — o content só injeta em páginas recém-carregadas.

### Correção (obrigatória após atualização do manifest)

1. Vá em `chrome://extensions/`
2. Clique no ícone de **refresh** (seta circular) na extensão Bolão AI — isso recarrega o manifest com os novos matches
3. **Atualize a página da Superbet** (F5)
4. Aguarde 2–3 segundos para o content_script injetar
5. Tente capturar novamente

### Fallback: Console do DevTools (se a extensão continuar falhando)

1. Na página **Minhas Apostas** aberta, aperte **F12**
2. Vá na aba **Console**
3. Cole o seguinte código e aperte Enter:

```javascript
(function() {
  const cards = Array.from(document.querySelectorAll('div')).filter(div => {
    const t = div.innerText || '';
    return t.includes('APOSTA') && (t.includes('AO VIVO') || t.includes('ÚNICO') || t.includes('Cashout'));
  });
  const bets = cards.map(div => {
    const text = div.innerText;
    const lines = text.split('\n').filter(Boolean);
    let event = '';
    for (const l of lines) {
      if (l.includes('·') || l.includes('—') || l.includes(' - ')) { event = l; break; }
    }
    const ticketM = text.match(/([A-Z0-9]{3,}-[A-Z0-9]{5,})/);
    const stakeM = text.match(/APOSTA\s*([\d.,\s]+)/i);
    const oddM = text.match(/ODDS\s*TOTAIS\s*([\d.,]+)/i);
    const cashM = text.match(/Cashout\s+([\d.,]+)/i);
    return {
      event_name: event,
      ticket_code: ticketM ? ticketM[1] : null,
      stake: stakeM ? parseFloat(stakeM[1].replace('.','').replace(',','.')) : 0,
      odds_placed: oddM ? parseFloat(oddM[1].replace(',','.')) : 0,
      cashout_value: cashM ? parseFloat(cashM[1].replace('.','').replace(',','.')) : null,
      raw: lines.slice(0, 8).join(' | ')
    };
  }).filter(b => b.stake > 0);
  console.table(bets);
  copy(JSON.stringify(bets, null, 2));
  console.log('✅ JSON copiado! Cole no script: python3 scripts/capture_superbet.py --paste');
})();
```

4. O JSON é copiado automaticamente para a área de transferência.
5. Salve num arquivo (`/tmp/bets.json`) e importe via API, ou use o script Python `capture_superbet.py --paste`.

---

## Estrutura

| Arquivo | Função |
|---------|--------|
| `manifest.json` | Configuração da extensão (MV3) |
| `content_script.js` | Escaneia o DOM da Superbet e extrai dados |
| `background.js` | Service worker — comunicação com a API |
| `popup.html` + `popup.js` | Interface do ícone da extensão |
| `superbet_parser.py` | Parser Python (fallback/CLI) |
| `scripts/capture_superbet.py` | Script CLI (clipboard) |
| `scripts/fetch_cashout.py` | Atualiza cash-out dos tickets |

## Notas

- A extensão usa **seletores heurísticos** no DOM. Se a Superbet mudar o layout, a captura pode falhar. Nesse caso, use o **script de clipboard** como fallback.
- O `ticket_code` é extraído do texto visível no card. Sem ticket, não é possível consultar cash-out automaticamente.
- A API deve estar rodando localmente (`uvicorn api.main:app --port 8000`).
