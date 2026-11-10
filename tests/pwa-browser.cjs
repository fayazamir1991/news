const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome' });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 2 });
    const page = await context.newPage();
    const origin = 'http://127.0.0.1:8080';
    await page.goto(origin);
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
      if (!navigator.serviceWorker.controller) await new Promise(resolve => navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true }));
    });
    const manifest = await page.evaluate(async () => (await fetch('/manifest.webmanifest')).json());
    assert.equal(manifest.display, 'standalone');
    assert.equal(manifest.scope, '/');
    for (const icon of manifest.icons) {
      const dimensions = await page.evaluate(src => new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image.naturalWidth + 'x' + image.naturalHeight);
        image.onerror = reject;
        image.src = src;
      }), icon.src);
      assert.equal(dimensions, icon.sizes);
    }
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.goto(origin + '/archive/');
    const issue = await page.locator('a[href^="/issues/"]').first().getAttribute('href');
    await page.goto(origin + issue);
    const title = await page.title();
    await page.screenshot({ path: '/tmp/dideban-mobile.png', fullPage: false });
    // Stop the real server: browser emulation alone can leave worker fetches online.
    execFileSync('docker', ['stop', 'weekly-news']);
    await context.setOffline(true);
    const offlineResponse = await page.goto(origin + issue);
    assert(offlineResponse.fromServiceWorker());
    assert.equal(await page.title(), title);
    await page.goto(origin + '/never-cached/');
    assert.match(await page.locator('h1').innerText(), /اتصال اینترنت/);
    await context.close();
    execFileSync('docker', ['start', 'weekly-news']);
    for (let attempt = 0; attempt < 20; attempt++) {
      try { if ((await fetch(origin + '/healthz')).ok) break; } catch {}
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    const ios = await browser.newContext({ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1' });
    const phone = await ios.newPage();
    await phone.goto(origin);
    await phone.locator('#install-app').click();
    assert(await phone.locator('#install-help').isVisible());
    console.log('PASS: manifest, icons, mobile layout, offline report, offline fallback, iPhone installation help');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
