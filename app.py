import os
import hmac
import hashlib
import base64
import requests
import pandas as pd

from flask import Flask, request, abort
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")


def verify_signature(body, signature):
    hash_value = hmac.new(
        CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()

    expected_signature = base64.b64encode(hash_value).decode("utf-8")

    return hmac.compare_digest(expected_signature, signature)


def reply_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }

    data = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text[:5000]
            }
        ]
    }

    requests.post(url, headers=headers, json=data)


def download_file(message_id):
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"

    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None

    filename = f"/tmp/{message_id}.xlsx"

    with open(filename, "wb") as f:
        f.write(response.content)

    return filename


def analyze_excel(filename):
    try:
        excel = pd.ExcelFile(filename)

        result = "📊 KẾT QUẢ ĐỌC FILE\n\n"
        result += f"📁 File: {os.path.basename(filename)}\n"
        result += f"📑 Số sheet: {len(excel.sheet_names)}\n\n"

        for sheet in excel.sheet_names:
            df = pd.read_excel(filename, sheet_name=sheet)

            result += f"📌 Sheet: {sheet}\n"
            result += f"• Số dòng: {len(df)}\n"
            result += f"• Số cột: {len(df.columns)}\n"

            columns = list(df.columns[:10])

            if columns:
                result += "• Cột: " + ", ".join(str(x) for x in columns) + "\n"

            result += "\n"

        return result

    except Exception as e:
        return f"❌ Không đọc được file Excel.\nLỗi: {str(e)}"


@app.route("/", methods=["GET"])
def home():
    return "LINE BOT đang hoạt động!"


@app.route("/webhook", methods=["POST"])
def webhook():

    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data()

    if not verify_signature(body, signature):
        abort(400)

    data = request.get_json()

    for event in data.get("events", []):

        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        reply_token = event.get("replyToken")

        if message.get("type") == "text":

            text = message.get("text", "").strip().lower()

            if text == "xin chào":
                reply_message(
                    reply_token,
                    "Xin chào 👋\nTôi là LINE BOT.\n\n"
                    "Bạn có thể gửi file Excel và tôi sẽ đọc số liệu."
                )

            elif text == "đọc số liệu":
                reply_message(
                    reply_token,
                    "📊 Bạn hãy gửi file Excel (.xlsx) cho tôi.\n\n"
                    "Tôi sẽ đọc và báo cáo số liệu."
                )

            else:
                reply_message(
                    reply_token,
                    f"Bạn vừa gửi: {message.get('text')}"
                )

        elif message.get("type") == "file":

            file_name = message.get("fileName", "")
            message_id = message.get("id")

            if not file_name.lower().endswith(".xlsx"):
                reply_message(
                    reply_token,
                    "❌ Hiện tại tôi chỉ hỗ trợ file Excel .xlsx"
                )
                continue

            reply_message(
                reply_token,
                "⏳ Tôi đang đọc file Excel..."
            )

            filename = download_file(message_id)

            if filename is None:
                reply_message(
                    reply_token,
                    "❌ Không tải được file từ LINE."
                )
                continue

            result = analyze_excel(filename)

            reply_message(reply_token, result)

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
