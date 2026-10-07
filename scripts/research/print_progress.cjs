// Browser rendering and measured geometry for the separate control-experiment report.
const { chromium } = require(process.env.REPORT_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const base = path.join(root, 'docs/research/control-experiment');
const output = path.join(root, 'build/control-experiment/report');

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const options = { headless: true };
  if (process.env.REPORT_CHROME_PATH) options.executablePath = process.env.REPORT_CHROME_PATH;
  const browser = await chromium.launch(options);
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 1000 } });
    await page.goto('file://' + path.join(base, 'progress.html'));
    await page.evaluate(() => document.fonts.ready);
    await page.emulateMedia({ media: 'print' });
    const sections = await page.locator('section.page').evaluateAll(es => es.map((e, i) => ({
      section: i + 1, height: e.getBoundingClientRect().height
    })));
    const overflow = await page.locator('p,td,li,h1,h2,a,pre,.node').evaluateAll(es => es
      .filter(e => e.scrollWidth > e.clientWidth + 2 && e.clientWidth > 0)
      .map(e => ({ tag: e.tagName, text: e.innerText.slice(0, 70) })));
    const checks = { sections, overflow, browser_version: browser.version(), study_date: '2026-10-07' };
    fs.writeFileSync(path.join(output, 'layout-check.json'), JSON.stringify(checks, null, 2) + '\n');
    if (overflow.length) throw Error('Horizontal overflow');
    if (sections.some(s => s.height > 970)) throw Error('Section exceeds one A4 content page');
    await page.pdf({ path: path.join(base, 'progress.pdf'), format: 'A4',
      preferCSSPageSize: true, printBackground: true, displayHeaderFooter: true,
      margin: { top: '20mm', bottom: '20mm', left: '20mm', right: '20mm' },
      headerTemplate: '<div></div>',
      footerTemplate: '<div style="font-size:9px;color:#647c84;width:100%;padding:0 20mm;font-family:Avenir Next;display:flex;justify-content:space-between"><span>Open MicroLED · 控制实验与项目进展 · 2026-10-07</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>' });
    console.log(JSON.stringify(checks));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
