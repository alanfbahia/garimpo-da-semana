/* Garimpo da Semana — renders the weekly best-seller catalog from data/products.json.
   All product fields are untrusted input: text goes through textContent, links and images
   are checked against host allowlists before use. */
(function () {
  "use strict";

  var LINK_HOSTS = [
    "shopee.com.br", "s.shopee.com.br", "shope.ee",
    "mercadolivre.com.br", "produto.mercadolivre.com.br", "www.mercadolivre.com.br",
    "mercadolivre.com", "meli.la"
  ];
  var IMAGE_HOST_SUFFIXES = [".susercontent.com", ".shopee.com.br", ".mlstatic.com"];
  var STORE_LABEL = { shopee: "Shopee", mercadolivre: "Mercado Livre" };
  var BLACK_FRIDAY = new Date("2026-11-27T00:00:00-03:00");

  var state = { category: "all", store: "all", query: "" };
  var data = null;

  // ---------- helpers ----------
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function hostAllowed(host, list) {
    host = host.toLowerCase();
    return list.some(function (h) { return host === h || host.endsWith("." + h); });
  }

  function safeLink(url) {
    try {
      var u = new URL(url);
      if (u.protocol !== "https:") return null;
      return hostAllowed(u.hostname, LINK_HOSTS) ? u.href : null;
    } catch (e) { return null; }
  }

  function safeImage(url) {
    try {
      var u = new URL(url, location.href);
      if (u.protocol !== "https:") return null;
      var host = u.hostname.toLowerCase();
      var ok = IMAGE_HOST_SUFFIXES.some(function (s) { return host.endsWith(s); });
      return ok ? u.href : null;
    } catch (e) { return null; }
  }

  var brl = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function compactSold(n) {
    if (!n || n < 1) return "";
    if (n >= 1000) {
      var k = Math.floor(n / 1000);
      return k + " mil+ vendidos";
    }
    return n + " vendidos";
  }

  function stars(r) {
    var full = Math.round(r);
    return "★★★★★".slice(0, full) + "☆☆☆☆☆".slice(0, 5 - full);
  }

  function discount(p) {
    if (!p.old_price || p.old_price <= p.price) return 0;
    return Math.round((1 - p.price / p.old_price) * 100);
  }

  function normalize(s) {
    return (s || "").toString().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  // Category illustration used when there is no product photo (or it fails to load).
  var ICONS = {
    casa: '<path d="M30 58 L60 32 L90 58 V90 H30 Z" fill="#ffd9c2"/><rect x="52" y="66" width="16" height="24" rx="2" fill="#f26b1d"/><path d="M24 60 L60 28 L96 60" fill="none" stroke="#c9520e" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
    pet: '<ellipse cx="60" cy="74" rx="18" ry="15" fill="#f26b1d"/><circle cx="38" cy="54" r="8" fill="#f9a46b"/><circle cx="52" cy="42" r="8" fill="#f9a46b"/><circle cx="68" cy="42" r="8" fill="#f9a46b"/><circle cx="82" cy="54" r="8" fill="#f9a46b"/>',
    beleza: '<rect x="48" y="44" width="24" height="46" rx="6" fill="#f26b1d"/><rect x="52" y="30" width="16" height="16" rx="3" fill="#c9520e"/><rect x="52" y="58" width="16" height="18" rx="3" fill="#ffd9c2"/>',
    tecnologia: '<path d="M34 66 a26 26 0 0 1 52 0" fill="none" stroke="#c9520e" stroke-width="7" stroke-linecap="round"/><rect x="28" y="62" width="16" height="26" rx="6" fill="#f26b1d"/><rect x="76" y="62" width="16" height="26" rx="6" fill="#f26b1d"/>',
    auto: '<circle cx="38" cy="78" r="13" fill="none" stroke="#c9520e" stroke-width="7"/><circle cx="84" cy="78" r="13" fill="none" stroke="#c9520e" stroke-width="7"/><path d="M38 78 L56 52 H72 L84 78 M56 52 L50 42 H40" fill="none" stroke="#f26b1d" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
    moda: '<path d="M44 32 L60 40 L76 32 L94 46 L84 58 L78 54 V90 H42 V54 L36 58 L26 46 Z" fill="#f26b1d"/><path d="M52 34 Q60 46 68 34" fill="#ffd9c2"/>',
    esporte: '<rect x="26" y="54" width="10" height="20" rx="3" fill="#c9520e"/><rect x="84" y="54" width="10" height="20" rx="3" fill="#c9520e"/><rect x="36" y="48" width="10" height="32" rx="3" fill="#f26b1d"/><rect x="74" y="48" width="10" height="32" rx="3" fill="#f26b1d"/><rect x="46" y="60" width="28" height="8" rx="2" fill="#f9a46b"/>'
  };

  function iconSvg(category) {
    var body = ICONS[category] || ICONS.casa;
    var wrap = document.createElement("span");
    wrap.innerHTML = '<svg viewBox="0 0 120 120" role="img" aria-hidden="true"><rect width="120" height="120" fill="#fbf1ea"/>' + body + "</svg>";
    return wrap.firstChild;
  }

  // ---------- card ----------
  function card(p, rankLabel) {
    var link = safeLink(p.url);
    var c = el("article", "card");

    var media = el("div", "card-img");
    var img = safeImage(p.image);
    if (img) {
      var i = new Image();
      i.loading = "lazy";
      i.decoding = "async";
      i.alt = p.title;
      i.referrerPolicy = "no-referrer";
      i.src = img;
      i.addEventListener("error", function () { media.replaceChild(iconSvg(p.category), i); });
      media.appendChild(i);
    } else {
      media.appendChild(iconSvg(p.category));
    }
    var off = discount(p);
    if (off >= 5) {
      var b = el("div", "badge-off", off + "%");
      b.appendChild(el("small", null, "OFF"));
      media.appendChild(b);
    }
    if (rankLabel) media.appendChild(el("div", "badge-rank", rankLabel));
    c.appendChild(media);

    var body = el("div", "card-body");
    body.appendChild(el("span", "store " + p.store, STORE_LABEL[p.store] || p.store));
    body.appendChild(el("h3", "title", p.title));

    var meta = el("div", "meta");
    if (p.rating) {
      meta.appendChild(el("span", "stars", stars(p.rating)));
      meta.appendChild(el("span", null, p.rating.toFixed(1).replace(".", ",")));
    }
    var sold = compactSold(p.sold);
    if (sold) meta.appendChild(el("span", null, "· " + sold));
    body.appendChild(meta);

    if (off >= 5) body.appendChild(el("span", "price-old", "R$ " + brl.format(p.old_price)));
    var price = el("div", "price");
    var now = el("span", "price-now");
    now.appendChild(el("span", "cur", "R$"));
    now.appendChild(document.createTextNode(brl.format(p.price)));
    price.appendChild(now);
    if (off >= 5) price.appendChild(el("span", "price-off", off + "% OFF"));
    body.appendChild(price);

    if (p.free_shipping) body.appendChild(el("span", "ship", "Frete grátis"));

    if (link) {
      var label = p.store === "mercadolivre" ? "Ver no Mercado Livre" : "Ver na Shopee";
      var a = el("a", "btn-buy " + p.store, label);
      a.href = link;
      a.target = "_blank";
      a.rel = "sponsored nofollow noopener noreferrer";
      body.appendChild(a);
    }
    c.appendChild(body);
    return c;
  }

  // ---------- filtering ----------
  function matches(p) {
    if (state.category !== "all" && p.category !== state.category) return false;
    if (state.store !== "all" && p.store !== state.store) return false;
    if (state.query) {
      var hay = normalize(p.title + " " + (p.tags || []).join(" "));
      if (hay.indexOf(state.query) === -1) return false;
    }
    return true;
  }

  function fill(container, list, rankFn) {
    container.textContent = "";
    if (!list.length) {
      var e = el("div", "empty");
      e.appendChild(el("p", null, "Nenhum produto encontrado com esses filtros."));
      var btn = el("button", null, "Limpar filtros");
      btn.type = "button";
      btn.addEventListener("click", resetFilters);
      e.appendChild(btn);
      container.appendChild(e);
      return;
    }
    list.forEach(function (p, idx) { container.appendChild(card(p, rankFn ? rankFn(p, idx) : null)); });
  }

  function render() {
    var all = data.products.filter(matches);

    var top = all.slice().sort(function (a, b) { return (b.sold || 0) - (a.sold || 0); });
    fill(document.getElementById("grid"), top, function (p, i) { return i < 3 ? "#" + (i + 1) + " mais vendido" : null; });

    var flash = all.filter(function (p) { return discount(p) >= 15; })
      .sort(function (a, b) { return discount(b) - discount(a); }).slice(0, 12);
    fill(document.getElementById("flash"), flash);

    var cheap = all.filter(function (p) { return p.price <= 50; })
      .sort(function (a, b) { return (b.sold || 0) - (a.sold || 0); }).slice(0, 12);
    fill(document.getElementById("cheap"), cheap);
  }

  function resetFilters() {
    state = { category: "all", store: "all", query: "" };
    document.getElementById("q").value = "";
    syncPressed();
    render();
  }

  function syncPressed() {
    document.querySelectorAll("#cat-chips .chip").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.cat === state.category));
    });
    document.querySelectorAll("#store-tabs button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.store === state.store));
    });
  }

  // ---------- setup ----------
  function buildChips() {
    var box = document.getElementById("cat-chips");
    var cats = [{ id: "all", label: "Todos" }].concat(data.categories || []);
    cats.forEach(function (c) {
      var b = el("button", "chip", c.label);
      b.type = "button";
      b.dataset.cat = c.id;
      b.setAttribute("aria-pressed", String(c.id === "all"));
      b.addEventListener("click", function () { state.category = c.id; syncPressed(); render(); });
      box.appendChild(b);
    });
  }

  function wireControls() {
    document.querySelectorAll("#store-tabs button").forEach(function (b) {
      b.addEventListener("click", function () { state.store = b.dataset.store; syncPressed(); render(); });
    });
    var q = document.getElementById("q");
    var t;
    q.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(function () { state.query = normalize(q.value.trim()); render(); }, 150);
    });
    document.getElementById("search-form").addEventListener("submit", function (e) {
      e.preventDefault();
      state.query = normalize(q.value.trim());
      render();
      document.getElementById("top-title").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function wireMeta() {
    var m = data.meta || {};
    if (m.demo) document.getElementById("demo-note").hidden = false;
    if (m.updated_at) {
      var d = new Date(m.updated_at);
      if (!isNaN(d)) {
        document.getElementById("updated").textContent =
          "Atualizado em " + d.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
      }
    }
    var tg = m.telegram_url;
    if (tg && /^https:\/\/t\.me\/[A-Za-z0-9_+]+$/.test(tg)) {
      ["tg-header", "tg-band"].forEach(function (id) {
        var a = document.getElementById(id);
        a.href = tg;
        a.target = "_blank";
      });
    }
    document.getElementById("year").textContent = String(new Date().getFullYear());
  }

  function startCountdown() {
    var box = document.getElementById("countdown");
    var cells = {};
    box.querySelectorAll("[data-k]").forEach(function (n) { cells[n.dataset.k] = n; });
    function pad(n) { return n < 10 ? "0" + n : String(n); }
    function tick() {
      var diff = Math.max(0, BLACK_FRIDAY - new Date());
      var s = Math.floor(diff / 1000);
      cells.d.textContent = pad(Math.floor(s / 86400));
      cells.h.textContent = pad(Math.floor((s % 86400) / 3600));
      cells.m.textContent = pad(Math.floor((s % 3600) / 60));
      cells.s.textContent = pad(s % 60);
    }
    tick();
    setInterval(tick, 1000);
  }

  function init(json) {
    data = json;
    data.products = (data.products || []).filter(function (p) {
      return p && typeof p.title === "string" && typeof p.price === "number" && STORE_LABEL[p.store];
    });
    buildChips();
    wireControls();
    wireMeta();
    render();
  }

  startCountdown();
  if (window.__GARIMPO_DATA__) {
    init(window.__GARIMPO_DATA__);
  } else {
    fetch("data/products.json", { cache: "no-cache" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(init)
      .catch(function () {
        document.getElementById("grid").appendChild(
          el("p", "empty", "Não foi possível carregar os produtos agora. Recarregue a página em alguns instantes."));
      });
  }
})();
