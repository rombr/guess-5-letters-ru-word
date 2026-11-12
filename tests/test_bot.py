import unittest
from unittest.mock import AsyncMock, patch

from aiogram import Bot, types

import bot as app


class BotFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = Bot(token="123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
        self.api = AsyncMock(return_value=True)
        self.api_patch = patch.object(Bot, "__call__", self.api)
        self.api_patch.start()
        self.state = app.dp.fsm.get_context(bot=self.bot, chat_id=42, user_id=42)
        await self.state.clear()
        self.update_id = 0
        app.dp.message.middleware(app.DebugMiddleware())

    async def asyncTearDown(self):
        await self.state.clear()
        self.api_patch.stop()
        await self.bot.session.close()

    async def send(self, text=None, **fields):
        self.update_id += 1
        message = types.Message(
            message_id=self.update_id, date=1,
            chat=types.Chat(id=42, type="private"),
            from_user=types.User(id=42, is_bot=False, first_name="Test"),
            text=text, **fields,
        )
        await app.dp.feed_update(self.bot, types.Update(update_id=self.update_id, message=message))

    def last_text(self):
        return self.api.call_args.args[0].text

    async def test_new_word_and_refinement(self):
        await self.send('/new')
        self.assertEqual(await self.state.get_state(), app.WordForm.yes_letters_new.state)
        self.assertEqual(self.api.call_args.args[0].reply_markup.keyboard[0][0].text, app.SKIP_PHRASE)
        await self.send(' К О ')
        self.assertEqual((await self.state.get_data())['yes_letters'], 'ко')
        self.assertEqual(await self.state.get_state(), app.WordForm.no_letters_new.state)
        await self.send(' Я ')
        self.assertEqual(await self.state.get_state(), app.WordForm.word_mask.state)
        await self.send('К О Ш К А')
        self.assertEqual(self.last_text(), '01) кошка')
        self.assertEqual((await self.state.get_data())['word_mask'], 'кошка')
        await self.send('/guess')
        self.assertEqual(self.last_text(), '01) кошка')
        await self.send('/yes_letters')
        await self.send('Ш')
        self.assertEqual((await self.state.get_data())['yes_letters'], 'кош')
        self.assertEqual(self.last_text(), '01) кошка')
        await self.send('/no_letters')
        await self.send('Э')
        self.assertEqual((await self.state.get_data())['no_letters'], 'эя')
        self.assertEqual(self.last_text(), '01) кошка')
        await self.send('/word_mask')
        await self.send('****')
        self.assertIn('length is 5', self.last_text())
        await self.send('*****')
        self.assertEqual((await self.state.get_data())['word_mask'], '*****')
        await self.send('/help')
        self.assertIsNone(await self.state.get_state())
        self.assertEqual(await self.state.get_data(), {})

    async def test_skip_invalid_and_nontext_messages(self):
        await self.send('/new')
        await self.send('latin')
        self.assertIn('Only cyrillic', self.last_text())
        self.api.reset_mock()
        await self.send(sticker=types.Sticker(file_id='test', file_unique_id='test', type='regular',
                                             width=1, height=1, is_animated=False, is_video=False))
        self.api.assert_not_called()
        await self.send('sKiP->')
        self.assertEqual(await self.state.get_state(), app.WordForm.no_letters_new.state)
        await self.send('я')
        await self.send('abcde')
        self.assertIn('Only cyrillic letters and *', self.last_text())
        await self.send('кошка')
        self.assertEqual(self.last_text(), '01) кошка')
        await self.send('/new')
        self.assertEqual(await self.state.get_data(), {})

    async def test_inline_new_word_button(self):
        await self.send('/start')
        self.assertEqual(self.api.call_args.args[0].reply_markup.inline_keyboard[0][0].callback_data, 'new_word')
        callback = types.CallbackQuery(
            id='test-callback', from_user=types.User(id=42, is_bot=False, first_name='Test'),
            chat_instance='test', data='new_word',
            message=types.Message(message_id=1, date=1, chat=types.Chat(id=42, type='private')),
        )
        await app.dp.feed_update(self.bot, types.Update(update_id=100, callback_query=callback))
        self.assertEqual(await self.state.get_state(), app.WordForm.yes_letters_new.state)
        self.assertEqual(self.api.call_args.args[0].__api_method__, 'answerCallbackQuery')

    async def test_guess_without_clues_fits_telegram_limit(self):
        await self.send('/guess')
        self.assertLessEqual(len(self.last_text()), 4096)
        self.assertIn('..........', self.last_text())


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_polling_drops_pending_updates(self):
        with patch.dict('os.environ', {'TELEGRAM_API_TOKEN': '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi'}), \
                patch.object(Bot, 'delete_webhook', new_callable=AsyncMock) as delete, \
                patch.object(app.dp, 'start_polling', new_callable=AsyncMock) as polling:
            await app.main()
            delete.assert_awaited_once_with(drop_pending_updates=True)
            polling.assert_awaited_once()

    async def test_missing_token_has_clear_error(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'TELEGRAM_API_TOKEN'):
                await app.main()
