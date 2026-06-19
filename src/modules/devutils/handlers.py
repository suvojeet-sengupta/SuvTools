import base64
import urllib.parse
import json
import hashlib
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from src.modules.base import BaseModule
import config

class DevUtilsModule(BaseModule):
    @property
    def name(self) -> str:
        return "devutils"

    def register_handlers(self, application: Application) -> None:
        application.add_handler(CommandHandler("base64", self.handle_base64))
        application.add_handler(CommandHandler("url", self.handle_url))
        application.add_handler(CommandHandler("json", self.handle_json))
        application.add_handler(CommandHandler("hash", self.handle_hash))

    def _is_allowed(self, update: Update) -> bool:
        if not config.ALLOWED_USERS:
            return True
        user = update.effective_user
        if not user:
            return False
        return str(user.id) in config.ALLOWED_USERS or (user.username and user.username in config.ALLOWED_USERS)

    async def handle_base64(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        message = update.message
        args = context.args
        op = "encode"
        text = ""

        if message.reply_to_message:
            text = message.reply_to_message.text or message.reply_to_message.caption
            if args:
                op = args[0].lower()
        else:
            if len(args) < 2:
                await message.reply_text(
                    "⚠️ **Usage:**\n"
                    "• `/base64 encode <text>`\n"
                    "• `/base64 decode <base64_text>`\n"
                    "• Reply to a message with `/base64 encode` or `/base64 decode`.",
                    parse_mode="Markdown"
                )
                return
            op = args[0].lower()
            text = " ".join(args[1:])

        if not text or not text.strip():
            await message.reply_text("⚠️ Text content is empty.")
            return

        try:
            if op == "encode":
                res = base64.b64encode(text.encode('utf-8')).decode('utf-8')
                await message.reply_text(f"🔏 **Base64 Encoded:**\n```\n{res}\n```", parse_mode="Markdown")
            elif op == "decode":
                res = base64.b64decode(text.encode('utf-8')).decode('utf-8')
                await message.reply_text(f"🔓 **Base64 Decoded:**\n```\n{res}\n```", parse_mode="Markdown")
            else:
                await message.reply_text("⚠️ Use `/base64 encode` or `/base64 decode`.")
        except Exception as e:
            await message.reply_text(f"❌ Action failed: {str(e)}")

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        message = update.message
        args = context.args
        op = "encode"
        text = ""

        if message.reply_to_message:
            text = message.reply_to_message.text or message.reply_to_message.caption
            if args:
                op = args[0].lower()
        else:
            if len(args) < 2:
                await message.reply_text(
                    "⚠️ **Usage:**\n"
                    "• `/url encode <text>`\n"
                    "• `/url decode <url_text>`\n"
                    "• Reply to a message with `/url encode` or `/url decode`.",
                    parse_mode="Markdown"
                )
                return
            op = args[0].lower()
            text = " ".join(args[1:])

        if not text or not text.strip():
            await message.reply_text("⚠️ Text content is empty.")
            return

        try:
            if op == "encode":
                res = urllib.parse.quote(text)
                await message.reply_text(f"🔗 **URL Encoded:**\n```\n{res}\n```", parse_mode="Markdown")
            elif op == "decode":
                res = urllib.parse.unquote(text)
                await message.reply_text(f"📖 **URL Decoded:**\n```\n{res}\n```", parse_mode="Markdown")
            else:
                await message.reply_text("⚠️ Use `/url encode` or `/url decode`.")
        except Exception as e:
            await message.reply_text(f"❌ Action failed: {str(e)}")

    async def handle_json(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        message = update.message
        args = context.args
        op = "beautify"
        text = ""

        if message.reply_to_message:
            text = message.reply_to_message.text or message.reply_to_message.caption
            if args:
                op = args[0].lower()
        else:
            if len(args) < 2:
                await message.reply_text(
                    "⚠️ **Usage:**\n"
                    "• `/json beautify <json_text>`\n"
                    "• `/json minify <json_text>`\n"
                    "• Reply to a message with `/json beautify` or `/json minify`.",
                    parse_mode="Markdown"
                )
                return
            op = args[0].lower()
            text = " ".join(args[1:])

        if not text or not text.strip():
            await message.reply_text("⚠️ JSON text content is empty.")
            return

        try:
            parsed = json.loads(text)
            if op == "beautify":
                res = json.dumps(parsed, indent=2)
                await message.reply_text(f"✨ **JSON Beautified:**\n```json\n{res}\n```", parse_mode="Markdown")
            elif op == "minify":
                res = json.dumps(parsed, separators=(',', ':'))
                await message.reply_text(f"⚡ **JSON Minified:**\n```json\n{res}\n```", parse_mode="Markdown")
            else:
                await message.reply_text("⚠️ Use `/json beautify` or `/json minify`.")
        except Exception as e:
            await message.reply_text(f"❌ Parsing failed: {str(e)}")

    async def handle_hash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return

        message = update.message
        args = context.args
        algo = "sha256"
        text = ""

        if message.reply_to_message:
            text = message.reply_to_message.text or message.reply_to_message.caption
            if args:
                algo = args[0].lower()
        else:
            if len(args) < 2:
                await message.reply_text(
                    "⚠️ **Usage:**\n"
                    "• `/hash sha256 <text>`\n"
                    "• `/hash md5 <text>`\n"
                    "• Reply to a message with `/hash sha256` or `/hash md5`.",
                    parse_mode="Markdown"
                )
                return
            algo = args[0].lower()
            text = " ".join(args[1:])

        if not text or not text.strip():
            await message.reply_text("⚠️ Text content is empty.")
            return

        try:
            encoded_text = text.encode('utf-8')
            if algo == "sha256":
                res = hashlib.sha256(encoded_text).hexdigest()
                await message.reply_text(f"🔑 **SHA-256 Hash:**\n`{res}`", parse_mode="Markdown")
            elif algo == "md5":
                res = hashlib.md5(encoded_text).hexdigest()
                await message.reply_text(f"🔑 **MD5 Hash:**\n`{res}`", parse_mode="Markdown")
            else:
                await message.reply_text("⚠️ Supported hash algorithms: `sha256`, `md5`.")
        except Exception as e:
            await message.reply_text(f"❌ Hashing failed: {str(e)}")
