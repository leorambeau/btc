import asyncio
import json
import csv
from datetime import datetime
from collections import deque
from pathlib import Path

import websockets
from IPython.display import display, clear_output
from plotly import graph_objects as go


class BTCRealtimeVisualizer:
    def __init__(self, max_points=100, csv_path="btc_data_log.csv"):
        self.max_points = max_points
        self.prices = deque(maxlen=max_points)
        self.timestamps = deque(maxlen=max_points)
        self.csv_path = Path(csv_path)
        self.current_price = 0.0
        self.csv_lock = asyncio.Lock()
        self._init_csv()
        
        self.fig = go.FigureWidget()
        self.fig.add_trace(go.Scatter(
            x=[], y=[],
            mode='lines',
            line=dict(color='#00ff41', width=2),
            name='BTC/USDT'
        ))
        
        self.fig.update_layout(
            title='<b>BTC/USDT: $0.00</b>',
            xaxis_title='Time',
            yaxis_title='Price (USDT)',
            template='plotly_dark',
            plot_bgcolor='#0d1117',
            paper_bgcolor='#0d1117',
            font=dict(color='#e0e0e0', size=12),
            hovermode='x unified',
            margin=dict(l=50, r=50, t=60, b=50),
            height=500,
        )
        
    def _init_csv(self):
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'price'])
    
    async def ws_handler(self):
        uri = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
        try:
            async with websockets.connect(uri) as ws:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    price = float(data['c'])
                    timestamp = datetime.fromtimestamp(data['E'] / 1000)
                    
                    self.current_price = price
                    self.prices.append(price)
                    self.timestamps.append(timestamp.strftime('%H:%M:%S'))
                    
                    asyncio.create_task(self._log_to_csv(timestamp, price))
                    self._update_graph()
        except Exception as e:
            print(f"WebSocket error: {e}")
            await asyncio.sleep(1)
            asyncio.create_task(self.ws_handler())
    
    async def _log_to_csv(self, timestamp, price):
        async with self.csv_lock:
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp.isoformat(), f'{price:.2f}'])
    
    def _update_graph(self):
        with self.fig.batch_update():
            self.fig.data[0].x = list(self.timestamps)
            self.fig.data[0].y = list(self.prices)
            self.fig.update_layout(
                title=f'<b>BTC/USDT: ${self.current_price:,.2f}</b>'
            )
    
    def display(self):
        display(self.fig)
    
    async def run(self):
        await self.ws_handler()


if __name__ == "__main__":
    visualizer = BTCRealtimeVisualizer()
    visualizer.display()
    asyncio.run(visualizer.run())
