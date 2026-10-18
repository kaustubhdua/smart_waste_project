import os
import folium
import joblib
import pandas as pd
import streamlit as st
from streamlit_folium import folium_static

from person1_preprocessing import preprocess_data, generate_synthetic_bin_data
from person2_ml_prediction import train_ml_model, load_ml_model, predict_next_fill
from person3_fuzzy_logic import calculate_priority, create_fuzzy_system
from person4_optimization import solve_vrp

st.set_page_config(page_title="Smart Waste Collection Dashboard", page_icon="🗑️", layout="wide")
st.title("🗑️ Smart Waste Collection & Route Optimization System")
st.markdown("AI-assisted waste monitoring, priority scoring, and collection planning")

@st.cache_resource
def load_resources():
    return create_fuzzy_system(), load_ml_model()

fuzzy_sim, ml_model = load_resources()
csv_path = "cleaned_waste_data.csv"
if not os.path.exists(csv_path):
    st.info("Creating a clearly labeled synthetic demo dataset for first-time setup.")
    preprocess_data(generate_synthetic_bin_data()).to_csv(csv_path, index=False)

df = pd.read_csv(csv_path)
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp"]).sort_values(["bin_id", "timestamp"])
latest_df = df.groupby("bin_id", sort=False).tail(1).copy().reset_index(drop=True)

if ml_model is None:
    st.warning("No trained model artifact found. Predictions are disabled until you train a model.")
    if st.button("Train model on current dataset"):
        with st.spinner("Training and evaluating the model on a chronological holdout..."):
            train_ml_model(csv_path)
        load_resources.clear()
        st.success("Model artifact created. Reloading dashboard.")
        st.rerun()
else:
    try:
        latest_df["predicted_fill_pct"] = predict_next_fill(ml_model, latest_df).round(1)
    except (ValueError, KeyError) as exc:
        latest_df["predicted_fill_pct"] = latest_df["fill_level_pct"]
        st.error(f"Model prediction unavailable for current rows: {exc}")
    else:
        st.caption("Predicted fill is a one-observation-ahead estimate; it is not a calibrated 6/12-hour forecast.")

# The CSV does not contain verified collection events, so do not fabricate elapsed
# service time. Time contribution is zero until service history is available.
latest_df["priority_score"] = latest_df.apply(
    lambda row: calculate_priority(row["predicted_fill_pct"] if "predicted_fill_pct" in latest_df else row["fill_level_pct"], 0, row["criticality"], fuzzy_sim),
    axis=1,
)
st.info("Dataset mode: synthetic/imported CSV. Service history is not present in this dataset, so elapsed-since-empty contribution is disabled.")

st.sidebar.header("Collection Controls")
min_priority = st.sidebar.slider("Minimum Priority Score for Pickup", 0, 100, 50)
num_trucks = st.sidebar.number_input("Number of Collection Trucks", min_value=1, max_value=5, value=2)
truck_capacity = st.sidebar.slider("Truck Capacity (Liters)", 500, 3000, 1000)

pickup_df = latest_df[latest_df["priority_score"] >= min_priority].copy()
pickup_df["waste_volume"] = (pickup_df["capacity_liters"] * pickup_df["fill_level_pct"] / 100).round().astype(int)
pickup_bins = pickup_df.to_dict("records")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Bins Monitored", len(latest_df))
col2.metric("Bins Requiring Pickup", len(pickup_bins))
col3.metric("Average Fill", f"{latest_df['fill_level_pct'].mean():.1f}%")
col4.metric("High Priority Bins", len(latest_df[latest_df["priority_score"] > 70]))
st.divider()
col_left, col_right = st.columns([2, 1])
with col_left:
    st.subheader("Bin Locations & Priority Map")
    depot_lat, depot_lon = 28.5355, 77.3910
    map_view = folium.Map(location=[depot_lat, depot_lon], zoom_start=12)
    folium.Marker([depot_lat, depot_lon], popup="Demo depot", icon=folium.Icon(color="black", icon="home")).add_to(map_view)
    for _, row in latest_df.iterrows():
        score = row["priority_score"]
        color = "red" if score >= 70 else "orange" if score >= 40 else "green"
        fill_display = row.get("predicted_fill_pct", row["fill_level_pct"])
        folium.CircleMarker(
            [row["latitude"], row["longitude"]], radius=8, color=color, fill=True,
            fill_color=color, fill_opacity=0.7,
            popup=f"Bin: {row['bin_id']} | Observed: {row['fill_level_pct']}% | Next observation estimate: {fill_display}% | Priority: {score}",
        ).add_to(map_view)
    folium_static(map_view, width=700, height=450)

with col_right:
    st.subheader("Demo route planning")
    st.warning("This legacy Streamlit route solver still uses approximate coordinate costs. Use the backend API /api/v1/routes/optimize for road-network optimization.")
    if st.button("Generate demo routes", type="primary"):
        if not pickup_bins:
            st.info("No bins meet the selected priority threshold.")
        else:
            routes = solve_vrp(pickup_bins, num_vehicles=num_trucks, vehicle_capacity=truck_capacity)
            for vehicle, details in routes.items():
                names = [pickup_bins[i]["bin_id"] for i in details["route_bin_indices"]]
                st.markdown(f"### {vehicle}")
                st.write(f"Route: {' → '.join(['Depot'] + names + ['Depot'])}")
                st.write(f"Estimated demand: {details['total_load']} L")
                st.progress(min(details["total_load"] / truck_capacity, 1.0))

with st.expander("Detailed bin status"):
    columns = ["bin_id", "fill_level_pct", "criticality", "priority_score", "capacity_liters"]
    if "predicted_fill_pct" in latest_df:
        columns.insert(2, "predicted_fill_pct")
    st.dataframe(latest_df[columns].sort_values("priority_score", ascending=False), use_container_width=True)
