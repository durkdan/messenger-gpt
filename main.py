from flask import Flask, request
import requests
import json
import base64
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
sender_ids = set()
memory = {}
chores = []
scheduler = BackgroundScheduler()
scheduler.start()

def get_gemini_answer(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            gemini_data = response.json()
            return gemini_data['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ Gemini Error {response.status_code}: {response.text}"
    except requests.exceptions.RequestException:
        return "⏳ Waiting for Gemini response... (Request may have timed out)"

@app.route("/", methods=["POST"])
def webhook():
    global memory
    data = request.get_json()
    sender_id = data.get("sender_id")
    message = data.get("message", "").strip()

    if sender_id not in sender_ids:
        sender_ids.add(sender_id)

    if message.startswith(".help"):
        return json.dumps({"replies": [
            ".help - shows this help command",
            ".time - shows the current time (Asia/Singapore)",
            ".chores [task] - adds a chore",
            ".chores show - shows chores",
            ".chores clear [nums] - clears chores by number",
            ".list [subject] [task type] [task]",
            ".list show - show all lists",
            ".list clear [nums]",
            ".list base64 - convert your current list to base64",
            ".list import [base64] - import base64 list"
        ]})

    elif message.startswith(".time"):
        try:
            res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Singapore", timeout=5)
            dt = datetime.fromisoformat(res.json()["datetime"])
            return json.dumps({"replies": [f"🕒 Current time: {dt.strftime('%Y-%m-%d %H:%M:%S')}"]})
        except:
            return json.dumps({"replies": ["⚠️ Could not fetch the time."]})

    elif message.startswith(".chores show"):
        if chores:
            return json.dumps({"replies": ["🧹 Chores:\n" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(chores)])]})
        else:
            return json.dumps({"replies": ["🧹 No chores added."]})

    elif message.startswith(".chores clear"):
        nums = [int(n)-1 for n in message.split()[2].split(",") if n.isdigit()]
        for i in sorted(nums, reverse=True):
            if 0 <= i < len(chores):
                chores.pop(i)
        return json.dumps({"replies": ["✅ Cleared specified chores."]})

    elif message.startswith(".chores"):
        chores.append(message[7:].strip())
        return json.dumps({"replies": ["🧹 Chore added."]})

    elif message.startswith(".list base64"):
        encoded = base64.b64encode(json.dumps(memory).encode()).decode()
        return json.dumps({"replies": [f"🔐 Base64: {encoded}"]})

    elif message.startswith(".list import"):
        b64_data = message.split(" ", 2)[2]
        try:
            decoded = base64.b64decode(b64_data.encode()).decode()
            memory = json.loads(decoded)
            return json.dumps({"replies": ["✅ Imported list successfully."]})
        except:
            return json.dumps({"replies": ["⚠️ Failed to import base64."]})

    elif message.startswith(".list show"):
        replies = []
        for subject, tasks in memory.items():
            replies.append(f"📚 {subject}:")
            for i, item in enumerate(tasks):
                replies.append(f"  {i+1}. {item['type']} - {item['task']}")
        return json.dumps({"replies": replies or ["📚 No tasks added yet."]})

    elif message.startswith(".list clear"):
        parts = message.split()
        if len(parts) < 3:
            return json.dumps({"replies": ["⚠️ Invalid format."]})
        subject = parts[2]
        if subject in memory:
            memory[subject] = []
        return json.dumps({"replies": ["✅ Cleared tasks for subject."]})

    elif message.startswith(".list"):
        try:
            _, subject, task_type, task = message.split(" ", 3)
            if subject not in memory:
                memory[subject] = []
            memory[subject].append({"type": task_type, "task": task})
            return json.dumps({"replies": ["✅ Task added."]})
        except:
            return json.dumps({"replies": ["⚠️ Invalid list format."]})

    else:
        response = get_gemini_answer(message)
        return json.dumps({"replies": [response]})

def scheduled_reminder():
    try:
        res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Singapore", timeout=5)
        data = res.json()
        dt = datetime.fromisoformat(data["datetime"])
        if dt.weekday() == 0 and dt.strftime("%H:%M") == "07:30":
            for sid in sender_ids:
                send_text_reply(sid, "🚜 Reminder: You're on classroom cleaning duty today! Don't forget to check your task list with .list show")
    except Exception as e:
        print(f"[Scheduler Error]: {e}")

def send_text_reply(sender_id, text):
    print(f"Sending to {sender_id}: {text}")

scheduler.add_job(scheduled_reminder, 'interval', minutes=1)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
