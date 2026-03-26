"""
Configuration centrale — Système d'Arbitrage Prédictif HFT Polymarket
Toutes les constantes et variables d'environnement sont ici.
"""

import os
from pathlib import Path

# ─── Binance ─────────────────────────────────────────────────────────────────
BINANCE_REST        = "https://api.binance.com"
BINANCE_WS_TICKER   = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
BINANCE_WS_BOOK     = "wss://stream.binance.com:9443/ws/btcusdt@depth5@100ms"
BINANCE_WS_AGTRADE  = "wss://stream.binance.com:9443/ws/btcusdt@aggTrade"

# ─── Polymarket CLOB ─────────────────────────────────────────────────────────
POLY_CLOB_URL       = "https://clob.polymarket.com"
POLY_GAMMA_URL      = "https://gamma-api.polymarket.com"
POLY_CHAIN_ID       = 137           # Polygon mainnet

# ─── Credentials (charger depuis .env ou variables d'environnement) ──────────
POLY_API_KEY        = os.getenv("POLY_API_KEY",     "")
POLY_SECRET         = os.getenv("POLY_SECRET",      "")
POLY_PASSPHRASE     = os.getenv("POLY_PASSPHRASE",  "")
POLY_PRIVATE_KEY    = os.getenv("POLY_PRIVATE_KEY", "")   # 0x...
POLY_WALLET_ADDRESS = os.getenv("POLY_WALLET_ADDR", "")   # 0x...

# ─── Logique de Trading ──────────────────────────────────────────────────────
POLY_TAKER_FEE      = 0.018         # 1.8% frais taker Polymarket
SAFETY_MARGIN       = 0.020         # 2.0% marge de sécurité supplémentaire
MIN_ARB_EDGE        = POLY_TAKER_FEE + SAFETY_MARGIN  # 3.8% seuil minimum

MAX_POSITION_USDC   = 50.0          # Mise maximale en USDC par trade
CONFIDENCE_BOOST    = True          # Augmenter le poids quand time_remaining < 60s
CONFIDENCE_BOOST_THRESHOLD = 60     # Secondes avant T0 pour activer le boost
CONFIDENCE_BOOST_FACTOR    = 1.15   # Multiplicateur de probabilité

# ─── Fenêtre de résolution Polymarket (5 minutes) ────────────────────────────
RESOLUTION_WINDOW_S = 300           # 5 minutes en secondes
POLY_RESOLUTION_INTERVAL = 5        # Résolution toutes les 5 minutes (minuterie)

# ─── Feature Engineering ─────────────────────────────────────────────────────
MOMENTUM_WINDOW     = 10            # Secondes pour momentum_short
VOLATILITY_WINDOW   = 30            # Secondes pour volatility_30s
PRICE_WINDOW_LIVE   = 300           # Points affichés sur le graphique live

FEATURES = [
    "delta_open",
    "time_remaining",
    "time_remaining_sq",            # Non-linéarité temporelle
    "momentum_short",
    "volatility_30s",
    "bid_ask_spread",
    "price_position",               # Position relative dans la fenêtre
    "accel",                        # Accélération du momentum
    "vol_ratio",                    # Ratio volatilité court/long terme
    "range_pct",                    # Range haut/bas de la fenêtre
]

# ─── XGBoost ─────────────────────────────────────────────────────────────────
XGB_PARAMS = {
    "n_estimators":     200,
    "max_depth":        3,           # Faible profondeur = inférence ultra-rapide
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 10,
    "gamma":            0.1,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "eval_metric":      "logloss",
    "tree_method":      "hist",      # CPU rapide (remplacer par "gpu_hist" sur VPS GPU)
    "n_jobs":           -1,
    "random_state":     42,
    "use_label_encoder": False,
}

TRAIN_DAYS          = 28
VAL_DAYS            = 2
TOTAL_HISTORY_DAYS  = TRAIN_DAYS + VAL_DAYS   # 30

# Fenêtre glissante d'entraînement (stride entre chaque window d'entraînement)
TRAIN_STRIDE_S      = 30            # Créer 1 sample toutes les 30s

# ─── Téléchargement données historiques ──────────────────────────────────────
HISTORY_FILE        = "btc_1s_history.parquet"
HISTORY_CSV_FALLBACK= "btc_1s_history.csv"
DOWNLOAD_CONCURRENCY= 8             # Requêtes parallèles Binance

# ─── Gas / Relayer ───────────────────────────────────────────────────────────
RELAYER_TIMEOUT_MS  = 200           # Seuil latence pour basculer vers self-gas
GAS_MODE            = os.getenv("GAS_MODE", "relayer")   # "relayer" | "self"

# ─── Dashboard ───────────────────────────────────────────────────────────────
DASH_PORT           = 8051          # Port différent du visualiseur existant (8050)
DASH_HOST           = "127.0.0.1"
DASH_REFRESH_MS     = 1000          # Refresh toutes les secondes

# ─── Fichiers de sortie ───────────────────────────────────────────────────────
MODEL_FILE          = "arb_xgb_model.joblib"
SCALER_FILE         = "arb_scaler.joblib"
SIGNALS_LOG         = "arb_signals.csv"
BENCHMARK_LOG       = "arb_benchmark.csv"

# ─── Vérification de l'environnement ─────────────────────────────────────────
def check_credentials() -> dict:
    """Vérifie que les credentials Polymarket sont configurés."""
    status = {
        "api_key":      bool(POLY_API_KEY),
        "secret":       bool(POLY_SECRET),
        "passphrase":   bool(POLY_PASSPHRASE),
        "private_key":  bool(POLY_PRIVATE_KEY),
        "wallet":       bool(POLY_WALLET_ADDRESS),
    }
    missing = [k for k, v in status.items() if not v]
    return {"ok": len(missing) == 0, "missing": missing, "status": status}


def load_dotenv(path: str = ".env"):
    """Charge un fichier .env dans les variables d'environnement."""
    env_path = Path(path)
    if not env_path.exists():
        return False
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"\''))
    return True
