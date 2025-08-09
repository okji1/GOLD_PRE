import requests

url = "https://api.investing.com/api/financialdata/1209162/chart"
headers = {
    "User-Agent": "Mozilla/5.0"
}

res = requests.get(url, headers=headers)
print('Status:', res.status_code)
print('Response:', res.text)
try:
    data = res.json()
    # 최근 시세 출력
    print(data["data"]["last_close_price"])
except Exception as e:
    print('JSON 파싱 오류:', e)
