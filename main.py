import os
import sqlite3
from fastapi import FastAPI, Request
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "filmithe100")

FREE_VIEWS = 2

app = FastAPI()

DB = "bot.db"


def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            views INTEGER DEFAULT 0,
            vip INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        "SELECT views, vip FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()

    if row is None:
        cur.execute(
            "INSERT INTO users (user_id, views, vip) VALUES (?, 0, 0)",
            (user_id,)
        )
        conn.commit()
        row = (0, 0)

    conn.close()
    return row


def add_view(user_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET views = views + 1 WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()


def bot_url():
    return f"https://api.telegram.org/bot{BOT_TOKEN}"


async def telegram(method, data):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{bot_url()}/{method}",
            json=data
        )
        return response.json()


async def send_message(chat_id, text, buttons=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if buttons:
        data["reply_markup"] = {
            "inline_keyboard": buttons
        }

    return await telegram("sendMessage", data)


async def handle_start(chat_id, user_id, start_parameter):
    views, vip = get_user(user_id)

    if vip == 1:
        await send_message(
            chat_id,
            "🎬 <b>VIP фаъол аст.</b>\n\n"
            "Акнун ту метавонӣ филмҳоро бе лимити просмотр тамошо кунӣ."
        )
        return

    if views >= FREE_VIEWS:
        await send_message(
            chat_id,
            "⚠️ <b>Лимит просмотров исчерпан.</b>\n\n"
            "Для дальнейшего просмотра нужен VIP.",
            [
                [
                    {
                        "text": "💰 Купить VIP ✅",
                        "callback_data": "buy_vip"
                    }
                ]
            ]
        )
        return

    add_view(user_id)

    views += 1

    await send_message(
        chat_id,
        f"🎬 <b>VIP Kino TV</b>\n\n"
        f"Просмотр открыт.\n"
        f"👁 Просмотров использовано: {views}/{FREE_VIEWS}",
        [
            [
                {
                    "text": "🎬 Смотреть фильм",
                    "url": f"https://t.me/{CHANNEL_USERNAME}/13"
                }
            ],
            [
                {
                    "text": "💰 Купить VIP",
                    "callback_data": "buy_vip"
                }
            ]
        ]
    )


@app.get("/")
async def home():
    return {"status": "VIP Kino TV bot is running"}


@app.post("/webhook")
async def webhook(request: Request):
    update = await request.json()

    if "message" in update:
        message = update["message"]

        chat = message.get("chat", {})
        user = message.get("from", {})

        chat_id = chat.get("id")
        user_id = user.get("id")

        text = message.get("text", "")

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            start_parameter = parts[1] if len(parts) > 1 else ""

            await handle_start(
                chat_id,
                user_id,
                start_parameter
            )

    elif "callback_query" in update:
        callback = update["callback_query"]

        callback_id = callback["id"]
        user_id = callback["from"]["id"]
        chat_id = callback["message"]["chat"]["id"]
        data = callback.get("data")

        await telegram(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_id
            }
        )

        if data == "buy_vip":
            await send_message(
                chat_id,
                "💎 <b>Покупка VIP</b>\n\n"
                "Выбери срок VIP:",
                [
                    [
                        {
                            "text": "💎 1 месяц — 199 ₽",
                            "callback_data": "vip_1_month"
                        }
                    ]
                ]
            )

        elif data == "vip_1_month":
            await send_message(
                chat_id,
                "💳 <b>Покупка VIP</b>\n\n"
                "Способ оплаты: Alif\n"
                "Срок VIP: 1 месяц\n"
                "Стоимость: 199 ₽\n\n"
                "После оплаты отправь чек администратору."
            )


init_db()
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, Request

# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "filmithe100")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MINIVIPKinoTV_bot")

# Telegram ID-и администратор
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# URL-и Render
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://vip-kino-bot.onrender.com"
)

# VIP
VIP_PRICE = 125
VIP_DAYS = 30

# 2 просмотр ройгон
FREE_VIEWS = 2

# Сбербанк
SBERBANK_PHONE = "+79960374218"

DB = "bot.db"

app = FastAPI()


# =========================
# DATABASE
# =========================

def db():
    return sqlite3.connect(DB)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            views INTEGER DEFAULT 0,
            vip_until TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_message_id INTEGER UNIQUE,
            title TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT views, vip_until FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()

    if row is None:
        cur.execute(
            "INSERT INTO users (user_id, views, vip_until) VALUES (?, 0, NULL)",
            (user_id,)
        )
        conn.commit()
        row = (0, None)

    conn.close()

    views = row[0]
    vip_until = row[1]

    vip_active = False

    if vip_until:
        try:
            vip_date = datetime.fromisoformat(vip_until)

            if vip_date > datetime.now(timezone.utc):
                vip_active = True
        except Exception:
            vip_active = False

    return views, vip_active, vip_until


def add_view(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET views = views + 1 WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()


def add_movie(message_id, title):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO movies
        (channel_message_id, title, created_at)
        VALUES (?, ?, ?)
    """, (
        message_id,
        title,
        datetime.now(timezone.utc).isoformat()
    ))

    conn.commit()
    conn.close()


def get_movie(movie_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT channel_message_id, title FROM movies WHERE id = ?",
        (movie_id,)
    )

    row = cur.fetchone()

    conn.close()

    return row


# =========================
# TELEGRAM API
# =========================

def bot_url():
    return f"https://api.telegram.org/bot{BOT_TOKEN}"


async def telegram(method, data=None):
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{bot_url()}/{method}",
            json=data or {}
        )

        return response.json()


async def send_message(chat_id, text, buttons=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if buttons:
        data["reply_markup"] = {
            "inline_keyboard": buttons
        }

    return await telegram("sendMessage", data)


# =========================
# WEBHOOK
# =========================

async def set_webhook():
    url = f"{WEBHOOK_URL}/webhook"

    result = await telegram(
        "setWebhook",
        {
            "url": url,
            "allowed_updates": [
                "message",
                "callback_query",
                "channel_post"
            ]
        }
    )

    print("Webhook:", result)


# =========================
# MOVIE BUTTON
# =========================

async def add_movie_button(message_id, movie_id):

    link = (
        f"https://t.me/{BOT_USERNAME}"
        f"?start=movie_{movie_id}"
    )

    buttons = {
        "inline_keyboard": [
            [
                {
                    "text": "🎬 Тамошо кардан",
                    "url": link
                }
            ]
        ]
    }

    result = await telegram(
        "editMessageReplyMarkup",
        {
            "chat_id": f"@{CHANNEL_USERNAME}",
            "message_id": message_id,
            "reply_markup": buttons
        }
    )

    return result


# =========================
# NEW CHANNEL MOVIE
# =========================

async def handle_channel_post(post):

    message_id = post.get("message_id")

    if not message_id:
        return

    # Фақат видео ё document қабул мекунем
    is_video = "video" in post
    is_document = "document" in post

    if not is_video and not is_document:
        return

    caption = post.get("caption", "")

    if caption:
        title = caption.split("\n")[0][:200]
    else:
        title = f"Фильм #{message_id}"

    # Сабти филм
    add_movie(message_id, title)

    # Пайдо кардани movie ID
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM movies WHERE channel_message_id = ?",
        (message_id,)
    )

    row = cur.fetchone()

    conn.close()

    if not row:
        return

    movie_id = row[0]

    # Тугма ба пост илова мешавад
    await add_movie_button(
        message_id,
        movie_id
    )

    print(
        f"New movie: {title} | "
        f"message_id={message_id} | "
        f"movie_id={movie_id}"
    )


# =========================
# START / MOVIE
# =========================

async def handle_start(chat_id, user_id, parameter):

    views, vip_active, vip_until = get_user(user_id)

    # =====================
    # VIP ACTIVE
    # =====================

    if vip_active:
        if parameter.startswith("movie_"):
            try:
                movie_id = int(parameter.replace("movie_", ""))
            except ValueError:
                await send_message(
                    chat_id,
                    "❌ Филм ёфт нашуд."
                )
                return

            movie = get_movie(movie_id)

            if not movie:
                await send_message(
                    chat_id,
                    "❌ Ин филм дигар ёфт нашуд."
                )
                return

            message_id, title = movie

            await telegram(
                "copyMessage",
                {
                    "chat_id": chat_id,
                    "from_chat_id": f"@{CHANNEL_USERNAME}",
                    "message_id": message_id
                }
            )

            return

        await send_message(
            chat_id,
            "💎 <b>VIP фаъол аст!</b>\n\n"
            "Ту метавонӣ ҳамаи филмҳоро бе маҳдудияти просмотр тамошо кунӣ."
        )

        return

    # =====================
    # MOVIE
    # =====================

    if parameter.startswith("movie_"):

        try:
            movie_id = int(
                parameter.replace("movie_", "")
            )
        except ValueError:

            await send_message(
                chat_id,
                "❌ ID-и филм нодуруст аст."
            )

            return

        movie = get_movie(movie_id)

        if not movie:

            await send_message(
                chat_id,
                "❌ Филм ёфт нашуд."
            )

            return

        message_id, title = movie

        # =================
        # FREE VIEWS
        # =================

        if views >= FREE_VIEWS:

            await send_message(
                chat_id,

                "⚠️ <b>Лимити просмотр тамом шуд.</b>\n\n"

                "Барои тамошои минбаъдаи филмҳо "
                "VIP лозим аст.\n\n"

                f"💎 VIP: <b>{VIP_PRICE} ₽ / {VIP_DAYS} рӯз</b>",

                [
                    [
                        {
                            "text": "💎 Харидани VIP",
                            "callback_data": "buy_vip"
                        }
                    ]
                ]
            )

            return

        # +1 просмотр
        add_view(user_id)

        views += 1

        # Филмро ба корбар мефиристем
        result = await telegram(
            "copyMessage",
            {
                "chat_id": chat_id,
                "from_chat_id": f"@{CHANNEL_USERNAME}",
                "message_id": message_id
            }
        )

        if not result.get("ok"):

            await send_message(
                chat_id,
                "❌ Филмро фиристода натавонистам."
            )

            return

        await send_message(
            chat_id,

            f"🎬 <b>{title}</b>\n\n"
            f"👁 Просмотр: <b>{views}/{FREE_VIEWS}</b>\n\n"
            "Барои просмотрҳои минбаъда VIP харед.",

            [
                [
                    {
                        "text": "💎 Харидани VIP",
                        "callback_data": "buy_vip"
                    }
                ]
            ]
        )

        return

    # =====================
    # NORMAL START
    # =====================

    await send_message(
        chat_id,

        "🎬 <b>Хуш омадед ба VIP Kino TV!</b>\n\n"
        "2 просмотр барои шумо ройгон аст.\n"
        "Баъд аз он барои тамошои филмҳо VIP лозим мешавад.\n\n"
        f"💎 VIP: <b>{VIP_PRICE} ₽ / моҳ</b>"
    )


# =========================
# CALLBACKS
# =========================

async def handle_callback(callback):

    callback_id = callback["id"]

    user_id = callback["from"]["id"]

    message = callback.get("message", {})

    chat_id = message.get("chat", {}).get("id")

    data = callback.get("data")

    # Хориҷ кардани loading
    await telegram(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id
        }
    )

    # =====================
    # BUY VIP
    # =====================

    if data == "buy_vip":

        await send_message(
            chat_id,

            "💎 <b>VIP — 1 моҳ</b>\n\n"

            f"💰 Нарх: <b>{VIP_PRICE} ₽</b>\n\n"

            "🏦 <b>Сбербанк</b>\n"
            f"📱 Номер: <code>{SBERBANK_PHONE}</code>\n\n"

            "Пас аз пардохт чекро ба администратор фиристед.\n"
            "Администратор VIP-ро фаъол мекунад.",

            [
                [
                    {
                        "text": "📩 Ирсоли чек ба администратор",
                        "url": "https://t.me/"
                        + BOT_USERNAME
                    }
                ]
            ]
        )

        return

    # =====================
    # ADMIN ACTIVATION
    # =====================

    if data.startswith("approve_"):

        if user_id != ADMIN_ID:
            return

        try:
            target_user = int(
                data.replace("approve_", "")
            )
        except ValueError:
            return

        activate_vip(target_user)

        await send_message(
            target_user,

            "✅ <b>VIP фаъол шуд!</b>\n\n"
            f"💎 Муҳлат: {VIP_DAYS} рӯз\n"
            "Акнун ҳамаи филмҳоро бе лимит тамошо карда метавонед."
        )

        await send_message(
            chat_id,
            "✅ VIP фаъол карда шуд."
        )


# =========================
# VIP
# =========================

def activate_vip(user_id):

    vip_until = (
        datetime.now(timezone.utc)
        + timedelta(days=VIP_DAYS)
    ).isoformat()

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET vip_until = ? WHERE user_id = ?",
        (
            vip_until,
            user_id
        )
    )

    conn.commit()
    conn.close()


# =========================
# WEB ROUTES
# =========================

@app.get("/")
async def home():

    return {
        "status": "VIP Kino TV bot is running"
    }


@app.post("/webhook")
async def webhook(request: Request):

    update = await request.json()

    # =====================
    # CHANNEL POST
    # =====================

    if "channel_post" in update:

        await handle_channel_post(
            update["channel_post"]
        )

        return {
            "ok": True
        }

    # =====================
    # MESSAGE
    # =====================

    if "message" in update:

        message = update["message"]

        chat = message.get("chat", {})
        user = message.get("from", {})

        chat_id = chat.get("id")
        user_id = user.get("id")

        text = message.get("text", "")

        if text.startswith("/start"):

            parts = text.split(
                maxsplit=1
            )

            parameter = (
                parts[1]
                if len(parts) > 1
                else ""
            )

            await handle_start(
                chat_id,
                user_id,
                parameter
            )

        return {
            "ok": True
        }

    # =====================
    # CALLBACK
    # =====================

    if "callback_query" in update:

        await handle_callback(
            update["callback_query"]
        )

        return {
            "ok": True
        }

    return {
        "ok": True
    }


# =========================
# STARTUP
# =========================

@app.on_event("startup")
async def startup():

    init_db()

    try:
        await set_webhook()
    except Exception as e:
        print(
            "Webhook error:",
            type(e).__name__,
            str(e)
        )
