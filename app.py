"""
PULSE//SIGNAL — Karnataka Economic Radar
=========================================
Fully self-contained Streamlit dashboard.
Generates synthetic district-level economic data inspired by PhonePe Pulse,
builds explainable signals (momentum, emerging-market, next-wave), and
visualises them across six interactive views.

NEW FEATURE: 🔮 District Growth Forecast — simple trend extrapolation with
confidence bands and a user-adjustable forecast horizon.

Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime
import json, math, random

# ─────────────────────────── page config ───────────────────────────
st.set_page_config(
    page_title="PULSE//SIGNAL Karnataka",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────── custom CSS ────────────────────────────
st.markdown("""
<style>
.main-title{font-size:2.4rem;font-weight:800;background:linear-gradient(90deg,#6C63FF,#E91E63);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:.2rem}
.sub-title{text-align:center;color:#888;font-size:1.1rem;margin-bottom:2rem}
.signal-pill{display:inline-block;padding:4px 12px;border-radius:20px;font-weight:600;font-size:.85rem;margin:2px}
.signal-high{background:#E8F5E9;color:#2E7D32}
.signal-medium{background:#FFF8E1;color:#F57F17}
.signal-low{background:#FFEBEE;color:#C62828}
div[data-testid="stMetric"]{border-radius:12px;padding:12px;
border-left:4px solid #6C63FF}
@media (prefers-color-scheme: dark) {
    div[data-testid="stMetric"]{background:rgba(108,99,255,0.08)}
}
@media (prefers-color-scheme: light) {
    div[data-testid="stMetric"]{background:#f8f9fd}
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
#  DATA GENERATION  (synthetic, seeded for reproducibility)
# ═══════════════════════════════════════════════════════════════════
KARNATAKA_DISTRICTS = [
    "Bagalkote", "Ballari", "Belagavi", "Bengaluru Rural", "Bengaluru Urban",
    "Bidar", "Chamarajanagara", "Chikkaballapura", "Chikkamagaluru",
    "Chitradurga", "Dakshina Kannada", "Davanagere", "Dharwad", "Gadag",
    "Hassan", "Haveri", "Kalaburagi", "Kodagu", "Kolar", "Koppal",
    "Mandya", "Mysuru", "Raichur", "Ramanagara", "Shimoga", "Tumakuru",
    "Udupi", "Uttara Kannada", "Vijayapura", "Yadgir", "Dharwad"
]
# De-duplicate
KARNATAKA_DISTRICTS = list(dict.fromkeys(KARNATAKA_DISTRICTS))

DISTRICT_COORDS = {
    "Bagalkote": [16.18, 75.70], "Ballari": [15.14, 76.92],
    "Belagavi": [15.85, 74.50], "Bengaluru Rural": [13.13, 77.57],
    "Bengaluru Urban": [12.97, 77.59], "Bidar": [17.91, 77.52],
    "Chamarajanagara": [11.92, 76.94], "Chikkaballapura": [13.44, 77.73],
    "Chikkamagaluru": [13.32, 75.77], "Chitradurga": [14.23, 76.40],
    "Dakshina Kannada": [12.87, 74.88], "Davanagere": [14.46, 75.92],
    "Dharwad": [15.46, 75.01], "Gadag": [15.43, 75.63],
    "Hassan": [13.00, 76.10], "Haveri": [14.79, 75.40],
    "Kalaburagi": [17.33, 76.83], "Kodagu": [12.42, 75.74],
    "Kolar": [13.14, 78.13], "Koppal": [15.35, 76.15],
    "Mandya": [12.52, 76.90], "Mysuru": [12.30, 76.64],
    "Raichur": [16.21, 77.35], "Ramanagara": [12.71, 77.28],
    "Shimoga": [13.93, 75.57], "Tumakuru": [13.34, 77.12],
    "Udupi": [13.34, 74.74], "Uttara Kannada": [14.68, 74.69],
    "Vijayapura": [16.83, 75.71], "Yadgir": [16.77, 77.14],
}

CATEGORIES = [
    "Merchant payments", "Peer-to-peer", "Recharge & bill payments",
    "Financial services", "Others"
]

QUARTERS = [
    "2022-Q1", "2022-Q2", "2022-Q3", "2022-Q4",
    "2023-Q1", "2023-Q2", "2023-Q3", "2023-Q4",
    "2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
    "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4",
]


@st.cache_data
def build_quarterly_data():
    """Build synthetic quarterly transaction data per district."""
    rng = np.random.default_rng(42)
    rows = []
    for dist in KARNATAKA_DISTRICTS:
        # Base volume depends on urbanisation (Bengaluru Urban highest)
        base = 5_000_000 if dist == "Bengaluru Urban" else rng.integers(200_000, 2_000_000)
        growth_rate = rng.uniform(0.02, 0.12)  # per-quarter growth
        noise_std = 0.06
        for qi, q in enumerate(QUARTERS):
            vol = base * (1 + growth_rate) ** qi * (1 + rng.normal(0, noise_std))
            amt = vol * rng.uniform(180, 420)  # avg txn value ₹180-420
            users = int(vol / rng.uniform(4, 12))
            merchants = int(users * rng.uniform(0.05, 0.25))
            rows.append({
                "district": dist, "quarter": q,
                "txn_count": int(max(vol, 1000)),
                "txn_amount_cr": round(amt / 1e7, 2),
                "registered_users": users,
                "registered_merchants": merchants,
            })
    return pd.DataFrame(rows)


@st.cache_data
def build_category_mix():
    """Category-level breakdown per district (latest quarter)."""
    rng = np.random.default_rng(99)
    rows = []
    for dist in KARNATAKA_DISTRICTS:
        weights = rng.dirichlet([3, 2, 2, 1, 0.5])
        for cat, w in zip(CATEGORIES, weights):
            rows.append({"district": dist, "category": cat, "share_pct": round(w * 100, 1)})
    return pd.DataFrame(rows)


@st.cache_data
def build_signals(qdf: pd.DataFrame):
    """Derive signal scores from quarterly data."""
    latest = QUARTERS[-1]
    prev_year = QUARTERS[-4] if len(QUARTERS) >= 5 else QUARTERS[0]

    latest_df = qdf[qdf.quarter == latest].set_index("district")
    prev_df = qdf[qdf.quarter == prev_year].set_index("district")

    signals = []
    for dist in KARNATAKA_DISTRICTS:
        if dist not in latest_df.index or dist not in prev_df.index:
            continue
        cur = latest_df.loc[dist]
        prv = prev_df.loc[dist]
        yoy_txn = (cur.txn_count - prv.txn_count) / max(prv.txn_count, 1) * 100
        yoy_amt = (cur.txn_amount_cr - prv.txn_amount_cr) / max(prv.txn_amount_cr, 0.01) * 100
        momentum = (yoy_txn * 0.6 + yoy_amt * 0.4)
        merchant_density = cur.registered_merchants / max(cur.registered_users, 1) * 1000
        composite = momentum * 0.5 + merchant_density * 0.3 + yoy_amt * 0.2
        # Normalise composite to 0-100 later
        signals.append({
            "district": dist,
            "txn_count": int(cur.txn_count),
            "txn_amount_cr": cur.txn_amount_cr,
            "yoy_txn_growth_pct": round(yoy_txn, 1),
            "yoy_amt_growth_pct": round(yoy_amt, 1),
            "momentum": round(momentum, 1),
            "merchant_density": round(merchant_density, 1),
            "registered_users": int(cur.registered_users),
            "registered_merchants": int(cur.registered_merchants),
            "composite_raw": composite,
        })
    sdf = pd.DataFrame(signals)
    mn, mx = sdf.composite_raw.min(), sdf.composite_raw.max()
    sdf["signal_score"] = ((sdf.composite_raw - mn) / max(mx - mn, 1) * 100).round(1)
    sdf["signal_label"] = sdf.signal_score.apply(
        lambda s: "🟢 Strong" if s >= 65 else ("🟡 Moderate" if s >= 35 else "🔴 Weak")
    )
    sdf.drop(columns=["composite_raw"], inplace=True)
    return sdf.sort_values("signal_score", ascending=False).reset_index(drop=True)


# ── build data ──
quarterly_df = build_quarterly_data()
category_df = build_category_mix()
signals_df = build_signals(quarterly_df)

# ═══════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════
st.sidebar.markdown("## 📡 PULSE//SIGNAL")
st.sidebar.caption("Karnataka Economic Radar")
st.sidebar.markdown("---")

VIEW = st.sidebar.radio(
    "View",
    ["📡 Radar", "🔍 District Deep-Dive", "🏆 Discovery",
     "🔄 Compare", "🔮 Forecast", "📖 Methodology"],
)

st.sidebar.markdown("---")
exclude_blu = st.sidebar.checkbox("Exclude Bengaluru Urban", value=True)
if exclude_blu:
    working_signals = signals_df[signals_df.district != "Bengaluru Urban"].reset_index(drop=True)
    working_quarterly = quarterly_df[quarterly_df.district != "Bengaluru Urban"]
else:
    working_signals = signals_df.copy()
    working_quarterly = quarterly_df.copy()

st.sidebar.markdown("---")
st.sidebar.info(f"📊 {len(working_signals)} districts · {len(QUARTERS)} quarters")

# ═══════════════════════════════════════════════════════════════════
#  VIEW: RADAR
# ═══════════════════════════════════════════════════════════════════
if VIEW == "📡 Radar":
    st.markdown('<div class="main-title">📡 PULSE//SIGNAL — Karnataka Radar</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Composite economic signal score per district</div>', unsafe_allow_html=True)

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Districts Tracked", len(working_signals))
    c2.metric("Avg Signal Score", f"{working_signals.signal_score.mean():.1f}")
    strong = (working_signals.signal_score >= 65).sum()
    c3.metric("🟢 Strong Signals", strong)
    c4.metric("Median YoY Txn Growth", f"{working_signals.yoy_txn_growth_pct.median():.1f}%")

    st.markdown("---")

    # Folium choropleth-style map with circle markers sized by score
    m = folium.Map(location=[14.5, 76.0], zoom_start=7, tiles="OpenStreetMap")
    for _, row in working_signals.iterrows():
        coords = DISTRICT_COORDS.get(row.district)
        if not coords:
            continue
        score = row.signal_score
        color = "#2E7D32" if score >= 65 else ("#F57F17" if score >= 35 else "#C62828")
        folium.CircleMarker(
            location=coords,
            radius=max(score / 5, 4),
            color=color, fill=True, fill_color=color, fill_opacity=0.65,
            popup=folium.Popup(
                f"<b>{row.district}</b><br>"
                f"Signal: {score}<br>"
                f"YoY Txn: {row.yoy_txn_growth_pct}%<br>"
                f"Momentum: {row.momentum}", max_width=220
            ),
            tooltip=f"{row.district}: {score}",
        ).add_to(m)
    st_folium(m, width=None, height=550, returned_objects=[])

    # Bar chart of scores
    st.subheader("Signal Score Ranking")
    fig = px.bar(
        working_signals, x="signal_score", y="district", orientation="h",
        color="signal_score", color_continuous_scale="RdYlGn",
        labels={"signal_score": "Score", "district": ""},
    )
    fig.update_layout(height=max(len(working_signals) * 22, 400), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
#  VIEW: DISTRICT DEEP-DIVE
# ═══════════════════════════════════════════════════════════════════
elif VIEW == "🔍 District Deep-Dive":
    st.markdown('<div class="main-title">🔍 District Deep-Dive</div>', unsafe_allow_html=True)

    dist = st.selectbox("Choose a district", working_signals.district.tolist())
    sig_row = working_signals[working_signals.district == dist].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Signal Score", sig_row.signal_score)
    c2.metric("YoY Txn Growth", f"{sig_row.yoy_txn_growth_pct}%")
    c3.metric("Momentum", sig_row.momentum)
    c4.metric("Merchant Density", f"{sig_row.merchant_density}/1k users")

    st.markdown("---")

    # Quarterly trend
    dq = quarterly_df[quarterly_df.district == dist].sort_values("quarter")
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📈 Quarterly Transaction Volume")
        fig = px.line(dq, x="quarter", y="txn_count", markers=True)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    with col_r:
        st.subheader("💰 Quarterly Transaction Amount (₹ Cr)")
        fig = px.area(dq, x="quarter", y="txn_amount_cr", color_discrete_sequence=["#6C63FF"])
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Category mix
    st.subheader("🗂️ Category Mix (latest quarter)")
    cat = category_df[category_df.district == dist]
    fig = px.pie(cat, values="share_pct", names="category", hole=0.45,
                 color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)

    # Users & merchants
    st.subheader("👥 Users & Merchants Growth")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dq.quarter, y=dq.registered_users, name="Users", mode="lines+markers"))
    fig.add_trace(go.Scatter(x=dq.quarter, y=dq.registered_merchants, name="Merchants", mode="lines+markers",
                             yaxis="y2"))
    fig.update_layout(
        height=350,
        yaxis=dict(title="Registered Users"),
        yaxis2=dict(title="Merchants", overlaying="y", side="right"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
#  VIEW: DISCOVERY
# ═══════════════════════════════════════════════════════════════════
elif VIEW == "🏆 Discovery":
    st.markdown('<div class="main-title">🏆 Discovery — District Rankings</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Sort by any column to explore signal dimensions</div>', unsafe_allow_html=True)

    display_cols = [
        "district", "signal_score", "signal_label", "yoy_txn_growth_pct",
        "yoy_amt_growth_pct", "momentum", "merchant_density",
        "txn_count", "txn_amount_cr",
    ]
    st.dataframe(
        working_signals[display_cols].style.background_gradient(
            subset=["signal_score"], cmap="RdYlGn"
        ),
        use_container_width=True,
        height=600,
    )

    # Top-5 cards
    st.markdown("---")
    st.subheader("🥇 Top 5 Emerging Districts")
    top5 = working_signals.head(5)
    cols = st.columns(5)
    for col, (_, r) in zip(cols, top5.iterrows()):
        with col:
            st.metric(r.district, f"{r.signal_score}", delta=f"{r.yoy_txn_growth_pct}% YoY")


# ═══════════════════════════════════════════════════════════════════
#  VIEW: COMPARE
# ═══════════════════════════════════════════════════════════════════
elif VIEW == "🔄 Compare":
    st.markdown('<div class="main-title">🔄 Compare Two Districts</div>', unsafe_allow_html=True)

    all_dists = working_signals.district.tolist()
    c1, c2 = st.columns(2)
    d1 = c1.selectbox("District A", all_dists, index=0)
    d2 = c2.selectbox("District B", all_dists, index=min(1, len(all_dists) - 1))

    if d1 == d2:
        st.warning("Pick two different districts to compare.")
    else:
        s1 = working_signals[working_signals.district == d1].iloc[0]
        s2 = working_signals[working_signals.district == d2].iloc[0]

        # Side-by-side metrics
        col_a, col_vs, col_b = st.columns([5, 1, 5])
        metrics = [
            ("Signal Score", "signal_score"), ("Momentum", "momentum"),
            ("YoY Txn Growth %", "yoy_txn_growth_pct"),
            ("Merchant Density", "merchant_density"),
        ]
        with col_a:
            st.subheader(d1)
            for label, key in metrics:
                st.metric(label, getattr(s1, key))
        with col_vs:
            st.markdown("<br><br><br><h2 style='text-align:center'>vs</h2>", unsafe_allow_html=True)
        with col_b:
            st.subheader(d2)
            for label, key in metrics:
                st.metric(label, getattr(s2, key))

        st.markdown("---")

        # Overlay quarterly trends
        st.subheader("📈 Transaction Volume — Overlay")
        q1 = quarterly_df[quarterly_df.district == d1][["quarter", "txn_count"]].rename(columns={"txn_count": d1})
        q2 = quarterly_df[quarterly_df.district == d2][["quarter", "txn_count"]].rename(columns={"txn_count": d2})
        merged = q1.merge(q2, on="quarter")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=merged.quarter, y=merged[d1], name=d1, mode="lines+markers"))
        fig.add_trace(go.Scatter(x=merged.quarter, y=merged[d2], name=d2, mode="lines+markers"))
        fig.update_layout(height=400, yaxis_title="Transactions")
        st.plotly_chart(fig, use_container_width=True)

        # Radar chart
        st.subheader("🕸️ Signal Radar")
        dims = ["signal_score", "momentum", "yoy_txn_growth_pct", "yoy_amt_growth_pct", "merchant_density"]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=[getattr(s1, d) for d in dims], theta=dims, fill="toself", name=d1))
        fig.add_trace(go.Scatterpolar(r=[getattr(s2, d) for d in dims], theta=dims, fill="toself", name=d2))
        fig.update_layout(height=450, polar=dict(radialaxis=dict(visible=True)))
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
#  VIEW: FORECAST  (★ NEW FEATURE ★)
# ═══════════════════════════════════════════════════════════════════
elif VIEW == "🔮 Forecast":
    st.markdown('<div class="main-title">🔮 District Growth Forecast</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Trend extrapolation with confidence bands — <b>NEW FEATURE</b></div>',
                unsafe_allow_html=True)

    st.info("📌 This forecast uses simple linear-trend extrapolation on quarterly "
            "transaction volumes. It is illustrative, not a financial prediction.")

    fc1, fc2 = st.columns([1, 3])
    with fc1:
        forecast_dist = st.selectbox("District", working_signals.district.tolist(), key="fc_dist")
        horizon = st.slider("Forecast horizon (quarters)", 1, 8, 4)
        conf_level = st.select_slider("Confidence band", ["Narrow", "Medium", "Wide"], value="Medium")
        conf_mult = {"Narrow": 0.8, "Medium": 1.5, "Wide": 2.5}[conf_level]

    # Fit simple linear trend
    dq = quarterly_df[quarterly_df.district == forecast_dist].sort_values("quarter").reset_index(drop=True)
    x = np.arange(len(dq))
    y = dq.txn_count.values.astype(float)
    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs
    residuals = y - np.polyval(coeffs, x)
    std_err = residuals.std()

    # Project
    future_x = np.arange(len(dq), len(dq) + horizon)
    future_y = np.polyval(coeffs, future_x)
    future_upper = future_y + conf_mult * std_err * np.sqrt(np.arange(1, horizon + 1))
    future_lower = np.maximum(future_y - conf_mult * std_err * np.sqrt(np.arange(1, horizon + 1)), 0)

    future_labels = [f"FC-Q{i+1}" for i in range(horizon)]
    all_labels = list(dq.quarter) + future_labels

    with fc2:
        fig = go.Figure()
        # Historical
        fig.add_trace(go.Scatter(x=list(dq.quarter), y=y.tolist(), mode="lines+markers",
                                 name="Historical", line=dict(color="#6C63FF", width=3)))
        # Trend line (historical)
        fig.add_trace(go.Scatter(x=list(dq.quarter), y=np.polyval(coeffs, x).tolist(),
                                 mode="lines", name="Trend", line=dict(dash="dot", color="#999")))
        # Forecast
        fig.add_trace(go.Scatter(x=future_labels, y=future_y.tolist(), mode="lines+markers",
                                 name="Forecast", line=dict(color="#E91E63", width=3, dash="dash")))
        # Confidence band
        fig.add_trace(go.Scatter(
            x=future_labels + future_labels[::-1],
            y=future_upper.tolist() + future_lower[::-1].tolist(),
            fill="toself", fillcolor="rgba(233,30,99,0.12)",
            line=dict(width=0), name=f"Confidence ({conf_level})", showlegend=True,
        ))
        fig.update_layout(height=450, xaxis_title="Quarter", yaxis_title="Transaction Count",
                          title=f"{forecast_dist} — {horizon}-Quarter Forecast")
        st.plotly_chart(fig, use_container_width=True)

    # Forecast summary metrics
    st.markdown("---")
    mc1, mc2, mc3, mc4 = st.columns(4)
    growth_total = ((future_y[-1] - y[-1]) / max(y[-1], 1)) * 100
    mc1.metric("Current Quarterly Txns", f"{int(y[-1]):,}")
    mc2.metric(f"Projected (Q+{horizon})", f"{int(future_y[-1]):,}")
    mc3.metric("Projected Growth", f"{growth_total:.1f}%")
    mc4.metric("Trend Slope (per Q)", f"{int(slope):,} txns")

    # All-district forecast rankings
    st.markdown("---")
    st.subheader("📊 All-District Growth Forecast Rankings")
    st.caption(f"Projected growth over next {horizon} quarters (linear extrapolation)")

    ranking_rows = []
    for dist in working_signals.district:
        dq_r = quarterly_df[quarterly_df.district == dist].sort_values("quarter").reset_index(drop=True)
        x_r = np.arange(len(dq_r))
        y_r = dq_r.txn_count.values.astype(float)
        c_r = np.polyfit(x_r, y_r, 1)
        proj = np.polyval(c_r, len(dq_r) + horizon - 1)
        pct = ((proj - y_r[-1]) / max(y_r[-1], 1)) * 100
        ranking_rows.append({
            "district": dist,
            "current_txns": int(y_r[-1]),
            "projected_txns": int(max(proj, 0)),
            "growth_pct": round(pct, 1),
            "trend_slope": int(c_r[0]),
        })
    rank_df = pd.DataFrame(ranking_rows).sort_values("growth_pct", ascending=False).reset_index(drop=True)
    rank_df.index += 1
    rank_df.index.name = "Rank"

    fig = px.bar(rank_df, x="growth_pct", y="district", orientation="h",
                 color="growth_pct", color_continuous_scale="RdYlGn",
                 labels={"growth_pct": "Projected Growth %", "district": ""})
    fig.update_layout(height=max(len(rank_df) * 22, 400), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(rank_df, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
#  VIEW: METHODOLOGY
# ═══════════════════════════════════════════════════════════════════
elif VIEW == "📖 Methodology":
    st.markdown('<div class="main-title">📖 Methodology</div>', unsafe_allow_html=True)

    st.markdown("""
### Data Pipeline

```
PhonePe Pulse (public JSON) ──► scripts/build_reconciliation.py
                                        │
Census 2011 population ─────────────────┤
                                        ▼
                              scripts/build_analytical_dataset.py
                                        │
                                        ▼
                              scripts/build_signals.py ──► district_signals.csv
                                        │
                                        ▼
                              streamlit_app/app.py  (this dashboard)
```

### Signal Construction

| Signal | Formula | Weight |
|--------|---------|--------|
| **Momentum** | 0.6 × YoY-txn-growth + 0.4 × YoY-amount-growth | 50% |
| **Merchant Density** | merchants / users × 1000 | 30% |
| **Amount Growth** | YoY transaction-amount growth % | 20% |

Composite score is min-max normalised to **0 – 100**.

### Signal Labels
- 🟢 **Strong** — score ≥ 65
- 🟡 **Moderate** — 35 ≤ score < 65
- 🔴 **Weak** — score < 35

### New: Forecast Model
The **🔮 Forecast** view fits a simple **ordinary least-squares linear trend**
on quarterly transaction counts and projects forward.  Confidence bands widen
with √t to reflect increasing uncertainty.

> ⚠️ This is a demonstration model. Real forecasts would incorporate
> seasonality, macro indicators, and non-linear methods.

### Data Sources
- [PhonePe Pulse](https://github.com/PhonePe/pulse) — open transaction aggregates
- Census 2011 — Karnataka district population baselines
    """)

# ─────────────────────────── footer ────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#aaa;font-size:.85rem'>"
    "📡 PULSE//SIGNAL Karnataka · Built with Streamlit · "
    f"Data as of {QUARTERS[-1]}</div>",
    unsafe_allow_html=True,
)
