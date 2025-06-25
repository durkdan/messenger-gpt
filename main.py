from flask import Flask, request
import requests
import os

app = Flask(__name__)

HUGGINGFACE_API_KEY = os.getenv("shh")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

# Memory for .list command
memory = {}

# -- HF MODELS --
MISTRAL_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
BART_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
HEADERS = {
    "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
    "Content-Type": "application/json"
}

def query_hf_model(model_url, input_text):
    payload = {"inputs": input_text}
    response = requests.post(model_url, headers=HEADERS, json=payload)
    if response.status_code == 200:
        try:
            output = response.json()
            if isinstance(output, list) and 'generated_text' in output[0]:
                return output[0]['generated_text']
            elif isinstance(output, dict) and 'summary_text' in output:
                return output['summary_text']
            elif isinstance(output, list) and 'summary_text' in output[0]:
                return output[0]['summary_text']
        except Exception as e:
            return "🤖 Model parsed incorrectly."
    return "🤖 Failed to get response from model."

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
        return "❌ Verification failed", 403

    data = request.get_json()
    for entry in data.get("entry", []):
        for messaging_event in entry.get("messaging", []):
            sender_id = messaging_event["sender"]["id"]
            message = messaging_event.get("message", {}).get("text", "")

            reply = handle_message(message.strip())

            send_url = "https://graph.facebook.com/v18.0/me/messages"
            params = {"access_token": PAGE_ACCESS_TOKEN}
            headers = {"Content-Type": "application/json"}
            payload = {
                "recipient": {"id": sender_id},
                "message": {"text": reply}
            }
            requests.post(send_url, params=params, headers=headers, json=payload)

    return "✅ Message received", 200

def handle_message(text):
    if text.lower() in ["hello", "hi", "yo", "oy", "hoy", "what up"]:
        return "Hi, I am Messenger-GPT fully owned by DrunksDan. I scan images, answer questions, and I'm in beta v0.7."

    if text.lower() in ["are you online?", "online", "are you on", "online ka ba"]:
        return "YES! fully up and responding here to fulfill your request and answers!."

    if text.lower().startswith(".list"):
        return process_list_command(text)

    # For general queries, default to Mistral
    return query_hf_model(MISTRAL_URL, text)

def process_list_command(text):
    parts = text.split(" ")
    if len(parts) < 2:
        return "⚠️ Invalid .list usage."

    if parts[1].lower() == "show":
        if not memory:
            return "There is no current required tasks."
        response = ["Here's all the required tasks:"]
        for subj, tasks in memory.items():
            for category, entry in tasks.items():
                response.append(f"{subj.upper()} [{category.upper()}]: {entry}")
        return "\n".join(response)

    if parts[1].lower() == "clear" and len(parts) >= 3:
        subject = parts[2].capitalize()
        if subject in memory:
            memory.pop(subject)
            return f"List cleared for {subject}!"
        return f"No list found for {subject}."

    if len(parts) >= 4:
        subject = parts[1].capitalize()
        category = parts[2].upper()
        content = " ".join(parts[3:])
        if subject not in memory:
            memory[subject] = {}
        memory[subject][category] = content
        return "Successfully listed input!"

    return "⚠️ Incomplete .list command."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
