import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Загружаем переменные
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="👤 Мои Персонажи", callback_data="my_chars"))
    builder.row(types.InlineKeyboardButton(text="✨ Создать Генезис", callback_data="create_char"))
    return builder.as_markup()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет, автор! Я — Muse Processor.\nВыбирай действие:",
        reply_markup=main_menu()
    )

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())