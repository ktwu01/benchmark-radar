/* Shared navigation owns route styling; each data surface owns its filters. */
(() => {
  'use strict';
  const header = document.querySelector('.site-header');
  const isChinese = () => document.documentElement.lang.startsWith('zh');
  const labels = [
    ['agents', 'Agent systems', 'Agent 系统'],
    ['coding', 'Coding', '代码与工程'],
    ['reasoning', 'Reasoning & knowledge', '推理与知识'],
    ['multimodal', 'Multimodal', '多模态']
  ];
  let counts = null;

  function syncNavigation() {
    const section = location.pathname.split('/').filter(Boolean)[0] || 'today';
    const active = section === 'benchmarks' ? 'explore' : ['today', 'explore', 'leaderboard', 'saturation', 'trends'].includes(section) ? section : 'resources';
    header?.querySelectorAll('[data-route]').forEach(item => {
      const current = item.dataset.route === active;
      item.dataset.active = String(current);
      if (current) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });
  }

  function translate() {
    const zh = isChinese();
    document.querySelectorAll('[data-study-en]').forEach(node => {
      node.textContent = node.getAttribute(zh ? 'data-study-zh' : 'data-study-en');
    });
    const toggle = document.getElementById('lang-toggle');
    const languageLabel = document.getElementById('lang-toggle-label');
    if (languageLabel) languageLabel.textContent = zh ? 'EN' : '中';
    if (toggle) {
      const label = zh ? 'Switch to English' : '切换为中文';
      toggle.setAttribute('aria-label', label);
      toggle.title = label;
      toggle.setAttribute('aria-pressed', String(zh));
    }
    const contact = document.getElementById('badge-contact');
    if (contact) {
      contact.title = zh ? '联系项目' : 'Contact';
      contact.setAttribute('aria-label', contact.title);
    }
    renderLauncher();
  }

  function renderLauncher() {
    document.querySelectorAll('.study-field-launcher').forEach(host => {
      host.replaceChildren(...labels.map(([id, en, zh]) => {
        const link = document.createElement('a');
        link.href = '/explore/#field=' + id + (isChinese() ? '&lang=zh' : '');
        const name = document.createElement('span');
        name.className = 'launch-name';
        name.textContent = isChinese() ? zh : en;
        link.append(name);
        const count = document.createElement('span');
        count.className = 'launch-count';
        count.textContent = counts ? counts[id].toLocaleString() : '—';
        const unit = document.createElement('span');
        unit.textContent = isChinese() ? '目录记录' : 'in catalog';
        count.append(unit);
        link.append(count);
        return link;
      }));
    });
  }

  syncNavigation();
  translate();
  new MutationObserver(translate).observe(document.documentElement, {attributes: true, attributeFilter: ['lang']});
  window.addEventListener('radar:routechange', syncNavigation);
  window.addEventListener('popstate', syncNavigation);
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('.study-resources[open]').forEach(menu => {
      menu.open = false;
      menu.querySelector('summary').focus();
    });
  });
  document.addEventListener('click', event => {
    document.querySelectorAll('.study-resources[open]').forEach(menu => {
      if (!menu.contains(event.target) || event.target.closest('a')) menu.open = false;
    });
  });

  if (!document.getElementById('today-view')) {
    document.getElementById('badge-contact')?.addEventListener('click', () => location.assign('/#contact'));
  }
  if (document.body.matches('.record-page, .logos-page')) {
    try { document.documentElement.lang = localStorage.getItem('benchmark-radar:lang') === 'zh' ? 'zh-CN' : 'en'; } catch {}
    document.getElementById('lang-toggle')?.addEventListener('click', () => {
      const lang = isChinese() ? 'en' : 'zh';
      document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
      try { localStorage.setItem('benchmark-radar:lang', lang); } catch {}
    });
  }
  if (document.getElementById('radar-explorer')) {
    try {
      const params = new URLSearchParams(location.hash.slice(1));
      if (!params.has('lang') && localStorage.getItem('benchmark-radar:lang') === 'zh') {
        params.set('lang', 'zh');
        history.replaceState(null, '', location.pathname + '#' + params);
        window.dispatchEvent(new HashChangeEvent('hashchange'));
      }
    } catch { /* Language remains available in the shared header. */ }
  }
  if (document.querySelector('.study-field-launcher')) {
    import('/assets/fields.js').then(async ({recordFields}) => {
      const response = await fetch('/data/benchmark-index.json');
      if (!response.ok) throw new Error('Catalog unavailable');
      const payload = await response.json();
      counts = Object.fromEntries(labels.map(([id]) => [id, 0]));
      payload.benchmarks.forEach(record => recordFields(record).forEach(field => {
        if (field in counts) counts[field]++;
      }));
      renderLauncher();
    }).catch(() => { /* Unavailable counts stay unknown; navigation stays usable. */ });
  }
})();
