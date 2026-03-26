import signal
import sys
import platform
from pathlib import Path


class BTCHFTOrchestrator:
    """Gestionnaire pour les visualiseurs BTC HFT"""
    
    def __init__(self):
        self.running = True
        self._setup_signals()
    
    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_interrupt)
        if platform.system() != 'Windows':
            signal.signal(signal.SIGTERM, self._handle_interrupt)
    
    def _handle_interrupt(self, signum, frame):
        print("\n\n⏹️  Arrêt du visualiseur...")
        self.running = False
        sys.exit(0)
    
    def print_menu(self):
        print("\n" + "="*60)
        print("🚀 BTC/USDT Real-time HFT Visualizer")
        print("="*60)
        print("\nVeuillez choisir une option:\n")
        print("1️⃣  PyQtGraph (Recommandé) - Performance maximale")
        print("   • 60+ FPS maintenu")
        print("   • Interface graphique native")
        print("   • Idéal pour HFT réel\n")
        
        print("2️⃣  Plotly Web Server - Explorer interactif")
        print("   • Interface web responsive")
        print("   • Dark mode élégant")
        print("   • Excellente pour l'analyse\n")
        
        print("3️⃣  Benchmark Performance - Tester la latence")
        print("   • Mesure WebSocket latency")
        print("   • Teste les performances")
        print("   • Génère un rapport\n")
        
        print("4️⃣  Data Loader ML - Analyser les données")
        print("   • Charger btc_data_log.csv")
        print("   • Statistiques détaillées")
        print("   • Préparer pour ML\n")
        
        print("5️⃣  Entraîner modèle ML - Random Forest")
        print("   • Prédiction de prix")
        print("   • Feature importance")
        print("   • Évaluation R² et MAE\n")
        
        print("0️⃣  Quitter\n")
    
    def run(self):
        while self.running:
            self.print_menu()
            choice = input("Choix (0-5): ").strip()
            
            if choice == '1':
                self._run_pyqtgraph()
            elif choice == '2':
                self._run_plotly()
            elif choice == '3':
                self._run_benchmark()
            elif choice == '4':
                self._run_data_loader()
            elif choice == '5':
                self._run_ml_model()
            elif choice == '0':
                print("\n👋 Au revoir!")
                break
            else:
                print("\n❌ Option invalide")
    
    def _run_pyqtgraph(self):
        print("\n🚀 Lancement PyQtGraph...")
        print("   • Enregistré à: PyQt5 app.exec_()")
        print("   • Arrêter: Cmd+Q ou fermer la fenêtre")
        
        try:
            from btc_hft_pyqtgraph import BTCVisualizer
            from PyQt5.QtWidgets import QApplication
            
            app = QApplication([])
            visualizer = BTCVisualizer()
            visualizer.show()
            
            print("   ✅ Interface lancée")
            app.exec_()
            print("   ✅ Interface fermée")
        except ImportError as e:
            print(f"❌ Erreur import: {e}")
            print("   pip install -r requirements.txt")
        except ImportError as e:
            print(f"❌ Erreur import: {e}")
            print("   pip install -r requirements.txt")
    
    def _run_plotly(self):
        print("\n🚀 Lancement Plotly Web Server...")
        print("   • Navigateur: http://127.0.0.1:8050")
        print("   • Arrêter: Ctrl+C dans le terminal")
        
        try:
            from btc_hft_standalone import BTCRealtimeVisualizer
            
            visualizer = BTCRealtimeVisualizer()
            visualizer.run()
        except ImportError as e:
            print(f"❌ Erreur import: {e}")
            
            visualizer = BTCRealtimeVisualizer()
            visualizer.run()
        except ImportError as e:
            print(f"❌ Erreur import: {e}")
    
    def _run_benchmark(self):
        print("\n🚀 Lancement Benchmark (30s)...")
        
        try:
            from btc_benchmark import PerformanceBenchmark
            import asyncio
            
            benchmark = PerformanceBenchmark(duration=30)
            asyncio.run(benchmark.ws_stream())
        except ImportError as e:
            print(f"❌ Erreur import: {e}")
    
    def _run_data_loader(self):
        print("\n📊 Analyse des données BTC...")
        
        try:
            from btc_data_loader import BTCDataLoader
            
            loader = BTCDataLoader()
            loader.stats()
            
            if Path("btc_data_log.csv").exists():
                prepare = input("Préparer données pour ML? (y/n): ").lower()
                if prepare == 'y':
                    X_train, y_train, X_test, y_test = loader.prepare_ml()
                    if X_train is not None:
                        print(f"✅ Dataset ML prêt")
                        print(f"   Train: {X_train.shape[0]} samples")
                        print(f"   Test: {X_test.shape[0]} samples")
            else:
                print("❌ btc_data_log.csv non trouvé")
                print("   Exécutez d'abord un visualiseur pour collecter les données")
        
        except ImportError as e:
            print(f"❌ Erreur import: {e}")
    
    def _run_ml_model(self):
        print("\n🤖 Entraînement modèle ML...")
        
        if not Path("btc_data_log.csv").exists():
            print("❌ btc_data_log.csv non trouvé")
            print("   Exécutez d'abord un visualiseur pour collecter les données")
            return
        
        try:
            from btc_ml_model import BTCPricePredictorRF
            
            predictor = BTCPricePredictorRF(lookback=20)
            if predictor.train():
                predictor.get_feature_importance()
            
        except ImportError as e:
            print(f"❌ Erreur import: {e}")


if __name__ == "__main__":
    print("\n📡 Initialisation...")
    
    required_files = [
        "btc_hft_pyqtgraph.py",
        "btc_hft_standalone.py",
        "btc_benchmark.py",
        "btc_data_loader.py",
        "btc_ml_model.py"
    ]
    
    missing = [f for f in required_files if not Path(f).exists()]
    if missing:
        print(f"⚠️  Fichiers manquants: {', '.join(missing)}")
    
    orchestrator = BTCHFTOrchestrator()
    orchestrator.run()
