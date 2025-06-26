from flask import Flask, request
import requests
import os
import re

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

memory = {}
answers = {}
answer_counter = 1

# Google Gemini call
def get_gemini_answer(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        r = requests.post(url, headers=headers, params=params, json=payload)
        r.raise_for_status()
        data = r.json()
        return data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"🤖 Gemini error: {e}"

# Reach check
def check_model_reach():
    test_prompt = "Hello"
    try:
        reply = get_gemini_answer(test_prompt)
        if reply and isinstance(reply, str):
            return "✅ Gemini API is reachable and responding!"
        else:
            return "⚠️ Gemini API didn't return a valid response."
    except Exception as e:
        return f"❌ Error reaching Gemini: {e}"

# Handle .list and .help

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
            "📘 Messenger-GPT Help Menu:\n"
            "Commands you can use:\n\n"
            ".list \"Subject\" \"PT/ASS/WW/BRING/REM\" Task\n"
            "  → Adds a task to a subject\n"
            "  Example: .list sci pt Finish the presentation\n\n"
            ".list show\n"
            "  → Displays all tasks you’ve listed\n\n"
            ".list clear \"Subject\"\n"
            "  → Clears all tasks under a subject\n\n"
            ".reach\n"
            "  → Checks if Gemini model is online and responding\n\n"
            ".explain [number]/all\n"
            "  → Explains answer(s) based on the tracked questions\n\n"
            ".write [subject] [category] [topic]\n"
            "  → Generate paragraphs/speech for school work\n\n"
            ".rewrite [text]\n"
            "  → Rewrite the provided sentence\n\n"
            "Subjects: Fil, Sci, Ap, TLE, Math, Mapeh, Eng, Esp"
        )

    return None

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is online!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    global answer_counter

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
                message = messaging_event.get("message", {}).get("text")

                if not message:
                    continue

                message_lower = message.lower().strip()

                if message_lower in ["hello", "yo", "oy", "hoy", "what up", "hi"]:
                    reply = (
                        "Hi, I am Messenger-GPT fully owned by DrunksDan. My purpose is to answer your questions, "
                        "try and scan your image, and if the image contains a question I will gladly like to help you with that.\n"
                        "I am STILL in beta version. (Version: beta v.0.7)"
                    )

                elif message_lower in ["are you online?", "online", "are you on", "online ka ba"]:
                    reply = "YES! Fully up and responding here to fulfill your request and answers!."

                elif message_lower == ".reach":
                    reply = check_model_reach()

                elif message_lower.startswith(".explain"):
                    parts = message_lower.split()
                    if len(parts) == 2 and parts[1] == "all":
                        all_expl = [f"{i}. {a}" for i, a in answers.items()]
                        reply = "\n".join(all_expl) if all_expl else "No explanations stored."
                    elif len(parts) == 2 and parts[1].isdigit():
                        key = int(parts[1])
                        reply = answers.get(key, f"No explanation for #{key}.")
                    else:
                        reply = "Usage: .explain [number] or .explain all"

                elif message_lower.startswith(".write"):
                    try:
                        parts = message.split(" ", 3)
                        subject = parts[1]
                        category = parts[2]
                        topic = parts[3]
                        prompt = f"Write a {category} in {subject} about: {topic}"
                        reply = get_gemini_answer(prompt)
                    except:
                        reply = "Usage: .write [subject] [category] [topic]"

                elif message_lower.startswith(".rewrite"):
                    text_to_rewrite = message[len(".rewrite"):].strip()
                    if text_to_rewrite:
                        prompt = f"Rewrite this clearly and professionally: {text_to_rewrite}"
                        reply = get_gemini_answer(prompt)
                    else:
                        reply = "Usage: .rewrite [text]"

                else:
                    reply = handle_list_command(message)

                    if not reply:
                        if re.match(r"^(who|what|when|where|why|how|if)[\s\S]*", message_lower):
                            answer = get_gemini_answer(message)
                            answers[answer_counter] = f"Q: {message}\nA: {answer}"
                            reply = f"{answer_counter}. {answer.splitlines()[0]}"
                            answer_counter += 1
                        else:
                            reply = get_gemini_answer(message)

                send_url = "https://graph.facebook.com/v18.0/me/messages"
                params = {"access_token": PAGE_ACCESS_TOKEN}
                headers = {"Content-Type": "application/json"}
                payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": reply}
                }
                requests.post(send_url, params=params, headers=headers, json=payload)

        return "✅ Message received", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
