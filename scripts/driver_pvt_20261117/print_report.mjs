import { createHash } from 'node:crypto';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const [playwrightModule, chrome] = process.argv.slice(2);
if (!playwrightModule || !chrome) {
  throw new Error('Usage: node print_report.mjs /path/to/playwright/index.mjs /path/to/chrome');
}
const { chromium } = await import(pathToFileURL(playwrightModule).href);
const root = fileURLToPath(new URL('../../', import.meta.url));
const report = path.join(root, 'docs/research/driver-pvt-20261117');
const work = path.join(root, 'build/driver-pvt-20261117/report-review');
const evidence = path.join(root, 'evidence/driver-pvt-20261117');
const index = path.join(report, 'index.html');
const pdf = path.join(report, 'technical-stage-report.pdf');
const url = pathToFileURL(index).href;
await mkdir(work, { recursive: true });
const browser = await chromium.launch({ executablePath: chrome, headless: true });

try {
  const reports = [];
  for (const width of [1280, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto(url, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const observation = await page.evaluate(() => ({
      title: document.querySelector('h1')?.textContent,
      loadedImages: [...document.images].filter(image => image.complete && image.naturalWidth > 0).length,
      images: document.images.length,
      headings: document.querySelectorAll('h2').length,
      horizontalOverflow: document.documentElement.scrollWidth - innerWidth,
    }));
    if (!observation.title || observation.images < 3 || observation.images !== observation.loadedImages || observation.horizontalOverflow > 1) {
      throw new Error(JSON.stringify(observation));
    }
    await page.screenshot({ path: path.join(work, `width-${width}.png`) });
    reports.push({ width, ...observation });
    if (width === 1280) {
      // Resolve PDF links for readers opening it outside the checkout.
      const rootURL = pathToFileURL(root).href.replace(/\/$/, '') + '/';
      await page.evaluate(({ rootURL }) => {
        const prefix = 'https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/main/';
        for (const link of document.querySelectorAll('a[href]')) {
          if (link.getAttribute('href').startsWith('#')) continue;
          if (link.href.startsWith(rootURL)) link.href = prefix + link.href.slice(rootURL.length);
        }
      }, { rootURL });
      await page.pdf({ path: pdf, preferCSSPageSize: true, printBackground: true,
        displayHeaderFooter: true, headerTemplate: '<div></div>',
        footerTemplate: '<div style="font:9px Arial;color:#526c75;margin:0 20mm;width:100%;display:flex;justify-content:space-between"><span>OPEN MICROLED DRIVER ASIC · 2026-11-17</span><span class="pageNumber"></span></div>' });
    }
    await page.close();
  }
  const sha256 = async name => createHash('sha256').update(await readFile(name)).digest('hex');
  await writeFile(path.join(evidence, 'report-browser.json'), JSON.stringify({
    passed: true, viewports: reports, html_sha256: await sha256(index), pdf_sha256: await sha256(pdf),
  }, null, 2) + '\n');
  console.log(JSON.stringify(reports));
} finally {
  await browser.close();
}
