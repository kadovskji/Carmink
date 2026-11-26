"""The group dictionary page of the Mini App: list, add, edit, delete, export, import, share codes.

Every method checks that the caller may edit the dictionary (see `dict_guard`) and reports problems as GameError."""
import json

import config
import dictio
import words
from errors import GameError


class DictMixin:
    async def dict_guard(self, chat_id: int, uid: int) -> None:
        """Group admins (or every member, if the group chose so) and the bot's owners."""
        if chat_id > 0:
            raise GameError("not_allowed")
        if uid in config.ADMIN_IDS:
            return
        if self.db.get_settings(chat_id)["words"] == "everyone":
            ok = await self.io.is_member(chat_id, uid)
        else:
            ok = await self.io.is_admin(chat_id, uid)
        if not ok:
            raise GameError("not_allowed")

    def _dict_lang(self, chat_id: int, lang: str | None) -> str:
        lang = lang if lang in words.LANGUAGES else self.db.get_lang(chat_id)
        self.db.ensure_dictionary(chat_id, lang)
        return lang

    async def dict_get(self, chat_id: int, uid: int, lang: str | None = None) -> dict:
        await self.dict_guard(chat_id, uid)
        lang = self._dict_lang(chat_id, lang)
        rows = self.db.dictionary(chat_id, lang)
        return {"lang": lang, "ui": self.db.get_lang(chat_id), "langs": list(words.LANGUAGES), "words": rows,
                "total": self.db.count_custom(chat_id), "max": config.CUSTOM_WORDS_MAX,
                "min": config.DICT_MIN_WORDS, "alts_max": config.CUSTOM_ALTS_MAX,
                "hours": config.DICT_CODE_HOURS}

    async def dict_add(self, chat_id: int, uid: int, lang: str | None, text: str, diff: int) -> None:
        await self.dict_guard(chat_id, uid)
        lang = self._dict_lang(chat_id, lang)
        parsed = words.parse_custom(text if isinstance(text, str) else "")
        if not parsed:
            raise GameError("bad_word")
        if self.db.count_custom(chat_id) >= config.CUSTOM_WORDS_MAX:
            raise GameError("dict_full")
        if not self.db.add_word(chat_id, lang, parsed[0], diff if diff in (1, 2, 3) else 2, uid, parsed[1]):
            raise GameError("word_dup")

    async def dict_edit(self, chat_id: int, uid: int, lang: str | None, word: str, new: str | None,
                        alts: list, diff: int | None, lock: bool) -> None:
        await self.dict_guard(chat_id, uid)
        lang = self._dict_lang(chat_id, lang)
        main = words.validate_custom(new) if new else None
        if new and not main:
            raise GameError("bad_word")
        clean, seen = [], {words.compact(main or word)}
        for a in alts if isinstance(alts, list) else []:
            a = words.validate_custom(a) if isinstance(a, str) else None
            if not a:
                raise GameError("bad_word")
            if words.compact(a) not in seen:
                seen.add(words.compact(a))
                clean.append(a)
        res = self.db.update_word(chat_id, lang, word, main, tuple(clean[:config.CUSTOM_ALTS_MAX]),
                                  diff if diff in (1, 2, 3) else None, bool(lock))
        if res != "ok":
            raise GameError("word_dup" if res == "dup" else "word_missing")

    async def dict_delete(self, chat_id: int, uid: int, lang: str | None, word: str) -> None:
        await self.dict_guard(chat_id, uid)
        lang = self._dict_lang(chat_id, lang)
        if self.db.count_custom(chat_id, lang) <= config.DICT_MIN_WORDS:
            raise GameError("dict_min", min=config.DICT_MIN_WORDS)
        if not self.db.delete_word(chat_id, lang, word):
            raise GameError("word_missing")

    def _snapshot(self, chat_id: int) -> str:
        self.db.ensure_dictionary(chat_id, self.db.get_lang(chat_id))
        return dictio.dump(self.db.export_rows(chat_id))

    async def dict_export(self, chat_id: int, uid: int) -> None:
        """The dictionary as a file, sent to the caller in private."""
        await self.dict_guard(chat_id, uid)
        data = self._snapshot(chat_id).encode("utf-8")
        ok = await self.io.send_document_dm(uid, data, f"carmink-dictionary-{abs(chat_id)}.json",
                                            "📚 Carmink dictionary")
        if not ok:
            raise GameError("need_dm")

    async def dict_code(self, chat_id: int, uid: int) -> dict:
        await self.dict_guard(chat_id, uid)
        code = dictio.new_code()
        self.db.save_code(code, chat_id, self._snapshot(chat_id), self.io.now())
        return {"code": code, "hours": config.DICT_CODE_HOURS}

    async def dict_import(self, chat_id: int, uid: int, lang: str | None, text: str | None,
                          code: str | None, dry: bool, update: bool = False) -> dict:
        """Merge a file, a pasted list or a share code into the dictionary. `dry`: only say what would happen."""
        await self.dict_guard(chat_id, uid)
        lang = self._dict_lang(chat_id, lang)
        if code:
            raw = self.db.load_code(dictio.clean_code(code), self.io.now()) if dictio.clean_code(code) else None
            if raw is None:
                raise GameError("bad_code")
        else:
            raw = text if isinstance(text, str) else ""
            if len(raw.encode("utf-8")) > config.DICT_IMPORT_MAX_BYTES:
                raise GameError("too_big")
        try:
            items, bad = dictio.parse(raw, lang)
        except ValueError:
            raise GameError("bad_file")
        if not items:
            raise GameError("bad_file")
        res = dictio.merge(self.db, chat_id, items, uid, dry, update)
        return {**res, "invalid": bad, "dry": dry}
