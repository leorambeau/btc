import asyncio
import json
import csv
import threading
import ssl
from datetime import datetime
from collections import deque
from pathlib import Path
from queue import Queue

import websockets
import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor


class BTCVisualizer(QWidget):
    def __init__(self, max_points=100, csv_path="btc_data_log.csv"):
        super().__init__()
        self.max_points = max_points
        self.prices = deque(maxlen=max_points)
        self.timestamps = deque(maxlen=max_points)
        self.time_indices = deque(maxlen=max_points)
        self.csv_path = Path(csv_path)
        self.current_price = 0.0
        self.update_queue = Queue()
        self.time_counter = 0
        
        self._init_csv()
        self._setup_ui()
        self._setup_ws()
        self._start_threads()
    
    def _init_csv(self):
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='') as f:
                csv.writer(f).writerow(['timestamp', 'price'])
    
    def _setup_ui(self):
        self.setWindowTitle('BTC/USDT - Real-time HFT Visualizer')
        self.setGeometry(100, 100, 1200, 700)
        self.setStyleSheet("background-color: #0d1117; color: #e0e0e0;")
        
        layout = QVBoxLayout()
        
        self.price_label = QLabel('BTC/USDT: $0.00')
        self.price_label.setFont(QFont('Arial', 36, QFont.Bold))
        self.price_label.setAlignment(Qt.AlignCenter)
        self.price_label.setStyleSheet("color: #00ff41; margin: 10px;")
        layout.addWidget(self.price_label)
        
        # Configuration des couleurs de pyqtgraph (commenté car non compatible avec cette version)
        # pg.setConfigOptions(background='#0d1117', foreground='#e0e0e0')
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('bottom', 'Time')
        self.plot_widget.setLabel('left', 'Price (USDT)')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='#00ff41', width=3))
        
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_plot)
        self.timer.start(50)
    
    def _update_plot(self):
        if self.prices and self.time_indices:
            self.curve.setData(
                list(self.time_indices),
                list(self.prices),
                skipFiniteCheck=True
            )
            self.price_label.setText(f'BTC/USDT: ${self.current_price:,.2f}')
    
    def _setup_ws(self):
        self.ws_task = None
    
    def _start_threads(self):
        ws_thread = threading.Thread(target=self._run_ws, daemon=True)
        csv_thread = threading.Thread(target=self._run_csv_writer, daemon=True)
        ws_thread.start()
        csv_thread.start()
    
    def _run_ws(self):
        asyncio.run(self._ws_stream())
    
    async def _ws_stream(self):
        uri = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
        reconnect_delay = 1
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        while True:
            try:
                async with websockets.connect(uri, ssl=ssl_context) as ws:
                    reconnect_delay = 1
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        price = float(data['c'])
                        timestamp = datetime.fromtimestamp(data['E'] / 1000)
                        
                        self.current_price = price
                        self.prices.append(price)
                        self.timestamps.append(timestamp.strftime('%H:%M:%S'))
                        self.time_indices.append(self.time_counter)
                        self.time_counter += 1
                        
                        self.update_queue.put((timestamp, price))
                        
            except Exception as e:
                print(f"WS Error: {e}")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)
    
    def _run_csv_writer(self):
        while True:
            try:
                timestamp, price = self.update_queue.get(timeout=1)
                with open(self.csv_path, 'a', newline='') as f:
                    csv.writer(f).writerow([timestamp.isoformat(), f'{price:.2f}'])
            except:
                pass


if __name__ == '__main__':
    app = QApplication([])
    visualizer = BTCVisualizer(max_points=100)
    visualizer.show()
    
    print("🚀 PyQtGraph HFT Visualizer started - 60+ FPS")
    print("📊 WebSocket: wss://stream.binance.com:9443/ws/btcusdt@ticker")
    print("💾 CSV: btc_data_log.csv\n")
    
    app.exec_()
