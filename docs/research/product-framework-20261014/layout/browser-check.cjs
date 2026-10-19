// Optional raster exports and actual browser interaction checks for viewer.html.
// No external pages or APIs are contacted. Requires local Chrome + Playwright.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '/Users/kimmy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
async function main() {
  const dir = __dirname;
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1120},deviceScaleFactor:1});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    const checks=[], states=[];
    for(const [name,w,h] of [['integrated',1280,850],['pixel',1280,740]]) {
      await page.setViewportSize({width:w,height:h});
      await page.goto('file://'+dir+'/'+name+'-2d.svg');
      await page.screenshot({path:path.join(dir,name+'-2d.png')});
    }
    await page.setViewportSize({width:1440,height:1120});
    await page.goto('file://'+dir+'/viewer.html');
    await page.waitForFunction(()=>window.FRAMEWORK_VIEWER_STATE?.rendered_polygons>0);
    states.push(await page.evaluate(()=>window.FRAMEWORK_VIEWER_STATE));
    checks.push({name:'top_has_geometry',passed:states.at(-1).rendered_polygons>0});
    await page.screenshot({path:dir+'/viewer-2d.png',fullPage:true});
    await page.selectOption('#design','pixel');await page.click('#three');
    await page.waitForFunction(()=>window.FRAMEWORK_VIEWER_STATE?.mode==='3d'&&window.FRAMEWORK_VIEWER_STATE?.design==='pixel');
    states.push(await page.evaluate(()=>window.FRAMEWORK_VIEWER_STATE));
    checks.push({name:'pixel_3d_geometry',passed:states.at(-1).rendered_polygons===633});
    await page.screenshot({path:dir+'/viewer-3d.png',fullPage:true});
    await page.locator('#canvas').screenshot({path:dir+'/pixel-3d-projection.png'});
    await page.click('#metals');
    await page.waitForFunction(()=>window.FRAMEWORK_VIEWER_STATE?.visible_layers.length===6);
    states.push(await page.evaluate(()=>window.FRAMEWORK_VIEWER_STATE));
    checks.push({name:'only_interconnect_excludes_well_active_poly',passed:states.at(-1).visible_layers.every(x=>[33,34,35,36,38,42].includes(x))});
    await page.locator('#zoom').fill('2.5');await page.locator('#zoom').dispatchEvent('input');
    await page.waitForFunction(()=>window.FRAMEWORK_VIEWER_STATE?.zoom===2.5);
    checks.push({name:'zoom_input',passed:true});
    await page.locator('[data-layer="42"]').uncheck();
    await page.waitForFunction(()=>!window.FRAMEWORK_VIEWER_STATE?.visible_layers.includes(42));
    checks.push({name:'layer_switch',passed:true});
    await page.click('#all');await page.click('#two');await page.click('#fit');
    await page.waitForFunction(()=>window.FRAMEWORK_VIEWER_STATE?.mode==='2d'&&window.FRAMEWORK_VIEWER_STATE?.zoom===1&&window.FRAMEWORK_VIEWER_STATE?.visible_layers.length===10);
    states.push(await page.evaluate(()=>window.FRAMEWORK_VIEWER_STATE));
    checks.push({name:'all_layers_and_reset',passed:true});
    await page.setViewportSize({width:600,height:1000});
    await page.screenshot({path:dir+'/viewer-mobile.png',fullPage:true});
    const widths=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));
    checks.push({name:'mobile_no_horizontal_overflow',passed:widths.scroll<=widths.client});
    checks.push({name:'no_javascript_errors',passed:errors.length===0});
    const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
    const files=['integrated-2d.png','pixel-2d.png','viewer-2d.png','viewer-3d.png','viewer-mobile.png','pixel-3d-projection.png'];
    const result={passed:checks.every(x=>x.passed),checks,errors,states,mobile_width:widths,
      checked_viewer_sha256:sha(dir+'/viewer.html'),checked_script_sha256:sha(__filename),
      screenshot_sha256:Object.fromEntries(files.map(f=>[f,sha(dir+'/'+f)])),
      no_new_electrical_or_physical_verification:true};
    fs.writeFileSync(dir+'/browser-validation.json',JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify({passed:result.passed,checks:checks.length,errors}));
    if(!result.passed)process.exitCode=1;
  } finally {await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1});
