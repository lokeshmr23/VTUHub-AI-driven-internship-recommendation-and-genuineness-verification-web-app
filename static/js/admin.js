/* =====================================================================
   InternMatch AI — admin pages
   ===================================================================== */
const Admin = (() => {
  const charts = {};
  let domainOptions = [];

  /* ------------------------------------------------------------ helpers */
  async function guard() {
    const user = await IM.guard('admin');
    if (!user) return null;
    IM.mountChrome(user);
    refreshFlagBadge();
    return user;
  }

  async function refreshFlagBadge() {
    try {
      const d = await api('/api/admin/flagged?per_page=1');
      const badge = document.getElementById('flaggedCount');
      if (badge && d.summary) {
        badge.textContent = d.summary.total_flagged;
        badge.style.display = d.summary.total_flagged ? 'inline-block' : 'none';
      }
      return d.summary;
    } catch { return null; }
  }

  function setKpis(kpis) {
    Object.entries(kpis).forEach(([key, value]) => {
      document.querySelectorAll(`[data-kpi="${key}"]`).forEach(el => {
        el.textContent = key.includes('rate') ? `${value}%` : value;
      });
    });
    const subs = {
      posted: `avg trust ${kpis.avg_trust_score}`,
      flagged_listings: `${kpis.flagged_listings} listings flagged`,
      students: `${kpis.students} students`,
    };
    Object.entries(subs).forEach(([k, v]) => {
      document.querySelectorAll(`[data-kpi-sub="${k}"]`).forEach(el => { el.textContent = v; });
    });
  }

  function trustCell(L) {
    return `<div class="d-flex align-items-center gap-2">
      ${UI.trustBadge(L.badge, L.trust_score, L.fraud_flag)}
      <div style="width:52px">${UI.matchBar(L.trust_score)}</div></div>`;
  }

  function redFlagChips(flags, limit = 2) {
    if (!flags || !flags.length) return '<span class="badge-ghost">clean</span>';
    return flags.slice(0, limit).map(f =>
      `<span class="badge-trust badge-red" title="${escapeHtml(f.evidence || '')}">
        <i class="bi bi-exclamation-triangle-fill"></i>${escapeHtml(f.label.slice(0, 26))}</span>`).join('') +
      (flags.length > limit ? `<span class="badge-ghost">+${flags.length - limit}</span>` : '');
  }

  /* ---------------------------------------------------------- dashboard */
  async function initDashboard() {
    if (!(await guard())) return;
    try {
      const d = await api('/api/admin/analytics');
      setKpis(d.kpis);

      UI.destroyChart(charts, 'band');
      charts.band = new Chart(document.getElementById('bandChart'), {
        type: 'bar',
        data: { labels: Object.keys(d.score_bands),
          datasets: [{ label: 'Listings', data: Object.values(d.score_bands),
            backgroundColor: ['#dc2626', '#ef4444', '#f59e0b', '#fbbf24', '#34d399', '#0f9d58'],
            borderRadius: 8 }] },
        options: { plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, grid: { color: '#eef1f7' } },
                    x: { grid: { display: false } } } },
      });

      UI.destroyChart(charts, 'badge');
      charts.badge = new Chart(document.getElementById('badgeChart'), {
        type: 'doughnut',
        data: { labels: ['Green', 'Amber', 'Red'],
          datasets: [{ data: [d.badge_distribution.Green, d.badge_distribution.Amber,
            d.badge_distribution.Red], backgroundColor: ['#0f9d58', '#f59e0b', '#dc2626'],
            borderWidth: 0, cutout: '66%' }] },
        options: { plugins: { legend: { position: 'bottom' } } },
      });

      UI.destroyChart(charts, 'trend');
      charts.trend = new Chart(document.getElementById('trendChart'), {
        type: 'line',
        data: { labels: d.posting_trend.map(p => p.label),
          datasets: [
            { label: 'Posted', data: d.posting_trend.map(p => p.posted),
              borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,.12)',
              fill: true, tension: .4, borderWidth: 2, pointRadius: 2 },
            { label: 'Flagged', data: d.posting_trend.map(p => p.flagged),
              borderColor: '#dc2626', backgroundColor: 'rgba(220,38,38,.10)',
              fill: true, tension: .4, borderWidth: 2, pointRadius: 2 }] },
        options: { plugins: { legend: { position: 'bottom' } },
          scales: { y: { beginAtZero: true, grid: { color: '#eef1f7' } },
                    x: { grid: { display: false } } } },
      });

      // top flags list
      document.getElementById('topFlagsBox').innerHTML = d.top_flags.length
        ? d.top_flags.map((f, i) => `
            <div class="d-flex align-items-center gap-2 mb-2">
              <span class="badge-ghost">${i + 1}</span>
              <div class="flex-grow-1">
                <div class="small fw-semibold">${escapeHtml(f.label)}</div>
                <div style="height:6px;border-radius:999px;background:#eef1f7;overflow:hidden">
                  <div style="width:${Math.round(f.count / d.top_flags[0].count * 100)}%;height:100%;
                    background:linear-gradient(90deg,#dc2626,#f59e0b)"></div></div>
              </div>
              <span class="fw-800">${f.count}</span></div>`).join('')
        : UI.emptyState({ title: 'No flags detected', icon: 'bi-shield-check',
            message: 'Every published listing currently passes the trust rules.' });

      // ML card
      const m = d.ml_model || {};
      document.getElementById('mlBox').innerHTML = `
        <div class="row g-3">
          <div class="col-6"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Train accuracy</div>
            <div class="fw-800 fs-4">${((m.train_accuracy || 0) * 100).toFixed(1)}%</div></div>
          <div class="col-6"><div class="text-muted-soft text-tiny text-uppercase fw-bold">ROC AUC</div>
            <div class="fw-800 fs-4">${(m.roc_auc || 0).toFixed(3)}</div></div>
          <div class="col-6"><div class="text-muted-soft text-tiny text-uppercase fw-bold">F1 score</div>
            <div class="fw-800 fs-4">${(m.f1 || 0).toFixed(3)}</div></div>
          <div class="col-6"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Training rows</div>
            <div class="fw-800 fs-4">${m.samples || 0}</div></div>
        </div>
        <div class="divider-y"></div>
        <div class="small text-muted-soft mb-2">${escapeHtml(m.features || '')}</div>
        <div class="d-flex gap-2">
          <button class="btn btn-soft btn-sm" id="retrainDash"><i class="bi bi-cpu me-1"></i>Retrain model</button>
          <span class="text-muted-soft text-tiny align-self-center">Thresholds: Green ≥${d.trust_thresholds.green} ·
            flag &lt;${d.trust_thresholds.flag}</span>
        </div>`;
      document.getElementById('retrainDash').onclick = (e) => retrain(e.currentTarget, () => initDashboard());

      // worst listings
      const worst = await api('/api/admin/internships?sort=trust_asc&per_page=6');
      document.getElementById('worstBody').innerHTML = worst.internships.map(L => `
        <tr class="cursor-pointer" onclick="location.href='/student/internship/${L.id}'">
          <td><div class="fw-semibold text-truncate" style="max-width:220px">${escapeHtml(L.title)}</div>
            <div class="text-muted-soft text-tiny">${escapeHtml(L.company)}</div></td>
          <td>${UI.trustBadge(L.badge, L.trust_score, L.fraud_flag)}</td></tr>`).join('');

      const btn = document.getElementById('recomputeAllBtn');
      if (btn) btn.onclick = () => recomputeAll(btn, () => initDashboard());
      UI.animateBars();
    } catch (err) {
      UI.errorState('#topFlagsBox', err.message);
      toast(err.message, 'error');
    }
  }

  async function retrain(btn, after) {
    btn.disabled = true;
    const original = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Training…';
    try {
      const res = await api('/api/admin/ml/retrain', { method: 'POST' });
      toast(res.message, 'success', 5200);
      after && after();
    } catch (err) { toast(err.message, 'error'); }
    finally { btn.disabled = false; btn.innerHTML = original; }
  }

  async function recomputeAll(btn, after) {
    const ok = await UI.confirmModal({ title: 'Re-score every listing?',
      body: 'Runs domain checks, red-flag analysis and the ML classifier across the whole catalogue.',
      confirmLabel: 'Re-score all' });
    if (!ok) return;
    btn.disabled = true;
    const original = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Scoring…';
    try {
      const res = await api('/api/admin/trustscore/recompute-all', { method: 'POST' });
      toast(res.message, 'success', 5000);
      after && after();
    } catch (err) { toast(err.message, 'error'); }
    finally { btn.disabled = false; btn.innerHTML = original; }
  }

  /* ----------------------------------------------------------- listings */
  async function initListings() {
    if (!(await guard())) return;
    let page = 1;
    const body = document.getElementById('listingsBody');
    const modalEl = document.getElementById('listingModal');
    const modal = new bootstrap.Modal(modalEl);

    try {
      const dom = await api('/api/internships?per_page=1');
      domainOptions = dom.domains || [];
      document.getElementById('fDomainField').innerHTML =
        domainOptions.map(d => `<option>${d}</option>`).join('');
    } catch { /* ignore */ }

    function collect() {
      return {
        title: v('fTitle'), company: v('fCompany'), contact_email: v('fEmail'),
        location: v('fLocation'), work_mode: v('fMode'), domain: v('fDomainField'),
        stipend: v('fStipend') || 0, duration_months: v('fDuration') || 3,
        openings: v('fOpenings') || 1, deadline: v('fDeadline') || null,
        skills_required: v('fSkills'), apply_url: v('fUrl'),
        description: v('fDescription'), source: v('fSource'),
      };
    }
    const v = (id) => document.getElementById(id).value.trim();

    function fillForm(L) {
      document.getElementById('fId').value = L ? L.id : '';
      document.getElementById('listingModalTitle').textContent =
        L ? `Edit listing #${L.id}` : 'New internship listing';
      const set = (id, val) => document.getElementById(id).value = val ?? '';
      set('fTitle', L?.title); set('fCompany', L?.company); set('fEmail', L?.contact_email);
      set('fLocation', L?.location); set('fMode', L?.work_mode || 'onsite');
      set('fDomainField', L?.domain || domainOptions[0]);
      set('fStipend', L?.stipend ?? 15000); set('fDuration', L?.duration_months ?? 3);
      set('fOpenings', L?.openings ?? 1); set('fDeadline', L?.deadline || '');
      set('fSkills', (L?.skills_required || []).join(', ')); set('fUrl', L?.apply_url);
      set('fDescription', L?.description); set('fSource', L?.source || 'admin');
      document.getElementById('listingFormError').classList.add('d-none');
      document.getElementById('trustPreview').innerHTML = L ? `
        <div class="border rounded-3 p-3" style="background:#fbfcff">
          <div class="d-flex justify-content-between align-items-center">
            <div><div class="text-muted-soft text-tiny text-uppercase fw-bold">Current trust score</div>
              <div class="fs-4 fw-800">${L.trust_score}/100 ${L.badge}</div></div>
            ${UI.trustRing(L.trust_score, L.badge, 'sm')}
          </div>
          <div class="text-muted-soft text-tiny mt-2">Saving re-runs the trust engine and writes an audit entry.</div>
        </div>` : '';
    }

    async function load() {
      body.innerHTML = UI.skeletonRows(8, 6);
      const params = new URLSearchParams({ page, per_page: 10,
        q: document.getElementById('lSearch').value.trim(),
        badge: document.getElementById('lBadge').value,
        flagged: document.getElementById('lFlagged').value,
        sort: document.getElementById('lSort').value });
      try {
        const d = await api(`/api/admin/internships?${params}`);
        document.getElementById('listingsMeta').textContent =
          `${fmt.num(d.meta.total)} listings · page ${d.meta.page}/${d.meta.pages}`;
        if (!d.internships.length) {
          body.innerHTML = `<tr><td colspan="6">${UI.emptyState({ title: 'No listings found',
            icon: 'bi-briefcase', message: 'Adjust the filters or create a new listing.',
            ctaLabel: 'New listing', ctaId: 'emptyNewBtn' })}</td></tr>`;
          document.getElementById('emptyNewBtn')?.addEventListener('click', () => { fillForm(null); modal.show(); });
        } else {
          body.innerHTML = d.internships.map(L => `
            <tr data-row="${L.id}">
              <td><div class="fw-semibold">${escapeHtml(L.title)}</div>
                <div class="text-muted-soft text-tiny">${fmt.date(L.posted_date)} · ${L.applicant_count} applicants</div></td>
              <td class="d-none d-md-table-cell">
                <div class="small">${escapeHtml(L.company)}</div>
                <div class="text-muted-soft text-tiny">${escapeHtml(L.company_domain || '—')}</div></td>
              <td class="d-none d-lg-table-cell">
                <span class="badge-ghost">${escapeHtml(L.domain || '')}</span>
                <span class="badge-ghost">${escapeHtml(L.work_mode || '')}</span></td>
              <td>${trustCell(L)}</td>
              <td class="d-none d-xl-table-cell">${redFlagChips(L.red_flags)}</td>
              <td class="text-end">
                <div class="d-flex gap-1 justify-content-end">
                  <button class="btn btn-soft btn-icon btn-sm" title="View listing"
                    onclick="location.href='/student/internship/${L.id}'"><i class="bi bi-eye"></i></button>
                  <button class="btn btn-soft btn-icon btn-sm" title="Recompute trust"
                    data-recompute="${L.id}"><i class="bi bi-arrow-repeat"></i></button>
                  <button class="btn btn-soft btn-icon btn-sm" title="Edit"
                    data-edit="${L.id}"><i class="bi bi-pencil"></i></button>
                  <button class="btn btn-soft btn-icon btn-sm" title="Override trust score"
                    data-override="${L.id}" data-score="${L.trust_score}" data-flag="${L.fraud_flag}">
                    <i class="bi bi-shield-lock"></i></button>
                  <button class="btn btn-outline-danger btn-icon btn-sm" title="Delete"
                    data-delete="${L.id}"><i class="bi bi-trash3"></i></button>
                </div></td></tr>`).join('');
          bindRows(d.internships);
        }
        UI.renderPagination('#listingsPagination', d.meta, (p) => { page = p; load(); });
        UI.animateBars();
      } catch (err) { UI.errorState(body, err.message, load); }
    }

    function bindRows(items) {
      const byId = Object.fromEntries(items.map(i => [i.id, i]));
      body.querySelectorAll('[data-edit]').forEach(b => b.onclick = async () => {
        try {
          const full = await api(`/api/internships/${b.getAttribute('data-edit')}`);
          fillForm(full.internship); modal.show();
        } catch (err) { toast(err.message, 'error'); }
      });
      body.querySelectorAll('[data-recompute]').forEach(b => b.onclick = async () => {
        b.disabled = true;
        const icon = b.innerHTML;
        b.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        try {
          const res = await api(`/api/admin/internships/${b.getAttribute('data-recompute')}/recompute`,
            { method: 'POST' });
          toast(`Re-scored → ${res.trust_score}/100 (${res.badge}).`, 'success');
          load();
        } catch (err) { toast(err.message, 'error'); b.disabled = false; b.innerHTML = icon; }
      });
      body.querySelectorAll('[data-override]').forEach(b => b.onclick = () => {
        const id = b.getAttribute('data-override');
        const L = byId[id];
        document.getElementById('oId').value = id;
        document.getElementById('oScore').value = b.getAttribute('data-score');
        document.getElementById('oFlag').checked = b.getAttribute('data-flag') === 'true';
        document.getElementById('oNote').value = '';
        document.getElementById('oContext').innerHTML =
          `<strong>${escapeHtml(L.title)}</strong> · ${escapeHtml(L.company)}
           <span class="badge-ghost ms-1">current ${L.trust_score} · ${L.badge}</span>`;
        document.getElementById('overrideError').classList.add('d-none');
        new bootstrap.Modal(document.getElementById('overrideModal')).show();
      });
      body.querySelectorAll('[data-delete]').forEach(b => b.onclick = async () => {
        const row = b.closest('tr');
        const ok = await UI.confirmModal({ title: 'Delete this listing?',
          body: 'Applications and feedback for it are deleted too. This cannot be undone.',
          confirmLabel: 'Delete', variant: 'danger' });
        if (!ok) return;
        row.style.opacity = '.35';              // optimistic
        try {
          const res = await api(`/api/admin/internships/${b.getAttribute('data-delete')}`,
            { method: 'DELETE' });
          toast(res.message, 'success');
          load();
        } catch (err) { row.style.opacity = '1'; toast(err.message, 'error'); }
      });
    }

    document.getElementById('newListingBtn').onclick = () => fillForm(null);
    document.getElementById('saveListingBtn').onclick = async (e) => {
      const btn = e.currentTarget;
      const id = document.getElementById('fId').value;
      const payload = collect();
      const errBox = document.getElementById('listingFormError');
      btn.disabled = true;
      btn.querySelector('[data-spin]').classList.remove('d-none');
      try {
        const res = id
          ? await api(`/api/admin/internships/${id}`, { method: 'PUT', body: payload })
          : await api('/api/admin/add-internship', { method: 'POST', body: payload });
        toast(res.message, res.trust?.fraud_flag ? 'warning' : 'success', 5200);
        modal.hide();
        load();
        refreshFlagBadge();
      } catch (err) {
        errBox.innerHTML = err.message + (err.payload?.field_errors
          ? '<ul class="mb-0 ps-3">' + err.payload.field_errors.map(f => `<li>${escapeHtml(f)}</li>`).join('') + '</ul>'
          : '');
        errBox.classList.remove('d-none');
        toast('Could not save the listing.', 'error');
      } finally {
        btn.disabled = false;
        btn.querySelector('[data-spin]').classList.add('d-none');
      }
    };

    document.getElementById('saveOverrideBtn').onclick = async (e) => {
      const btn = e.currentTarget;
      const errBox = document.getElementById('overrideError');
      btn.disabled = true;
      btn.querySelector('[data-spin]').classList.remove('d-none');
      try {
        const res = await api('/api/admin/trustscore-override', { method: 'POST', body: {
          internship_id: Number(document.getElementById('oId').value),
          trust_score: Number(document.getElementById('oScore').value),
          mark_fraud: document.getElementById('oFlag').checked,
          note: document.getElementById('oNote').value.trim(),
        }});
        toast(res.message, 'success', 4500);
        bootstrap.Modal.getInstance(document.getElementById('overrideModal')).hide();
        load();
      } catch (err) {
        errBox.textContent = err.message;
        errBox.classList.remove('d-none');
      } finally {
        btn.disabled = false;
        btn.querySelector('[data-spin]').classList.add('d-none');
      }
    };

    ['lBadge', 'lFlagged', 'lSort'].forEach(id =>
      document.getElementById(id).addEventListener('change', () => { page = 1; load(); }));
    document.getElementById('lApply').onclick = () => { page = 1; load(); };
    document.getElementById('lClear').onclick = () => {
      document.getElementById('lSearch').value = '';
      document.getElementById('lBadge').value = '';
      document.getElementById('lFlagged').value = '';
      document.getElementById('lSort').value = 'recent';
      page = 1; load();
    };
    document.getElementById('lSearch').addEventListener('keydown', e => {
      if (e.key === 'Enter') { page = 1; load(); }
    });
    load();
  }

  /* ------------------------------------------------------------ flagged */
  async function initFlagged() {
    if (!(await guard())) return;
    let page = 1;
    const list = document.getElementById('queueList');

    async function load() {
      list.innerHTML = `<div class="card"><div class="card-body">${UI.skeletonRows(5, 4)}</div></div>`;
      const params = new URLSearchParams({ page, per_page: 8,
        q: document.getElementById('qSearch').value.trim(),
        severity: document.getElementById('qSeverity').value });
      try {
        const d = await api(`/api/admin/flagged?${params}`);
        const s = d.summary;
        document.getElementById('qTotal').textContent = s.total_flagged;
        document.getElementById('qCritical').textContent = s.critical;
        document.getElementById('qNew').textContent = s.new_this_week;
        document.getElementById('qAvg').textContent = s.avg_flagged_score;

        if (!d.queue.length) {
          list.innerHTML = `<div class="card"><div class="card-body">${UI.emptyState({
            title: 'Queue is clear 🎉', icon: 'bi-shield-check',
            message: 'No listings are currently flagged. New imports are scored automatically.' })}</div></div>`;
          document.getElementById('queuePagination').innerHTML = '';
          return;
        }

        list.innerHTML = d.queue.map(L => `
          <div class="card mb-3" data-queue="${L.id}">
            <div class="card-body">
              <div class="row g-3 align-items-center">
                <div class="col-lg-5">
                  <div class="d-flex gap-3">
                    ${UI.trustRing(L.trust_score, L.badge, 'sm')}
                    <div class="min-w-0">
                      <a class="fw-bold text-dark d-block text-truncate" href="/student/internship/${L.id}">
                        ${escapeHtml(L.title)}</a>
                      <div class="text-muted-soft small text-truncate">${escapeHtml(L.company)}
                        · ${escapeHtml(L.contact_email || 'no email')}</div>
                      <div class="chip-row mt-2">
                        ${UI.trustBadge(L.badge, L.trust_score, L.fraud_flag)}
                        <span class="badge-ghost">${escapeHtml(L.company_domain || '—')}</span>
                        <span class="badge-ghost">rule ${Math.round((L.rule_score || 0) * 100)}%</span>
                        <span class="badge-ghost">ML ${((L.ml_fraud_prob || 0) * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="col-lg-4">
                  ${(L.top_flags || []).length
                    ? (L.top_flags || []).map(f => `<div class="flag-item ${f.severity === 'high' ? '' : 'medium'}">
                        <div class="d-flex justify-content-between gap-2">
                          <span class="small">${escapeHtml(f.label)}</span>
                          <span class="sev" style="color:${f.severity === 'high' ? 'var(--im-red)' : 'var(--im-amber)'}">
                            ${f.severity}</span></div>
                        <div class="text-muted-soft text-tiny">“${escapeHtml(f.evidence || '')}”</div>
                      </div>`).join('')
                    : '<div class="flag-item medium"><span class="small">Failed a domain hard check (new / blacklisted / free-mail domain).</span></div>'}
                </div>
                <div class="col-lg-3 text-lg-end">
                  <div class="d-grid gap-2">
                    <button class="btn btn-gradient btn-sm" data-resolve="${L.id}">
                      <i class="bi bi-check2-circle me-1"></i>Mark safe &amp; clear</button>
                    <button class="btn btn-soft btn-sm" data-edit-score="${L.id}" data-score="${L.trust_score}">
                      <i class="bi bi-sliders me-1"></i>Override score</button>
                    <div class="d-flex gap-2">
                      <a class="btn btn-light btn-sm flex-fill" href="/student/internship/${L.id}">Inspect</a>
                      <button class="btn btn-outline-danger btn-sm" data-delete="${L.id}">
                        <i class="bi bi-trash3"></i></button>
                    </div>
                  </div>
                </div>
              </div>
            </div></div>`).join('');

        UI.renderPagination('#queuePagination', d.meta, (p) => { page = p; load(); });
        UI.animateRings(list); UI.animateBars(list);
        bindQueue();
      } catch (err) { UI.errorState(list, err.message, load); }
    }

    function bindQueue() {
      list.querySelectorAll('[data-resolve]').forEach(b => b.onclick = async () => {
        const ok = await UI.confirmModal({ title: 'Clear this flag?',
          body: 'The listing keeps its trust score but is no longer marked as fraud. An audit entry records your review.',
          confirmLabel: 'Mark safe' });
        if (!ok) return;
        const card = b.closest('[data-queue]');
        card.style.opacity = '.35';                 // optimistic removal
        try {
          const res = await api(`/api/admin/flagged/${b.getAttribute('data-resolve')}/resolve`,
            { method: 'POST', body: { note: 'Reviewed in fraud queue — verified as safe by placement cell.' } });
          toast(res.message, 'success');
          card.remove();
          load(); refreshFlagBadge();
        } catch (err) { card.style.opacity = '1'; toast(err.message, 'error'); }
      });
      list.querySelectorAll('[data-edit-score]').forEach(b => b.onclick = () => {
        document.getElementById('oId').value = b.getAttribute('data-edit-score');
        document.getElementById('oScore').value = b.getAttribute('data-score');
        document.getElementById('oFlag').checked = true;
        document.getElementById('oNote').value = '';
        document.getElementById('oContext').textContent = 'Adjusting a flagged listing from the review queue.';
        document.getElementById('overrideError').classList.add('d-none');
        new bootstrap.Modal(document.getElementById('overrideModal')).show();
      });
      list.querySelectorAll('[data-delete]').forEach(b => b.onclick = async () => {
        const ok = await UI.confirmModal({ title: 'Delete this listing?',
          body: 'The scam listing and all its data will be removed permanently.',
          confirmLabel: 'Delete', variant: 'danger' });
        if (!ok) return;
        const card = b.closest('[data-queue]');
        card.style.opacity = '.35';
        try {
          await api(`/api/admin/internships/${b.getAttribute('data-delete')}`, { method: 'DELETE' });
          toast('Listing deleted.', 'success');
          load(); refreshFlagBadge();
        } catch (err) { card.style.opacity = '1'; toast(err.message, 'error'); }
      });
      // override modal in this page may not exist — create lazily
      if (!document.getElementById('overrideModal')) {
        document.body.insertAdjacentHTML('beforeend', `
          <div class="modal fade" id="overrideModal" tabindex="-1"><div class="modal-dialog modal-dialog-centered">
            <div class="modal-content"><div class="modal-header">
              <h6 class="modal-title"><i class="bi bi-shield-lock me-2"></i>Override trust score</h6>
              <button class="btn-close" data-bs-dismiss="modal"></button></div>
              <div class="modal-body">
                <input type="hidden" id="oId"><div class="small text-muted-soft mb-2" id="oContext"></div>
                <label class="form-label" for="oScore">New trust score (0–100)</label>
                <input class="form-control mb-3" id="oScore" type="number" min="0" max="100">
                <div class="form-check form-switch mb-3">
                  <input class="form-check-input" type="checkbox" id="oFlag">
                  <label class="form-check-label small" for="oFlag">Keep fraud flag</label></div>
                <label class="form-label" for="oNote">Justification (required)</label>
                <textarea class="form-control form-control-sm" id="oNote" rows="3"></textarea>
                <div id="overrideError" class="alert alert-danger py-2 small mt-3 d-none"></div></div>
              <div class="modal-footer">
                <button class="btn btn-light btn-sm" data-bs-dismiss="modal">Cancel</button>
                <button class="btn btn-primary btn-sm" id="saveOverrideBtn">Apply override</button>
              </div></div></div></div>`);
        document.getElementById('saveOverrideBtn').onclick = async (e) => {
          const btn = e.currentTarget;
          btn.disabled = true;
          try {
            const res = await api('/api/admin/trustscore-override', { method: 'POST', body: {
              internship_id: Number(document.getElementById('oId').value),
              trust_score: Number(document.getElementById('oScore').value),
              mark_fraud: document.getElementById('oFlag').checked,
              note: document.getElementById('oNote').value.trim() } });
            toast(res.message, 'success', 4500);
            bootstrap.Modal.getInstance(document.getElementById('overrideModal')).hide();
            load();
          } catch (err) {
            const box = document.getElementById('overrideError');
            box.textContent = err.message; box.classList.remove('d-none');
          } finally { btn.disabled = false; }
        };
      }
    }

    document.getElementById('qApply').onclick = () => { page = 1; load(); };
    document.getElementById('qClear').onclick = () => {
      document.getElementById('qSearch').value = '';
      document.getElementById('qSeverity').value = '';
      page = 1; load();
    };
    document.getElementById('qSeverity').addEventListener('change', () => { page = 1; load(); });
    document.getElementById('qSearch').addEventListener('keydown', e => {
      if (e.key === 'Enter') { page = 1; load(); } });

    document.getElementById('exportFlagged').addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        const res = await fetch('/api/admin/export/flagged.csv',
          { headers: { Authorization: `Bearer ${IM.getToken()}` }, credentials: 'include' });
        if (!res.ok) throw new Error('Export failed');
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'flagged_listings.csv';
        a.click();
        toast('Flagged listings exported to CSV.', 'success');
      } catch (err) { toast(err.message, 'error'); }
    });

    load();
  }

  /* --------------------------------------------------------- bulk upload */
  async function initBulkUpload() {
    if (!(await guard())) return;
    const fileInput = document.getElementById('csvFile');
    const drop = document.getElementById('csvDrop');
    const btn = document.getElementById('csvBtn');

    document.getElementById('colList').innerHTML = ['title', 'company', 'contact_email', 'location',
      'work_mode', 'domain', 'description', 'skills_required', 'stipend', 'duration_months',
      'openings', 'apply_url', 'deadline', 'posted_date', 'source']
      .map(c => `<span class="skill-tag" style="font-size:.75rem">${c}</span>`).join('');

    fileInput.addEventListener('change', () => {
      const f = fileInput.files[0];
      document.getElementById('csvTitle').textContent = f ? f.name : 'Choose a .csv file or drop it here';
      document.getElementById('csvHint').textContent = f
        ? `${(f.size / 1024).toFixed(1)} KB — ready to import` : 'Header row must match the template';
      btn.disabled = !f;
    });
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault(); drop.classList.add('dragover'); }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault(); drop.classList.remove('dragover'); }));
    drop.addEventListener('drop', e => {
      if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        fileInput.dispatchEvent(new Event('change'));
      }
    });

    document.getElementById('csvForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const f = fileInput.files[0];
      if (!f) return;
      const fd = new FormData();
      fd.append('file', f);
      btn.disabled = true;
      btn.querySelector('[data-spin]').classList.remove('d-none');
      document.getElementById('importSummary').innerHTML =
        `<div class="spinner-wrap"><div class="spinner-border text-primary"></div>
         <div class="text-muted-soft small">Parsing rows, validating fields and running the trust engine…</div></div>`;
      try {
        const res = await api('/api/admin/bulk-upload', { method: 'POST', formData: fd });
        toast(res.message, res.flagged ? 'warning' : 'success', 5200);
        document.getElementById('importSummary').innerHTML = `
          <div class="row g-3">
            <div class="col-4"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Imported</div>
              <div class="fs-3 fw-800" style="color:var(--im-green)">${res.created}</div></div>
            <div class="col-4"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Skipped</div>
              <div class="fs-3 fw-800" style="color:var(--im-amber)">${res.skipped}</div></div>
            <div class="col-4"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Flagged</div>
              <div class="fs-3 fw-800" style="color:var(--im-red)">${res.flagged}</div></div>
          </div>
          ${res.flagged ? `<div class="alert alert-warning py-2 small mt-3 mb-0">
            <i class="bi bi-flag-fill me-1"></i>${res.flagged} imported listing(s) went straight to the
            <a href="/admin/flagged" class="fw-semibold">fraud review queue</a>.</div>` : ''}
          ${res.errors?.length ? `<div class="divider-y"></div>
            <div class="text-uppercase text-muted-soft text-tiny fw-bold mb-2">Rows with issues</div>
            ${res.errors.map(e => `<div class="flag-item medium">
              <div class="small"><strong>Row ${e.row}</strong> · ${escapeHtml(e.company || '')}</div>
              <div class="text-muted-soft text-tiny">${e.errors.map(escapeHtml).join(' · ')}</div>
            </div>`).join('')}` : ''}`;

        document.getElementById('importResults').innerHTML = res.results?.length
          ? res.results.map((r, i) => `<tr>
              <td>${i + 1}</td>
              <td class="text-truncate" style="max-width:220px">${escapeHtml(r.title)}</td>
              <td class="text-truncate" style="max-width:160px">${escapeHtml(r.company)}</td>
              <td>${UI.trustBadge(r.badge, r.trust_score, r.fraud_flag)}</td>
              <td>${r.fraud_flag
                ? '<span class="badge-trust badge-red"><i class="bi bi-flag-fill"></i>queued</span>'
                : '<span class="badge-trust badge-green"><i class="bi bi-check2"></i>published</span>'}</td>
            </tr>`).join('')
          : '<tr><td colspan="5" class="text-center text-muted-soft py-4">No rows imported.</td></tr>';

        fileInput.value = '';
        document.getElementById('csvTitle').textContent = 'Choose a .csv file or drop it here';
        refreshFlagBadge();
      } catch (err) {
        toast(err.message, 'error', 6000);
        document.getElementById('importSummary').innerHTML =
          `<div class="alert alert-danger mb-0"><i class="bi bi-exclamation-octagon me-1"></i>
            ${escapeHtml(err.message)}</div>`;
      } finally {
        btn.disabled = false;
        btn.querySelector('[data-spin]').classList.add('d-none');
      }
    });
  }

  /* ----------------------------------------------------------- analytics */
  async function initAnalytics() {
    if (!(await guard())) return;

    async function load() {
      try {
        const d = await api('/api/admin/analytics');
        setKpis(d.kpis);

        UI.destroyChart(charts, 'band');
        charts.band = new Chart(document.getElementById('aBandChart'), {
          type: 'bar',
          data: { labels: Object.keys(d.score_bands), datasets: [{ data: Object.values(d.score_bands),
            backgroundColor: ['#dc2626', '#ef4444', '#f59e0b', '#fbbf24', '#34d399', '#0f9d58'],
            borderRadius: 8 }] },
          options: { plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, grid: { color: '#eef1f7' } }, x: { grid: { display: false } } } },
        });

        UI.destroyChart(charts, 'badge');
        charts.badge = new Chart(document.getElementById('aBadgeChart'), {
          type: 'pie',
          data: { labels: ['Green', 'Amber', 'Red'],
            datasets: [{ data: [d.badge_distribution.Green, d.badge_distribution.Amber,
              d.badge_distribution.Red], backgroundColor: ['#0f9d58', '#f59e0b', '#dc2626'], borderWidth: 0 }] },
          options: { plugins: { legend: { position: 'bottom' } } },
        });

        UI.destroyChart(charts, 'domain');
        charts.domain = new Chart(document.getElementById('aDomainChart'), {
          type: 'bar',
          data: { labels: d.domain_stats.map(x => x.domain.replace(' & ', ' & ')),
            datasets: [
              { label: 'Listings', data: d.domain_stats.map(x => x.listings),
                backgroundColor: '#4f46e5', borderRadius: 6, yAxisID: 'y' },
              { label: 'Avg trust', data: d.domain_stats.map(x => x.avg_trust),
                backgroundColor: '#0f9d58', borderRadius: 6, yAxisID: 'y1' }] },
          options: { plugins: { legend: { position: 'bottom' } },
            scales: { x: { ticks: { maxRotation: 60, minRotation: 40 }, grid: { display: false } },
              y: { beginAtZero: true, position: 'left', grid: { color: '#eef1f7' } },
              y1: { beginAtZero: true, max: 100, position: 'right', grid: { display: false } } } },
        });

        UI.destroyChart(charts, 'flags');
        charts.flags = new Chart(document.getElementById('aFlagChart'), {
          type: 'bar',
          data: { labels: d.top_flags.map(f => f.label.replace(/^(.{34}).*$/, '$1…')),
            datasets: [{ data: d.top_flags.map(f => f.count),
              backgroundColor: '#dc2626', borderRadius: 8 }] },
          options: { indexAxis: 'y', plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, grid: { color: '#eef1f7' } }, y: { grid: { display: false } } } },
        });

        UI.destroyChart(charts, 'apps');
        charts.apps = new Chart(document.getElementById('aAppChart'), {
          type: 'doughnut',
          data: { labels: d.application_status.map(s => s.status.replace('_', ' ')),
            datasets: [{ data: d.application_status.map(s => s.count),
              backgroundColor: ['#6366f1', '#0ea5e9', '#f59e0b', '#8b5cf6', '#0f9d58', '#94a3b8'],
              borderWidth: 0, cutout: '62%' }] },
          options: { plugins: { legend: { position: 'bottom' } } },
        });

        UI.destroyChart(charts, 'feedback');
        charts.feedback = new Chart(document.getElementById('aFeedbackChart'), {
          type: 'bar',
          data: { labels: d.feedback_split.map(f => f.verdict),
            datasets: [{ label: 'Reports', data: d.feedback_split.map(f => f.count),
              backgroundColor: ['#0f9d58', '#dc2626'], borderRadius: 8 }] },
          options: { plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, grid: { color: '#eef1f7' } }, x: { grid: { display: false } } } },
        });
        const totalFb = d.feedback_split.reduce((s, f) => s + f.count, 0);
        const avgRating = totalFb
          ? (d.feedback_split.reduce((s, f) => s + f.avg_rating * f.count, 0) / totalFb).toFixed(2) : '—';
        document.getElementById('feedbackAvg').textContent = `${totalFb} reports · avg rating ${avgRating}/5`;

        UI.destroyChart(charts, 'trend');
        charts.trend = new Chart(document.getElementById('aTrendChart'), {
          type: 'line',
          data: { labels: d.posting_trend.map(p => p.label),
            datasets: [
              { label: 'Posted', data: d.posting_trend.map(p => p.posted), borderColor: '#4f46e5',
                backgroundColor: 'rgba(79,70,229,.12)', fill: true, tension: .4, borderWidth: 2, pointRadius: 2 },
              { label: 'Flagged', data: d.posting_trend.map(p => p.flagged), borderColor: '#dc2626',
                backgroundColor: 'rgba(220,38,38,.1)', fill: true, tension: .4, borderWidth: 2, pointRadius: 2 }] },
          options: { plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true, grid: { color: '#eef1f7' } }, x: { grid: { display: false } } } },
        });

        document.getElementById('topCompanies').innerHTML = d.top_companies.map(c => `
          <tr><td class="fw-semibold">${escapeHtml(c.company)}</td>
            <td class="text-end"><span class="badge-ghost">${c.listings}</span></td></tr>`).join('');

        const m = d.ml_model || {};
        document.getElementById('modelBox').innerHTML = `
          <div class="mb-3">
            <div class="d-flex justify-content-between small"><span class="text-muted-soft">Train accuracy</span>
              <strong>${((m.train_accuracy || 0) * 100).toFixed(1)}%</strong></div>
            ${UI.matchBar((m.train_accuracy || 0) * 100)}
            <div class="d-flex justify-content-between small mt-2"><span class="text-muted-soft">ROC AUC</span>
              <strong>${(m.roc_auc || 0).toFixed(3)}</strong></div>
            ${UI.matchBar((m.roc_auc || 0) * 100)}
            <div class="d-flex justify-content-between small mt-2"><span class="text-muted-soft">F1</span>
              <strong>${(m.f1 || 0).toFixed(3)}</strong></div>
            ${UI.matchBar((m.f1 || 0) * 100)}
          </div>
          <div class="formula-box mb-3">${escapeHtml(m.features || '')}
            <br>trained on ${m.samples || 0} rows (${m.fraud_samples || 0} fraud / ${m.genuine_samples || 0} genuine)</div>
          <div class="small text-muted-soft">
            Badge thresholds — Green ≥ ${d.trust_thresholds.green} · Amber ${d.trust_thresholds.amber}–74 ·
            Red &lt; ${d.trust_thresholds.amber} · auto-flag below ${d.trust_thresholds.flag}.<br>
            Trust = 0.5 × RuleScore + 0.5 × (1 − MLFraudProbability).
          </div>`;
        UI.animateBars();
      } catch (err) { toast(err.message, 'error'); }
    }

    document.getElementById('refreshAnalytics').onclick = load;
    document.getElementById('retrainBtn').onclick = (e) => retrain(e.currentTarget, load);
    load();
  }

  /* ------------------------------------------------------------ students */
  async function initStudents() {
    if (!(await guard())) return;
    let page = 1;
    const body = document.getElementById('studentsBody');
    const modal = new bootstrap.Modal(document.getElementById('studentModal'));

    async function load() {
      body.innerHTML = UI.skeletonRows(8, 6);
      const params = new URLSearchParams({ page, per_page: 10,
        q: document.getElementById('sSearch').value.trim(),
        branch: document.getElementById('sBranch').value });
      try {
        const d = await api(`/api/admin/students?${params}`);
        document.getElementById('studentsMeta').textContent =
          `${fmt.num(d.meta.total)} students · page ${d.meta.page}/${d.meta.pages}`;
        body.innerHTML = d.students.length ? d.students.map(s => `
          <tr>
            <td><div class="d-flex align-items-center gap-2">
              <div class="avatar">${initials(s.name)}</div>
              <div class="min-w-0"><div class="fw-semibold text-truncate">${escapeHtml(s.name)}</div>
                <div class="text-muted-soft text-tiny text-truncate">${escapeHtml(s.email)}</div></div>
            </div></td>
            <td class="d-none d-md-table-cell"><div class="small">${escapeHtml(s.college || '—')}</div>
              <div class="text-muted-soft text-tiny">${escapeHtml(s.branch || '')} ·
                ${s.graduation_year || '—'}</div></td>
            <td class="d-none d-lg-table-cell">
              <span class="badge-soft">${escapeHtml(s.preferred_domain || 'not set')}</span></td>
            <td>${(s.skills || []).slice(0, 3).map(k => `<span class="skill-tag"
              style="font-size:.72rem">${escapeHtml(k)}</span>`).join('')}
              ${s.skills?.length > 3 ? `<span class="badge-ghost">+${s.skills.length - 3}</span>` : ''}</td>
            <td><span class="fw-bold">${s.ats_score || 0}</span>
              <div style="width:44px">${UI.matchBar(s.ats_score || 0)}</div></td>
            <td class="d-none d-md-table-cell"><span class="badge-soft">${s.applications}</span>
              <span class="badge-ghost" title="shortlisted or beyond">${s.shortlisted}</span></td>
            <td class="text-end">
              <button class="btn btn-soft btn-sm" data-view="${s.id}">
                <i class="bi bi-eye me-1"></i>View</button></td></tr>`).join('')
          : `<tr><td colspan="7">${UI.emptyState({ title: 'No students match',
              icon: 'bi-people', message: 'Try clearing the search or branch filter.' })}</td></tr>`;
        UI.renderPagination('#studentsPagination', d.meta, (p) => { page = p; load(); });
        UI.animateBars();
        body.querySelectorAll('[data-view]').forEach(b => b.onclick = async () => {
          document.getElementById('studentModalBody').innerHTML =
            '<div class="spinner-wrap"><div class="spinner-border text-primary"></div></div>';
          modal.show();
          try {
            const det = await api(`/api/student/profile/${b.getAttribute('data-view')}`);
            const p = det.profile, st = det.stats;
            document.getElementById('studentModalBody').innerHTML = `
              <div class="d-flex align-items-center gap-3 mb-3">
                <div class="avatar" style="width:52px;height:52px;font-size:1.1rem">${initials(p.name)}</div>
                <div><h5 class="mb-0">${escapeHtml(p.name)}</h5>
                  <div class="text-muted-soft small">${escapeHtml(p.email)} · ${escapeHtml(p.college || '')}</div>
                  <div class="chip-row mt-1"><span class="badge-soft">${escapeHtml(p.branch || '')}</span>
                    <span class="badge-ghost">${escapeHtml(p.preferred_domain || 'no domain')}</span>
                    <span class="badge-ghost">CGPA ${p.cgpa ?? '—'}</span>
                    <span class="badge-ghost">ATS ${p.ats_score}</span></div></div>
              </div>
              <div class="row g-3 mb-3">
                <div class="col-3"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Skills</div>
                  <div class="fs-4 fw-800">${st.total_skills}</div></div>
                <div class="col-3"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Applications</div>
                  <div class="fs-4 fw-800">${st.applications}</div></div>
                <div class="col-3"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Feedback</div>
                  <div class="fs-4 fw-800">${st.feedback_given}</div></div>
                <div class="col-3"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Complete</div>
                  <div class="fs-4 fw-800">${st.completeness}%</div></div>
              </div>
              <div class="text-uppercase text-muted-soft text-tiny fw-bold mb-2">Skill cloud</div>
              ${UI.skillCloud(det.skill_cloud, 30) || '<span class="text-muted-soft small">No skills extracted.</span>'}
              <div class="divider-y"></div>
              <div class="text-uppercase text-muted-soft text-tiny fw-bold mb-2">Domain fit</div>
              ${det.domain_matches.slice(0, 4).map(dm => `
                <div class="d-flex justify-content-between small mb-1">
                  <span>${escapeHtml(dm.domain)} ${dm.is_preferred ? '<span class="badge-soft">preferred</span>' : ''}</span>
                  <span class="text-muted-soft">${dm.confidence}%</span></div>${UI.matchBar(dm.confidence)}
              `).join('') || '<span class="text-muted-soft small">No domain signal.</span>'}`;
            UI.animateBars();
          } catch (err) {
            document.getElementById('studentModalBody').innerHTML =
              `<div class="alert alert-danger mb-0">${escapeHtml(err.message)}</div>`;
          }
        });
      } catch (err) { UI.errorState(body, err.message, load); }
    }

    document.getElementById('sApply').onclick = () => { page = 1; load(); };
    document.getElementById('sClear').onclick = () => {
      document.getElementById('sSearch').value = '';
      document.getElementById('sBranch').value = '';
      page = 1; load();
    };
    document.getElementById('sBranch').addEventListener('change', () => { page = 1; load(); });
    document.getElementById('sSearch').addEventListener('keydown', e => {
      if (e.key === 'Enter') { page = 1; load(); } });
    load();
  }

  /* ------------------------------------------------------------ feedback */
  async function initFeedback() {
    if (!(await guard())) return;
    let page = 1;
    const body = document.getElementById('feedbackBody');

    async function load() {
      body.innerHTML = UI.skeletonRows(8, 6);
      const params = new URLSearchParams({ page, per_page: 15,
        verdict: document.getElementById('fbFilter').value });
      try {
        const d = await api(`/api/admin/feedback?${params}`);
        const s = d.summary;
        document.getElementById('fbTotal').textContent = s.count;
        document.getElementById('fbAvg').textContent = s.average_rating;
        const verified = d.feedback.filter(f => f.verdict === 'Verified');
        document.getElementById('fbVerified').textContent = verified.length;
        document.getElementById('fbSuspicious').textContent = d.feedback.length - verified.length;
        body.innerHTML = d.feedback.length ? d.feedback.map(f => `
          <tr>
            <td><a class="fw-semibold text-dark" href="/student/internship/${f.internship_id}">
                ${escapeHtml(f.internship_title || '')}</a>
              <div class="text-muted-soft text-tiny">${escapeHtml(f.company || '')}</div></td>
            <td class="small">${escapeHtml(f.student_name || '—')}</td>
            <td><span class="badge-trust ${f.verdict === 'Verified' ? 'badge-green' : 'badge-red'}">
              <i class="bi bi-${f.verdict === 'Verified' ? 'check' : 'exclamation'}-circle"></i>
              ${escapeHtml(f.verdict)}</span></td>
            <td><span style="color:#f59e0b">${'★'.repeat(f.rating)}</span>
              <span class="text-muted-soft text-tiny">${f.rating}/5</span></td>
            <td class="d-none d-lg-table-cell small text-muted-soft">
              ${f.comment ? '“' + escapeHtml(f.comment) + '”' : '—'}</td>
            <td class="d-none d-md-table-cell text-muted-soft text-tiny">${fmt.ago(f.created_at)}</td>
          </tr>`).join('')
          : `<tr><td colspan="6">${UI.emptyState({ title: 'No feedback yet',
              icon: 'bi-chat-left-text', message: 'Students are prompted to give feedback right after applying.' })}</td></tr>`;
        UI.renderPagination('#feedbackPagination', d.meta, (p) => { page = p; load(); });
      } catch (err) { UI.errorState(body, err.message, load); }
    }

    document.getElementById('fbFilter').addEventListener('change', () => { page = 1; load(); });
    load();
  }

  /* --------------------------------------------------------------- audit */
  async function initAudit() {
    if (!(await guard())) return;
    let page = 1;
    const body = document.getElementById('auditBody');

    async function load() {
      body.innerHTML = UI.skeletonRows(8, 5);
      const params = new URLSearchParams({ page, per_page: 20,
        action: document.getElementById('auditFilter').value });
      try {
        const d = await api(`/api/admin/audit-log?${params}`);
        body.innerHTML = d.logs.length ? d.logs.map(l => `
          <tr>
            <td class="text-muted-soft text-tiny">${fmt.dateTime(l.created_at)}</td>
            <td>${l.internship_id
              ? `<a class="text-dark fw-semibold" href="/student/internship/${l.internship_id}">
                  ${escapeHtml(l.internship_title || '#' + l.internship_id)}</a>`
              : '<span class="text-muted-soft">—</span>'}</td>
            <td><span class="badge-soft">${escapeHtml(l.action || '')}</span></td>
            <td>${l.old_score !== null && l.old_score !== undefined
                ? `${UI.trustBadge(l.old_badge || 'Amber', l.old_score)} <i class="bi bi-arrow-right mx-1"></i>` : ''}
              ${l.new_score !== null && l.new_score !== undefined
                ? UI.trustBadge(l.new_badge || 'Amber', l.new_score) : ''}</td>
            <td class="d-none d-lg-table-cell">
              <div class="small">${escapeHtml(l.actor || 'system')}</div>
              <div class="text-muted-soft text-tiny">${escapeHtml(l.note || '')}</div></td>
          </tr>`).join('')
          : `<tr><td colspan="5">${UI.emptyState({ title: 'No audit entries',
              icon: 'bi-clock-history', message: 'Score changes, overrides and imports appear here.' })}</td></tr>`;
        UI.renderPagination('#auditPagination', d.meta, (p) => { page = p; load(); });
      } catch (err) { UI.errorState(body, err.message, load); }
    }

    async function loadDomains() {
      try {
        const d = await api('/api/admin/domains');
        document.getElementById('domainBody').innerHTML = d.domains.map(dom => `
          <tr><td><div class="fw-semibold small">${escapeHtml(dom.domain)}</div>
              <div class="text-muted-soft text-tiny">${dom.age_years} yrs · ${escapeHtml(dom.source)}</div></td>
            <td class="text-end">${dom.is_blacklisted
              ? '<span class="badge-trust badge-red"><i class="bi bi-slash-circle"></i>blacklist</span>'
              : dom.is_disposable
              ? '<span class="badge-trust badge-red"><i class="bi bi-trash3"></i>burner</span>'
              : dom.is_free_provider
              ? '<span class="badge-trust badge-amber"><i class="bi bi-envelope"></i>free mail</span>'
              : dom.age_days >= 730
              ? '<span class="badge-trust badge-green"><i class="bi bi-patch-check"></i>trusted</span>'
              : '<span class="badge-trust badge-amber"><i class="bi bi-clock"></i>young</span>'}</td></tr>`).join('');
      } catch (err) { /* silent */ }
    }

    document.getElementById('auditFilter').addEventListener('change', () => { page = 1; load(); });
    const rcBtn = document.getElementById('recomputeAllBtn');
    if (rcBtn) rcBtn.onclick = () => recomputeAll(rcBtn, load);
    load();
    loadDomains();
  }

  return { initDashboard, initListings, initFlagged, initBulkUpload, initAnalytics,
           initStudents, initFeedback, initAudit };
})();
