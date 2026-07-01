/**
 * Perfil detalhado de uma rota — APIs e tempo até conteúdo.
 * Uso: node scripts/profile-single-page.mjs /jogos
 */
import { chromium } from "playwright";

const BASE = process.env.APP_URL ?? "http://localhost:5173";
const path = process.argv[2] ?? "/jogos";

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  const t0 = Date.now();
  await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 30000 });

  // espera sair do skeleton
  for (let i = 0; i < 60; i++) {
    const state = await page.evaluate(() => {
      const main = document.getElementById("main-content");
      const text = main?.innerText?.trim() ?? "";
      const title = document.title;
      const h1 = document.querySelector("h1, h2")?.textContent?.trim() ?? "";
      const loading = /carregando|loading/i.test(text.slice(0, 300));
      return { title, h1, textLen: text.length, loading };
    });
    if (!state.loading && state.textLen > 50) {
      const ms = Date.now() - t0;
      const resources = await page.evaluate(() => {
        return performance
          .getEntriesByType("resource")
          .filter((r) => r.name.includes("/api/"))
          .map((r) => ({
            path: new URL(r.name).pathname + new URL(r.name).search,
            ms: Math.round(r.duration),
            size: r.transferSize,
          }))
          .sort((a, b) => b.ms - a.ms);
      });

      console.log(`\n=== ${path} ===`);
      console.log(`Título: ${state.title}`);
      console.log(`Heading: ${state.h1}`);
      console.log(`Pronto em: ${ms}ms`);
      console.log("\nAPIs (mais lentas):");
      for (const r of resources.slice(0, 12)) {
        console.log(`  ${String(r.ms).padStart(5)}ms  ${r.path}`);
      }
      if (resources.length === 0) console.log("  (nenhuma /api/ — cache ou erro de auth no proxy)");
      await browser.close();
      return;
    }
    await page.waitForTimeout(500);
  }

  const stuck = await page.evaluate(() => ({
    title: document.title,
    h1: document.querySelector("h1, h2")?.textContent,
    snippet: document.getElementById("main-content")?.innerText?.slice(0, 200),
  }));
  console.log(`TIMEOUT ${path} após ${Date.now() - t0}ms`);
  console.log(stuck);
  await browser.close();
  process.exit(1);
}

run();
