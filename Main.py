import asyncio
import os
import random
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, BotCommand
)
from aiogram.filters import Command

TOKEN = '7783424722:AAEkIHR-Jg5_vd6rwbvKM1sLoihlXj--Ets'  # ЗАМЕНИТЕ НА СВОЙ ТОКЕН

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
DB_NAME = "eaabot.db"

# === БАЗА ДАННЫХ ===
def setup_db():
    with sqlite3.connect(DB_NAME) as db:
        cur = db.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                score INTEGER DEFAULT 0,
                multiplier REAL DEFAULT 1.0,
                upgrades INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS log (
                user_id INTEGER,
                timestamp TEXT,
                score INTEGER
            )
        ''')
        db.commit()

def get_user(user_id: int) -> tuple:
    with sqlite3.connect(DB_NAME) as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cur.fetchone()
        if not user:
            cur.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            db.commit()
            return (user_id, 0, 1.0, 0, 0)
        return user

def update_score(user_id: int, base: int = 1) -> int:
    user = get_user(user_id)
    multiplier = user[2]
    if user[4]:
        multiplier *= 1.5
    gained = int(base * multiplier)
    with sqlite3.connect(DB_NAME) as db:
        cur = db.cursor()
        cur.execute("UPDATE users SET score = score + ? WHERE user_id = ?", (gained, user_id))
        cur.execute(
            "INSERT INTO log (user_id, timestamp, score) VALUES (?, ?, ?)",
            (user_id, datetime.utcnow().isoformat(), gained)
        )
        db.commit()
    return gained

# === ОБРАБОТКА СООБЩЕНИЙ ===
@router.message()
async def handle_eaa(message: Message):
    # Игнорируем команды (начинающиеся с /)
    if message.text and not message.text.startswith('/') and 'эаа' in message.text.lower():
        gained = update_score(message.from_user.id)
        await message.reply(f"+{gained} очков за 'Эаа'!")

# === МАГАЗИН ===
@router.message(Command("shop"))
async def show_shop(message: Message):
    user = get_user(message.from_user.id)
    score, mult, upgrades, vip = user[1], user[2], user[3], user[4]
    price = int(10 * (2.5 ** upgrades))
    if vip:
        price = int(price * 0.75)
    vip_status = "✅" if vip else "❌"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔼 Купить прокачку", callback_data="buy_upgrade")],
        [InlineKeyboardButton(text="💎 Купить VIP", callback_data="buy_vip")],
        [InlineKeyboardButton(text="❓ Купить ???", callback_data="buy_mystery")]
    ])

    await message.reply(
        f"🪙 <b>Очки:</b> {score}\n"
        f"🔼 <b>Прокачек:</b> {upgrades}, <b>множитель:</b> {mult}\n"
        f"💎 <b>VIP:</b> {vip_status}\n\n"
        f"⬇ Выберите действие ниже:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# === ПОКУПКИ ===
async def buy_upgrade(message: Message):
    user = get_user(message.from_user.id)
    upgrades, score, vip, mult = user[3], user[1], user[4], user[2]
    price = int(10 * (2.5 ** upgrades))
    if vip:
        price = int(price * 0.75)
    if score >= price:
        new_mult = round(mult + 0.6, 2)
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.execute(
                "UPDATE users SET score = score - ?, upgrades = upgrades + 1, multiplier = ? WHERE user_id = ?",
                (price, new_mult, message.from_user.id)
            )
            db.commit()
        await message.reply(f"✅ Прокачка куплена! Множитель теперь {new_mult}")
    else:
        await message.reply("❌ Недостаточно очков.")

async def buy_vip(message: Message):
    user = get_user(message.from_user.id)
    if user[1] >= 1000 and not user[4]:
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.execute(
                "UPDATE users SET score = score - 1000, vip = 1 WHERE user_id = ?",
                (message.from_user.id,)
            )
            db.commit()
        await message.reply("🎉 Вы стали VIP!")
    else:
        await message.reply("❌ Недостаточно очков или вы уже VIP.")

async def buy_mystery(message: Message):
    user = get_user(message.from_user.id)
    price = 99999999999999
    if user[1] >= price:
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.execute("UPDATE users SET score = score - ? WHERE user_id = ?", (price, message.from_user.id))
            db.commit()
        if not os.path.exists("images"):
            await message.reply("❌ Папка 'images' не найдена.")
            return
        files = os.listdir("images")
        if not files:
            await message.reply("❌ В папке 'images' нет картинок.")
            return
        img = random.choice(files)
        with open(os.path.join("images", img), "rb") as photo:
            await message.answer_photo(photo, caption="🎁 Вот ваша случайная картинка!")
    else:
        await message.reply("❌ Недостаточно очков.")

# === CALLBACK HANDLERS ===
@router.callback_query(lambda c: c.data == "buy_upgrade")
async def cb_buy_upgrade(callback: CallbackQuery):
    callback.message.from_user = callback.from_user
    await buy_upgrade(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "buy_vip")
async def cb_buy_vip(callback: CallbackQuery):
    callback.message.from_user = callback.from_user
    await buy_vip(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "buy_mystery")
async def cb_buy_mystery(callback: CallbackQuery):
    callback.message.from_user = callback.from_user
    await buy_mystery(callback.message)
    await callback.answer()

# === ТОПЫ ===
@router.message(Command("topall"))
async def show_top_all(message: Message):
    with sqlite3.connect(DB_NAME) as db:
        cur = db.cursor()
        cur.execute("SELECT user_id, score FROM users ORDER BY score DESC LIMIT 10")
        top = cur.fetchall()

    text = "<b>🏆 Топ игроков (всего):</b>\n"
    for i, (uid, score) in enumerate(top, 1):
        try:
            chat = await bot.get_chat(uid)
            name = chat.full_name
        except Exception:
            name = str(uid)
        mention = f'<a href="tg://user?id={uid}">{name}</a>'
        text += f"{i}. {mention} — {score} очков\n"

    await message.reply(text, parse_mode="HTML")

@router.message(Command("topday"))
async def show_top_day(message: Message):
    today = datetime.utcnow().date().isoformat()
    with sqlite3.connect(DB_NAME) as db:
        cur = db.cursor()
        cur.execute('''
            SELECT user_id, SUM(score) as daily_score
            FROM log
            WHERE DATE(timestamp) = ?
            GROUP BY user_id
            ORDER BY daily_score DESC
            LIMIT 10
        ''', (today,))
        top = cur.fetchall()

    text = "<b>📅 Топ игроков за сегодня:</b>\n"
    for i, (uid, score) in enumerate(top, 1):
        try:
            chat = await bot.get_chat(uid)
            name = chat.full_name
        except Exception:
            name = str(uid)
        mention = f'<a href="tg://user?id={uid}">{name}</a>'
        text += f"{i}. {mention} — {score} очков\n"

    await message.reply(text, parse_mode="HTML")

# === MAIN ===
async def main():
    setup_db()
    dp.include_router(router)

    await bot.set_my_commands([
        BotCommand(command="shop", description="Открыть магазин"),
        BotCommand(command="topday", description="Топ за сегодня"),
        BotCommand(command="topall", description="Топ за всё время"),
    ])

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
