import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from openai import AsyncOpenAI

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
ai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Состояния для диалога
class CharCreation(StatesGroup):
    waiting_for_description = State()

# Это и есть то самое "переопределение пути", о котором они просят
ai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.proxyapi.ru/openai/v1" 
)

# Системный промпт для "мозга" бота
SYSTEM_PROMPT = (
    "Ты — мой соавтор и творческий напарник. Мы вместе пишем историю. "
    "Общайся со мной на 'ты', будь прямолинейным и профессиональным. "
    "Не говори о пользователе в третьем лице.\n\n"
    "Твоя задача — препарировать присланного мной персонажа по этой схеме:\n"
    "1. **Внутренний изъян героя**: Найди скрытую слабость или травму, которую он прячет за маской. Опиши это как факт о персонаже.\n"
    "2. **Главный конфликт**: Укажи на противоречие между тем, чего он хочет, и тем, что ему реально нужно.\n"
    "3. **Мой совет тебе**: Предложи мне (автору) конкретный и дерзкий способ, как этот изъян может взорвать сюжет в кульминации.\n"
    "Пиши без лишних вступлений, сразу к делу."
)

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = [
        [types.InlineKeyboardButton(text="✨ Создать Генезис", callback_data="create_char")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    await message.answer("Привет! Я Muse Processor. Готов препарировать твоего героя. Начнем?", reply_markup=markup)

@dp.callback_query(F.data == "create_char")
async def start_creation(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Опиши своего персонажа. Как его видит читатель? (Его имя, роль, манера поведения)")
    await state.set_state(CharCreation.waiting_for_description)

@dp.message(CharCreation.waiting_for_description)
async def analyze_character(message: types.Message, state: FSMContext):
    await message.answer("🔍 Анализирую психологический профиль...")
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.85, # Чуть выше среднего для нестандартных идей
            max_tokens=800
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        await message.answer(f"Ошибка нейросети: {e}")
    
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())