"""
Moteur d'Arbitrage HFT — Boucle principale temps réel

Architecture :
  Thread 1 — WebSocket Binance @aggTrade  → prix tick-by-tick
  Thread 2 — WebSocket Binance @depth5    → bid/ask spread
  Thread 3 — Polling Polymarket           → prix YES/NO toutes les 5s
  Thread 4 — ML Inference                 → predict_proba() à chaque tick
  Thread 5 — Signal Logger                → CSV + alertes

Tout est thread-safe via collections.deque et threading.Event.
"""

import asyncio
import json
import threading
import time
import csv
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from queue import Queue, Empty
from threading import Event

import websockets
import requests

from arb_config import (
    BINANCE_WS_TICKER, BINANCE_WS_BOOK,
    RESOLUTION_WINDOW_S, POLY_RESOLUTION_INTERVAL,
    MIN_ARB_EDGE, PRICE_WINDOW_LIVE,
    SIGNALS_LOG, BENCHMARK_LOG,
    check_credentials,
)
from arb_features import LiveFeatureBuffer
from arb_polymarket import PolymarketClient, MarketPrice, compute_arb_signal, ArbSignal

logger = logging.getLogger(__name__)

# ─── État partagé (thread-safe via deque + Lock) ─────────────────────────────

class EngineState:
    """
    État global partagé entre tous les threads.
    Toutes les propriétés sont thread-safe.
    """

    def __init__(self, max_points: int = PRICE_WINDOW_LIVE):
        # Prix et timestamps (pour affichage)
        self.prices     = deque(maxlen=max_points)
        self.timestamps = deque(maxlen=max_points)
        self.ai_probs   = deque(maxlen=max_points)   # Probabilité IA [0,1]

        # Valeurs courantes
        self.current_price   = 0.0
        self.current_prob    = 0.5
        self.bid_ask_spread  = 0.0
        self.best_bid        = 0.0
        self.best_ask        = 0.0

        # Fenêtre Polymarket
        self.window_open_price  = 0.0     # Prix BTC à l'ouverture de la window
        self.window_open_time   = None    # datetime UTC de l'ouverture
        self.time_remaining     = 300.0   # Secondes avant T0

        # Marché Polymarket actif
        self.active_market: MarketPrice | None = None
        self.poly_yes_price   = 0.5
        self.poly_no_price    = 0.5
        self.poly_last_update = None

        # Signaux
        self.last_signal:  ArbSignal | None = None
        self.signals_count = 0
        self.arb_detected  = False

        # Feature buffer
        self.feature_buffer = LiveFeatureBuffer(max_size=400)

        # Control
        self._lock   = threading.Lock()
        self.running = True

    def update_price(self, price: float, ts: datetime):
        """Met à jour le prix courant et le buffer ML."""
        with self._lock:
            self.current_price = price
            self.prices.append(price)
            self.timestamps.append(ts.strftime("%H:%M:%S"))
            self.feature_buffer.push(price)

    def update_book(self, bid: float, ask: float):
        """Met à jour le carnet d'ordres."""
        with self._lock:
            self.best_bid       = bid
            self.best_ask       = ask
            self.bid_ask_spread = ask - bid if ask > bid else 0.0

    def update_ai_prob(self, prob: float):
        """Met à jour la probabilité IA."""
        with self._lock:
            self.current_prob = prob
            self.ai_probs.append(prob)

    def update_poly_price(self, market: MarketPrice):
        """Met à jour le prix Polymarket."""
        with self._lock:
            self.active_market   = market
            self.poly_yes_price  = market.yes_price
            self.poly_no_price   = market.no_price
            self.poly_last_update = datetime.now(timezone.utc)

    def compute_time_remaining(self) -> float:
        """Calcule les secondes avant la prochaine résolution Polymarket."""
        now = datetime.now(timezone.utc)
        # Résolution à la prochaine minute multiple de 5
        minute = now.minute
        secs   = now.second
        next_boundary = ((minute // POLY_RESOLUTION_INTERVAL) + 1) * POLY_RESOLUTION_INTERVAL
        if next_boundary >= 60:
            next_boundary -= 60
            next_t0 = now.replace(minute=next_boundary, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_t0 = now.replace(minute=next_boundary, second=0, microsecond=0)
        remaining = (next_t0 - now).total_seconds()
        self.time_remaining = remaining
        return remaining

    def snap_window_open(self):
        """Enregistre le prix d'ouverture de la window courante (T-5min)."""
        with self._lock:
            if self.current_price > 0:
                self.window_open_price = self.current_price
                self.window_open_time  = datetime.now(timezone.utc)
                logger.info(f"[Engine] Window ouverte — BTC: ${self.current_price:,.2f}")


# ─── Thread WebSocket Binance Ticker ─────────────────────────────────────────

async def _binance_ticker_stream(state: EngineState):
    """
    Stream Binance @aggTrade pour le prix tick-by-tick.
    Reconnexion automatique avec backoff exponentiel.
    """
    uri            = BINANCE_WS_TICKER
    reconnect_delay = 1.0

    while state.running:
        try:
            async with websockets.connect(uri, ping_interval=20) as ws:
                reconnect_delay = 1.0
                logger.info("[Binance] Connecté au stream ticker")

                while state.running:
                    raw  = await asyncio.wait_for(ws.recv(), timeout=30)
                    msg  = json.loads(raw)

                    price = float(msg.get("c", 0))          # 'c' = last price
                    ts_ms = int(msg.get("E", 0))
                    ts    = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

                    if price > 0:
                        state.update_price(price, ts)

        except asyncio.TimeoutError:
            logger.warning("[Binance] Timeout ticker — reconnexion")
        except Exception as e:
            logger.warning(f"[Binance] Erreur ticker: {e} — reconnexion dans {reconnect_delay:.0f}s")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)


async def _binance_book_stream(state: EngineState):
    """
    Stream Binance @depth5@100ms pour le bid/ask spread en temps réel.
    """
    uri            = BINANCE_WS_BOOK
    reconnect_delay = 1.0

    while state.running:
        try:
            async with websockets.connect(uri, ping_interval=20) as ws:
                reconnect_delay = 1.0
                logger.info("[Binance] Connecté au stream orderbook")

                while state.running:
                    raw  = await asyncio.wait_for(ws.recv(), timeout=30)
                    msg  = json.loads(raw)

                    bids = msg.get("b", [])
                    asks = msg.get("a", [])

                    if bids and asks:
                        best_bid = float(bids[0][0])
                        best_ask = float(asks[0][0])
                        state.update_book(best_bid, best_ask)

        except asyncio.TimeoutError:
            logger.warning("[Binance] Timeout book — reconnexion")
        except Exception as e:
            logger.warning(f"[Binance] Erreur book: {e} — reconnexion dans {reconnect_delay:.0f}s")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)


# ─── Thread Polling Polymarket ────────────────────────────────────────────────

def _polymarket_poller(state: EngineState, client: PolymarketClient, poll_interval: float = 5.0):
    """
    Interroge Polymarket toutes les `poll_interval` secondes pour :
    1. Trouver/rafraîchir le marché BTC 5-min actif
    2. Mettre à jour le prix YES/NO
    """
    current_market_id    = None
    current_yes_token_id = None
    current_gamma_id     = None

    while state.running:
        try:
            # Rafraîchir la liste des marchés toutes les 60s
            if current_market_id is None or int(time.time()) % 60 == 0:
                markets = client.find_btc_5min_markets(limit=1)
                if markets:
                    market = markets[0]
                    current_market_id    = market.condition_id
                    current_yes_token_id = market.yes_token_id
                    current_gamma_id     = market.market_id   # ID numérique Gamma
                    state.update_poly_price(market)
                    logger.info(
                        f"[Poly] Marché: {market.question[:50]}"
                        f" — YES={market.yes_price:.3f} NO={market.no_price:.3f}"
                    )
                else:
                    logger.debug("[Poly] Aucun marché actif trouvé")

            elif current_market_id:
                # Rafraîchir le prix (CLOB en priorité, Gamma en fallback)
                price_obj = client.get_market_price(
                    current_market_id,
                    current_yes_token_id or "",
                    current_gamma_id     or "",
                )
                if price_obj:
                    if state.active_market:
                        price_obj.question     = state.active_market.question
                        price_obj.market_id    = state.active_market.market_id
                        price_obj.yes_token_id = state.active_market.yes_token_id
                        price_obj.no_token_id  = state.active_market.no_token_id
                    state.update_poly_price(price_obj)

        except Exception as e:
            logger.error(f"[Poly] Erreur polling: {e}")

        time.sleep(poll_interval)


# ─── Thread ML Inference ─────────────────────────────────────────────────────

def _inference_loop(state: EngineState, model, signal_queue: Queue):
    """
    Boucle d'inférence ML — tourne aussi vite que possible.
    Calcule predict_proba() dès qu'un nouveau prix est disponible.
    """
    last_price    = -1.0
    window_open_timer = 0.0

    while state.running:
        price = state.current_price

        # Attendre un nouveau prix
        if price == last_price or price == 0:
            time.sleep(0.05)
            continue
        last_price = price

        # Calculer time_remaining
        time_remaining = state.compute_time_remaining()

        # Détecter la nouvelle window (quand time_remaining reset à ~300s)
        if time_remaining > 295 and (time.time() - window_open_timer) > 30:
            state.snap_window_open()
            window_open_timer = time.time()

        # Calculer les features
        feat = state.feature_buffer.compute(
            window_open_price = state.window_open_price if state.window_open_price > 0 else price,
            time_remaining    = time_remaining,
            bid_ask_spread    = state.bid_ask_spread,
        )

        if feat is None:
            time.sleep(0.05)
            continue

        # Inférence XGBoost
        ia_prob = model.predict_proba_live(feat, time_remaining=time_remaining)
        state.update_ai_prob(ia_prob)

        # Calcul du signal d'arbitrage
        if state.active_market and state.active_market.yes_price > 0:
            signal = compute_arb_signal(
                ia_prob        = ia_prob,
                market         = state.active_market,
                time_remaining = time_remaining,
                min_edge       = MIN_ARB_EDGE,
            )
            if signal:
                state.last_signal  = signal
                state.arb_detected = True
                state.signals_count += 1
                signal_queue.put(signal)
                logger.info(
                    f"[ARB_DETECTED] {signal.direction} | "
                    f"IA={ia_prob:.3f} | POLY={signal.poly_price:.3f} | "
                    f"EDGE={signal.edge:.3f} | T-{time_remaining:.0f}s"
                )
            else:
                state.arb_detected = False


# ─── Thread Signal Logger ─────────────────────────────────────────────────────

def _signal_logger(signal_queue: Queue, client: PolymarketClient, dry_run: bool = True):
    """
    Consomme les signaux d'arbitrage, les log en CSV et optionnellement place les ordres.

    Args:
        dry_run: Si True, logue seulement sans placer d'ordre réel
    """
    log_path = Path(SIGNALS_LOG)
    write_header = not log_path.exists()

    while True:
        try:
            signal: ArbSignal = signal_queue.get(timeout=1)

            # Log CSV
            with open(log_path, "a", newline="") as f:
                w = csv.writer(f)
                if write_header:
                    w.writerow([
                        "timestamp", "direction", "ia_prob", "poly_price",
                        "edge", "time_remaining", "position_usdc",
                        "order_id", "order_ok", "latency_ms", "dry_run"
                    ])
                    write_header = False

                if dry_run:
                    w.writerow([
                        signal.timestamp.isoformat(),
                        signal.direction, f"{signal.ia_prob:.4f}",
                        f"{signal.poly_price:.4f}", f"{signal.edge:.4f}",
                        f"{signal.time_remaining:.0f}", f"{signal.position_usdc:.2f}",
                        "", "", "", "TRUE"
                    ])
                else:
                    result = client.place_order(signal)
                    w.writerow([
                        signal.timestamp.isoformat(),
                        signal.direction, f"{signal.ia_prob:.4f}",
                        f"{signal.poly_price:.4f}", f"{signal.edge:.4f}",
                        f"{signal.time_remaining:.0f}", f"{signal.position_usdc:.2f}",
                        result.order_id, result.ok, f"{result.latency_ms:.1f}", "FALSE"
                    ])
                    if result.ok:
                        logger.info(f"[Order] ✅ Ordre placé — ID: {result.order_id} ({result.latency_ms:.0f}ms)")
                    else:
                        logger.error(f"[Order] ❌ Échec: {result.error}")

        except Empty:
            continue
        except Exception as e:
            logger.error(f"[Logger] Erreur: {e}")


# ─── Moteur principal ─────────────────────────────────────────────────────────

class HFTArbitrageEngine:
    """
    Orchestre tous les threads du système d'arbitrage.
    """

    def __init__(self, model, dry_run: bool = True):
        self.model        = model
        self.dry_run      = dry_run
        self.state        = EngineState()
        self.poly_client  = PolymarketClient()
        self.signal_queue = Queue()
        self._threads     = []

        if dry_run:
            logger.info("[Engine] Mode DRY RUN — aucun ordre réel ne sera placé")
        else:
            creds = check_credentials()
            if not creds["ok"]:
                raise RuntimeError(
                    f"[Engine] Credentials manquants: {creds['missing']}\n"
                    f"Configurez votre .env ou variables d'environnement"
                )
            logger.info("[Engine] Mode LIVE — ordres réels activés")

    def start(self):
        """Lance tous les threads et boucles async."""
        logger.info("\n[Engine] ═══ Démarrage du Moteur d'Arbitrage HFT ═══")
        logger.info(f"[Engine] Modèle    : {'CHARGÉ' if self.model.trained else 'NON ENTRAÎNÉ'}")
        logger.info(f"[Engine] Seuil ARB : {MIN_ARB_EDGE:.1%} (fees {0.018:.1%} + marge {0.020:.1%})")
        logger.info(f"[Engine] Dry Run   : {self.dry_run}")

        # Thread Polymarket poller
        t_poly = threading.Thread(
            target=_polymarket_poller,
            args=(self.state, self.poly_client, 5.0),
            daemon=True, name="PolyPoller"
        )
        t_poly.start()
        self._threads.append(t_poly)

        # Thread ML inference
        t_infer = threading.Thread(
            target=_inference_loop,
            args=(self.state, self.model, self.signal_queue),
            daemon=True, name="MLInference"
        )
        t_infer.start()
        self._threads.append(t_infer)

        # Thread signal logger
        t_log = threading.Thread(
            target=_signal_logger,
            args=(self.signal_queue, self.poly_client, self.dry_run),
            daemon=True, name="SignalLogger"
        )
        t_log.start()
        self._threads.append(t_log)

        # Thread WebSocket Binance (asyncio dans son propre thread)
        t_ws = threading.Thread(
            target=self._run_websockets,
            daemon=True, name="BinanceWS"
        )
        t_ws.start()
        self._threads.append(t_ws)

        logger.info(f"[Engine] {len(self._threads)} threads démarrés — En attente de données...\n")

    def stop(self):
        """Arrête proprement le moteur."""
        logger.info("[Engine] Arrêt en cours...")
        self.state.running = False

    def _run_websockets(self):
        """Lance les deux streams WebSocket dans un event loop dédié."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(asyncio.gather(
                _binance_ticker_stream(self.state),
                _binance_book_stream(self.state),
            ))
        finally:
            loop.close()

    @property
    def state_snapshot(self) -> dict:
        """Retourne un snapshot de l'état pour le dashboard (thread-safe)."""
        s = self.state
        return {
            "price":          s.current_price,
            "ai_prob":        s.current_prob,
            "bid_ask_spread": s.bid_ask_spread,
            "time_remaining": s.time_remaining,
            "poly_yes":       s.poly_yes_price,
            "poly_no":        s.poly_no_price,
            "arb_detected":   s.arb_detected,
            "signals_count":  s.signals_count,
            "prices":         list(s.prices),
            "timestamps":     list(s.timestamps),
            "ai_probs":       list(s.ai_probs),
            "last_signal":        s.last_signal,
            "poly_market":        s.active_market.question[:60] if s.active_market else "Recherche...",
            "window_open_price":  s.window_open_price,
        }
