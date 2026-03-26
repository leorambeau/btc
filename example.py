"""
Exemples d'utilisation avancée du BTC HFT Visualizer
"""

from btc_data_loader import BTCDataLoader
from btc_ml_model import BTCPricePredictorRF
import asyncio
import pandas as pd


# ===========================================================
# EXEMPLE 1: Charger et analyser les données collectées
# ===========================================================
def example_data_analysis():
    print("📊 EXEMPLE 1: Analyse des données")
    print("─" * 50)
    
    loader = BTCDataLoader("btc_data_log.csv")
    df = loader.load()
    
    if df is None:
        print("❌ Pas de données. Démarrez d'abord un visualiseur.")
        return
    
    print(f"Total de points: {len(df)}")
    print(f"Prix min: ${df['price'].min():.2f}")
    print(f"Prix max: ${df['price'].max():.2f}")
    print(f"Volatilité: ${df['price'].std():.2f}")
    print(f"\nPremiers points:")
    print(df.head())


# ===========================================================
# EXEMPLE 2: Préparer données ML
# ===========================================================
def example_ml_preparation():
    print("\n\n🤖 EXEMPLE 2: Préparation données ML")
    print("─" * 50)
    
    loader = BTCDataLoader()
    X_train, y_train, X_test, y_test = loader.prepare_ml(lookback=20)
    
    if X_train is None:
        print("❌ Données insuffisantes")
        return
    
    print(f"Features (X): {X_train.shape}")
    print(f"Targets (y): {y_train.shape}")
    print(f"\nFeatures: sma_5, sma_10, volatility, momentum, rsi, price")


# ===========================================================
# EXEMPLE 3: Entraîner et utiliser le modèle
# ===========================================================
def example_ml_training():
    print("\n\n🎯 EXEMPLE 3: Entraînement modèle ML")
    print("─" * 50)
    
    predictor = BTCPricePredictorRF(lookback=20)
    
    if predictor.train("btc_data_log.csv"):
        predictor.get_feature_importance()
        
        # Prédire avec des features arbitraires
        sample_features = [
            42500,      # sma_5
            42450,      # sma_10
            125.5,      # volatility
            50,         # momentum
            65,         # rsi
            42550       # price
        ]
        
        prediction = predictor.predict(sample_features)
        print(f"\n💡 Prédiction pour features{sample_features}:")
        print(f"   → ${prediction:.2f}")


# ===========================================================
# EXEMPLE 4: Streaming temps réel avec callback
# ===========================================================
async def example_websocket_callback():
    print("\n\n⚡ EXEMPLE 4: WebSocket avec callback")
    print("─" * 50)
    
    uri = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
    
    import websockets
    import json
    
    count = 0
    try:
        async with websockets.connect(uri) as ws:
            print("Recevant 5 updates...")
            while count < 5:
                msg = await ws.recv()
                data = json.loads(msg)
                price = float(data['c'])
                print(f"   {count+1}. ${price:,.2f}")
                count += 1
    except Exception as e:
        print(f"❌ Error: {e}")


# ===========================================================
# EXEMPLE 5: Backtest simple
# ===========================================================
def example_backtest():
    print("\n\n📈 EXEMPLE 5: Backtest simple")
    print("─" * 50)
    
    loader = BTCDataLoader()
    df = loader.load()
    
    if df is None or len(df) < 2:
        print("❌ Données insuffisantes")
        return
    
    prices = df['price'].values
    
    # Stratégie basique: MA crossover simulado
    short_window = 5
    long_window = 20
    
    if len(prices) < long_window:
        print(f"❌ Besoin de {long_window} points minimum")
        return
    
    winning_trades = 0
    total_trades = 0
    
    for i in range(long_window, len(prices) - 1):
        ma_short = prices[i-short_window:i].mean()
        ma_long = prices[i-long_window:i].mean()
        
        if ma_short > ma_long:
            if prices[i+1] > prices[i]:
                winning_trades += 1
            total_trades += 1
    
    if total_trades > 0:
        win_rate = (winning_trades / total_trades) * 100
        print(f"Stratégie MA Crossover ({short_window}/{long_window}):")
        print(f"   Trades: {total_trades}")
        print(f"   Gagnés: {winning_trades}")
        print(f"   Win rate: {win_rate:.1f}%")


# ===========================================================
# EXEMPLE 6: Détection des extrema locaux
# ===========================================================
def example_extrema_detection():
    print("\n\n🔝 EXEMPLE 6: Détection extrema")
    print("─" * 50)
    
    loader = BTCDataLoader()
    df = loader.load()
    
    if df is None or len(df) < 3:
        print("❌ Données insuffisantes")
        return
    
    prices = df['price'].values
    times = df['timestamp'].values
    
    peaks = []
    valleys = []
    
    for i in range(1, len(prices) - 1):
        if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
            peaks.append((times[i], prices[i]))
        elif prices[i] < prices[i-1] and prices[i] < prices[i+1]:
            valleys.append((times[i], prices[i]))
    
    print(f"Peaks (maxima): {len(peaks)}")
    if peaks:
        print(f"   Dernier: {peaks[-1][0]} @ ${peaks[-1][1]:.2f}")
    
    print(f"\nValleys (minima): {len(valleys)}")
    if valleys:
        print(f"   Dernier: {valleys[-1][0]} @ ${valleys[-1][1]:.2f}")


# ===========================================================
# MENU PRINCIPAL
# ===========================================================
def main():
    print("\n" + "="*60)
    print("📚 EXEMPLES D'UTILISATION - BTC HFT Visualizer")
    print("="*60 + "\n")
    
    examples = [
        ("Analyse des données", example_data_analysis),
        ("Préparation ML", example_ml_preparation),
        ("Entraînement ML", example_ml_training),
        ("WebSocket callback", example_websocket_callback),
        ("Backtest simple", example_backtest),
        ("Détection extrema", example_extrema_detection),
    ]
    
    for i, (name, func) in enumerate(examples, 1):
        print(f"{i}. {name}")
    
    print(f"{len(examples)+1}. Exécuter tous")
    print(f"0. Quitter")
    
    choice = input("\nChoix: ").strip()
    
    if choice == '0':
        return
    elif choice == str(len(examples) + 1):
        for name, func in examples:
            try:
                if asyncio.iscoroutinefunction(func):
                    asyncio.run(func())
                else:
                    func()
            except Exception as e:
                print(f"❌ Erreur dans {name}: {e}")
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(examples):
                func = examples[idx][1]
                if asyncio.iscoroutinefunction(func):
                    asyncio.run(func())
                else:
                    func()
        except (ValueError, IndexError):
            print("❌ Option invalide")


if __name__ == "__main__":
    main()
