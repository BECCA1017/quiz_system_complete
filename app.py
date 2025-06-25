
from flask import Flask, render_template, request, redirect, session, send_file
import random, csv, os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import url_for

app = Flask(__name__)
app.secret_key = 'secret'

# 題庫載入
def load_questions():
    questions = []
    if os.path.exists("questions.csv"):
        with open("questions.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                questions.append(row)
    return questions

# 排行榜資料
LEADERBOARD_FILE = "leaderboard.csv"
def load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        return []
    with open(LEADERBOARD_FILE, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def save_leaderboard(data):
    with open(LEADERBOARD_FILE, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["nickname", "score", "time"])
        writer.writeheader()
        writer.writerows(data)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    nickname = request.form.get("nickname", "").strip()
    blocked = ["你娘","幹","媽的","靠北","賤","去你的","fuck","操"]
    if not nickname or any(bad in nickname for bad in blocked):
        return render_template("index.html", error="請輸入有效的暱稱")
    session["nickname"] = nickname
    questions = load_questions()
    if len(questions) < 40:
        return "題庫不足 40 題"
    session["quiz"] = random.sample(questions, 40)
    session["index"] = 0
    session["score"] = 100
    session["start_time"] = datetime.now().isoformat()
    return redirect("/question")

@app.route("/question", methods=["GET", "POST"])
def question():
    index = session.get("index", 0)
    quiz = session.get("quiz", [])
    if index >= len(quiz):
        return redirect("/result")
    question = quiz[index]
    return render_template("question.html", number=index+1, question=question, time_limit=30)

@app.route("/submit", methods=["POST"])
def submit():
    answer = request.form.get("answer")
    index = session["index"]
    quiz = session["quiz"]
    correct = quiz[index]["正確答案"]
    session["index"] += 1
    if answer != correct:
        session["score"] -= 2.5
        return render_template("feedback.html", result="錯誤", correct=correct)
    return render_template("feedback.html", result="正確", correct=correct)

@app.route("/result")
def result():
    nickname = session["nickname"]
    score = session["score"]
    start_time = datetime.fromisoformat(session["start_time"])
    used_time = (datetime.now() - start_time).seconds
    leaderboard = load_leaderboard()
    leaderboard.append({"nickname": nickname, "score": score, "time": used_time})
    leaderboard = sorted(leaderboard, key=lambda x: (-float(x["score"]), x["time"]))[:50]
    save_leaderboard(leaderboard)
    return render_template("result.html", nickname=nickname, score=score, time=used_time)

@app.route("/leaderboard")
def leaderboard():
    board = load_leaderboard()
    return render_template("leaderboard.html", leaderboard=board)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")
        if user == "nfabmroc" and pwd == "nfabmroc":
            session["admin"] = True
            return redirect("/admin/dashboard")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect("/admin/login")
    questions = load_questions()
    stats = {}
    for q in questions:
        qid = q.get("題號", "")
        stats[qid] = int(q.get("錯誤次數", 0))
    sorted_stats = sorted(stats.items(), key=lambda x: -x[1])
    return render_template("admin_dashboard.html", stats=sorted_stats)

@app.route("/admin/upload", methods=["POST"])
def admin_upload():
    if not session.get("admin"):
        return redirect("/admin/login")
    file = request.files["file"]
    filename = secure_filename(file.filename)
    file.save("questions.csv")
    return redirect("/admin/dashboard")

@app.route("/admin/export")
def admin_export():
    if not session.get("admin"):
        return redirect("/admin/login")
    return send_file(LEADERBOARD_FILE, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
