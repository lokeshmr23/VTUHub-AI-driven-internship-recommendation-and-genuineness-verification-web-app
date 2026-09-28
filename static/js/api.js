/* =====================================================================
   InternMatch AI — API client, session handling, toasts
   ===================================================================== */
const IM = (() => {
  const TOKEN_KEY = 'im_token';
  const USER_KEY = 'im_user';

  /* Storage shim: sandboxed preview iframes can block localStorage entirely.
     Fall back to an in-memory store (the server also sets an auth cookie, so
     API calls still authenticate inside restricted iframes). */
  const memStore = {};
  const store = (() => {
    try {
      const probe = '__im_probe__';
      window.localStorage.setItem(probe, '1');
      window.localStorage.removeItem(probe);
      return window.localStorage;
    } catch (err) {
      console.warn('[InternMatch] localStorage unavailable — using in-memory session store.');
      return {
        getItem: (k) => (k in memStore ? memStore[k] : null),
        setItem: (k, v) => { memStore[k] = String(v); },
        removeItem: (k) => { delete memStore[k]; },
      };
    }
  })();

  const getToken = () => store.getItem(TOKEN_KEY);
  const getUser = () => {
    try { return JSON.parse(store.getItem(USER_KEY) || 'null'); }
    catch { return null; }
  };
  const setSession = (payload) => {
    if (payload.access_token) store.setItem(TOKEN_KEY, payload.access_token);
    if (payload.user) store.setItem(USER_KEY, JSON.stringify(payload.user));
  };
  const clearSession = () => {
    store.removeItem(TOKEN_KEY);
    store.removeItem(USER_KEY);
  };
  const studentId = () => {
    const u = getUser();
    if (!u) return null;
    if (u.profile && u.profile.id) return u.profile.id;
    return u.student_id || null;
  };

  class ApiError extends Error {
    constructor(message, status, payload) {
      super(message);
      this.status = status;
      this.payload = payload || {};
    }
  }

  async function api(path, options = {}) {
    const { method = 'GET', body, formData, auth = true, signal } = options;
    const headers = {};
    if (auth) {
      const t = getToken();
      if (t) headers['Authorization'] = `Bearer ${t}`;
    }
    let payload;
    if (formData) {
      payload = formData;
    } else if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }

    let res;
    try {
      res = await fetch(path, { method, headers, body: payload, signal,
                                credentials: 'include' });
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      throw new ApiError('Network error — is the server running?', 0);
    }

    let data = null;
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      try { data = await res.json(); } catch { data = null; }
    }
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || `Request failed (${res.status})`;
      if (res.status === 401 && auth) {
        clearSession();
        if (!location.pathname.startsWith('/login')) {
          toast('Your session expired. Please log in again.', 'warning');
          setTimeout(() => location.href = '/login', 900);
        }
      }
      throw new ApiError(msg, res.status, data);
    }
    return data;
  }

  /* ------------------------------------------------------------- toasts */
  function toast(message, type = 'info', timeout = 4200) {
    let stack = document.querySelector('.toast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'toast-stack';
      document.body.appendChild(stack);
    }
    const icons = { success: 'bi-check-circle-fill', error: 'bi-exclamation-octagon-fill',
                    warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
    const el = document.createElement('div');
    el.className = `im-toast ${type}`;
    el.innerHTML = `<i class="bi ${icons[type] || icons.info} t-icon"></i>
                    <div class="flex-grow-1">${escapeHtml(message)}</div>
                    <button class="btn-close btn-close-sm" style="font-size:.6rem"></button>`;
    el.querySelector('.btn-close').onclick = () => el.remove();
    stack.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s';
      setTimeout(() => el.remove(), 320); }, timeout);
    return el;
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>"']/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function initials(name) {
    return (name || '?').split(' ').filter(Boolean).slice(0, 2)
      .map(w => w[0].toUpperCase()).join('');
  }

  /* ------------------------------------------------------- auth guard */
  async function ensureSession() {
    /* Inside restricted iframes the in-memory store is empty after a page
       navigation, but the auth cookie still works — rehydrate from /me. */
    const user = getUser();
    if (user) return user;
    try {
      const data = await api('/api/auth/me', { auth: true });   // authenticates via cookie
      if (data && data.user) {
        setSession({ user: data.user });                        // token stays null -> cookie auth
        return data.user;
      }
    } catch { /* fall through to login */ }
    return null;
  }

  async function guard(requiredRole) {
    let user = getUser();
    if (!user) user = await ensureSession();
    if (!user) {
      location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
      return null;
    }
    if (requiredRole && user.role !== requiredRole) {
      toast(`This area is for ${requiredRole}s only.`, 'warning');
      setTimeout(() => location.href = user.role === 'admin' ? '/admin/dashboard' : '/student/dashboard', 700);
      return null;
    }
    return user;
  }

  /* --------------------------------------------------- session helpers */
  async function refreshUser() {
    try {
      const data = await api('/api/auth/me');
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      return data.user;
    } catch { return null; }
  }

  async function logout() {
    try { await api('/api/auth/logout', { method: 'POST', auth: false }); } catch { /* ignore */ }
    clearSession();
    toast('Signed out. See you soon!', 'success', 1800);
    setTimeout(() => location.href = '/', 500);
  }

  /* -------------------------------------------------------- UI chrome */
  function mountChrome(user, opts = {}) {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && user) {
      sidebar.querySelectorAll('[data-name]').forEach(el => el.textContent = user.name);
      sidebar.querySelectorAll('[data-email]').forEach(el => el.textContent = user.email);
      sidebar.querySelectorAll('[data-role]').forEach(el => el.textContent = user.role);
      sidebar.querySelectorAll('[data-initials]').forEach(el => el.textContent = initials(user.name));
    }
    document.querySelectorAll('[data-logout]').forEach(btn => btn.onclick = logout);

    const toggle = document.querySelector('.sidebar-toggle');
    if (toggle) {
      toggle.onclick = () => document.body.classList.toggle('sidebar-open');
    }
    const backdrop = document.querySelector('.sidebar-backdrop');
    if (backdrop) backdrop.onclick = () => document.body.classList.remove('sidebar-open');

    // highlight active nav item
    const path = location.pathname;
    document.querySelectorAll('.sidebar .nav-link').forEach(link => {
      const href = link.getAttribute('href');
      if (href && href !== '/' && (path === href || path.startsWith(href))) link.classList.add('active');
    });
  }

  return { api, ApiError, getToken, getUser, setSession, clearSession, studentId, toast,
           escapeHtml, initials, guard, ensureSession, refreshUser, logout, mountChrome };
})();

const { api, toast, escapeHtml, initials } = IM;
const fmt = {
  inr: (v) => v ? `₹${Number(v).toLocaleString('en-IN')}` : '—',
  date: (v) => v ? new Date(v).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—',
  dateTime: (v) => v ? new Date(v).toLocaleString('en-IN',
    { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—',
  num: (v) => Number(v || 0).toLocaleString('en-IN'),
  pct: (v) => `${Math.round(Number(v || 0))}%`,
  ago: (v) => {
    if (!v) return '—';
    const diff = (Date.now() - new Date(v).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 2592000) return `${Math.floor(diff / 86400)}d ago`;
    return fmt.date(v);
  },
};
