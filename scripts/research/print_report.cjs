// Print the report with a real browser and retain its page geometry checks.
// REPORT_PLAYWRIGHT_MODULE and REPORT_CHROME_PATH allow a bundled installation.
const { chromium } = require(process.env.REPORT_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'build/research-report');

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const options = { headless: true };
  if (process.env.REPORT_CHROME_PATH) options.executablePath = process.env.REPORT_CHROME_PATH;
  const browser = await chromium.launch(options);
  const page = await browser.newPage({ viewport: { width: 1200, height: 1000 } });
  await page.goto('file://' + path.join(root, 'docs/research/research-report.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.emulateMedia({ media: 'print' });
  const sections = await page.locator('section.page').evaluateAll(elements => elements.map((e, i) => ({
    section: i + 1, height: e.getBoundingClientRect().height
  })));
  const overflow = await page.locator('p,td,li,h1,h2,a,pre').evaluateAll(elements => elements
    .filter(e => e.scrollWidth > e.clientWidth + 2 && e.clientWidth > 0)
    .map(e => ({ tag: e.tagName, text: e.innerText.slice(0, 70) })));
  const version = (await page.title()).match(/v\d+\.\d+/)?.[0] || '';
  const checks = { sections, overflow, browser_version: browser.version(), report_version: version };
  fs.writeFileSync(path.join(output, 'layout-check.json'), JSON.stringify(checks, null, 2) + '\n');
  if (overflow.length) throw Error('Horizontal overflow');
  if (sections.some(s => s.height > 970)) throw Error('Section exceeds one A4 content page');
  await page.pdf({
    path: path.join(root, 'docs/research/research-report.pdf'), format: 'A4',
    preferCSSPageSize: true, printBackground: true, displayHeaderFooter: true,
    margin: { top: '20mm', bottom: '20mm', left: '20mm', right: '20mm' },
    headerTemplate: '<div></div>',
    footerTemplate: `<div style="font-size:9px;color:#647c84;width:100%;padding:0 20mm;font-family:Avenir Next;display:flex;justify-content:space-between"><span>Open MicroLED Driver ASIC · ${version}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`
  });
  console.log(JSON.stringify(checks));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
