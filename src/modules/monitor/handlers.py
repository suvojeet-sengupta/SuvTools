import os
import asyncio
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError

from src.modules.base import BaseModule
from src.utils.logger import logger
import config

class MonitorModule(BaseModule):
    def __init__(self):
        # Maps chat_id -> active asyncio monitor Task
        self.active_monitors = {}

    @property
    def name(self) -> str:
        return "monitor"

    def register_handlers(self, application: Application) -> None:
        application.add_handler(CommandHandler("sysinfo", self.handle_sysinfo))
        application.add_handler(CommandHandler("status", self.handle_status))
        application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^stop_monitor$"))

    def _is_allowed(self, update: Update) -> bool:
        """Verifies if the user is authorized to query system stats."""
        if not config.ALLOWED_USERS:
            return True
        user = update.effective_user
        if not user:
            return False
        user_id_str = str(user.id)
        username = user.username
        return user_id_str in config.ALLOWED_USERS or (username and username in config.ALLOWED_USERS)

    def _get_sys_info(self) -> str:
        """Collects resource metrics using Linux system utilities."""
        # 1. CPU Load
        try:
            with open("/proc/loadavg", "r") as f:
                load = f.read().strip().split()
                cpu_load = f"{load[0]} (1m), {load[1]} (5m), {load[2]} (15m)"
        except Exception:
            cpu_load = "N/A"

        # 2. Memory Utilization
        try:
            mem_info = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        mem_info[parts[0].strip()] = parts[1].strip()
                        
            total_kb = int(mem_info.get("MemTotal", "0 kB").split()[0])
            free_kb = int(mem_info.get("MemFree", "0 kB").split()[0])
            buffers_kb = int(mem_info.get("Buffers", "0 kB").split()[0])
            cached_kb = int(mem_info.get("Cached", "0 kB").split()[0])
            available_kb = int(mem_info.get("MemAvailable", "0 kB").split()[0]) if "MemAvailable" in mem_info else (free_kb + buffers_kb + cached_kb)
            
            used_kb = total_kb - available_kb
            total_gb = total_kb / (1024 * 1024)
            used_gb = used_kb / (1024 * 1024)
            ram_percent = (used_kb / total_kb) * 100 if total_kb > 0 else 0
            ram_usage = f"{used_gb:.2f} GB / {total_gb:.2f} GB ({ram_percent:.1f}%)"
        except Exception:
            ram_usage = "N/A"

        # 3. Storage Space
        try:
            res = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, check=True)
            lines = res.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                disk_usage = f"{parts[2]} used / {parts[1]} total ({parts[4]} used)"
            else:
                disk_usage = "N/A"
        except Exception:
            disk_usage = "N/A"

        # 4. Server Uptime
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
                uptime_hours = uptime_seconds // 3600
                uptime_days = uptime_hours // 24
                uptime_hours = uptime_hours % 24
                uptime_mins = (uptime_seconds % 3600) // 60
                uptime_str = f"{int(uptime_days)}d {int(uptime_hours)}h {int(uptime_mins)}m"
        except Exception:
            uptime_str = "N/A"

        # 5. Get current queue counts
        try:
            from src.modules.transcriber.handlers import queue_manager
            active_jobs = len(queue_manager.active_jobs) if queue_manager else 0
            waiting_jobs = len(queue_manager.waiting_jobs) if queue_manager else 0
        except Exception:
            active_jobs, waiting_jobs = 0, 0

        # Output compilation
        metrics = (
            f"• **CPU Load**: `{cpu_load}`\n"
            f"• **RAM Usage**: `{ram_usage}`\n"
            f"• **Disk Usage (/)**: `{disk_usage}`\n"
            f"• **Server Uptime**: `{uptime_str}`\n"
            f"• **Transcriber Queue**: `{active_jobs} active / {waiting_jobs} waiting`"
        )
        return metrics

    async def handle_sysinfo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Displays system resources info and updates it in real-time."""
        if not self._is_allowed(update):
            await update.message.reply_text("⛔ You are not authorized to view system stats.")
            return

        chat_id = update.effective_chat.id

        # Setup Stop button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Stop Live Monitor", callback_data="stop_monitor")]
        ])

        status_msg = await update.message.reply_text(
            "🔍 Initializing Live Monitor...",
            reply_markup=keyboard
        )

        # Cancel any active monitor loop in this chat to avoid duplicates
        if chat_id in self.active_monitors:
            old_task = self.active_monitors[chat_id]
            old_task.cancel()

        # Spawn a background live monitor task
        task = asyncio.create_task(self._live_monitor_loop(chat_id, status_msg))
        self.active_monitors[chat_id] = task

    async def _live_monitor_loop(self, chat_id: int, message: Update.message):
        """Runs the 3-second diagnostic message update loop."""
        spinners = ["🟢", "🟡", "🔵", "🟣"]
        iteration = 0
        max_iterations = 60 # Run for 3 minutes max (60 * 3s = 180s)
        
        try:
            while iteration < max_iterations:
                metrics = await asyncio.to_thread(self._get_sys_info)
                spinner = spinners[iteration % len(spinners)]
                
                text = (
                    f"🖥️ **Live VPS Diagnostics** {spinner}\n\n"
                    f"{metrics}\n\n"
                    f"⚡ _Monitoring live. Auto-closes in {int((max_iterations - iteration) * 3)}s._"
                )
                
                try:
                    await message.edit_text(
                        text,
                        parse_mode="Markdown",
                        reply_markup=message.reply_markup
                    )
                except TelegramError as e:
                    # If message was deleted or can't be edited, break loop
                    if "Message to edit not found" in str(e) or "Message is not modified" not in str(e):
                        pass
                
                await asyncio.sleep(3)
                iteration += 1

            # End of loop: show final snapshot
            await self._stop_monitoring_for_chat(chat_id, message)

        except asyncio.CancelledError:
            # Task was cancelled cleanly (e.g. via CallbackQuery button)
            pass

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes the button clicks."""
        query = update.callback_query
        await query.answer()

        chat_id = update.effective_chat.id
        if query.data == "stop_monitor":
            await self._stop_monitoring_for_chat(chat_id, query.message)

    async def _stop_monitoring_for_chat(self, chat_id: int, message: Update.message):
        """Stops the live updates and draws a static final snapshot."""
        # Retrieve and cancel the running task
        task = self.active_monitors.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

        try:
            metrics = await asyncio.to_thread(self._get_sys_info)
            final_text = (
                f"📊 **VPS Diagnostics (Snapshot)**\n\n"
                f"{metrics}\n\n"
                f"🛑 _Live monitoring has been stopped._"
            )
            await message.edit_text(final_text, parse_mode="Markdown")
        except Exception:
            pass

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """A lightweight ping/status diagnostic."""
        await update.message.reply_text("🟢 **Bot is online and healthy!**", parse_mode="Markdown")
