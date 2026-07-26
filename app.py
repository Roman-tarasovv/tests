
from flask import Flask, send_from_directory, jsonify
from pathlib import Path
import threading
import json
from filelock import FileLock
import os

app = Flask(__name__, static_folder=None)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = DATA_DIR / "records.json"
LOCK_PATH = DATA_DIR / "records.json.lock"

if not STORE_PATH.exists():
    STORE_PATH.write_text("{}", encoding="utf-8")

def _read_store_unlocked():
    raw = STORE_PATH.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except:
        return {}
    return data if isinstance(data, dict) else {}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/receive-transaction')
def receive_transaction():
    return send_from_directory('receive-transaction', 'index.html')

@app.route('/data/records.json')
def get_records():
    with FileLock(str(LOCK_PATH)):
        store = _read_store_unlocked()
        return jsonify(store)

@app.route('/<path:path>')
def static_files(path):
    p = (path or "").replace("\\", "/").lstrip("/")

    forbidden_exts = {".py", ".txt", ".service", ".ini", ".temp"}
    forbidden_prefixes = ("venv/", "data/", ".git/")

    lp = p.lower()
    if lp.startswith(forbidden_prefixes):
        return "404 Not Found", 404
    for ext in forbidden_exts:
        if lp.endswith(ext):
            return "404 Not Found", 404

    if lp.startswith("receive-transaction/"):
        rel = p.split("/", 1)[1]
        return send_from_directory("receive-transaction", rel)

    return send_from_directory(".", p)

def run_flask():
    port = int(os.environ.get('PORT', 8888))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    from bot import bot
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

