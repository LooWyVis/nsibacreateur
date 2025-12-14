// static/app.js
const state = {
  all: [],
  selectedTags: new Set(),
};

const $ = (id) => document.getElementById(id);

let ALL_TOPICS_SORTED = [];
let SHOW_ALL_TAGS = false;

function uniqSorted(arr) {
  return [...new Set(arr)].sort((a, b) => ("" + a).localeCompare("" + b, "fr"));
}

function buildSelect(el, values, labelAll) {
  el.innerHTML = "";
  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = labelAll;
  el.appendChild(opt0);
  values.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    el.appendChild(opt);
  });
}

function normalize(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .trim();
}

async function openLocalThenFallback(localPathFromDownloads, fallbackUrl) {
  if (localPathFromDownloads) {
    const localUrl = "/pdf/" + localPathFromDownloads.replace(/^downloads\//, "");
    try {
      const res = await fetch(localUrl, { method: "HEAD" });
      if (res.ok) {
        window.open(localUrl, "_blank", "noopener,noreferrer");
        return;
      }
    } catch (_) {}
  }
  if (fallbackUrl) {
    window.open(fallbackUrl, "_blank", "noopener,noreferrer");
  } else {
    alert("Fichier introuvable (local) et aucun lien de secours disponible.");
  }
}

/* ---------- Tags: propreté + tri fréquence + voir plus ---------- */

function isUsefulTag(t) {
  if (!t) return false;
  const s = String(t).trim();

  // Trop long = souvent une phrase
  if (s.length > 28) return false;

  // évite tags “bruit” si jamais il en reste
  const low = normalize(s);
  const bannedStarts = [
    "cet exercice",
    "sur la",
    "sur les",
    "deux parties",
    "principalement",
    "utilise la structure",
    "logique booleenne",
  ];
  if (bannedStarts.some((b) => low.startsWith(b))) return false;

  // parenthèses résiduelles
  if (s.includes("(") || s.includes(")")) return false;

  // Trop de mots => phrase
  const words = s.split(/\s+/);
  if (words.length >= 4) return false;

  return true;
}

function buildTopicStats(exercises) {
  const freq = new Map();
  exercises.forEach((ex) => {
    (ex.topics || []).forEach((t) => {
      const tag = String(t).trim();
      if (!isUsefulTag(tag)) return;
      freq.set(tag, (freq.get(tag) || 0) + 1);
    });
  });

  return [...freq.entries()]
    .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], "fr"))
    .map(([tag]) => tag);
}

function renderTags() {
  const tagsEl = $("tags");
  const filterEl = $("tagFilter");
  const query = filterEl ? normalize(filterEl.value) : "";

  tagsEl.innerHTML = "";

  const baseList = ALL_TOPICS_SORTED.filter(
    (t) => !query || normalize(t).includes(query)
  );

  const limit = 40;
  const list = SHOW_ALL_TAGS ? baseList : baseList.slice(0, limit);

  list.forEach((t) => {
    const btn = document.createElement("button");
    btn.className = "tag" + (state.selectedTags.has(t) ? " on" : "");
    btn.textContent = t;
    btn.onclick = () => {
      if (state.selectedTags.has(t)) state.selectedTags.delete(t);
      else state.selectedTags.add(t);
      refresh();
      renderTags();
    };
    tagsEl.appendChild(btn);
  });

  if (baseList.length > limit) {
    const toggle = document.createElement("button");
    toggle.className = "tag";
    toggle.textContent = SHOW_ALL_TAGS
      ? "Voir moins"
      : `Voir plus (+${baseList.length - limit})`;
    toggle.onclick = () => {
      SHOW_ALL_TAGS = !SHOW_ALL_TAGS;
      renderTags();
    };
    tagsEl.appendChild(toggle);
  }
}

/* ---------- Filtrage ---------- */

function matches(ex) {
  const q = normalize($("q").value);
  const year = $("year").value;
  const session = $("session").value;
  const points = $("points").value;

  if (year && String(ex.year) !== String(year)) return false;
  if (session && ex.session !== session) return false;
  if (points && String(ex.points) !== String(points)) return false;

  // tags: match ALL tags sélectionnés
  if (state.selectedTags.size > 0) {
    const exTopics = new Set((ex.topics || []).map((t) => t));
    for (const t of state.selectedTags) {
      if (!exTopics.has(t)) return false;
    }
  }

  // mode strict: n'utiliser QUE les thèmes sélectionnés
  const strict = $("onlySelectedSearch")?.checked;
  if (strict && state.selectedTags.size > 0) {
    const exTopics = new Set((ex.topics || []).map((t) => t));
    for (const t of exTopics) {
      if (!state.selectedTags.has(t)) return false;
    }
  }

  // recherche texte
  if (!q) return true;

  const hay = normalize(
    [
      ex.session,
      ex.subject_label,
      ex.code,
      `exercice ${ex.exercise}`,
      `${ex.points} points`,
      (ex.topics || []).join(" "),
      ex.raw,
    ].join(" | ")
  );

  return hay.includes(q);
}

/* ---------- Cartes ---------- */

function card(ex) {
  const el = document.createElement("article");
  el.className = "card";

  const title = document.createElement("h3");
  title.textContent = `${ex.year} — ${ex.session} — ${ex.subject_label} — Ex ${ex.exercise} (${ex.points} pts)`;
  el.appendChild(title);

  const meta = document.createElement("p");
  meta.className = "muted";

  const strict = $("onlySelectedSearch")?.checked;
  let shownTopics = ex.topics || [];
  if (strict && state.selectedTags.size > 0) {
    shownTopics = shownTopics.filter((t) => state.selectedTags.has(t));
  }

  meta.textContent = `${ex.code} · ${shownTopics.join(", ") || "—"}`;
  el.appendChild(meta);

  const raw = document.createElement("p");
  raw.textContent = ex.raw || "";
  el.appendChild(raw);

  const actions = document.createElement("div");
  actions.className = "actions";

  const b1 = document.createElement("button");
  b1.className = "btn";
  b1.textContent = "Ouvrir le sujet (PDF)";
  b1.onclick = () =>
    openLocalThenFallback(ex.local_subject_file, ex.pdf_subject_url);
  actions.appendChild(b1);

  const corr = (ex.corriges || []).filter((c) => c.url);

  if (corr.length === 1) {
    const b2 = document.createElement("button");
    b2.className = "btn";
    b2.textContent = "Ouvrir le corrigé";
    b2.onclick = () => openLocalThenFallback(corr[0].local_file, corr[0].url);
    actions.appendChild(b2);
  } else if (corr.length > 1) {
    const sel = document.createElement("select");
    sel.className = "select";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "Choisir un corrigé…";
    sel.appendChild(opt0);

    corr.forEach((c, i) => {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = c.label || `Corrigé ${i + 1}`;
      sel.appendChild(opt);
    });

    const b2 = document.createElement("button");
    b2.className = "btn";
    b2.textContent = "Ouvrir";
    b2.onclick = () => {
      const i = Number(sel.value);
      if (Number.isNaN(i) || sel.value === "") return;
      openLocalThenFallback(corr[i].local_file, corr[i].url);
    };

    actions.appendChild(sel);
    actions.appendChild(b2);
  }

  el.appendChild(actions);
  return el;
}

/* ---------- Refresh ---------- */

function refresh() {
  const filtered = state.all.filter(matches);
  $("count").textContent = `${filtered.length} exercice(s)`;

  const res = $("results");
  res.innerHTML = "";
  filtered.slice(0, 400).forEach((ex) => res.appendChild(card(ex)));
}

/* ---------- Init ---------- */

async function init() {
  const res = await fetch("/data/exercises.json");
  state.all = await res.json();

  buildSelect($("year"), uniqSorted(state.all.map((x) => x.year)), "Toutes les années");
  buildSelect(
    $("session"),
    uniqSorted(state.all.map((x) => x.session)),
    "Toutes les sessions"
  );
  buildSelect(
    $("points"),
    uniqSorted(state.all.map((x) => x.points)),
    "Tous les points"
  );

  // Tags
  ALL_TOPICS_SORTED = buildTopicStats(state.all);
  SHOW_ALL_TAGS = false;
  renderTags();

  // listeners filtres
  ["q", "year", "session", "points"].forEach((id) =>
    $(id).addEventListener("input", refresh)
  );

  const onlyEl = $("onlySelectedSearch");
  if (onlyEl) onlyEl.addEventListener("change", () => {
    refresh();
  });

  const tagFilterEl = $("tagFilter");
  if (tagFilterEl)
    tagFilterEl.addEventListener("input", () => {
      SHOW_ALL_TAGS = false;
      renderTags();
    });

  $("reset").onclick = () => {
    $("q").value = "";
    $("year").value = "";
    $("session").value = "";
    $("points").value = "";
    state.selectedTags.clear();
    SHOW_ALL_TAGS = false;

    if ($("tagFilter")) $("tagFilter").value = "";
    // option: on ne force pas la checkbox strict à off, mais tu peux si tu veux :
    // if ($("onlySelectedSearch")) $("onlySelectedSearch").checked = false;

    renderTags();
    refresh();
  };

  refresh();
}

init().catch((err) => {
  console.error(err);
  alert("Impossible de charger exercises.json. Vérifie que downloads/exercises.json existe.");
});
