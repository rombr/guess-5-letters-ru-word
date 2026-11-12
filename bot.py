import asyncio
import os
import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from core import guess


logger = logging.getLogger("bot")

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class DebugMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        registered_handler = data.get("handler")
        if registered_handler:
            logger.info("Call handler: %s", registered_handler.callback.__name__)
        return await handler(event, data)


# States
class WordForm(StatesGroup):
    yes_letters_new = State()
    no_letters_new = State()
    word_mask = State()
    yes_letters_add = State()
    no_letters_add = State()


RU_LETTERS = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
DEFAULT_WORD_MASK = "*" * 5
SKIP_PHRASE = "Skip->"


def reply_keyboard(text: str) -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=text)]],
        resize_keyboard=True,
        selective=True,
    )


def make_guess_answer(message: str) -> str:
    """Format guess result"""
    if not message:
        return "Sorry, I can not find words..."
    if len(message) <= 4096:
        return message

    lines = message.split("\n")
    # Index was calculated manually
    first_lines = lines[:379]
    last_line = lines[-1]
    splitter = "." * 10
    formatted_message = "\n".join(first_lines + [splitter, last_line])
    return formatted_message


def normalize_input(text: str) -> str:
    """Remove whitespace and lowercase user-entered letters or word masks."""
    return "".join(text.split()).lower()


def normalize_letters(letters: str) -> str:
    normalized_letters = "".join(sorted(set(normalize_input(letters))))
    return normalized_letters


def ru_letters_filter(message: types.Message) -> bool:
    letters = normalize_input(message.text or "")
    other_letters = set(letters) - set(RU_LETTERS)
    return bool(letters) and not other_letters


def word_mask_filter(message: types.Message) -> bool:
    word_mask = normalize_input(message.text or "")
    if len(word_mask) != 5:
        return False

    other_letters = set(word_mask) - set(RU_LETTERS + "*")
    return not other_letters


@dp.message(F.text, Command("start", "help"))
async def cmd_start_help(message: types.Message, state: FSMContext):
    """
    This handler will be called when user sends `/start` or `/help` command
    """
    current_state = await state.get_state()
    if current_state:
        await state.clear()

    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text="New word", callback_data="new_word")]]
    )
    await message.answer(
        "Hi!\nI will help you to guess 5 letters russian word.\n Let's start",
        reply_markup=markup,
    )


@dp.callback_query(StateFilter(None), F.data == "new_word")
async def new_word_button_callback(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()

    # Set state
    await state.set_state(WordForm.yes_letters_new)

    markup = reply_keyboard(SKIP_PHRASE)

    if isinstance(callback.message, types.Message):
        await callback.message.answer("Please enter yes letters:", reply_markup=markup)

    # commit callback
    await callback.answer()


@dp.message(F.text, Command("new"))
async def cmd_new(message: types.Message, state: FSMContext):
    """
    Guess a new word
    """
    current_state = await state.get_state()
    if current_state:
        await state.clear()

    # Set state
    await state.set_state(WordForm.yes_letters_new)

    markup = reply_keyboard(SKIP_PHRASE)

    await message.answer("Please enter yes letters:", reply_markup=markup)


@dp.message(F.text, Command("guess"))
async def cmd_guess(message: types.Message, state: FSMContext):
    data = await state.get_data()
    guess_answer = make_guess_answer(
        guess(
            data.get("yes_letters", ""),
            data.get("no_letters", ""),
            data.get("word_mask", DEFAULT_WORD_MASK),
        )
    )
    await message.answer(guess_answer, reply_markup=types.ReplyKeyboardRemove())


@dp.message(F.text, Command("yes_letters"))
async def cmd_yes_letters(message: types.Message, state: FSMContext):
    """
    This handler will be called when user sends `/yes_letters` command
    """
    data = await state.get_data()
    current_value = data.get("yes_letters") or ""

    await state.set_state(WordForm.yes_letters_add)

    await message.answer(
        "Please enter new yes letters:", reply_markup=types.ReplyKeyboardRemove()
    )
    if current_value:
        await message.answer(
            f"Current is `{current_value}`", parse_mode=ParseMode.MARKDOWN
        )


@dp.message(F.text, Command("no_letters"))
async def cmd_no_letters(message: types.Message, state: FSMContext):
    """
    This handler will be called when user sends `/no_letters` command
    """
    data = await state.get_data()
    current_value = data.get("no_letters") or ""

    await state.set_state(WordForm.no_letters_add)

    await message.answer(
        "Please enter new no letters:", reply_markup=types.ReplyKeyboardRemove()
    )
    if current_value:
        await message.answer(
            f"Current is `{current_value}`", parse_mode=ParseMode.MARKDOWN
        )


@dp.message(F.text, Command("word_mask"))
async def cmd_word_mask(message: types.Message, state: FSMContext):
    """
    This handler will be called when user sends `/word_mask` command
    """
    data = await state.get_data()
    current_value = data.get("word_mask") or ""

    await state.set_state(WordForm.word_mask)

    markup = reply_keyboard(current_value or DEFAULT_WORD_MASK)

    await message.answer("Please enter new word mask:", reply_markup=markup)
    if current_value:

        await message.answer(
            f"Current is `{current_value}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )


@dp.message(
    WordForm.yes_letters_new, F.text.casefold() == SKIP_PHRASE.casefold()
)
async def skip_process_yes_letters_new(message: types.Message, state: FSMContext):
    """
    Skip process yes letters init
    """
    await state.set_state(WordForm.no_letters_new)
    await message.answer(
        "Please enter no letters:", reply_markup=types.ReplyKeyboardRemove()
    )


@dp.message(WordForm.yes_letters_new, F.text, ru_letters_filter)
async def process_yes_letters_new(message: types.Message, state: FSMContext):
    """
    Process yes letters init
    """
    data = await state.get_data()
    data["yes_letters"] = normalize_letters(message.text)
    await state.update_data(yes_letters=data["yes_letters"])

    await state.set_state(WordForm.no_letters_new)
    await message.answer(
        "Please enter no letters:", reply_markup=types.ReplyKeyboardRemove()
    )


@dp.message(WordForm.yes_letters_add, F.text, ru_letters_filter)
async def process_yes_letters_add(message: types.Message, state: FSMContext):
    """
    Process add yes letters
    """
    data = await state.get_data()
    current_value = data.get("yes_letters") or ""
    data["yes_letters"] = normalize_letters(current_value + message.text)
    await state.update_data(yes_letters=data["yes_letters"])

    guess_answer = make_guess_answer(
        guess(
            data.get("yes_letters", ""),
            data.get("no_letters", ""),
            data.get("word_mask", DEFAULT_WORD_MASK),
        )
    )
    await message.answer(
        guess_answer,
        reply_markup=types.ReplyKeyboardRemove(),
    )


@dp.message(WordForm.no_letters_new, F.text, ru_letters_filter)
async def process_no_letters_new(message: types.Message, state: FSMContext):
    """
    Process no letters init
    """
    # Update state and data
    await state.set_state(WordForm.word_mask)
    await state.update_data(no_letters=normalize_letters(message.text))

    # Configure ReplyKeyboardMarkup
    markup = reply_keyboard(DEFAULT_WORD_MASK)

    await message.answer("What is the word mask?", reply_markup=markup)


@dp.message(WordForm.no_letters_add, F.text, ru_letters_filter)
async def process_no_letters_add(message: types.Message, state: FSMContext):
    """
    Process add no letters
    """
    data = await state.get_data()
    current_value = data.get("no_letters") or ""
    data["no_letters"] = normalize_letters(current_value + message.text)
    await state.update_data(no_letters=data["no_letters"])

    guess_answer = make_guess_answer(
        guess(
            data.get("yes_letters", ""),
            data.get("no_letters", ""),
            data.get("word_mask", DEFAULT_WORD_MASK),
        )
    )
    await message.answer(
        guess_answer,
        reply_markup=types.ReplyKeyboardRemove(),
    )


@dp.message(
    F.text,
    StateFilter(
        WordForm.yes_letters_new,
        WordForm.yes_letters_add,
        WordForm.no_letters_new,
        WordForm.no_letters_add,
    )
)
async def cyrillic_letters_invalid(message: types.Message, state: FSMContext):
    """
    If cyrillic letters are invalid
    """
    await message.answer("Only cyrillic letters.\nPlease try again")


@dp.message(WordForm.word_mask, F.text, word_mask_filter)
async def process_word_mask(message: types.Message, state: FSMContext):
    """
    Process word mask
    """
    data = await state.get_data()
    data["word_mask"] = normalize_input(message.text or "")
    await state.update_data(word_mask=data["word_mask"])

    # Remove keyboard
    markup = types.ReplyKeyboardRemove()

    guess_answer = make_guess_answer(
        guess(
            data.get("yes_letters", ""),
            data.get("no_letters", ""),
            data.get("word_mask", DEFAULT_WORD_MASK),
        )
    )
    # And send message
    await message.answer(
        guess_answer,
        reply_markup=markup,
    )


@dp.message(WordForm.word_mask, F.text)
async def word_mask_invalid(message: types.Message, state: FSMContext):
    """
    If word mask is invalid
    """
    data = await state.get_data()
    current_value = data.get("word_mask") or ""

    markup = reply_keyboard(current_value or DEFAULT_WORD_MASK)

    await message.answer(
        "Only cyrillic letters and *, length is 5.\nPlease try again",
        reply_markup=markup,
    )


async def main():
    token = os.environ.get("TELEGRAM_API_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_API_TOKEN before starting the bot")

    logging.basicConfig(level=logging.INFO)
    dp.message.middleware(DebugMiddleware())
    async with Bot(token=token) as bot:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
