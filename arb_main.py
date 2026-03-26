"""
Point d'entrée principal — Système d'Arbitrage Prédictif HFT BTC/Polymarket

Usage:
    python arb_main.py

Menu :
  1. Télécharger données historiques (30 jours, 1s)
  2. Entraîner le modèle XGBoost
  3. Lancer le trading en mode DRY RUN (sans ordres réels)
  4. Lancer le trading LIVE (ordres réels — credentials requis)
  5. Benchmark latence WebSocket
  6. Vérifier la configuration

Architecture déployable sur VPS (Espagne / Singapour) :
    export POLY_API_KEY=...
    export POLY_SECRET=...
    export POLY_PASSPHRASE=...
    export POLY_PRIVATE_KEY=0x...
    export POLY_WALLET_ADDR=0x...
    nohup python arb_main.py &
"""

import sys
import signal
import logging
import threading
from pathlib import Path

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("arb_engine.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


# ─── Chargement config + .env ─────────────────────────────────────────────────
from arb_config import load_dotenv, check_credentials, DASH_PORT, DASH_HOST
load_dotenv(".env")   # Charge le .env si présent (silencieux sinon)


# ─── Menu principal ──────────────────────────────────────────────────────────

BANNER = r"""
╔═══════════════════════════════════════════════════════════╗
║   ARB HFT — Système d'Arbitrage Prédictif                ║
║   BTC/USDT × Polymarket (Résolution Chainlink)           ║
╚═══════════════════════════════════════════════════════════╝
"""

MENU = """
  1  Télécharger les données historiques  (30j × 1s Binance)
  2  Entraîner le modèle XGBoost          (28j train / 2j val)
  3  Lancer le trading — DRY RUN          (aucun ordre réel)
  4  Lancer le trading — LIVE             (ordres réels)
  5  Benchmark latence WebSocket
  6  Vérifier la configuration / credentials
  0  Quitter
"""


def print_menu():
    print(MENU)
    return input("  Choix (0-6) : ").strip()


# ─── Actions ─────────────────────────────────────────────────────────────────

def action_download():
    """Télécharge 30 jours de klines 1s depuis Binance."""
    import asyncio
    from arb_binance_loader import download_history
    from arb_config import TOTAL_HISTORY_DAYS

    print(f"\nTéléchargement de {TOTAL_HISTORY_DAYS} jours de données 1s...")
    print("Cela prend environ 3-5 minutes selon la connexion.\n")

    force = input("Re-télécharger même si le cache existe ? (y/N) : ").lower() == "y"
    asyncio.run(download_history(days=TOTAL_HISTORY_DAYS, force=force))


def action_train():
    """Entraîne le modèle XGBoost (pipeline complet)."""
    from arb_xgboost import train_full_pipeline
    model = train_full_pipeline()
    print(f"\nMétriques : {model.metrics}")
    return model


def action_run(dry_run: bool = True):
    """Lance le système d'arbitrage complet avec dashboard Plotly."""
    from arb_xgboost import load_or_train, BTCDirectionModel
    from arb_engine import HFTArbitrageEngine
    from arb_dashboard import ArbDashboard

    # Vérifications pré-lancement
    if not dry_run:
        creds = check_credentials()
        if not creds["ok"]:
            print(f"\nCredentials manquants : {creds['missing']}")
            print("Configurez votre fichier .env ou les variables d'environnement.")
            print("Exemple .env :")
            print("  POLY_API_KEY=votre_cle")
            print("  POLY_SECRET=votre_secret")
            print("  POLY_PASSPHRASE=votre_passphrase")
            print("  POLY_PRIVATE_KEY=0x...")
            print("  POLY_WALLET_ADDR=0x...")
            return

    # Charger ou entraîner le modèle
    print("\nChargement du modèle...")
    model = load_or_train()

    if not model.trained:
        print("Modèle non disponible — lancez d'abord l'option 2 (entraînement).")
        return

    mode_str = "DRY RUN" if dry_run else "LIVE"
    print(f"\nDémarrage en mode {mode_str}...")

    # Lancer le moteur
    engine = HFTArbitrageEngine(model=model, dry_run=dry_run)
    engine.start()

    # Gestion Ctrl+C
    stop_event = threading.Event()
    def _handle_sigint(sig, frame):
        print("\n\nArrêt demandé...")
        engine.stop()
        stop_event.set()
    signal.signal(signal.SIGINT, _handle_sigint)

    # Lancer le dashboard Dash dans le thread principal
    # (Dash/Flask doit tourner dans le thread principal)
    try:
        dashboard = ArbDashboard(engine)
        dashboard.run(open_browser=True)
    except KeyboardInterrupt:
        engine.stop()
        print("\nArrêt du moteur.")


def action_benchmark():
    """Mesure la latence WebSocket Binance (30 secondes)."""
    import asyncio
    import json
    import time
    import websockets

    async def _run():
        uri         = "wss://stream.binance.com:9443/ws/btcusdt@aggTrade"
        latencies   = []
        t_start     = time.time()
        print("\nBenchmark WebSocket Binance — 30 secondes...\n")

        async with websockets.connect(uri) as ws:
            while time.time() - t_start < 30:
                t0  = time.perf_counter()
                raw = await ws.recv()
                lat = (time.perf_counter() - t0) * 1000
                latencies.append(lat)

                msg   = json.loads(raw)
                price = float(msg.get("p", 0))
                print(f"  ${price:,.2f}  latence={lat:.2f}ms", end="\r")

        if latencies:
            import statistics
            print(f"\n\nRésultats sur {len(latencies)} messages :")
            print(f"  Médiane    : {statistics.median(latencies):.2f}ms")
            print(f"  Moyenne    : {statistics.mean(latencies):.2f}ms")
            print(f"  Min        : {min(latencies):.2f}ms")
            print(f"  Max        : {max(latencies):.2f}ms")
            print(f"  P99        : {sorted(latencies)[int(len(latencies)*0.99)]:.2f}ms")

    asyncio.run(_run())


def action_check_config():
    """Vérifie la configuration et les dépendances."""
    print("\n═══ Vérification de la configuration ═══\n")

    # Credentials Polymarket
    creds = check_credentials()
    print("Credentials Polymarket :")
    for k, v in creds["status"].items():
        status = "✅" if v else "❌"
        print(f"  {status} {k}")

    # Dépendances Python
    print("\nDépendances :")
    deps = [
        ("xgboost",         "XGBoost (modèle ML)"),
        ("sklearn",         "scikit-learn (métriques + calibration)"),
        ("aiohttp",         "aiohttp (téléchargement async)"),
        ("websockets",      "websockets (stream Binance)"),
        ("pandas",          "pandas (DataFrames)"),
        ("numpy",           "numpy (calculs vectoriels)"),
        ("plotly",          "plotly (graphiques)"),
        ("dash",            "dash (dashboard web)"),
        ("joblib",          "joblib (persistence modèle)"),
        ("py_clob_client",  "py-clob-client (Polymarket CLOB)"),
        ("eth_account",     "eth_account/web3 (signature EIP-712)"),
        ("pyarrow",         "pyarrow (format parquet)"),
    ]
    for module, desc in deps:
        try:
            __import__(module)
            print(f"  ✅ {desc}")
        except ImportError:
            print(f"  ❌ {desc}  → pip install {module.replace('_','-')}")

    # Fichiers
    print("\nFichiers :")
    files_to_check = [
        ("btc_1s_history.parquet", "Données historiques 30j"),
        ("arb_xgb_model.joblib",   "Modèle XGBoost"),
        ("arb_scaler.joblib",      "Scaler"),
        (".env",                   "Fichier credentials"),
    ]
    for fname, desc in files_to_check:
        exists = Path(fname).exists()
        size   = f" ({Path(fname).stat().st_size/1e6:.1f}MB)" if exists else ""
        print(f"  {'✅' if exists else '❌'} {desc}{size}")

    # Config réseau (ping Binance)
    print("\nConnectivité :")
    try:
        import requests
        r = requests.get("https://api.binance.com/api/v3/ping", timeout=5)
        print(f"  ✅ Binance API ({r.elapsed.total_seconds()*1000:.0f}ms)")
    except Exception as e:
        print(f"  ❌ Binance API — {e}")

    try:
        import requests
        r = requests.get("https://clob.polymarket.com/", timeout=5)
        print(f"  ✅ Polymarket CLOB ({r.elapsed.total_seconds()*1000:.0f}ms)")
    except Exception as e:
        print(f"  ❌ Polymarket CLOB — {e}")

    print()


# ─── Boucle principale ────────────────────────────────────────────────────────

def main():
    print(BANNER)

    # Auto-check au démarrage
    creds = check_credentials()
    if not creds["ok"]:
        print(f"  ⚠️  Credentials Polymarket manquants: {creds['missing']}")
        print(f"  → Créez un fichier .env (voir option 6)\n")

    while True:
        choice = print_menu()

        if choice == "1":
            action_download()
        elif choice == "2":
            action_train()
        elif choice == "3":
            action_run(dry_run=True)
        elif choice == "4":
            confirm = input(
                "\n  ⚠️  Mode LIVE — des ordres RÉELS seront placés sur Polymarket.\n"
                "  Confirmez avec 'LIVE' : "
            )
            if confirm == "LIVE":
                action_run(dry_run=False)
            else:
                print("  Annulé.")
        elif choice == "5":
            action_benchmark()
        elif choice == "6":
            action_check_config()
        elif choice == "0":
            print("\nAu revoir.\n")
            sys.exit(0)
        else:
            print("  Option invalide.")


if __name__ == "__main__":
    main()
