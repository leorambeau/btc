# 🏗️ Architecture - BTC HFT Visualizer

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────┐
│  Binance WebSocket (wss://stream.binance.com:9443)     │
│  BTC/USDT @ticker (≈1msg/sec)                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │  asyncio Event Loop        │
        │  (ws_stream coroutine)     │
        └────────┬───────────────────┘
                 │
    ┌────────────┴────────────┬──────────────────┐
    │                         │                  │
    ▼                         ▼                  ▼
┌─────────────┐      ┌─────────────────┐  ┌────────────┐
│ deque(100)  │      │ Queue FIFO      │  │ threading  │
│ Prices      │      │ CSV Writes      │  │ CSV Writer │
└──────┬──────┘      └────────┬────────┘  └────┬───────┘
       │                      │                 │
       │                      ├─────────────────┘
       │                      │
       │         btc_data_log.csv
       │         (timestamp, price)
       │
       └──────────────────────┬─────────────────────┐
                              │                     │
                    ┌─────────▼──────────┐  ┌──────▼──────────┐
                    │ PyQtGraph          │  │ Plotly Web      │
                    │ (Native GUI)       │  │ (HTTP Server)   │
                    │ 60+ FPS            │  │ Responsive      │
                    └────────────────────┘  └─────────────────┘
```

## Composants

### 1. **WebSocket Handler (asyncio)**
- **Fichier**: `btc_hft_pyqtgraph.py` / `btc_hft_standalone.py`
- **Fonction**: `_ws_stream()`
- **Comportement**:
  - Connexion non-bloquante via `websockets`
  - Parse JSON real-time
  - Reconnexion auto avec délai exponentiel (1→30s)
  - Timestamp serveur Binance (ms precision)

**Latency**: ~50-100ms Binance→Client

### 2. **Data Storage (collections.deque)**
```python
deque(maxlen=100)  # O(1) append/pop
```
- **Max points**: 100 (configurable)
- **Avantages**:
  - Mémoire fixe (→ constante)
  - Pas de réallocation array
  - FIFO efficace
  
**Memory usage**: ~100 floats × 8 bytes = 800 bytes

### 3. **CSV Writer (Threading)**
- **Fichier**: `btc_data_loader.py`
- **Mécanisme**: 
  - Queue non-bloquante entre WebSocket thread et Writer thread
  - `threading.Thread` + `Queue` pour async vs UI
  - Flushes tous les N points ou time interval

**Impact GUI**: Zéro (thread séparé)

### 4. **Visualisation**

#### Option A: PyQtGraph (Recommandé)
```
PyQt5 Main Loop
    ↓
QTimer (50ms interval)
    ↓
_update_plot() [Qt slot]
    ↓
curve.setData() [GPU accelerated]
    ↓
Monitor @ 60 FPS
```

**Avantages**:
- GPU rendering (si disponible)
- Native window (pas de navigateur overhead)
- Minimal CPU usage (~5-10%)

#### Option B: Plotly Web
```
Plotly FigureWidget
    ↓
batch_update() [atomique]
    ↓
HTTP→Browser
    ↓
D3.js rendering
    ↓
Monitor @ 30 FPS
```

**Avantages**:
- Interactive zoom/pan
- Web-based (accessible)
- Export facile to HTML

### 5. **ML Pipeline**

```
btc_data_log.csv
    ↓
BTCDataLoader.get_features()
    ├─ SMA-5, SMA-10 (momentum)
    ├─ Volatility (std)
    ├─ Momentum (Δ price)
    └─ RSI (relative strength)
    ↓
StandardScaler (normalize)
    ↓
RandomForestRegressor (100 trees, max_depth=15)
    ↓
Predictions (next price)
```

**Feature importance** (typos):
1. SMA-10 (~40-50%)
2. Volatility (~20-30%)
3. RSI (~15-20%)
4. Momentum (~5-10%)

## Performance

### Latency Measurement
```
Binance API
    ├─ Process time: ~100-500ms
    ├─ Network: ~50-150ms
    │
    Web Socket Receive
    │
    JSON Parse: ~1-2ms
    │
    Deque Append: ~0.1ms
    │
    PyQtGraph Update: ~5-10ms
    └─ Total: ~160-670ms worst case
```

### Memory Profile
- **Deque**: 800 bytes (100 floats)
- **Deque timestamps**: 800 bytes strings
- **Overhead**: ~2KB
- **Total**: ~4KB running memory

### CPU Usage
- **WebSocket loop**: ~1-2%
- **GUI render** @ 60 FPS: ~3-5%
- **CSV writer**: negligible
- **Total**: ~5-10% single core

## Reconnection Strategy

```python
reconnect_delay = 1
while True:
    try:
        async with websockets.connect(uri) as ws:
            # streaming...
    except Exception:
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, 30)
        # Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s
```

## Data Accuracy

- **Source**: Binance ticker (c = current price close)
- **Precision**: Float64 (15 decimal places)
- **Timestamp**: ms from Binance server
- **Consistency**: Single stream (no data splits)

## Scaling Considerations

### For 1000 points (10x data):
- Memory: ~4KB → 40KB
- GPU: Still OK
- Latency: +20-30ms max

### For 10,000 points (100x data):
- Memory: ~4KB → 400KB
- GPU: May stutter
- **Recommendation**: Use SQLite + async queries

## Future Optimizations

1. **Multi-symbol streaming**:
   ```python
   symbols = ['btcusdt', 'ethusdt', 'bnbusdt']
   tasks = [ws_stream(sym) for sym in symbols]
   await asyncio.gather(*tasks)
   ```

2. **Database backend**:
   ```python
   # Replace CSV with SQLite for faster queries
   db.insert(timestamp, price, features)
   ```

3. **Real-time indicator calculation**:
   ```python
   # Pre-compute VWAP, Bollinger Bands, etc
   vwap = calculate_vwap(prices, volumes)
   ```

4. **Multi-timeframe analysis**:
   ```python
   # 1m, 5m, 15m, 1h candles in parallel
   ```

## Thread Safety

```python
# Queue is thread-safe (internal locks)
update_queue = Queue()  # ← thread → safe

# Deque is NOT thread-safe for iteration
# So only main thread reads deque for display

# CSV file + lock (simple but adequate)
async with self.csv_lock:
    with open(path, 'a') as f:
        csv.writer(f).writerow([ts, price])
```

## Testing

Run benchmark:
```bash
python btc_benchmark.py
```

Expected results:
- Messages/sec: 0.5-2 (depends on Binance)
- WebSocket latency: 50-150ms
- Update latency: 10-30ms
- Estimated FPS: 30-60 FPS

## References

- Binance WebSocket Docs: https://developers.binance.com/docs/binance-api/websocket-api
- asyncio: https://docs.python.org/3/library/asyncio.html
- PyQtGraph: http://www.pyqtgraph.org/
- Plotly Python: https://plotly.com/python/
