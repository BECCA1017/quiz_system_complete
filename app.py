from flask import Flask, render_template, request, redirect, session, send_file
import pandas as pd
import random
import csv
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret"

QUESTION_FILE = "questions.csv"
LEADERBOARD_FILE = "leaderboard.csv"

def load_questions():
    df = pd.read_csv(QUESTION_FILE)
    return df.to_dict(orient="records")

def save_leaderboard(data):
    os.makedirs("data", exist_ok=True)
    with open("data/ranking.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["nickname", "score", "time"])
        writer.writeheader()
        writer.writerows(data)

def load_leaderboard():
    if not os.path.exists("data/ranking.csv"):
        return []
    with open("data/ranking.csv", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    nickname = request.form.get("nickname", "").strip()
    banned = ["你娘", "幹", "媽的", "靠北", "賤", "去你的", "fuck", "操"]
    if any(bad in nickname.lower() for bad in banned):
        return render_template("index.html", error="請輸入適當的暱稱")
    questions = load_questions()
    if len(questions) < 20:
        return "題庫不足 20 題"
    selected_ids = random.sample(range(len(questions)), 20)
    session["quiz_ids"] = selected_ids
    session["score"] = 100
    session["current"] = 0
    session["nickname"] = nickname
    session["start_time"] = datetime.now().isoformat()
    return redirect("/question")

@app.route("/question", methods=["GET"])
def question():
    questions = load_questions()
    quiz_ids = session.get("quiz_ids", [])
    current = session.get("current", 0)
    if current >= len(quiz_ids):
        return redirect("/result")
    qid = quiz_ids[current]
    question = questions[qid]
    return render_template("question.html", number=current+1, question=question, time_limit=30)

@app.route("/submit", methods=["POST"])
def submit():
    answer = request.form.get("answer")
    questions = load_questions()
    quiz_ids = session.get("quiz_ids", [])
    current = session.get("current", 0)
    qid = quiz_ids[current]
    correct = str(questions[qid]["answer"])
    is_correct = answer == correct
    if not is_correct:
        session["score"] -= 5

        # 紀錄錯題統計
        wrong_path = "data/wrong_stats.csv"
        if os.path.exists(wrong_path):
            wrong_df = pd.read_csv(wrong_path)
        else:
            wrong_df = pd.DataFrame(columns=["qid", "count"])

        if str(qid) in wrong_df["qid"].astype(str).values:
            wrong_df.loc[wrong_df["qid"].astype(str) == str(qid), "count"] += 1
        else:
            wrong_df = pd.concat([wrong_df, pd.DataFrame([{"qid": qid, "count": 1}])], ignore_index=True)
        wrong_df.to_csv(wrong_path, index=False)

    session["last_answer"] = answer
    session["last_correct"] = correct
    session["last_question"] = questions[qid]
    return redirect("/feedback")

@app.route("/feedback")
def feedback():
    return render_template("intermediate.html", question=session["last_question"],
                           selected=session["last_answer"],
                           correct=session["last_correct"],
                           number=session["current"]+1)

@app.route("/next")
def next_question():
    session["current"] += 1
    return redirect("/question")

@app.route("/result")
def result():
    if "score" not in session or "nickname" not in session or "start_time" not in session:
        return redirect("/")
    
    nickname = session["nickname"]
    score = session["score"]
    start_time = datetime.fromisoformat(session["start_time"])
    used_time = (datetime.now() - start_time).seconds

    leaderboard = load_leaderboard()
    leaderboard.append({
        "nickname": nickname,
        "score": score,
        "time": used_time
    })

    # 排序前先轉換型別，避免 int 和 str 混用出錯
    for item in leaderboard:
        item["score"] = float(item["score"])
        item["time"] = int(item["time"])

    leaderboard = sorted(leaderboard, key=lambda x: (-x["score"], x["time"]))[:50]
    save_leaderboard(leaderboard)

    # ✅ 這段記錄作答紀錄也要在函式裡面！
    usage_log_path = "data/usage_log.csv"
    log_entry = {
        "nickname": nickname,
        "score": score,
        "used_time": used_time,
        "timestamp": datetime.now().isoformat()
    }
    if os.path.exists(usage_log_path):
        usage_df = pd.read_csv(usage_log_path)
        usage_df = pd.concat([usage_df, pd.DataFrame([log_entry])], ignore_index=True)
    else:
        usage_df = pd.DataFrame([log_entry])
    usage_df.to_csv(usage_log_path, index=False)

    return render_template("result.html", nickname=nickname, score=score, time=used_time, leaderboard=leaderboard)

@app.route("/ranking")
def ranking():
    if os.path.exists("data/ranking.csv"):
        df = pd.read_csv("data/ranking.csv")
        df = df.sort_values(by=["score", "time"], ascending=[False, True]).head(50)
        data = df.to_dict(orient="records")
    else:
        data = []
    return render_template("ranking.html", ranking=data)

@app.route("/admin")
def admin():
    total_usage = 0
    wrong_stats = []
    try:
        # 計算使用次數
        if os.path.exists("data/usage_log.csv"):
            with open("data/usage_log.csv", newline="", encoding="utf-8") as f:
                total_usage = sum(1 for _ in f) - 1  # 扣掉標題列

        # 讀取錯題統計
        if os.path.exists("data/wrong_stats.csv"):
            df = pd.read_csv("data/wrong_stats.csv")
            df = df.sort_values(by="錯誤次數", ascending=False).head(10)
            wrong_stats = df.to_dict(orient="records")

    except Exception as e:
        print("後台資料載入失敗", e)

    return render_template("admin.html", total_usage=total_usage, wrong_stats=wrong_stats)


@app.route("/download/usage")
def download_usage():
    return send_file("data/usage_log.csv", as_attachment=True, download_name="使用紀錄.xlsx")


@app.route("/download/wrong")
def download_wrong():
    return send_file("data/wrong_stats.csv", as_attachment=True, download_name="錯題統計.xlsx")

@app.route("/favicon.ico")
def favicon():
    return send_file("static/favicon.ico")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
