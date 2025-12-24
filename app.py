from flask import Flask, render_template, send_from_directory, abort, request, jsonify
import os, json, random

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")

EXERCISES_CACHE = None

def load_exercises():
    global EXERCISES_CACHE
    if EXERCISES_CACHE is None:
        path = os.path.join(DOWNLOADS_DIR, "exercises_standardises.json")
        with open(path, "r", encoding="utf-8") as f:
            EXERCISES_CACHE = json.load(f)
    print(EXERCISES_CACHE)
    return EXERCISES_CACHE

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/generator")
def generator_page():
    return render_template("generator.html")

@app.get("/data/<path:filename>")
def data_files(filename):
    full = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.isfile(full):
        abort(404)
    return send_from_directory(DOWNLOADS_DIR, filename)

@app.get("/pdf/<path:filepath>")
def pdf_files(filepath):
    full = os.path.join(DOWNLOADS_DIR, filepath)
    if not os.path.isfile(full):
        abort(404)
    directory = os.path.dirname(full)
    name = os.path.basename(full)
    return send_from_directory(directory, name)

def exercise_score(ex, remaining_tags, allowed_tags=None):
    ex_tags = set(ex.get("topics") or [])
    if allowed_tags is not None:
        ex_tags = ex_tags & allowed_tags  # on ne “compte” que les thèmes sélectionnés
    new_cov = len(ex_tags & remaining_tags)

    pts = ex.get("points") or 0
    pts_bonus = 0.05 if pts >= 8 else 0.0
    return new_cov + pts_bonus

def generate_combo(exercises, wanted_tags, k=3, avoid_same_subject=True, only_selected=False, seed=None):
    if seed is not None:
        random.seed(seed)

    wanted_tags = set(wanted_tags)
    remaining = set(wanted_tags)

    chosen = []
    used_subjects = set()

    pool = exercises[:]
    random.shuffle(pool)

    # Filtrage strict: topics(ex) ⊆ wanted_tags
    if only_selected and wanted_tags:
        pool = [ex for ex in pool if set(ex.get("topics") or []).issubset(wanted_tags)]

    for _ in range(k):
        best = None
        best_score = -1

        for ex in pool:
            if avoid_same_subject and ex.get("subject_id") in used_subjects:
                continue
            sc = exercise_score(ex, remaining, allowed_tags=wanted_tags if wanted_tags else None)
            if sc > best_score:
                best = ex
                best_score = sc

        if best is None:
            break

        chosen.append(best)
        used_subjects.add(best.get("subject_id"))
        remaining -= (set(best.get("topics") or []) & wanted_tags)

        pool = [e for e in pool if e.get("id") != best.get("id")]

    # Complétion: seulement si on n'est PAS en mode strict
    while len(chosen) < k and pool and not only_selected:
        ex = pool.pop()
        if avoid_same_subject and ex.get("subject_id") in used_subjects:
            continue
        chosen.append(ex)
        used_subjects.add(ex.get("subject_id"))

    covered = wanted_tags - remaining

    # Ajout de champs d’affichage: topics_used/topics_other
    out_ex = []
    for ex in chosen:
        ex_tags = set(ex.get("topics") or [])
        used = sorted(ex_tags & wanted_tags)
        other = sorted(ex_tags - wanted_tags) if wanted_tags else []
        ex2 = dict(ex)
        ex2["topics_used"] = used
        ex2["topics_other"] = other
        out_ex.append(ex2)

    return {
        "requested_tags": sorted(wanted_tags),
        "covered_tags": sorted(covered),
        "missing_tags": sorted(remaining),
        "count": len(out_ex),
        "exercises": out_ex
    }

@app.post("/api/generate")
def api_generate():
    data = request.get_json(force=True) or {}
    tags = data.get("tags") or []
    k = int(data.get("k") or 3)
    k = max(3, min(5, k))

    avoid_same_subject = bool(data.get("avoid_same_subject", True))
    year_min = data.get("year_min")
    year_max = data.get("year_max")
    sessions = data.get("sessions")  # liste optionnelle
    only_selected = bool(data.get("only_selected_topics", False))

    exercises = load_exercises()

    # filtres optionnels
    def ok(ex):
        y = ex.get("year")
        if year_min is not None and y is not None and int(y) < int(year_min):
            return False
        if year_max is not None and y is not None and int(y) > int(year_max):
            return False
        if sessions and ex.get("session") not in sessions:
            return False
        return True

    pool = [ex for ex in exercises if ok(ex)]
    if not pool:
        return jsonify({"error": "Aucun exercice après filtres."}), 400

    result = generate_combo(pool, tags, k=k, avoid_same_subject=avoid_same_subject, only_selected=only_selected, seed=data.get("seed"))

    return jsonify(result)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
