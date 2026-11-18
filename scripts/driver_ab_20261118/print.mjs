import path from 'node:path';
import {createHash} from 'node:crypto';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {fileURLToPath, pathToFileURL} from 'node:url';

const [moduleName, executablePath] = process.argv.slice(2);
const {chromium} = await import(pathToFileURL(moduleName).href);
const root = fileURLToPath(new URL('../../', import.meta.url));
const base = 'driver-ab-20261118';
const doc = path.join(root,'docs/research',base);
const qa = path.join(root, 'build', base, 'report-review');
const index = path.join(doc,'index.html');
const pdf = path.join(doc,'technical-stage-report.pdf');
const audit = [];
await mkdir(qa,{recursive:true});
const browser = await chromium.launch({executablePath});
try {
  for (const width of [1280,390]) {
    const page = await browser.newPage({viewport:{width,height:900}});
    await page.goto(pathToFileURL(index).href);
    await page.evaluate(() => document.fonts.ready);
    const result = await page.evaluate(() => ({
      width:innerWidth, overflow:document.documentElement.scrollWidth-innerWidth,
      images:[...document.images].map(x=>({src:x.getAttribute('src'),loaded:x.complete&&x.naturalWidth>0})),
      headings:[...document.querySelectorAll('h2')].map(h=>h.textContent)
    }));
    if (result.overflow>1 || result.images.length<3 || result.images.some(x=>!x.loaded))
      throw Error(JSON.stringify(result));
    audit.push(result);
    await page.screenshot({path:path.join(qa,'width-'+width+'.png')});
    if (width===1280) {
      await page.evaluate(prefix=>{
        for(const a of document.querySelectorAll('a[href]')){
          if (!a.href.startsWith(prefix)) continue;
          const repoPath = a.href.slice(prefix.length);
          const ref = repoPath.startsWith('evidence/') ? '445863f722790d605654ed18bd77e864a79650d6' : 'main';
          a.href = 'https://github.com/Kevin-Kaiyo/open-microled-driver-asic/blob/'+ref+'/'+repoPath;
        }
      },pathToFileURL(root).href.replace(/\/$/,'')+'/');
      await page.pdf({path:pdf, preferCSSPageSize:true, printBackground:true,
        displayHeaderFooter:true,headerTemplate:'<span></span>',footerTemplate:'<div style="font:9px Arial;color:#526c75;margin:0 19mm;width:100%;display:flex;justify-content:space-between"><span>Open MicroLED Driver ASIC · A/B · 2026-11-18</span><span class="pageNumber"></span></div>'});
    }
    await page.close();
  }
} finally {await browser.close();}
const sha=async f=>createHash('sha256').update(await readFile(f)).digest('hex');
await writeFile(path.join(root,'evidence',base,'report-browser.json'),JSON.stringify({
  views:audit,html_sha256:await sha(index),pdf_sha256:await sha(pdf)
}, null, 2)+'\n');
