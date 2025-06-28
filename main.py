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
sender_ids = set()

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

def check_model_reach():
    reply = get_gemini_answer("Hello")
    return reply if reply.startswith("🤖") else "✅ Gemini AI model is reachable and responding!"

def scheduled_reminder():
    try:
        res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Singapore", timeout=5)
        data = res.json()
        dt = datetime.fromisoformat(data["datetime"])
        day_of_week = dt.weekday()
        time_str = dt.strftime("%H:%M")

        if day_of_week == 0 and time_str == "07:30":
            for sid in sender_ids:
                send_text_reply(sid, "🚜 Reminder: You're on classroom cleaning duty today! Don't forget to check your task list with .list show")
    except Exception as e:
        print(f"[Scheduler Error]: {e}")

def handle_list_command(text):
    global memory
    parts = text.strip().split()
    cmd = parts[0].lower()

    if cmd == ".time":
        try:
            try:
                res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Kuala_Lumpur", timeout=5)
                data = res.json()
            except Exception as e:
                print(f"[Time API Fallback]: KL failed with {e}, trying Singapore...")
                res = requests.get("https://worldtimeapi.org/api/timezone/Asia/Singapore", timeout=5)
                data = res.json()

            dt = datetime.fromisoformat(data["datetime"])
            return dt.strftime("📆 %A, %B %d, %Y | 🕒 %I:%M:%S %p (UTC+8)")
        except Exception as e:
            print(f"[Time Command Error]: {e}")
            return "⚠️ Unable to fetch time from both KL and SG."

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

    elif cmd == ".help":
        return (
            "📘 **Messenger-GPT Help Menu**\n\n"
            "**Commands you can use:**\n\n"
            "🔹 `.list add [subject] [task]`\n"
            "→ Adds a task to a subject\n"
            " e.g., `.list add sci Finish the presentation`\n\n"
            "🔹 `.list show`\n"
            "→ Displays all tasks you’ve listed\n\n"
            "🔹 `.list clear`\n"
            "→ Clears all tasks\n\n"
            "🔹 `.list import [base64]`\n"
            "→ Import tasks using a base64 string\n\n"
            "🔹 `.list export`\n"
            "→ Export current tasks as a base64 string\n\n"
            "🔹 `.schedule [Monday-Friday] [message]`\n"
            "→ Schedule weekly reminders (sent at 07:30)\n\n"
            "🔹 `.reach`\n"
            "→ Checks if the AI model is online and responding\n\n"
            "🔹 `.write [subject] [category] [topic]`\n"
            "→ Generates a paragraph/speech/summary based on input\n"
            " e.g., `.write fil paragraph buod ng ibong adarna`\n\n"
            "🔹 `.rewrite [your text]`\n"
            "→ Requests a rewritten version of your input text\n\n"
            "**💡 Tips:**\n"
            "• You can just ask questions directly (starting with **who, what, when, where, why, how, if**, etc.) and the bot will auto-reply.\n\n"
            "📚 **Subjects Supported:**\nFil, Sci, Ap, TLE, Math, Mapeh, Eng, Esp"
        )

    elif cmd == ".list":
        if len(parts) >= 2 and parts[1].lower() == "show":
            if not memory:
                return "📝 Your task list is empty."
            response = "📝 Task List:\n"
            for subject, tasks in memory.items():
                response += f"\n📚 {subject}:\n"
                for task in tasks:
                    response += f"  - {task}\n"
            return response

        elif len(parts) >= 3 and parts[1].lower() == "import":
            try:
                b64_data = " ".join(parts[2:])
                decoded = base64.b64decode(b64_data).decode("utf-8")
                task_data = json.loads(decoded)
                memory.update(task_data)
                return "✅ Task list imported successfully!"
            except Exception as e:
                return f"⚠️ Failed to import task list: {e}"

        elif len(parts) >= 4 and parts[1].lower() == "add":
            subject = parts[2].capitalize()
            task = " ".join(parts[3:])
            if subject not in memory:
                memory[subject] = []
            memory[subject].append(task)
            return f"✅ Added task under {subject}."

        elif len(parts) == 2 and parts[1].lower() == "clear":
            memory.clear()
            return "🗑️ Task list cleared."

        elif len(parts) == 2 and parts[1].lower() == "export":
            try:
                encoded = base64.b64encode(json.dumps(memory).encode("utf-8")).decode("utf-8")
                return f"📄 Exported Task List (base64):\n{encoded}"
            except Exception as e:
                return f"⚠️ Export failed: {e}"

    elif cmd == ".reach":
        return check_model_reach()

    elif cmd == ".write" and len(parts) >= 4:
        subject = parts[1].capitalize()
        category = parts[2].lower()
        topic = " ".join(parts[3:])
        prompt = (
            f"Write a {category} for the subject {subject}.\n\n"
            f"Topic: {topic}\n\n"
            f"Make sure it's clear, relevant, and appropriate for a school assignment."
        )
        return get_gemini_answer(prompt)

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

def send_typing_reply(sender_id, message):
    send_url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }
    requests.post(send_url, params=params, headers=headers, json=payload)

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
