/* =====================================================================
   InternMatch AI — reusable UI components (badges, rings, states, charts)
   ===================================================================== */
const UI = (() => {
  const BADGE_META = {
    Green: { cls: 'badge-green', icon: 'bi-shield-fill-check', label: 'Verified' },
    Amber: { cls: 'badge-amber', icon: 'bi-shield-exclamation', label: 'Caution' },
    Red: { cls: 'badge-red', icon: 'bi-shield-fill-x', label: 'High risk' },
  };

  function badgeMeta(badge, flagged) {
    if (flagged && badge !== 'Red') return { cls: 'badge-red', icon: 'bi-flag-fill', label: 'Flagged' };
    return BADGE_META[badge] || BADGE_META.Amber;
  }

  function trustBadge(badge, score, flagged, extra = '') {
    const m = badgeMeta(badge, flagged);
    const scoreTxt = (score !== undefined && score !== null) ? ` ${score}` : '';
    return `<span class="badge-trust ${m.cls} ${extra}" title="Trust score ${score}/100 — ${m.label}">
              <i class="bi ${m.icon}"></i>${escapeHtml(badge || 'Amber')}${scoreTxt}</span>`;
  }

  function trustRing(score, badge, size = '') {
    const pct = Math.max(0, Math.min(100, Number(score) || 0));
    const r = 46, c = 2 * Math.PI * r;
    const offset = c - (pct / 100) * c;
    const colors = { Green: '#0f9d58', Amber: '#f59e0b', Red: '#dc2626' };
    const color = colors[badge] || '#4f46e5';
    return `<div class="trust-ring ${size}" data-score="${pct}">
      <svg width="100%" height="100%" viewBox="0 0 108 108">
        <circle class="ring-track" cx="54" cy="54" r="${r}" fill="none" stroke-width="9"></circle>
        <circle class="ring-value" cx="54" cy="54" r="${r}" fill="none" stroke="${color}"
                stroke-width="9" stroke-linecap="round"
                stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${c.toFixed(1)}"
                data-target="${offset.toFixed(1)}"></circle>
      </svg>
      <div class="ring-center">
        <div class="ring-score" style="color:${color}">${pct}</div>
        <div class="ring-cap">Trust</div>
      </div>
    </div>`;
  }

  function animateRings(root = document) {
    root.querySelectorAll('.trust-ring .ring-value').forEach((el) => {
      const target = el.getAttribute('data-target');
      requestAnimationFrame(() => { el.style.strokeDashoffset = target; });
    });
  }

  function matchBar(pct) {
    return `<div class="match-bar"><span style="width:0%" data-w="${pct}"></span></div>`;
  }
  function animateBars(root = document) {
    root.querySelectorAll('.match-bar > span[data-w]').forEach((el) => {
      requestAnimationFrame(() => { el.style.width = `${el.getAttribute('data-w')}%`; });
    });
  }

  function statusPill(status) {
    const label = (status || 'applied').replace(/_/g, ' ');
    return `<span class="status-pill status-${status}">${escapeHtml(label)}</span>`;
  }

  function skeletonCards(n = 6, cols = 'col-md-6 col-xl-4') {
    let html = '';
    for (let i = 0; i < n; i++) {
      html += `<div class="${cols}"><div class="card listing-card h-100"><div class="card-body">
        <div class="d-flex gap-3 mb-3">
          <div class="skeleton" style="width:44px;height:44px;border-radius:12px"></div>
          <div class="flex-grow-1"><div class="skeleton skeleton-line w-75"></div>
          <div class="skeleton skeleton-line w-50 mb-0"></div></div>
        </div>
        <div class="skeleton skeleton-line"></div>
        <div class="skeleton skeleton-line w-75"></div>
        <div class="skeleton skeleton-line w-30"></div>
        <div class="skeleton" style="height:34px;border-radius:10px;margin-top:1rem"></div>
      </div></div></div>`;
    }
    return html;
  }

  function skeletonRows(n = 6, cols = 6) {
    let html = '';
    for (let i = 0; i < n; i++) {
      html += '<tr>';
      for (let j = 0; j < cols; j++) {
        html += `<td><div class="skeleton skeleton-line ${j === 0 ? '' : 'w-75'} mb-0"></div></td>`;
      }
      html += '</tr>';
    }
    return html;
  }

  function loading(container, message = 'Loading…', height = '220px') {
    const el = typeof container === 'string' ? document.querySelector(container) : container;
    if (!el) return;
    el.innerHTML = `<div class="spinner-wrap" style="min-height:${height}">
      <div class="spinner-border text-primary" role="status" style="width:2rem;height:2rem"></div>
      <div class="text-muted-soft small">${escapeHtml(message)}</div></div>`;
  }

  function emptyState({ title = 'Nothing here yet', message = '', icon = 'bi-inbox',
                        ctaLabel = '', ctaHref = '', ctaId = '' } = {}) {
    const cta = ctaLabel
      ? `<a class="btn btn-gradient" ${ctaId ? `id="${ctaId}"` : ''} ${ctaHref ? `href="${ctaHref}"` : ''}>
           <i class="bi bi-arrow-right me-1"></i>${escapeHtml(ctaLabel)}</a>`
      : '';
    return `<div class="empty-state">
      <div class="icon"><i class="bi ${icon}"></i></div>
      <h5>${escapeHtml(title)}</h5>
      ${message ? `<p>${escapeHtml(message)}</p>` : ''}${cta}</div>`;
  }

  function errorState(container, message, retryFn) {
    const el = typeof container === 'string' ? document.querySelector(container) : container;
    el.innerHTML = `<div class="empty-state">
      <div class="icon" style="background:#fdeaea;color:#dc2626"><i class="bi bi-wifi-off"></i></div>
      <h5>Couldn't load this</h5><p>${escapeHtml(message)}</p>
      ${retryFn ? '<button class="btn btn-soft" data-retry><i class="bi bi-arrow-clockwise me-1"></i>Retry</button>' : ''}
    </div>`;
    if (retryFn) el.querySelector('[data-retry]')?.addEventListener('click', retryFn);
  }

  function renderPagination(el, meta, onPage) {
    const node = typeof el === 'string' ? document.querySelector(el) : el;
    if (!node || !meta || meta.pages <= 1) { if (node) node.innerHTML = ''; return; }
    const { page, pages } = meta;
    const btn = (label, target, disabled, active = false) =>
      `<li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}">
         <button class="page-link" data-page="${target}" ${disabled ? 'disabled' : ''}>${label}</button></li>`;
    let items = '';
    const start = Math.max(1, page - 2), end = Math.min(pages, start + 4);
    for (let p = start; p <= end; p++) items += btn(p, p, false, p === page);
    node.innerHTML = `<nav class="d-flex align-items-center justify-content-between flex-wrap gap-2">
      <span class="text-muted-soft text-tiny">Page ${page} of ${pages} · ${fmt.num(meta.total)} records</span>
      <ul class="pagination pagination-sm mb-0">
        ${btn('<i class="bi bi-chevron-left"></i>', page - 1, !meta.has_prev)}
        ${items}
        ${btn('<i class="bi bi-chevron-right"></i>', page + 1, !meta.has_next)}
      </ul></nav>`;
    node.querySelectorAll('[data-page]').forEach(b => b.addEventListener('click', () => {
      const p = Number(b.getAttribute('data-page'));
      if (p >= 1 && p <= pages && p !== page) onPage(p);
    }));
  }

  function skillCloud(items, limit = 40) {
    if (!items || !items.length) return '';
    return `<div class="tag-cloud">` + items.slice(0, limit).map(s => {
      const cat = (s.category || 'Other').replace(/\s+/g, '-');
      const size = Math.max(12, Math.min(30, s.size || (12 + (s.weight || 0) * 16)));
      const title = `${s.skill} · ${s.category || ''} · weight ${(s.weight ?? 0)}`;
      return `<span class="skill-tag cat-${cat}" style="font-size:${size}px" title="${escapeHtml(title)}">
        ${escapeHtml(s.skill)}</span>`;
    }).join('') + `</div>`;
  }

  function chartDefaults() {
    if (typeof Chart === 'undefined') return;
    Chart.defaults.font.family = '"Inter", system-ui, sans-serif';
    Chart.defaults.font.size = 11.5;
    Chart.defaults.color = '#6b7590';
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.padding = 14;
    Chart.defaults.maintainAspectRatio = false;
  }

  function destroyChart(registry, key) {
    if (registry[key]) { registry[key].destroy(); delete registry[key]; }
  }

  function sparkline(ctx, values, color = '#4f46e5') {
    return new Chart(ctx, {
      type: 'line',
      data: { labels: values.map((_, i) => i + 1),
              datasets: [{ data: values, borderColor: color, borderWidth: 2, tension: .4,
                           pointRadius: 0, fill: true,
                           backgroundColor: 'rgba(79,70,229,.08)' }] },
      options: { plugins: { legend: { display: false }, tooltip: { enabled: false } },
                 scales: { x: { display: false }, y: { display: false } },
                 elements: { line: { borderJoinStyle: 'round' } } },
    });
  }

  function confirmModal({ title, body, confirmLabel = 'Confirm', variant = 'primary' }) {
    return new Promise((resolve) => {
      const id = 'im-confirm-' + Date.now();
      const html = `<div class="modal fade" id="${id}" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content">
            <div class="modal-header"><h6 class="modal-title">${escapeHtml(title)}</h6>
              <button class="btn-close" data-bs-dismiss="modal"></button></div>
            <div class="modal-body small text-muted-soft">${body}</div>
            <div class="modal-footer">
              <button class="btn btn-light btn-sm" data-bs-dismiss="modal">Cancel</button>
              <button class="btn btn-${variant} btn-sm" data-confirm>${escapeHtml(confirmLabel)}</button>
            </div></div></div></div>`;
      document.body.insertAdjacentHTML('beforeend', html);
      const el = document.getElementById(id);
      const modal = new bootstrap.Modal(el);
      let result = false;
      el.querySelector('[data-confirm]').addEventListener('click', () => { result = true; modal.hide(); });
      el.addEventListener('hidden.bs.modal', () => { el.remove(); resolve(result); });
      modal.show();
    });
  }

  return { trustBadge, trustRing, animateRings, matchBar, animateBars, statusPill,
           skeletonCards, skeletonRows, loading, emptyState, errorState, renderPagination,
           skillCloud, chartDefaults, destroyChart, sparkline, confirmModal, badgeMeta };
})();
