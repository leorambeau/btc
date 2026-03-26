import numpy as np
from btc_data_loader import BTCDataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


class BTCPricePredictorRF:
    def __init__(self, lookback=20):
        self.lookback = lookback
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def train(self, csv_path="btc_data_log.csv"):
        loader = BTCDataLoader(csv_path)
        X_train, y_train, X_test, y_test = loader.prepare_ml(self.lookback)
        
        if X_train is None:
            print("❌ Training data insufficient")
            return False
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        print(f"🔧 Training Random Forest ({X_train.shape[0]} samples)...")
        self.model.fit(X_train_scaled, y_train)
        
        y_pred_test = self.model.predict(X_test_scaled)
        
        mse = mean_squared_error(y_test, y_pred_test)
        mae = mean_absolute_error(y_test, y_pred_test)
        r2 = r2_score(y_test, y_pred_test)
        
        print(f"\n✅ Model Trained")
        print(f"{'─' * 40}")
        print(f"RMSE: ${np.sqrt(mse):.4f}")
        print(f"MAE:  ${mae:.4f}")
        print(f"R²:   {r2:.4f}")
        print(f"{'─' * 40}\n")
        
        self.is_trained = True
        return True
    
    def predict(self, features):
        if not self.is_trained:
            print("❌ Model not trained yet")
            return None
        
        features_scaled = self.scaler.transform([features])
        return self.model.predict(features_scaled)[0]
    
    def get_feature_importance(self):
        if not self.is_trained:
            return None
        
        feature_names = ['sma_5', 'sma_10', 'volatility', 'momentum', 'rsi', 'price']
        importances = self.model.feature_importances_
        
        feature_importance = list(zip(feature_names, importances))
        feature_importance.sort(key=lambda x: x[1], reverse=True)
        
        print("\n📊 Feature Importance")
        print(f"{'─' * 35}")
        for name, importance in feature_importance:
            print(f"{name:12} : {'█' * int(importance * 100)} {importance:.4f}")
        print(f"{'─' * 35}\n")
        
        return feature_importance


if __name__ == "__main__":
    predictor = BTCPricePredictorRF(lookback=20)
    
    if predictor.train():
        predictor.get_feature_importance()
        
        sample_features = [42500, 42450, 125.5, 50, 65, 42550]
        prediction = predictor.predict(sample_features)
        print(f"💡 Sample prediction: ${prediction:.2f}")
