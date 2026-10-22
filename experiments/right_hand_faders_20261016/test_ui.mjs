// Headless artifact QA uses a disposable browser context, never a user profile.
import {createRequire} from 'node:module';
import fs from 'node:fs';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/Sakuya/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const context=await browser.newContext({viewport:{width:1100,height:950},hasTouch:true});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const results=[];
function check(value,name){if(!value)throw Error(name);results.push(name)}
try {
 await page.goto('http://127.0.0.1:8766/',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>Boolean(window.faderPreview));
 const state=()=>page.evaluate(()=>window.faderPreview.state);
 const flushTouch=()=>page.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done))));
 await page.locator('#middle').click();let s=await state();check(s.held[2]===240&&s.touches.length===2,'two sides target midpoint');
 await page.screenshot({path:new URL('evidence/preview-midpoint.png',import.meta.url).pathname.replace(/^\/(.:)/,'$1'),fullPage:true});
 await page.locator('#release').click();s=await state();check(s.held[2]===240&&s.touches.length===0,'release retains position');
 await page.locator('#reset').click();await page.locator('#near').click();s=await state();check(s.held[2]===330,'same side nearest controls');
 await page.locator('#reset').click();await page.locator('#zones').click();s=await state();check(s.radius===150&&s.held[2]===100&&s.held[3]===420,'oversized radius cannot cross zone');
 await page.screenshot({path:new URL('evidence/preview-zones.png',import.meta.url).pathname.replace(/^\/(.:)/,'$1'),fullPage:true});
 await page.locator('#reset').click();
 const box=await page.locator('#surface').boundingBox();
 const pos=(x,y)=>({x:box.x+x*box.width/800,y:box.y+y*box.height/480});
 // Real browser pointer events generated from a multi-touch report.
 const cdp=await context.newCDPSession(page);
 const points=[{...pos(230,120),id:0},{...pos(270,360),id:1}];
 await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:points});
 await flushTouch();
 s=await state();check(s.touches.length===2&&s.held[2]===240,'multi-touch pointer input reaches model');
 await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{...pos(230,180),id:0},{...pos(270,360),id:1}]});
 await flushTouch();
 s=await state();check(s.held[2]===270,'moving one finger updates midpoint');
 await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
 await flushTouch();
 s=await state();check(s.touches.length===0,'touch end releases ownership');
 check(s.held[2]===270,'simultaneous release does not publish a one-finger intermediate target');
 const retained=s.held[2];await page.waitForTimeout(40);check((await state()).held[2]===retained,'touch end holds last reported result');
 await page.setViewportSize({width:390,height:844});
 check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile viewport has no horizontal overflow');
 await page.screenshot({path:new URL('evidence/preview-mobile.png',import.meta.url).pathname.replace(/^\/(.:)/,'$1'),fullPage:true});
 check(errors.length===0,'no browser runtime errors');
 const result={status:'PASS within disposable browser prototype',checks:results,errors,hardware_verified:false,audio_connected:false};
 fs.writeFileSync(new URL('evidence/ui-validation.json',import.meta.url),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));
}finally{await browser.close()}
