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
