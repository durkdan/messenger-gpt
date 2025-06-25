from flask import Flask, request
import requests
import os

app = Flask(__name__)

HUGGINGFACE_API_KEY = os.getenv("shh")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

memory = {}

# Zephyr-7B for Q&A (free and public)
def get_zephyr_answer(question):
    url = "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"inputs": question}
    response = requests.post(url, headers=headers, json=payload)
    try:
        return response.json()[0]['generated_text']
    except:
        return "🤖 I couldn't understand that."

# BART for summarizing search result text
def summarize_text(text):
    url = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"inputs": text}
    response = requests.post(url, headers=headers, json=payload)
    try:
        return response.json()[0]['summary_text']
    except:
        return "🤖 Summary unavailable."

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
            ".help\n"
            "  → Shows this help message\n\n"
            "Subjects: Fil, Sci, Ap, TLE, Math, Mapeh, Eng, Esp"
        )

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

                else:
                    reply = handle_list_command(message)

                    if not reply:
                        try:
                            reply = get_zephyr_answer(message)
                        except Exception as e:
                            reply = f"🤖 Error contacting AI: {e}"

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
