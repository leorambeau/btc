import unittest
import asyncio
import json
from datetime import datetime
from pathlib import Path
from collections import deque


class TestBTCDataStructures(unittest.TestCase):
    """Test les structures de données"""
    
    def test_deque_max_length(self):
        prices = deque(maxlen=5)
        for i in range(10):
            prices.append(i)
        
        self.assertEqual(len(prices), 5)
        self.assertEqual(list(prices), [5, 6, 7, 8, 9])
    
    def test_deque_memory_constant(self):
        prices = deque(maxlen=100)
        import sys
        
        size_empty = sys.getsizeof(prices)
        
        for i in range(1000):
            prices.append(i)
        
        size_full = sys.getsizeof(prices)
        
        # Size should be roughly same
        self.assertLess(abs(size_full - size_empty), 100)


class TestBTCDataLoader(unittest.TestCase):
    """Test loader et préparation ML"""
    
    def setUp(self):
        self.csv_path = Path("test_btc_data.csv")
        
        with open(self.csv_path, 'w') as f:
            f.write("timestamp,price\n")
            for i in range(50):
                ts = datetime.now().isoformat()
                price = 40000 + i * 100
                f.write(f"{ts},{price}\n")
    
    def tearDown(self):
        if self.csv_path.exists():
            self.csv_path.unlink()
    
    def test_csv_creation(self):
        self.assertTrue(self.csv_path.exists())
        
        with open(self.csv_path) as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 51)  # Header + 50 rows
    
    def test_dataloader_load(self):
        from btc_data_loader import BTCDataLoader
        
        loader = BTCDataLoader(str(self.csv_path))
        df = loader.load()
        
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 50)
        self.assertIn('timestamp', df.columns)
        self.assertIn('price', df.columns)
    
    def test_feature_calculation(self):
        from btc_data_loader import BTCDataLoader
        
        loader = BTCDataLoader(str(self.csv_path))
        df = loader.load()
        features = loader.get_features(df, lookback=10)
        
        self.assertGreater(len(features), 0)
        self.assertIn('sma_5', features.columns)
        self.assertIn('volatility', features.columns)
        self.assertIn('target', features.columns)


class TestBTCML(unittest.TestCase):
    """Test modèle ML"""
    
    def setUp(self):
        self.csv_path = Path("test_ml_data.csv")
        
        with open(self.csv_path, 'w') as f:
            f.write("timestamp,price\n")
            for i in range(100):
                ts = datetime.now().isoformat()
                price = 40000 + i * 50 + (i % 10 - 5) * 20
                f.write(f"{ts},{price}\n")
    
    def tearDown(self):
        if self.csv_path.exists():
            self.csv_path.unlink()
    
    def test_model_training(self):
        from btc_ml_model import BTCPricePredictorRF
        
        predictor = BTCPricePredictorRF(lookback=10)
        success = predictor.train(str(self.csv_path))
        
        self.assertTrue(success)
        self.assertTrue(predictor.is_trained)
    
    def test_model_prediction(self):
        from btc_ml_model import BTCPricePredictorRF
        
        predictor = BTCPricePredictorRF(lookback=10)
        predictor.train(str(self.csv_path))
        
        # Features: [sma_5, sma_10, volatility, momentum, rsi, price]
        features = [40000, 40100, 50, 25, 60, 40150]
        prediction = predictor.predict(features)
        
        self.assertIsNotNone(prediction)
        self.assertIsInstance(prediction, (float, int))
        self.assertGreater(prediction, 30000)  # Sanity check
        self.assertLess(prediction, 50000)


class TestJSONParsing(unittest.TestCase):
    """Test parsing des données Binance"""
    
    def test_binance_ticker_parse(self):
        sample_msg = {
            'c': '42567.89',
            'E': 1648310000000
        }
        
        price = float(sample_msg['c'])
        timestamp = sample_msg['E']
        
        self.assertEqual(price, 42567.89)
        self.assertEqual(timestamp, 1648310000000)
    
    def test_large_numbers_precision(self):
        price_str = '45678.123456789'
        price = float(price_str)
        
        self.assertAlmostEqual(price, 45678.123456, places=6)


class TestAsyncIO(unittest.TestCase):
    """Test asyncio patterns"""
    
    def test_async_function(self):
        async def sample_task():
            await asyncio.sleep(0.01)
            return 42
        
        result = asyncio.run(sample_task())
        self.assertEqual(result, 42)
    
    def test_queue_behavior(self):
        from queue import Queue
        
        q = Queue()
        q.put(("2026-03-25", 42567.89))
        
        ts, price = q.get(timeout=1)
        self.assertEqual(price, 42567.89)


class TestBenchmark(unittest.TestCase):
    """Test performance metrics"""
    
    def test_deque_append_speed(self):
        import time
        
        prices = deque(maxlen=100)
        
        start = time.time()
        for i in range(10000):
            prices.append(i % 50000)
        elapsed = time.time() - start
        
        # Should be very fast (~1ms for 10k appends)
        self.assertLess(elapsed, 0.1)
    
    def test_json_parse_speed(self):
        import time
        
        sample = json.dumps({'c': '42567.89', 'E': 1648310000000})
        
        start = time.time()
        for _ in range(10000):
            data = json.loads(sample)
        elapsed = time.time() - start
        
        # Should be fast (~10ms for 10k parses)
        self.assertLess(elapsed, 0.05)


class TestCSVOperations(unittest.TestCase):
    """Test CSV I/O"""
    
    def setUp(self):
        self.csv_path = Path("test_csv_io.csv")
    
    def tearDown(self):
        if self.csv_path.exists():
            self.csv_path.unlink()
    
    def test_csv_write(self):
        import csv
        
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'price'])
            writer.writerow(['2026-03-25T14:32:45', '42567.89'])
        
        self.assertTrue(self.csv_path.exists())
        
        with open(self.csv_path) as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 2)
    
    def test_csv_append(self):
        import csv
        
        # Create
        with open(self.csv_path, 'w', newline='') as f:
            csv.writer(f).writerow(['timestamp', 'price'])
        
        # Append multiple
        for i in range(5):
            with open(self.csv_path, 'a', newline='') as f:
                csv.writer(f).writerow([f'2026-03-25T14:{i}', 40000 + i*100])
        
        with open(self.csv_path) as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 6)  # Header + 5 rows


class TestWebSocketURL(unittest.TestCase):
    """Test WebSocket configuration"""
    
    def test_binance_url_validity(self):
        uri = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
        
        self.assertTrue(uri.startswith('wss://'))
        self.assertIn('binance.com', uri)
        self.assertIn('ticker', uri)
    
    def test_symbol_parsing(self):
        uri = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
        symbol = uri.split('/')[-1].split('@')[0]
        
        self.assertEqual(symbol, 'btcusdt')


def run_all_tests():
    """Run all tests with summary"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestBTCDataStructures))
    suite.addTests(loader.loadTestsFromTestCase(TestBTCDataLoader))
    suite.addTests(loader.loadTestsFromTestCase(TestBTCML))
    suite.addTests(loader.loadTestsFromTestCase(TestJSONParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestAsyncIO))
    suite.addTests(loader.loadTestsFromTestCase(TestBenchmark))
    suite.addTests(loader.loadTestsFromTestCase(TestCSVOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestWebSocketURL))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
