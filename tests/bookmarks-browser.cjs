const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome' });
  try {
    const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 390, height: 844 } });
    await context.route('**/auth/v1/settings', route => route.fulfill({ json: { external: { google: true } } }));
    await context.addInitScript(() => {
      const user = id => ({ user: { id, email: id + '@example.test' } });
      let session = user(localStorage.getItem('mock-user') || 'alice');
      const rows = JSON.parse(localStorage.getItem('mock-bookmarks') || '{}');
      let changed;
      window.mockFail = false;
      window.switchAccount = id => {
        session = id ? user(id) : null;
        localStorage.setItem('mock-user', id || 'alice');
        changed('SIGNED_IN', session);
      };
      window.supabase = { createClient: () => ({
        auth: {
          onAuthStateChange: fn => { changed = fn; },
          getSession: async () => ({ data: { session }, error: null }),
          signOut: async () => { session = null; changed('SIGNED_OUT', null); return {}; },
          signInWithOAuth: async args => { window.oauthRequest = args; return {}; }
        },
        from: () => {
          let operation, filters = {}, value;
          const query = {
            select: () => { operation = 'select'; return query; },
            delete: () => { operation = 'delete'; return query; },
            upsert: row => { operation = 'insert'; value = row; return query; },
            eq: (key, val) => { filters[key] = val; return query; },
            order: () => query,
            range: () => query,
            then: resolve => {
              if (window.mockFail) return Promise.resolve({ error: new Error('network') }).then(resolve);
              const uid = filters.user_id || value?.user_id;
              if (uid !== session?.user.id) return Promise.resolve({ error: new Error('wrong account') }).then(resolve);
              rows[uid] ||= [];
              if (operation === 'insert' && !rows[uid].includes(value.item_id)) rows[uid].push(value.item_id);
              if (operation === 'delete') rows[uid] = rows[uid].filter(id => id !== filters.item_id);
              localStorage.setItem('mock-bookmarks', JSON.stringify(rows));
              return Promise.resolve({ data: rows[uid].map(item_id => ({ item_id })), error: null }).then(resolve);
            }
          };
          return query;
        }
      }) };
    });
    const page = await context.newPage();
    const origin = 'http://127.0.0.1:8080';
    await page.goto(origin);
    const button = page.locator('.bookmark').first();
    await button.waitFor();
    await page.waitForFunction(() => !document.querySelector('.bookmark').disabled);
    await button.click();
    await page.waitForFunction(() => document.querySelector('.bookmark').getAttribute('aria-pressed') === 'true');
    await page.goto(origin + '/bookmarks/');
    await page.locator('#bookmark-list article').waitFor();
    assert.equal(await page.locator('#bookmark-list article').count(), 1);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.reload();
    await page.locator('#bookmark-list article').waitFor();
    await page.evaluate(() => window.switchAccount('bob'));
    await page.waitForFunction(() => document.querySelector('#account-name').textContent.startsWith('bob'));
    await page.waitForFunction(() => document.querySelector('#bookmarks-message').textContent.includes('هنوز'));
    assert.equal(await page.locator('#bookmark-list article').count(), 0);
    await page.evaluate(() => window.switchAccount('alice'));
    await page.locator('#bookmark-list article').waitFor();
    await page.evaluate(() => { window.mockFail = true; });
    await page.locator('.bookmark').click();
    await page.waitForFunction(() => document.querySelector('#account-status').textContent.includes('تغییر ذخیره نشد'));
    assert.equal(await page.locator('#bookmark-list article').count(), 1);
    await page.evaluate(() => { window.mockFail = false; });
    await page.locator('.bookmark').click();
    await page.waitForFunction(() => document.querySelector('#bookmark-list').children.length === 0);
    await page.locator('#sign-out').click();
    await page.locator('#sign-in').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#account-name').textContent(), '');
    await page.locator('#sign-in').click();
    await page.waitForFunction(() => !!window.oauthRequest);
    const request = await page.evaluate(() => window.oauthRequest);
    assert.equal(request.provider, 'google');
    assert.equal(request.options.redirectTo, origin + '/auth/callback/');
    assert.equal(request.options.scopes, 'openid email profile');
    console.log('Bookmark UI: save, persistence, account switch, failed write, remove, logout and Google request passed (mock SDK).');
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
