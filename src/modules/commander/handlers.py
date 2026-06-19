import os
import asyncio
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

from src.modules.base import BaseModule
from src.utils.logger import logger
import config

class CommanderModule(BaseModule):
    @property
    def name(self) -> str:
        return "commander"

    def register_handlers(self, application: Application) -> None:
        # Secure terminal command runner
        application.add_handler(CommandHandler("run", self.handle_run))
        
        # Interactive command buttons
        application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^run_cmd_"))
        
        # File list & File downloader
        application.add_handler(CommandHandler("files", self.handle_files))
        application.add_handler(CommandHandler("getfile", self.handle_getfile))
        
        # File upload to VPS (Requires replying to an uploaded document with /upload)
        application.add_handler(CommandHandler("upload", self.handle_upload))

    def _is_allowed(self, update: Update) -> bool:
        """Enforces strict admin-only check. Commands can only run if configured in ALLOWED_USERS."""
        if not config.ALLOWED_USERS:
            # For security, if ALLOWED_USERS is empty, commander is disabled by default to prevent hijacking!
            return False
        user = update.effective_user
        if not user:
            return False
        
        user_id_str = str(user.id)
        username = user.username
        
        return user_id_str in config.ALLOWED_USERS or (username and username in config.ALLOWED_USERS)

    async def handle_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Runs custom bash commands or triggers interactive buttons menu."""
        if not self._is_allowed(update):
            await update.message.reply_text("⛔ Commander access denied. Secure authorization required.")
            return

        message = update.message
        args = context.args

        # Scenario 1: User types '/run' with no args -> Show quick diagnostics keyboard
        if not args:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 PM2 Status", callback_data="run_cmd_pm2_status"),
                    InlineKeyboardButton("🪵 PM2 Logs", callback_data="run_cmd_pm2_logs")
                ],
                [
                    InlineKeyboardButton("💻 Free RAM", callback_data="run_cmd_ram"),
                    InlineKeyboardButton("💾 Disk Space", callback_data="run_cmd_disk")
                ]
            ])
            await message.reply_text(
                "⚙️ **VPS Commander Console**\n"
                "Select a diagnostic button below or execute a custom command:\n"
                "• `/run <bash command>`\n"
                "• _Example:_ `/run pm2 restart all`",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return

        # Scenario 2: Execute the custom command
        command_str = " ".join(args)
        await self._execute_and_reply(message, command_str)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles diagnostic button clicks."""
        query = update.callback_query
        await query.answer()

        if not self._is_allowed(update):
            await query.message.reply_text("⛔ Commander access denied.")
            return

        action = query.data
        command = ""

        if action == "run_cmd_pm2_status":
            command = "pm2 status"
        elif action == "run_cmd_pm2_logs":
            command = "pm2 logs --lines 20 --no-daemon"
        elif action == "run_cmd_ram":
            command = "free -h"
        elif action == "run_cmd_disk":
            command = "df -h"
        else:
            return

        await self._execute_and_reply(query.message, command)

    async def _execute_and_reply(self, reply_target, command: str):
        """Helper to run shell commands in a threadpool and reply with output."""
        status_msg = await reply_target.reply_text(f"⚡ Running: `{command}`...")
        logger.info(f"VPS Commander: executing shell command: '{command}'")
        
        try:
            # Run command in thread pool to prevent blocking loop, set 20-second timeout
            process_res = await asyncio.to_thread(
                subprocess.run,
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=20,
                cwd="/root/SuvTools"
            )
            
            output = process_res.stdout.strip() if process_res.stdout else "*(No stdout generated)*"
            
            # Format and send response
            header = f"💻 **Command Output:**\n`$ {command}`\n\n"
            code_block = f"```\n{output}\n```"
            response_text = header + code_block
            
            if len(response_text) <= 4000:
                await status_msg.edit_text(response_text, parse_mode="Markdown")
            else:
                # Text exceeds Telegram limit: save to file and send as Document
                await status_msg.delete()
                import uuid
                txt_path = os.path.join(config.DOWNLOAD_DIR, f"cmd_output_{uuid.uuid4()}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"Command executed: {command}\n")
                    f.write("=" * 40 + "\n\n")
                    f.write(output)
                    
                with open(txt_path, "rb") as doc_file:
                    await reply_target.reply_document(
                        document=doc_file,
                        filename=f"cmd_output.txt",
                        caption=f"📄 Output too long. Sent as file."
                    )
                if os.path.exists(txt_path):
                    os.remove(txt_path)
                    
        except asyncio.TimeoutError:
            await status_msg.edit_text(f"❌ Command timed out (20s limit): `{command}`")
        except Exception as e:
            logger.error(f"Failed to run command '{command}': {e}")
            await status_msg.edit_text(f"❌ Failed to execute command: {str(e)}")

    async def handle_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lists files inside the working directory."""
        if not self._is_allowed(update):
            return

        message = update.message
        args = context.args
        target_dir = "/root/SuvTools"
        
        if args:
            # Prevent directory traversal attacks (e.g. /files ../../etc)
            clean_path = os.path.normpath(args[0])
            if clean_path.startswith(".."):
                await message.reply_text("⛔ Access denied: cannot access parent directories.")
                return
            target_dir = os.path.join("/root/SuvTools", clean_path)

        if not os.path.exists(target_dir):
            await message.reply_text("⚠️ Directory does not exist.")
            return

        try:
            items = os.listdir(target_dir)
            files_list = []
            dirs_list = []
            
            for item in items:
                path = os.path.join(target_dir, item)
                if os.path.isdir(path):
                    dirs_list.append(f"📁 {item}/")
                else:
                    files_list.append(f"📄 {item}")
                    
            dirs_list.sort()
            files_list.sort()
            
            response = (
                f"📂 **Directory Explorer:** `{target_dir}`\n\n"
                + "\n".join(dirs_list + files_list)
            )
            
            await message.reply_text(response or "📦 Directory is empty.")
        except Exception as e:
            await message.reply_text(f"❌ Failed to list files: {str(e)}")

    async def handle_getfile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Downloads a specific file from the VPS."""
        if not self._is_allowed(update):
            return

        message = update.message
        args = context.args

        if not args:
            await message.reply_text("⚠️ **Usage:** `/getfile <relative_file_path>`\n• _Example:_ `/getfile config.py`")
            return

        target_file = os.path.normpath(args[0])
        # Prevent traversal
        if target_file.startswith(".."):
            await message.reply_text("⛔ Access denied.")
            return

        file_path = os.path.join("/root/SuvTools", target_file)
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            await message.reply_text("⚠️ File not found.")
            return

        # Restrict uploading very large files to Telegram (max 50MB limit)
        if os.path.getsize(file_path) > 52428800:
            await message.reply_text("⚠️ File is too large to upload (>50MB).")
            return

        try:
            with open(file_path, "rb") as f:
                await message.reply_document(
                    document=f,
                    filename=os.path.basename(file_path),
                    caption=f"📤 File sent from VPS: `{target_file}`"
                )
        except Exception as e:
            await message.reply_text(f"❌ Failed to send file: {str(e)}")

    async def handle_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Uploads a document from Telegram directly into the VPS workspace."""
        if not self._is_allowed(update):
            return

        message = update.message
        
        # Verify if they replied to a document/file attachment
        if not message.reply_to_message or not message.reply_to_message.document:
            await message.reply_text(
                "⚠️ **Usage:**\n"
                "1. Upload a file to this chat.\n"
                "2. Reply to that file with the `/upload` command."
            )
            return

        doc = message.reply_to_message.document
        dest_filename = doc.file_name or "uploaded_file.bin"
        
        # Determine destination
        args = context.args
        dest_dir = "/root/SuvTools"
        
        if args:
            clean_path = os.path.normpath(args[0])
            if clean_path.startswith(".."):
                await message.reply_text("⛔ Access denied.")
                return
            dest_dir = os.path.join("/root/SuvTools", clean_path)

        dest_path = os.path.join(dest_dir, dest_filename)
        os.makedirs(dest_dir, exist_ok=True)

        status_msg = await message.reply_text(f"📥 Uploading file to VPS: `{dest_path}`...")
        try:
            telegram_file = await context.bot.get_file(doc.file_id)
            await telegram_file.download_to_drive(dest_path)
            await status_msg.edit_text(f"✅ File successfully saved to VPS at:\n`{dest_path}`")
        except Exception as e:
            await status_msg.edit_text(f"❌ Failed to save file to VPS: {str(e)}")
