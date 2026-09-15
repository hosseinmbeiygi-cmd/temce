import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("BRSAPI_API_KEY", "")
r = requests.get(
    "https://api.brsapi.ir/Codal/Announcement.php",
    params={"key": API_KEY, "l18": "فولاد", "date_start": "1405-01-01", "date_end": "1405-05-01", "page": 1},
    timeout=30,
)
print(f"status: {r.status_code}")
data = r.json()
count = data.get("count_announcement", 0)
anns = data.get("announcement", [])
print(f"count_announcement: {count}")
print(f"got: {len(anns)}")
if anns:
    print(f"first title: {anns[0].get('title', '')[:60]}")
    print(f"first date: {anns[0].get('date_send', '')}")

