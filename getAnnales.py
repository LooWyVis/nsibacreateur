import os, re, json, time
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date

BASE = "https://www.math93.com"
PAGES = [
    f"{BASE}/annales-du-bac/bac-specialite-nsi/annales-nsi-2025/nsi-ecrit-2025.html",
    f"{BASE}/annales-du-bac/bac-specialite-nsi/annales-nsi-2024/nsi-ecrit-2024.html",
    f"{BASE}/annales-du-bac/bac-specialite-nsi/annales-nsi-2023/nsi-ecrit-2023.html",
    f"{BASE}/annales-du-bac/bac-specialite-nsi/annales-nsi-2022/nsi-ecrit-2022.html",
    f"{BASE}/annales-du-bac/bac-specialite-nsi/annales-nsi-2021/1113-annales-du-bac-nsi-epreuve-ecrite-2021.html",
]
UA = {"User-Agent": "Mozilla/5.0 (compatible; annales-indexer/1.0)"}
OUT_DIR = "downloads"

TOPIC_ALIASES = {
    "poo": "programmation orientée objet",
    "bdd": "bases de données",
    "bases de données relationnelles": "bases de données",
    "sql": "sql",
    "arbres binaires": "arbres binaires",
    "graphes": "graphes",
    "récursivité": "récursivité",
    "réseaux": "réseaux",
    "processus": "processus",
    "piles": "piles",
    "files": "files",
    "dictionnaires": "dictionnaires",
    "tableaux": "tableaux",
    "tris": "tris",
    "gloutons": "algorithmes gloutons",
    "programmation dynamique": "programmation dynamique",
    "huffman": "huffman",
    "compression": "compression",
    "décidabilité": "décidabilité",
    "sécurisation des communications": "sécurité / crypto",
    "cryptographie": "sécurité / crypto",
}

# Liste de thèmes "canon" + motifs de détection (tu peux enrichir)
TOPIC_PATTERNS = [
    ("sql", r"\bsql\b|requêtes?\s+sql|langage\s+sql"),
    ("bases de données", r"bases?\s+de\s+donn(e|é)es?|mod[eè]le\s+relationnel"),
    ("graphes", r"\bgraphes?\b|parcours\s+de\s+graphes?|chemins?\s+dans\s+un\s+graphe"),
    ("arbres binaires", r"arbres?\s+binaires?"),
    ("arbres binaires de recherche", r"arbres?\s+binaires?\s+de\s+recherche"),
    ("récursivité", r"r[eé]cursivit[eé]|r[eé]cursif"),
    ("programmation orientée objet", r"\bpoo\b|programmation\s+orient[eé]e\s+objet|programmation\s+objet"),
    ("programmation python", r"\bpython\b|programmation\s+en\s+python"),
    ("tableaux", r"\btableaux?\b"),
    ("dictionnaires", r"\bdictionnaires?\b"),
    ("listes", r"\blistes?\b"),
    ("piles", r"\bpiles?\b|lifo"),
    ("files", r"\bfiles?\b|fifo"),
    ("tris", r"\btris?\b|tri\s+fusion|tri\s+rapide|algorithmes?\s+de\s+tri"),
    ("algorithmes gloutons", r"\bglouton(s)?\b"),
    ("programmation dynamique", r"\bprogrammation\s+dynamique\b"),
    ("réseaux", r"r[eé]seaux?|adressage\s+ip|cidr|routeurs?|routage|ospf|rip|protocoles?\s+r[eé]seau"),
    ("processus", r"\bprocessus\b|ordonnancement|interblocage"),
    ("systèmes d’exploitation", r"syst[eè]mes?\s+d['’]exploitation|linux|unix|ligne\s+de\s+commande"),
    ("sécurité / crypto", r"cryptographie|s[eé]curisation|s[eé]curit[eé]\s+des\s+communications"),
    ("huffman", r"\bhuffman\b|compression"),
    ("décidabilité", r"d[eé]cidabilit[eé]"),
]

SESSION_KEYWORDS = [
    "Métropole", "Asie", "Amérique Nord", "Amérique Sud",
    "Polynésie", "Centre Etrangers", "Asie Pacifique"
]

def safe_name(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[^\w\-.() ]+", "_", s)
    return s[:180]

def rel_from_downloads(abs_path: str) -> str:
    """
    Chemin relatif depuis OUT_DIR (ex: downloads/NSI/... -> NSI/...)
    """
    abs_out = os.path.abspath(OUT_DIR)
    abs_p = os.path.abspath(abs_path)
    rel = os.path.relpath(abs_p, abs_out)
    return rel.replace("\\", "/")

def download(url: str, dest_path: str):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return
    with requests.get(url, headers=UA, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)

def norm_topic(t: str) -> str:
    t0 = t.strip().lower()
    t0 = t0.replace("é","e").replace("è","e").replace("ê","e").replace("à","a").replace("ï","i").replace("î","i").replace("ô","o").replace("ù","u").replace("ç","c")
    t0 = re.sub(r"[()]", "", t0)
    t0 = re.sub(r"\s+", " ", t0).strip()
    return TOPIC_ALIASES.get(t0, t.strip().lower())


def clean_theme_text(s: str) -> str:
    s = (s or "").strip()

    # Enlever parenthèses d'annotations (1re), (Tle), etc.
    s = re.sub(r"\([^)]*\)", " ", s)

    # Enlever les tournures "Cet exercice porte sur ..."
    s = re.sub(r"^cet exercice (porte sur|traite de|concerne)\s+", "", s, flags=re.I)

    # Nettoyage ponctuation/espaces
    s = s.replace("POO", "programmation orientée objet")
    s = s.replace("BDD", "bases de données")
    s = re.sub(r"\s+", " ", s).strip(" .:-\n\t")
    return s


def split_topics(raw: str):
    s = clean_theme_text(raw).lower()

    found = []
    for canon, pat in TOPIC_PATTERNS:
        if re.search(pat, s, flags=re.I):
            found.append(canon)

    # fallback si rien trouvé : découpage soft (mais propre)
    if not found:
        parts = re.split(r",|;|/|\bet\b", clean_theme_text(raw), flags=re.I)
        for p in parts:
            p = p.strip(" .:-\n\t")
            if len(p) >= 3:
                found.append(norm_topic(p))

    # dédoublonnage en gardant l’ordre
    seen = set()
    out = []
    for t in found:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out

def extract_year_from_page(url: str, soup: BeautifulSoup):
    m = re.search(r"annales-nsi-(20\d{2})", url)
    if m:
        return int(m.group(1))
    h = soup.find(["h1","h2"])
    if h:
        m2 = re.search(r"(20\d{2})", h.get_text(" ", strip=True))
        if m2:
            return int(m2.group(1))
    return None

def detect_session(text: str):
    for k in SESSION_KEYWORDS:
        if k.lower() in text.lower():
            return k
    return None

def detect_subject_label(text: str):
    m = re.search(r"Sujet\s*([0-9]+[A-Z]?)", text, flags=re.I)
    return f"Sujet {m.group(1)}" if m else None

def detect_code(text: str):
    m = re.search(r"\b\d{2}-NSI[A-Z0-9]+\b", text)
    return m.group(0) if m else None

def detect_date(text: str, year: int):
    try:
        dt = parse_date(text, dayfirst=True, fuzzy=True, default=parse_date(f"01/01/{year}", dayfirst=True))
        if re.search(r"\b\d{1,2}\b", text):
            return dt.date().isoformat()
    except Exception:
        pass
    return None

def find_main_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        cap = table.find("caption")
        if cap and "epreuves ecrites" in cap.get_text(" ", strip=True).lower():
            return table
    for table in soup.find_all("table"):
        ths = [x.get_text(" ", strip=True).lower() for x in table.find_all(["th","td"], limit=10)]
        if any("sujet" in t for t in ths) and any("corrig" in t for t in ths):
            return table
    return None

subjects = []
exercises = []
downloads = []

for page_url in PAGES:
    r = requests.get(page_url, headers=UA, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    year = extract_year_from_page(page_url, soup)
    table = find_main_table(soup)
    if not table:
        print(f"[WARN] Table non trouvée: {page_url}")
        continue

    rows = table.find("tbody").find_all("tr", recursive=False) if table.find("tbody") else table.find_all("tr", recursive=False)
    for tr in rows:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 2:
            continue

        sujet_td = tds[0]
        contenu_td = tds[1]
        corr_td = tds[2] if len(tds) >= 3 else None

        sujet_text = sujet_td.get_text(" ", strip=True)

        session = detect_session(sujet_text) or "Inconnu"
        subject_label = detect_subject_label(sujet_text) or "Sujet ?"
        code = detect_code(sujet_text) or safe_name(sujet_text)[:40]

        # lien PDF du sujet
        pdf_subject_url = None
        for a in sujet_td.find_all("a", href=True):
            href = urljoin(page_url, a["href"])
            if href.lower().endswith(".pdf"):
                pdf_subject_url = href
                break

        date_iso = detect_date(sujet_text, year) if year else None
        subject_id = f"{year}-{session.lower().replace(' ', '-')}-{code}"

        # === Chemins locaux (pré-calculés, pour écrire dans JSON) ===
        # dossier local standard
        subdir = os.path.join(OUT_DIR, "NSI", str(year), safe_name(session), safe_name(code))

        local_subject_abs = None
        local_subject_rel = None
        if year and pdf_subject_url:
            local_subject_abs = os.path.join(subdir, safe_name("SUJET.pdf"))
            local_subject_rel = rel_from_downloads(local_subject_abs)

        # corrigés (avec local_file si PDF)
        corriges = []
        if corr_td:
            for a in corr_td.find_all("a", href=True):
                url = urljoin(page_url, a["href"])
                label = a.get_text(" ", strip=True) or os.path.basename(urlparse(url).path)

                entry = {"label": label, "url": url}

                if url.lower().endswith(".pdf") and year:
                    local_corr_abs = os.path.join(subdir, safe_name(f"{label}.pdf"))
                    entry["local_file"] = rel_from_downloads(local_corr_abs)

                corriges.append(entry)

        subjects.append({
            "id": subject_id,
            "year": year,
            "session": session,
            "subject_label": subject_label,
            "code": code,
            "date": date_iso,
            "page": page_url,
            "pdf_subject_url": pdf_subject_url,
            "local_subject_file": local_subject_rel,   # <-- AJOUT
            "corriges": corriges
        })

        # exercices
        lis = contenu_td.find_all("li")
        for li in lis:
            txt = li.get_text(" ", strip=True)
            m = re.search(r"Exercice\s*(\d+)\s*\[(\d+)\s*points?\]\s*:\s*(.*)", txt, flags=re.I)
            if not m:
                continue
            ex_num = int(m.group(1))
            points = int(m.group(2))
            themes_raw = m.group(3).strip()
            topics = split_topics(themes_raw)

            exercises.append({
                "id": f"{subject_id}-ex{ex_num}",
                "subject_id": subject_id,
                "year": year,
                "session": session,
                "subject_label": subject_label,
                "code": code,
                "exercise": ex_num,
                "points": points,
                "topics": topics,
                "raw": themes_raw,
                "pdf_subject_url": pdf_subject_url,
                "local_subject_file": local_subject_rel,  # <-- AJOUT
                "corriges": corriges                      # contient local_file si PDF
            })

        # téléchargement (cohérent avec les chemins écrits)
        if year and pdf_subject_url and local_subject_abs:
            downloads.append((pdf_subject_url, local_subject_abs))
        for c in corriges:
            if c["url"].lower().endswith(".pdf") and "local_file" in c:
                # reconstruire chemin absolu depuis OUT_DIR + local_file
                downloads.append((c["url"], os.path.join(OUT_DIR, c["local_file"].replace("/", os.sep))))

# Écriture JSON
os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "subjects.json"), "w", encoding="utf-8") as f:
    json.dump(subjects, f, ensure_ascii=False, indent=2)

with open(os.path.join(OUT_DIR, "exercises.json"), "w", encoding="utf-8") as f:
    json.dump(exercises, f, ensure_ascii=False, indent=2)

# Download PDFs
for (url, dest) in downloads:
    try:
        download(url, dest)
        time.sleep(0.2)
    except Exception as e:
        print(f"[WARN] Download fail: {url} -> {e}")

print(f"OK: {len(subjects)} sujets, {len(exercises)} exercices.")
print(f"JSON: {OUT_DIR}/subjects.json et {OUT_DIR}/exercises.json")
