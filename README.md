# BTC/USDT Real-time HFT Visualizer

Trois implémentations optimisées pour visualiser le prix du Bitcoin en temps réel via WebSocket Binance.

## 📋 Fichiers

### 1. **btc_hft_visualizer.py** - Jupyter Notebook
- Pour utiliser dans Jupyter/IPython
- Utilise Plotly FigureWidget
- Meilleur pour l'exploration interactive

### 2. **btc_hft_standalone.py** - Plotly Web Server
- Application standalone
- Affiche dans un navigateur
- Interface dark mode épurée
- Lance un serveur local

### 3. **btc_hft_pyqtgraph.py** - PyQtGraph GUI (Recommandé)
- Fenêtre Qt native
- **60+ FPS maintenu** ✅
- Plus rapide et léger que Plotly
- Meilleur pour HFT réel

## 🚀 Installation

```bash
pip install -r requirements.txt
```

## 🎯 Exécution

### Option 1: PyQtGraph (Performance maximale)
```bash
python btc_hft_pyqtgraph.py
```

### Option 2: Plotly Web
```bash
python btc_hft_standalone.py
```

### Option 3: Jupyter
```python
from btc_hft_visualizer import BTCRealtimeVisualizer
import asyncio

visualizer = BTCRealtimeVisualizer()
visualizer.display()
asyncio.run(visualizer.run())
```

## 📊 Caractéristiques

✅ **Architecture asynchrone** - asyncio + threading séparé pour CSV  
✅ **Fenêtre glissante 100pts** - Mémoire optimisée avec deque  
✅ **Dark Mode** - Interface noire pour réduire la fatigue oculaire  
✅ **60 FPS** - PyQtGraph maintient les performances  
✅ **CSV en fond** - Enregistrement non-bloquant des données  
✅ **WebSocket Binance** - Live feed BTC/USDT  
✅ **Reconnexion auto** - Réessai avec délai exponentiel  

## 📁 Sortie

**btc_data_log.csv**
```
timestamp,price
2026-03-25T14:32:45.123456,42567.89
2026-03-25T14:32:45.223456,42568.34
...
```

## ⚙️ Optimisations HFT

- **Deque limitée** : O(1) append/pop, mémoire constante
- **Async WebSocket** : Non-bloquant, latence minimale
- **Threading CSV** : N'impacte pas le rendu graphique
- **PyQtGraph GPU** : Rendu GPU pour vitesse maximale
- **Queue non-bloquante** : Communication thread-safe

## 🔧 Tuning

Ajuster le buffer pour plus de points (attention latence):
```python
visualizer = BTCRealtimeVisualizer(max_points=200)  # Par défaut 100
```

## 📡 Source de données

- **WebSocket**: `wss://stream.binance.com:9443/ws/btcusdt@ticker`
- **Paire**: BTC/USDT
- **Fréquence**: ~1000ms entre updates (selon Binance)

## 🎓 Préparation ML

Le CSV `btc_data_log.csv` est formaté pour un entraînement ML futur:
- Format ISO timestamp
- Prix en float
- Facile à charger avec pandas/numpy
