(() => {
  'use strict';
  const config = window.DIDEBAN_AUTH || {};
  const login = document.getElementById('sign-in');
  const logout = document.getElementById('sign-out');
  const name = document.getElementById('account-name');
  const status = document.getElementById('account-status');
  const list = document.getElementById('bookmark-list');
  const message = document.getElementById('bookmarks-message');
  let client, session, catalog, sdkPromise;
  let generation = 0;
  let reading = 0;
  let loaded = false;
  let saved = new Set();
  let reactions = new Map();
  let reactionsLoaded = false;
  let reactionReading = 0;
  const reactionBusy = new Set();
  const busy = new Set();
  const configured = !!(config.url && config.publishableKey);

  function announce(text) {
    status.textContent = text;
    status.hidden = !text;
  }

  function loadSdk() {
    if (window.supabase) return Promise.resolve();
    if (!sdkPromise) sdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.84.0/dist/umd/supabase.js';
      script.integrity = 'sha384-i4FdG1ygjuBiZgSNBbyDvmEkKgU/3lQPFmJy2go+l/KwIrBeQKJsYfNIUapFapEM';
      script.crossOrigin = 'anonymous';
      const timer = setTimeout(() => script.onerror(), 15000);
      script.onload = () => { clearTimeout(timer); resolve(); };
      script.onerror = () => { clearTimeout(timer); script.remove(); sdkPromise = null; reject(new Error('sdk')); };
      document.head.append(script);
    });
    return sdkPromise;
  }

  async function getCatalog() {
    if (!catalog) {
      const response = await fetch('/items.json');
      if (!response.ok) throw new Error('catalog');
      catalog = await response.json();
    }
    return catalog;
  }

  function updateReactions() {
    document.querySelectorAll('.reaction').forEach(button => {
      button.setAttribute('aria-pressed', String(reactions.get(button.dataset.itemId) === Number(button.dataset.value)));
      button.disabled = reactionBusy.has(button.dataset.itemId) || (!!session && !reactionsLoaded);
      button.title = session ? 'برای پس‌گرفتن رأی، دوباره همین دکمه را بزنید.' : 'برای ثبت رأی با Google وارد شوید.';
    });
  }

  async function readReactions() {
    if (!session || !client) return;
    const epoch = generation, request = ++reactionReading, userId = session.user.id;
    try {
      const rows = [];
      for (let offset = 0; ; offset += 500) {
        const { data, error } = await client.from('item_reactions').select('item_id,value')
          .eq('user_id', userId).order('item_id').range(offset, offset + 499);
        if (error) throw error;
        rows.push(...data);
        if (data.length < 500) break;
      }
      if (epoch !== generation || request !== reactionReading) return;
      reactions = new Map(rows.map(row => [row.item_id, row.value]));
      reactionsLoaded = true;
      updateReactions();
    } catch {
      if (epoch === generation && request === reactionReading) announce('دریافت رأی‌ها انجام نشد. اتصال را بررسی و صفحه را دوباره باز کنید.');
    }
  }

  async function toggleReaction(button) {
    if (!session) { await signIn(); return; }
    const id = button.dataset.itemId;
    if (!reactionsLoaded || reactionBusy.has(id)) return;
    if (!navigator.onLine) { announce('برای ثبت رأی به اینترنت وصل شوید.'); return; }
    const epoch = generation, userId = session.user.id, value = Number(button.dataset.value);
    const removing = reactions.get(id) === value;
    reactionBusy.add(id);
    updateReactions();
    try {
      const query = client.from('item_reactions');
      const result = removing
        ? await query.delete().eq('user_id', userId).eq('item_id', id)
        : await query.upsert({ user_id: userId, item_id: id, value }, { onConflict: 'user_id,item_id' });
      if (result.error) throw result.error;
      if (epoch !== generation) return;
      // Invalidate an older in-flight read before applying this confirmed write.
      reactionReading++;
      if (removing) reactions.delete(id); else reactions.set(id, value);
      announce(removing ? 'رأی شما پس گرفته شد.' : 'رأی ثبت شد و در انتخاب گزارش‌های عمومی بعدی اثر می‌گذارد.');
    } catch {
      if (epoch === generation) announce('رأی ذخیره نشد. دوباره تلاش کنید.');
    } finally {
      if (epoch === generation) { reactionBusy.delete(id); updateReactions(); }
    }
  }

  function updateButtons() {
    updateReactions();
    document.querySelectorAll('.bookmark').forEach(button => {
      const id = button.dataset.itemId;
      const isSaved = saved.has(id);
      const label = isSaved ? 'حذف از ذخیره‌شده‌ها' : 'ذخیرهٔ مطلب';
      button.setAttribute('aria-label', label);
      button.title = label;
      button.setAttribute('aria-pressed', String(isSaved));
      button.disabled = busy.has(id) || (!!session && !loaded);
    });
  }

  function render() {
    if (login) login.hidden = !!session;
    if (logout) logout.hidden = !session;
    if (name) name.hidden = !session;
    if (name) name.textContent = session?.user.email || '';
    if (list) {
      list.replaceChildren();
      message.textContent = !session ? 'برای دیدن لیست اختصاصی خود وارد حساب Google شوید.'
        : !loaded ? 'در حال دریافت ذخیره‌شده‌ها…'
        : saved.size ? '' : 'هنوز مطلبی ذخیره نکرده‌اید.';
      if (session && loaded) for (const id of saved) {
        const item = catalog[id];
        const article = document.createElement('article');
        const wrapper = document.createElement('div');
        const title = document.createElement('h2');
        if (item) {
          const link = document.createElement('a');
          link.href = item.url;
          link.textContent = item.title;
          title.append(link);
          const summary = document.createElement('p');
          summary.textContent = item.summary;
          const meta = document.createElement('p');
          meta.className = 'bookmark-meta';
          meta.textContent = item.section + ' · ' + item.issue;
          wrapper.append(title, meta, summary);
        } else {
          title.textContent = 'این مطلب دیگر در آرشیو نیست.';
          wrapper.append(title);
        }
        const button = document.createElement('button');
        button.className = 'bookmark icon-action';
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        for (const [key, value] of Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.7', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' })) svg.setAttribute(key, value);
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', 'M6 3h12v18l-6-4-6 4Z');
        svg.append(path);
        button.append(svg);
        button.dataset.itemId = id;
        button.setAttribute('aria-label', 'حذف ' + (item?.title || 'مطلب از ذخیره‌شده‌ها'));
        wrapper.append(button);
        article.append(wrapper);
        list.append(article);
      }
    }
    updateButtons();
  }

  async function readBookmarks() {
    if (!session || !client) return;
    const epoch = generation;
    const request = ++reading;
    const userId = session.user.id;
    try {
      await getCatalog();
      const rows = [];
      for (let offset = 0; ; offset += 500) {
        const { data, error } = await client.from('bookmarks').select('item_id,created_at')
          .eq('user_id', userId).order('created_at', { ascending: false })
          .order('item_id').range(offset, offset + 499);
        if (error) throw error;
        rows.push(...data);
        if (data.length < 500) break;
      }
      if (epoch !== generation || request !== reading) return;
      saved = new Set(rows.map(row => row.item_id));
      loaded = true;
      announce('');
      render();
    } catch {
      if (epoch !== generation || request !== reading) return;
      announce(navigator.onLine ? 'دریافت ذخیره‌شده‌ها انجام نشد. دوباره تلاش کنید.' : 'برای دریافت لیست اختصاصی به اینترنت وصل شوید.');
      if (message) message.textContent = 'دریافت لیست انجام نشد.';
    }
  }

  function setSession(next) {
    const changedUser = session?.user.id !== next?.user.id;
    session = next;
    if (changedUser || !next) {
      generation++;
      saved.clear();
      reactions.clear();
      reactionsLoaded = false;
      reactionBusy.clear();
      loaded = false;
      busy.clear();
    }
    render();
    if (next) { void readBookmarks(); void readReactions(); }
  }

  async function signIn() {
    if (!configured) { announce('ورود به حساب هنوز توسط مدیر سایت فعال نشده است.'); return; }
    if (!navigator.onLine) { announce('برای ورود با Google به اینترنت وصل شوید.'); return; }
    if (login) login.disabled = true;
    try {
      if (!client) await initialize();
      const settings = await fetch(config.url + '/auth/v1/settings', { headers: { apikey: config.publishableKey } });
      if (!settings.ok) throw new Error('settings');
      if (!(await settings.json()).external?.google) {
        announce('ورود با Google هنوز توسط مدیر سایت فعال نشده است.');
        return;
      }
      sessionStorage.setItem('dideban-return', location.pathname + location.hash);
      const { error } = await client.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: location.origin + '/auth/callback/', scopes: 'openid email profile' }
      });
      if (error) throw error;
    } catch {
      announce('ورود انجام نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.');
    } finally { if (login) login.disabled = false; }
  }

  async function toggleBookmark(button) {
    const id = button.dataset.itemId;
    if (!session) { await signIn(); return; }
    if (!loaded || busy.has(id)) return;
    if (!navigator.onLine) { announce('برای تغییر ذخیره‌شده‌ها به اینترنت وصل شوید.'); return; }
    const userId = session.user.id;
    const epoch = generation;
    const removing = saved.has(id);
    busy.add(id);
    updateButtons();
    try {
      const query = client.from('bookmarks');
      const result = removing
        ? await query.delete().eq('user_id', userId).eq('item_id', id)
        : await query.upsert({ user_id: userId, item_id: id }, { onConflict: 'user_id,item_id', ignoreDuplicates: true });
      if (result.error) throw result.error;
      if (epoch !== generation) return;
      announce(removing ? 'مطلب از ذخیره‌شده‌ها حذف شد.' : 'مطلب در حساب شما ذخیره شد.');
      await readBookmarks();
    } catch {
      if (epoch === generation) announce('تغییر ذخیره نشد. دوباره تلاش کنید.');
    } finally {
      if (epoch === generation) { busy.delete(id); updateButtons(); }
    }
  }

  let initialization;
  function initialize() {
    if (initialization) return initialization;
    initialization = (async () => {
      await loadSdk();
      client = window.supabase.createClient(config.url, config.publishableKey, {
        auth: { flowType: 'pkce', detectSessionInUrl: false, persistSession: true, autoRefreshToken: true }
      });
      client.auth.onAuthStateChange((_event, next) => {
        setTimeout(() => setSession(next), 0);
      });
      if (location.pathname === '/auth/callback/') {
        const params = new URLSearchParams(location.search);
        history.replaceState(null, '', '/auth/callback/');
        if (params.has('error')) throw new Error('cancelled');
        const code = params.get('code');
        if (!code) throw new Error('missing-code');
        const { error } = await client.auth.exchangeCodeForSession(code);
        if (error) throw error;
        const target = sessionStorage.getItem('dideban-return') || '/bookmarks/';
        sessionStorage.removeItem('dideban-return');
        location.replace(target.startsWith('/') && !target.startsWith('//') && !target.includes('\\') && !target.startsWith('/auth/') ? target : '/bookmarks/');
        return;
      }
      const { data, error } = await client.auth.getSession();
      if (error) throw error;
      setSession(data.session);
    })().catch(error => {
      initialization = null;
      announce('ارتباط با حساب انجام نشد. دوباره با Google وارد شوید.');
      throw error;
    });
    return initialization;
  }

  login?.addEventListener('click', signIn);
  logout?.addEventListener('click', async () => {
    logout.disabled = true;
    try {
      const { error } = await client.auth.signOut({ scope: 'local' });
      if (error) throw error;
      setSession(null);
      announce('از حساب خارج شدید.');
    } catch { announce('خروج انجام نشد. دوباره تلاش کنید.'); }
    finally { logout.disabled = false; }
  });
  document.addEventListener('click', event => {
    const reaction = event.target.closest('.reaction');
    if (reaction) void toggleReaction(reaction);
    const button = event.target.closest('.bookmark');
    if (button) void toggleBookmark(button);
  });
  window.addEventListener('online', () => { if (session) { void readBookmarks(); void readReactions(); } else if (configured) void initialize().catch(() => {}); });
  render();
  if (configured) void initialize().catch(() => {});
})();
