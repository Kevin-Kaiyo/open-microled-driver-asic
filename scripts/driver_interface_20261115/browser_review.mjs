// Local rendered HTML QA. No publishing, network navigation or external mutation.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const stage='driver-interface-20261115';
const doc=path.join(root,'docs/research',stage);
const work=path.join(root,'build',stage,'render');
const {chromium}=await import(process.env.REPORT_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.REPORT_CHROME_BIN?{executablePath:process.env.REPORT_CHROME_BIN}:{})});
await fs.mkdir(work,{recursive:true});
const checks=[];
try {
  for(const width of [1280,390]){
    const page=await browser.newPage({viewport:{width,height:900},deviceScaleFactor:1});
    for(const file of ['index.html','reproduce.html','methods-notes.html']){
      const errors=[];const handler=e=>errors.push(String(e));page.on('pageerror',handler);
      await page.goto(pathToFileURL(path.join(doc,file)).href,{waitUntil:'load'});
      await page.evaluate(()=>document.fonts.ready);
      const observed=await page.evaluate(()=>({
        overflow:document.documentElement.scrollWidth>innerWidth+1,
        images:[...document.images].filter(x=>!x.complete||!x.naturalWidth).map(x=>x.getAttribute('src')),
        sections:document.querySelectorAll('section').length,
        title:document.title,
      }));
      if(file==='index.html')await page.screenshot({path:path.join(work,`html-${width}.png`)});
      checks.push({width,file,...observed,errors});page.off('pageerror',handler);
    }
    await page.close();
  }
  const receipt={passed:checks.every(x=>!x.overflow&&!x.images.length&&!x.errors.length),browser:await browser.version(),checks,scope:'Local HTML at desktop/mobile widths; image loads, overflow and runtime errors. No live deployment claimed.'};
  await fs.writeFile(path.join(root,'evidence',stage,'browser-review.json'),JSON.stringify(receipt,null,2)+'\n');
  if(!receipt.passed)throw Error(JSON.stringify(receipt));
  console.log(JSON.stringify({passed:receipt.passed,checks:checks.length}));
}finally{await browser.close();}
