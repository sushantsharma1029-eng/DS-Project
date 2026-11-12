# Sales Data Explorer

An interactive Streamlit application for uploading, validating, cleaning, and exploring sales data.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Upload CSV, Excel (`.xlsx`), or JSON files from the sidebar. The included experiment dataset loads by default. The app reports dimensions, column types, missing values, and duplicate records; offers configurable cleaning; applies up to three interactive filters; displays sales KPIs; and provides three interactive charts.

The KPI fields are detected from common names (`Sales`/`Revenue`/`Amount`, `Profit`, `Quantity`/`Qty`, and `Order ID` variants). If a matching field is absent, its KPI shows a dash.

## Streamlit Community Cloud

Push this folder to a GitHub repository, then create a Community Cloud app using `app.py` as the entry point. Keep `requirements.txt` at the repository root.
