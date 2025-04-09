import logging
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from datetime import datetime, timedelta
import asyncio
import os

# Встановлюємо логування
logging.basicConfig(level=logging.INFO)

# Токен бота
TOKEN = "6623384285:AAHZXQoJogiuw_QxKgQ2dvLQpI3DOgc8LUQ"
ADMIN_IDS = [721421608, 521523585]

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Шляхи до файлів
ENTRIES_FILE = "entries.json"
WHITELIST_FILE = "whitelist.json"

# Завантаження whitelist
if os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "r") as f:
        white_list = json.load(f)
else:
    white_list = ADMIN_IDS.copy()

# Збереження whitelist
def save_whitelist():
    with open(WHITELIST_FILE, "w") as f:
        json.dump(white_list, f)

# Завантаження записів
if os.path.exists(ENTRIES_FILE) and os.path.getsize(ENTRIES_FILE) > 0:
    with open(ENTRIES_FILE, "r") as f:
        user_entries = json.load(f)
else:
    user_entries = {}

# Збереження записів
def save_entries():
    with open(ENTRIES_FILE, "w") as f:
        json.dump(user_entries, f)

# Слоти часу
FULL_TIME_SLOTS = ['7:00-7:30','7:30-8:00','8:00-8:30','8:30-9:00','9:00-9:30','9:30-10:00','10:00-10:30','10:30-11:00','11:00-11:30','11:30-12:00','12:00-12:30','12:30-13:00','13:00-13:30','13:30-14:00','14:00-14:30','14:30-15:00','15:00-15:30','15:30-16:00','16:00-16:30','16:30-17:00','17:00-17:30','17:30-18:00','18:00-18:30','18:30-19:00','19:00-19:30','19:30-20:00']
SHORT_TIME_SLOTS = FULL_TIME_SLOTS[:FULL_TIME_SLOTS.index("18:00-18:30")]

# FSM
class BookingState(StatesGroup):
    choosing_day = State()
    choosing_time = State()
    choosing_cancel = State()

class AdminState(StatesGroup):
    adding_user = State()

# Головне меню
def main_menu(is_admin=False):
    buttons = [
        [KeyboardButton(text="Записатися")],
        [KeyboardButton(text="Скасувати запис")],
        [KeyboardButton(text="Мої записи")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="📋 Всі записи"), KeyboardButton(text="➕ Додати користувача")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id not in white_list:
        await message.answer("Вибач, але ти не маєш доступу до цього бота.")
        return
    await state.clear()
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer("Привіт! Обери дію:", reply_markup=main_menu(is_admin=is_admin))

@dp.message(lambda m: m.text == "➕ Додати користувача")
async def add_user_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Недостатньо прав.")
        return
    await message.answer("Введіть ID користувача, якого додати до whitelist:")
    await state.set_state(AdminState.adding_user)

@dp.message(AdminState.adding_user)
async def process_user_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        if user_id in white_list:
            await message.answer("Користувач вже є у whitelist.")
        else:
            white_list.append(user_id)
            save_whitelist()
            await message.answer(f"Користувача з ID {user_id} додано до whitelist ✅")
    except ValueError:
        await message.answer("Некоректний формат. Введіть числовий ID.")
    await state.clear()

@dp.message(lambda m: m.text == "📋 Всі записи")
async def show_all_entries(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Недостатньо прав.")
        return
    if not user_entries:
        await message.answer("Немає записів.")
        return
    text = "Всі записи:\n"
    for d, lst in user_entries.items():
        for e in lst:
            text += f"{d} о {e['time']} – @{e.get('username', 'невідомо')}\n"
    await message.answer(text)

@dp.message(lambda m: m.text == "Записатися")
async def start_booking(message: Message, state: FSMContext):
    await state.set_state(BookingState.choosing_day)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Сьогодні", callback_data="today"), InlineKeyboardButton(text="Завтра", callback_data="tomorrow")]])
    if datetime.now().weekday() == 3:
        kb.inline_keyboard[0].append(InlineKeyboardButton(text="Субота", callback_data="saturday"))
    await message.answer("Оберіть день:", reply_markup=kb)

@dp.callback_query(lambda c: c.data in ["today", "tomorrow", "saturday"])
async def choose_day(callback: CallbackQuery, state: FSMContext):
    await state.update_data(chosen_day=callback.data)

    if callback.data == "today":
        date = datetime.now()
    elif callback.data == "tomorrow":
        date = datetime.now() + timedelta(days=1)
    elif callback.data == "saturday":
        today = datetime.now()
        days_ahead = 5 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        date = today + timedelta(days=days_ahead)

    date_str = date.strftime("%Y-%m-%d")
    booked_times = [entry["time"] for entry in user_entries.get(date_str, [])]

    slots = SHORT_TIME_SLOTS if date.weekday() in [5, 6] else FULL_TIME_SLOTS

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for t in slots:
        if t in booked_times:
            text = f"❌ {t}"
            cb = "_"
        else:
            text = t
            cb = t
        row.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(row) == 2:
            kb.inline_keyboard.append(row)
            row = []
    if row:
        kb.inline_keyboard.append(row)

    await callback.message.edit_text("Оберіть час:", reply_markup=kb)
    await state.set_state(BookingState.choosing_time)

@dp.callback_query(BookingState.choosing_time)
async def choose_time(callback: CallbackQuery, state: FSMContext):
    time = callback.data
    if time == "_":
        await callback.answer("Цей час вже зайнятий.", show_alert=True)
        return

    data = await state.get_data()
    day = data["chosen_day"]

    if day == "today":
        date = datetime.now()
    elif day == "tomorrow":
        date = datetime.now() + timedelta(days=1)
    elif day == "saturday":
        today = datetime.now()
        days_ahead = 5 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        date = today + timedelta(days=days_ahead)

    date_str = date.strftime("%Y-%m-%d")
    if date_str not in user_entries:
        user_entries[date_str] = []

    user_entries[date_str].append({"id": callback.from_user.id, "username": callback.from_user.username, "time": time})
    save_entries()

    # Спеціальне повідомлення для конкретного користувача
    special_user_id = 990663653
    if callback.from_user.id == special_user_id:
        await callback.message.edit_text(f"🌟 Дякую, пані Світлана за ваш чудесенький запис. Дуже чекаемо на вас: {date_str} о {time}!")
    else:
        await callback.message.edit_text(f"Вас записано на {date_str} о {time}!")

    await state.clear()

@dp.message(lambda m: m.text == "Скасувати запис")
async def cancel_booking(message: Message, state: FSMContext):
    user_id = message.from_user.id
    entries = [(d, e["time"]) for d, lst in user_entries.items() for e in lst if e["id"] == user_id]

    if not entries:
        await message.answer("У вас немає активних записів.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{d} – {t}", callback_data=f"cancel|{d}|{t}")] for d, t in entries])
    await message.answer("Оберіть запис для скасування:", reply_markup=kb)
    await state.set_state(BookingState.choosing_cancel)

@dp.callback_query(BookingState.choosing_cancel)
async def confirm_cancel(callback: CallbackQuery, state: FSMContext):
    _, d, t = callback.data.split("|")
    uid = callback.from_user.id

    user_entries[d] = [e for e in user_entries.get(d, []) if not (e["id"] == uid and e["time"] == t)]
    if not user_entries[d]:
        del user_entries[d]
    save_entries()
    await callback.message.edit_text(f"Запис на {d} о {t} скасовано.")
    await state.clear()

@dp.message(lambda m: m.text == "Мої записи")
async def show_my_entries(message: Message):
    uid = message.from_user.id
    entries = [(d, e["time"]) for d, lst in user_entries.items() for e in lst if e["id"] == uid]

    if not entries:
        await message.answer("У вас немає записів.")
    else:
        text = "Ваші записи:\n" + "\n".join([f"{d} о {t}" for d, t in entries])
        await message.answer(text)

if __name__ == "__main__":
    async def main():
        await dp.start_polling(bot)
    asyncio.run(main())