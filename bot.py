import random
import os
import urllib.parse
import asyncio
import requests
import logging
import aiohttp
import re
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandStart
from dotenv import load_dotenv, find_dotenv
from functools import lru_cache
from dota_heroes import HEROES

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(find_dotenv())

bot = Bot(token=os.getenv('DOTA2BOT_TOKEN'))
dp = Dispatcher()

# Популярные герои для быстрого выбора
POPULAR_HEROES = ["Pudge", "Invoker", "Sniper", "Lina", "Shadow Fiend"]

DESIRED_CATEGORIES = [
    "Появление", "Передвижение", "Атака", "Убийство", "Смерть", "Покупка предмета",
    "Добивание", "Воскрешение", "Встреча с союзником", "Встреча с врагом", "Смех",
    "Благодарность", "Провокация", "Начало боя", "Победа", "Поражение"
]

# Кэширование реплик для оптимизации
# Регулярное выражение для фильтрации звуков
SOUND_PATTERN = re.compile(r'^[УХЫАМРКФНТ]{1,3}[!]$', re.IGNORECASE)

async def keep_alive():
    url = 'https://dota-chat-bot.onrender.com/'
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as response:
                    logger.info(f"Ping: {response.status}")
            except Exception as e:
                logger.error(f"Ping error: {e}")
            await asyncio.sleep(1000)





@lru_cache(maxsize=100)
def get_cached_quotes(hero_name: str) -> tuple:
    try:
        hero_name_url = hero_name.replace(" ", "_")
        url = f"https://dota2.fandom.com/ru/wiki/{hero_name_url}/Реплики"
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.select_one('div.mw-parser-output')
        if not content:
            return ("Реплики для этого героя не найдены.",)

        valid_quotes = []
        current_category = None

        # Проходим по всем элементам в контенте
        for element in content.find_all(['h2', 'h3', 'ul'], recursive=False):
            if element.name in ['h2', 'h3']:
                # Обновляем категорию
                category_span = element.find('span', class_='mw-headline')
                current_category = category_span.get_text(strip=True) if category_span else None
            elif element.name == 'ul' and current_category:
                # Проверяем, входит ли категория в желаемые
                if current_category in DESIRED_CATEGORIES:
                    quotes = element.find_all('li', recursive=False)
                    for quote in quotes:
                        # Удаляем элементы <span> (аудио и другие)
                        for span in quote.find_all('span'):
                            span.decompose()
                        text = quote.get_text(strip=True)

                        # Упрощенная фильтрация
                        if not text or len(text) < 3:  # Минимальная длина уменьшена
                            continue
                        if SOUND_PATTERN.match(text):  # Фильтр только для явных звуков
                            continue

                        valid_quotes.append(text)

        return tuple(valid_quotes) if valid_quotes else ("Реплики для этого героя не найдены.",)
    except Exception as e:
        return (f"Ошибка: {str(e)}",)

async def get_random_quote(hero_name: str) -> str:
    quotes = get_cached_quotes(hero_name)
    return random.choice(quotes) if len(quotes) > 1 or quotes[0].startswith("Реплики") else quotes[0]

# Создание клавиатуры
def get_hero_keyboard():
    keyboard = ReplyKeyboardBuilder()
    for hero in POPULAR_HEROES:
        keyboard.button(text=hero)
    keyboard.button(text="Список всех героев")
    keyboard.button(text="Случайная реплика")
    keyboard.adjust(5)
    return keyboard.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_control_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="/changehero")],
                                              [KeyboardButton(text="/info")], 
                                              [KeyboardButton(text="/stop")]], 
                                              resize_keyboard=True)
    return keyboard

class HeroState(StatesGroup):
    waiting_for_hero = State()
    chatting_with_hero = State()

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await message.answer(
        "👋 Привет! Я бот, который поможет тебе пообщаться с героями Dota 2! "
        "Выбери героя или используй команду /random для случайной реплики.",
        parse_mode="Markdown",
        reply_markup=get_hero_keyboard()
    )
    await state.set_state(HeroState.waiting_for_hero)

@dp.message(Command(commands=["random", "Случайная реплика"]))
async def random_quote(message: Message):
    hero_name = random.choice(HEROES)
    quote = await get_random_quote(hero_name)
    await message.answer(f"*{hero_name}*: {quote}", parse_mode="Markdown")

@dp.message(Command("changehero"))
async def change_hero(message: Message, state: FSMContext):
    await message.answer(
        "Выбери нового героя:",
        parse_mode="Markdown",
        reply_markup=get_hero_keyboard()
    )
    await state.set_state(HeroState.waiting_for_hero)

@dp.message(Command("info"))
async def hero_info(message: Message, state: FSMContext):
    user_data = await state.get_data()
    hero_name = user_data.get('hero')
    if not hero_name:
        await message.answer("Сначала выбери героя с помощью /start или /changehero!")
        return
    
    hero_name_url = urllib.parse.quote(hero_name.replace(" ", "_"))
    url = f"https://dota2.fandom.com/ru/wiki/{hero_name_url}"
    await message.answer(
        f"📖 Подробная информация о *{hero_name}*: [перейти на страницу героя]({url})",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@dp.message(Command("stop"))
async def stop_chat(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Чат с героем завершен. Начни заново с /start!",
        parse_mode="Markdown",
        reply_markup=None
    )

@dp.message(HeroState.waiting_for_hero, F.text == "Список всех героев")
async def show_all_heroes(message: Message, state: FSMContext):
    heroes_list = "\n".join(HEROES)
    await message.answer(
        f"📜 Список всех героев Dota 2:\n{heroes_list}\n\nВыбери героя или напиши его имя:",
        parse_mode="Markdown",
        reply_markup=get_hero_keyboard()
    )

@dp.message(HeroState.waiting_for_hero)
async def process_hero_name(message: Message, state: FSMContext):
    hero_name = message.text.strip().title()
    if hero_name not in HEROES:
        await message.answer(
            "❌ Такого героя нет в Dota 2. Попробуй еще раз или выбери из списка!",
            parse_mode="Markdown",
            reply_markup=get_hero_keyboard()
        )
        return

    await state.update_data(hero=hero_name)
    await state.set_state(HeroState.chatting_with_hero)
    await message.answer(
        f"🎮 Ты выбрал *{hero_name}*! Пиши что угодно, и {hero_name} ответит.\n"
        f"Команды: /changehero, /info, /stop",
        parse_mode="Markdown",
        reply_markup=get_control_keyboard()
    )

@dp.message(HeroState.chatting_with_hero, F.text)
async def send_hero_quote(message: Message, state: FSMContext):
    user_data = await state.get_data()
    hero_name = user_data.get('hero')
    
    if not hero_name:
        await message.answer(
            "❌ Сначала выбери героя с помощью /start или /changehero!",
            parse_mode="Markdown",
            reply_markup=get_hero_keyboard()
        )
        await state.set_state(HeroState.waiting_for_hero)
        return
    
    quote = await get_random_quote(hero_name)
    await message.answer(
        f"*{hero_name}*: {quote}",
        parse_mode="Markdown",
        reply_markup=get_control_keyboard()
    )

async def main():
    asyncio.create_task(keep_alive())
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.delete_my_commands()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
