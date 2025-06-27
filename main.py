from flask import Flask, request
import requests
import os
import base64
import json
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

memory = {}
sender_ids = set()  # Track users to send scheduled messages

# Gemini request with retry logic and logging
def get_gemini_answer(prompt, retries=2):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()

            if "candidates" in result and result["candidates"]:
                return result["candidates"][0]["content"]["parts"][0].get("text", "🤖 Gemini gave no text.")
            elif "error" in result:
                print(f"[Gemini Error]: {result['error']}")
                return f"🤖 Gemini error: {result['error'].get('message', 'Unknown error')}"
            else:
                print(f"[Gemini Unexpected]: {json.dumps(result)}")
                return "🤖 No response from Gemini."
        except Exception as e:
            print(f"[Gemini Exception]: Attempt {attempt + 1} failed with error: {e}")
            time.sleep(1)

    return "🤖 Gemini failed to respond after retries."

# Reachability check
def check_model_reach():
    reply = get_gemini_answer("Hello")
    return reply if reply.startswith("🤖") else "✅ Gemini AI model is reachable and responding!"

# Scheduled reminder task
def scheduled_reminder():
    try:
        res = requests.get("https://worldclockapi.com/api/json/utc/now")
        data = res.json()
        current_time = data["currentDateTime"]
        dt = datetime.fromisoformat(current_time.replace("Z", ""))
        day_of_week = dt.weekday()
        time_str = dt.strftime("%H:%M")

        if day_of_week == 0 and time_str == "07:30":  # Monday 07:30 AM
            for sid in sender_ids:
                send_text_reply(sid, "🚜 Reminder: You're on classroom cleaning duty today! Don't forget to check your task list with .list show")
    except Exception as e:
        print(f"[Scheduler Error]: {e}")

# .list, .chores, .help command handler
def handle_list_command(text):
    global memory
    parts = text.strip().split()
    cmd = parts[0].lower()

    if cmd in [".list", ".chores"]:
        is_chores = cmd == ".chores"

        if len(parts) >= 2:
            sub_cmd = parts[1].lower()

            if sub_cmd == "show":
                if len(parts) == 3 and parts[2] == "id":
                    try:
                        encoded = base64.b64encode(json.dumps(memory).encode()).decode()
                        return f"📜 Your encoded task list:\n\n{encoded}"
                    except Exception as e:
                        return f"⚠️ Failed to encode memory: {e}"

                if not memory:
                    return "There is no current required tasks."
                result = ["Heres all the required tasks:"]
                for subj, tasks in memory.items():
                    result.append(f"{subj.upper()}:")
                    for t in tasks:
                        result.append(f"- {t}")
                return "\n".join(result)

            elif sub_cmd == "import" and len(parts) >= 3:
                try:
                    b64_data = parts[2]
                    decoded = json.loads(base64.b64decode(b64_data.encode()).decode())
                    for k, v in decoded.items():
                        memory[k] = v
                    return "✅ Imported tasks into memory!"
                except Exception as e:
                    return f"❌ Failed to import: {e}"

            elif sub_cmd == "clear" and len(parts) == 3:
                subject = parts[2].capitalize()
                if subject in memory:
                    del memory[subject]
                    return f"List cleared for {subject}!"
                return f"Nothing to clear for {subject}."

            elif sub_cmd == "clear" and parts[2].lower() == "all":
                memory.clear()
                return "✅ All subjects cleared from memory."

            elif is_chores and len(parts) >= 2:
                task_content = " ".join(parts[1:])
                if "Chores" not in memory:
                    memory["Chores"] = []
                memory["Chores"].append(task_content)
                return "✅ Chore added!"

            elif len(parts) >= 4:
                subject = parts[1].capitalize()
                task_type = parts[2].upper()
                task_content = " ".join(parts[3:])
                if subject not in memory:
                    memory[subject] = []
                memory[subject].append(f"[{task_type}] {task_content}")
                return "✅ Successfully listed input!"

    elif cmd == ".help":
        return (
            "📘 Messenger-GPT Help Menu:\n"
            "Commands you can use:\n\n"
            ".list [Subject] [PT/ASS/WW/BRING/REM] Task\n"
            "  → Adds a task to a subject\n"
            "  Example: .list sci pt Finish the presentation\n\n"
            ".list show\n"
            "  → Displays all tasks you’ve listed\n\n"
            ".list show id\n"
            "  → Export your task list as a base64 code (backup)\n\n"
            ".list import [base64]\n"
            "  → Import a previously saved task list\n\n"
            ".list clear [Subject]\n"
            "  → Clears all tasks under a subject\n\n"
            ".list clear all\n"
            "  → Clears all subjects\n\n"
            ".reach\n"
            "  → Checks if Gemini AI is online\n\n"
            ".time\n"
            "  → Checks current time in Manila\n\n"
            ".schedule [day] [message]\n"
            "  → Schedule a message for a weekday (Monday to Friday)"
        )

    elif cmd == ".time":
        try:
            res = requests.get("https://worldclockapi.com/api/json/utc/now", timeout=5)
            data = res.json()
            dt = datetime.fromisoformat(data["currentDateTime"].replace("Z", ""))
            return dt.strftime("🗕️ %A, %Y-%m-%d | ⏰ %H:%M:%S")
        except Exception as e:
            print(f"[Time Command Error]: {e}")
            return "⚠️ Unable to fetch time."

    elif cmd == ".schedule" and len(parts) >= 3:
        weekday = parts[1].capitalize()
        message_text = " ".join(parts[2:])
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        if weekday not in weekdays:
            return "❌ Invalid weekday. Use: Monday to Friday."

        def scheduled_message():
            for sid in sender_ids:
                send_text_reply(sid, f"🗓️ Scheduled ({weekday}): {message_text}")

        scheduler.add_job(scheduled_message, 'cron', day_of_week=weekdays.index(weekday), hour=7, minute=30)
        return f"✅ Message scheduled for every {weekday} at 07:30."

    return None

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is online!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        return (challenge, 200) if mode == "subscribe" and token == VERIFY_TOKEN else ("Verification failed", 403)

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

                if message_lower in ["hello", "yo", "oy", "hoy", "what up", "hi"]:
                    reply = (
                        "Hi, I am Messenger-GPT fully owned by DrunksDan. My purpose is to answer your questions, "
                        "I will gladly like to help you with that.\n"
                        "I am STILL in beta version. (Version: beta v.1.2 using Gemini)"
                    )

                elif message_lower in ["are you online?", "online", "are you on", "online ka ba"]:
                    reply = "YES! Fully up and responding here to fulfill your request and answers!."

                elif message_lower == ".reach":
                    reply = check_model_reach()

                else:
                    reply = handle_list_command(message)

                    if not reply:
                        send_typing_reply(sender_id, "⌛ Processing your request, please wait...")
                        try:
                            reply = get_gemini_answer(message)
                        except Exception as e:
                            reply = f"🤖 Error: {e}"

                send_text_reply(sender_id, reply)

        return "✅ Message received", 200

# Send temporary "thinking..." reply
def send_typing_reply(sender_id, message):
    send_url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }
    requests.post(send_url, params=params, headers=headers, json=payload)

# Send final reply
def send_text_reply(sender_id, message):
    send_url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }
    requests.post(send_url, params=params, headers=headers, json=payload)

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_reminder, 'interval', minutes=1)
    scheduler.start()
    app.run(host="0.0.0.0", port=5000, debug=True)
