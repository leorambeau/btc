"""
Feature Engineering — Fenêtres 5 minutes pour la prédiction UP/DOWN BTC

Chaque sample représente un snapshot à l'intérieur d'une fenêtre de 5 min :
  - window_start = T-5min (ouverture du marché Polymarket)
  - window_end   = T0      (résolution Chainlink)
  - t            = instant courant (T-5min ≤ t < T0)

Target : 1 si prix[T0] ≥ prix[T-5min], sinon 0
"""

import numpy as np
import pandas as pd
from typing import Tuple

from arb_config import (
    RESOLUTION_WINDOW_S, TRAIN_DAYS, VAL_DAYS,
    MOMENTUM_WINDOW, VOLATILITY_WINDOW, TRAIN_STRIDE_S, FEATURES
)


# ─── Construction du dataset d'entraînement ──────────────────────────────────

def build_training_dataset(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Construit les datasets train/val à partir de l'historique 1s.

    Stratégie :
    - Windows de 5 min (300s) avec stride de TRAIN_STRIDE_S secondes
    - Pour chaque window, 5 snapshots à des time_remaining variés (en fin de window)
    - Split temporel : 28 jours train, 2 jours val

    Returns:
        df_train, df_val  — DataFrames avec colonnes FEATURES + "target"
    """
    prices  = df["close"].values.astype(np.float64)
    n       = len(prices)
    W       = RESOLUTION_WINDOW_S  # 300

    # Split temporel (pas de data leakage)
    split_idx = int(len(df) * TRAIN_DAYS / (TRAIN_DAYS + VAL_DAYS))  # 28/30

    print(f"[Features] {n:,} ticks — split à l'index {split_idx:,} ({TRAIN_DAYS}j train / {VAL_DAYS}j val)")

    train_records = _extract_windows(prices, 0,         split_idx, W)
    val_records   = _extract_windows(prices, split_idx, n,         W)

    df_train = pd.DataFrame(train_records, columns=FEATURES + ["target"])
    df_val   = pd.DataFrame(val_records,   columns=FEATURES + ["target"])

    print(f"[Features] Train : {len(df_train):,} samples | Val : {len(df_val):,} samples")
    print(f"[Features] Distribution train — UP: {df_train['target'].mean():.2%} / DOWN: {1-df_train['target'].mean():.2%}")

    return df_train, df_val


def _extract_windows(prices: np.ndarray, start: int, end: int, W: int) -> list:
    """
    Extrait les features pour toutes les windows dans [start, end].
    Stride = TRAIN_STRIDE_S secondes entre chaque window.

    Pour chaque window, on prend 5 snapshots :
      t = [0.3, 0.5, 0.7, 0.85, 0.95] * W (exprime la progression dans la window)
    """
    records      = []
    stride       = TRAIN_STRIDE_S
    snapshots_pct = [0.3, 0.5, 0.7, 0.85, 0.95]  # Instants relatifs dans la window

    for w_end in range(start + W, end, stride):
        w_start  = w_end - W
        p_open   = prices[w_start]
        p_close  = prices[w_end]
        target   = 1 if p_close >= p_open else 0

        for pct in snapshots_pct:
            t = int(w_start + pct * W)
            feat = _compute_features(prices, t, w_start, w_end)
            if feat is not None:
                records.append(feat + [target])

    return records


# ─── Calcul des features (utilisé aussi en temps réel) ───────────────────────

def _compute_features(
    prices: np.ndarray,
    t: int,
    w_start: int,
    w_end: int,
) -> list | None:
    """
    Calcule le vecteur de features à l'instant t dans la window [w_start, w_end].
    Retourne None si les données sont insuffisantes.
    """
    if t < VOLATILITY_WINDOW or t < w_start or t >= w_end:
        return None

    p_t    = prices[t]
    p_open = prices[w_start]

    if p_open == 0 or p_t == 0:
        return None

    time_remaining    = float(w_end - t)
    time_remaining_sq = time_remaining ** 2

    # delta_open : variation depuis l'ouverture de la window
    delta_open = (p_t / p_open) - 1.0

    # momentum_short : variation sur les N dernières secondes
    t_mom = max(0, t - MOMENTUM_WINDOW)
    momentum_short = (p_t / prices[t_mom]) - 1.0 if prices[t_mom] > 0 else 0.0

    # volatility_30s : écart-type normalisé sur les 30 derniers ticks
    t_vol = max(0, t - VOLATILITY_WINDOW)
    vol_prices    = prices[t_vol:t + 1]
    volatility_30s = float(np.std(vol_prices)) / p_t if len(vol_prices) > 1 else 0.0

    # bid_ask_spread : placeholder (mis à jour par le live feed)
    bid_ask_spread = 0.0

    # price_position : position dans le range haut/bas de la window courante
    win_slice  = prices[w_start:t + 1]
    win_min    = float(np.min(win_slice))
    win_max    = float(np.max(win_slice))
    range_span = win_max - win_min
    price_position = (p_t - win_min) / range_span if range_span > 1e-8 else 0.5

    # accel : différence de momentum (momentum actuel - momentum il y a 10s)
    if t >= MOMENTUM_WINDOW * 2:
        t_prev = t - MOMENTUM_WINDOW
        mom_prev = (prices[t_prev] / prices[max(0, t_prev - MOMENTUM_WINDOW)]) - 1.0
        accel = momentum_short - mom_prev
    else:
        accel = 0.0

    # vol_ratio : volatilité court terme / long terme
    short_std = float(np.std(prices[max(0, t - 10):t + 1]))
    long_std  = float(np.std(prices[max(0, t - 60):t + 1]))
    vol_ratio = short_std / (long_std + 1e-10)

    # range_pct : (high - low) / open sur la window
    range_pct = range_span / p_open if p_open > 0 else 0.0

    return [
        delta_open,
        time_remaining,
        time_remaining_sq,
        momentum_short,
        volatility_30s,
        bid_ask_spread,
        price_position,
        accel,
        vol_ratio,
        range_pct,
    ]


# ─── Inference en temps réel ─────────────────────────────────────────────────

class LiveFeatureBuffer:
    """
    Buffer circulaire maintenu en temps réel pour calculer les features
    à chaque tick WebSocket.
    """

    def __init__(self, max_size: int = 400):
        self.prices = np.zeros(max_size, dtype=np.float64)
        self.max_size = max_size
        self._ptr    = 0
        self._count  = 0

    def push(self, price: float):
        self.prices[self._ptr] = price
        self._ptr   = (self._ptr + 1) % self.max_size
        self._count = min(self._count + 1, self.max_size)

    @property
    def count(self) -> int:
        return self._count

    def _get_ordered(self) -> np.ndarray:
        """Retourne les prix dans l'ordre chronologique."""
        if self._count < self.max_size:
            return self.prices[:self._count]
        return np.roll(self.prices, -self._ptr)

    def compute(
        self,
        window_open_price: float,
        time_remaining: float,
        bid_ask_spread: float = 0.0,
    ) -> np.ndarray | None:
        """
        Calcule le vecteur de features pour une inférence immédiate.

        Args:
            window_open_price: Prix BTC au début de la window Polymarket (T-5min)
            time_remaining:    Secondes restantes avant T0
            bid_ask_spread:    Spread bid/ask actuel (0 si non disponible)

        Returns:
            np.ndarray de shape (1, n_features) ou None si données insuffisantes
        """
        if self._count < VOLATILITY_WINDOW:
            return None

        arr    = self._get_ordered()
        p_t    = arr[-1]
        p_open = window_open_price

        if p_open == 0 or p_t == 0:
            return None

        time_remaining_sq = time_remaining ** 2
        delta_open        = (p_t / p_open) - 1.0

        t_mom           = max(0, len(arr) - MOMENTUM_WINDOW - 1)
        momentum_short  = (p_t / arr[t_mom]) - 1.0 if arr[t_mom] > 0 else 0.0

        vol_slice      = arr[max(0, len(arr) - VOLATILITY_WINDOW):]
        volatility_30s = float(np.std(vol_slice)) / p_t if len(vol_slice) > 1 else 0.0

        # Price position dans la window
        win_min, win_max = float(np.min(arr)), float(np.max(arr))
        range_span       = win_max - win_min
        price_position   = (p_t - win_min) / range_span if range_span > 1e-8 else 0.5

        if len(arr) >= MOMENTUM_WINDOW * 2:
            t_prev   = max(0, len(arr) - MOMENTUM_WINDOW - 1)
            t_pp     = max(0, t_prev - MOMENTUM_WINDOW)
            mom_prev = (arr[t_prev] / arr[t_pp]) - 1.0 if arr[t_pp] > 0 else 0.0
            accel    = momentum_short - mom_prev
        else:
            accel = 0.0

        short_std  = float(np.std(arr[max(0, len(arr) - 10):]))
        long_std   = float(np.std(arr[max(0, len(arr) - 60):]))
        vol_ratio  = short_std / (long_std + 1e-10)

        range_pct  = range_span / p_open if p_open > 0 else 0.0

        feat = np.array([[
            delta_open,
            time_remaining,
            time_remaining_sq,
            momentum_short,
            volatility_30s,
            bid_ask_spread,
            price_position,
            accel,
            vol_ratio,
            range_pct,
        ]], dtype=np.float32)

        return feat


if __name__ == "__main__":
    from arb_binance_loader import load_or_download
    import time

    print("Chargement des données historiques...")
    df_hist = load_or_download()

    t0 = time.time()
    df_train, df_val = build_training_dataset(df_hist)
    print(f"Feature engineering terminé en {time.time()-t0:.1f}s")
    print(df_train.describe())
