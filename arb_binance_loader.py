"""
Téléchargement historique BTCUSDT — Granularité 1 seconde (30 jours)
Utilise aiohttp en parallèle pour minimiser le temps de téléchargement.

Usage:
    python arb_binance_loader.py
    → Génère btc_1s_history.parquet (~300 MB)
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

from arb_config import (
    BINANCE_REST, HISTORY_FILE, HISTORY_CSV_FALLBACK,
    TOTAL_HISTORY_DAYS, DOWNLOAD_CONCURRENCY
)

# ─── Constantes API ───────────────────────────────────────────────────────────
KLINES_ENDPOINT = f"{BINANCE_REST}/api/v3/klines"
KLINES_LIMIT    = 1000          # Max par requête
KLINE_INTERVAL  = "1s"          # Granularité 1 seconde
WEIGHT_PER_REQ  = 10            # Poids Binance pour limit=1000
MAX_WEIGHT_MIN  = 5000          # Marge de sécurité (max officiel: 6000/min)

KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_base", "taker_quote", "ignore"
]


async def fetch_chunk(
    session: aiohttp.ClientSession,
    start_ms: int,
    end_ms: int,
    semaphore: asyncio.Semaphore,
    rate_limiter: asyncio.Queue,
) -> list:
    """
    Fetch un bloc de klines 1s entre start_ms et end_ms.
    Gère automatiquement les erreurs 429 (rate limit).
    """
    params = {
        "symbol":    "BTCUSDT",
        "interval":  KLINE_INTERVAL,
        "startTime": start_ms,
        "endTime":   end_ms,
        "limit":     KLINES_LIMIT,
    }
    async with semaphore:
        for attempt in range(6):
            try:
                # Token bucket simple pour respecter le rate limit
                await rate_limiter.get()
                async with session.get(
                    KLINES_ENDPOINT,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429 or resp.status == 418:
                        retry_after = int(resp.headers.get("Retry-After", 60))
                        print(f"  [RateLimit] Pause {retry_after}s...")
                        await asyncio.sleep(retry_after)
                    else:
                        print(f"  [HTTP {resp.status}] attempt {attempt+1}")
                        await asyncio.sleep(2 ** attempt)
            except asyncio.TimeoutError:
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                print(f"  [Error] {e} — attempt {attempt+1}")
                await asyncio.sleep(2 ** attempt)
    return []


async def _rate_limiter_producer(queue: asyncio.Queue, rate: float):
    """
    Injecte des tokens dans la queue à une vitesse constante (rate tokens/seconde).
    Empêche de dépasser le rate limit Binance.
    """
    interval = 1.0 / rate
    while True:
        await queue.put(1)
        await asyncio.sleep(interval)


async def download_history(
    days: int = TOTAL_HISTORY_DAYS,
    output_file: str = HISTORY_FILE,
    force: bool = False,
) -> pd.DataFrame:
    """
    Télécharge `days` jours de klines 1s BTCUSDT depuis Binance.

    Args:
        days:        Nombre de jours à télécharger (défaut: 30)
        output_file: Fichier de sortie (.parquet ou .csv)
        force:       Re-télécharger même si le fichier existe

    Returns:
        DataFrame avec colonnes: open_time, open, high, low, close, volume
    """
    output_path = Path(output_file)

    # Cache: ne pas re-télécharger si le fichier est récent (< 1 heure)
    if not force and output_path.exists():
        age_h = (time.time() - output_path.stat().st_mtime) / 3600
        if age_h < 1:
            print(f"[Loader] Cache frais ({age_h:.1f}h) → chargement depuis {output_file}")
            return _load_cached(output_path)
        else:
            print(f"[Loader] Cache obsolète ({age_h:.1f}h) → re-téléchargement")

    end_dt   = datetime.now(timezone.utc).replace(microsecond=0)
    start_dt = end_dt - timedelta(days=days)

    end_ms   = int(end_dt.timestamp()   * 1000)
    start_ms = int(start_dt.timestamp() * 1000)

    # Créer les chunks (1000 secondes = 1 requête)
    chunk_ms = KLINES_LIMIT * 1000          # 1000s en millisecondes
    chunks   = []
    t = start_ms
    while t < end_ms:
        chunk_end = min(t + chunk_ms - 1, end_ms)
        chunks.append((t, chunk_end))
        t += chunk_ms

    total_chunks = len(chunks)
    total_pts    = total_chunks * KLINES_LIMIT
    print(f"\n[Loader] === Téléchargement {days} jours de données 1s BTCUSDT ===")
    print(f"[Loader] Période  : {start_dt.strftime('%Y-%m-%d')} → {end_dt.strftime('%Y-%m-%d')}")
    print(f"[Loader] Chunks   : {total_chunks:,} requêtes (~{total_pts/1e6:.1f}M points)")
    print(f"[Loader] Parallèle: {DOWNLOAD_CONCURRENCY} connexions simultanées\n")

    semaphore    = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)
    rate_queue   = asyncio.Queue(maxsize=50)

    # Rate: max_weight/min ÷ weight_per_req ÷ 60 = tokens/seconde
    tokens_per_sec = (MAX_WEIGHT_MIN / WEIGHT_PER_REQ) / 60  # ~8.3 req/s
    print(f"[Loader] Rate limit: {tokens_per_sec:.1f} req/s")

    all_rows = []
    t0       = time.time()

    connector = aiohttp.TCPConnector(limit=DOWNLOAD_CONCURRENCY + 5)
    async with aiohttp.ClientSession(connector=connector) as session:

        # Démarrer le producer de tokens en arrière-plan
        rate_task = asyncio.create_task(
            _rate_limiter_producer(rate_queue, tokens_per_sec)
        )

        tasks = [
            fetch_chunk(session, s, e, semaphore, rate_queue)
            for s, e in chunks
        ]

        completed = 0
        for coro in asyncio.as_completed(tasks):
            rows = await coro
            all_rows.extend(rows)
            completed += 1

            if completed % 200 == 0 or completed == total_chunks:
                elapsed  = time.time() - t0
                pct      = completed / total_chunks * 100
                eta      = elapsed / completed * (total_chunks - completed)
                print(
                    f"[Loader] {pct:5.1f}% — {completed:,}/{total_chunks:,} chunks"
                    f" — {len(all_rows)/1e3:.0f}k pts"
                    f" — ETA {eta:.0f}s"
                )

        rate_task.cancel()

    if not all_rows:
        raise RuntimeError("[Loader] Aucune donnée téléchargée. Vérifiez l'accès réseau.")

    # Construire le DataFrame
    df = pd.DataFrame(all_rows, columns=KLINE_COLS)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df = (
        df[["open_time", "open", "high", "low", "close", "volume"]]
        .sort_values("open_time")
        .drop_duplicates("open_time")
        .reset_index(drop=True)
    )

    elapsed = time.time() - t0
    print(f"\n[Loader] Terminé en {elapsed:.1f}s")
    print(f"[Loader] {len(df):,} lignes — {df['open_time'].min()} → {df['open_time'].max()}")

    # Sauvegarde
    try:
        df.to_parquet(output_path, index=False)
        size_mb = output_path.stat().st_size / 1e6
        print(f"[Loader] Sauvegardé → {output_file} ({size_mb:.1f} MB)")
    except Exception:
        csv_path = HISTORY_CSV_FALLBACK
        df.to_csv(csv_path, index=False)
        print(f"[Loader] Parquet indisponible → sauvegardé CSV: {csv_path}")

    return df


def _load_cached(path: Path) -> pd.DataFrame:
    """Charge le fichier cache (parquet ou csv)."""
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, parse_dates=["open_time"])
    print(f"[Loader] {len(df):,} lignes chargées depuis le cache.")
    return df


def load_or_download(days: int = TOTAL_HISTORY_DAYS) -> pd.DataFrame:
    """Point d'entrée principal — charge le cache ou télécharge."""
    path = Path(HISTORY_FILE)
    if path.exists():
        return _load_cached(path)
    csv_path = Path(HISTORY_CSV_FALLBACK)
    if csv_path.exists():
        return _load_cached(csv_path)
    return asyncio.run(download_history(days=days))


if __name__ == "__main__":
    df = asyncio.run(download_history(days=TOTAL_HISTORY_DAYS, force=True))
    print(df.tail())
    print(f"\nColonnes: {df.columns.tolist()}")
    print(f"Types:    {df.dtypes.to_dict()}")
