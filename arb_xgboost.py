"""
Modèle XGBoost — Prédiction UP/DOWN BTC sur fenêtre 5 minutes

Entraînement  : 28 jours
Validation    : 2 jours (glissante)
Inférence     : predict_proba() < 1ms par tick WebSocket

Usage:
    python arb_xgboost.py          → entraîne et sauvegarde le modèle
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
import time

from arb_config import XGB_PARAMS, MODEL_FILE, SCALER_FILE, FEATURES, CONFIDENCE_BOOST

try:
    from xgboost import XGBClassifier
    XGBOOST_OK = True
except ImportError:
    XGBOOST_OK = False
    print("[XGB] ⚠️  xgboost non installé — pip install xgboost")

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import (
        roc_auc_score, accuracy_score, log_loss,
        classification_report, confusion_matrix
    )
    from sklearn.calibration import CalibratedClassifierCV
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False
    print("[XGB] ⚠️  scikit-learn non installé — pip install scikit-learn")


class BTCDirectionModel:
    """
    Wrapper XGBoost optimisé pour l'inférence HFT (<1ms par tick).

    Attributs publics:
        model  : XGBClassifier entraîné
        scaler : StandardScaler (normalisation features)
        trained: bool — True si le modèle est prêt
    """

    def __init__(self):
        self.model   = None
        self.scaler  = None
        self.trained = False
        self._metrics = {}

    # ─── Entraînement ────────────────────────────────────────────────────────

    def train(
        self,
        df_train: pd.DataFrame,
        df_val:   pd.DataFrame,
        calibrate: bool = True,
    ) -> dict:
        """
        Entraîne le modèle XGBoost avec early stopping sur df_val.

        Args:
            df_train:  DataFrame train avec colonnes FEATURES + "target"
            df_val:    DataFrame val avec colonnes FEATURES + "target"
            calibrate: Si True, calibre les probabilités (meilleure précision)

        Returns:
            Dictionnaire de métriques (AUC, accuracy, log_loss)
        """
        if not XGBOOST_OK or not SKLEARN_OK:
            raise ImportError("xgboost et scikit-learn requis")

        X_train = df_train[FEATURES].values.astype(np.float32)
        y_train = df_train["target"].values.astype(int)
        X_val   = df_val[FEATURES].values.astype(np.float32)
        y_val   = df_val["target"].values.astype(int)

        print(f"[XGB] Train: {len(X_train):,} samples | Val: {len(X_val):,} samples")
        print(f"[XGB] Features: {FEATURES}")

        # Normalisation
        self.scaler = StandardScaler()
        X_train_s   = self.scaler.fit_transform(X_train)
        X_val_s     = self.scaler.transform(X_val)

        # Paramètres XGBoost (copie pour ne pas modifier la config)
        params = {k: v for k, v in XGB_PARAMS.items() if k != "use_label_encoder"}

        t0 = time.time()
        print(f"[XGB] Entraînement XGBClassifier (max_depth={params['max_depth']}, n_est={params['n_estimators']})...")

        base_model = XGBClassifier(**params)
        base_model.fit(
            X_train_s, y_train,
            eval_set=[(X_val_s, y_val)],
            verbose=50,
        )

        elapsed = time.time() - t0
        print(f"[XGB] Entraînement terminé en {elapsed:.1f}s")

        # Calibration des probabilités (isotonic regression)
        if calibrate:
            print("[XGB] Calibration des probabilités (isotonic)...")
            self.model = CalibratedClassifierCV(base_model, method="isotonic", cv=3)
            self.model.fit(X_train_s, y_train)
        else:
            self.model = base_model

        # Évaluation
        proba_val = self.model.predict_proba(X_val_s)[:, 1]
        pred_val  = (proba_val >= 0.5).astype(int)

        self._metrics = {
            "auc":      round(roc_auc_score(y_val, proba_val), 4),
            "accuracy": round(accuracy_score(y_val, pred_val), 4),
            "log_loss": round(log_loss(y_val, proba_val), 4),
            "train_samples": len(X_train),
            "val_samples":   len(X_val),
            "elapsed_s":     round(elapsed, 1),
        }

        print(f"\n[XGB] ═══ Résultats Validation ═══")
        print(f"[XGB]   AUC-ROC   : {self._metrics['auc']:.4f}")
        print(f"[XGB]   Accuracy  : {self._metrics['accuracy']:.4f}")
        print(f"[XGB]   Log-Loss  : {self._metrics['log_loss']:.4f}")
        print(f"\n[XGB] {classification_report(y_val, pred_val, target_names=['DOWN','UP'])}")
        print(f"[XGB] Confusion Matrix:\n{confusion_matrix(y_val, pred_val)}")

        # Importance des features
        if hasattr(base_model, "feature_importances_"):
            importances = base_model.feature_importances_
            feat_imp = sorted(zip(FEATURES, importances), key=lambda x: -x[1])
            print("\n[XGB] Feature Importance:")
            for name, imp in feat_imp:
                bar = "█" * int(imp * 40)
                print(f"  {name:<22} {imp:.4f} {bar}")

        self.trained = True
        return self._metrics

    # ─── Inférence temps réel ─────────────────────────────────────────────────

    def predict_proba_live(
        self,
        features: np.ndarray,
        time_remaining: float = None,
    ) -> float:
        """
        Inférence ultra-rapide pour un seul vecteur de features.

        Args:
            features:       np.ndarray shape (1, n_features) — depuis LiveFeatureBuffer
            time_remaining: Secondes restantes (pour confidence boost)

        Returns:
            float — probabilité P(UP) entre 0.0 et 1.0
        """
        if not self.trained or self.model is None:
            return 0.5

        features_s = self.scaler.transform(features.astype(np.float32))
        prob_up    = float(self.model.predict_proba(features_s)[0, 1])

        # Boost de confiance quand time_remaining est faible
        if CONFIDENCE_BOOST and time_remaining is not None and time_remaining < 60:
            boost_factor = 1.0 + (1.0 - time_remaining / 60) * 0.15
            # Amplifier la déviation par rapport à 0.5 (pas dépasser [0,1])
            deviation   = (prob_up - 0.5) * boost_factor
            prob_up     = max(0.01, min(0.99, 0.5 + deviation))

        return prob_up

    # ─── Persistence ─────────────────────────────────────────────────────────

    def save(self, model_path: str = MODEL_FILE, scaler_path: str = SCALER_FILE):
        """Sauvegarde le modèle et le scaler."""
        if not self.trained:
            raise RuntimeError("Modèle non entraîné")
        joblib.dump(self.model,  model_path)
        joblib.dump(self.scaler, scaler_path)
        print(f"[XGB] Modèle sauvegardé → {model_path}")
        print(f"[XGB] Scaler sauvegardé  → {scaler_path}")

    def load(
        self,
        model_path:  str = MODEL_FILE,
        scaler_path: str = SCALER_FILE,
    ) -> bool:
        """Charge un modèle existant. Retourne True si succès."""
        mp = Path(model_path)
        sp = Path(scaler_path)
        if not mp.exists() or not sp.exists():
            print(f"[XGB] Fichiers modèle introuvables: {model_path}, {scaler_path}")
            return False
        self.model   = joblib.load(mp)
        self.scaler  = joblib.load(sp)
        self.trained = True
        print(f"[XGB] Modèle chargé depuis {model_path}")
        return True

    # ─── Benchmark latence inférence ─────────────────────────────────────────

    def benchmark_inference(self, n_iters: int = 10_000) -> float:
        """
        Mesure la latence moyenne d'inférence.
        Objectif : < 1ms par tick.
        """
        if not self.trained:
            return -1.0

        dummy = np.random.randn(1, len(FEATURES)).astype(np.float32)
        t0    = time.perf_counter()
        for _ in range(n_iters):
            self.predict_proba_live(dummy, time_remaining=120.0)
        elapsed = (time.perf_counter() - t0) / n_iters * 1000  # ms

        print(f"[XGB] Latence inférence: {elapsed:.3f}ms / tick ({n_iters:,} iters)")
        if elapsed < 1.0:
            print(f"[XGB] ✅ Objectif <1ms atteint")
        else:
            print(f"[XGB] ⚠️  Latence dépasse 1ms — réduire max_depth ou n_estimators")

        return elapsed

    @property
    def metrics(self) -> dict:
        return self._metrics


# ─── Pipeline complet entraînement ───────────────────────────────────────────

def train_full_pipeline() -> BTCDirectionModel:
    """
    Pipeline complet :
    1. Charger les données historiques
    2. Construire les features
    3. Entraîner XGBoost
    4. Sauvegarder le modèle
    """
    from arb_binance_loader import load_or_download
    from arb_features import build_training_dataset

    print("\n[Pipeline] === Entraînement du modèle prédictif ===\n")

    # 1. Données
    print("[Pipeline] Étape 1/3 — Chargement données historiques...")
    df_hist = load_or_download()

    # 2. Features
    print("[Pipeline] Étape 2/3 — Construction des features...")
    df_train, df_val = build_training_dataset(df_hist)

    # 3. Modèle
    print("[Pipeline] Étape 3/3 — Entraînement XGBoost...")
    mdl = BTCDirectionModel()
    mdl.train(df_train, df_val)
    mdl.save()

    # Benchmark
    mdl.benchmark_inference()

    print("\n[Pipeline] ✅ Pipeline terminé — modèle prêt pour le trading live\n")
    return mdl


def load_or_train() -> BTCDirectionModel:
    """Charge le modèle existant ou entraîne depuis zéro."""
    mdl = BTCDirectionModel()
    if mdl.load():
        mdl.benchmark_inference(n_iters=1000)
        return mdl
    print("[XGB] Aucun modèle trouvé → entraînement complet...")
    return train_full_pipeline()


if __name__ == "__main__":
    mdl = train_full_pipeline()
