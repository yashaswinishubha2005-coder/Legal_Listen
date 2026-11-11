/* "How it works" page: theme toggle only. */
(function () {
  "use strict";
  const get = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const set = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } };
  const btn = document.getElementById("theme");
  const isDark = () => (document.documentElement.dataset.theme ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
  const apply = (th) => {
    if (th === "light" || th === "dark") document.documentElement.dataset.theme = th;
    btn.textContent = isDark() ? "☀️" : "🌙";
  };
  apply(get("ll_theme"));
  btn.addEventListener("click", () => { const n = isDark() ? "light" : "dark"; set("ll_theme", n); apply(n); });
})();
