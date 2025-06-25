from flask import Flask, request
import requests
import os

app = Flask(__name__)

HUGGINGFACE_API_KEY = os.getenv("shh")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

def get_huggingface_reply(message):
    url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": message
    }

    print(f"🔄 Calling Hugging Face with message: {message}")
    response = requests.post(url, headers=headers, json=payload)
    print(f"📊 HF Response status: {response.status_code}")
    print(f"📋 HF Response body: {response.text}")

    if response.status_code == 200:
        output = response.json()
        print(f"🔍 Parsed output: {output}")

        # Handle different response formats
        if isinstance(output, list) and len(output) > 0:
            if "generated_text" in output[0]:
                reply = output[0]["generated_text"]
                print(f"✅ Found generated_text: {reply}")
                return reply
        elif isinstance(output, dict):
            if "generated_text" in output:
                reply = output["generated_text"]
                print(f"✅ Found generated_text in dict: {reply}")
                return reply
            elif "error" in output:
                print(f"❌ HF API Error: {output['error']}")
                return "🤖 The AI model is currently loading. Please try again in a moment."

        print(f"⚠️ Unexpected response format: {output}")
        return "🤖 Model responded, but no text was generated."
    else:
        print(f"❌ HF API failed with status {response.status_code}: {response.text}")
        return "It didn't work, try again. The model didn't meet your reply/question."

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is online!"

@app.route("/test", methods=["GET"])
def test_bot():
    # Test if Hugging Face API is working
    test_message = "Hello"
    reply = get_huggingface_reply(test_message)
    return f"<h2>Bot Test</h2><p><strong>Test message:</strong> '{test_message}'</p><p><strong>Bot reply:</strong> '{reply}'</p>"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Verification flow
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("✅ Webhook verified")
            return challenge, 200
        else:
            print("❌ Webhook verification failed")
            return "Verification failed", 403

    elif request.method == "POST":
        data = request.get_json()
        print(f"📨 Webhook POST received:\n{data}")

        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]
                message = messaging_event.get("message", {}).get("text")
                print(f"📩 Sender: {sender_id}")
                print(f"📄 Message: {message}")

                if not message:
                    print("⚠️ No text found in message.")
                    continue

                try:
                    reply = get_huggingface_reply(message)
                    print(f"🤖 HuggingFace reply: {reply}")
                except Exception as e:
                    print(f"❌ HuggingFace error: {e}")
                    reply = "Something went wrong while contacting HuggingFace."

                # Send back to user
                send_url = "https://graph.facebook.com/v18.0/me/messages"
                params = {"access_token": PAGE_ACCESS_TOKEN}
                headers = {"Content-Type": "application/json"}
                payload = {
                    "recipient": {"id": sender_id},
                    "message": {"text": reply}
                }
                print(f"📤 Sending reply to user: {payload}")
                fb_response = requests.post(send_url, params=params, headers=headers, json=payload)
                print(f"📬 Facebook response: {fb_response.status_code} {fb_response.text}")

        return "✅ Message received", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)