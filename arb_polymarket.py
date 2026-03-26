"""
Client Polymarket CLOB — Marchés BTC 5 minutes / Résolution Chainlink

Fonctions principales :
  - Trouver les marchés BTC "5 min" actifs
  - Lire les prix YES/NO en temps réel
  - Signer et placer des ordres EIP-712 (sans MetaMask)
  - Gestion automatique du gaz (relayer gratuit ou self-funded)

Prérequis :
    pip install py-clob-client web3

Variables d'environnement (.env) :
    POLY_API_KEY, POLY_SECRET, POLY_PASSPHRASE, POLY_PRIVATE_KEY, POLY_WALLET_ADDR
"""

import asyncio
import json
import time
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

import aiohttp
import requests

from arb_config import (
    POLY_CLOB_URL, POLY_GAMMA_URL, POLY_CHAIN_ID,
    POLY_API_KEY, POLY_SECRET, POLY_PASSPHRASE,
    POLY_PRIVATE_KEY, POLY_WALLET_ADDRESS,
    MAX_POSITION_USDC, RELAYER_TIMEOUT_MS, GAS_MODE,
    check_credentials,
)

logger = logging.getLogger(__name__)


# ─── Structures de données ───────────────────────────────────────────────────

@dataclass
class MarketPrice:
    """Prix d'un marché Polymarket à un instant t."""
    market_id:    str
    condition_id: str
    yes_token_id: str
    no_token_id:  str
    yes_price:    float     # 0.0 – 1.0 (probabilité implicite)
    no_price:     float
    spread:       float
    timestamp:    datetime
    question:     str


@dataclass
class ArbSignal:
    """Signal d'arbitrage détecté."""
    market_id:      str
    direction:      str          # "YES" ou "NO"
    ia_prob:        float        # Probabilité IA
    poly_price:     float        # Prix Polymarket
    edge:           float        # ia_prob - poly_price - fees
    time_remaining: float        # Secondes avant T0
    position_usdc:  float        # Taille suggérée
    timestamp:      datetime


@dataclass
class OrderResult:
    """Résultat d'un ordre placé."""
    ok:         bool
    order_id:   str
    side:       str
    price:      float
    size:       float
    gas_mode:   str
    latency_ms: float
    error:      str = ""


# ─── Client CLOB Polymarket ──────────────────────────────────────────────────

class PolymarketClient:
    """
    Gère la connexion au CLOB Polymarket et la signature EIP-712.

    Utilise py-clob-client si disponible, sinon implémente la signature
    manuellement via eth_account (web3.py).
    """

    def __init__(self):
        self._clob_client  = None
        self._session      = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._creds_ok     = check_credentials()["ok"]
        self._init_client()

    def _init_client(self):
        """Initialise le client CLOB (py-clob-client si disponible)."""
        if not self._creds_ok:
            logger.warning("[Poly] Credentials manquants — mode lecture seule")
            return

        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds

            creds = ApiCreds(
                api_key        = POLY_API_KEY,
                api_secret     = POLY_SECRET,
                api_passphrase = POLY_PASSPHRASE,
            )
            self._clob_client = ClobClient(
                host     = POLY_CLOB_URL,
                chain_id = POLY_CHAIN_ID,
                key      = POLY_PRIVATE_KEY,
                creds    = creds,
            )
            logger.info("[Poly] ✅ ClobClient initialisé (py-clob-client)")

        except ImportError:
            logger.warning("[Poly] py-clob-client non installé — utilisation du client manuel")
            self._init_manual_signer()

    def _init_manual_signer(self):
        """Signer manuel EIP-712 via eth_account (web3.py)."""
        try:
            from eth_account import Account
            self._account = Account.from_key(POLY_PRIVATE_KEY)
            logger.info(f"[Poly] ✅ Signer manuel initialisé — wallet {self._account.address}")
        except ImportError:
            logger.error("[Poly] web3 non installé — pip install web3")

    # ─── Recherche de marchés ─────────────────────────────────────────────────

    def find_btc_5min_markets(self, limit: int = 10) -> list[MarketPrice]:
        """
        Trouve les marchés BTC actifs via l'API Gamma.
        Priorité aux marchés "5 min" si disponibles, sinon tous les marchés BTC actifs.

        Returns:
            Liste de MarketPrice triée par liquidité décroissante
        """
        markets = []

        try:
            # Recherche via l'API Gamma (catalogue des marchés)
            params = {
                "active":   "true",
                "closed":   "false",
                "archived": "false",
                "limit":    200,
            }
            resp = self._session.get(
                f"{POLY_GAMMA_URL}/markets",
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            for m in data:
                q = m.get("question", "").lower()
                if "btc" in q or "bitcoin" in q:
                    price_obj = self._parse_market_price(m)
                    if price_obj:
                        markets.append(price_obj)

            # Trier par liquidité décroissante
            markets.sort(key=lambda x: float(x.spread), reverse=False)

            if markets:
                logger.info(f"[Poly] {len(markets)} marchés BTC actifs trouvés")
            else:
                logger.warning("[Poly] Aucun marché BTC actif — aucun filtre 5-min appliqué")

        except requests.RequestException as e:
            logger.error(f"[Poly] Erreur recherche marchés: {e}")

        return markets[:limit]

    def get_market_price(self, condition_id: str, yes_token_id: str = "", gamma_market_id: str = "") -> Optional[MarketPrice]:
        """
        Récupère le prix actuel d'un marché.
        Priorité : CLOB /book (si yes_token_id fourni) → Gamma /markets/{id}

        Args:
            condition_id:    ID de condition du marché (0x...)
            yes_token_id:    Token ID numérique du outcome YES (depuis clobTokenIds)
            gamma_market_id: ID numérique Gamma (ex: "540844") pour le fallback REST

        Returns:
            MarketPrice avec les meilleures offres bid/ask pour YES/NO
        """
        # Tentative via CLOB si on a un vrai token_id numérique
        if yes_token_id:
            try:
                url = f"{POLY_CLOB_URL}/book"
                t0  = time.perf_counter()
                resp = self._session.get(url, params={"token_id": yes_token_id}, timeout=5)
                latency_ms = (time.perf_counter() - t0) * 1000

                if latency_ms > RELAYER_TIMEOUT_MS:
                    logger.warning(f"[Poly] Latence CLOB: {latency_ms:.0f}ms")

                if resp.ok:
                    book      = resp.json()
                    yes_price = self._mid_price(book.get("bids", []), book.get("asks", []))
                    no_price  = 1.0 - yes_price if yes_price else 0.5
                    spread    = self._bid_ask_spread(book)

                    # Si le spread est > 40% (carnet synthétique sans vraie liquidité),
                    # le mid-price est peu fiable — ne pas retourner ce résultat
                    if spread > 0.40:
                        logger.debug(f"[Poly] CLOB spread trop large ({spread:.2f}), fallback Gamma")
                    else:
                        return MarketPrice(
                            market_id    = condition_id,
                            condition_id = condition_id,
                            yes_token_id = yes_token_id,
                            no_token_id  = "",
                            yes_price    = yes_price,
                            no_price     = no_price,
                            spread       = spread,
                            timestamp    = datetime.now(timezone.utc),
                            question     = "",
                        )
            except Exception as e:
                logger.warning(f"[Poly] CLOB book failed, fallback Gamma: {e}")

        # Fallback : récupérer les prix depuis la Gamma API via l'ID numérique
        if gamma_market_id:
            try:
                resp = self._session.get(
                    f"{POLY_GAMMA_URL}/markets/{gamma_market_id}",
                    timeout=5,
                )
                if resp.ok:
                    m = resp.json()
                    price_obj = self._parse_market_price(m)
                    if price_obj:
                        return price_obj
            except Exception as e:
                logger.error(f"[Poly] get_market_price Gamma fallback error: {e}")

        return None

    # ─── Placement d'ordre ────────────────────────────────────────────────────

    def place_order(self, signal: ArbSignal) -> OrderResult:
        """
        Place un ordre limit sur Polymarket.

        Utilise py-clob-client si disponible (gère EIP-712 automatiquement),
        sinon signe manuellement via eth_account.

        Args:
            signal: Signal d'arbitrage avec direction, prix, taille

        Returns:
            OrderResult avec statut et latence
        """
        if not self._creds_ok:
            return OrderResult(
                ok=False, order_id="", side=signal.direction,
                price=signal.poly_price, size=signal.position_usdc,
                gas_mode="none", latency_ms=0,
                error="Credentials non configurés"
            )

        t0 = time.perf_counter()

        if self._clob_client is not None:
            result = self._place_via_clob_client(signal)
        else:
            result = self._place_via_manual_sign(signal)

        result.latency_ms = (time.perf_counter() - t0) * 1000

        # Basculer sur le gas self-funded si latence excessive
        if result.latency_ms > RELAYER_TIMEOUT_MS and GAS_MODE == "relayer":
            logger.warning(
                f"[Poly] Latence relayer {result.latency_ms:.0f}ms > {RELAYER_TIMEOUT_MS}ms"
                f" — envisager GAS_MODE=self"
            )

        return result

    def _place_via_clob_client(self, signal: ArbSignal) -> OrderResult:
        """Placement via py-clob-client (EIP-712 géré automatiquement)."""
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType, Side

            side  = Side.BUY if signal.direction == "YES" else Side.BUY
            price = signal.poly_price
            size  = signal.position_usdc / price if price > 0 else 0

            order_args = OrderArgs(
                token_id = signal.market_id,
                price    = round(price, 4),
                size     = round(size, 2),
                side     = side,
                fee_rate_bps = 0,       # Relayer couvre les frais
            )
            resp = self._clob_client.create_and_post_order(order_args)

            return OrderResult(
                ok       = True,
                order_id = resp.get("orderID", ""),
                side     = signal.direction,
                price    = price,
                size     = size,
                gas_mode = GAS_MODE,
                latency_ms = 0,
            )

        except Exception as e:
            logger.error(f"[Poly] Erreur placement ordre CLOB: {e}")
            return OrderResult(
                ok=False, order_id="", side=signal.direction,
                price=signal.poly_price, size=0,
                gas_mode=GAS_MODE, latency_ms=0,
                error=str(e)
            )

    def _place_via_manual_sign(self, signal: ArbSignal) -> OrderResult:
        """
        Placement manuel avec signature EIP-712 (sans py-clob-client).

        Structure EIP-712 Polymarket :
          domain  : { name, version, chainId, verifyingContract }
          types   : { Order: [...] }
          message : { salt, maker, tokenId, makerAmount, takerAmount,
                      expiration, nonce, feeRateBps, side, signatureType }
        """
        try:
            from eth_account import Account
            from eth_account.structured_data import encode_structured_data
            import secrets

            CTFX_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # CTFExchange Polygon

            domain = {
                "name":              "Polymarket CTF Exchange",
                "version":           "1",
                "chainId":           POLY_CHAIN_ID,
                "verifyingContract": CTFX_ADDRESS,
            }

            price_bps   = int(signal.poly_price * 10_000)
            size_usdc   = int(signal.position_usdc * 1_000_000)  # USDC 6 decimals
            size_tokens = int(size_usdc / (price_bps / 10_000)) if price_bps > 0 else 0

            order_msg = {
                "salt":          int(secrets.token_hex(16), 16) % (2**256),
                "maker":         POLY_WALLET_ADDRESS,
                "signer":        POLY_WALLET_ADDRESS,
                "taker":         "0x0000000000000000000000000000000000000000",
                "tokenId":       int(signal.market_id) if signal.market_id.isdigit() else 0,
                "makerAmount":   size_usdc,
                "takerAmount":   size_tokens,
                "expiration":    int(time.time()) + 300,  # 5 min expiry
                "nonce":         0,
                "feeRateBps":    0,
                "side":          0,    # 0=BUY
                "signatureType": 0,    # 0=EOA
            }

            structured_data = {
                "types": {
                    "EIP712Domain": [
                        {"name": "name",              "type": "string"},
                        {"name": "version",           "type": "string"},
                        {"name": "chainId",           "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"},
                    ],
                    "Order": [
                        {"name": "salt",          "type": "uint256"},
                        {"name": "maker",         "type": "address"},
                        {"name": "signer",        "type": "address"},
                        {"name": "taker",         "type": "address"},
                        {"name": "tokenId",       "type": "uint256"},
                        {"name": "makerAmount",   "type": "uint256"},
                        {"name": "takerAmount",   "type": "uint256"},
                        {"name": "expiration",    "type": "uint256"},
                        {"name": "nonce",         "type": "uint256"},
                        {"name": "feeRateBps",    "type": "uint256"},
                        {"name": "side",          "type": "uint8"},
                        {"name": "signatureType", "type": "uint8"},
                    ],
                },
                "domain":      domain,
                "primaryType": "Order",
                "message":     order_msg,
            }

            signable       = encode_structured_data(structured_data)
            account        = Account.from_key(POLY_PRIVATE_KEY)
            signed         = account.sign_message(signable)
            signature_hex  = signed.signature.hex()

            # POST vers le CLOB
            payload = {
                "order":     order_msg,
                "owner":     POLY_WALLET_ADDRESS,
                "orderType": "GTC",
                "signature": signature_hex,
            }
            resp = self._session.post(
                f"{POLY_CLOB_URL}/order",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            return OrderResult(
                ok       = True,
                order_id = data.get("orderID", ""),
                side     = signal.direction,
                price    = signal.poly_price,
                size     = size_usdc / 1_000_000,
                gas_mode = GAS_MODE,
                latency_ms = 0,
            )

        except Exception as e:
            logger.error(f"[Poly] Erreur signature EIP-712: {e}")
            return OrderResult(
                ok=False, order_id="", side=signal.direction,
                price=signal.poly_price, size=0,
                gas_mode=GAS_MODE, latency_ms=0,
                error=str(e)
            )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _mid_price(bids: list, asks: list) -> float:
        """Calcule le mid-price à partir du carnet d'ordres."""
        try:
            best_bid = float(bids[0]["price"]) if bids else 0.0
            best_ask = float(asks[0]["price"]) if asks else 1.0
            return (best_bid + best_ask) / 2
        except (IndexError, KeyError, ValueError):
            return 0.5

    @staticmethod
    def _bid_ask_spread(book: dict) -> float:
        """Calcule le spread bid-ask."""
        try:
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            if bids and asks:
                return float(asks[0]["price"]) - float(bids[0]["price"])
        except (IndexError, KeyError, ValueError):
            pass
        return 0.0

    @staticmethod
    def _parse_market_price(m: dict) -> Optional[MarketPrice]:
        """
        Parse un market Gamma en MarketPrice.

        La Gamma API retourne les prix dans outcomePrices (liste JSON stringifiée)
        et les token IDs CLOB dans clobTokenIds.
        outcomes[0] = "Yes", outcomes[1] = "No" (ordre conventionnel).
        """
        try:
            import json as _json

            # Prix : outcomePrices est une liste JSON comme '["0.4845", "0.5155"]'
            raw_prices = m.get("outcomePrices", "[]")
            if isinstance(raw_prices, str):
                prices = _json.loads(raw_prices)
            else:
                prices = raw_prices  # déjà une liste

            yes_price = float(prices[0]) if len(prices) > 0 else 0.5
            no_price  = float(prices[1]) if len(prices) > 1 else 1.0 - yes_price

            # Token IDs CLOB (nécessaires pour l'endpoint /book)
            raw_token_ids = m.get("clobTokenIds", "[]")
            if isinstance(raw_token_ids, str):
                token_ids = _json.loads(raw_token_ids)
            else:
                token_ids = raw_token_ids or []

            yes_token_id = token_ids[0] if len(token_ids) > 0 else ""
            no_token_id  = token_ids[1] if len(token_ids) > 1 else ""

            # Spread : utiliser le champ Gamma si dispo, sinon calcul
            spread_raw = m.get("spread")
            spread = float(spread_raw) if spread_raw is not None else abs(yes_price + no_price - 1.0)

            return MarketPrice(
                market_id    = m.get("id",          ""),
                condition_id = m.get("conditionId", ""),
                yes_token_id = yes_token_id,
                no_token_id  = no_token_id,
                yes_price    = yes_price,
                no_price     = no_price,
                spread       = spread,
                timestamp    = datetime.now(timezone.utc),
                question     = m.get("question", ""),
            )
        except Exception as e:
            logger.debug(f"[Poly] _parse_market_price error: {e}")
            return None


# ─── Calculateur d'arbitrage ─────────────────────────────────────────────────

def compute_arb_signal(
    ia_prob:        float,
    market:         MarketPrice,
    time_remaining: float,
    min_edge:       float,
) -> Optional[ArbSignal]:
    """
    Calcule si un signal d'arbitrage existe.

    Conditions :
      UP  : ia_prob - market.yes_price > min_edge
      DOWN: (1 - ia_prob) - market.no_price > min_edge
    """
    from arb_config import MAX_POSITION_USDC

    edge_yes = ia_prob - market.yes_price
    edge_no  = (1.0 - ia_prob) - market.no_price

    if edge_yes > min_edge:
        return ArbSignal(
            market_id      = market.market_id,
            direction      = "YES",
            ia_prob        = ia_prob,
            poly_price     = market.yes_price,
            edge           = edge_yes,
            time_remaining = time_remaining,
            position_usdc  = _kelly_size(edge_yes, market.yes_price),
            timestamp      = datetime.now(timezone.utc),
        )

    if edge_no > min_edge:
        return ArbSignal(
            market_id      = market.market_id,
            direction      = "NO",
            ia_prob        = 1.0 - ia_prob,
            poly_price     = market.no_price,
            edge           = edge_no,
            time_remaining = time_remaining,
            position_usdc  = _kelly_size(edge_no, market.no_price),
            timestamp      = datetime.now(timezone.utc),
        )

    return None


def _kelly_size(edge: float, price: float, max_usdc: float = MAX_POSITION_USDC) -> float:
    """
    Critère de Kelly fractionnel (0.25x) pour dimensionner la position.
    Kelly = edge / (1 - price)  → size = min(kelly * max_usdc, max_usdc)
    """
    if price >= 1.0 or price <= 0.0:
        return 0.0
    kelly_fraction  = (edge / (1.0 - price)) * 0.25  # Kelly 25%
    size_usdc       = min(kelly_fraction * max_usdc, max_usdc)
    return round(max(size_usdc, 0.0), 2)


if __name__ == "__main__":
    # Test de connexion (lecture seule)
    client = PolymarketClient()
    markets = client.find_btc_5min_markets()

    if markets:
        print(f"\nMarchés BTC 5-min actifs:")
        for m in markets:
            print(f"  {m.question[:60]:<60} YES={m.yes_price:.3f} NO={m.no_price:.3f}")
    else:
        print("Aucun marché BTC 5-min actif trouvé.")
        creds = check_credentials()
        print(f"Credentials: {creds}")
