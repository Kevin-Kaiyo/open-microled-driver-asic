/* Render, exercise and export original component schematics, not EDA simulation. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require(process.env.REPORT_PLAYWRIGHT_MODULE || '/Users/kimmy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(ROOT, 'docs/research/six-mos-pwm-tutorial-20261012');
const BUILD = path.join(ROOT, 'build/six-mos-pwm-tutorial-20261012');
const figureDir = path.join(OUT, 'figures');
const checks = [];
function check(name, passed, detail) {checks.push({name,passed,detail});if(!passed)throw Error(name+': '+JSON.stringify(detail));}
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const sourceNames = ['six-mos-pwm.html','current-steering.html'];
const content = sourceNames.map(n=>fs.readFileSync(path.join(OUT,n),'utf8'));
const wrapper = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>PWM 电流镜与通信电流舵：工作原理</title><style>
:root{color-scheme:light dark;--background:#fff;--foreground:#284652;--muted-foreground:#66747b;--viz-series-1:#176e73;--viz-series-2:#ad652e;--primary:#284652;--primary-foreground:#fff;--border:#c8d1d5;--accent:#edf1f2;--accent-foreground:#284652}
@media(prefers-color-scheme:dark){:root{--background:#161d22;--foreground:#e0e8ec;--muted-foreground:#a0adb6;--viz-series-1:#74cccf;--viz-series-2:#efb67f;--primary:#e0e8ec;--primary-foreground:#161d22;--border:#56636c;--accent:#303a43;--accent-foreground:#e0e8ec}}
*{box-sizing:border-box}body{margin:0;background:var(--background);color:var(--foreground);font-family:'PingFang SC','Avenir Next',sans-serif;font-size:16px;line-height:1.65}main{max-width:776px;margin:auto;padding:20px}.viz-controls,.viz-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.viz-row{margin:14px 0}.text-small{font-size:14px}.btn{font:inherit;padding:7px 11px;border:1px solid var(--border);border-radius:5px;background:transparent;color:var(--foreground);cursor:pointer}.btn[aria-pressed=true]{background:var(--primary);color:var(--primary-foreground)}h1{font-size:26px;font-weight:500;line-height:1.3}h3{font-size:19px;font-weight:500}hr{border:0;border-top:1px solid var(--border);margin:32px 0}a{color:var(--viz-series-1)}@media(max-width:400px){main{padding:10px}}@media(pointer:coarse){.btn{min-height:44px}}@media print{.viz-controls{display:none}}
</style></head><body><main><h1>从 PWM 电流镜到通信电流舵</h1><p>本项目的电流镜驱动采用六只 MOS；这是器件数量，不是行业统一的架构名称。通信图是独立教学概念；图示不是新增的高速仿真结果。</p><p><a href="README.md">完整技术说明与连接表</a> · <a href="figure-ledger.json">图形与来源记录</a></p>${content[0]}<hr>${content[1]}</main></body></html>`;
fs.mkdirSync(BUILD,{recursive:true});fs.mkdirSync(figureDir,{recursive:true});
fs.writeFileSync(path.join(OUT,'tutorial.html'),wrapper);
(async()=>{
  const browser=await chromium.launch({executablePath:process.env.REPORT_CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const page=await browser.newPage({viewport:{width:820,height:1000},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('file://'+path.join(OUT,'tutorial.html'));await page.waitForFunction(()=>document.querySelectorAll('.six-schematic svg,.steer-schematic svg').length===2);
  await page.evaluate(()=>document.fonts.ready);
  const pixel='#six-mos-pwm-20261012', steering='#current-steering-20261012';
  const states=[['original','original'],['charge','charge'],['on','on'],['discharge','discharge'],['off','off']];
  const byName={XREF:'MREF',XOUT:'MOUT',XPASS:'MPASS',XCLAMP:'MCLAMP',XINV_N:'MN',XINV_P:'MP'};
  const netlist=fs.readFileSync(path.join(ROOT,'analog/driver/pixel_driver.spice'),'utf8');
  const expected={};for(const line of netlist.split(/\r?\n/)){const words=line.trim().split(/\s+/);if(byName[words[0]])expected[byName[words[0]]]=words.slice(1,5);}
  check('netlist_six_devices',Object.keys(expected).length===6,Object.keys(expected));
  const exportSvg=async selector=>page.locator(selector+' svg').evaluate(svg=>{
    const clone=svg.cloneNode(true),a=[svg,...svg.querySelectorAll('*')],b=[clone,...clone.querySelectorAll('*')];
    const properties=['color','fill','stroke','stroke-width','stroke-dasharray','stroke-linecap','stroke-linejoin','font-family','font-size','font-weight'];
    a.forEach((original,i)=>{const css=getComputedStyle(original);properties.forEach(key=>b[i].style.setProperty(key,css.getPropertyValue(key)));});
    clone.setAttribute('xmlns','http://www.w3.org/2000/svg');clone.setAttribute('width',svg.viewBox.baseVal.width);clone.setAttribute('height',svg.viewBox.baseVal.height);
    return new XMLSerializer().serializeToString(clone)+'\n';
  });
  const diagramRecords=[];
  for(const [mode,suffix] of states){
    await page.locator(pixel+` button[data-mode="${mode}"]`).click();
    await page.waitForFunction(m=>document.querySelector('#six-mos-pwm-20261012').dataset.selectedMode===m,mode);
    const data=await page.locator(pixel+' svg').evaluate(svg=>({
      devices:[...svg.querySelectorAll('[data-device]')].map(e=>({name:e.dataset.device,type:e.dataset.type,state:e.dataset.state,nets:e.dataset.nets.split(' '),terminal_order:e.dataset.terminalOrder})),
      current_paths:svg.querySelectorAll('.current-path').length,charge_paths:svg.querySelectorAll('.charge-path').length,
      title:svg.querySelector('title').textContent
    }));
    check('six_'+mode+'_connections',data.devices.length===6&&data.devices.every(d=>JSON.stringify(d.nets)===JSON.stringify(expected[d.name])),data.devices);
    check('six_'+mode+'_reference_current',mode==='original'||data.current_paths>=1,data.current_paths);
    if(mode==='on'||mode==='off')check('six_'+mode+'_no_steady_gate_arrows',data.charge_paths===0,data.charge_paths);
    if(mode==='charge'||mode==='discharge')check('six_'+mode+'_transient_gate_arrows',data.charge_paths>0,data.charge_paths);
    if(mode==='off')check('off_only_reference_arrow',data.current_paths===1,data.current_paths);
    if(mode==='on')check('on_reference_and_led_arrows',data.current_paths===3,data.current_paths);
    const name='six-mos-'+suffix+'.svg';fs.writeFileSync(path.join(figureDir,name),await exportSvg(pixel));
    await page.locator(pixel).screenshot({path:path.join(BUILD,'six-'+mode+'-desktop.png')});
    diagramRecords.push({file:'figures/'+name,...data});
  }
  for(const withCascode of [false,true])for(const mode of ['one','zero']){
    await page.locator(steering+' input[data-cascode]').setChecked(withCascode);
    await page.locator(steering+` button[data-mode="${mode}"]`).click();
    const data=await page.locator(steering+' svg').evaluate(svg=>({devices:[...svg.querySelectorAll('[data-device]')].map(e=>({name:e.dataset.device,state:e.dataset.state})),paths:svg.querySelectorAll('.current-path').length}));
    const prefix='steer_'+(withCascode?'cascode_':'')+mode;
    check(prefix+'_devices',data.devices.length===(withCascode?4:3),data.devices);
    check(prefix+'_switches',data.devices.find(d=>d.name==='ML').state===(mode==='one'?'导通':'截止')&&data.devices.find(d=>d.name==='MD').state===(mode==='one'?'截止':'导通'),data.devices);
    const suffix=(withCascode?'cascode-':'')+mode;
    fs.writeFileSync(path.join(figureDir,'current-steering-'+suffix+'.svg'),await exportSvg(steering));
    await page.locator(steering).screenshot({path:path.join(BUILD,'steer-'+suffix+'-desktop.png')});
    diagramRecords.push({file:'figures/current-steering-'+suffix+'.svg',...data});
  }
  for(const width of [320,390,660,820]){
    await page.setViewportSize({width,height:1100});
    await page.locator(pixel+' button[data-mode="on"]').click();await page.locator(steering+' button[data-mode="one"]').click();
    await page.waitForFunction(()=>Math.abs(document.querySelector('.six-schematic').getBoundingClientRect().width-document.querySelector('.six-schematic svg').viewBox.baseVal.width)<=1);
    const bounds=await page.evaluate(()=>{
      const issues=[];for(const selector of ['.six-schematic svg','.steer-schematic svg']){const svg=document.querySelector(selector),v=svg.viewBox.baseVal;for(const t of svg.querySelectorAll('text')){const r=t.getBoundingClientRect(),s=svg.getBoundingClientRect();if(r.left<s.left-1||r.right>s.right+1||r.top<s.top-1||r.bottom>s.bottom+1)issues.push({text:t.textContent,rect:{left:r.left-s.left,right:r.right-s.left},svg_width:s.width});}}
      return {document_width:document.documentElement.scrollWidth,viewport:innerWidth,issues};
    });
    check('viewport_'+width+'_document_fit',bounds.document_width<=bounds.viewport,bounds);
    check('viewport_'+width+'_text_in_svg',bounds.issues.length===0,bounds.issues);
    const overlaps=await page.evaluate(()=>{
      const result=[];for(const selector of ['.six-schematic svg','.steer-schematic svg']){const ts=[...document.querySelector(selector).querySelectorAll('text')];for(let i=0;i<ts.length;i++)for(let j=i+1;j<ts.length;j++){const a=ts[i].getBoundingClientRect(),b=ts[j].getBoundingClientRect();if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)result.push([ts[i].textContent,ts[j].textContent]);}}return result;
    });
    check('viewport_'+width+'_no_text_overlaps',overlaps.length===0,overlaps);
    await page.locator(pixel).screenshot({path:path.join(BUILD,'six-on-'+width+'.png')});await page.locator(steering).screenshot({path:path.join(BUILD,'steer-one-'+width+'.png')});
  }
  await page.locator(steering+' input[data-cascode]').uncheck();
  for(const width of [320,820]){
    await page.setViewportSize({width,height:1100});
    for(const mode of ['charge','discharge']){
      await page.locator(pixel+` button[data-mode="${mode}"]`).click();
      const states=await page.locator(pixel+' svg').evaluate(svg=>[...svg.querySelectorAll('[data-device]')].map(e=>({name:e.dataset.device,state:e.dataset.state})));
      check('transition_'+mode+'_consistent_states',states.every(s=>s.name==='MREF'||s.state==='过渡'),states);
      await page.locator(pixel).screenshot({path:path.join(BUILD,'six-'+mode+'-'+width+'.png')});
    }
  }
  await page.emulateMedia({colorScheme:'dark'});await page.setViewportSize({width:820,height:1000});
  await page.locator(pixel+' button[data-mode="on"]').click();
  await page.locator(pixel).screenshot({path:path.join(BUILD,'six-on-dark.png')});await page.locator(steering).screenshot({path:path.join(BUILD,'steer-one-dark.png')});
  check('no_browser_errors',errors.length===0,errors);
  const ledger={classification:'Original teaching schematics; no new transistor/optical simulation',date:'2026-10-12',terminal_order:'D G S B',pixel_netlist:'analog/driver/pixel_driver.spice',pixel_netlist_sha256:hash(path.join(ROOT,'analog/driver/pixel_driver.spice')),pixel_device_connections:expected,
    current_convention:'Conventional current; solid arrows persistent, dashed arrows transition-only; LED outward arrows indicate emitted light',
    switching_qualification:'Endpoint logic states plus qualitative main charging/discharging paths. Finite skew, overlap, feedthrough and remaining parasitic currents are not plotted as validated waveforms.',
    high_speed:{classification:'Independent conceptual current steering cell: 3 NMOS, optional fourth cascode NMOS',devices:{MI:['VX','VBIAS','0','0'],ML:['LED_K','DATA','VX','0'],MD:['DUMMY_K','DATA_B','VX','0']},cascode_variant:{MC:['VX','VCAS','VI','0'],MI:['VI','VBIAS','0','0']},omitted:['differential pre-driver','bias generator','LVDS/decoder','pads/ESD/package/parasitics'],dummy_load:'Illustrative resistor; not H05 figure reproduction or actual H05 load',sizing_voltage_rate:'Not specified or simulated',primary_source:'https://doi.org/10.1109/LPT.2016.2624281',locator:'H05 accepted manuscript PDF p2 section II-A/Fig2; actual implementation includes cascode and uses a 1.8 V dummy rail'},diagrams:diagramRecords,
    sources:Object.fromEntries(['analog/driver/pixel_driver.spice','scripts/interface/run.py','evidence/interface/dc.csv','evidence/interface/summary.json'].map(p=>[p,hash(path.join(ROOT,p))]))};
  fs.writeFileSync(path.join(OUT,'figure-ledger.json'),JSON.stringify(ledger,null,2)+'\n');
  for(const doc of ['README.md','high-speed-notes.md']){
    const body=fs.readFileSync(path.join(OUT,doc),'utf8');const links=[...body.matchAll(/\]\(([^)]+)\)/g)].map(m=>m[1]).filter(x=>!/^https?:/.test(x));
    check(doc+'_local_links',links.every(x=>fs.existsSync(path.resolve(OUT,x))),links);
  }
  check('no_fragment_document_markup',content.every(c=>!/<(?:html|head|body)(?:\s|>)/i.test(c)),null);
  check('no_literal_escaped_markup',content.every(c=>!c.includes('<div class=\\"')),null);
  const validation={status:'passed',checks,check_count:checks.length,limitations:['No new EDA or optical run','Browser checks and netlist metadata crosscheck are supplemented by visual and independent circuit review'],outputs_sha256:Object.fromEntries(['tutorial.html','figure-ledger.json','README.md','high-speed-notes.md',...sourceNames,...fs.readdirSync(figureDir).map(n=>'figures/'+n)].map(p=>[p,hash(path.join(OUT,p))]))};
  fs.writeFileSync(path.join(OUT,'validation.json'),JSON.stringify(validation,null,2)+'\n');
  await browser.close();console.log(JSON.stringify({status:'passed',checks:checks.length,figures:diagramRecords.length}));
})().catch(e=>{console.error(e);process.exit(1);});
