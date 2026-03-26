import asyncio
import json
import time
from collections import deque
from datetime import datetime

import websockets


class PerformanceBenchmark:
    def __init__(self, duration=30, csv_log=True):
        self.duration = duration
        self.csv_log = csv_log
        self.prices = deque(maxlen=100)
        self.update_times = deque(maxlen=1000)
        self.latencies = deque(maxlen=1000)
        self.last_update = None
    
    async def ws_stream(self):
        uri = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
        start_time = time.time()
        message_count = 0
        
        print(f"🚀 Starting WebSocket benchmark ({self.duration}s)...")
        print(f"📡 Connection: {uri}\n")
        
        try:
            async with websockets.connect(uri) as ws:
                while time.time() - start_time < self.duration:
                    start_msg = time.time()
                    msg = await ws.recv()
                    recv_time = time.time() - start_msg
                    
                    data = json.loads(msg)
                    price = float(data['c'])
                    timestamp = data['E']
                    
                    self.prices.append(price)
                    self.latencies.append(recv_time * 1000)
                    
                    if self.last_update:
                        frame_time = (time.time() - self.last_update) * 1000
                        self.update_times.append(frame_time)
                    
                    self.last_update = time.time()
                    message_count += 1
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        self._print_results(message_count)
    
    def _print_results(self, message_count):
        print(f"\n{'='*60}")
        print(f"📊 BENCHMARK RESULTS ({self.duration}s)")
        print(f"{'='*60}\n")
        
        print(f"Messages received: {message_count}")
        print(f"Average frequency: {message_count/self.duration:.1f} msg/sec")
        
        if self.update_times:
            avg_update = sum(self.update_times) / len(self.update_times)
            max_update = max(self.update_times)
            min_update = min(self.update_times)
            
            print(f"\n⏱️  Update Times (ms):")
            print(f"   Average: {avg_update:.2f}ms")
            print(f"   Min: {min_update:.2f}ms")
            print(f"   Max: {max_update:.2f}ms")
            print(f"   P99: {sorted(self.update_times)[int(len(self.update_times)*0.99)]:.2f}ms")
        
        if self.latencies:
            avg_latency = sum(self.latencies) / len(self.latencies)
            max_latency = max(self.latencies)
            
            print(f"\n📡 WebSocket Latency (ms):")
            print(f"   Average: {avg_latency:.3f}ms")
            print(f"   Max: {max_latency:.3f}ms")
            print(f"   P99: {sorted(self.latencies)[int(len(self.latencies)*0.99)]:.3f}ms")
        
        if self.prices:
            prices_list = list(self.prices)
            price_change = prices_list[-1] - prices_list[0]
            price_range = max(prices_list) - min(prices_list)
            
            print(f"\n💹 Price Movement:")
            print(f"   Current: ${prices_list[-1]:.2f}")
            print(f"   Range: ${price_range:.2f}")
            print(f"   Change: {(price_change/prices_list[0])*100:.3f}%")
        
        fps_estimate = 1000 / (sum(self.update_times) / len(self.update_times)) if self.update_times else 0
        print(f"\n🎯 Estimated FPS (render): {fps_estimate:.1f} FPS")
        print(f"{'='*60}\n")
        
        if self.csv_log:
            self._log_results()
    
    def _log_results(self):
        from pathlib import Path
        import csv
        
        log_file = Path("benchmark_results.csv")
        exists = log_file.exists()
        
        with open(log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow([
                    'timestamp', 'duration', 'message_count', 'avg_update_ms',
                    'avg_latency_ms', 'estimated_fps'
                ])
            
            avg_update = sum(self.update_times) / len(self.update_times) if self.update_times else 0
            avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
            fps = 1000 / avg_update if avg_update > 0 else 0
            
            writer.writerow([
                datetime.now().isoformat(),
                self.duration,
                len(list(self.prices)),
                f'{avg_update:.2f}',
                f'{avg_latency:.3f}',
                f'{fps:.1f}'
            ])
        
        print(f"✅ Results logged to benchmark_results.csv")


if __name__ == "__main__":
    benchmark = PerformanceBenchmark(duration=30, csv_log=True)
    asyncio.run(benchmark.ws_stream())
