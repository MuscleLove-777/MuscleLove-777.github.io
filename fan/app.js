(() => {
  const choices = {
    look: {label: '作品を眺める', href: '/patreon/', copy: 'まずは公開ギャラリーへ。筋肉美のオリジナル作品からどうぞ。'},
    play: {label: '無料ゲームで遊ぶ', href: '/games/', copy: 'インストール不要。ブラウザですぐ遊べるゲームへどうぞ。'},
    know: {label: '筋肉・フィットネス記事を読む', href: '/network/fitness/', copy: '競技、食事、鍛え方の読みものをテーマ別に探せます。'}
  };
  const result = document.querySelector('#finder-result');
  document.querySelectorAll('[data-mood]').forEach((button) => {
    button.addEventListener('click', () => {
      const choice = choices[button.dataset.mood];
      if (!choice || !result) return;
      document.querySelectorAll('[data-mood]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
      result.innerHTML = `<span>YOUR ROUTE</span><p>${choice.copy} <a href="${choice.href}">${choice.label} ↗</a></p>`;
    });
  });
  if (!window.__mlRevenueCtaTracking) {
    window.__mlRevenueCtaTracking = true;
    document.addEventListener('click', (event) => {
      const link = event.target.closest?.('a[data-ml-revenue-cta]');
      if (!link || typeof window.gtag !== 'function') return;
      window.gtag('event', 'ml_revenue_cta_click', {event_category: 'revenue_cta', event_label: link.dataset.mlRevenueCta, destination_url: link.href, source_path: location.pathname, transport_type: 'beacon'});
    }, true);
  }
})();
