import os
from datetime import datetime, timezone

from flask import Flask, redirect, render_template, request, url_for
from google.cloud import firestore

app = Flask(__name__)

# Підключення до хмарної БД Google Firestore
db = firestore.Client(database="default")
tasks = db.collection("tasks")


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
        tasks.add({
            "user_name": user_name,
            "title": title,
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
