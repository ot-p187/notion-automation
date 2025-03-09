import requests
import json
import time
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# from pprint import pprint
# from dotenv import load_dotenv

# 環境変数の読み込み
# load_dotenv()

# Notion API設定
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
SCHEDULE_DB_ID = os.getenv("SCHEDULE_DB_ID")
ATTENDANCE_DB_ID = os.getenv("ATTENDANCE_DB_ID")

# Gmail設定
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# メール送信関数
def send_email(subject, body, recipient):
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, recipient, msg.as_string())

# 会議スケジュールDBから未処理の全ページを取得（ページネーション対応）
def get_unprocessed_schedules():
    url = f"https://api.notion.com/v1/databases/{SCHEDULE_DB_ID}/query"
    payload = {
        "filter": {
            "property": "処理済み",
            "checkbox": {"equals": False}
        },
        "sorts": [
            {"property": "作成日", "direction": "descending"}
        ],
        "page_size": 100
    }

    results = []
    while True:
        response = requests.post(url, headers=HEADERS, json=payload)
        data = response.json()
        results.extend(data.get("results", []))

        if not data.get("has_more", False):
            break

        payload["start_cursor"] = data["next_cursor"]

    return results

# 出席依頼DBにページを追加
def create_attendance_entry(name, email, schedule_page_id):
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": ATTENDANCE_DB_ID},
        "properties": {
            "名前": {"title": [{"text": {"content": name}}]},
            "メール": {"email": email},
            "会議スケジュールDB": {"relation": [{"id": schedule_page_id}]},
            "出欠": {"select": {"name": "未回答"}}
        }
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    return response.json()

# 出席依頼DBの削除
def delete_attendance_entry(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    response = requests.delete(url, headers=HEADERS)
    return response.json()

# 出席依頼DBから削除対象のエントリーを取得し削除
def remove_deleted_schedules():
    url = f"https://api.notion.com/v1/databases/{ATTENDANCE_DB_ID}/query"
    response = requests.post(url, headers=HEADERS)
    data = response.json()
    attendance_entries = data.get("results", [])

    # 現在の会議スケジュールのIDを取得
    schedules = get_unprocessed_schedules()
    valid_schedule_ids = {schedule["id"] for schedule in schedules}

    for entry in attendance_entries:
        attendance_id = entry["id"]
        related_schedules = entry["properties"].get("会議スケジュールDB", {}).get("relation", [])
        if not related_schedules or related_schedules[0]["id"] not in valid_schedule_ids:
            delete_attendance_entry(attendance_id)
            print(f"Deleted attendance entry {attendance_id} due to missing schedule.")

# スケジュールDBの「処理済み」チェックをONにする
def mark_schedule_as_processed(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"処理済み": {"checkbox": True}}}
    response = requests.patch(url, headers=HEADERS, json=payload)
    return response.json()

# メイン処理
def process_new_schedules():
    schedules = get_unprocessed_schedules()
    if not schedules:
        print("No new schedules found.")
        return

    for schedule in schedules:
        schedule_page_id = schedule["id"]
        schedule_title = schedule["properties"].get("会議名", {}).get("title", [{}])[0].get("text", {}).get("content", "未設定")
        schedule_date = schedule["properties"].get("日付", {}).get("date", {}).get("start", "未設定")
        members_property = schedule["properties"].get("メンバーリスト", {}).get("formula", {})
        if not members_property:
            print("No members found for schedule.")
            continue

        members_text = members_property.get("string", "")
        members_list = [m.strip() for m in members_text.split(",")]

        for member in members_list:
            try:
                name, email = member.split(" : ")
                create_attendance_entry(name, email, schedule_page_id)
                print(f"Added {name} ({email}) to attendance DB")
                send_email("新しい会議が設定されました。", f"会議: {schedule_title}\n日付: {schedule_date}\n詳細はAppで確認してください。", email)
            except ValueError:
                print(f"Skipping invalid entry: {member}")

        # スケジュールを「処理済み」に更新
        mark_schedule_as_processed(schedule_page_id)
        print(f"Marked schedule {schedule_page_id} as processed.")

    # 削除されたスケジュールの出席依頼を削除
    remove_deleted_schedules()

if __name__ == "__main__":
    process_new_schedules()
