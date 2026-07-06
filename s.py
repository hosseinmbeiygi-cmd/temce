import requests

API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"
url = f"https://Api.BrsApi.ir/Codal/Announcement.php?key={API_KEY}&l18=وبملت&page=1"
resp = requests.get(url).json()
print(f"تعداد کل اطلاعیه‌ها: {resp.get('count_announcement', 0)}")
print(f"تعداد صفحات: {resp.get('count_page', 0)}")