const {chromium}=require(process.env.REPORT_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..');
const base=path.join(root,'docs/research/reference-safety-20261013');
const build=path.join(root,'build/research-reference-safety-20261013');
(async()=>{
 fs.mkdirSync(build,{recursive:true});
 const options={headless:true};
 if(process.env.REPORT_CHROME_PATH)options.executablePath=process.env.REPORT_CHROME_PATH;
 const browser=await chromium.launch(options);
 try{
  const p=await browser.newPage({viewport:{width:1200,height:1100}});
  await p.goto('file://'+path.join(base,'report.html'));await p.evaluate(()=>document.fonts.ready);
  await p.emulateMedia({media:'print'});
  const sections=await p.locator('.page').evaluateAll(es=>es.map((e,i)=>({section:i+1,height:e.getBoundingClientRect().height})));
  const overflow=await p.locator('p,td,li,h1,h2,a,code').evaluateAll(es=>es.filter(e=>e.clientWidth>0&&e.scrollWidth>e.clientWidth+2).map(e=>({tag:e.tagName,text:e.innerText.slice(0,70)})));
  const images=await p.locator('img').evaluateAll(es=>es.map(e=>({src:e.getAttribute('src'),loaded:e.complete&&e.naturalWidth>0})));
  const result={sections,overflow,images,browser_version:browser.version()};
  fs.writeFileSync(path.join(build,'layout-check.json'),JSON.stringify(result,null,2)+'\n');
  if(overflow.length||images.some(x=>!x.loaded)||sections.some(x=>x.height>970))throw Error('Layout requires repair: '+JSON.stringify(result));
  await p.pdf({path:path.join(base,'report.pdf'),format:'A4',preferCSSPageSize:true,printBackground:true,displayHeaderFooter:true,
    margin:{top:'19mm',bottom:'20mm',left:'20mm',right:'20mm'},headerTemplate:'<div></div>',
    footerTemplate:'<div style="font-size:9px;color:#637982;width:100%;padding:0 20mm;font-family:Avenir Next;display:flex;justify-content:space-between"><span>Open MicroLED · 参考源、保护与架构 · 2026-10-14</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'});
  console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
