# 🚦 PULSE//SIGNAL — Karnataka Economic Radar

**Identifies economic hotspots in Karnataka from PhonePe Pulse-style public data
and turns raw transaction volumes into explainable signals — momentum, emerging
markets, and next-wave districts (excluding Bengaluru Urban).**

## Views
| View | What it shows |
|------|--------------|
| 📡 Radar | Choropleth map of all 31 districts coloured by composite signal score |
| 🔍 District Deep-Dive | Single-district drilldown: quarterly trends, category mix, peer comparison |
| 🏆 Discovery | Rankings table with sortable columns for every signal dimension |
| 🔄 Compare | Side-by-side comparison of any two districts |
| 📖 Methodology | How signals are built from raw PhonePe data |
| **🔮 Forecast (NEW)** | AI-style trend extrapolation — predicted growth trajectories for each district |

## Quick start
```bash
pip install -r requirements.txt
streamlit run app.py
```

## New Feature Added
**🔮 District Growth Forecast** — uses simple trend extrapolation on quarterly
transaction data to project future growth for each Karnataka district. Includes
confidence bands, growth-rate rankings, and an interactive forecast horizon
slider.

## License
MIT
