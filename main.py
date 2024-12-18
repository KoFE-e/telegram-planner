from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import asyncio
import os
import sqlite3
import pytz

# Set timezone to Moscow
tz_moscow = pytz.timezone('Europe/Moscow')

# Telegram Bot API Token
API_TOKEN = os.getenv('TELEGRAM_BOT_API_TOKEN')
if not API_TOKEN:
    raise ValueError("Переменная окружения TELEGRAM_BOT_API_TOKEN не установлена.")

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()

# Initialize SQLite database
conn = sqlite3.connect("schedule.db")
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    user_id INTEGER,
    task TEXT,
    time TEXT
)
''')
conn.commit()

# Create keyboard
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("Добавить задачу"))
keyboard.add(KeyboardButton("Список задач"))
keyboard.add(KeyboardButton("Удалить задачу"))

def add_task(user_id, task, time):
    c.execute("INSERT INTO tasks (user_id, task, time) VALUES (?, ?, ?)", (user_id, task, time.isoformat()))
    conn.commit()
    scheduler.add_job(
        send_task_notification,
        trigger=DateTrigger(run_date=time),
        args=[user_id, task],
        id=f"{user_id}_{task}_{time.isoformat()}"
    )

def remove_task(user_id, task):
    c.execute("DELETE FROM tasks WHERE user_id = ? AND task = ?", (user_id, task))
    conn.commit()
    for job in scheduler.get_jobs():
        if job.id.startswith(f"{user_id}_{task}"):
            scheduler.remove_job(job.id)

def list_tasks(user_id):
    c.execute("SELECT task, time FROM tasks WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    return [{"task": row[0], "time": datetime.fromisoformat(row[1]).astimezone(tz_moscow)} for row in rows]

async def send_task_notification(user_id, task):
    await bot.send_message(user_id, f"Напоминание: {task}")

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply(
        "Привет! Я помогу тебе составить расписание.\n\n"
        "Команды:\n"
        "/add <дата в формате ГГГГ-ММ-ДД ЧЧ:ММ> <дело> - добавить дело\n"
        "/list - показать список дел\n"
        "/remove <дело> - удалить дело",
        reply_markup=keyboard
    )

@dp.message_handler(lambda message: message.text == "Добавить задачу")
async def prompt_add_task(message: types.Message):
    await message.reply("Введите задачу в формате: <дата в формате ГГГГ-ММ-ДД ЧЧ:ММ> <дело>")

@dp.message_handler(lambda message: message.text == "Список задач")
async def list_schedule_menu(message: types.Message):
    tasks = list_tasks(message.from_user.id)
    if not tasks:
        await message.reply("Ваш список дел пуст.")
    else:
        reply = "Ваши дела:\n"
        for t in tasks:
            reply += f"{t['time'].strftime('%Y-%m-%d %H:%M')} - {t['task']}\n"
        await message.reply(reply)

@dp.message_handler(lambda message: message.text == "Удалить задачу")
async def prompt_remove_task(message: types.Message):
    await message.reply("Введите название задачи для удаления.")

@dp.message_handler(commands=['add'])
async def add_schedule(message: types.Message):
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 3:
            await message.reply("Неверный формат. Используйте: /add <дата в формате ГГГГ-ММ-ДД ЧЧ:ММ> <дело>")
            return
        datetime_str, task = parts[1] + ' ' + parts[2], parts[3]
        try:
            naive_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            time = tz_moscow.localize(naive_time)
        except ValueError:
            await message.reply("Неверный формат даты. Используйте: ГГГГ-ММ-ДД ЧЧ:ММ")
            return
        if time < datetime.now(tz=tz_moscow):
            await message.reply("Нельзя добавить задачу на прошедшее время.")
            return
        add_task(message.from_user.id, task, time)
        await message.reply(f"Дело '{task}' добавлено на {time.strftime('%Y-%m-%d %H:%M')}.")
    except Exception as e:
        await message.reply(f"Произошла ошибка: {str(e)}")

@dp.message_handler(commands=['list'])
async def list_schedule(message: types.Message):
    tasks = list_tasks(message.from_user.id)
    if not tasks:
        await message.reply("Ваш список дел пуст.")
    else:
        reply = "Ваши дела:\n"
        for t in tasks:
            reply += f"{t['time'].strftime('%Y-%m-%d %H:%M')} - {t['task']}\n"
        await message.reply(reply)

@dp.message_handler(commands=['remove'])
async def remove_schedule(message: types.Message):
    try:
        task = message.text.split(maxsplit=1)[1]
        remove_task(message.from_user.id, task)
        await message.reply(f"Дело '{task}' удалено.")
    except IndexError:
        await message.reply("Используйте формат: /remove <дело>")

if __name__ == '__main__':
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)
