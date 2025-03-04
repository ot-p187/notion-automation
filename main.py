import requests
import json
import time

# Notion API設定
NOTION_API_KEY = "your_notion_api_key"
SCHEDULE_DB_ID = "your_schedule_db_id"
ATTENDANCE_DB_ID = "your_attendance_db_id"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 会議スケジュールDBから最新ページを取得
def get_latest_schedule():
    url = f"https://api.notion.com/v1/databases/{SCHEDULE_DB_ID}/query"
    response = requests.post(url, headers=HEADERS)
    data = response.json()
    
    # 最新のページを取得
    if "results" in data and len(data["results"]) > 0:
        return data["results"][0]  # 最新のページ
    return None

# 出席依頼DBにページを追加
def create_attendance_entry(name, email, schedule_page_id):
    url = "https://api.notion.com/v1/pages"
    
    payload = {
        "parent": {"database_id": ATTENDANCE_DB_ID},
        "properties": {
            "名前": {"title": [{"text": {"content": name}}]},
            "メール": {"email": email},
            "リレーション": {"relation": [{"id": schedule_page_id}]}
        }
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    return response.json()

# メイン処理
def process_new_schedule():
    latest_schedule = get_latest_schedule()
    if not latest_schedule:
        print("No new schedule found.")
        return
    
    schedule_page_id = latest_schedule["id"]
    
    # メンバーリストを取得
    members_property = latest_schedule["properties"]["メンバーリスト"]["rich_text"]
    if not members_property:
        print("No members found.")
        return
    
    members_text = members_property[0]["text"]["content"]
    members_list = [m.strip() for m in members_text.split(",")]  # リストに変換
    
    for member in members_list:
        try:
            name, email = member.split(" : ")
            create_attendance_entry(name, email, schedule_page_id)
            print(f"Added {name} ({email}) to attendance DB")
        except ValueError:
            print(f"Skipping invalid entry: {member}")

# 定期実行（5分ごと）
# while True:
#    process_new_schedule()
#    time.sleep(300)

if __name__ == "__main__":
    process_new_schedule()
