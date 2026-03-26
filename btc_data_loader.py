import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


class BTCDataLoader:
    def __init__(self, csv_path="btc_data_log.csv"):
        self.csv_path = Path(csv_path)
    
    def load(self):
        if not self.csv_path.exists():
            print(f"❌ {self.csv_path} not found")
            return None
        
        df = pd.read_csv(self.csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['price'] = df['price'].astype(float)
        return df
    
    def get_features(self, df, lookback=20):
        features = []
        
        prices = df['price'].values
        
        for i in range(lookback, len(prices) - 1):
            window = prices[i-lookback:i]
            target = prices[i+1]
            
            feat = {
                'sma_5': np.mean(window[-5:]),
                'sma_10': np.mean(window[-10:]),
                'volatility': np.std(window),
                'momentum': prices[i] - prices[i-1],
                'rsi': self._calculate_rsi(window),
                'price': prices[i],
                'target': target
            }
            features.append(feat)
        
        return pd.DataFrame(features)
    
    def _calculate_rsi(self, prices, period=14):
        if len(prices) < period:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100 if avg_gain > 0 else 50
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def prepare_ml(self, lookback=20, train_size=0.8):
        df = self.load()
        if df is None or len(df) < lookback + 2:
            print(f"❌ Not enough data (min: {lookback + 2}, got: {len(df) if df is not None else 0})")
            return None, None, None, None
        
        features_df = self.get_features(df, lookback)
        
        train_idx = int(len(features_df) * train_size)
        
        X_train = features_df.iloc[:train_idx].drop(['target', 'price'], axis=1).values
        y_train = features_df.iloc[:train_idx]['target'].values
        
        X_test = features_df.iloc[train_idx:].drop(['target', 'price'], axis=1).values
        y_test = features_df.iloc[train_idx:]['target'].values
        
        return X_train, y_train, X_test, y_test
    
    def stats(self):
        df = self.load()
        if df is None:
            return
        
        print(f"\n📊 BTC/USDT Data Statistics")
        print(f"{'─' * 50}")
        print(f"Total points: {len(df)}")
        print(f"Price range: ${df['price'].min():.2f} - ${df['price'].max():.2f}")
        print(f"Average: ${df['price'].mean():.2f}")
        print(f"Volatility: ${df['price'].std():.2f}")
        print(f"Change: {((df['price'].iloc[-1] / df['price'].iloc[0]) - 1) * 100:.2f}%")
        print(f"Time span: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        print(f"{'─' * 50}\n")


if __name__ == "__main__":
    loader = BTCDataLoader()
    loader.stats()
    
    X_train, y_train, X_test, y_test = loader.prepare_ml(lookback=20)
    
    if X_train is not None:
        print(f"✅ ML Dataset Ready")
        print(f"   Train: {X_train.shape[0]} samples, {X_train.shape[1]} features")
        print(f"   Test:  {X_test.shape[0]} samples")
