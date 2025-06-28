from flask import Flask, request
import requests
import os
import base64
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

memory = {}
chores = []
sender_ids = set()

scheduler = BackgroundScheduler()

# Gemini 2.0 Flash Model
def get_gemini_answer(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"🤖 Gemini failed to respond: {e}"

# Check if Gemini model is online
def check_model_reach():
    return get_gemini_answer("Hello")

# Scheduled reminder
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

scheduler.add_job(scheduled_reminder, 'interval', minutes=1)
scheduler.start()

# Helper to send message

def send_text_reply(sid, msg):
    send_url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": sid},
        "message": {"text": msg}
    }
    requests.post(send_url, params=params, headers=headers, json=payload)

# Handle .list command
def handle_list_command(text):
    parts = text.strip().split()
    cmd = parts[0].lower()

    if cmd == ".list" and len(parts) >= 2:
        sub_cmd = parts[1].lower()

        if sub_cmd == "show":
            if not memory:
                return "There is no current required tasks."
            result = ["Heres all the required tasks:"]
            for subj, tasks in memory.items():
                result.append(f"{subj.upper()}:")
                for t in tasks:
                    result.append(f"- {t}")
            return "\n".join(result)

        elif sub_cmd == "clear" and len(parts) == 3:
            subject = parts[2].capitalize()
            if subject in memory:
                del memory[subject]
                return f"List cleared for {subject}!"
            else:
                return f"Nothing to clear for {subject}."

        elif sub_cmd == "base64":
            encoded = base64.b64encode(str(memory).encode()).decode()
            return f"📦 Base64 export: {encoded}"

        elif sub_cmd == "import" and len(parts) == 3:
            try:
                decoded = base64.b64decode(parts[2].encode()).decode()
                global memory
                memory = eval(decoded)
                return "✅ List successfully imported from base64."
            except:
                return "⚠️ Failed to import base64 string."

        elif len(parts) >= 4:
            subject = parts[1].capitalize()
            task_type = parts[2].upper()
            task_content = " ".join(parts[3:])
            if subject not in memory:
                memory[subject] = []
            memory[subject].append(f"[{task_type}] {task_content}")
            return "Successfully listed input!"

    elif cmd == ".help":
        return (
            "📘 Messenger-GPT Help Menu:\n\n"
            ".list \"Subject\" \"PT/ASS/WW/BRING/REM\" Task\n"
            "  → Adds a task to a subject\n"
            "  Example: .list sci pt Finish the presentation\n\n"
            ".list show\n"
            "  → Displays all tasks you’ve listed\n\n"
            ".list clear \"Subject\"\n"
            "  → Clears all tasks under a subject\n\n"
            ".list base64\n"
            "  → Export task list as base64\n\n"
            ".list import [base64]\n"
            "  → Import task list from base64\n\n"
            ".reach\n"
            "  → Checks if AI model is online and responding\n\n"
            ".write [subject] [category] [topic]\n"
            ".rewrite [your text]"
        )

    return None

# Chores command
def handle_chores_command(text):
    parts = text.strip().split()
    if text.startswith(".chores show"):
        if not chores:
            return "No chores added yet."
        return "\n".join([f"{i+1}. {c}" for i, c in enumerate(chores)])
    elif text.startswith(".chores clear"):
        try:
            indexes = [int(i)-1 for i in parts[2].split(",") if i.isdigit()]
            for idx in sorted(indexes, reverse=True):
                if 0 <= idx < len(chores):
                    chores.pop(idx)
            return "Selected chores cleared."
        except:
            return "Invalid clear command."
    else:
        chore = text[len(".chores "):].strip()
        chores.append(chore)
        return "🧹 Chore added!"

# Time checker
def get_current_time():
    try:
        res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Singapore", timeout=5)
        data = res.json()
        dt = datetime.fromisoformat(data["datetime"])
        return dt.strftime("%A, %d %B %Y - %H:%M:%S")
    except:
        return "Failed to retrieve time."

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is online!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Verification failed", 403

    elif request.method == "POST":
        data = request.get_json()

        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]
                sender_ids.add(sender_id)
                message = messaging_event.get("message", {}).get("text")

                if not message:
                    continue

                message_lower = message.lower().strip()

                if message_lower in ["hello", "yo", "hi", "oy"]:
                    reply = "Hi, I am Messenger-GPT fully owned by DrunksDan. I can help you with your tasks, reminders, and questions."

                elif message_lower == ".reach":
                    reply = check_model_reach()

                elif message_lower.startswith(".list") or message_lower.startswith(".help"):
                    reply = handle_list_command(message)

                elif message_lower.startswith(".chores"):
                    reply = handle_chores_command(message)

                elif message_lower == ".time":
                    reply = get_current_time()

                elif message_lower.startswith(".write"):
                    reply = get_gemini_answer(f"Write something for: {message[len('.write'):].strip()}")

                elif message_lower.startswith(".rewrite"):
                    reply = get_gemini_answer(f"Rewrite this: {message[len('.rewrite'):].strip()}")

                else:
                    reply = "⏳ Waiting for response..."
                    send_text_reply(sender_id, reply)
                    ai_reply = get_gemini_answer(message)
                    reply = ai_reply if ai_reply else "⚠️ Gemini didn’t respond."

                send_text_reply(sender_id, reply)

        return "✅ Message received", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
