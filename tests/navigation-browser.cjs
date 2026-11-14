const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome' });
  try {
    const context = await browser.newContext({ serviceWorkers: 'block' });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const origin = 'http://127.0.0.1:8080';
    for (const width of [320, 390, 760]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto(origin);
      const nav = page.locator('.bottom-nav');
      assert(await nav.isVisible());
      assert(!(await page.locator('.desktop-nav').isVisible()));
      assert.deepEqual(await nav.locator('a span').allTextContents(), ['آرشیو', 'مروری‌ها', 'خانه', 'حساب', 'ذخیره‌ها']);
      const boxes = await nav.locator('a').evaluateAll(nodes => nodes.map(node => {
        const b = node.getBoundingClientRect();
        return { x: b.x, width: b.width, height: b.height, fits: node.scrollWidth <= node.clientWidth };
      }));
      assert(boxes.every(b => b.width >= 44 && b.height >= 44 && b.fits));
      assert(boxes.slice(1).every((b, i) => b.x < boxes[i].x));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.equal(await nav.locator('[aria-current="page"]').getAttribute('href'), '/');
    }
    await page.goto(origin + '/issues/1405-08-21/');
    assert.match(await page.locator('#survey .survey-dates').innerText(), /^(ارسال به arXiv|انتشار مقاله): [۰-۹]+/);
    await page.locator('.bottom-nav a[href="/surveys/"]').click();
    assert.equal(await page.locator('h1').innerText(), 'مقالات مروری');
    await page.locator('.survey-list a').first().click();
    assert.equal(await page.locator('.survey-article h2').count(), 3);
    assert.match(await page.locator('.intro .survey-dates').innerText(), /(ارسال به arXiv|انتشار مقاله): [۰-۹]+/);
    assert((await page.locator('.survey-sources a').count()) >= 1);
    assert.equal(await page.locator('.survey-article a.source').count(), 0);
    assert(await page.locator('.survey-sources').evaluate(node => node.getBoundingClientRect().top < document.querySelector('.survey-article').getBoundingClientRect().top));
    assert(await page.locator('.survey-article').innerText().then(s => s.includes('ترجمهٔ کامل مقدمه')));
    assert.equal(await page.locator('.bottom-nav [aria-current="page"]').getAttribute('href'), '/surveys/');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    for (const [url, title] of [['/account/', 'حساب کاربری'], ['/bookmarks/', 'ذخیره‌شده‌ها'], ['/archive/', 'آرشیو گزارش‌ها']]) {
      await page.locator('.bottom-nav a[href="' + url + '"]').click();
      assert.equal(await page.locator('h1').innerText(), title);
      assert.equal(await page.locator('.bottom-nav [aria-current="page"]').getAttribute('href'), url);
    }
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(origin);
    assert(!(await page.locator('.bottom-nav').isVisible()));
    assert(await page.locator('.desktop-nav').isVisible());
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(errors, []);
    console.log('PASS: 320/390/760px RTL navigation, five short labels, touch targets, survey/archive/account routes, desktop navigation, no JS errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
