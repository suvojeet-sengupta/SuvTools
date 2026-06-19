import asyncio
import http
import json
import websockets
from src.utils.logger import logger
from src.modules.monitor.metrics import get_system_metrics
import config

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SuvTools VPS Live Diagnostics</title>
    <!-- Outfit Font -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(23, 29, 43, 0.65);
            --card-border: rgba(255, 255, 255, 0.08);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-glow: rgba(59, 130, 246, 0.35);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.35);
            --warning: #f59e0b;
            --danger: #ef4444;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 2rem;
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.1) 0px, transparent 50%);
            background-attachment: fixed;
        }

        header {
            max-width: 1200px;
            width: 100%;
            margin: 0 auto 2rem auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo i {
            font-size: 2rem;
            color: var(--primary);
            filter: drop-shadow(0 0 8px var(--primary-glow));
        }

        .logo h1 {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #fff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 0.5rem 1rem;
            border-radius: 99px;
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--success);
            box-shadow: 0 0 10px var(--success-glow);
            transition: all 0.3s ease;
        }

        .status-badge.offline {
            color: var(--danger);
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
        }

        main {
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 1.5rem;
            flex-grow: 1;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 1.25rem;
            padding: 1.5rem;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            position: relative;
            overflow: hidden;
        }

        /* Card Sizes */
        .col-4 { grid-column: span 4; }
        .col-6 { grid-column: span 6; }
        .col-8 { grid-column: span 8; }
        .col-12 { grid-column: span 12; }

        @media (max-width: 1024px) {
            .col-4, .col-6, .col-8 { grid-column: span 6; }
        }

        @media (max-width: 640px) {
            .col-4, .col-6, .col-8, .col-12 { grid-column: span 12; }
            body { padding: 1rem; }
        }

        .card-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .card-title i {
            color: var(--primary);
        }

        /* Circular Progress Rings */
        .ring-container {
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
            margin: 1rem 0;
        }

        .progress-ring {
            transform: rotate(-90deg);
        }

        .progress-ring__circle {
            transition: stroke-dashoffset 0.35s;
            transform-origin: 50% 50%;
        }

        .ring-value {
            position: absolute;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }

        .ring-number {
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-main);
        }

        .ring-unit {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        .stat-details {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 0.75rem;
            font-size: 0.875rem;
        }

        .stat-label {
            color: var(--text-muted);
        }

        .stat-value {
            font-weight: 600;
        }

        /* Grid Data List */
        .data-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1.25rem;
            height: 100%;
        }

        .data-box {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 0.75rem;
            padding: 1rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .data-icon {
            font-size: 1.5rem;
            width: 3rem;
            height: 3rem;
            background: rgba(59, 130, 246, 0.1);
            color: var(--primary);
            border-radius: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            filter: drop-shadow(0 0 4px var(--primary-glow));
        }

        .data-icon.success {
            background: rgba(16, 185, 129, 0.1);
            color: var(--success);
            filter: drop-shadow(0 0 4px var(--success-glow));
        }

        .data-text {
            display: flex;
            flex-direction: column;
        }

        .data-val {
            font-size: 1.25rem;
            font-weight: 700;
        }

        .data-lbl {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Queue Card */
        .queue-display {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 1rem;
            height: 100%;
            padding: 1rem 0;
        }

        .queue-number-large {
            font-size: 4rem;
            font-weight: 700;
            color: var(--primary);
            line-height: 1;
            text-shadow: 0 0 20px var(--primary-glow);
            transition: all 0.3s ease;
        }

        .queue-number-large.active {
            color: var(--success);
            text-shadow: 0 0 20px var(--success-glow);
        }

        .queue-subtitle {
            font-size: 0.875rem;
            color: var(--text-muted);
            text-align: center;
        }

        footer {
            max-width: 1200px;
            width: 100%;
            margin: 2rem auto 0 auto;
            text-align: center;
            font-size: 0.875rem;
            color: var(--text-muted);
            border-top: 1px solid var(--card-border);
            padding-top: 1.5rem;
        }

        footer a {
            color: var(--primary);
            text-decoration: none;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <i class="fa-solid fa-gauge-high"></i>
            <h1>SuvTools Live Panel</h1>
        </div>
        <div id="connection-status" class="status-badge offline">
            <i class="fa-solid fa-circle-nodes"></i> Connecting...
        </div>
    </header>

    <main>
        <!-- CPU Card -->
        <div class="card col-4">
            <div class="card-title">
                <i class="fa-solid fa-microchip"></i> CPU Utilization
            </div>
            <div class="ring-container">
                <svg class="progress-ring" width="160" height="160">
                    <circle class="progress-ring__background" stroke="rgba(255,255,255,0.03)" stroke-width="12" fill="transparent" r="68" cx="80" cy="80"/>
                    <circle id="cpu-ring" class="progress-ring__circle" stroke="var(--primary)" stroke-width="12" fill="transparent" r="68" cx="80" cy="80" stroke-linecap="round"/>
                </svg>
                <div class="ring-value">
                    <span id="cpu-percent" class="ring-number">0.0</span>
                    <span class="ring-unit">% Load</span>
                </div>
            </div>
            <div class="stat-details">
                <span class="stat-label">Load Averages</span>
                <span id="cpu-load-val" class="stat-value">0.00, 0.00, 0.00</span>
            </div>
            <div class="stat-details">
                <span class="stat-label">CPU Cores</span>
                <span id="cpu-cores-val" class="stat-value">0 Cores</span>
            </div>
        </div>

        <!-- RAM Card -->
        <div class="card col-4">
            <div class="card-title">
                <i class="fa-solid fa-memory"></i> Memory Usage
            </div>
            <div class="ring-container">
                <svg class="progress-ring" width="160" height="160">
                    <circle class="progress-ring__background" stroke="rgba(255,255,255,0.03)" stroke-width="12" fill="transparent" r="68" cx="80" cy="80"/>
                    <circle id="ram-ring" class="progress-ring__circle" stroke="var(--success)" stroke-width="12" fill="transparent" r="68" cx="80" cy="80" stroke-linecap="round"/>
                </svg>
                <div class="ring-value">
                    <span id="ram-percent" class="ring-number">0.0</span>
                    <span class="ring-unit">Used %</span>
                </div>
            </div>
            <div class="stat-details">
                <span class="stat-label">Memory Space</span>
                <span id="ram-usage-val" class="stat-value">0.0 GB / 0.0 GB</span>
            </div>
            <div class="stat-details">
                <span class="stat-label">Diagnostics Status</span>
                <span class="stat-value" style="color: var(--success)">Healthy</span>
            </div>
        </div>

        <!-- Live Queue Card -->
        <div class="card col-4">
            <div class="card-title">
                <i class="fa-solid fa-layer-group"></i> Transcription Queue
            </div>
            <div class="queue-display">
                <div id="queue-large-val" class="queue-number-large">0</div>
                <div class="queue-subtitle">Active / Pending Jobs in Buffer</div>
            </div>
            <div class="stat-details">
                <span class="stat-label">Active Transcribing</span>
                <span id="queue-active-val" class="stat-value">0 Jobs</span>
            </div>
            <div class="stat-details">
                <span class="stat-label">Waiting in Queue</span>
                <span id="queue-waiting-val" class="stat-value">0 Jobs</span>
            </div>
        </div>

        <!-- System Stats Details -->
        <div class="card col-12">
            <div class="card-title">
                <i class="fa-solid fa-server"></i> System Properties & Storage
            </div>
            <div class="data-grid">
                <div class="data-box">
                    <div class="data-icon"><i class="fa-solid fa-hdd"></i></div>
                    <div class="data-text">
                        <span id="disk-total-val" class="data-val">0.0 GB</span>
                        <span class="data-lbl">Total Capacity (/)</span>
                    </div>
                </div>
                <div class="data-box">
                    <div class="data-icon success"><i class="fa-solid fa-chart-line"></i></div>
                    <div class="data-text">
                        <span id="disk-used-val" class="data-val">0.0 GB (0%)</span>
                        <span class="data-lbl">Disk Space Consumption</span>
                    </div>
                </div>
                <div class="data-box">
                    <div class="data-icon"><i class="fa-solid fa-clock"></i></div>
                    <div class="data-text">
                        <span id="sys-uptime-val" class="data-val">0d 0h 0m</span>
                        <span class="data-lbl">Host Server Uptime</span>
                    </div>
                </div>
                <div class="data-box">
                    <div class="data-icon success"><i class="fa-solid fa-network-wired"></i></div>
                    <div class="data-text">
                        <span id="socket-port" class="data-val">WS Port: 8000</span>
                        <span class="data-lbl">Diagnostics Socket Service</span>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <footer>
        <p>SuvTools Multitool Platform &copy; 2026. Built with python-telegram-bot & faster-whisper. Managed via <a href="https://pm2.keymetrics.io/" target="_blank">PM2</a>.</p>
    </footer>

    <script>
        // Setup Circular Progress Ring Logic
        function configureProgressRing(circleId) {
            const circle = document.getElementById(circleId);
            const radius = circle.r.baseVal.value;
            const circumference = radius * 2 * Math.PI;
            
            circle.style.strokeDasharray = `${circumference} ${circumference}`;
            circle.style.strokeDashoffset = circumference;
            
            return function(percent) {
                const offset = circumference - (percent / 100 * circumference);
                circle.style.strokeDashoffset = offset;
            }
        }

        const updateCpuRing = configureProgressRing('cpu-ring');
        const updateRamRing = configureProgressRing('ram-ring');

        // WebSocket connection manager
        let socket;
        const wsUri = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + '/ws';
        const connectionStatus = document.getElementById('connection-status');
        document.getElementById('socket-port').innerText = 'WS Port: ' + window.location.port;

        function connectWebSocket() {
            connectionStatus.className = 'status-badge offline';
            connectionStatus.innerHTML = '<i class="fa-solid fa-circle-nodes"></i> Connecting...';

            socket = new WebSocket(wsUri);

            socket.onopen = function() {
                connectionStatus.className = 'status-badge';
                connectionStatus.innerHTML = '<i class="fa-solid fa-circle-check"></i> Live Sync Active';
            };

            socket.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    // 1. Update CPU
                    // calculate overall CPU percent from load relative to core count
                    const load1m = data.cpu_load[0];
                    const cores = data.cpu_cores;
                    const cpuPercent = Math.min((load1m / cores) * 100, 100.0);
                    
                    document.getElementById('cpu-percent').innerText = cpuPercent.toFixed(1);
                    updateCpuRing(cpuPercent);
                    document.getElementById('cpu-load-val').innerText = data.cpu_load.map(x => x.toFixed(2)).join(', ');
                    document.getElementById('cpu-cores-val').innerText = cores + ' vCPUs';

                    // 2. Update RAM
                    const ram = data.ram;
                    document.getElementById('ram-percent').innerText = ram.percent.toFixed(1);
                    updateRamRing(ram.percent);
                    document.getElementById('ram-usage-val').innerText = ram.used + ' GB / ' + ram.total + ' GB';

                    // 3. Update Queue
                    const q = data.queue;
                    const queueLarge = document.getElementById('queue-large-val');
                    queueLarge.innerText = q.total;
                    if (q.active > 0) {
                        queueLarge.className = 'queue-number-large active';
                    } else {
                        queueLarge.className = 'queue-number-large';
                    }
                    document.getElementById('queue-active-val').innerText = q.active + ' Job' + (q.active !== 1 ? 's' : '') + ' Transcribing';
                    document.getElementById('queue-waiting-val').innerText = q.waiting + ' Job' + (q.waiting !== 1 ? 's' : '') + ' Queued';

                    // 4. Update Properties & Storage
                    const d = data.disk;
                    document.getElementById('disk-total-val').innerText = d.total;
                    document.getElementById('disk-used-val').innerText = d.used + ' (' + d.percent + '% used)';
                    document.getElementById('sys-uptime-val').innerText = data.uptime;

                } catch (err) {
                    console.error('Failed to parse websocket message:', err);
                }
            };

            socket.onclose = function() {
                connectionStatus.className = 'status-badge offline';
                connectionStatus.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Reconnecting...';
                // Try to reconnect after 3 seconds
                setTimeout(connectWebSocket, 3000);
            };

            socket.onerror = function(err) {
                console.error('WebSocket Error:', err);
                socket.close();
            };
        }

        // Initialize connection
        connectWebSocket();
    </script>
</body>
</html>
"""

class DashboardServer:
    def __init__(self):
        self.server = None
        self.clients = set()
        self.loop_task = None
        self.port = config.MONITOR_PORT
        self.host = config.MONITOR_HOST

    async def start(self):
        """Starts the WebSocket & HTTP combined diagnostics server."""
        logger.info(f"Starting Live Diagnostics Server on http://{self.host}:{self.port}...")
        try:
            self.server = await websockets.serve(
                self._handler,
                self.host,
                self.port,
                process_request=self._process_request
            )
            logger.info("Live Diagnostics Server is running successfully.")
            # Start background data broadcast loop
            self.loop_task = asyncio.create_task(self._broadcast_loop())
        except Exception as e:
            logger.error(f"Failed to start Live Diagnostics Server: {e}")

    async def stop(self):
        """Gracefully stops the diagnostics server."""
        logger.info("Stopping Live Diagnostics Server...")
        if self.loop_task:
            self.loop_task.cancel()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Live Diagnostics Server fully shut down.")

    async def _process_request(self, path: str, request_headers):
        """Intercepts HTTP requests to serve the diagnostic HTML page."""
        # Force exact match on root path for dashboard view
        if path == "/":
            headers = [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(HTML_CONTENT.encode("utf-8")))),
                ("Connection", "close"),
            ]
            return http.HTTPStatus.OK, headers, HTML_CONTENT.encode("utf-8")
        return None  # Continue with normal WS handshake (for /ws connection)

    async def _handler(self, websocket, path):
        """Handles websocket registrations and clients."""
        logger.info(f"New client connected to Live WS: {websocket.remote_address}")
        self.clients.add(websocket)
        try:
            # We just need to keep connection open and listen for close
            async for message in websocket:
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            logger.info(f"Client disconnected from Live WS: {websocket.remote_address}")

    async def _broadcast_loop(self):
        """Streams real-time metrics to all connected clients every 1s."""
        while True:
            try:
                if self.clients:
                    metrics = get_system_metrics()
                    payload = json.dumps(metrics)
                    # Send payload to all registered websocket connections
                    await asyncio.gather(
                        *[client.send(payload) for client in self.clients],
                        return_exceptions=True
                    )
            except Exception as e:
                logger.error(f"Error in Live WS broadcast loop: {e}")
            await asyncio.sleep(1)
