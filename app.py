import os
from collections import Counter
from datetime import datetime, timezone

import joblib
from flask import Flask, jsonify, redirect, render_template, request, url_for
from google.cloud import firestore

app = Flask(__name__)

# Підключення до хмарної БД Google Firestore
db = firestore.Client(database="default")
tasks = db.collection("tasks")

# Завантаження власної моделі ШІ, навченої в Google Colab
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model = joblib.load(os.path.join(BASE_DIR, "model.pkl"))


def classify(text):
    """Повертає категорію завдання та впевненість моделі у відсотках."""
    proba = model.predict_proba([text])[0]
    best = int(proba.argmax())
    return str(model.classes_[best]), round(float(proba[best]) * 100, 1)


@app.route("/")
def index():
    docs = tasks.order_by("created_at", direction=firestore.Query.DESCENDING).stream()
    all_tasks = []
    for d in docs:
        item = d.to_dict()
        item["_id"] = d.id
        all_tasks.append(item)
    return render_template("index.html", tasks=all_tasks)


@app.route("/add", methods=["POST"])
def add():
    user_name = request.form.get("user_name", "").strip()
    title = request.form.get("title", "").strip()
    if user_name and title:
        category, confidence = classify(title)
        tasks.add({
            "user_name": user_name,
            "title": title,
            "category": category,
            "confidence": confidence,
            "done": False,
            "created_at": datetime.now(timezone.utc),
        })
    return redirect(url_for("index"))


@app.route("/done/<task_id>", methods=["POST"])
def done(task_id):
    tasks.document(task_id).update({"done": True})
    return redirect(url_for("index"))


@app.route("/delete/<task_id>", methods=["POST"])
def delete(task_id):
    tasks.document(task_id).delete()
    return redirect(url_for("index"))


@app.route("/stats")
def stats():
    total = Counter()
    finished = Counter()
    for d in tasks.stream():
        item = d.to_dict()
        category = item.get("category") or classify(item.get("title", ""))[0]
        total[category] += 1
        if item.get("done"):
            finished[category] += 1
    rows = [
        {"category": c, "total": total[c], "done": finished[c],
         "percent": round(finished[c] / total[c] * 100) if total[c] else 0}
        for c in sorted(total)
    ]
    return render_template(
        "stats.html",
        rows=rows,
        labels=[r["category"] for r in rows],
        values=[r["total"] for r in rows],
        all_count=sum(total.values()),
    )


@app.route("/api/classify")
def api_classify():
    text = request.args.get("text", "").strip()
    if not text:
        return jsonify({"error": "Параметр text обов'язковий"}), 400
    category, confidence = classify(text)
    return jsonify({"text": text, "category": category, "confidence": confidence})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
