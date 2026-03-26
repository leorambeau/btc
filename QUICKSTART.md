# 🚀 QUICKSTART - Bitcoin HFT Visualizer

## ⚡ 30 secondes pour démarrer

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Démarrer le visualiseur (Performance maximale)
```bash
python btc_hft_pyqtgraph.py
```

Vous verrez:
- 📊 Graphique temps réel du prix BTC
- 💹 Prix actuel en gros affichage
- 📁 Fichier CSV auto-généré: `btc_data_log.csv`

**Ctrl+C** pour arrêter.

---

## 📊 3 Options de visualisation

| Mode | Command | Meilleur pour |
|------|---------|---------------|
| **PyQtGraph** (⭐ Rapide) | `python btc_hft_pyqtgraph.py` | HFT temps réel, 60+ FPS |
| **Plotly Web** | `python btc_hft_standalone.py` | Analyse exploratoire |
| **Jupyter** | `from btc_hft_visualizer import BTCRealtimeVisualizer` | Notebooks interactifs |

---

## 📈 Analyser les données collectées

```bash
# Afficher statistiques
python btc_data_loader.py

# Entraîner modèle ML de prédiction
python btc_ml_model.py

# Tester latence WebSocket
python btc_benchmark.py
```

---

## 🎯 Menu interactif complet

```bash
python main.py
```

Choisissez entre:
- Démarrer visualiseur
- Analyser données
- Entraîner modèle ML
- Tester performance

---

## 💾 Fichiers générés

```
btc_data_log.csv          # Données collectées (timestamp, price)
benchmark_results.csv     # Résultats performance WebSocket
```

---

## 🔧 Configuration

Éditer `config.ini` pour:
- Nombre de points affichés (MAX_POINTS)
- FPS cible (TARGET_FPS)
- Couleurs et dimensions GUI
- Paramètres ML (lookback, training split)

---

## ❓ FAQ

**Q: Ca lag?**
A: Utiliser PyQtGraph (option 1). Plotly est plus lourd.

**Q: Comment utiliser les données pour ML?**
A: `python btc_data_loader.py` puis `python btc_ml_model.py`

**Q: Augmenter points affichés?**
A: `config.ini` → `MAX_POINTS = 200` (attention latence)

**Q: Exporter les données?**
A: Déjà en CSV! Charger avec pandas: `pd.read_csv('btc_data_log.csv')`

---

## 📡 Architecture

```
WebSocket Binance
      ↓
  asyncio stream
      ↓
  ┌─────────┐
  │ Deque   │ → CSV Writer (fond)
  │ (100pt) │
  └────┬────┘
       ↓
  PyQtGraph / Plotly / Jupyter
  (Affichage temps réel)
```

---

## 🎓 Bonus: Entraîner un modèle ML

```python
from btc_ml_model import BTCPricePredictorRF

model = BTCPricePredictorRF()
model.train("btc_data_log.csv")
model.get_feature_importance()

# Prédire
features = [sma_5, sma_10, volatility, momentum, rsi, price]
next_price = model.predict(features)
```

---

## ✅ Checklist

- [ ] `pip install -r requirements.txt`
- [ ] `python btc_hft_pyqtgraph.py` → Vérifier affichage
- [ ] Laisser tourner 5+ minutes → Collecter données
- [ ] `python btc_data_loader.py` → Vérifier CSV
- [ ] `python btc_ml_model.py` → Entraîner ML
- [ ] `python btc_benchmark.py` → Tester latence

---

Enjoy! 🚀📈
