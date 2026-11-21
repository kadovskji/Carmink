"""The real `IO` of the engine: Telegram messages through python-telegram-bot, timers through JobQueue."""
import logging
import time
from typing import Awaitable, Callable

from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, InputFile, InputMediaPhoto,
                      ReplyParameters)
from telegram.error import TelegramError
from telegram.ext import Application

LOG = logging.getLogger("carmink.tg")


class TelegramIO:
    def __init__(self, app: Application) -> None:
        self.app = app

    def now(self) -> float:
        return time.time()

    async def send(self, chat_id, text, buttons=None, reply_to=None):
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(label, url=url)]
                                       for label, url in buttons]) if buttons else None
        reply = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True) \
            if reply_to else None
        try:
            msg = await self.app.bot.send_message(chat_id, text, parse_mode="HTML",
                                                  reply_markup=markup, reply_parameters=reply)
            return msg.message_id
        except TelegramError as e:
            LOG.warning("send_message to %s failed: %s", chat_id, e)
            return None

    @staticmethod
    def _markup(buttons):
        return InlineKeyboardMarkup([[InlineKeyboardButton(label, url=url)]
                                     for label, url in buttons]) if buttons else None

    async def send_dm(self, user_id, text, buttons=None) -> bool:
        """A private message; False if the user never started the bot (or blocked it)."""
        try:
            await self.app.bot.send_message(user_id, text, parse_mode="HTML",
                                            reply_markup=self._markup(buttons))
            return True
        except TelegramError as e:
            LOG.info("private message to %s failed: %s", user_id, e)
            return False

    async def send_photo_dm(self, user_id, jpeg, caption) -> bool:
        try:
            await self.app.bot.send_photo(user_id, photo=jpeg, caption=caption, parse_mode="HTML")
            return True
        except TelegramError as e:
            LOG.info("private photo to %s failed: %s", user_id, e)
            return False

    async def send_animation(self, chat_id, data, caption):
        try:
            msg = await self.app.bot.send_animation(
                chat_id, animation=InputFile(data, filename="broken-canva.gif"),
                caption=caption, parse_mode="HTML")
            return msg.message_id
        except TelegramError as e:
            LOG.warning("send_animation to %s failed: %s", chat_id, e)
            return None

    async def edit_text(self, chat_id, message_id, text, buttons=None):
        try:
            await self.app.bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                                 parse_mode="HTML",
                                                 reply_markup=self._markup(buttons))
        except TelegramError as e:      # "message is not modified", flood limits...
            LOG.info("edit of message %s in %s skipped: %s", message_id, chat_id, e)

    async def send_photo(self, chat_id, jpeg, caption):
        try:
            msg = await self.app.bot.send_photo(chat_id, photo=jpeg, caption=caption,
                                                parse_mode="HTML")
            return msg.message_id
        except TelegramError as e:
            LOG.warning("send_photo to %s failed: %s", chat_id, e)
            return None

    async def edit_photo(self, chat_id, message_id, jpeg, caption):
        try:
            if jpeg:
                media = InputMediaPhoto(media=jpeg, caption=caption, parse_mode="HTML")
                await self.app.bot.edit_message_media(chat_id=chat_id, message_id=message_id,
                                                      media=media)
            else:
                await self.app.bot.edit_message_caption(chat_id=chat_id, message_id=message_id,
                                                        caption=caption, parse_mode="HTML")
        except TelegramError as e:      # "message is not modified", flood limits...
            LOG.info("edit of message %s in %s skipped: %s", message_id, chat_id, e)

    async def delete(self, chat_id, message_id):
        try:
            await self.app.bot.delete_message(chat_id, message_id)
        except TelegramError as e:      # the bot is not an admin with "delete messages"
            LOG.info("could not delete message %s in %s: %s", message_id, chat_id, e)

    async def is_admin(self, chat_id, user_id):
        try:
            member = await self.app.bot.get_chat_member(chat_id, user_id)
        except TelegramError:
            return False
        return member.status in ("administrator", "creator")

    def schedule(self, name: str, delay: float, fn: Callable[[], Awaitable[None]]) -> None:
        for job in self.app.job_queue.get_jobs_by_name(name):
            job.schedule_removal()

        async def run(context) -> None:
            await fn()
        self.app.job_queue.run_once(run, max(0.0, delay), name=name)

    def cancel(self, prefix: str) -> None:
        for job in self.app.job_queue.jobs():
            if job.name and job.name.startswith(prefix):
                job.schedule_removal()
