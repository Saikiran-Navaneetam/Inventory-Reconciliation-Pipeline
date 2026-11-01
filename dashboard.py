from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

# ============================================================
# CONFIGURATION & PAGE STYLE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "data" / "inventory.duckdb"

st.set_page_config(
    page_title="Inventory Control Tower",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #0B1220; color: #E5E7EB; }
    [data-testid="stSidebar"] {
        background: #111B2E;
        border-right: 1px solid #26344D;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #172B4D, #1D3B70);
        border: 1px solid #304B73;
        padding: 17px 19px;
        border-radius: 12px;
    }
    [data-testid="stMetricLabel"] { color: #C4D3EA; }
    [data-testid="stMetricValue"] { color: #FFFFFF; }
    .main-header {
        font-size: 32px;
        font-weight: 800;
        color: #F8FAFC;
        margin-bottom: 2px;
    }
    .sub-header {
        color: #94A3B8;
        font-size: 14px;
        margin-bottom: 18px;
    }
    .eyebrow {
        color: #60A5FA;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.4px;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #2B3D59;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def style_chart(fig, height=360):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0"),
        margin=dict(l=20, r=20, t=55, b=20),
        legend_title_text="",
    )
    return fig


# ============================================================
# DATABASE ACCESS
# ============================================================

def table_exists(conn, table_name):
    return conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name = ?
        """,
        [table_name],
    ).fetchone()[0] > 0


def table_count(conn, table_name):
    if not table_exists(conn, table_name):
        return None

    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
    )


@st.cache_data(ttl=60)
def load_data():

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    with duckdb.connect(
        str(DATABASE_PATH),
        read_only=True
    ) as conn:

        required = [
            "daily_inventory_balances",
            "inventory_movements",
            "pipeline_runs",
        ]

        missing = [
            name for name in required
            if not table_exists(conn, name)
        ]

        if missing:
            raise RuntimeError(
                "Missing required tables: "
                + ", ".join(missing)
            )

        balances = conn.execute(
            """
            SELECT
                business_date,
                product_id,
                location_id,
                opening_quantity,
                receipts_quantity,
                issues_quantity,
                transfer_in_quantity,
                transfer_out_quantity,
                adjustment_quantity,
                net_movement_quantity,
                closing_quantity,
                negative_stock_flag
            FROM daily_inventory_balances
            ORDER BY business_date
            """
        ).fetchdf()

        movements = conn.execute(
            """
            SELECT
                movement_id,
                product_id,
                location_id,
                movement_type,
                quantity,
                effective_at,
                source_file,
                run_id
            FROM inventory_movements
            """
        ).fetchdf()

        counts = {
            name: table_count(conn, name)
            for name in [
                "raw_inventory_events",
                "inventory_events",
                "rejected_records",
                "inventory_movements",
                "daily_inventory_balances",
            ]
        }

        run_columns = [
            row[0]
            for row in conn.execute(
                "DESCRIBE pipeline_runs"
            ).fetchall()
        ]

        run_total = table_count(
            conn,
            "pipeline_runs"
        ) or 0

        success_count = None
        failed_count = None

        if "status" in run_columns:

            success_count, failed_count = conn.execute(
                """
                SELECT
                    SUM(
                        CASE
                            WHEN UPPER(status) = 'SUCCESS'
                            THEN 1 ELSE 0
                        END
                    ),
                    SUM(
                        CASE
                            WHEN UPPER(status) = 'FAILED'
                            THEN 1 ELSE 0
                        END
                    )
                FROM pipeline_runs
                """
            ).fetchone()

            success_count = int(success_count or 0)
            failed_count = int(failed_count or 0)

    balances["business_date"] = pd.to_datetime(
        balances["business_date"]
    )

    movements["effective_at"] = pd.to_datetime(
        movements["effective_at"]
    )

    run_info = {
        "total_runs": run_total,
        "successful_runs": success_count,
        "failed_runs": failed_count,
    }

    return balances, movements, counts, run_info


# ============================================================
# LOAD AND VALIDATE DATA
# ============================================================

try:

    balances, movements, table_counts, run_info = load_data()

except Exception as exc:

    st.error(
        f"Unable to load dashboard data: {exc}"
    )

    st.stop()


if balances.empty:

    st.warning(
        "No inventory balance records are available."
    )

    st.stop()


# ============================================================
# SIDEBAR, NAVIGATION & FILTERS
# ============================================================

st.sidebar.markdown(
    "<h2 style='color:#60A5FA;'>📦 INVENTORY CONTROL</h2>",
    unsafe_allow_html=True,
)

st.sidebar.caption(
    "INVENTORY RECONCILIATION PLATFORM"
)

st.sidebar.divider()

page = st.sidebar.radio(
    "NAVIGATION",
    [
        "Executive Overview",
        "Inventory Explorer",
        "Warehouse Analysis",
        "Movement Intelligence",
        "Alerts Center",
        "Data Quality Center",
        "Pipeline Monitoring",
        "Reconciliation Center",
    ],
)

st.sidebar.divider()

st.sidebar.subheader(
    "DATA FILTERS"
)

min_date = balances.business_date.min().date()
max_date = balances.business_date.max().date()

date_range = st.sidebar.date_input(
    "Business date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

products = sorted(
    balances.product_id.dropna().unique().tolist()
)

locations = sorted(
    balances.location_id.dropna().unique().tolist()
)

selected_products = st.sidebar.multiselect(
    "Products",
    products,
    default=products,
)

selected_locations = st.sidebar.multiselect(
    "Locations",
    locations,
    default=locations,
)

if not isinstance(date_range, (tuple, list)) or len(date_range) != 2:

    st.info(
        "Select both a start date and an end date."
    )

    st.stop()


start_date, end_date = date_range

if start_date > end_date:

    st.error(
        "The start date must be on or before the end date."
    )

    st.stop()


filtered = balances[
    balances.business_date.dt.date.between(
        start_date,
        end_date
    )
    & balances.product_id.isin(selected_products)
    & balances.location_id.isin(selected_locations)
].copy()


if filtered.empty:

    st.warning(
        "No balance records match the selected filters."
    )

    st.stop()


latest_date = filtered.business_date.max()

latest = filtered[
    filtered.business_date == latest_date
].copy()


filtered_movements = movements[
    movements.effective_at.dt.date.between(
        start_date,
        end_date
    )
    & movements.product_id.isin(selected_products)
    & movements.location_id.isin(selected_locations)
].copy()


# ============================================================
# NEGATIVE STOCK CALCULATIONS
# ============================================================

# These are product-location positions, not unique products.

negative_positions = latest[
    latest.negative_stock_flag.fillna(False).astype(bool)
].copy()

negative_position_count = len(negative_positions)

affected_products = (
    negative_positions.product_id.nunique()
)

affected_locations = (
    negative_positions.location_id.nunique()
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    "<div class='eyebrow'>"
    "INVENTORY OPERATIONS / ANALYTICS"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    "<div class='main-header'>"
    "Inventory Control Tower"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    "<div class='sub-header'>"
    "Inventory position • Movement intelligence • "
    "Data quality • Pipeline observability"
    "</div>",
    unsafe_allow_html=True,
)

st.caption(
    f"Reporting period: {start_date} to {end_date} "
    f"| Latest balance date: {latest_date.date()}"
)


# ============================================================
# 1. EXECUTIVE OVERVIEW
# ============================================================

if page == "Executive Overview":

    st.subheader(
        "Executive Overview"
    )

    receipts = float(
        filtered.receipts_quantity.sum()
    )

    issues = float(
        filtered.issues_quantity.sum()
    )

    closing_stock = float(
        latest.closing_quantity.sum()
    )

    k1, k2, k3, k4 = st.columns(4)

    k1.metric(
        "Latest Closing Stock",
        f"{closing_stock:,.0f}"
    )

    k2.metric(
        "Receipts in Period",
        f"{receipts:,.0f}"
    )

    k3.metric(
        "Issues in Period",
        f"{issues:,.0f}"
    )

    k4.metric(
        "Negative Stock Positions",
        f"{negative_position_count:,}"
    )

    st.caption(
        f"Affected products: {affected_products} | "
        f"Affected locations: {affected_locations}. "
        "Negative positions count product-location combinations, "
        "not unique products."
    )

    st.divider()

    left, right = st.columns([1.15, 1])

    with left:

        st.markdown(
            "### Latest Inventory Health"
        )

        health = pd.DataFrame(
            {
                "Stock Status": [
                    "Non-negative",
                    "Negative",
                ],
                "Positions": [
                    len(latest) - negative_position_count,
                    negative_position_count,
                ],
            }
        )

        fig = px.pie(
            health,
            names="Stock Status",
            values="Positions",
            hole=0.66,
            color="Stock Status",
            color_discrete_map={
                "Non-negative": "#10B981",
                "Negative": "#EF4444",
            },
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent",
        )

        st.plotly_chart(
            style_chart(fig),
            use_container_width=True,
        )

    with right:

        st.markdown(
            "### Operational Coverage"
        )

        a, b = st.columns(2)

        a.metric(
            "Products",
            f"{latest.product_id.nunique():,}"
        )

        b.metric(
            "Locations",
            f"{latest.location_id.nunique():,}"
        )

        a.metric(
            "Balance Rows",
            f"{len(filtered):,}"
        )

        b.metric(
            "Movement Rows",
            f"{len(filtered_movements):,}"
        )

        st.markdown(
            "### Pipeline Snapshot"
        )

        st.metric(
            "Recorded Pipeline Runs",
            f"{run_info['total_runs']:,}"
        )

            # ============================================================
    # INVENTORY TREND ANALYSIS
    # ============================================================

    st.divider()
    st.subheader("Inventory Trend Analysis")

    # Aggregate daily metrics for the selected products, locations,
    # and date range. Each row represents one business date.
    daily_trends = (
        filtered.assign(
            negative_position=filtered[
                "negative_stock_flag"
            ].fillna(False).astype(bool).astype(int)
        )
        .groupby("business_date", as_index=False)
        .agg(
            Closing_Stock=("closing_quantity", "sum"),
            Receipts=("receipts_quantity", "sum"),
            Issues=("issues_quantity", "sum"),
            Net_Movement=("net_movement_quantity", "sum"),
            Negative_Positions=("negative_position", "sum"),
        )
        .sort_values("business_date")
    )

    # ------------------------------------------------------------
    # 1. CLOSING STOCK TREND
    # ------------------------------------------------------------

    st.markdown("### 1. Daily Closing Stock Trend")

    st.caption(
        "Total closing inventory across the selected products "
        "and locations at the end of each business day."
    )

    fig = px.line(
        daily_trends,
        x="business_date",
        y="Closing_Stock",
        markers=True,
        title="Inventory Position Over Time",
    )

    fig.update_traces(
        line=dict(width=3, color="#38BDF8"),
        marker=dict(size=7),
        hovertemplate=(
            "Date: %{x|%d %b %Y}<br>"
            "Closing Stock: %{y:,.0f}"
            "<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title="Business Date",
        yaxis_title="Closing Stock Quantity",
        hovermode="x unified",
    )

    st.plotly_chart(
        style_chart(fig, 420),
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # 2. RECEIPTS VS ISSUES TREND
    # ------------------------------------------------------------

    st.markdown("### 2. Daily Receipts vs Issues")

    st.caption(
        "Compares incoming inventory with outgoing inventory "
        "for each business day."
    )

    movement_trend = daily_trends.melt(
        id_vars="business_date",
        value_vars=["Receipts", "Issues"],
        var_name="Movement",
        value_name="Quantity",
    )

    fig = px.line(
        movement_trend,
        x="business_date",
        y="Quantity",
        color="Movement",
        markers=True,
        color_discrete_map={
            "Receipts": "#38BDF8",
            "Issues": "#F59E0B",
        },
        title="Daily Inventory Inflows and Outflows",
    )

    fig.update_layout(
        xaxis_title="Business Date",
        yaxis_title="Quantity",
        hovermode="x unified",
    )

    st.plotly_chart(
        style_chart(fig, 420),
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # 3. NEGATIVE STOCK TREND
    # ------------------------------------------------------------

    st.markdown("### 3. Negative Stock Trend")

    st.caption(
        "Counts product-location combinations with negative "
        "closing inventory on each business day."
    )

    fig = px.line(
        daily_trends,
        x="business_date",
        y="Negative_Positions",
        markers=True,
        title="Negative Inventory Positions Over Time",
    )

    fig.update_traces(
        line=dict(width=3, color="#EF4444"),
        marker=dict(size=7),
        hovertemplate=(
            "Date: %{x|%d %b %Y}<br>"
            "Negative Positions: %{y:,.0f}"
            "<extra></extra>"
        ),
    )

    fig.update_layout(
        xaxis_title="Business Date",
        yaxis_title="Negative Product-Location Positions",
        hovermode="x unified",
    )

    st.plotly_chart(
        style_chart(fig, 420),
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # 4. NET MOVEMENT TREND
    # ------------------------------------------------------------

    st.markdown("### 4. Daily Net Inventory Movement")

    st.caption(
        "Positive values indicate a net increase in inventory. "
        "Negative values indicate a net decrease. Transfers and "
        "adjustments are included."
    )

    fig = px.bar(
        daily_trends,
        x="business_date",
        y="Net_Movement",
        title="Daily Net Inventory Movement",
    )

    fig.update_traces(
        marker_color="#A78BFA",
        hovertemplate=(
            "Date: %{x|%d %b %Y}<br>"
            "Net Movement: %{y:,.0f}"
            "<extra></extra>"
        ),
    )

    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="#94A3B8",
    )

    fig.update_layout(
        xaxis_title="Business Date",
        yaxis_title="Net Movement Quantity",
        hovermode="x unified",
    )

    st.plotly_chart(
        style_chart(fig, 420),
        use_container_width=True,
    )


# ============================================================
# 2. INVENTORY EXPLORER
# ============================================================

elif page == "Inventory Explorer":

    st.subheader(
        "Product Inventory Explorer"
    )

    product_summary = (
        latest.groupby(
            "product_id",
            as_index=False
        )
        .agg(
            Closing_Stock=("closing_quantity", "sum"),
            Opening_Stock=("opening_quantity", "sum"),
            Receipts=("receipts_quantity", "sum"),
            Issues=("issues_quantity", "sum"),
            Locations=("location_id", "nunique"),
            Negative_Positions=("negative_stock_flag", "sum"),
        )
        .sort_values("Closing_Stock")
    )

    fig = px.bar(
        product_summary.nsmallest(
            20,
            "Closing_Stock"
        ),
        x="Closing_Stock",
        y="product_id",
        orientation="h",
        title="20 Products with Lowest Closing Stock",
        color="Closing_Stock",
        color_continuous_scale="Blues",
    )

    st.plotly_chart(
        style_chart(fig, 550),
        use_container_width=True,
    )

    st.markdown(
        "### Product-Level Inventory Details"
    )

    st.dataframe(
        product_summary,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 3. WAREHOUSE ANALYSIS
# ============================================================

elif page == "Warehouse Analysis":

    st.subheader(
        "Warehouse Inventory Intelligence"
    )

    warehouse = (
        latest.groupby(
            "location_id",
            as_index=False
        )
        .agg(
            Closing_Stock=("closing_quantity", "sum"),
            Receipts=("receipts_quantity", "sum"),
            Issues=("issues_quantity", "sum"),
            Negative_Positions=("negative_stock_flag", "sum"),
            Products=("product_id", "nunique"),
        )
    )

    c1, c2 = st.columns(2)

    with c1:

        fig = px.bar(
            warehouse,
            x="location_id",
            y="Closing_Stock",
            title="Latest Closing Stock by Location",
            color="Closing_Stock",
            color_continuous_scale="Blues",
        )

        st.plotly_chart(
            style_chart(fig),
            use_container_width=True,
        )

    with c2:

        fig = px.bar(
            warehouse,
            x="location_id",
            y="Negative_Positions",
            title="Negative Stock Positions by Location",
            color="Negative_Positions",
            color_continuous_scale="Reds",
        )

        st.plotly_chart(
            style_chart(fig),
            use_container_width=True,
        )

    st.dataframe(
        warehouse,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 4. MOVEMENT INTELLIGENCE
# ============================================================

elif page == "Movement Intelligence":

    st.subheader(
        "Inventory Movement Intelligence"
    )

    if filtered_movements.empty:

        st.info(
            "No movements match the selected filters."
        )

    else:

        movement_summary = (
            filtered_movements.groupby(
                "movement_type",
                as_index=False
            )
            .agg(
                Movement_Count=("movement_id", "count"),
                Total_Quantity=(
                    "quantity",
                    lambda values: values.abs().sum(),
                ),
            )
            .sort_values(
                "Movement_Count",
                ascending=False
            )
        )

        c1, c2 = st.columns(2)

        with c1:

            fig = px.pie(
                movement_summary,
                names="movement_type",
                values="Movement_Count",
                hole=0.58,
                title="Movement Records by Type",
            )

            st.plotly_chart(
                style_chart(fig),
                use_container_width=True,
            )

        with c2:

            fig = px.bar(
                movement_summary,
                x="movement_type",
                y="Total_Quantity",
                color="movement_type",
                title="Absolute Movement Quantity by Type",
            )

            st.plotly_chart(
                style_chart(fig),
                use_container_width=True,
            )

        st.markdown(
            "### Movement Summary"
        )

        st.dataframe(
            movement_summary,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 5. ALERTS CENTER
# ============================================================

elif page == "Alerts Center":

    st.subheader(
        "Inventory Risk & Alerts"
    )

    if negative_positions.empty:

        st.success(
            "No negative inventory positions in "
            "the latest selected snapshot."
        )

    else:

        st.error(
            f"{negative_position_count:,} negative product-location "
            f"positions across {affected_products:,} products and "
            f"{affected_locations:,} locations."
        )

        negative_positions = negative_positions.sort_values(
            "closing_quantity"
        )

        st.dataframe(
            negative_positions[
                [
                    "product_id",
                    "location_id",
                    "business_date",
                    "opening_quantity",
                    "closing_quantity",
                    "negative_stock_flag",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download Negative Stock Report",
            data=negative_positions.to_csv(
                index=False
            ).encode("utf-8"),
            file_name="negative_inventory_alerts.csv",
            mime="text/csv",
        )


# ============================================================
# 6. DATA QUALITY CENTER
# ============================================================

elif page == "Data Quality Center":

    st.subheader(
        "Data Quality & Processing Volumes"
    )

    st.caption(
        "Counts are current table row counts, not per-run counts."
    )

    metric_defs = [
        ("Raw Events", "raw_inventory_events"),
        ("Validated Events", "inventory_events"),
        ("Rejected Records", "rejected_records"),
        ("Generated Movements", "inventory_movements"),
        ("Daily Balance Rows", "daily_inventory_balances"),
    ]

    cols = st.columns(5)

    for col, (label, key) in zip(cols, metric_defs):

        value = table_counts.get(key)

        col.metric(
            label,
            "Unavailable" if value is None else f"{value:,}"
        )

    raw_count = table_counts.get(
        "raw_inventory_events"
    )

    valid_count = table_counts.get(
        "inventory_events"
    )

    rejected_count = table_counts.get(
        "rejected_records"
    )

    st.divider()

    st.markdown(
        "### Validation Volume"
    )

    if raw_count is not None and valid_count is not None:

        accepted_rate = (
            valid_count / raw_count * 100
            if raw_count
            else 0
        )

        a, b = st.columns(2)

        a.metric(
            "Validated / Raw",
            f"{accepted_rate:.2f}%"
        )

        if rejected_count is not None:

            rejected_rate = (
                rejected_count / raw_count * 100
                if raw_count
                else 0
            )

            b.metric(
                "Rejected / Raw",
                f"{rejected_rate:.2f}%"
            )

        else:

            b.metric(
                "Rejected / Raw",
                "Unavailable"
            )

        if (
            rejected_count is not None
            and valid_count + rejected_count != raw_count
        ):

            st.info(
                "These tables do not form a simple one-to-one partition. "
                "They may retain different processing histories."
            )

    else:

        st.info(
            "Raw and validated event counts are not both available."
        )

        # ============================================================
# 7. PIPELINE MONITORING
# ============================================================

elif page == "Pipeline Monitoring":

    st.subheader(
        "Pipeline Observability"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Total Runs",
        f"{run_info['total_runs']:,}"
    )

    c2.metric(
        "Successful Runs",
        "Unavailable"
        if run_info["successful_runs"] is None
        else f"{run_info['successful_runs']:,}"
    )

    c3.metric(
        "Failed Runs",
        "Unavailable"
        if run_info["failed_runs"] is None
        else f"{run_info['failed_runs']:,}"
    )

    st.divider()

    st.markdown(
        "### Current Pipeline Table Counts"
    )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Pipeline Stage": "Raw events",
                    "Rows": table_counts.get(
                        "raw_inventory_events"
                    ),
                },
                {
                    "Pipeline Stage": "Validated events",
                    "Rows": table_counts.get(
                        "inventory_events"
                    ),
                },
                {
                    "Pipeline Stage": "Rejected records",
                    "Rows": table_counts.get(
                        "rejected_records"
                    ),
                },
                {
                    "Pipeline Stage": "Inventory movements",
                    "Rows": table_counts.get(
                        "inventory_movements"
                    ),
                },
                {
                    "Pipeline Stage": "Daily balances",
                    "Rows": table_counts.get(
                        "daily_inventory_balances"
                    ),
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Run duration, per-run row counts and latest-run timestamps "
        "are not displayed because those column definitions "
        "have not yet been verified."
    )


# ============================================================
# 8. RECONCILIATION CENTER
# ============================================================

elif page == "Reconciliation Center":

    st.subheader(
        "Movement-to-Balance Reconciliation"
    )

    st.caption(
        "Compares inventory_movements with daily_inventory_balances "
        "for the selected date, product and location filters. "
        "Receipt, issue and transfer legs use absolute movement quantities."
    )

    categories = {
        "RECEIPT": (
            "receipts_quantity",
            "Receipts",
        ),
        "ISSUE": (
            "issues_quantity",
            "Issues",
        ),
        "TRANSFER_IN": (
            "transfer_in_quantity",
            "Transfer In",
        ),
        "TRANSFER_OUT": (
            "transfer_out_quantity",
            "Transfer Out",
        ),
    }

    rows = []

    for movement_type, (balance_col, label) in categories.items():

        movement_value = 0.0

        if not filtered_movements.empty:

            type_mask = (
                filtered_movements.movement_type
                .astype(str)
                .str.upper()
                == movement_type
            )

            movement_value = float(
                filtered_movements.loc[
                    type_mask,
                    "quantity"
                ].abs().sum()
            )

        balance_value = float(
            filtered[balance_col].sum()
        )

        difference = (
            movement_value - balance_value
        )

        rows.append(
            {
                "Category": label,
                "Movement Table": movement_value,
                "Daily Balance Table": balance_value,
                "Difference": difference,
                "Status": (
                    "MATCH"
                    if abs(difference) < 0.001
                    else "CHECK"
                ),
            }
        )

    reconciliation = pd.DataFrame(rows)

    st.dataframe(
        reconciliation,
        use_container_width=True,
        hide_index=True,
    )

    if (
        reconciliation.Status == "MATCH"
    ).all():

        st.success(
            "All displayed categories match for the selected scope."
        )

    else:

        st.warning(
            "One or more categories differ. Check filter scope and "
            "transformation semantics before treating this as a data defect."
        )

    st.divider()

    st.markdown(
        "### Transfer Leg Check"
    )

    transfer_in = float(
        filtered.transfer_in_quantity.sum()
    )

    transfer_out = float(
        filtered.transfer_out_quantity.sum()
    )

    transfer_difference = (
        transfer_in - transfer_out
    )

    a, b, c = st.columns(3)

    a.metric(
        "Transfer In",
        f"{transfer_in:,.0f}"
    )

    b.metric(
        "Transfer Out",
        f"{transfer_out:,.0f}"
    )

    c.metric(
        "In / Out Difference",
        f"{transfer_difference:,.0f}"
    )

    if abs(transfer_difference) < 0.001:

        st.success(
            "Transfer-in and transfer-out quantities balance."
        )

    else:

        st.warning(
            "Transfer-in and transfer-out totals differ "
            "for this filter scope."
        )


# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "INVENTORY RECONCILIATION PIPELINE"
)

st.sidebar.caption(
    "Python • DuckDB • SQL • Streamlit • Plotly"
)

st.caption(
    "Inventory Control Tower | "
    "Data sourced from the project DuckDB database"
)