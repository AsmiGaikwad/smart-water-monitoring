
import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from datetime import datetime

# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="Smart Water Monitoring",
    page_icon="💧",
    layout="wide"
)

# ---------------- CUSTOM STYLE ----------------

st.markdown("""
<style>
.main {
    background-color: #f5f8fc;
}
.block-container {
    padding-top: 1.5rem;
}
[data-testid="stMetric"] {
    background-color: white;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #e5eaf0;
}
</style>
""", unsafe_allow_html=True)

# ---------------- DATABASE CONNECTION ----------------

@st.cache_resource
def get_database():

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    )

# ---------------- FETCH SENSOR DATA ----------------

@st.cache_data(ttl=5)
def fetch_data():

    db = get_database()

    response = (
        db.table("sensor_readings")
        .select("*")
        .order("received_at", desc=True)
        .limit(100)
        .execute()
    )

    df = pd.DataFrame(response.data)

    if not df.empty:
        df["received_at"] = pd.to_datetime(
            df["received_at"],
            errors="coerce",
            utc=True
        )

        for col in [
            "ph", "tds", "turbidity", "temperature"
        ]:
            df[col] = pd.to_numeric(
                df[col], errors="coerce"
            )

        df = df.dropna(
            subset=[
                "received_at",
                "ph",
                "tds",
                "turbidity",
                "temperature"
            ]
        )

        df = df.sort_values("received_at")

    return df


# ---------------- REFERENCE LIMITS ----------------

PH_MIN = 6.5
PH_MAX = 8.5
TDS_MAX = 500
TURBIDITY_MAX = 1.0


def check_water(ph, tds, turbidity):

    problems = []

    if not PH_MIN <= ph <= PH_MAX:
        problems.append("pH outside 6.5–8.5")

    if tds > TDS_MAX:
        problems.append("TDS above 500 ppm")

    if turbidity > TURBIDITY_MAX:
        problems.append("Turbidity above 1 NTU")

    if problems:
        return "Unsafe", problems

    return "Within reference limits", []


# ---------------- HEADER ----------------

st.title("💧 Smart Water Quality Monitoring")
st.caption(
    "IoT-based water monitoring using ESP32, "
    "Wokwi, MQTT and Supabase"
)

# ---------------- SIDEBAR ----------------

st.sidebar.title("Dashboard Controls")

auto_refresh = st.sidebar.checkbox(
    "Auto refresh every 5 seconds",
    value=True
)

if st.sidebar.button("🔄 Refresh Now"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()

st.sidebar.markdown("### Reference Limits")
st.sidebar.write("pH: 6.5 – 8.5")
st.sidebar.write("TDS: ≤ 500 ppm")
st.sidebar.write("Turbidity: ≤ 1 NTU")

# ---------------- AUTO REFRESH ----------------

if auto_refresh:
    st.components.v1.html(
        """
        <script>
        setTimeout(function() {
            window.parent.location.reload();
        }, 5000);
        </script>
        """,
        height=0
    )

# ---------------- LOAD DATA ----------------

try:
    df = fetch_data()

except Exception as error:

    st.error("Unable to retrieve data from Supabase.")
    st.code(str(error))
    st.stop()


if df.empty:

    st.warning(
        "No sensor readings found. "
        "Start your Wokwi simulation and MQTT receiver."
    )

    st.info(
        "Once readings arrive, they will appear here automatically."
    )

    st.stop()


# ---------------- LATEST READING ----------------

latest = df.iloc[-1]

ph = float(latest["ph"])
tds = float(latest["tds"])
turbidity = float(latest["turbidity"])
temperature = float(latest["temperature"])

status, problems = check_water(
    ph, tds, turbidity
)

# ---------------- CONNECTION STATUS ----------------

st.caption(
    "Latest database reading: "
    + latest["received_at"].strftime(
        "%d %b %Y, %I:%M:%S %p UTC"
    )
)

# ---------------- SENSOR CARDS ----------------

st.subheader("Live Sensor Monitoring")

c1, c2, c3, c4 = st.columns(4)

c1.metric("pH Level", f"{ph:.2f}", "pH")
c2.metric("TDS", f"{tds:.2f}", "ppm")
c3.metric("Turbidity", f"{turbidity:.2f}", "NTU")
c4.metric("Temperature", f"{temperature:.2f}", "°C")

st.divider()

# ---------------- WATER STATUS ----------------

st.subheader("Water Quality Reference Screening")

if problems:

    st.error("⚠️ OUTSIDE REFERENCE LIMITS")

    for problem in problems:
        st.write("•", problem)

else:

    st.success("✓ ALL CHECKED PARAMETERS WITHIN REFERENCE LIMITS")

st.caption(
    "This is a screening result based on selected reference "
    "limits, not a certification of drinking-water safety."
)

# ---------------- PARAMETER CHECKS ----------------

st.subheader("Individual Parameter Checks")

p1, p2, p3 = st.columns(3)

p1.write("**pH**")
p1.write(
    "Within limits"
    if PH_MIN <= ph <= PH_MAX
    else "Outside limits"
)

p2.write("**TDS**")
p2.write(
    "Within limits"
    if tds <= TDS_MAX
    else "Above limit"
)

p3.write("**Turbidity**")
p3.write(
    "Within limits"
    if turbidity <= TURBIDITY_MAX
    else "Above limit"
)

st.divider()

# ---------------- HISTORICAL GRAPHS ----------------

st.subheader("Sensor Trends")

tab1, tab2, tab3, tab4 = st.tabs([
    "pH",
    "TDS",
    "Turbidity",
    "Temperature"
])

with tab1:

    fig = px.line(
        df,
        x="received_at",
        y="ph",
        title="pH Level Over Time",
        markers=True
    )

    fig.add_hrect(
        y0=PH_MIN,
        y1=PH_MAX,
        opacity=0.12,
        line_width=0
    )

    st.plotly_chart(fig, use_container_width=True)

with tab2:

    fig = px.line(
        df,
        x="received_at",
        y="tds",
        title="TDS Over Time",
        markers=True
    )

    fig.add_hline(
        y=TDS_MAX,
        line_dash="dash",
        annotation_text="500 ppm reference"
    )

    st.plotly_chart(fig, use_container_width=True)

with tab3:

    fig = px.line(
        df,
        x="received_at",
        y="turbidity",
        title="Turbidity Over Time",
        markers=True
    )

    fig.add_hline(
        y=TURBIDITY_MAX,
        line_dash="dash",
        annotation_text="1 NTU reference"
    )

    st.plotly_chart(fig, use_container_width=True)

with tab4:

    fig = px.line(
        df,
        x="received_at",
        y="temperature",
        title="Temperature Over Time",
        markers=True
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------------- DATABASE HISTORY ----------------

st.divider()

st.subheader("Sensor Reading History")

display_df = df.sort_values(
    "received_at", ascending=False
).copy()

display_df["water_status"] = display_df.apply(
    lambda row: check_water(
        row["ph"],
        row["tds"],
        row["turbidity"]
    )[0],
    axis=1
)

display_df = display_df.rename(columns={
    "id": "ID",
    "device_id": "Device",
    "ph": "pH",
    "tds": "TDS (ppm)",
    "turbidity": "Turbidity (NTU)",
    "temperature": "Temperature (°C)",
    "received_at": "Timestamp",
    "water_status": "Reference Status"
})

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)

# ---------------- DOWNLOAD REPORT ----------------

csv_data = display_df.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    label="📥 Download Sensor History CSV",
    data=csv_data,
    file_name="water_sensor_history.csv",
    mime="text/csv"
)

# ---------------- FOOTER ----------------

st.divider()

st.caption(
    "Smart Water Quality Monitoring System | "
    "ESP32 + Wokwi + MQTT + Supabase + Streamlit"
)
