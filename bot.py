import json
import random
import time
import sys
import logging
import os
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from filelock import FileLock

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STORE_PATH = DATA_DIR / "records.json"
LOCK_PATH = DATA_DIR / "records.json.lock"

if not STORE_PATH.exists():
    STORE_PATH.write_text("{}", encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("trustbot")
logging.getLogger("telebot").setLevel(logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8888").strip()

if not (BASE_URL.startswith("http://") or BASE_URL.startswith("https://")):
    BASE_URL = "http://" + BASE_URL.lstrip("/")
BASE_URL = BASE_URL.replace("://localhost", "://127.0.0.1").rstrip("/")

if not TOKEN:
    raise SystemExit("No bot token in settings.ini")

bot = telebot.TeleBot(TOKEN)

state = {}

_price_cache = {"ts": 0, "rates": {"USDT": 1.0, "USDC": 1.0}}

def _read_store_unlocked():
    raw = STORE_PATH.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except:
        return {}
    return data if isinstance(data, dict) else {}

def _write_store_unlocked(store):
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE_PATH)

def get_store():
    with FileLock(str(LOCK_PATH)):
        return _read_store_unlocked()

def put_record(record):
    with FileLock(str(LOCK_PATH)):
        store = _read_store_unlocked()
        store[record["id"]] = record
        _write_store_unlocked(store)

def delete_record(rid, chat_id):
    with FileLock(str(LOCK_PATH)):
        store = _read_store_unlocked()
        rec = store.get(rid)
        if not rec:
            return False, "not_found"
        if str(rec.get("chatId", "")) != str(chat_id):
            return False, "not_owner"
        del store[rid]
        _write_store_unlocked(store)
        return True, "deleted"

def new_id(store):
    for _ in range(200):
        rid = str(random.randint(10000000, 99999999))
        if rid not in store:
            return rid
    return str(int(time.time()))

def q2(x):
    return float(f"{x:.2f}")

def q6(x):
    return float(f"{x:.6f}")

def fetch_usd_rates():
    now = int(time.time())
    if now - int(_price_cache["ts"]) < 60:
        return _price_cache["rates"]

    url = "https://api.coingecko.com/api/v3/simple/price?ids=tether,usd-coin&vs_currencies=usd"
    req = Request(url, headers={"User-Agent": "trustbot/1.0"})
    try:
        with urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8"))
        usdt = float(data.get("tether", {}).get("usd", 1.0))
        usdc = float(data.get("usd-coin", {}).get("usd", 1.0))
        rates = {"USDT": usdt, "USDC": usdc}
        _price_cache["ts"] = now
        _price_cache["rates"] = rates
        return rates
    except (URLError, HTTPError, ValueError, TimeoutError, json.JSONDecodeError):
        return _price_cache["rates"]

def usd_rate_for_coin(symbol):
    rates = fetch_usd_rates()
    return float(rates.get(symbol, 1.0))

def reset(chat_id):
    state[chat_id] = {"step": "idle"}

def menu_kb():
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("Создать ссылку", callback_data="menu:create"),
        InlineKeyboardButton("Список ссылок", callback_data="menu:list"),
    )
    return kb

def show_menu(chat_id, text="Меню"):
    bot.send_message(chat_id, text, reply_markup=menu_kb())

def show_coin_picker(chat_id):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("USDT", callback_data="coin:USDT"),
        InlineKeyboardButton("USDC", callback_data="coin:USDC"),
    )
    bot.send_message(chat_id, "Выбери монету", reply_markup=kb)

def show_net_picker(chat_id):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("TRC20", callback_data="net:TRC20"),
        InlineKeyboardButton("ERC20", callback_data="net:ERC20"),
    )
    bot.send_message(chat_id, "Выбери сеть", reply_markup=kb)

def fmt_amount(a):
    try:
        x = float(a)
    except:
        return "0"
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"

def build_links_markup(chat_id, store):
    items = []
    for rid, rec in store.items():
        if isinstance(rec, dict) and str(rec.get("chatId", "")) == str(chat_id):
            items.append((rid, rec))

    items.sort(key=lambda x: int(x[1].get("createdAt", 0)), reverse=True)
    items = items[:20]

    if not items:
        return "Ссылок пока нет", menu_kb()

    kb = InlineKeyboardMarkup()

    for rid, rec in items:
        link = f"{BASE_URL}/receive-transaction?id={rid}"
        label = f"{rec.get('coin','')} {fmt_amount(rec.get('amountTokens',0))} {rec.get('network','')}".strip()
        if not label:
            label = f"Открыть {rid}"
        if len(label) > 40:
            label = label[:40]
        kb.row(
            InlineKeyboardButton(label, url=link),
            InlineKeyboardButton("🗑", callback_data=f"del:{rid}")
        )

    return "Ваши ссылки:", kb

def send_links_list(chat_id):
    store = get_store()
    text, kb = build_links_markup(chat_id, store)
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.message_handler(commands=["start"])
def cmd_start(m):
    log.info(f"START chat={m.chat.id}")
    reset(m.chat.id)
    show_menu(m.chat.id, "Меню")

@bot.callback_query_handler(func=lambda c: c.data == "menu:create")
def cb_menu_create(c):
    chat_id = c.message.chat.id
    log.info(f"MENU_CREATE chat={chat_id}")
    bot.answer_callback_query(c.id)
    state[chat_id] = {"step": "coin"}
    show_coin_picker(chat_id)

@bot.callback_query_handler(func=lambda c: c.data == "menu:list")
def cb_menu_list(c):
    chat_id = c.message.chat.id
    log.info(f"MENU_LIST chat={chat_id}")
    bot.answer_callback_query(c.id)
    send_links_list(chat_id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("coin:"))
def cb_coin(c):
    chat_id = c.message.chat.id
    bot.answer_callback_query(c.id)
    s = state.get(chat_id) or {}
    if s.get("step") != "coin":
        return
    coin = c.data.split(":", 1)[1]
    s["coin"] = coin
    s["step"] = "network"
    state[chat_id] = s
    show_net_picker(chat_id)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("net:"))
def cb_net(c):
    chat_id = c.message.chat.id
    bot.answer_callback_query(c.id)
    s = state.get(chat_id) or {}
    if s.get("step") != "network":
        return
    net = c.data.split(":", 1)[1]
    s["network"] = net
    s["step"] = "amount"
    state[chat_id] = s
    bot.send_message(chat_id, "Кол-во токенов")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("del:"))
def cb_delete(c):
    chat_id = c.message.chat.id
    rid = c.data.split(":", 1)[1]
    log.info(f"DELETE_CLICK chat={chat_id} rid={rid}")
    try:
        ok, status = delete_record(rid, chat_id)
        log.info(f"DELETE_RESULT chat={chat_id} rid={rid} ok={ok} status={status}")
        bot.answer_callback_query(c.id, "Удалено" if ok else "Не найдено", show_alert=False)
        store2 = get_store()
        text, kb = build_links_markup(chat_id, store2)
        bot.edit_message_text(text, chat_id, c.message.message_id, reply_markup=kb)
    except Exception as e:
        log.exception(f"DELETE_FAILED chat={chat_id} rid={rid} err={e}")
        try:
            bot.answer_callback_query(c.id, "Ошибка", show_alert=False)
        except:
            pass

@bot.message_handler(content_types=["text"])
def on_text(m):
    chat_id = m.chat.id
    s = state.get(chat_id)
    if not s:
        reset(chat_id)
        show_menu(chat_id, "Меню")
        return

    step = s.get("step")
    t = (m.text or "").strip()

    log.info(f"TEXT chat={chat_id} step={step}")

    if step == "amount":
        try:
            amount = float(t.replace(",", "."))
        except:
            bot.send_message(chat_id, "Введи число больше 0")
            return
        if amount <= 0:
            bot.send_message(chat_id, "Введи число больше 0")
            return
        s["amountTokens"] = q6(amount)
        s["step"] = "walletName"
        state[chat_id] = s
        bot.send_message(chat_id, "Название кошелька")
        return

    if step == "walletName":
        s["walletName"] = t
        s["step"] = "fromAddress"
        state[chat_id] = s
        bot.send_message(chat_id, "Адрес кошелька отправителя")
        return

    if step == "fromAddress":
        s["fromAddress"] = t
        s["step"] = "toAddress"
        state[chat_id] = s
        bot.send_message(chat_id, "Адрес кошелька получателя")
        return

    if step == "toAddress":
        s["toAddress"] = t

        coin = s.get("coin")
        network = s.get("network")
        amount_tokens = float(s.get("amountTokens", 0.0))
        wallet_name = s.get("walletName", "")
        from_addr = s.get("fromAddress", "")
        to_addr = s.get("toAddress", "")

        rate = usd_rate_for_coin(coin)

        base_fee_percent = round(random.uniform(0.5, 1.0), 2)
        discount_percent = random.randint(10, 100)
        effective_fee_percent = base_fee_percent * (1.0 - discount_percent / 100.0)

        fee_tokens = q6(amount_tokens * (effective_fee_percent / 100.0))

        amount_usd = q2(amount_tokens * rate)
        fee_usd = q2(fee_tokens * rate)
        total_usd = q2(amount_usd + fee_usd)

        store = get_store()
        rid = new_id(store)

        record = {
            "id": rid,
            "chatId": chat_id,
            "coin": coin,
            "network": network,
            "usdRate": float(f"{rate:.8f}"),
            "amountTokens": amount_tokens,
            "amountUsd": amount_usd,
            "walletName": wallet_name,
            "fromAddress": from_addr,
            "toAddress": to_addr,
            "baseFeePercent": base_fee_percent,
            "discountPercent": discount_percent,
            "feeTokens": fee_tokens,
            "feeUsd": fee_usd,
            "totalUsd": total_usd,
            "createdAt": int(time.time())
        }

        put_record(record)

        log.info(f"CREATED chat={chat_id} rid={rid} coin={coin} rate={rate}")

        reset(chat_id)
        bot.send_message(chat_id, f"{BASE_URL}/receive-transaction?id={rid}", reply_markup=menu_kb())
        return

    show_menu(chat_id, "Меню")

if __name__ == "__main__":
    log.info(f"BASE_DIR={BASE_DIR}")
    log.info(f"STORE_PATH={STORE_PATH}")
    log.info(f"BASE_URL={BASE_URL}")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
