import os
import sqlite3
import logging
import asyncio
from collections import defaultdict
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import AsyncOpenAI

# 1. НАСТРОЙКИ
load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())
ai_client = AsyncOpenAI(
    api_key=os.getenv("PROXYAPI_KEY"),
    base_url="https://api.proxyapi.ru/openai/v1"
)

# Память диалогов (RAM)
user_history = defaultdict(list)

# 2. БАЗА ДАННЫХ
def init_db():
    conn = sqlite3.connect("muse_bot.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS characters 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                       char_name TEXT, description TEXT, analysis TEXT)''')
    conn.commit()
    conn.close()

init_db()

# 3. ЕДИНЫЙ СИСТЕМНЫЙ ПРОМПТ
SYSTEM_PROMPT = (
    "Ты — Muse Processor 🌟, профессиональный соавтор. Твой стиль сочетает конструктивную критику и менторскую поддержку. "
    "Если автор пишет не по делу (приветствия, смолл-ток) — отвечай кратко и дружелюбно. "
    "Если автор описывает идею или героя — давай глубокий, аргументированный анализ. "
    "Используй Markdown для красоты: **жирный текст**, линии '---' и эмодзи. "
    "Будь честным: находи слабые места, но сразу предлагай, как их усилить."
)

# 4. ОБРАБОТЧИКИ КОМАНД И КНОПОК МЕНЮ

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = [
        [types.KeyboardButton(text="📚 Мои герои")],
        [types.KeyboardButton(text="🧹 Очистить память диалога")]
    ]
    markup = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "✨ **Muse Processor готов.**\n\n"
        "Просто начни описывать своего персонажа или сюжетный поворот. "
        "Я проанализирую твою идею и автоматически сохраню её в твою библиотеку.",
        reply_markup=markup, parse_mode="Markdown"
    )

# ВАЖНО: Этот обработчик ДОЛЖЕН идти раньше нейросети
@dp.message(F.text == "🧹 Очистить память диалога")
async def clear_mem(message: types.Message):
    user_id = message.from_user.id
    user_history[user_id] = [] # Программная очистка
    await message.answer("🧼 **Память текущего диалога очищена.**\n\nЯ готов слушать новые идеи с чистого листа!", parse_mode="Markdown")

@dp.message(F.text == "📚 Мои герои")
async def show_library(message: types.Message):
    conn = sqlite3.connect("muse_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, char_name FROM characters WHERE user_id = ? ORDER BY id DESC LIMIT 15", (message.from_user.id,))
    chars = cursor.fetchall()
    conn.close()
    
    if not chars:
        await message.answer("📭 Твоя библиотека пока пуста. Опиши мне своего первого героя!")
        return
        
    builder = InlineKeyboardBuilder()
    for c_id, name in chars:
        builder.row(types.InlineKeyboardButton(text=f"👤 {name}", callback_data=f"view_{c_id}"))
    await message.answer("📑 **Твоя творческая библиотека:**", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_"))
async def view_char(callback: types.CallbackQuery):
    char_id = callback.data.split("_")[1]
    conn = sqlite3.connect("muse_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT char_name, analysis FROM characters WHERE id = ?", (char_id,))
    char = cursor.fetchone()
    conn.close()
    
    if char:
        name, analysis = char
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🖼 Визуализировать", callback_data=f"draw_{char_id}"))
        
        text = f"👤 **ПЕРСОНАЖ: {name}**\n\n--- \n\n{analysis}"
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("draw_"))
async def draw_character(callback: types.CallbackQuery):
    char_id = callback.data.split("_")[1]
    await callback.answer("🎨 Создаю визуальный образ...")
    
    conn = sqlite3.connect("muse_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT description FROM characters WHERE id = ?", (char_id,))
    char_data = cursor.fetchone()
    conn.close()

    if char_data:
        try:
            # Промпт для генерации
            prompt = f"Cinematic character concept art, professional lighting, digital art style: {char_data[0]}"
            response = await ai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            image_url = response.data[0].url
            await callback.message.answer_photo(photo=image_url, caption=f"✨ Визуальное воплощение твоего героя.")
        except Exception as e:
            logging.error(f"DALL-E Error: {e}")
            await callback.message.answer("⚠️ Не удалось создать изображение. Попробуй изменить описание.")

# 5. ГЛАВНЫЙ ИНТЕЛЛЕКТУАЛЬНЫЙ ОБРАБОТЧИК
# Он стоит В САМОМ КОНЦЕ, чтобы не перехватывать команды и кнопки
@dp.message(F.text & ~F.text.startswith("/"))
async def global_chat_handler(message: types.Message):
    user_id = message.from_user.id
    
    # Добавляем сообщение автора в память
    user_history[user_id].append({"role": "user", "content": f"АВТОР: {message.text}"})
    if len(user_history[user_id]) > 15:
        user_history[user_id] = user_history[user_id][-15:]

    await bot.send_chat_action(message.chat.id, "typing")
    
    # Инструкция для ИИ по сохранению героев
    save_instr = (
        "\nЕсли в этом сообщении автор описывает НОВОГО персонажа, "
        "начни свой ответ строго с префикса '[SAVE: Имя Персонажа]'. "
        "В остальном — будь мудрым соавтором с красивым форматированием."
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT + save_instr}] + user_history[user_id]

    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=messages, 
            temperature=0.7
        )
        answer = response.choices[0].message.content

        # Логика автосохранения в базу
        if "[SAVE:" in answer:
            tag_end = answer.find("]")
            char_name = answer[6:tag_end].strip()
            clean_answer = answer[tag_end+1:].strip()
            
            conn = sqlite3.connect("muse_bot.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO characters (user_id, char_name, description, analysis) VALUES (?,?,?,?)",
                           (user_id, char_name, message.text, clean_answer))
            conn.commit()
            conn.close()
            answer = clean_answer

        user_history[user_id].append({"role": "assistant", "content": answer})
        await message.answer(answer, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"AI Error: {e}")
        await message.answer("❌ Нейросеть взяла паузу. Попробуй отправить сообщение еще раз.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())