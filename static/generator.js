const $ = (id) => document.getElementById(id);

function normalize(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD").replace(/\p{Diacritic}/gu, "")
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
  if (fallbackUrl) window.open(fallbackUrl, "_blank", "noopener,noreferrer");
  else alert("Fichier introuvable (local) et aucun lien de secours.");
}

let EXS = [];
let ALL_TAGS = [];
let selected = new Set();

function computeTags(exs) {
  const freq = new Map();
  exs.forEach(ex => (ex.topics || []).forEach(t => {
    const tag = String(t).trim();
    if (!tag) return;
    freq.set(tag, (freq.get(tag) || 0) + 1);
  }));
  return [...freq.entries()]
    .sort((a,b) => (b[1]-a[1]) || a[0].localeCompare(b[0], "fr"))
    .map(([t]) => t);
}

function renderTags() {
  const q = normalize($("tagSearch").value);
  const list = ALL_TAGS.filter(t => !q || normalize(t).includes(q)).slice(0, 120);

  $("tagList").innerHTML = "";
  list.forEach(t => {
    const b = document.createElement("button");
    b.className = "tag" + (selected.has(t) ? " on" : "");
    b.textContent = t;
    b.onclick = () => {
      if (selected.has(t)) selected.delete(t);
      else selected.add(t);
      $("selCount").textContent = `${selected.size} tag(s) sélectionné(s)`;
      renderTags();
    };
    $("tagList").appendChild(b);
  });
}

function card(ex) {
  const el = document.createElement("article");
  el.className = "card";

  const title = document.createElement("h3");
  title.textContent = `${ex.year} — ${ex.session} — ${ex.subject_label} — Ex ${ex.exercise} (${ex.points} pts)`;
  el.appendChild(title);

  const meta = document.createElement("p");
  meta.className = "muted";
  const used = (ex.topics_used && ex.topics_used.length) ? ex.topics_used : (ex.topics || []);
  meta.textContent = `${ex.code} · ${used.join(", ") || "—"}`;
  el.appendChild(meta);

  if (ex.topics_other && ex.topics_other.length && !$("onlySelected").checked) {
    const extra = document.createElement("p");
    extra.className = "muted";
    extra.textContent = `Autres thèmes : ${ex.topics_other.join(", ")}`;
    el.appendChild(extra);
  }


  const raw = document.createElement("p");
  raw.textContent = ex.raw || "";
  el.appendChild(raw);

  const actions = document.createElement("div");
  actions.className = "actions";

  const b1 = document.createElement("button");
  b1.className = "btn";
  b1.textContent = "Sujet (PDF)";
  b1.onclick = () => openLocalThenFallback(ex.local_subject_file, ex.pdf_subject_url);
  actions.appendChild(b1);

  const corr = (ex.corriges || []).filter(c => c.url);
  if (corr.length > 0) {
    const sel = document.createElement("select");
    sel.className = "select";
    sel.innerHTML = `<option value="">Corrigé…</option>` + corr.map((c, i) =>
      `<option value="${i}">${c.label || ("Corrigé " + (i+1))}</option>`
    ).join("");

    const b2 = document.createElement("button");
    b2.className = "btn";
    b2.textContent = "Ouvrir";
    b2.onclick = () => {
      if (sel.value === "") return;
      const i = Number(sel.value);
      openLocalThenFallback(corr[i].local_file, corr[i].url);
    };

    actions.appendChild(sel);
    actions.appendChild(b2);
  }

  el.appendChild(actions);
  return el;
}

async function generate() {

  const body = {
    tags: [...selected],
    k: Number($("k").value),
    avoid_same_subject: $("avoidSame").checked,
    only_selected_topics: $("onlySelected").checked
  };


  const res = await fetch("/api/generate", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });

  const data = await res.json();
  if (!res.ok) {
    $("coverage").textContent = data.error || "Erreur génération";
    $("combo").innerHTML = "";
    return;
  }

  $("coverage").textContent =
    `Couverts: ${data.covered_tags.length}/${data.requested_tags.length}` +
    (data.missing_tags.length ? ` · Manquants: ${data.missing_tags.join(", ")}` : "");

  const wrap = $("combo");
  wrap.innerHTML = "";
  data.exercises.forEach(ex => wrap.appendChild(card(ex)));
}

async function init() {
  const r = await fetch("/data/exercises.json");
  EXS = await r.json();
  ALL_TAGS = computeTags(EXS);

  $("selCount").textContent = `${selected.size} tag(s) sélectionné(s)`;
  $("tagSearch").addEventListener("input", renderTags);
  $("generate").onclick = generate;
  $("clear").onclick = () => {
    selected.clear();
    $("selCount").textContent = `0 tag(s) sélectionné(s)`;
    renderTags();
    $("coverage").textContent = "—";
    $("combo").innerHTML = "";
  };

  renderTags();
}
init();
