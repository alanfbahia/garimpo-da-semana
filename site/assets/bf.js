/* Countdown for the Black Friday page (no inline scripts: CSP). */
(function () {
  var end = new Date("2026-11-27T00:00:00-03:00");
  var box = document.getElementById("countdown");
  if (!box) return;
  var c = {};
  box.querySelectorAll("[data-k]").forEach(function (n) { c[n.dataset.k] = n; });
  function pad(n) { return n < 10 ? "0" + n : String(n); }
  function tick() {
    var s = Math.max(0, Math.floor((end - new Date()) / 1000));
    c.d.textContent = pad(Math.floor(s / 86400));
    c.h.textContent = pad(Math.floor((s % 86400) / 3600));
    c.m.textContent = pad(Math.floor((s % 3600) / 60));
    c.s.textContent = pad(s % 60);
  }
  tick();
  setInterval(tick, 1000);
})();
