import os
import asyncio
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.modules.base import BaseModule
from src.utils.logger import logger
import config

class MonitorModule(BaseModule):
    @property
    def name(self) -> str:
        return "monitor"

    def register_handlers(self, application: Application) -> None:
        application.add_handler(CommandHandler("sysinfo", self.handle_sysinfo))
        application.add_handler(CommandHandler("status", self.handle_status))

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
                # format: [filesystem, size, used, avail, use%, mounted]
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

        # Output compilation
        metrics = (
            "💻 **VPS System Diagnostics:**\n\n"
            f"• **CPU Load**: `{cpu_load}`\n"
            f"• **RAM Usage**: `{ram_usage}`\n"
            f"• **Disk Usage (/)**: `{disk_usage}`\n"
            f"• **Uptime**: `{uptime_str}`"
        )
        return metrics

    async def handle_sysinfo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Displays system resources info."""
        if not self._is_allowed(update):
            await update.message.reply_text("⛔ You are not authorized to view system stats.")
            return

        status_msg = await update.message.reply_text("🔍 Gathering system metrics...")
        try:
            metrics = await asyncio.to_thread(self._get_sys_info)
            dashboard_info = (
                f"{metrics}\n\n"
                f"⚡ **Live Web Dashboard** (WebSockets):\n"
                f"• URL: `http://<your_vps_ip>:{config.MONITOR_PORT}/`"
            )
            await status_msg.edit_text(dashboard_info, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to query system stats: {e}")
            await status_msg.edit_text(f"❌ Failed to fetch system diagnostics: {e}")

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """A lightweight ping/status diagnostic."""
        status_text = (
            "🟢 **Bot is online and running successfully under PM2!**\n\n"
            f"📊 **Real-time Diagnostics Web Portal** is active at:\n"
            f"`http://<your_vps_ip>:{config.MONITOR_PORT}/`\n\n"
            "Open this link in your browser to view real-time system charts (CPU, RAM, Disk, Queue sizes) streamed live via WebSockets!"
        )
        await update.message.reply_text(status_text, parse_mode="Markdown")
