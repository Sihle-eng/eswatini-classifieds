import requests

CRON_SECRET = "eswatini2025daily"   # match your config
RENDER_URL = "https://eswatini-classifieds.onrender.com/ping"  # replace with your actual onrender.com URL

try:
    r = requests.get(RENDER_URL, params={"secret": CRON_SECRET}, timeout=10)
    print(f"Ping status: {r.status_code}")
except Exception as e:
    print(f"Ping failed: {e}")