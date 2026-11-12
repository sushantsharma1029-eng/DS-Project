from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Sales Data Explorer", page_icon="📊", layout="wide")
st.title("📊 Sales Data Explorer")
st.caption("Upload, validate, clean, and explore a sales dataset interactively.")

SAMPLE_PATH = Path(__file__).parent / "data" / "experiment10_raw_dataset.csv"
SALES_FIELDS = {"sales": ["Sales", "Revenue", "Amount"], "profit": ["Profit", "Net Profit"], "quantity": ["Quantity", "Qty"], "order": ["Order ID", "OrderID", "Order Number"]}


def read_dataset(upload: Any) -> pd.DataFrame:
    """Read a CSV, Excel, or JSON upload into a DataFrame."""
    suffix = Path(upload.name).suffix.lower()
    content = upload.getvalue()
    if suffix == ".csv":
        return pd.read_csv(BytesIO(content))
    if suffix == ".xlsx":
        return pd.read_excel(BytesIO(content))
    if suffix == ".json":
        try:
            return pd.read_json(BytesIO(content))
        except ValueError:
            return pd.read_json(BytesIO(content), lines=True)
    raise ValueError("Unsupported file type. Upload a .csv, .xlsx, or .json file.")


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace from column names and string values."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for col in out.columns:
        if not (pd.api.types.is_object_dtype(out[col]) or isinstance(out[col].dtype, pd.StringDtype)):
            continue
        out[col] = out[col].map(lambda value: value.strip() if isinstance(value, str) else value)
    return out


def statistical_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return reusable numeric and categorical statistical summaries."""
    if df.empty:
        return pd.DataFrame()
    summary = df.describe(include="all").transpose()
    return summary


def detect_column(columns: list[str], candidates: list[str]) -> str | None:
    lookup = {str(c).strip().lower(): c for c in columns}
    return next((lookup[name.lower()] for name in candidates if name.lower() in lookup), None)


def display_validation(df: pd.DataFrame) -> None:
    """Show schema and integrity checks for the loaded dataset."""
    st.subheader("Data validation")
    a, b, c = st.columns(3)
    a.metric("Rows", f"{len(df):,}")
    b.metric("Columns", f"{len(df.columns):,}")
    c.metric("Duplicate records", f"{int(df.duplicated().sum()):,}")
    schema = pd.DataFrame({"Column": df.columns, "Data type": [str(t) for t in df.dtypes], "Missing values": df.isna().sum().values, "Missing %": (df.isna().mean().values * 100).round(2)})
    st.dataframe(schema, width="stretch", hide_index=True)


def main() -> None:
    with st.sidebar:
        st.header("Data source")
        upload = st.file_uploader("Upload a dataset", type=["csv", "xlsx", "json"])
        use_sample = st.checkbox("Use included experiment dataset", value=upload is None and SAMPLE_PATH.exists())

    try:
        if upload is not None:
            raw = read_dataset(upload)
            source_label = upload.name
        elif use_sample and SAMPLE_PATH.exists():
            raw = pd.read_csv(SAMPLE_PATH)
            source_label = SAMPLE_PATH.name
        else:
            st.info("Upload a CSV, Excel (.xlsx), or JSON file to begin.")
            return
        if raw.empty:
            st.error("The uploaded file contains no rows.")
            return
        if len(raw.columns) == 0:
            st.error("The uploaded file contains no columns.")
            return
        st.caption(f"Loaded **{source_label}**")
        display_validation(raw)

        st.subheader("Preprocessing")
        p1, p2, p3 = st.columns(3)
        with p1:
            trim_values = st.checkbox("Trim text whitespace", value=True)
        with p2:
            drop_duplicates = st.checkbox("Remove duplicate records", value=True)
        with p3:
            missing_policy = st.selectbox("Missing value handling", ["Keep as is", "Drop rows with missing values", "Fill numeric with median, text with mode"])

        df = clean_column_names(raw) if trim_values else raw.copy()
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col]):
                numeric = pd.to_numeric(df[col].str.replace(",", "", regex=False), errors="coerce")
                nonmissing = int(df[col].notna().sum())
                if nonmissing and int(numeric.notna().sum()) / nonmissing >= 0.8:
                    df[col] = numeric.where(np.isfinite(numeric))
        for col in df.select_dtypes(include="number").columns:
            df[col] = df[col].where(np.isfinite(df[col]))
        duplicate_count = int(df.duplicated().sum())
        if drop_duplicates and duplicate_count:
            df = df.drop_duplicates().copy()
        if missing_policy == "Drop rows with missing values":
            df = df.dropna().copy()
        elif missing_policy.startswith("Fill"):
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    median = df[col].median()
                    if pd.notna(median):
                        df[col] = df[col].fillna(median)
                elif df[col].notna().any():
                    mode = df[col].mode(dropna=True)
                    if not mode.empty:
                        df[col] = df[col].fillna(mode.iloc[0])
        for col in df.columns:
            if any(word in str(col).lower() for word in ["date", "time"]):
                parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
                if parsed.notna().any():
                    df[col] = parsed
        st.caption(f"Working data: {len(df):,} rows × {len(df.columns):,} columns. {duplicate_count:,} duplicate row(s) detected before cleaning.")

        st.subheader("Interactive filters")
        dimensions = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_datetime64_any_dtype(df[c]) and df[c].nunique(dropna=True) > 1]
        date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
        filter_cols = list(dict.fromkeys(dimensions + date_cols))[:3]
        filtered = df.copy()
        filters = st.columns(max(1, len(filter_cols)))
        for col, slot in zip(filter_cols, filters):
            if col in date_cols:
                valid = filtered[col].dropna()
                if not valid.empty:
                    date_range = slot.date_input(f"{col} range", value=(valid.min().date(), valid.max().date()), key=f"filter_{col}")
                    if isinstance(date_range, tuple) and len(date_range) == 2:
                        filtered = filtered[filtered[col].dt.date.between(date_range[0], date_range[1])]
            else:
                vals = sorted(filtered[col].dropna().astype(str).unique().tolist())
                selected = slot.multiselect(f"{col}", vals, default=vals, key=f"filter_{col}")
                filtered = filtered[filtered[col].astype(str).isin(selected)]
        if not filter_cols:
            st.info("No categorical or date columns with multiple values were found for filtering.")

        sales_col = detect_column(list(filtered.columns), SALES_FIELDS["sales"])
        profit_col = detect_column(list(filtered.columns), SALES_FIELDS["profit"])
        qty_col = detect_column(list(filtered.columns), SALES_FIELDS["quantity"])
        order_col = detect_column(list(filtered.columns), SALES_FIELDS["order"])
        kpi_cols = st.columns(5)
        if sales_col and pd.api.types.is_numeric_dtype(filtered[sales_col]):
            total_sales = filtered[sales_col].sum()
            kpi_cols[0].metric("Total Sales", f"${total_sales:,.2f}")
        else:
            total_sales = None
            kpi_cols[0].metric("Total Sales", "—", help="Upload a numeric Sales, Revenue, or Amount column.")
        if profit_col and pd.api.types.is_numeric_dtype(filtered[profit_col]):
            total_profit = filtered[profit_col].sum()
            kpi_cols[1].metric("Total Profit", f"${total_profit:,.2f}")
        else:
            total_profit = None
            kpi_cols[1].metric("Total Profit", "—", help="Upload a numeric Profit column.")
        kpi_cols[2].metric("Total Orders", f"{filtered[order_col].nunique(dropna=True):,}" if order_col else "—", help="Counts unique Order ID values.")
        kpi_cols[3].metric("Total Quantity Sold", f"{filtered[qty_col].sum():,.0f}" if qty_col and pd.api.types.is_numeric_dtype(filtered[qty_col]) else "—")
        margin = total_profit / total_sales * 100 if total_profit is not None and total_sales not in (None, 0) else None
        kpi_cols[4].metric("Profit Margin", f"{margin:.2f}%" if margin is not None else "—")

        st.subheader("Interactive visualizations")
        chart_tabs = st.tabs(["Sales breakdown", "Trend", "Comparison"])
        with chart_tabs[0]:
            category_col = next((c for c in ["Category", "Sub-Category", "Region", "Segment"] if c in filtered.columns), dimensions[0] if dimensions else None)
            if sales_col and category_col:
                chart_data = filtered.groupby(category_col, dropna=False)[sales_col].sum().reset_index().sort_values(sales_col, ascending=False)
                st.plotly_chart(px.bar(chart_data, x=category_col, y=sales_col, color=category_col, title=f"{sales_col} by {category_col}"), width="stretch")
            elif sales_col:
                st.plotly_chart(px.histogram(filtered, x=sales_col, title=f"Distribution of {sales_col}"), width="stretch")
            else:
                st.info("Add a numeric sales field to display a sales breakdown.")
        with chart_tabs[1]:
            if date_cols and sales_col:
                trend = filtered.dropna(subset=[date_cols[0]]).set_index(date_cols[0]).resample("MS")[sales_col].sum().reset_index()
                st.plotly_chart(px.line(trend, x=date_cols[0], y=sales_col, markers=True, title=f"Monthly {sales_col} trend"), width="stretch")
            elif date_cols and profit_col:
                trend = filtered.dropna(subset=[date_cols[0]]).set_index(date_cols[0]).resample("MS")[profit_col].sum().reset_index()
                st.plotly_chart(px.line(trend, x=date_cols[0], y=profit_col, markers=True, title=f"Monthly {profit_col} trend"), width="stretch")
            else:
                st.info("A date column and numeric sales or profit field are needed for the trend chart.")
        with chart_tabs[2]:
            compare_col = next((c for c in ["Region", "Segment", "Ship Mode", "Category", "Sub-Category"] if c in filtered.columns and c != category_col), dimensions[-1] if len(dimensions) > 1 else None)
            if compare_col and sales_col:
                metric_cols = [sales_col] + ([profit_col] if profit_col else [])
                agg = filtered.groupby(compare_col, dropna=False)[metric_cols].sum().reset_index().melt(id_vars=compare_col, var_name="Metric", value_name="Value")
                st.plotly_chart(px.bar(agg, x=compare_col, y="Value", color="Metric", barmode="group", title=f"Sales and profit by {compare_col}"), width="stretch")
            elif dimensions and qty_col:
                agg = filtered.groupby(dimensions[0], dropna=False)[qty_col].sum().reset_index()
                st.plotly_chart(px.pie(agg, names=dimensions[0], values=qty_col, title=f"{qty_col} by {dimensions[0]}"), width="stretch")
            else:
                st.info("Add a category and numeric sales, profit, or quantity field for the comparison chart.")

        with st.expander("Statistical summary and filtered data"):
            st.markdown("**Statistical summary**")
            st.dataframe(statistical_summary(filtered), width="stretch")
            st.markdown("**Filtered data preview**")
            st.dataframe(filtered.head(500), width="stretch")
            st.download_button("Download filtered data as CSV", filtered.to_csv(index=False).encode("utf-8"), "filtered_data.csv", "text/csv")
    except Exception as exc:
        st.error(f"Could not load or analyze this dataset: {exc}")
        st.caption("Check that the file is valid and contains a header row. Supported formats: CSV, XLSX, and JSON.")


if __name__ == "__main__":
    main()
