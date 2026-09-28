/* =====================================================================
   InternMatch AI — student pages
   ===================================================================== */
const Student = (() => {
  const charts = {};
  let profileCache = null;

  /* ------------------------------------------------------------ helpers */
  function listingCard(item, opts = {}) {
    const rec = item.internship ? item : null;
    const L = rec ? rec.internship : item;
    const matchPct = rec ? rec.match_pct : (opts.matchPct || null);
    const accent = L.badge === 'Red' ? 'flagged' : '';
    const matched = rec ? rec.matched_skills || [] : [];
    const missing = rec ? (rec.missing_skills || []).slice(0, 3) : [];
    const bonus = rec && rec.domain_bonus_applied
      ? `<span class="badge-soft" title="+0.10 domain preference bonus applied">+10% domain bonus</span>` : '';

    return `<div class="col-md-6 col-xl-4" data-listing-id="${L.id}">
      <div class="card listing-card h-100 ${accent}">
        <div class="card-body d-flex flex-column">
          <div class="d-flex gap-3 mb-3 align-items-start">
            <div class="company-logo">${escapeHtml(initials(L.company))}</div>
            <div class="flex-grow-1 min-w-0" style="overflow:hidden">
              <a href="/student/internship/${L.id}" class="fw-bold text-dark d-block text-truncate"
                 title="${escapeHtml(L.title)}">${escapeHtml(L.title)}</a>
              <div class="text-muted-soft text-truncate small">${escapeHtml(L.company)}</div>
            </div>
            <div class="flex-0-auto">${UI.trustBadge(L.badge, L.trust_score, L.fraud_flag)}</div>
          </div>

          <div class="meta-line mb-2">
            <span><i class="bi bi-geo-alt"></i> ${escapeHtml(L.location || '—')}</span>
            <span><i class="bi bi-laptop"></i> ${escapeHtml(L.work_mode || '')}</span>
            <span><i class="bi bi-cash-coin"></i> ${L.stipend ? fmt.inr(L.stipend) + '/mo' : 'Unpaid'}</span>
          </div>
          <div class="chip-row mb-3">
            <span class="badge-ghost">${escapeHtml(L.domain || '')}</span>
            <span class="badge-ghost">${L.duration_months || '?'} mo</span>
            ${bonus}
          </div>

          ${matchPct !== null && matchPct !== undefined ? `
            <div class="d-flex justify-content-between align-items-center mb-1">
              <span class="text-muted-soft text-tiny fw-bold text-uppercase">Match</span>
              <span class="fw-800" style="color:var(--im-primary)">${matchPct}%</span>
            </div>
            ${UI.matchBar(matchPct)}` : ''}

          ${matched.length ? `<div class="chip-row mt-3">
            ${matched.slice(0, 4).map(m => `<span class="skill-tag" style="font-size:.74rem">
              <i class="bi bi-check2"></i>${escapeHtml(m.skill)}</span>`).join('')}
            ${missing.length ? missing.map(m => `<span class="badge-ghost" title="Not found in your resume">
              ${escapeHtml(m)}</span>`).join('') : ''}
          </div>` : ''}

          <div class="mt-auto pt-3 d-flex gap-2">
            <a class="btn btn-soft btn-sm flex-fill" href="/student/internship/${L.id}">
              <i class="bi bi-shield-check me-1"></i>Details</a>
            <button class="btn btn-gradient btn-sm flex-fill" data-apply="${L.id}"
                    data-url="${escapeHtml(L.apply_url || '')}" data-title="${escapeHtml(L.title)}">
              <i class="bi bi-box-arrow-up-right me-1"></i>Apply</button>
          </div>
        </div>
      </div>
    </div>`;
  }

  function bindApplyButtons(root = document) {
    root.querySelectorAll('[data-apply]').forEach(btn => {
      if (btn.dataset.bound) return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', () => applyToListing(btn));
    });
  }

  /* --------------------------------------------------- apply + feedback */
  async function applyToListing(btn) {
    const id = btn.getAttribute('data-apply');
    const url = btn.getAttribute('data-url');
    const title = btn.getAttribute('data-title') || 'this listing';
    const original = btn.innerHTML;
    const sid = IM.studentId();

    // optimistic UI
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Applying…';
    try {
      const res = await api('/api/applications', { method: 'POST',
        body: { internship_id: Number(id), student_id: sid } });
      btn.classList.remove('btn-gradient');
      btn.classList.add('btn-soft');
      btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Applied';
      toast(res.message + (res.trust_warning
        ? ' ⚠ This listing is flagged — never pay any fee.' : ''), res.trust_warning ? 'warning' : 'success');
      if (url) window.open(url, '_blank', 'noopener');
      setTimeout(() => openFeedbackModal(Number(id), title), 900);
    } catch (err) {
      btn.disabled = false;
      btn.innerHTML = original;
      toast(err.message, 'error');
    }
  }

  function openFeedbackModal(internshipId, title) {
    const id = 'feedbackModal';
    document.getElementById(id)?.remove();
    const html = `<div class="modal fade" id="${id}" tabindex="-1" data-bs-backdrop="static">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h6 class="modal-title"><i class="bi bi-patch-question me-2 text-primary"></i>Was this listing genuine?</h6>
          </div>
          <div class="modal-body" id="feedbackBody">
            <p class="small text-muted-soft mb-3">You applied to <strong>${escapeHtml(title)}</strong>.
              Your verdict helps other students and the placement cell. Takes 5 seconds.</p>
            <div class="d-flex gap-2 mb-3">
              <button class="btn btn-outline-success flex-fill" data-verdict="Verified">
                <i class="bi bi-shield-check me-1"></i>Verified</button>
              <button class="btn btn-outline-danger flex-fill" data-verdict="Suspicious">
                <i class="bi bi-shield-exclamation me-1"></i>Suspicious</button>
            </div>
            <div class="mb-3">
              <label class="form-label">Rate the listing / recruiter</label>
              <div class="star-rating" id="starRating">
                ${[1, 2, 3, 4, 5].map(n => `<i class="bi bi-star-fill" data-star="${n}"></i>`).join('')}
              </div>
            </div>
            <label class="form-label" for="fbComment">Comment (optional)</label>
            <textarea class="form-control form-control-sm" id="fbComment" rows="2"
              placeholder="e.g. asked for a registration fee on WhatsApp"></textarea>
            <div class="alert alert-danger py-2 small mt-3 d-none" id="fbError"></div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-light btn-sm" data-bs-dismiss="modal">Skip</button>
            <button class="btn btn-gradient btn-sm" id="fbSubmit" disabled>
              <span class="spinner-border spinner-border-sm d-none me-2" data-spin></span>Submit feedback</button>
          </div>
        </div>
      </div></div>`;
    document.body.insertAdjacentHTML('beforeend', html);
    const el = document.getElementById(id);
    const modal = new bootstrap.Modal(el);
    modal.show();

    let verdict = null, rating = 0;
    const submitBtn = el.querySelector('#fbSubmit');
    const setReady = () => { submitBtn.disabled = !(verdict && rating); };

    el.querySelectorAll('[data-verdict]').forEach(b => b.onclick = () => {
      el.querySelectorAll('[data-verdict]').forEach(x => {
        x.classList.remove('active', 'btn-success', 'btn-danger');
        x.classList.add(x.dataset.verdict === 'Verified' ? 'btn-outline-success' : 'btn-outline-danger');
      });
      verdict = b.dataset.verdict;
      b.classList.remove('btn-outline-success', 'btn-outline-danger');
      b.classList.add('active', verdict === 'Verified' ? 'btn-success' : 'btn-danger');
      setReady();
    });
    el.querySelectorAll('[data-star]').forEach(star => {
      star.onmouseenter = () => paintStars(el, Number(star.dataset.star));
      star.onmouseleave = () => paintStars(el, rating);
      star.onclick = () => { rating = Number(star.dataset.star); paintStars(el, rating); setReady(); };
    });

    submitBtn.onclick = async () => {
      submitBtn.disabled = true;
      submitBtn.querySelector('[data-spin]').classList.remove('d-none');
      try {
        const res = await api('/api/feedback', { method: 'POST', body: {
          internship_id: internshipId, student_id: IM.studentId(),
          verdict, rating, comment: el.querySelector('#fbComment').value.trim() || null } });
        const body = el.querySelector('#feedbackBody');
        body.innerHTML = `<div class="text-center py-3">
          <div style="font-size:2.6rem;color:var(--im-green)"><i class="bi bi-check-circle-fill"></i></div>
          <h5 class="fw-bold mt-2">Thank you for the feedback! 🙏</h5>
          <p class="text-muted-soft mb-1">Your <strong>${escapeHtml(verdict)}</strong> verdict was saved against
            <strong>${escapeHtml(title)}</strong>.</p>
          <p class="text-muted-soft small mb-3">Listing rating is now
            <strong>${res.internship_rating.average}</strong>/5 from
            ${res.internship_rating.count} report(s). The placement cell sees this instantly.</p>
          <button class="btn btn-gradient btn-sm" data-bs-dismiss="modal">Done</button></div>`;
        document.querySelector('.modal-footer').classList.add('d-none');
        toast('Feedback saved — thanks for keeping the board safe!', 'success');
        setTimeout(() => modal.hide(), 2600);
      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.querySelector('[data-spin]').classList.add('d-none');
        const errBox = el.querySelector('#fbError');
        errBox.textContent = err.message;
        errBox.classList.remove('d-none');
      }
    };
  }

  function paintStars(el, upto) {
    el.querySelectorAll('[data-star]').forEach((s, i) => s.classList.toggle('active', i < upto));
  }

  /* ---------------------------------------------------------- dashboard */
  async function initDashboard() {
    const user = await IM.guard('student');
    if (!user) return;
    IM.mountChrome(user);
    const sid = IM.studentId();
    if (!sid) {
      document.getElementById('dashboardRoot').innerHTML =
        UI.emptyState({ title: 'No student profile linked', icon: 'bi-person-x',
          message: 'This account has no student profile attached.',
          ctaLabel: 'Back home', ctaHref: '/' });
      return;
    }
    document.getElementById('heroGreeting').textContent = `Welcome back, ${user.name.split(' ')[0]} 👋`;
    UI.loading('#topRecs', 'Building your ranked matches…', '200px');
    document.getElementById('topRecs').innerHTML = UI.skeletonCards(3, 'col-md-6 col-xl-4');
    document.getElementById('recentAppsBody').innerHTML = UI.skeletonRows(4, 6);

    try {
      const d = await api(`/api/student/dashboard/${sid}`);
      profileCache = d.profile;

      document.querySelector('[data-kpi="applications"]').textContent = d.stats.applications;
      document.querySelector('[data-kpi-sub="applications"]').textContent =
        `${d.stats.selected} selected · ${d.stats.feedback_given} feedback`;
      document.querySelector('[data-kpi="shortlisted"]').textContent = d.stats.shortlisted;
      document.querySelector('[data-kpi="avg_match"]').textContent = fmt.pct(d.stats.avg_match);
      document.querySelector('[data-kpi="ats_score"]').textContent = d.stats.ats_score;
      document.querySelector('[data-kpi-sub="skills"]').textContent = `${d.stats.skills} skills extracted`;

      const hasResume = !!(d.profile.resume_filename);
      document.getElementById('heroSub').innerHTML = hasResume
        ? `Resume <strong>${escapeHtml(d.profile.resume_filename)}</strong> parsed
           ${fmt.ago(d.profile.resume_uploaded_at)} · ATS ${d.stats.ats_score}/100 ·
           preferred domain <strong>${escapeHtml(d.profile.preferred_domain || 'not set')}</strong>`
        : 'You haven\'t uploaded a resume yet — upload one to unlock ranked recommendations.';
      document.getElementById('heroActions').innerHTML = hasResume
        ? `<a class="btn btn-light btn-sm" href="/student/profile"><i class="bi bi-arrow-repeat me-1"></i>Re-parse resume</a>
           <a class="btn btn-dark btn-sm" href="/student/recommendations"><i class="bi bi-stars me-1"></i>${d.top_recommendations.length} matches</a>`
        : `<a class="btn btn-light btn-sm" href="/student/profile"><i class="bi bi-cloud-arrow-up me-1"></i>Upload resume now</a>`;

      document.getElementById('skillCloudBox').innerHTML = d.skill_cloud.length
        ? UI.skillCloud(d.skill_cloud, 22) +
          `<div class="mt-3 small text-muted-soft">Best-fit domain:
            <strong>${escapeHtml(d.profile.preferred_domain || (d.domain_matches[0]?.domain ?? '—'))}</strong></div>`
        : UI.emptyState({ title: 'No skills yet', icon: 'bi-cloud-plus',
            message: 'Upload your resume to build a skill profile.',
            ctaLabel: 'Upload resume', ctaHref: '/student/profile' });

      // funnel chart
      const statuses = ['applied', 'under_review', 'shortlisted', 'interview', 'selected', 'rejected'];
      const labels = statuses.map(s => s.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()));
      const values = statuses.map(s => (d.status_breakdown.find(x => x.status === s)?.count) || 0);
      document.getElementById('funnelTotal').textContent = `${d.stats.applications} total`;
      UI.destroyChart(charts, 'status');
      charts.status = new Chart(document.getElementById('statusChart'), {
        type: 'bar',
        data: { labels, datasets: [{ data: values, backgroundColor: '#6366f1',
          borderRadius: 8, barThickness: 22 }] },
        options: { indexAxis: 'y', plugins: { legend: { display: false } },
          scales: { x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef1f7' } },
                    y: { grid: { display: false } } } },
      });

      // trust exposure doughnut
      const exp = d.trust_exposure || { Green: 0, Amber: 0, Red: 0 };
      UI.destroyChart(charts, 'exposure');
      charts.exposure = new Chart(document.getElementById('trustExposureChart'), {
        type: 'doughnut',
        data: { labels: ['Green', 'Amber', 'Red'],
          datasets: [{ data: [exp.Green, exp.Amber, exp.Red],
            backgroundColor: ['#0f9d58', '#f59e0b', '#dc2626'], borderWidth: 0, cutout: '68%' }] },
        options: { plugins: { legend: { position: 'bottom' } } },
      });

      // top recommendations
      const grid = document.getElementById('topRecs');
      if (!d.top_recommendations.length) {
        grid.innerHTML = `<div class="col-12">${UI.emptyState({
          title: 'No matches yet', icon: 'bi-stars',
          message: d.stats.skills ? 'Try widening your filters on the recommendations page.'
                                  : 'Upload a resume to build your skill vector first.',
          ctaLabel: d.stats.skills ? 'Open recommendations' : 'Upload resume',
          ctaHref: d.stats.skills ? '/student/recommendations' : '/student/profile' })}</div>`;
      } else {
        grid.innerHTML = d.top_recommendations.map(r => listingCard(r)).join('');
        bindApplyButtons(grid);
      }

      // recent applications
      const body = document.getElementById('recentAppsBody');
      if (!d.recent_applications.length) {
        body.innerHTML = `<tr><td colspan="6">${UI.emptyState({ title: 'No applications yet',
          message: 'Apply to a listing from the recommendations page to track it here.',
          icon: 'bi-send', ctaLabel: 'Find internships', ctaHref: '/student/recommendations' })}</td></tr>`;
      } else {
        body.innerHTML = d.recent_applications.map(a => {
          const L = a.internship || {};
          return `<tr class="cursor-pointer" onclick="location.href='/student/internship/${L.id}'">
            <td class="fw-semibold">${escapeHtml(L.title)}</td>
            <td class="text-muted-soft">${escapeHtml(L.company)}</td>
            <td><span class="fw-bold" style="color:var(--im-primary)">${Math.round((a.match_score || 0) * 100)}%</span></td>
            <td>${UI.trustBadge(L.badge, L.trust_score, L.fraud_flag)}</td>
            <td>${UI.statusPill(a.status)}</td>
            <td class="text-muted-soft text-tiny">${fmt.ago(a.applied_at)}</td></tr>`;
        }).join('');
      }
      UI.animateRings(); UI.animateBars();
    } catch (err) {
      UI.errorState('#dashboardRoot', err.message, () => initDashboard());
    }
  }

  /* ---------------------------------------------------- recommendations */
  async function initRecommendations() {
    const user = await IM.guard('student');
    if (!user) return;
    IM.mountChrome(user);
    const sid = IM.studentId();
    const grid = document.getElementById('recGrid');
    let currentPage = 1, browseMode = false;

    grid.innerHTML = UI.skeletonCards(6);
    document.getElementById('fTrust').addEventListener('input', e => {
      document.getElementById('trustLabel').textContent = e.target.value;
    });

    try {
      const cfg = await api(`/api/recommendations/${sid}?limit=1`);
      const domains = new Set([...(cfg.profile && cfg.profile.preferred_domain ? [cfg.profile.preferred_domain] : [])]);
      document.getElementById('algoFormula').textContent = cfg.config.formula;
      document.getElementById('algoNotes').innerHTML = cfg.config.notes.map(n => `<li>${escapeHtml(n)}</li>`).join('');
      document.getElementById('fDomain').innerHTML = '<option value="">All domains</option>' +
        ['Data Science & ML', 'Web Development', 'Backend Engineering', 'Mobile App Development',
         'Cloud & DevOps', 'Cybersecurity', 'Embedded & IoT', 'Mechanical Engineering',
         'Civil Engineering', 'Electrical Engineering', 'QA & Testing', 'UI/UX Design',
         'Business & Analytics', 'Blockchain & Web3']
          .map(d => `<option>${d}</option>`).join('');
      if (cfg.profile && cfg.profile.preferred_domain) {
        document.getElementById('fDomain').value = cfg.profile.preferred_domain;
      }
      if (cfg.needs_resume) {
        grid.innerHTML = `<div class="col-12">${UI.emptyState({
          title: 'Upload your resume to unlock ranked matches', icon: 'bi-file-earmark-person',
          message: cfg.empty_state.message, ctaLabel: 'Upload resume', ctaHref: '/student/profile' })}</div>`;
        renderFallback(cfg.fallback_listings || []);
        return;
      }
    } catch (err) {
      UI.errorState(grid, err.message, () => initRecommendations());
      return;
    }

    function renderFallback(listings) {
      if (!listings.length) return;
      document.getElementById('recGrid').insertAdjacentHTML('afterend', `
        <div class="col-12 mt-4" id="fallbackBox">
          <h5 class="fw-bold mb-3"><i class="bi bi-collection me-2 text-primary"></i>Highest-trust listings meanwhile</h5>
          <div class="row g-3">${listings.map(l => listingCard(l, { matchPct: null })).join('')}</div>
        </div>`);
      bindApplyButtons(document.getElementById('fallbackBox'));
    }

    async function load(extra = {}) {
      grid.innerHTML = UI.skeletonCards(6);
      const params = new URLSearchParams({
        limit: 12, page: currentPage,
        domain: document.getElementById('fDomain').value,
        work_mode: document.getElementById('fMode').value,
        min_trust: document.getElementById('fTrust').value,
        include_flagged: document.getElementById('fFlagged').checked,
        q: document.getElementById('fQuery').value.trim(),
        ...extra,
      });
      try {
        if (browseMode) {
          params.set('per_page', 12);
          params.set('sort', document.getElementById('fSort').value);
          const res = await api(`/api/internships?${params}`);
          let items = res.internships;
          if (document.getElementById('fBonus').checked && profileCache?.preferred_domain) {
            items = items.filter(i => i.domain === profileCache.preferred_domain);
          }
          grid.innerHTML = items.length
            ? items.map(l => listingCard(l, { matchPct: null })).join('')
            : `<div class="col-12">${UI.emptyState({ title: 'No listings match these filters',
                icon: 'bi-search', message: 'Try clearing the domain filter or lowering the minimum trust score.' })}</div>`;
          document.getElementById('resultMeta').textContent =
            `${res.meta.total} listings · browse mode`;
          UI.renderPagination('#recPagination', res.meta, (p) => { currentPage = p; load(); });
        } else {
          const res = await api(`/api/recommendations/${sid}?${params}`);
          let recs = res.recommendations;
          if (document.getElementById('fBonus').checked && res.profile?.preferred_domain) {
            recs = recs.filter(r => r.internship.domain === res.profile.preferred_domain);
          }
          if (document.getElementById('fSort').value === 'trust') {
            recs = [...recs].sort((a, b) => b.internship.trust_score - a.internship.trust_score);
          } else if (document.getElementById('fSort').value === 'stipend') {
            recs = [...recs].sort((a, b) => b.internship.stipend - a.internship.stipend);
          } else if (document.getElementById('fSort').value === 'recent') {
            recs = [...recs].sort((a, b) => (b.internship.posted_date || '').localeCompare(a.internship.posted_date || ''));
          }
          grid.innerHTML = recs.length
            ? recs.map(r => listingCard(r)).join('')
            : `<div class="col-12">${UI.emptyState({ title: res.empty_state?.title || 'No matches',
                icon: 'bi-stars', message: res.empty_state?.message || '' })}</div>`;
          document.getElementById('resultMeta').textContent =
            `${recs.length} ranked matches · ranked mode (85% match + 15% trust)`;
          document.getElementById('recPagination').innerHTML = '';
          bindApplyButtons(grid);
        }
        UI.animateRings(grid); UI.animateBars(grid);
      } catch (err) {
        UI.errorState(grid, err.message, () => load());
      }
    }

    // browse-mode toggle
    const toggle = document.createElement('button');
    toggle.className = 'btn btn-soft btn-sm ms-auto';
    toggle.innerHTML = '<i class="bi bi-collection me-1"></i>Switch to browse mode';
    document.querySelector('#fBonus').closest('.d-flex').appendChild(toggle);
    toggle.onclick = () => {
      browseMode = !browseMode;
      currentPage = 1;
      toggle.innerHTML = browseMode
        ? '<i class="bi bi-stars me-1"></i>Switch to ranked mode'
        : '<i class="bi bi-collection me-1"></i>Switch to browse mode';
      load();
    };

    document.getElementById('applyFilters').onclick = () => { currentPage = 1; load(); };
    ['fDomain', 'fMode', 'fSort', 'fFlagged', 'fBonus'].forEach(id =>
      document.getElementById(id).addEventListener('change', () => { currentPage = 1; load(); }));
    document.getElementById('fQuery').addEventListener('keydown', e => {
      if (e.key === 'Enter') { currentPage = 1; load(); }
    });

    // prefetch profile for the bonus filter
    api(`/api/student/profile/${sid}`).then(d => { profileCache = d.profile; }).catch(() => {});
    load();
  }

  /* ------------------------------------------------------------ profile */
  async function initProfile() {
    const user = await IM.guard('student');
    if (!user) return;
    IM.mountChrome(user);
    const sid = IM.studentId();
    if (!sid) { toast('No student profile linked to this account.', 'error'); return; }

    const fileInput = document.getElementById('resumeFile');
    const drop = document.getElementById('dropZone');
    const submit = document.getElementById('uploadBtn');

    fileInput.addEventListener('change', () => {
      const f = fileInput.files[0];
      document.getElementById('fileHint').textContent = f ? `${f.name} · ${(f.size / 1024).toFixed(0)} KB` : 'No file selected';
      document.getElementById('dropTitle').textContent = f ? f.name : 'Drop your resume here or click to browse';
      submit.disabled = !f;
    });
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault(); drop.classList.add('dragover');
    }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault(); drop.classList.remove('dragover');
    }));
    drop.addEventListener('drop', e => {
      if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        fileInput.dispatchEvent(new Event('change'));
      }
    });

    document.getElementById('uploadForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const f = fileInput.files[0];
      if (!f) return;
      const fd = new FormData();
      fd.append('resume', f);
      document.getElementById('uploadProgress').classList.remove('d-none');
      submit.disabled = true;
      submit.querySelector('[data-spin]').classList.remove('d-none');
      try {
        const res = await api('/api/upload-resume', { method: 'POST', formData: fd });
        toast(res.message, 'success', 5000);
        renderExtraction(res.extraction, res.profile);
        document.getElementById('uploadProgress').classList.add('d-none');
        submit.querySelector('[data-spin]').classList.add('d-none');
        fileInput.value = '';
        document.getElementById('dropTitle').textContent = 'Drop your resume here or click to browse';
        document.getElementById('fileHint').textContent = 'Parsed successfully ✓';
        loadUploads();
        IM.refreshUser();
      } catch (err) {
        toast(err.message, 'error', 6000);
        document.getElementById('uploadProgress').classList.add('d-none');
        submit.disabled = false;
        submit.querySelector('[data-spin]').classList.add('d-none');
      }
    });

    document.getElementById('profileForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('saveProfileBtn');
      btn.disabled = true;
      btn.querySelector('[data-spin]').classList.remove('d-none');
      try {
        const res = await api(`/api/student/profile/${sid}`, { method: 'PUT', body: {
          name: document.getElementById('pName').value.trim(),
          roll_number: document.getElementById('pRoll').value.trim(),
          college: document.getElementById('pCollege').value.trim(),
          branch: document.getElementById('pBranch').value.trim(),
          graduation_year: document.getElementById('pYear').value || null,
          cgpa: document.getElementById('pCgpa').value || null,
          preferred_domain: document.getElementById('pDomain').value,
          preferred_location: document.getElementById('pLocation').value.trim(),
          work_mode_pref: document.getElementById('pMode').value,
        }});
        profileCache = res.profile;
        toast(res.message + ' Recommendations will re-rank with the new domain bonus.',
              'success', 4200);
        fillForm(res.profile);
      } catch (err) {
        toast(err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.querySelector('[data-spin]').classList.add('d-none');
      }
    });

    async function loadUploads() {
      try {
        const d = await api(`/api/student/profile/${sid}`);
        const rows = d.uploads || [];
        document.getElementById('uploadHistory').innerHTML = rows.length
          ? rows.map(u => `<tr>
              <td class="text-truncate" style="max-width:180px" title="${escapeHtml(u.filename)}">
                ${escapeHtml(u.filename)}</td>
              <td><span class="badge-ghost">${u.skills_found}</span></td>
              <td><span class="badge-soft">${u.ats_score}</span></td>
              <td class="text-muted-soft text-tiny">${fmt.ago(u.created_at)}</td></tr>`).join('')
          : '<tr><td colspan="4" class="text-center text-muted-soft py-4">No uploads recorded yet.</td></tr>';
      } catch { /* ignore */ }
    }

    function fillForm(p) {
      document.getElementById('pName').value = p.name || '';
      document.getElementById('pRoll').value = p.roll_number || '';
      document.getElementById('pCollege').value = p.college || '';
      document.getElementById('pBranch').value = p.branch || '';
      document.getElementById('pYear').value = p.graduation_year || '';
      document.getElementById('pCgpa').value = p.cgpa || '';
      document.getElementById('pLocation').value = p.preferred_location || '';
      document.getElementById('pMode').value = p.work_mode_pref || 'any';
      const select = document.getElementById('pDomain');
      select.innerHTML = '<option value="">Not set</option>' +
        ['Data Science & ML', 'Web Development', 'Backend Engineering', 'Mobile App Development',
         'Cloud & DevOps', 'Cybersecurity', 'Embedded & IoT', 'Mechanical Engineering',
         'Civil Engineering', 'Electrical Engineering', 'QA & Testing', 'UI/UX Design',
         'Business & Analytics', 'Blockchain & Web3']
          .map(d => `<option ${d === p.preferred_domain ? 'selected' : ''}>${d}</option>`).join('');
    }

    function renderExtraction(x, p) {
      document.getElementById('sSkills').textContent = x.skills.length;
      document.getElementById('sCategories').textContent = x.skill_categories.length;
      document.getElementById('sAts').textContent = x.ats_score;
      document.getElementById('sComplete').textContent = `${p.completeness}%`;
      document.getElementById('cloudBox').innerHTML = x.skill_details.length
        ? UI.skillCloud(x.skill_details.map(s => ({ ...s, size: 13 + s.weight * 20 }))) : '';
      document.getElementById('domainBox').innerHTML = x.domains.length
        ? x.domains.slice(0, 6).map(d => `
            <div class="mb-3">
              <div class="d-flex justify-content-between small mb-1">
                <span class="fw-semibold">${escapeHtml(d.domain)}
                  ${d.domain === p.preferred_domain ? '<span class="badge-soft ms-1">preferred</span>' : ''}</span>
                <span class="text-muted-soft">${d.confidence}% confidence</span></div>
              ${UI.matchBar(d.confidence)}
              <div class="chip-row mt-2">${d.matched_skills.map(s =>
                `<span class="badge-ghost">${escapeHtml(s)}</span>`).join('')}</div>
            </div>`).join('')
        : '<p class="text-muted-soft small mb-0">No domain signal detected.</p>';
      document.getElementById('keywordCloud').innerHTML = x.keywords.map(([k, c]) =>
        `<span class="badge-ghost" style="font-size:${11 + Math.min(c, 4)}px">${escapeHtml(k)}</span>`).join('');
      const m = x.meta || {};
      document.getElementById('entityList').innerHTML = `
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Degree</span>
          <strong>${escapeHtml(m.degree || '—')}</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Branch</span>
          <strong>${escapeHtml(m.branch || '—')}</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">CGPA</span>
          <strong>${m.cgpa ?? '—'}</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Grad year</span>
          <strong>${m.graduation_year || '—'}</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Experience</span>
          <strong>${m.experience_months || 0} months</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Projects / certs</span>
          <strong>${m.project_count || 0} / ${m.certification_count || 0}</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Words / sentences</span>
          <strong>${m.word_count || 0} / ${x.sentences}</strong></div>`;
      document.getElementById('insightsBox').innerHTML = x.insights.map(i =>
        `<div class="insight ${i.level}"><i class="bi bi-${i.level === 'success' ? 'check-circle'
          : i.level === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
          <span>${escapeHtml(i.text)}</span></div>`).join('');

      UI.destroyChart(charts, 'cat');
      charts.cat = new Chart(document.getElementById('catChart'), {
        type: 'bar',
        data: { labels: x.skill_categories.map(c => c.category),
          datasets: [{ data: x.skill_categories.map(c => c.count), backgroundColor: '#8b5cf6',
            borderRadius: 8 }] },
        options: { indexAxis: 'y', plugins: { legend: { display: false } },
          scales: { x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef1f7' } },
                    y: { grid: { display: false } } } },
      });
      UI.animateBars();
      fillForm(p);
      if (!document.getElementById('pDomain').value && x.top_domain) {
        document.getElementById('pDomain').value = x.top_domain;
      }
    }
    window.__renderExtraction = renderExtraction;

    // initial load
    try {
      const d = await api(`/api/student/profile/${sid}`);
      profileCache = d.profile;
      fillForm(d.profile);
      document.getElementById('sSkills').textContent = d.stats.total_skills;
      document.getElementById('sCategories').textContent = d.stats.categories;
      document.getElementById('sAts').textContent = d.stats.ats_score;
      document.getElementById('sComplete').textContent = `${d.stats.completeness}%`;
      document.getElementById('cloudBox').innerHTML = d.skill_cloud.length
        ? UI.skillCloud(d.skill_cloud)
        : UI.emptyState({ title: 'No resume parsed yet', icon: 'bi-cloud-plus',
            message: 'Upload a PDF or DOCX resume above — extraction takes a couple of seconds.' });
      document.getElementById('domainBox').innerHTML = d.domain_matches.length
        ? d.domain_matches.map(dm => `<div class="mb-3">
            <div class="d-flex justify-content-between small mb-1">
              <span class="fw-semibold">${escapeHtml(dm.domain)}
                ${dm.is_preferred ? '<span class="badge-soft ms-1">preferred</span>' : ''}</span>
              <span class="text-muted-soft">${dm.confidence}% fit</span></div>
            ${UI.matchBar(dm.confidence)}
            <div class="chip-row mt-2">${dm.matched_skills.map(s =>
              `<span class="badge-ghost">${escapeHtml(s)}</span>`).join('')}</div></div>`).join('')
        : '<p class="text-muted-soft small mb-0">Upload a resume to see domain fit.</p>';

      const p = d.profile;
      if (p.skill_details && p.skill_details.length) {
        const byCat = {};
        (p.skill_details || []).forEach(s => { byCat[s.category] = (byCat[s.category] || 0) + 1; });
        UI.destroyChart(charts, 'cat');
        charts.cat = new Chart(document.getElementById('catChart'), {
          type: 'bar',
          data: { labels: Object.keys(byCat), datasets: [{ data: Object.values(byCat),
            backgroundColor: '#8b5cf6', borderRadius: 8 }] },
          options: { indexAxis: 'y', plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef1f7' } },
                      y: { grid: { display: false } } } },
        });
      }
      const meta = p.parsed_meta || {};
      if (meta.word_count) {
        document.getElementById('entityList').innerHTML = `
          <div class="d-flex justify-content-between"><span class="text-muted-soft">Degree</span><strong>${escapeHtml(meta.degree || '—')}</strong></div>
          <div class="d-flex justify-content-between"><span class="text-muted-soft">CGPA</span><strong>${meta.cgpa ?? p.cgpa ?? '—'}</strong></div>
          <div class="d-flex justify-content-between"><span class="text-muted-soft">Grad year</span><strong>${meta.graduation_year || p.graduation_year || '—'}</strong></div>
          <div class="d-flex justify-content-between"><span class="text-muted-soft">Experience</span><strong>${meta.experience_months || 0} months</strong></div>
          <div class="d-flex justify-content-between"><span class="text-muted-soft">Projects</span><strong>${meta.project_count || 0}</strong></div>
          <div class="d-flex justify-content-between"><span class="text-muted-soft">Words</span><strong>${meta.word_count}</strong></div>`;
      }
      if (p.skills && p.skills.length) {
        document.getElementById('insightsBox').innerHTML = `
          <div class="insight success"><i class="bi bi-check-circle"></i>
            <span>${p.skills.length} skills on file across
              ${new Set((p.skill_details || []).map(s => s.category)).size} categories, ATS score
              ${p.ats_score}/100.</span></div>
          <div class="insight info"><i class="bi bi-info-circle"></i>
            <span>Preferred domain set to <strong>${escapeHtml(p.preferred_domain || '—')}</strong> —
              listings in this domain get a +0.10 match bonus.</span></div>
          <div class="insight ${p.completeness >= 75 ? 'success' : 'warning'}">
            <i class="bi bi-${p.completeness >= 75 ? 'check-circle' : 'exclamation-triangle'}"></i>
            <span>Profile is ${p.completeness}% complete. Fill the remaining fields to improve
              recommendation accuracy.</span></div>`;
      }
      UI.animateBars();
      loadUploads();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  /* ------------------------------------------------------- applications */
  async function initApplications() {
    const user = await IM.guard('student');
    if (!user) return;
    IM.mountChrome(user);
    const sid = IM.studentId();
    const body = document.getElementById('appsBody');
    let page = 1;

    const STATUSES = ['applied', 'under_review', 'shortlisted', 'interview', 'selected', 'rejected'];

    async function load() {
      body.innerHTML = UI.skeletonRows(6, 6);
      const params = new URLSearchParams({ page, per_page: 10 });
      const status = document.getElementById('statusFilter').value;
      if (status) params.set('status', status);
      try {
        const d = await api(`/api/student/applications/${sid}?${params}`);
        const apps = d.applications;
        document.getElementById('aTotal').textContent = d.meta.total;
        document.getElementById('aProgress').textContent =
          apps.filter(a => ['under_review', 'shortlisted', 'interview'].includes(a.status)).length;
        document.getElementById('aSelected').textContent =
          apps.filter(a => a.status === 'selected').length;
        document.getElementById('aFlagged').textContent =
          apps.filter(a => a.internship && a.internship.fraud_flag).length;

        if (!apps.length) {
          body.innerHTML = `<tr><td colspan="6">${UI.emptyState({ title: 'No applications',
            icon: 'bi-send', message: 'Apply to internships from the recommendations page.',
            ctaLabel: 'Browse recommendations', ctaHref: '/student/recommendations' })}</td></tr>`;
        } else {
          body.innerHTML = apps.map(a => {
            const L = a.internship || {};
            return `<tr data-app="${a.id}">
              <td>
                <a href="/student/internship/${L.id}" class="fw-semibold text-dark d-block">${escapeHtml(L.title)}</a>
                <span class="text-muted-soft text-tiny">${escapeHtml(L.company)} · ${escapeHtml(L.location || '')}</span>
              </td>
              <td class="d-none d-md-table-cell">
                <div class="d-flex align-items-center gap-2" style="min-width:110px">
                  <span class="fw-bold text-tiny" style="color:var(--im-primary)">${Math.round((a.match_score || 0) * 100)}%</span>
                  <div class="flex-grow-1">${UI.matchBar((a.match_score || 0) * 100)}</div>
                </div></td>
              <td>${UI.trustBadge(L.badge, L.trust_score, L.fraud_flag)}</td>
              <td>
                <select class="form-select form-select-sm" data-status-select="${a.id}" style="width:auto">
                  ${STATUSES.map(s => `<option value="${s}" ${s === a.status ? 'selected' : ''}>
                    ${s.replace('_', ' ')}</option>`).join('')}
                </select></td>
              <td class="text-muted-soft text-tiny">${fmt.date(a.applied_at)}</td>
              <td class="text-end">
                <div class="d-flex gap-1 justify-content-end">
                  <button class="btn btn-soft btn-icon btn-sm" title="Give feedback"
                          data-feedback="${L.id}" data-title="${escapeHtml(L.title)}">
                    <i class="bi bi-chat-square-heart"></i></button>
                  <button class="btn btn-outline-danger btn-icon btn-sm" title="Withdraw"
                          data-delete="${a.id}"><i class="bi bi-trash3"></i></button>
                </div></td></tr>`;
          }).join('');
          bindRows();
        }
        UI.animateBars();
        UI.renderPagination('#appsPagination', d.meta, (p) => { page = p; load(); });
        renderChart(d.status_breakdown);
      } catch (err) {
        UI.errorState(body, err.message, load);
      }
    }

    function bindRows() {
      body.querySelectorAll('[data-status-select]').forEach(sel => {
        let previous = sel.value;
        sel.addEventListener('change', async () => {
          const id = sel.getAttribute('data-status-select');
          const next = sel.value;
          sel.classList.add('is-valid');       // optimistic
          try {
            await api(`/api/applications/${id}`, { method: 'PATCH', body: { status: next } });
            toast(`Status updated to “${next.replace('_', ' ')}”.`, 'success', 2200);
            previous = next;
          } catch (err) {
            sel.value = previous;              // rollback
            sel.classList.remove('is-valid');
            toast(err.message, 'error');
          } finally {
            setTimeout(() => sel.classList.remove('is-valid'), 1200);
          }
        });
      });
      body.querySelectorAll('[data-feedback]').forEach(btn => {
        btn.onclick = () => openFeedbackModal(Number(btn.getAttribute('data-feedback')),
          btn.getAttribute('data-title'));
      });
      body.querySelectorAll('[data-delete]').forEach(btn => {
        btn.onclick = async () => {
          const id = btn.getAttribute('data-delete');
          const row = btn.closest('tr');
          const ok = await UI.confirmModal({
            title: 'Withdraw application?',
            body: 'This removes the application from your history. You can re-apply later.',
            confirmLabel: 'Withdraw', variant: 'danger' });
          if (!ok) return;
          row.style.transition = 'opacity .25s';       // optimistic removal
          row.style.opacity = '0.4';
          try {
            await api(`/api/applications/${id}`, { method: 'DELETE' });
            row.remove();
            toast('Application withdrawn.', 'success', 2200);
            load();
          } catch (err) {
            row.style.opacity = '1';
            toast(err.message, 'error');
          }
        };
      });
    }

    function renderChart(breakdown) {
      const labels = STATUSES.map(s => s.replace('_', ' '));
      const values = STATUSES.map(s => (breakdown.find(b => b.status === s)?.count) || 0);
      UI.destroyChart(charts, 'apps');
      charts.apps = new Chart(document.getElementById('appStatusChart'), {
        type: 'doughnut',
        data: { labels, datasets: [{ data: values,
          backgroundColor: ['#6366f1', '#0ea5e9', '#f59e0b', '#8b5cf6', '#0f9d58', '#94a3b8'],
          borderWidth: 0, cutout: '62%' }] },
        options: { plugins: { legend: { position: 'bottom' } } },
      });
    }

    document.getElementById('statusFilter').addEventListener('change', () => { page = 1; load(); });
    document.getElementById('refreshApps').onclick = load;
    load();
  }

  /* ---------------------------------------------------- feedback page */
  async function initFeedbackPage() {
    const user = await IM.guard('student');
    if (!user) return;
    IM.mountChrome(user);
    const sid = IM.studentId();

    try {
      const [fb, apps] = await Promise.all([
        api(`/api/student/feedback/${sid}`),
        api(`/api/student/applications/${sid}?per_page=50`),
      ]);

      const fed = new Set(fb.feedback.map(f => f.internship_id));
      const pending = apps.applications.filter(a => !fed.has(a.internship_id));
      const pendingBox = document.getElementById('pendingFeedback');
      pendingBox.innerHTML = pending.length
        ? pending.slice(0, 6).map(a => `
          <div class="d-flex justify-content-between align-items-center gap-2 mb-2 pb-2"
               style="border-bottom:1px solid var(--im-border)">
            <div class="min-w-0">
              <div class="fw-semibold text-truncate small">${escapeHtml(a.internship?.title || '')}</div>
              <div class="text-muted-soft text-tiny">${escapeHtml(a.internship?.company || '')}
                ${a.internship?.badge ? ' · ' + UI.trustBadge(a.internship.badge, a.internship.trust_score, a.internship.fraud_flag) : ''}</div>
            </div>
            <button class="btn btn-soft btn-sm" data-pending-fb="${a.internship_id}"
                    data-title="${escapeHtml(a.internship?.title || '')}">Review</button>
          </div>`).join('')
        : UI.emptyState({ title: 'All caught up', icon: 'bi-emoji-smile',
            message: 'You have no pending listings to review.' });

      pendingBox.querySelectorAll('[data-pending-fb]').forEach(b =>
        b.onclick = () => openFeedbackModal(Number(b.getAttribute('data-pending-fb')),
          b.getAttribute('data-title')));

      document.getElementById('feedbackCount').textContent = `${fb.count} report(s)`;
      document.getElementById('feedbackList').innerHTML = fb.feedback.length
        ? fb.feedback.map(f => `
          <div class="d-flex gap-3 pb-3 mb-3" style="border-bottom:1px solid var(--im-border)">
            <div class="avatar" style="background:${f.verdict === 'Verified' ? 'var(--im-green)' : 'var(--im-red)'}">
              <i class="bi bi-${f.verdict === 'Verified' ? 'shield-check' : 'shield-exclamation'}"></i></div>
            <div class="flex-grow-1">
              <div class="d-flex justify-content-between flex-wrap gap-2">
                <div>
                  <div class="fw-semibold">${escapeHtml(f.internship_title || '')}</div>
                  <div class="text-muted-soft text-tiny">${escapeHtml(f.company || '')}</div>
                </div>
                <div class="text-end">
                  <span class="badge-trust ${f.verdict === 'Verified' ? 'badge-green' : 'badge-red'}">
                    <i class="bi bi-${f.verdict === 'Verified' ? 'check' : 'exclamation'}-circle"></i>
                    ${escapeHtml(f.verdict)}</span>
                  <div class="mt-1" style="color:#f59e0b">${'★'.repeat(f.rating)}<span
                    style="color:#d8dce8">${'★'.repeat(5 - f.rating)}</span></div>
                </div>
              </div>
              ${f.comment ? `<p class="small text-muted-soft mb-1 mt-2">“${escapeHtml(f.comment)}”</p>` : ''}
              <div class="text-muted-soft text-tiny">${fmt.ago(f.created_at)}</div>
            </div></div>`).join('')
        : UI.emptyState({ title: 'No feedback yet', icon: 'bi-chat-square-heart',
            message: 'After applying, tell us whether the listing looked Verified or Suspicious.' });
    } catch (err) {
      UI.errorState('#feedbackList', err.message);
    }
  }

  /* -------------------------------------------------------- detail page */
  async function initDetail() {
    const user = await IM.guard('student');
    if (!user) return;
    IM.mountChrome(user);
    const root = document.getElementById('detailRoot');
    const id = root.getAttribute('data-internship-id');
    const main = document.getElementById('detailMain');
    const side = document.getElementById('detailSide');

    UI.loading(main, 'Loading listing…', '320px');
    UI.loading(side, 'Fetching trust report…', '320px');

    try {
      const d = await api(`/api/internships/${id}`);
      const L = d.internship, T = d.trust;
      document.getElementById('detailTitle').textContent = L.title;

      main.innerHTML = `
        <div class="card mb-3">
          <div class="card-body">
            <div class="d-flex gap-3 align-items-start">
              <div class="company-logo" style="width:56px;height:56px;font-size:1.1rem;border-radius:14px">
                ${escapeHtml(initials(L.company))}</div>
              <div class="flex-grow-1">
                <h4 class="fw-bold mb-1">${escapeHtml(L.title)}</h4>
                <div class="text-muted-soft">${escapeHtml(L.company)} · ${escapeHtml(L.location || '')}</div>
                <div class="chip-row mt-2">
                  ${UI.trustBadge(L.badge, L.trust_score, L.fraud_flag)}
                  <span class="badge-ghost"><i class="bi bi-laptop me-1"></i>${escapeHtml(L.work_mode || '')}</span>
                  <span class="badge-ghost"><i class="bi bi-cash me-1"></i>${L.stipend ? fmt.inr(L.stipend) + '/mo' : 'Unpaid'}</span>
                  <span class="badge-ghost"><i class="bi bi-calendar3 me-1"></i>${L.duration_months} months</span>
                  <span class="badge-ghost"><i class="bi bi-people me-1"></i>${L.openings} openings</span>
                  <span class="badge-soft">${escapeHtml(L.domain || '')}</span>
                </div>
              </div>
            </div>
            <div class="row g-3 mt-3">
              <div class="col-sm-6 col-lg-3"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Posted</div>
                <div class="fw-semibold">${fmt.date(L.posted_date)}</div></div>
              <div class="col-sm-6 col-lg-3"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Apply by</div>
                <div class="fw-semibold">${fmt.date(L.deadline)}</div></div>
              <div class="col-sm-6 col-lg-3"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Recruiter email</div>
                <div class="fw-semibold text-truncate" title="${escapeHtml(L.contact_email || '')}">${escapeHtml(L.contact_email || '—')}</div></div>
              <div class="col-sm-6 col-lg-3"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Applicants</div>
                <div class="fw-semibold">${L.applicant_count}</div></div>
            </div>
          </div>
        </div>

        ${L.fraud_flag ? `<div class="alert alert-danger d-flex gap-2 align-items-start">
          <i class="bi bi-exclamation-octagon-fill fs-4"></i>
          <div><strong>This listing is flagged as suspicious (trust ${L.trust_score}/100).</strong><br>
          ${escapeHtml((L.red_flags || []).map(f => f.label).slice(0, 2).join(' · ') || 'Failed a domain hard check.')}
          Never pay a registration fee, deposit or "training charge". Report it below if you were asked to.</div>
        </div>` : ''}
        ${T.override_by_admin ? `<div class="alert alert-warning py-2 small">
          <i class="bi bi-person-check me-1"></i>Score manually reviewed by the placement cell:
          “${escapeHtml(T.override_note || '')}”</div>` : ''}

        <div class="card mb-3">
          <div class="card-header"><i class="bi bi-file-text me-2 text-primary"></i>Job description</div>
          <div class="card-body">
            <div style="white-space:pre-wrap;line-height:1.65">${escapeHtml(L.description || '')}</div>
            <div class="divider-y"></div>
            <div class="text-uppercase text-muted-soft text-tiny fw-bold mb-2">Skills required</div>
            <div class="chip-row">${(L.skills_required || []).map(s => {
              const mine = (profileCache?.skills || []).includes(s);
              return `<span class="skill-tag ${mine ? '' : 'badge-ghost'}"
                style="${mine ? '' : 'background:#f4f6fb;color:#64748b;border-color:#e6e9f2'}">
                ${mine ? '<i class="bi bi-check2"></i>' : ''}${escapeHtml(s)}</span>`;
            }).join('') || '<span class="text-muted-soft small">No specific skills listed.</span>'}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span><i class="bi bi-diagram-3 me-2 text-primary"></i>Trust report — how ${L.trust_score}/100 was computed</span>
            <button class="btn btn-soft btn-sm" id="recomputeTrust"><i class="bi bi-arrow-repeat me-1"></i>Re-run checks</button>
          </div>
          <div class="card-body" id="trustReport"></div>
        </div>`;

      side.innerHTML = `
        <div class="card mb-3">
          <div class="card-body text-center">
            ${UI.trustRing(L.trust_score, L.badge, '')}
            <div class="mt-3">${UI.trustBadge(L.badge, L.trust_score, L.fraud_flag)}</div>
            <div class="text-muted-soft small mt-2">${T.badge_legend[L.badge] || ''}</div>
            <div class="divider-y"></div>
            <div class="row text-center g-2">
              <div class="col-6"><div class="text-muted-soft text-tiny text-uppercase fw-bold">Rule score</div>
                <div class="fw-800">${Math.round((L.rule_score || 0) * 100)}%</div></div>
              <div class="col-6"><div class="text-muted-soft text-tiny text-uppercase fw-bold">ML fraud P</div>
                <div class="fw-800" style="color:${(L.ml_fraud_prob || 0) > 0.5 ? 'var(--im-red)' : 'var(--im-green)'}">
                  ${((L.ml_fraud_prob || 0) * 100).toFixed(1)}%</div></div>
            </div>
            <div class="divider-y"></div>
            <div class="d-grid gap-2">
              <button class="btn btn-gradient" id="applyBtn"
                      data-url="${escapeHtml(L.apply_url || '')}">
                <i class="bi bi-box-arrow-up-right me-1"></i>Apply on company site</button>
              <a class="btn btn-soft" href="/student/recommendations">
                <i class="bi bi-arrow-left me-1"></i>Back to recommendations</a>
              <button class="btn btn-outline-secondary" id="feedbackBtn">
                <i class="bi bi-chat-square-heart me-1"></i>Report / give feedback</button>
            </div>
          </div>
        </div>

        <div class="card mb-3">
          <div class="card-header"><i class="bi bi-globe2 me-2 text-primary"></i>Recruiter domain</div>
          <div class="card-body" id="domainBox"></div>
        </div>

        <div class="card">
          <div class="card-header"><i class="bi bi-clock-history me-2 text-primary"></i>Score history</div>
          <div class="card-body" id="historyBox"></div>
        </div>`;

      renderTrustReport(T, L);
      renderDomain(T.domain);
      document.getElementById('historyBox').innerHTML = d.history?.length
        ? `<div class="timeline">${d.history.map(h => `<div class="timeline-item">
            <div class="small fw-semibold">${escapeHtml(h.action)} ·
              ${h.old_score !== null && h.old_score !== undefined ? `${h.old_score} → ` : ''}${h.new_score ?? '—'}</div>
            <div class="text-muted-soft text-tiny">${escapeHtml(h.actor || 'system')} · ${fmt.dateTime(h.created_at)}</div>
            ${h.note ? `<div class="text-muted-soft text-tiny">“${escapeHtml(h.note)}”</div>` : ''}
          </div>`).join('')}</div>`
        : '<p class="text-muted-soft small mb-0">No score changes recorded yet.</p>';

      document.getElementById('applyBtn').onclick = (e) => {
        const btn = e.currentTarget;
        btn.setAttribute('data-apply', L.id);
        btn.setAttribute('data-title', L.title);
        applyToListing(btn);
      };
      document.getElementById('feedbackBtn').onclick = () => openFeedbackModal(L.id, L.title);
      document.getElementById('recomputeTrust').onclick = async (e) => {
        const b = e.currentTarget;
        b.disabled = true;
        b.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Re-running…';
        try {
          const res = await api(`/api/trustscore/${L.id}?refresh=true`);
          toast(`Trust re-checked: score ${res.trust.trust_score} (${res.trust.badge}).`, 'success');
          setTimeout(() => initDetail(), 600);
        } catch (err) {
          toast(err.message, 'error');
          b.disabled = false;
          b.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Re-run checks';
        }
      };

      // similar listings
      if (d.similar?.length) {
        document.getElementById('similarBox').innerHTML =
          `<h5 class="fw-bold mb-3"><i class="bi bi-collection me-2 text-primary"></i>Similar in ${escapeHtml(L.domain || '')}</h5>
           <div class="row g-3">${d.similar.map(s => listingCard(s, { matchPct: null })).join('')}</div>`;
        bindApplyButtons(document.getElementById('similarBox'));
      }
      UI.animateRings(root); UI.animateBars(root);
    } catch (err) {
      UI.errorState(main, err.message, () => initDetail());
      side.innerHTML = '';
    }
  }

  function renderTrustReport(T, L) {
    const b = T.breakdown || {};
    const domain = b.domain || {}, flags = b.red_flags || {}, complete = b.completeness || {}, ml = b.ml || {};
    const component = (title, sub, score, weight, color, extra = '') => `
      <div class="mb-3">
        <div class="d-flex justify-content-between align-items-center mb-1">
          <div><span class="fw-semibold">${title}</span>
            <span class="text-muted-soft text-tiny ms-2">weight ${weight}%</span></div>
          <span class="fw-800" style="color:${color}">${score}%</span>
        </div>
        ${UI.matchBar(score)}
        <div class="text-muted-soft text-tiny mt-1">${sub}</div>
        ${extra}
      </div>`;

    document.getElementById('trustReport').innerHTML = `
      <div class="formula-box mb-3">${escapeHtml(b.formula?.expression || '')}<br>
        → RuleScore = ${(b.formula?.rule_score ?? 0).toFixed(3)} ·
          MLFraudP = ${(ml.fraud_probability ?? 0).toFixed(3)} ·
          <strong>TrustScore = ${L.trust_score}</strong>${L.fraud_flag ? ' · FLAGGED' : ''}</div>
      ${component('Email &amp; domain validation', `${(domain.findings || []).length} check(s)`,
        domain.score ?? 0, domain.weight ?? 40, '#6366f1',
        (domain.findings || []).map(f => `<div class="flag-item ${f.level === 'danger' ? '' : 'medium'} mt-2">
          <div class="d-flex justify-content-between">
            <span class="small">${escapeHtml(f.label)}</span>
            <span class="sev" style="color:${f.level === 'danger' ? 'var(--im-red)'
              : f.level === 'warning' ? 'var(--im-amber)' : 'var(--im-green)'}">
              ${f.level}</span></div></div>`).join(''))}
      ${component('Red-flag phrase analysis', `${(flags.hits || []).length} phrase(s) matched`,
        flags.score ?? 100, flags.weight ?? 35, '#f59e0b',
        (flags.hits || []).map(h => `<div class="flag-item ${h.severity === 'high' ? '' : 'medium'} mt-2">
          <div class="d-flex justify-content-between gap-2">
            <span class="small">${escapeHtml(h.label)}</span>
            <span class="sev" style="color:${h.severity === 'high' ? 'var(--im-red)' : 'var(--im-amber)'}">
              ${h.severity}</span></div>
          <div class="text-muted-soft text-tiny mt-1">matched: “${escapeHtml(h.evidence)}”</div></div>`).join('')
          || '<div class="text-muted-soft text-tiny mt-1">No red-flag phrases detected.</div>')}
      ${component('Listing completeness', 'fields + description depth',
        complete.score ?? 0, complete.weight ?? 25, '#0f9d58',
        (complete.findings || []).map(f => `<div class="text-muted-soft text-tiny">·
          ${escapeHtml(f.label)}</div>`).join(''))}
      <div class="d-flex justify-content-between align-items-center mb-1">
        <div><span class="fw-semibold">ML fraud classifier</span>
          <span class="text-muted-soft text-tiny ms-2">weight ${ml.weight ?? 50}%</span></div>
        <span class="fw-800" style="color:${(ml.fraud_probability || 0) > .5 ? 'var(--im-red)' : 'var(--im-green)'}">
          P(fraud) ${((ml.fraud_probability ?? 0) * 100).toFixed(1)}%</span>
      </div>
      ${UI.matchBar((1 - (ml.fraud_probability ?? 0)) * 100)}
      <div class="text-muted-soft text-tiny mt-1">TF-IDF + engineered risk features →
        LogisticRegression (trained on labelled genuine/fraud listings).</div>`;
  }

  function renderDomain(dom) {
    if (!dom) { document.getElementById('domainBox').innerHTML = '<p class="small text-muted-soft mb-0">No domain data.</p>'; return; }
    const rep = dom.reputation || {};
    document.getElementById('domainBox').innerHTML = `
      <div class="d-flex justify-content-between align-items-start mb-2">
        <div><div class="fw-semibold text-truncate" style="max-width:200px">${escapeHtml(dom.domain || '—')}</div>
          <div class="text-muted-soft text-tiny">source: ${escapeHtml(dom.source || '—')}</div></div>
        <span class="badge-trust ${rep.level === 'success' ? 'badge-green'
          : rep.level === 'warning' ? 'badge-amber' : 'badge-red'}">${escapeHtml(rep.label || '')}</span>
      </div>
      <div class="small">
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Domain age</span>
          <strong>${dom.age_years ?? 0} years</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Free provider</span>
          <strong>${dom.is_free_provider ? 'Yes' : 'No'}</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Disposable</span>
          <strong>${dom.is_disposable ? 'Yes' : 'No'}</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">Blacklisted</span>
          <strong class="${dom.is_blacklisted ? 'text-danger' : ''}">${dom.is_blacklisted ? 'Yes' : 'No'}</strong></div>
        <div class="d-flex justify-content-between"><span class="text-muted-soft">MX record</span>
          <strong>${dom.mx_valid ? 'Valid' : 'Missing'}</strong></div>
      </div>`;
  }

  return { initDashboard, initRecommendations, initProfile, initApplications,
           initFeedbackPage, initDetail };
})();
