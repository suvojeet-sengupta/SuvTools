import os
import subprocess
from src.utils.logger import logger

# Try to import queue_manager from transcriber to show live queue sizes
try:
    from src.modules.transcriber.handlers import queue_manager
except ImportError:
    queue_manager = None

def get_system_metrics() -> dict:
    """Collects real-time VPS resources and bot queue statistics."""
    # 1. CPU Load & Cores
    try:
        with open("/proc/loadavg", "r") as f:
            load = f.read().strip().split()
            cpu_load = [float(load[0]), float(load[1]), float(load[2])]
    except Exception:
        cpu_load = [0.0, 0.0, 0.0]

    # Get CPU cores count
    try:
        cpu_cores = os.cpu_count() or 4
    except Exception:
        cpu_cores = 4

    # 2. RAM Usage
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
    except Exception:
        total_gb, used_gb, ram_percent = 0.0, 0.0, 0.0

    # 3. Disk Usage
    try:
        res = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, check=True)
        lines = res.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            # filesystem, size, used, avail, use%, mounted
            disk_total = parts[1]
            disk_used = parts[2]
            disk_avail = parts[3]
            disk_percent = float(parts[4].replace("%", ""))
        else:
            disk_total, disk_used, disk_avail, disk_percent = "N/A", "N/A", "N/A", 0.0
    except Exception:
        disk_total, disk_used, disk_avail, disk_percent = "N/A", "N/A", "N/A", 0.0

    # 4. Uptime
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
        uptime_seconds = 0.0

    # 5. Queue statistics from transcriber module
    active_jobs = 0
    waiting_jobs = 0
    if queue_manager:
        active_jobs = len(queue_manager.active_jobs)
        waiting_jobs = len(queue_manager.waiting_jobs)

    return {
        "cpu_load": cpu_load,
        "cpu_cores": cpu_cores,
        "ram": {
            "total": round(total_gb, 2),
            "used": round(used_gb, 2),
            "percent": round(ram_percent, 1)
        },
        "disk": {
            "total": disk_total,
            "used": disk_used,
            "available": disk_avail,
            "percent": disk_percent
        },
        "uptime": uptime_str,
        "uptime_seconds": int(uptime_seconds),
        "queue": {
            "active": active_jobs,
            "waiting": waiting_jobs,
            "total": active_jobs + waiting_jobs
        }
    }
