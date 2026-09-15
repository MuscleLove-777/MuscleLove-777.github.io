(() => {
  document.documentElement.classList.add('ml-js');
  const menu = document.querySelector('.ml-menu');
  const nav = document.querySelector('.ml-nav-links');
  menu?.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(open));
    menu.textContent = open ? '閉じる' : 'メニュー';
    nav?.classList.toggle('is-open', open);
  });
  const tools = document.querySelector('.ml-tools');
  const stories = [...document.querySelectorAll('.ml-story')];
  const input = document.querySelector('#ml-search');
  const count = document.querySelector('#ml-result-count');
  let selected = 'all';
  function filter() {
    const query = (input?.value || '').normalize('NFKC').trim().toLocaleLowerCase('ja');
    let visible = 0;
    for (const story of stories) {
      const matches = (selected === 'all' || story.dataset.category === selected) &&
        story.textContent.normalize('NFKC').toLocaleLowerCase('ja').includes(query);
      story.hidden = !matches;
      if (matches) visible++;
    }
    if (count) count.textContent = `${visible} / ${stories.length} 件の記事`;
    const empty = document.querySelector('.ml-empty');
    if (empty) empty.hidden = visible !== 0;
  }
  if (tools) tools.hidden = false;
  document.querySelectorAll('.ml-filter').forEach(button => button.addEventListener('click', () => {
    selected = button.dataset.filter;
    document.querySelectorAll('.ml-filter').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    filter();
  }));
  input?.addEventListener('input', filter);
  filter();
  // A local cover remains available even if an older article's remote image fails.
  document.querySelectorAll('img[data-ml-fallback]').forEach(img => {
    const fallback = () => {
      const src = img.dataset.mlFallback;
      if (!src) return;
      delete img.dataset.mlFallback;
      img.removeAttribute('srcset');
      img.src = src;
    };
    img.addEventListener('error', fallback, {once:true});
    if (img.complete && !img.naturalWidth) fallback();
  });
  if (!window.__mlRevenueCtaTracking) {
    window.__mlRevenueCtaTracking = true;
    document.addEventListener('click', event => {
      const link = event.target.closest?.('a[data-ml-revenue-cta]');
      if (!link || typeof window.gtag !== 'function') return;
      window.gtag('event', 'ml_revenue_cta_click', {
        event_category:'revenue_cta', event_label:link.dataset.mlRevenueCta,
        destination_url:link.href, source_path:location.pathname, transport_type:'beacon'
      });
    }, true);
  }
})();
