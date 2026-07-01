/**
 * Teste de navegação SPA pela sidebar (sem F5).
 * Uso: node scripts/test-sidebar-nav.mjs
 */
import { chromium } from "playwright";

const BASE = process.env.APP_URL ?? "http://localhost:5173";

const ROUTES = [
  { label: "Dashboard", path: "/", heading: /dashboard|bolão|palpite/i },
  { label: "Jogos", path: "/jogos", heading: /jogos|calendário|agenda/i },
  { label: "Amistosos", path: "/amistosos", heading: /amistoso/i },
  { label: "Ao vivo", path: "/ao-vivo", heading: /ao vivo|live/i },
  { label: "Carteira", path: "/carteira", heading: /carteira/i },
  { label: "Notícias", path: "/noticias", heading: /notícia|feed/i },
];

async function mainContentVisible(page) {
  const main = page.locator("#main-content");
  await main.waitFor({ state: "attached", timeout: 8000 });
  const box = await main.boundingBox();
  if (!box || box.height < 40) return false;
  const opacity = await main.evaluate((el) => {
    const style = window.getComputedStyle(el.closest("[class]") ?? el);
    let node = el.parentElement;
    while (node) {
      const o = parseFloat(window.getComputedStyle(node).opacity);
      if (o < 0.05) return o;
      node = node.parentElement;
    }
    return parseFloat(style.opacity);
  });
  const text = (await main.innerText()).trim();
  return opacity > 0.05 && text.length > 20;
}

async function clickSidebar(page, label) {
  const link = page.locator("aside nav").getByRole("link", { name: label, exact: true });
  await link.waitFor({ state: "visible", timeout: 5000 });
  await link.click();
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await context.newPage();
  const failures = [];

  try {
    await page.goto(`${BASE}/jogos`, { waitUntil: "networkidle", timeout: 20000 });
    await page.waitForTimeout(600);

    if (!(await mainContentVisible(page))) {
      failures.push({ step: "initial /jogos", error: "conteúdo invisível ou vazio" });
    }

    // Reproduz bug do usuário: scroll longe no Jogos → clique sidebar → deve ver topo da nova página
    const mainScroll = page.locator("#main-scroll");
    await mainScroll.evaluate((el) => {
      el.scrollTop = 1200;
    });
    await clickSidebar(page, "Carteira");
    await page.waitForURL("**/carteira**", { timeout: 8000 });
    await page.waitForTimeout(400);
    const scrollTop = await mainScroll.evaluate((el) => el.scrollTop);
    const carteiraVisible = await mainContentVisible(page);
    if (scrollTop > 80) {
      failures.push({
        step: "scroll após Jogos→Carteira",
        error: `scroll preso em ${scrollTop}px`,
      });
    }
    console.log(
      `${scrollTop <= 80 && carteiraVisible ? "✓" : "✗"} Jogos(scroll) → Carteira scrollTop=${scrollTop}`,
    );

    // Volta para Jogos para continuar suite
    await clickSidebar(page, "Jogos");
    await page.waitForURL("**/jogos**", { timeout: 8000 });
    await page.waitForTimeout(300);

    for (const route of ROUTES) {
      try {
        await clickSidebar(page, route.label);
        await page.waitForURL(`**${route.path === "/" ? "/" : route.path}**`, { timeout: 8000 });
        await page.waitForTimeout(450);

        const url = new URL(page.url());
        const pathOk =
          route.path === "/"
            ? url.pathname === "/"
            : url.pathname === route.path || url.pathname.startsWith(route.path);

        const visible = await mainContentVisible(page);
        const hasHeading = await page
          .locator("h1, h2")
          .filter({ hasText: route.heading })
          .first()
          .isVisible()
          .catch(() => false);

        if (!pathOk) {
          failures.push({ step: route.label, error: `URL errada: ${url.pathname}` });
        } else if (!visible) {
          failures.push({ step: route.label, error: "página em branco / opacity 0" });
        } else if (!hasHeading) {
          // heading opcional — só aviso
          console.log(`  ⚠ ${route.label}: conteúdo ok, heading não encontrado`);
        }

        console.log(
          `${pathOk && visible ? "✓" : "✗"} ${route.label} → ${url.pathname} (visible=${visible})`,
        );
      } catch (err) {
        failures.push({ step: route.label, error: String(err) });
        console.log(`✗ ${route.label} → ${String(err)}`);
      }
    }

    // Volta para Jogos (reproduz fluxo do usuário)
    await clickSidebar(page, "Jogos");
    await page.waitForURL("**/jogos**", { timeout: 8000 });
    await page.waitForTimeout(400);
    const backOk = (await mainContentVisible(page)) && page.url().includes("/jogos");
    console.log(`${backOk ? "✓" : "✗"} Retorno Jogos (visible=${backOk})`);
    if (!backOk) failures.push({ step: "retorno Jogos", error: "conteúdo não apareceu" });
  } finally {
    await browser.close();
  }

  if (failures.length) {
    console.error("\nFalhas:", JSON.stringify(failures, null, 2));
    process.exit(1);
  }
  console.log("\nNavegação sidebar OK — todas as rotas renderizaram sem reload.");
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
