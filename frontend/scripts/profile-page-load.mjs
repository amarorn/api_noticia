/**
 * Mede tempo de carregamento por tela (sidebar) e APIs lentas.
 * Uso: node scripts/profile-page-load.mjs
 */
import { chromium } from "playwright";

const BASE = process.env.APP_URL ?? "http://localhost:5173";

const PAGES = [
  { label: "Dashboard", path: "/" },
  { label: "Jogos", path: "/jogos" },
  { label: "Amistosos", path: "/amistosos" },
  { label: "Ao vivo", path: "/ao-vivo" },
  { label: "Grupos", path: "/grupos" },
  { label: "Convocações", path: "/convocacoes" },
  { label: "Álbum", path: "/album" },
  { label: "Palpite avulso", path: "/palpite-avulso" },
  { label: "Histórico", path: "/historico" },
  { label: "Notícias", path: "/noticias" },
  { label: "Brasileirao", path: "/brasileirao" },
  { label: "Performance", path: "/performance" },
  { label: "Modelos", path: "/modelos" },
  { label: "Carteira", path: "/carteira" },
];

async function clickSidebar(page, label) {
  const link = page.locator("aside nav").getByRole("link", { name: label, exact: true });
  await link.click();
}

async function waitReady(page, timeoutMs = 30000) {
  const start = Date.now();
  const skeleton = page.locator(
    '[class*="Skeleton"], [class*="skeleton"], [aria-busy="true"]',
  );
  const main = page.locator("#main-content");

  await main.waitFor({ state: "attached", timeout: timeoutMs });

  while (Date.now() - start < timeoutMs) {
    const skCount = await skeleton.count();
    let visibleSk = 0;
    for (let i = 0; i < Math.min(skCount, 5); i++) {
      if (await skeleton.nth(i).isVisible().catch(() => false)) visibleSk++;
    }
    const text = ((await main.innerText().catch(() => "")) || "").trim();
    const loadingWords = /carregando|loading|aguarde/i.test(text.slice(0, 400));
    if (visibleSk === 0 && !loadingWords && text.length > 40) {
      return Date.now() - start;
    }
    await page.waitForTimeout(200);
  }
  return Date.now() - start;
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await context.newPage();

  const apiStats = new Map();

  page.on("response", async (res) => {
    const url = res.url();
    if (!url.includes("/api/") && !url.match(/localhost:5173\/(worldcup|health|news|wallet)/)) {
      if (!url.includes("127.0.0.1:8000") && !url.includes("/api/")) return;
    }
    if (!url.includes("/api/") && !url.includes(":8000") && !url.includes("/worldcup")) return;
    try {
      const timing = res.request().timing();
      const ms = timing.responseEnd > 0 ? timing.responseEnd : 0;
      const path = new URL(url).pathname;
      const prev = apiStats.get(path) || { count: 0, total: 0, max: 0 };
      prev.count++;
      prev.total += ms;
      prev.max = Math.max(prev.max, ms);
      apiStats.set(path, prev);
    } catch {
      /* ignore */
    }
  });

  const results = [];

  try {
    await page.goto(`${BASE}/jogos`, { waitUntil: "domcontentloaded", timeout: 25000 });
    await page.waitForTimeout(800);

    for (const p of PAGES) {
      const apiBefore = new Map(apiStats);

      const t0 = Date.now();
      if (page.url().endsWith(p.path) || (p.path === "/" && new URL(page.url()).pathname === "/")) {
        await page.reload({ waitUntil: "domcontentloaded" });
      } else {
        await clickSidebar(page, p.label);
        await page.waitForURL(`**${p.path === "/" ? "/" : p.path}**`, { timeout: 15000 });
      }
      const navMs = Date.now() - t0;

      const readyMs = await waitReady(page, 35000);
      const totalMs = Date.now() - t0;

      const slowApis = [];
      for (const [path, stat] of apiStats) {
        const delta = stat.count - (apiBefore.get(path)?.count || 0);
        if (delta > 0) {
          slowApis.push({ path, ms: Math.round(stat.max), calls: delta });
        }
      }
      slowApis.sort((a, b) => b.ms - a.ms);

      results.push({
        label: p.label,
        path: p.path,
        navMs,
        readyMs,
        totalMs,
        slowApis: slowApis.slice(0, 5),
      });

      console.log(
        `${totalMs > 5000 ? "🐢" : totalMs > 2000 ? "⚠️" : "✓"} ${p.label.padEnd(14)} total=${totalMs}ms ready=${readyMs}ms nav=${navMs}ms`,
      );
      for (const api of slowApis.slice(0, 3)) {
        if (api.ms > 300) console.log(`     API ${api.path} ~${api.ms}ms (${api.calls}x)`);
      }
    }
  } finally {
    await browser.close();
  }

  results.sort((a, b) => b.totalMs - a.totalMs);
  console.log("\n=== TOP 5 MAIS LENTAS ===");
  for (const r of results.slice(0, 5)) {
    console.log(`${r.label} (${r.path}): ${r.totalMs}ms`);
    for (const api of r.slowApis) {
      console.log(`  - ${api.path}: ${api.ms}ms`);
    }
  }
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
