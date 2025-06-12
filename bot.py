import random
import os, urllib, asyncio, requests
import urllib.parse
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandStart
from dota_heroes import HEROES
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

bot = Bot(token=os.getenv('DOTA2BOT_TOKEN'))
dp = Dispatcher()


class HeroState(StatesGroup):
    waiting_for_hero = State()
    chatting_with_hero = State()

async def get_random_quote(hero_name: str) -> str:
    try:
        hero_name_url = urllib.parse.quote(hero_name.replace(" ", "_"))
        url = f"https://dota2.fandom.com/ru/wiki/{hero_name_url}/Реплики"
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        quotes = soup.select('div.mw-parser-output ul li')
        if not quotes:
            return "Реплики для этого героя не найдены."
        
        # Фильтруем только текстовые реплики, исключая пустые или системные
        valid_quotes = []
        for quote in quotes:
            # Удаляем тег <span> и его содержимое
            for span in quote.find_all('span'):
                span.decompose()  # Удаляет тег <span> и его содержимое
            text = quote.get_text(strip=True)
            if text:  # Проверяем, что текст не пустой
                valid_quotes.append(text)
                
        if not valid_quotes:
            return "Реплики для этого героя не найдены."
        
        # Выбираем случайную реплику
        return random.choice(valid_quotes)
    except requests.RequestException:
        return "Ошибка при загрузке страницы с репликами."
    except Exception:
        return "Произошла ошибка при обработке реплик."

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await message.answer("Привет с каким героем из доты вы хотите пообщаться?")
    await state.set_state(HeroState.waiting_for_hero)
    

@dp.message(HeroState.waiting_for_hero)
async def process_hero_name(message: Message, state: FSMContext):
    hero_name = message.text.strip().title()
    if hero_name not in HEROES:
        await message.answer("Такого героя нет в Dota 2. Попробуй еще раз!")
        return

    await state.update_data(hero=hero_name)
    await state.set_state(HeroState.chatting_with_hero)
    await message.answer(f"Ты выбрал {hero_name}! Теперь пиши что угодно, и {hero_name} ответит.")

@dp.message(HeroState.chatting_with_hero, F.text)
async def send_hero_audio(message: Message, state: FSMContext):
    # Получаем сохраненного героя
    user_data = await state.get_data()
    hero_name = user_data.get('hero')
    
    if not hero_name:
        await message.answer("Сначала выбери героя с помощью /start!")
        await state.set_state(HeroState.waiting_for_hero)
        return
    
    quote = await get_random_quote(hero_name)
    await message.answer(f"{hero_name}: {quote}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

