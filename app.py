import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import timedelta

# =========================================================
# PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Smart Water Quality Monitoring",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# CUSTOM CSS
# =========================================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }
    .main-heading {
        font-size: 2rem;
        font-weight: 750;
        margin-bottom: 0;
    }
    .sub-heading {
        color: #808080;
        margin-top: 0.2rem;
        margin-bottom: 1rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(120, 120, 120, 0.07);
        border: 1px solid rgba(120, 120, 120, 0.18);
        padding: 13px 15px;
        border-radius: 12px;
    }
    div[data-testid="stMetricLabel"] p {
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# REFERENCE VALUES USED FOR PROJECT SCREENING
# =========================================================
PH_MIN = 6.5
PH_MAX = 8.5
TDS_MAX = 500.0
TURBIDITY_MAX = 1.0


# =========================================================
# SUPABASE CONNECTION
# =========================================================
@st.cache_resource
def get_supabase_client():
    """Connect to Supabase using Streamlit Cloud Secrets."""
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL or secret key is empty.")

        return create_client(supabase_url, supabase_key)

    except KeyError as error:
        st.error(
            f"Missing Streamlit secret: {error}. "
            "Open Manage app → Settings → Secrets and add both Supabase values."
        )
        st.stop()
    except Exception as error:
        st.error(f"Could not connect to Supabase: {error}")
        st.stop()


@st.cache_data(ttl=30, show_spinner=False)
def fetch_sensor_data(_client):
    """
    Retrieve up to 5,000 latest records.
    Data is cached for 30 seconds. Refresh Now clears this cache immediately.
    """
    response = (
        _client.table("sensor_readings")
        .select("id, device_id, ph, tds, turbidity, temperature, received_at")
        .order("received_at", desc=True)
        .limit(5000)
        .execute()
    )

    records = response.data or []
    df = pd.DataFrame(records)

    if df.empty:
        return df

    for column in ["ph", "tds", "turbidity", "temperature"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["received_at"] = pd.to_datetime(
        df["received_at"], errors="coerce", utc=True
    )
    df = df.dropna(subset=["received_at"])
    return df.sort_values("received_at").reset_index(drop=True)


# =========================================================
# REFERENCE SCREENING
# =========================================================
def reference_check(row):
    issues = []

    if pd.isna(row["ph"]) or not PH_MIN <= row["ph"] <= PH_MAX:
        issues.append("pH outside 6.5–8.5")

    if pd.isna(row["tds"]) or row["tds"] > TDS_MAX:
        issues.append("TDS above 500 ppm")

    if pd.isna(row["turbidity"]) or row["turbidity"] > TURBIDITY_MAX:
        issues.append("Turbidity above 1 NTU")

    if issues:
        return "Outside reference limits", "; ".join(issues)

    return (
        "Within reference limits",
        "All three measured parameters are within the selected project reference limits"
    )


# =========================================================
# HEADER + MANUAL REFRESH
# =========================================================
header_left, header_right = st.columns([5, 1])

with header_left:
    st.markdown(
        '<div class="main-heading">💧 Smart Water Quality Monitoring</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sub-heading">ESP32 • Wokwi • MQTT • Supabase • Streamlit</div>',
        unsafe_allow_html=True
    )

with header_right:
    st.write("")
    if st.button("🔄 Refresh Now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.caption(
    "Manual refresh is enabled. Sensor data continues to be collected in Supabase "
    "while the dashboard is open."
)

# =========================================================
# LOAD DATA
# =========================================================
supabase = get_supabase_client()

try:
    with st.spinner("Loading sensor readings..."):
        data = fetch_sensor_data(supabase)
except Exception as error:
    st.error("Unable to retrieve data from the Supabase sensor_readings table.")
    st.code(str(error))
    st.info(
        "Check your Streamlit Secrets and confirm that the table contains "
        "id, device_id, ph, tds, turbidity, temperature and received_at."
    )
    st.stop()

if data.empty:
    st.warning("No sensor readings are available yet.")
    st.info(
        "Start the Wokwi simulation and keep mqtt_receiver.py running. "
        "After data is inserted into Supabase, click Refresh Now."
    )
    st.stop()

# Add screening results to every fetched row
screening = data.apply(reference_check, axis=1, result_type="expand")
screening.columns = ["Reference_Status", "Reference_Notes"]
data = pd.concat([data, screening], axis=1)

# =========================================================
# SIDEBAR FILTERS
# =========================================================
st.sidebar.title("Dashboard Filters")

device_list = (
    sorted(data["device_id"].dropna().astype(str).unique().tolist())
    if "device_id" in data.columns else []
)
device_options = ["All devices"] + device_list
selected_device = st.sidebar.selectbox("Select device", device_options)

min_date = data["received_at"].min().date()
max_date = data["received_at"].max().date()
default_start = max(min_date, max_date - timedelta(days=7))

selected_dates = st.sidebar.date_input(
    "Select date range",
    value=(default_start, max_date),
    min_value=min_date,
    max_value=max_date
)

filtered = data.copy()

if selected_device != "All devices" and "device_id" in filtered.columns:
    filtered = filtered[
        filtered["device_id"].astype(str) == selected_device
    ]

if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
    filtered = filtered[
        (filtered["received_at"].dt.date >= start_date)
        & (filtered["received_at"].dt.date <= end_date)
    ]

if filtered.empty:
    st.warning("No readings match the selected device and date range.")
    st.stop()

latest = filtered.iloc[-1]
latest_time_ist = latest["received_at"].tz_convert("Asia/Kolkata")
chart_data = filtered.copy()
chart_data["Time (IST)"] = chart_data["received_at"].dt.tz_convert("Asia/Kolkata")

# =========================================================
# TOP-LEVEL TABS
# =========================================================
overview_tab, analytics_tab, checks_tab, history_tab, download_tab = st.tabs(
    [
        "🏠 Overview",
        "📈 Sensor Analytics",
        "🧪 Reference Checks",
        "📋 Reading History",
        "⬇️ Download Data"
    ]
)

# =========================================================
# TAB 1: OVERVIEW
# =========================================================
with overview_tab:
    st.subheader("Latest Sensor Readings")
    st.caption(
        "Latest reading in the selected filters: "
        + latest_time_ist.strftime("%d %b %Y, %I:%M:%S %p IST")
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "pH",
        f"{latest['ph']:.2f}" if pd.notna(latest["ph"]) else "N/A"
    )
    metric2.metric(
        "TDS",
        f"{latest['tds']:.1f} ppm" if pd.notna(latest["tds"]) else "N/A"
    )
    metric3.metric(
        "Turbidity",
        f"{latest['turbidity']:.2f} NTU"
        if pd.notna(latest["turbidity"]) else "N/A"
    )
    metric4.metric(
        "Temperature",
        f"{latest['temperature']:.1f} °C"
        if pd.notna(latest["temperature"]) else "N/A"
    )

    st.divider()
    st.subheader("Monitoring Summary")

    total_count = len(filtered)
    within_count = int(
        (filtered["Reference_Status"] == "Within reference limits").sum()
    )
    outside_count = total_count - within_count

    summary1, summary2, summary3 = st.columns(3)
    summary1.metric("Total readings", f"{total_count:,}")
    summary2.metric("Within reference limits", f"{within_count:,}")
    summary3.metric("Outside reference limits", f"{outside_count:,}")

    st.divider()
    st.subheader("Latest Reference Screening")

    if latest["Reference_Status"] == "Within reference limits":
        st.success("Latest reading: Within the selected reference limits")
    else:
        st.error("Latest reading: Outside the selected reference limits")
        st.write("**Reason:** " + latest["Reference_Notes"])

    st.caption(
        "Screening uses the project's selected reference values. It does not "
        "certify that water is safe to drink."
    )

    st.divider()
    st.subheader("Recent Sensor Readings")

    recent = filtered.sort_values("received_at", ascending=False).head(10).copy()
    recent["received_at"] = recent["received_at"].dt.strftime(
        "%d-%m-%Y %I:%M:%S %p UTC"
    )
    st.dataframe(
        recent[
            [
                col for col in [
                    "device_id", "ph", "tds", "turbidity",
                    "temperature", "Reference_Status", "received_at"
                ] if col in recent.columns
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# TAB 2: SENSOR ANALYTICS
# =========================================================
with analytics_tab:
    st.subheader("Sensor Trend Analysis")
    st.caption("Explore how each sensor parameter changes over time.")

    graph_left, graph_right = st.columns(2)

    with graph_left:
        ph_fig = px.line(
            chart_data,
            x="Time (IST)",
            y="ph",
            title="pH Variation",
            markers=True
        )
        ph_fig.add_hline(
            y=PH_MIN, line_dash="dash",
            annotation_text="Lower reference: 6.5"
        )
        ph_fig.add_hline(
            y=PH_MAX, line_dash="dash",
            annotation_text="Upper reference: 8.5"
        )
        ph_fig.update_layout(
            xaxis_title="Time (IST)", yaxis_title="pH"
        )
        st.plotly_chart(ph_fig, use_container_width=True)

    with graph_right:
        tds_fig = px.line(
            chart_data,
            x="Time (IST)",
            y="tds",
            title="TDS Variation",
            markers=True
        )
        tds_fig.add_hline(
            y=TDS_MAX, line_dash="dash",
            annotation_text="Reference: 500 ppm"
        )
        tds_fig.update_layout(
            xaxis_title="Time (IST)", yaxis_title="TDS (ppm)"
        )
        st.plotly_chart(tds_fig, use_container_width=True)

    graph_left2, graph_right2 = st.columns(2)

    with graph_left2:
        turbidity_fig = px.line(
            chart_data,
            x="Time (IST)",
            y="turbidity",
            title="Turbidity Variation",
            markers=True
        )
        turbidity_fig.add_hline(
            y=TURBIDITY_MAX, line_dash="dash",
            annotation_text="Reference: 1 NTU"
        )
        turbidity_fig.update_layout(
            xaxis_title="Time (IST)", yaxis_title="Turbidity (NTU)"
        )
        st.plotly_chart(turbidity_fig, use_container_width=True)

    with graph_right2:
        temperature_fig = px.line(
            chart_data,
            x="Time (IST)",
            y="temperature",
            title="Temperature Variation",
            markers=True
        )
        temperature_fig.update_layout(
            xaxis_title="Time (IST)", yaxis_title="Temperature (°C)"
        )
        st.plotly_chart(temperature_fig, use_container_width=True)

    st.divider()
    st.subheader("Reference Screening Distribution")

    status_counts = (
        filtered["Reference_Status"]
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Number of readings")
    )

    distribution_left, distribution_right = st.columns([1, 1])

    with distribution_left:
        status_fig = px.pie(
            status_counts,
            names="Status",
            values="Number of readings",
            title="Within / Outside Reference Limits",
            hole=0.42
        )
        st.plotly_chart(status_fig, use_container_width=True)

    with distribution_right:
        st.write("**Screening counts**")
        st.dataframe(status_counts, use_container_width=True, hide_index=True)
        st.caption(
            "This distribution is based on the selected reference checks, "
            "not a laboratory determination of water potability."
        )


# =========================================================
# TAB 3: REFERENCE CHECKS
# =========================================================
with checks_tab:
    st.subheader("Drinking-Water Reference Checks")
    st.warning(
        "These are indicative project screening values only. They do not "
        "replace laboratory testing or official drinking-water certification."
    )

    st.markdown("#### Reference values used")
    ref1, ref2, ref3 = st.columns(3)
    ref1.metric("pH range", "6.5 – 8.5")
    ref2.metric("TDS maximum", "500 ppm")
    ref3.metric("Turbidity maximum", "1 NTU")

    st.divider()
    st.markdown("#### Latest reading check")

    checks_to_show = [
        ("pH", latest["ph"], PH_MIN, PH_MAX, "6.5–8.5"),
        ("TDS", latest["tds"], None, TDS_MAX, "≤500 ppm"),
        ("Turbidity", latest["turbidity"], None, TURBIDITY_MAX, "≤1 NTU"),
    ]

    check_col1, check_col2, check_col3 = st.columns(3)

    for container, (label, value, lower, upper, limit_text) in zip(
        [check_col1, check_col2, check_col3], checks_to_show
    ):
        with container:
            st.markdown(f"**{label}**")
            if pd.isna(value):
                st.warning(f"No valid reading\n\nReference: {limit_text}")
            else:
                passed = (
                    (value >= lower if lower is not None else True)
                    and value <= upper
                )
                if passed:
                    st.success(f"{value:.2f}\n\nWithin reference: {limit_text}")
                else:
                    st.error(f"{value:.2f}\n\nOutside reference: {limit_text}")

    st.divider()
    st.markdown("#### Screening status for all selected readings")

    status_table = filtered[
        [
            col for col in [
                "received_at", "ph", "tds", "turbidity",
                "Reference_Status", "Reference_Notes"
            ] if col in filtered.columns
        ]
    ].sort_values("received_at", ascending=False).copy()

    status_table["received_at"] = status_table["received_at"].dt.strftime(
        "%d-%m-%Y %I:%M:%S %p UTC"
    )
    st.dataframe(status_table, use_container_width=True, hide_index=True)


# =========================================================
# TAB 4: READING HISTORY
# =========================================================
with history_tab:
    st.subheader("Sensor Reading History")
    st.caption("Use the device and date filters in the left sidebar to narrow the history.")

    history_search = st.text_input(
        "Search screening status or device ID",
        placeholder="Example: Within reference limits or ESP32-001"
    )

    history = filtered.sort_values("received_at", ascending=False).copy()

    if history_search.strip():
        search_text = history_search.strip().lower()
        searchable = (
            history["Reference_Status"].astype(str).str.lower().str.contains(
                search_text, na=False
            )
            | history["device_id"].astype(str).str.lower().str.contains(
                search_text, na=False
            )
        )
        history = history[searchable]

    history["received_at"] = history["received_at"].dt.strftime(
        "%d-%m-%Y %I:%M:%S %p UTC"
    )

    history_columns = [
        col for col in [
            "id", "device_id", "ph", "tds", "turbidity",
            "temperature", "Reference_Status", "Reference_Notes", "received_at"
        ] if col in history.columns
    ]

    st.write(f"**Records displayed: {len(history):,}**")
    st.dataframe(
        history[history_columns],
        use_container_width=True,
        hide_index=True,
        height=500
    )


# =========================================================
# TAB 5: DOWNLOAD DATA
# =========================================================
with download_tab:
    st.subheader("Download Sensor Data")
    st.write(
        "Download the readings matching the device and date filters "
        "currently selected in the sidebar."
    )

    export_data = filtered.copy()
    export_data["received_at"] = export_data["received_at"].dt.strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    csv_bytes = export_data.to_csv(index=False).encode("utf-8")

    st.metric("Records available for download", f"{len(export_data):,}")

    st.download_button(
        label="⬇️ Download selected readings as CSV",
        data=csv_bytes,
        file_name="smart_water_sensor_readings.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.caption(
        "The CSV contains the sensor readings and the reference-screening "
        "status calculated by this dashboard."
    )


# =========================================================
# FOOTER
# =========================================================
st.divider()
st.caption(
    "Smart Water Quality Monitoring System | ESP32 + Wokwi + MQTT + Supabase + Streamlit"
)
st.caption(
    "Water quality screening is indicative only. Actual drinking-water safety "
    "requires appropriate laboratory testing."
)

