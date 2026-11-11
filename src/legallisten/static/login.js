/* LegalListen sign-in page. No external dependencies. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
  };
  let lang = store.get("ll_lang") || "en";
  let mode = "in";                                   // in | up
  const ui = () => (window.UI[lang] || window.UI.en);

  function applyUI() {
    const t = ui();
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(e => { const k = e.dataset.i18n; if (t[k]) e.textContent = t[k]; });
    document.querySelectorAll(".lang-seg button").forEach(b => b.classList.toggle("active", b.dataset.lang === lang));
    setMode(mode);
  }

  function setMode(m) {
    const t = ui();
    mode = m;
    $("#tab-in").classList.toggle("active", m === "in"); $("#tab-in").setAttribute("aria-selected", String(m === "in"));
    $("#tab-up").classList.toggle("active", m === "up"); $("#tab-up").setAttribute("aria-selected", String(m === "up"));
    $("#f-name").hidden = m !== "up";
    $("#pw-meter").hidden = m !== "up";
    $("#form-title").textContent = m === "up" ? t.a_create_title : t.a_welcome;
    $("#form-sub").textContent = m === "up" ? t.a_create_sub : t.a_welcome_sub;
    $("#submit span").textContent = m === "up" ? t.a_signup : t.a_signin;
    $("#password").autocomplete = m === "up" ? "new-password" : "current-password";
    error("");
    meter();
  }

  function error(msg) { const e = $("#auth-error"); e.textContent = msg || ""; e.hidden = !msg; }

  // Rough strength guide: length matters most; variety helps.
  function meter() {
    const pw = $("#password").value, t = ui();
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
    if (/\d/.test(pw) || /[^\w\s]/.test(pw)) score++;
    const names = [t.a_pw0, t.a_pw1, t.a_pw2, t.a_pw3, t.a_pw4];
    const m = $("#pw-meter");
    m.dataset.score = pw ? String(score) : "";
    $("#pw-text").textContent = pw ? names[score] : t.a_pw_hint;
  }

  async function submit(ev) {
    ev.preventDefault();
    const t = ui();
    const email = $("#email").value.trim(), password = $("#password").value, name = $("#name").value.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email)) { error(t.a_err_email); $("#email").focus(); return; }
    if (password.length < 8) { error(t.a_err_pw); $("#password").focus(); return; }
    if (mode === "up" && !name) { error(t.a_err_name); $("#name").focus(); return; }
    $("#submit").disabled = true; error("");
    try {
      const res = await fetch(mode === "up" ? "/api/auth/register" : "/api/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mode === "up" ? { name, email, password, lang } : { email, password }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const d = body.detail;
        error(res.status === 401 ? t.a_err_wrong : res.status === 409 ? t.a_err_exists : res.status === 429 ? t.a_err_slow
          : typeof d === "string" ? d : t.a_err_generic);
        return;
      }
      store.del("ll_guest");
      if (body.user && body.user.lang && mode === "in") store.set("ll_lang", body.user.lang);
      location.href = "/";
    } catch (e) { error(t.a_err_generic); }
    finally { $("#submit").disabled = false; }
  }

  function isDark() { return (document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark"; }
  function applyTheme(th) {
    if (th === "light" || th === "dark") document.documentElement.dataset.theme = th;
    $("#theme").textContent = isDark() ? "☀️" : "🌙";
  }

  async function init() {
    applyTheme(store.get("ll_theme"));
    // Already signed in? Go straight to the app.
    try { const r = await (await fetch("/api/auth/me")).json(); if (r.user) { location.replace("/"); return; } } catch (e) { /* offline */ }
    if (location.hash === "#signup") mode = "up";
    applyUI();
    $("#tab-in").addEventListener("click", () => setMode("in"));
    $("#tab-up").addEventListener("click", () => setMode("up"));
    $("#auth-form").addEventListener("submit", submit);
    $("#password").addEventListener("input", meter);
    $("#pw-toggle").addEventListener("click", () => {
      const p = $("#password"); const show = p.type === "password";
      p.type = show ? "text" : "password"; $("#pw-toggle").textContent = show ? "🙈" : "👁";
      $("#pw-toggle").setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
    $("#guest").addEventListener("click", () => { store.set("ll_guest", "1"); location.href = "/"; });
    document.querySelectorAll(".lang-seg button").forEach(b => b.addEventListener("click", () => {
      lang = b.dataset.lang; store.set("ll_lang", lang); applyUI();
    }));
    $("#theme").addEventListener("click", () => { const n = isDark() ? "light" : "dark"; store.set("ll_theme", n); applyTheme(n); });
    $("#email").focus();
  }
  document.addEventListener("DOMContentLoaded", init);
})();
