"""
Dashboard Temps Réel — Arbitrage Prédictif BTC/Polymarket

Affiche sur http://127.0.0.1:8051 :
  • Graphique prix BTC (ligne verte)
  • Courbe probabilité IA (0–100%, ligne cyan superposée)
  • Compte à rebours visuel jusqu'à T0 (résolution Polymarket)
  • Panneau d'état : prix Polymarket YES/NO, spread, signal ARB

Usage:
    from arb_dashboard import ArbDashboard
    dashboard = ArbDashboard(engine)
    dashboard.run()
"""

import threading
import webbrowser
from datetime import datetime, timezone

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, callback
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

from arb_config import DASH_PORT, DASH_HOST, DASH_REFRESH_MS, RESOLUTION_WINDOW_S


# ─── Couleurs dark mode ───────────────────────────────────────────────────────
C_BG        = "#0d1117"
C_SURFACE   = "#161b22"
C_BORDER    = "#30363d"
C_GREEN     = "#00ff41"
C_CYAN      = "#00d4ff"
C_ORANGE    = "#ff7b00"
C_RED       = "#ff4444"
C_TEXT      = "#e0e0e0"
C_MUTED     = "#8b949e"
C_ARB_GREEN = "#00ff88"


def _countdown_bar_color(remaining: float) -> str:
    """Couleur du compte à rebours selon l'urgence."""
    pct = remaining / RESOLUTION_WINDOW_S
    if pct > 0.5:
        return C_GREEN
    elif pct > 0.2:
        return C_ORANGE
    else:
        return C_RED


def _format_countdown(remaining: float) -> str:
    """Format mm:ss pour le compte à rebours."""
    remaining = max(0, int(remaining))
    m, s      = divmod(remaining, 60)
    return f"{m:02d}:{s:02d}"


class ArbDashboard:
    """
    Dashboard Plotly Dash pour le système d'arbitrage.
    Se connecte à un HFTArbitrageEngine pour lire l'état en temps réel.
    """

    def __init__(self, engine):
        self.engine = engine
        self.app    = self._build_app()

    def _build_app(self) -> Dash:
        try:
            app = Dash(
                __name__,
                external_stylesheets=[dbc.themes.CYBORG],
                suppress_callback_exceptions=True,
                title="ARB HFT | BTC/Polymarket",
            )
        except Exception:
            app = Dash(
                __name__,
                suppress_callback_exceptions=True,
                title="ARB HFT | BTC/Polymarket",
            )

        app.layout = self._layout()
        self._register_callbacks(app)
        return app

    def _layout(self) -> html.Div:
        return html.Div([
            # Header
            html.Div([
                html.H2("ARB HFT — BTC/USDT × Polymarket", style={
                    "color": C_GREEN, "margin": "0", "fontFamily": "monospace",
                    "fontSize": "20px", "letterSpacing": "2px"
                }),
                html.Span(id="status-badge", children="● LIVE", style={
                    "color": C_ARB_GREEN, "fontFamily": "monospace",
                    "fontSize": "14px", "marginLeft": "16px"
                }),
            ], style={
                "display": "flex", "alignItems": "center",
                "padding": "12px 20px", "backgroundColor": C_SURFACE,
                "borderBottom": f"1px solid {C_BORDER}"
            }),

            # KPI Cards Row
            html.Div([
                _kpi_card("BTC PRICE",    "kpi-price",       C_GREEN,  "$--,---"),
                _kpi_card("AI P(UP)",     "kpi-prob",        C_CYAN,   "--.-%"),
                _kpi_card("AI P(DOWN)",   "kpi-prob-down",   C_RED,    "--.-%"),
                _kpi_card("REF T-5min",   "kpi-ref-price",   C_MUTED,  "$--,---"),
                _kpi_card("POLY YES",     "kpi-poly-yes",    C_TEXT,   "-.---"),
                _kpi_card("POLY NO",      "kpi-poly-no",     C_TEXT,   "-.---"),
                _kpi_card("BID/ASK",      "kpi-spread",      C_MUTED,  "-.--"),
                _kpi_card("SIGNALS",      "kpi-signals",     C_ORANGE, "0"),
            ], style={
                "display": "flex", "flexWrap": "wrap",
                "padding": "8px 16px", "gap": "8px",
                "backgroundColor": C_BG,
            }),

            # Override manuel REF T-5min
            html.Div([
                html.Div("OVERRIDE REF T-5min", style={
                    "color": C_MUTED, "fontSize": "10px",
                    "fontFamily": "monospace", "marginRight": "10px",
                    "letterSpacing": "1px", "alignSelf": "center"
                }),
                dcc.Input(
                    id="ref-price-input",
                    type="number",
                    placeholder="ex: 87500.00",
                    debounce=False,
                    style={
                        "backgroundColor": C_SURFACE, "color": C_TEXT,
                        "border": f"1px solid {C_BORDER}", "borderRadius": "4px",
                        "padding": "6px 10px", "fontFamily": "monospace",
                        "fontSize": "13px", "width": "140px",
                    }
                ),
                html.Button("SET", id="ref-price-btn", n_clicks=0, style={
                    "backgroundColor": C_ORANGE, "color": "#000",
                    "border": "none", "borderRadius": "4px",
                    "padding": "6px 14px", "fontFamily": "monospace",
                    "fontWeight": "bold", "cursor": "pointer",
                    "marginLeft": "8px", "fontSize": "12px",
                }),
                html.Button("↺ AUTO", id="ref-auto-btn", n_clicks=0, style={
                    "backgroundColor": "transparent", "color": C_MUTED,
                    "border": f"1px solid {C_BORDER}", "borderRadius": "4px",
                    "padding": "6px 10px", "fontFamily": "monospace",
                    "cursor": "pointer", "marginLeft": "6px", "fontSize": "11px",
                }),
                html.Span(id="ref-price-feedback", style={
                    "color": C_ARB_GREEN, "fontFamily": "monospace",
                    "fontSize": "11px", "marginLeft": "12px"
                }),
            ], style={
                "display": "flex", "alignItems": "center",
                "padding": "8px 20px", "backgroundColor": C_SURFACE,
                "borderBottom": f"1px solid {C_BORDER}"
            }),

            # Compte à rebours + Market
            html.Div([
                html.Div([
                    html.Div("PROCHAINE RÉSOLUTION T₀", style={
                        "color": C_MUTED, "fontSize": "10px",
                        "fontFamily": "monospace", "letterSpacing": "1px"
                    }),
                    html.Div(id="countdown-display", children="05:00", style={
                        "color": C_ORANGE, "fontSize": "40px",
                        "fontFamily": "monospace", "fontWeight": "bold",
                        "lineHeight": "1.1"
                    }),
                    # Barre de progression
                    html.Div([
                        html.Div(id="countdown-bar", style={
                            "height": "4px", "width": "100%",
                            "backgroundColor": C_GREEN,
                            "transition": "width 1s linear, background-color 1s"
                        })
                    ], style={
                        "width": "180px", "backgroundColor": C_BORDER,
                        "borderRadius": "2px", "marginTop": "4px"
                    }),
                ], style={"textAlign": "center", "minWidth": "200px"}),

                html.Div([
                    html.Div("MARCHÉ ACTIF", style={
                        "color": C_MUTED, "fontSize": "10px",
                        "fontFamily": "monospace", "marginBottom": "4px"
                    }),
                    html.Div(id="market-label", children="Recherche...", style={
                        "color": C_TEXT, "fontSize": "12px", "fontFamily": "monospace"
                    }),
                    html.Div(id="arb-alert", style={"marginTop": "8px"}),
                ], style={"flex": "1", "padding": "0 20px"}),

            ], style={
                "display": "flex", "alignItems": "center",
                "padding": "12px 20px", "backgroundColor": C_SURFACE,
                "borderBottom": f"1px solid {C_BORDER}"
            }),

            # Graphique principal (prix + probabilité IA)
            dcc.Graph(
                id="main-graph",
                style={"height": "55vh"},
                config={"displayModeBar": False}
            ),

            # Derniers signaux
            html.Div([
                html.Div("DERNIERS SIGNAUX ARB", style={
                    "color": C_MUTED, "fontSize": "10px",
                    "fontFamily": "monospace", "marginBottom": "8px"
                }),
                html.Div(id="signal-log", style={
                    "fontFamily": "monospace", "fontSize": "11px", "color": C_TEXT
                }),
            ], style={
                "padding": "10px 20px", "backgroundColor": C_SURFACE,
                "borderTop": f"1px solid {C_BORDER}"
            }),

            # Interval de refresh
            dcc.Interval(id="interval", interval=DASH_REFRESH_MS, n_intervals=0),
            dcc.Store(id="signal-history", data=[]),
            dcc.Store(id="ref-manual-flag", data=False),
            dcc.Store(id="ref-last-auto",  data=0),

        ], style={"backgroundColor": C_BG, "minHeight": "100vh", "color": C_TEXT})

    def _register_callbacks(self, app: Dash):

        @app.callback(
            [
                Output("main-graph",       "figure"),
                Output("kpi-price",        "children"),
                Output("kpi-prob",         "children"),
                Output("kpi-prob-down",    "children"),
                Output("kpi-ref-price",    "children"),
                Output("kpi-poly-yes",     "children"),
                Output("kpi-poly-no",      "children"),
                Output("kpi-spread",       "children"),
                Output("kpi-signals",      "children"),
                Output("countdown-display","children"),
                Output("countdown-bar",    "style"),
                Output("market-label",     "children"),
                Output("arb-alert",        "children"),
                Output("signal-log",       "children"),
                Output("signal-history",   "data"),
            ],
            Input("interval", "n_intervals"),
            [
                __import__('dash').dependencies.State("signal-history", "data")
            ],
            prevent_initial_call=False,
        )
        def update_all(n, sig_history):
            snap = self.engine.state_snapshot

            # ── Graphique ───────────────────────────────────────────────────
            fig = self._build_figure(snap)

            # ── KPIs ────────────────────────────────────────────────────────
            price_str      = f"${snap['price']:>10,.2f}"
            prob_pct       = snap['ai_prob'] * 100
            prob_str       = f"{prob_pct:.1f}%"
            prob_down_pct  = (1 - snap['ai_prob']) * 100
            prob_down_str  = f"{prob_down_pct:.1f}%"
            ref_price      = snap.get('window_open_price', 0)
            ref_str        = f"${ref_price:,.2f}" if ref_price > 0 else "---"
            poly_yes_s     = f"{snap['poly_yes']:.3f}"
            poly_no_s      = f"{snap['poly_no']:.3f}"
            spread_s       = f"{snap['bid_ask_spread']:.2f}"
            signals_s      = str(snap['signals_count'])

            # ── Compte à rebours ─────────────────────────────────────────
            remaining   = snap['time_remaining']
            countdown_s = _format_countdown(remaining)
            pct_remain  = remaining / RESOLUTION_WINDOW_S
            bar_color   = _countdown_bar_color(remaining)
            bar_style   = {
                "height": "4px",
                "width":  f"{pct_remain * 100:.1f}%",
                "backgroundColor": bar_color,
                "transition": "width 1s linear, background-color 1s"
            }

            # ── Alerte ARB ────────────────────────────────────────────────
            if snap['arb_detected'] and snap['last_signal']:
                sig    = snap['last_signal']
                alert  = html.Div([
                    html.Span("⚡ ARB DETECTED", style={
                        "color": C_ARB_GREEN, "fontWeight": "bold",
                        "fontFamily": "monospace", "fontSize": "13px"
                    }),
                    html.Span(
                        f"  {sig.direction}  IA={sig.ia_prob:.3f}"
                        f"  POLY={sig.poly_price:.3f}  EDGE={sig.edge:.3f}",
                        style={"color": C_TEXT, "fontFamily": "monospace", "fontSize": "11px"}
                    ),
                ])
            else:
                edge_yes = snap['ai_prob'] - snap['poly_yes']
                edge_no  = (1 - snap['ai_prob']) - snap['poly_no']
                best_edge = max(edge_yes, edge_no)
                from arb_config import MIN_ARB_EDGE
                remaining_edge = MIN_ARB_EDGE - best_edge
                alert = html.Div(
                    f"No arb — besoin +{remaining_edge:.3f} de plus",
                    style={"color": C_MUTED, "fontFamily": "monospace", "fontSize": "11px"}
                )

            # ── Historique signaux ────────────────────────────────────────
            sig_history = sig_history or []
            if snap['arb_detected'] and snap['last_signal']:
                sig = snap['last_signal']
                entry = {
                    "ts":    sig.timestamp.strftime("%H:%M:%S"),
                    "dir":   sig.direction,
                    "ia":    f"{sig.ia_prob:.3f}",
                    "poly":  f"{sig.poly_price:.3f}",
                    "edge":  f"{sig.edge:.4f}",
                    "tr":    f"{sig.time_remaining:.0f}s",
                }
                # Éviter les doublons
                if not sig_history or sig_history[-1].get("ts") != entry["ts"]:
                    sig_history = (sig_history + [entry])[-20:]  # Garder 20 derniers

            sig_rows = [
                html.Div(
                    f"{e['ts']}  {e['dir']:<4}  IA={e['ia']}  POLY={e['poly']}"
                    f"  EDGE={e['edge']}  T-{e['tr']}",
                    style={"color": C_ARB_GREEN if e['dir'] == "YES" else C_CYAN,
                           "marginBottom": "2px"}
                )
                for e in reversed(sig_history[-10:])
            ] or [html.Div("Aucun signal encore", style={"color": C_MUTED})]

            return (
                fig, price_str, prob_str, prob_down_str, ref_str,
                poly_yes_s, poly_no_s, spread_s, signals_s,
                countdown_s, bar_style,
                snap['poly_market'],
                alert,
                sig_rows,
                sig_history,
            )

        # Callback 1 : auto-fill uniquement quand une nouvelle window de 5min démarre
        @app.callback(
            [
                Output("ref-price-input", "value"),
                Output("ref-last-auto",   "data"),
            ],
            Input("interval", "n_intervals"),
            [
                __import__('dash').dependencies.State("ref-manual-flag", "data"),
                __import__('dash').dependencies.State("ref-last-auto",   "data"),
                __import__('dash').dependencies.State("ref-price-input", "value"),
            ],
            prevent_initial_call=False,
        )
        def autofill_ref(n, is_manual, last_auto, current_val):
            ref = self.engine.state.window_open_price
            # Nouvelle window détectée = ref a changé depuis le dernier auto-fill
            new_window = ref > 0 and ref != last_auto
            if is_manual or not new_window:
                return current_val, last_auto   # Rien ne change
            return round(ref, 2), ref           # Nouvelle window → mise à jour

        # Callback 2 : SET manuel + bouton AUTO
        @app.callback(
            [
                Output("ref-price-feedback", "children"),
                Output("ref-manual-flag",    "data"),
            ],
            [
                Input("ref-price-btn",  "n_clicks"),
                Input("ref-auto-btn",   "n_clicks"),
            ],
            __import__('dash').dependencies.State("ref-price-input", "value"),
            prevent_initial_call=True,
        )
        def handle_ref_buttons(set_clicks, auto_clicks, value):
            from dash import ctx
            triggered = ctx.triggered_id
            if triggered == "ref-price-btn":
                if value is None or float(value) <= 0:
                    return "⚠ valeur invalide", True
                self.engine.state.window_open_price = float(value)
                return f"✓ REF forcé à ${float(value):,.2f}", True
            elif triggered == "ref-auto-btn":
                return "↺ mode AUTO", False
            return "", False

    def _build_figure(self, snap: dict) -> go.Figure:
        """Construit le graphique double-axe prix / probabilité IA."""
        prices     = snap["prices"]
        timestamps = snap["timestamps"]
        ai_probs   = snap["ai_probs"]

        # Aligner les longueurs
        n = min(len(prices), len(timestamps))
        prices     = prices[-n:]
        timestamps = timestamps[-n:]

        # Aligner les probs (peuvent être plus courtes)
        n_prob = min(len(ai_probs), n)
        ai_probs_aligned = [None] * (n - n_prob) + list(ai_probs[-n_prob:])
        ai_pct           = [p * 100 if p is not None else None for p in ai_probs_aligned]

        fig = make_subplots(
            specs=[[{"secondary_y": True}]],
            rows=1, cols=1,
        )

        # Trace prix BTC
        fig.add_trace(go.Scatter(
            x             = timestamps,
            y             = prices,
            mode          = "lines",
            name          = "BTC/USDT",
            line          = dict(color=C_GREEN, width=2),
            hovertemplate = "<b>$%{y:,.2f}</b><br>%{x}<extra></extra>",
        ), secondary_y=False)

        # Trace probabilité IA (0–100%)
        fig.add_trace(go.Scatter(
            x             = timestamps,
            y             = ai_pct,
            mode          = "lines",
            name          = "IA P(UP) %",
            line          = dict(color=C_CYAN, width=1.5, dash="dot"),
            opacity       = 0.85,
            hovertemplate = "<b>P(UP)=%{y:.1f}%</b><br>%{x}<extra></extra>",
        ), secondary_y=True)

        # Ligne de seuil à 50%
        fig.add_hline(
            y=50, line_dash="dash", line_color=C_BORDER,
            line_width=1, secondary_y=True,
            annotation_text="50%",
            annotation_font_color=C_MUTED,
        )

        # Layout dark mode
        current_price = snap.get("price", 0)
        fig.update_layout(
            title={
                "text": (
                    f"<b>BTC/USDT  ${current_price:,.2f}</b>"
                    f"  <span style='color:{C_CYAN};font-size:14px'>"
                    f"P(UP)={snap['ai_prob']*100:.1f}%</span>"
                ),
                "x": 0.5, "xanchor": "center",
                "font": {"color": C_TEXT, "size": 16}
            },
            plot_bgcolor  = C_BG,
            paper_bgcolor = C_BG,
            font          = dict(color=C_TEXT, size=11, family="monospace"),
            legend        = dict(
                x=0.01, y=0.99, bgcolor="rgba(0,0,0,0)",
                font=dict(color=C_TEXT, size=10)
            ),
            hovermode     = "x unified",
            margin        = dict(l=60, r=70, t=60, b=40),
            xaxis         = dict(showgrid=True, gridcolor=C_BORDER, gridwidth=1),
            yaxis         = dict(
                title     = "Prix BTC (USDT)",
                showgrid  = True, gridcolor=C_BORDER, gridwidth=1,
                color     = C_GREEN,
            ),
            yaxis2        = dict(
                title     = "P(UP) %",
                range     = [0, 100],
                showgrid  = False,
                color     = C_CYAN,
                ticksuffix= "%",
            ),
        )

        return fig

    def run(self, open_browser: bool = True):
        """Lance le serveur Dash."""
        print(f"\n[Dashboard] Démarrage sur http://{DASH_HOST}:{DASH_PORT}")
        print(f"[Dashboard] Refresh: {DASH_REFRESH_MS}ms")
        print(f"[Dashboard] Fermer avec Ctrl+C\n")

        if open_browser:
            threading.Timer(1.5, lambda: webbrowser.open(f"http://{DASH_HOST}:{DASH_PORT}")).start()

        self.app.run(
            debug=False,
            host=DASH_HOST,
            port=DASH_PORT,
        )


# ─── Helper KPI Card ─────────────────────────────────────────────────────────

def _kpi_card(label: str, value_id: str, color: str, default: str) -> html.Div:
    return html.Div([
        html.Div(label, style={
            "color": C_MUTED, "fontSize": "9px",
            "fontFamily": "monospace", "letterSpacing": "1px",
            "marginBottom": "2px"
        }),
        html.Div(default, id=value_id, style={
            "color": color, "fontSize": "18px",
            "fontFamily": "monospace", "fontWeight": "bold"
        }),
    ], style={
        "backgroundColor": C_SURFACE,
        "border": f"1px solid {C_BORDER}",
        "borderRadius": "6px",
        "padding": "8px 14px",
        "minWidth": "110px",
    })
