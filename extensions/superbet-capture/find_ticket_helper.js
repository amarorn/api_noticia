/**
 * Helper para encontrar seletores DOM da Superbet.
 * Cole isso no Console do DevTools (F12) na página Minhas Apostas.
 */
(function findTicketSelectors() {
  const card = document.querySelector('[class*="ticket"], [class*="aposta"], [class*="bet"]');
  if (!card) {
    console.warn("Nenhum card de aposta encontrado. Certifique-se de estar na página 'Minhas Apostas'.");
    return;
  }

  // 1. Tentar encontrar ticket code por texto
  const text = card.innerText || card.textContent || "";
  const ticketMatch = text.match(/([A-Z0-9]{3,}-?[A-Z0-9]{5,})/);
  if (ticketMatch) {
    console.log("✅ Ticket code encontrado no texto:", ticketMatch[1]);
  } else {
    console.warn("⚠️ Ticket code não encontrado no texto visível do card.");
  }

  // 2. Tentar encontrar por data-atributos
  const elWithData = card.querySelector('[class*="id"], [class*="code"], [class*="ticket"]');
  if (elWithData) {
    console.log("🔍 Elemento candidato:", elWithData);
    console.log("   Seletor:", elWithData.className);
    console.log("   Texto:", elWithData.innerText?.slice(0, 50));
  }

  // 3. Listar todos os elementos filhos com seus textos (para análise)
  console.log("\n📋 Elementos filhos do card:");
  const children = card.querySelectorAll("*");
  children.forEach((child, i) => {
    const txt = (child.innerText || child.textContent || "").trim();
    if (txt.length > 2 && txt.length < 100) {
      console.log(`  [${i}] ${child.tagName} class="${child.className?.slice(0, 60)}" → "${txt.slice(0, 60)}"`);
    }
  });

  console.log("\n💡 Dica: procure a linha que contém algo como '892P-1YINSZ' e me envie o seletor (className) dela.");
})();
