import os
import logging

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.handler import current_handler
from aiogram.dispatcher.middlewares import BaseMiddleware

from core import guess


TELEGRAM_API_TOKEN = os.environ.get("TELEGRAM_API_TOKEN")


logger = logging.getLogger("bot")


storage = MemoryStorage()


# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_API_TOKEN)
dp = Dispatcher(bot, storage=storage)


class DebugMiddleware(BaseMiddleware):
    async def on_process_message(self, message: types.Message, data: dict):
        """
        This handler is called when dispatcher receives a message

        :param message:
        """
        # Get current handler
        handler = current_handler.get()
        logger.info(f"Call handler: {handler.__name__}")


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


def normalize_letters(letters: str) -> str:
    normalized_letters = "".join(sorted(set((letters.strip().lower()))))
    return normalized_letters


def ru_letters_filter(message: types.Message) -> bool:
    other_letters = set(message.text.lower()) - set(RU_LETTERS)
    return not other_letters


def word_mask_filter(message: types.Message) -> bool:
    if len(message.text) != 5:
        return False

    other_letters = set(message.text.lower()) - set(RU_LETTERS + "*")
    return not other_letters


@dp.message_handler(state="*", commands=["start", "help"])
async def cmd_start_help(message: types.Message, state: FSMContext):
    """
    This handler will be called when user sends `/start` or `/help` command
    """
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("New word", callback_data="new_word"))
    await message.answer(
        "Hi!\nI will help you to guess 5 letters russian word.\n Let's start",
        reply_markup=markup,
    )


@dp.callback_query_handler(text="new_word")
async def new_word_button_callback(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    # Set state
    await WordForm.yes_letters_new.set()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add(SKIP_PHRASE)

    await callback.message.answer("Please enter yes letters:", reply_markup=markup)

    # commit callback
    await callback.answer()


@dp.message_handler(state="*", commands="new")
async def cmd_new(message: types.Message, state: FSMContext):
    """
    Guess a new word
    """
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    # Set state
    await WordForm.yes_letters_new.set()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add(SKIP_PHRASE)

    await message.answer("Please enter yes letters:", reply_markup=markup)


@dp.message_handler(state="*", commands="guess")
async def cmd_guess(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        guess_answer = make_guess_answer(
            guess(
                data.get("yes_letters", ""),
                data.get("no_letters", ""),
                data.get("word_mask", DEFAULT_WORD_MASK),
            )
        )
        await message.answer(guess_answer, reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(state="*", commands="yes_letters")
async def cmd_yes_letters(message: types.Message, state: FSMContext):
    """
    This handler will be called when user sends `/yes_letters` command
    """
    async with state.proxy() as data:
        current_value = data.get("yes_letters") or ""

        await WordForm.yes_letters_add.set()

        await message.answer(
            "Please enter new yes letters:", reply_markup=types.ReplyKeyboardRemove()
        )
        if current_value:
            await message.answer(
                f"Current is `{current_value}`", parse_mode=types.ParseMode.MARKDOWN
            )


@dp.message_handler(state="*", commands="no_letters")
async def cmd_no_letters(message: types.Message, state: FSMContext):
    """
    This handler will be called when user sends `/no_letters` command
    """
    async with state.proxy() as data:
        current_value = data.get("no_letters") or ""

        await WordForm.no_letters_add.set()

        await message.answer(
            "Please enter new no letters:", reply_markup=types.ReplyKeyboardRemove()
        )
        if current_value:
            await message.answer(
                f"Current is `{current_value}`", parse_mode=types.ParseMode.MARKDOWN
            )


@dp.message_handler(state="*", commands="word_mask")
async def cmd_word_mask(message: types.Message, state: FSMContext):
    """
    This handler will be called when user sends `/word_mask` command
    """
    async with state.proxy() as data:
        current_value = data.get("word_mask") or ""

        await WordForm.word_mask.set()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        markup.add(current_value or DEFAULT_WORD_MASK)

        await message.answer("Please enter new word mask:", reply_markup=markup)
        if current_value:

            await message.answer(
                f"Current is `{current_value}`",
                parse_mode=types.ParseMode.MARKDOWN,
                reply_markup=markup,
            )


@dp.message_handler(
    Text(equals=SKIP_PHRASE, ignore_case=True), state=WordForm.yes_letters_new
)
async def skip_process_yes_letters_new(message: types.Message, state: FSMContext):
    """
    Skip process yes letters init
    """
    await WordForm.next()
    await message.answer(
        "Please enter no letters:", reply_markup=types.ReplyKeyboardRemove()
    )


@dp.message_handler(ru_letters_filter, state=WordForm.yes_letters_new)
async def process_yes_letters_new(message: types.Message, state: FSMContext):
    """
    Process yes letters init
    """
    async with state.proxy() as data:
        data["yes_letters"] = normalize_letters(message.text)

    await WordForm.next()
    await message.answer(
        "Please enter no letters:", reply_markup=types.ReplyKeyboardRemove()
    )


@dp.message_handler(ru_letters_filter, state=WordForm.yes_letters_add)
async def process_yes_letters_add(message: types.Message, state: FSMContext):
    """
    Process add yes letters
    """
    async with state.proxy() as data:
        current_value = data.get("yes_letters") or ""
        data["yes_letters"] = normalize_letters(current_value + message.text)

        guess_answer = make_guess_answer(
            guess(
                data.get("yes_letters", ""),
                data.get("no_letters", ""),
                data.get("word_mask", DEFAULT_WORD_MASK),
            )
        )
        await bot.send_message(
            message.chat.id,
            guess_answer,
            reply_markup=types.ReplyKeyboardRemove(),
        )


@dp.message_handler(ru_letters_filter, state=WordForm.no_letters_new)
async def process_no_letters_new(message: types.Message, state: FSMContext):
    """
    Process no letters init
    """
    # Update state and data
    await WordForm.next()
    await state.update_data(no_letters=normalize_letters(message.text))

    # Configure ReplyKeyboardMarkup
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add(DEFAULT_WORD_MASK)

    await message.answer("What is the word mask?", reply_markup=markup)


@dp.message_handler(ru_letters_filter, state=WordForm.no_letters_add)
async def process_no_letters_add(message: types.Message, state: FSMContext):
    """
    Process add no letters
    """
    async with state.proxy() as data:
        current_value = data.get("no_letters") or ""
        data["no_letters"] = normalize_letters(current_value + message.text)

        guess_answer = make_guess_answer(
            guess(
                data.get("yes_letters", ""),
                data.get("no_letters", ""),
                data.get("word_mask", DEFAULT_WORD_MASK),
            )
        )
        await bot.send_message(
            message.chat.id,
            guess_answer,
            reply_markup=types.ReplyKeyboardRemove(),
        )


@dp.message_handler(
    state=[
        WordForm.yes_letters_new,
        WordForm.yes_letters_add,
        WordForm.no_letters_new,
        WordForm.no_letters_add,
    ]
)
async def cyrillic_letters_invalid(message: types.Message, state: FSMContext):
    """
    If cyrillic letters are invalid
    """
    await message.answer("Only cyrillic letters.\nPlease try again")


@dp.message_handler(word_mask_filter, state=WordForm.word_mask)
async def process_word_mask(message: types.Message, state: FSMContext):
    """
    Process word mask
    """
    async with state.proxy() as data:
        data["word_mask"] = message.text.lower()

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
        await bot.send_message(
            message.chat.id,
            guess_answer,
            reply_markup=markup,
        )


@dp.message_handler(state=WordForm.word_mask)
async def word_mask_invalid(message: types.Message, state: FSMContext):
    """
    If word mask is invalid
    """
    async with state.proxy() as data:
        current_value = data.get("word_mask") or ""

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        markup.add(current_value or DEFAULT_WORD_MASK)

        await message.answer(
            "Only cyrillic letters and *, length is 5.\nPlease try again",
            reply_markup=markup,
        )


if __name__ == "__main__":

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    dp.middleware.setup(DebugMiddleware())

    executor.start_polling(dp, skip_updates=True)
