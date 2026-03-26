import asyncio
import json
import csv
from datetime import datetime
from collections import deque
from pathlib import Path
import threading
from queue import Queue
import webbrowser
from threading import Event

import websockets
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, callback
from dash.dependencies import Input, Output


class BTCRealtimeVisualizer:
    def __init__(self, max_points=100, csv_path="btc_data_log.csv"):
        self.max_points = max_points
        self.prices = deque(maxlen=max_points)
        self.timestamps = deque(maxlen=max_points)
        self.csv_path = Path(csv_path)
        self.current_price = 0.0
        self.update_queue = Queue()
        self.stop_event = Event()
        self._init_csv()
        
    def _init_csv(self):
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='') as f:
                csv.writer(f).writerow(['timestamp', 'price'])
    
    async def ws_stream(self):
        uri = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
        reconnect_delay = 1
        
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    reconnect_delay = 1
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        price = float(data['c'])
                        timestamp = datetime.fromtimestamp(data['E'] / 1000)
                        
                        self.current_price = price
                        self.prices.append(price)
                        self.timestamps.append(timestamp.strftime('%H:%M:%S'))
                        
                        self.update_queue.put((timestamp, price))
                        
            except Exception as e:
                print(f"Connection error: {e}. Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)
    
    def csv_writer_thread(self):
        while not self.stop_event.is_set():
            try:
                timestamp, price = self.update_queue.get(timeout=1)
                with open(self.csv_path, 'a', newline='') as f:
                    csv.writer(f).writerow([timestamp.isoformat(), f'{price:.2f}'])
            except:
                pass
    
    def build_figure(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(self.timestamps),
            y=list(self.prices),
            mode='lines',
            line=dict(color='#00ff41', width=2.5),
            name='BTC/USDT',
            hovertemplate='<b>%{y:$,.2f}</b><br>%{x}<extra></extra>'
        ))
        
        fig.update_layout(
            title={
                'text': f'<b style="font-size:32px">BTC/USDT: ${self.current_price:,.2f}</b>',
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis_title='Time',
            yaxis_title='Price (USDT)',
            template='plotly_dark',
            plot_bgcolor='#0d1117',
            paper_bgcolor='#0d1117',
            font=dict(color='#e0e0e0', size=11),
            hovermode='x unified',
            margin=dict(l=60, r=30, t=100, b=50),
            height=600,
            xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#21262d'),
            yaxis=dict(showgrid=True, gridwidth=1, gridcolor='#21262d'),
        )
        
        return fig
    
    def run(self):
        self.stop_event = Event()
        
        ws_thread = threading.Thread(target=lambda: asyncio.run(self.ws_stream()), daemon=True)
        csv_thread = threading.Thread(target=self.csv_writer_thread, daemon=True)
        
        ws_thread.start()
        csv_thread.start()
        
        # Créer l'app Dash avec configuration appropriée
        app = Dash(__name__, suppress_callback_exceptions=True)
        
        @app.callback(
            Output('graph', 'figure'),
            Input('interval', 'n_intervals'),
            prevent_initial_call=False
        )
        def update_graph(n):
            return self.build_figure()
        
        app.layout = html.Div([
            dcc.Graph(id='graph', style={'height': '90vh'}),
            dcc.Interval(id='interval', interval=500, n_intervals=0)
        ], style={'backgroundColor': '#0d1117', 'color': '#e0e0e0'})
        
        print("🚀 Bitcoin HFT Visualizer started")
        print("📊 Live feed: wss://stream.binance.com:9443/ws/btcusdt@ticker")
        print("💾 Logging to: btc_data_log.csv")
        print("🌐 Opening browser at http://127.0.0.1:8050")
        print("⏱️  Updating every ~500ms")
        print("🛑 Fermer à tout moment avec Ctrl+C\n")
        
        try:
            # Ouvrir le navigateur automatiquement
            webbrowser.open('http://127.0.0.1:8050')
            app.run_server(debug=False, host='127.0.0.1', port=8050)
        except KeyboardInterrupt:
            print("\n✋ Arrêt du serveur...")
            self.stop_event.set()


if __name__ == "__main__":
    visualizer = BTCRealtimeVisualizer(max_points=100, csv_path="btc_data_log.csv")
    visualizer.run()
