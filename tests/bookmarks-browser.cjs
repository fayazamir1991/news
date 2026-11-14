const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : { channel: 'chrome' });
  try {
    const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 390, height: 844 } });
    await context.route('**/auth/v1/settings', route => route.fulfill({ json: { external: { google: true } } }));
    await context.addInitScript(() => {
      const user = id => ({ user: { id, email: id + '@example.test' } });
      let session = user(localStorage.getItem('mock-user') || 'alice');
      const rows = JSON.parse(localStorage.getItem('mock-bookmarks') || '{}');
      const votes = JSON.parse(localStorage.getItem('mock-reactions') || '{}');
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
        from: table => {
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
              if (table === 'item_reactions') {
                votes[uid] ||= {};
                if (operation === 'insert') votes[uid][value.item_id] = value.value;
                if (operation === 'delete') delete votes[uid][filters.item_id];
                localStorage.setItem('mock-reactions', JSON.stringify(votes));
                return Promise.resolve({ data: Object.entries(votes[uid]).map(([item_id,value]) => ({item_id,value})), error:null }).then(resolve);
              }
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
    const like = page.locator('.reaction[data-value="1"]').first();
    const dislike = page.locator('.reaction[data-value="-1"]').first();
    await page.waitForFunction(() => !document.querySelector('.reaction').disabled);
    await like.click();
    await page.waitForFunction(() => document.querySelector('.reaction[data-value="1"]').getAttribute('aria-pressed') === 'true');
    await dislike.click();
    await page.waitForFunction(() => document.querySelector('.reaction[data-value="-1"]').getAttribute('aria-pressed') === 'true');
    assert.equal(await like.getAttribute('aria-pressed'), 'false');
    await page.reload();
    await page.waitForFunction(() => document.querySelector('.reaction[data-value="-1"]').getAttribute('aria-pressed') === 'true');
    await page.evaluate(() => window.switchAccount('bob'));
    await page.waitForFunction(() => !document.querySelector('.reaction').disabled);
    assert.equal(await dislike.getAttribute('aria-pressed'), 'false');
    await page.evaluate(() => window.switchAccount('alice'));
    await page.waitForFunction(() => document.querySelector('.reaction[data-value="-1"]').getAttribute('aria-pressed') === 'true');
    await page.evaluate(() => { window.mockFail = true; });
    await like.click();
    await page.waitForFunction(() => document.querySelector('#account-status').textContent.includes('رأی ذخیره نشد'));
    assert.equal(await dislike.getAttribute('aria-pressed'), 'true');
    await page.evaluate(() => { window.mockFail = false; });
    await context.setOffline(true);
    await like.click();
    assert.equal(await dislike.getAttribute('aria-pressed'), 'true');
    await context.setOffline(false);
    await page.waitForFunction(() => !document.querySelector('.reaction').disabled);
    await dislike.click();
    await page.waitForFunction(() => document.querySelector('.reaction[data-value="-1"]').getAttribute('aria-pressed') === 'false');
    const button = page.locator('.bookmark').first();
    await button.waitFor();
    await page.waitForFunction(() => !document.querySelector('.bookmark').disabled);
    assert.equal(await button.innerText(), '');
    assert.equal(await button.locator('svg').count(), 1);
    const bounds = await page.locator('.item-actions').first().locator('button').evaluateAll(nodes => nodes.map(n => { const b=n.getBoundingClientRect(); return {y:b.y,w:b.width,h:b.height}; }));
    assert.equal(bounds.length, 3);
    assert(bounds.every(b => b.y === bounds[0].y && b.w >= 44 && b.h >= 44));
    await button.click();
    await page.waitForFunction(() => document.querySelector('.bookmark').getAttribute('aria-pressed') === 'true');
    await page.goto(origin + '/bookmarks/');
    await page.locator('#bookmark-list article').waitFor();
    assert.equal(await page.locator('#bookmark-list article').count(), 1);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.reload();
    await page.locator('#bookmark-list article').waitFor();
    await page.evaluate(() => window.switchAccount('bob'));
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
    // Use an archived issue with a survey, even when the latest issue has none.
    await page.goto(origin + '/issues/1405-08-21/');
    const surveyButton = page.locator('#survey .bookmark');
    const surveyId = await surveyButton.getAttribute('data-item-id');
    await page.waitForFunction(() => !document.querySelector('#survey .bookmark').disabled);
    await surveyButton.click();
    await page.waitForFunction(() => document.querySelector('#survey .bookmark').getAttribute('aria-pressed') === 'true');
    await page.locator('#survey .reaction[data-value="1"]').click();
    await page.waitForFunction(() => document.querySelector('#survey .reaction[data-value="1"]').getAttribute('aria-pressed') === 'true');
    await page.locator('#survey a.survey-link').click();
    await page.waitForFunction(() => document.querySelector('.bookmark').getAttribute('aria-pressed') === 'true');
    assert.equal(await page.locator('.bookmark').getAttribute('data-item-id'), surveyId);
    await page.waitForFunction(() => document.querySelector('.reaction[data-value="1"]').getAttribute('aria-pressed') === 'true');
    await page.goto(origin + '/account/');
    await page.locator('#sign-out').click();
    await page.locator('#sign-in').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#account-name').textContent(), '');
    await page.locator('#sign-in').click();
    await page.waitForFunction(() => !!window.oauthRequest);
    const request = await page.evaluate(() => window.oauthRequest);
    assert.equal(request.provider, 'google');
    assert.equal(request.options.redirectTo, origin + '/auth/callback/');
    assert.equal(request.options.scopes, 'openid email profile');
    await page.goto(origin);
    await page.evaluate(() => window.switchAccount(null));
    await page.locator('.reaction').first().click();
    await page.waitForFunction(() => !!window.oauthRequest);
    console.log('Bookmark and feedback UI: vote, replace, retract, offline, failed vote, survey identity, save, persistence, account switch, failed write, remove, logout and Google request passed (mock SDK).');
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
