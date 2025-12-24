import json
import os
import re
import unicodedata
from typing import Any, Dict, List

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")

EXERCISES_CACHE = None

def load_exercises(path):
    global EXERCISES_CACHE
    if EXERCISES_CACHE is None:
        with open(path, "r", encoding="utf-8") as f:
            EXERCISES_CACHE = json.load(f)
    return EXERCISES_CACHE


def get_themes(exos):
    themes = []

    for exo in exos:
        for theme in exo["topics"]:
            if theme not in themes:
                themes.append(theme)
    
    return themes


def _strip_accents(s: str) -> str:
    # enlève les accents (Amérique -> Amerique)
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )


def _normalize_topic(topic: str) -> str:
    """
    Normalise un topic vers un format homogène.
    À adapter selon tes règles métier.
    """
    if not isinstance(topic, str):
        return ""

    t = topic.strip().lower()
    t = t.replace("’", "'")
    t = _strip_accents(t)

    # espaces propres
    t = re.sub(r"\s+", " ", t)

    contains_rules = [
        ("objet", "poo"),
        ("gloutons", "algorithmes gloutons"),
        ("arbres", "arbres"),
        ("arbre", "arbres"),
        ("algo", "programmation"),
        ("securite", "chiffrement"),
        ("sql", "bases de donnees"),
        ("programmation", "programmation"),
        ("graphe", "graphes"),
        ("liste", "listes"),
        ("tableau", "tableaux"),
        ("huffman", "divers"),
        ("goban", "divers"),
    ]

    # règles "contient → devient"
    for needle, replacement in contains_rules:
        if needle in t:
            return replacement

    # exemples de standardisation (tu peux enrichir)
    aliases = {
        "poo": "programmation orientee objet",
        "programmation orientee objet": "programmation orientee objet",
        "programmation orientee objet (poo)": "programmation orientee objet",
        "arbres binaires": "arbres binaires",
        "recursivite": "recursivite",
        "algorithmes": "algorithmes",
    }
    t = aliases.get(t, t)

    return t


def _standardize_topics(topics: Any) -> List[str]:
    """
    - garde seulement les strings
    - normalise
    - supprime les vides
    - supprime doublons en gardant l'ordre
    - tri optionnel (désactivé ici, on garde l'ordre d'apparition)
    """
    if not isinstance(topics, list):
        return []

    seen = set()
    out: List[str] = []
    for x in topics:
        if not isinstance(x, str):
            continue
        nx = _normalize_topic(x)
        if not nx:
            continue
        if nx in seen:
            continue
        seen.add(nx)
        out.append(nx)
    return out


def standardiser(DOWNLOADS_DIR: str) -> str:
    """
    Entree  : path = os.path.join(DOWNLOADS_DIR, "exercises.json")
    Sortie  : path = os.path.join(DOWNLOADS_DIR, "exercises_standardises.json")
    """
    in_path = os.path.join(DOWNLOADS_DIR, "exercises.json")
    out_path = os.path.join(DOWNLOADS_DIR, "exercises_standardises.json")

    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Le JSON attendu est une liste d'objets (array).")

    for obj in data:
        if isinstance(obj, dict) and "topics" in obj:
            obj["topics"] = _standardize_topics(obj["topics"])

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return out_path



src = path = os.path.join(DOWNLOADS_DIR, "exercises.json")
src_std = os.path.join(DOWNLOADS_DIR, "exercises_standardises.json")

out = standardiser(DOWNLOADS_DIR)

exos_std = load_exercises(src_std)

themes = get_themes(exos_std)

print(themes)
