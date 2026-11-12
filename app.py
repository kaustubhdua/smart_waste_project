"""WasteOps — interactive, self-contained collection operations workspace.

The product runs entirely in the Streamlit process. Its operational workspace is
initialized locally and persists for the lifetime of the browser session.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from uuid import uuid4

import json
import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from person4_optimization import solve_vrp

st.set_page_config(
    page_title="WasteOps | Collection Operations",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Design system
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { color-scheme: dark; }
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
      font-family: 'DM Sans', sans-serif;
    }
    .stApp {
      background:
        radial-gradient(ellipse at 10% 0%, rgba(37,105,77,.18), transparent 32%),
        radial-gradient(ellipse at 95% 8%, rgba(39,94,104,.13), transparent 27%),
        #08120f;
      color: #edf5ef;
    }
    [data-testid="stHeader"] { background: rgba(8,18,15,.82); }
    [data-testid="stToolbar"], #MainMenu, footer { visibility:hidden; }
    [data-testid="stSidebar"] {
      background: linear-gradient(180deg,#0d1d17 0%,#0a1712 100%);
      border-right: 1px solid rgba(159,199,173,.12);
    }
    [data-testid="stSidebar"] > div { padding-top: 1.2rem; }
    .block-container { max-width: 1500px; padding: 1.5rem 2rem 3rem; }
    h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.7px; }
    h1 { font-size:2.1rem !important; font-weight:800 !important; }
    h2 { font-size:1.45rem !important; font-weight:750 !important; }
    h3 { font-size:1.05rem !important; font-weight:700 !important; }
    p, label, .stMarkdown { color:#dce9e0; }
    .brand { display:flex; align-items:center; gap:11px; padding:8px 4px 22px; }
    .brand-icon { width:42px;height:42px;border-radius:13px;display:grid;place-items:center;
      color:#082016;background:linear-gradient(145deg,#a8e6c1,#58c89a);font-size:23px;
      box-shadow:0 8px 28px rgba(73,196,141,.16); }
    .brand-name { color:#f2fbf5;font:800 19px 'Manrope',sans-serif;letter-spacing:-.7px; }
    .brand-sub { color:#86a494;font-size:10px;letter-spacing:2px;text-transform:uppercase; }
    .eyebrow { color:#8fe0b2;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase; }
    .muted { color:#91a99a !important; }
    .panel { background:linear-gradient(145deg,rgba(19,42,31,.92),rgba(12,29,22,.94));
      border:1px solid rgba(169,210,185,.13);border-radius:17px;padding:18px 20px;
      box-shadow:0 16px 42px rgba(0,0,0,.12); }
    .metric-label { color:#8fa99a;font-size:11px;font-weight:600;letter-spacing:.7px;text-transform:uppercase; }
    .metric-value { color:#f2faf4;font:800 30px 'Manrope',sans-serif;margin-top:5px; }
    .metric-foot { color:#83d6a5;font-size:11px;margin-top:4px; }
    .pill { display:inline-block;border-radius:99px;padding:4px 9px;font-size:10px;
      font-weight:700;letter-spacing:.4px;background:rgba(143,224,178,.12);color:#9be8bb; }
    .section-head { display:flex;align-items:center;justify-content:space-between;margin:22px 0 12px; }
    .section-head span { color:#8fe0b2;font-size:10px;font-weight:700;letter-spacing:1.7px;text-transform:uppercase; }
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
      border:1px solid rgba(143,224,178,.22);border-radius:10px;background:#8fe0b2;color:#082016;
      font-weight:750;min-height:42px;transition:all .15s ease;
    }
    .stButton > button:hover,.stDownloadButton > button:hover,.stFormSubmitButton > button:hover {
      background:#b0edc9;color:#082016;border-color:#b0edc9;
    }
    .stButton > button[kind="secondary"] { background:#14271e;color:#dce9e0;border:1px solid #2c4939; }
    [data-testid="stMetric"] { background:linear-gradient(145deg,#14281f,#102219);
      border:1px solid rgba(169,210,185,.12);padding:15px 17px;border-radius:15px; }
    [data-testid="stMetricLabel"] { color:#91a99a; }
    [data-testid="stMetricValue"] { color:#f2faf4; }
    [data-testid="stDataFrame"] { border:1px solid rgba(169,210,185,.12);border-radius:12px;overflow:hidden; }
    [data-baseweb="select"] > div, [data-baseweb="input"] > div, textarea {
      background:#102219 !important;border-color:#2c4939 !important;
    }
    hr { border-color:rgba(169,210,185,.12) !important; }
    .stProgress > div > div { background:#79d8a2; }
    [data-testid="stSidebar"] .stRadio label { padding:7px 4px; }
    @media(max-width:760px) {
      .block-container { padding:1rem .85rem 2rem; }
      h1 { font-size:1.65rem !important; }
      .metric-value { font-size:25px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session workspace and local operations data
# ---------------------------------------------------------------------------
DEPOT = (28.5355, 77.3910)
AREAS = ["Sector 18", "Sector 62", "Sector 50", "Sector 76", "Sector 137", "Sector 15", "Sector 44"]
BIN_TYPES = ["General waste", "Recyclables", "Organic waste", "Mixed waste"]


def make_workspace() -> dict:
    rng = np.random.default_rng(42)
    now = datetime.now().replace(second=0, microsecond=0)
    bins = []
    for i in range(1, 31):
        fill = float(rng.integers(18, 99))
        capacity = int(rng.choice([120, 240, 360, 660]))
        bins.append({
            "id": f"BIN-{i:03d}",
            "area": AREAS[(i - 1) % len(AREAS)],
            "type": BIN_TYPES[(i - 1) % len(BIN_TYPES)],
            "latitude": DEPOT[0] + float(rng.uniform(-.027, .027)),
            "longitude": DEPOT[1] + float(rng.uniform(-.032, .032)),
            "capacity_l": capacity,
            "fill_pct": round(fill, 1),
            "temperature_c": round(float(rng.uniform(24, 37)), 1),
            "criticality": ["High", "Medium", "Low"][(i - 1) % 3],
            "last_collected": (now - timedelta(hours=int(rng.integers(5, 70)))).isoformat(timespec="minutes"),
            "status": "Needs collection" if fill >= 80 else ("Attention" if fill >= 65 else "Normal"),
            "battery_pct": int(rng.integers(62, 100)),
        })
    vehicles = [
        {"id":"TRK-01","driver":"Aarav Sharma","type":"Compactor","capacity_l":1200,"available":True,"fuel_pct":82,"zone":"Central"},
        {"id":"TRK-02","driver":"Meera Singh","type":"Tipper","capacity_l":900,"available":True,"fuel_pct":67,"zone":"North"},
        {"id":"TRK-03","driver":"Kabir Verma","type":"Compactor","capacity_l":1500,"available":True,"fuel_pct":91,"zone":"South"},
        {"id":"TRK-04","driver":"Ananya Rao","type":"Mini truck","capacity_l":600,"available":True,"fuel_pct":54,"zone":"East"},
    ]
    jobs = [
        {"id":"JOB-1042","bin_id":"BIN-003","area":"Sector 50","priority":"High","status":"Assigned","vehicle":"TRK-01","created":(now-timedelta(hours=2)).strftime("%d %b, %H:%M")},
        {"id":"JOB-1041","bin_id":"BIN-011","area":"Sector 62","priority":"High","status":"In progress","vehicle":"TRK-02","created":(now-timedelta(hours=1)).strftime("%d %b, %H:%M")},
        {"id":"JOB-1040","bin_id":"BIN-019","area":"Sector 76","priority":"Medium","status":"Completed","vehicle":"TRK-03","created":(now-timedelta(hours=4)).strftime("%d %b, %H:%M")},
        {"id":"JOB-1039","bin_id":"BIN-007","area":"Sector 18","priority":"Medium","status":"Completed","vehicle":"TRK-04","created":(now-timedelta(hours=6)).strftime("%d %b, %H:%M")},
    ]
    history = []
    for hour in range(23, -1, -1):
        ts = now - timedelta(hours=hour)
        history.append({"time":ts.strftime("%H:%M"),"collected":int(rng.integers(90,240)),"requests":int(rng.integers(3,13))})
    return {"bins":bins,"vehicles":vehicles,"jobs":jobs,"history":history,"routes":{},"route_order":[],"events":[],"next_job":1043,"next_bin":31}


if "wasteops" not in st.session_state:
    st.session_state.wasteops = make_workspace()
if "active_page" not in st.session_state:
    st.session_state.active_page = "Overview"

data = st.session_state.wasteops
bins = data["bins"]
vehicles = data["vehicles"]
jobs = data["jobs"]


def priority_score(row: dict) -> float:
    fill = float(row["fill_pct"])
    criticality = {"High": 18, "Medium": 10, "Low": 4}.get(row["criticality"], 4)
    age = max(0.0, (datetime.now() - datetime.fromisoformat(row["last_collected"])).total_seconds() / 3600)
    return round(min(100, fill * .68 + min(age, 48) * .35 + criticality), 1)


def distance_km(a, b) -> float:
    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)
    dlat, dlon = lat2-lat1, lon2-lon1
    value = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(value))


def log_event(message: str):
    data["events"].insert(0, {"time":datetime.now().strftime("%d %b · %H:%M"),"message":message})
    data["events"] = data["events"][:30]


def refresh_bin_status(row: dict):
    row["status"] = "Needs collection" if row["fill_pct"] >= 80 else ("Attention" if row["fill_pct"] >= 65 else "Normal")


def build_map(selected_ids=None, route_lines=None, height=480):
    selected_ids = set(selected_ids or [])
    m = folium.Map(location=DEPOT, zoom_start=12, tiles="CartoDB dark_matter", control_scale=True)
    folium.Marker(DEPOT, tooltip="WasteOps depot", icon=folium.Icon(color="green", icon="home")).add_to(m)
    for row in bins:
        color = "#f05b5b" if row["fill_pct"] >= 80 else ("#f2bd55" if row["fill_pct"] >= 65 else "#55c98b")
        folium.CircleMarker(
            [row["latitude"],row["longitude"]], radius=8 if row["id"] in selected_ids else 6,
            color=color, fill=True, fill_color=color, fill_opacity=.9,
            tooltip=f'{row["id"]} · {row["fill_pct"]:.0f}% full',
            popup=f'<b>{row["id"]}</b><br>{row["area"]}<br>{row["fill_pct"]:.1f}% full<br>{row["capacity_l"]} L',
        ).add_to(m)
    route_colors = ["#73d7a0","#69aee8","#e6b65f","#c28be8"]
    for route_index, (vehicle, ordered) in enumerate((route_lines or {}).items()):
        coords = [DEPOT] + [[next(b for b in bins if b["id"] == bid)["latitude"],
                              next(b for b in bins if b["id"] == bid)["longitude"]] for bid in ordered] + [DEPOT]
        if len(coords) > 2:
            folium.PolyLine(coords, color=route_colors[route_index % len(route_colors)],
                            weight=4, opacity=.85, tooltip=vehicle).add_to(m)
    return m


def make_route_plan(threshold: int = 65):
    candidates = sorted([b for b in bins if b["fill_pct"] >= threshold], key=priority_score, reverse=True)
    if not candidates:
        data["routes"] = {}
        data["route_order"] = []
        return False, "All collection points are within their service thresholds."
    vehicle_rows = [v for v in vehicles if v["available"]]
    if not vehicle_rows:
        return False, "No available vehicles. Release a vehicle before planning routes."
    capacity = min(v["capacity_l"] for v in vehicle_rows)
    demands = [max(1, int(round(b["capacity_l"] * b["fill_pct"] / 100))) for b in candidates]
    if max(demands) > capacity:
        return False, "A collection point exceeds the capacity of the available fleet."
    try:
        optimized = solve_vrp(
            [{"latitude":b["latitude"],"longitude":b["longitude"],"waste_volume":d}
             for b,d in zip(candidates,demands)],
            num_vehicles=len(vehicle_rows),
            vehicle_capacity=capacity,
        )
    except Exception as exc:
        return False, f"Route planning could not complete: {exc}"
    routes = {}
    for index, (vehicle_key, result) in enumerate(optimized.items()):
        vehicle = vehicle_rows[index]
        route_bins = [candidates[i]["id"] for i in result["route_bin_indices"]]
        coords = [DEPOT] + [[next(b for b in bins if b["id"] == bid)["latitude"],
                              next(b for b in bins if b["id"] == bid)["longitude"]] for bid in route_bins] + [DEPOT]
        km = sum(distance_km(coords[i],coords[i+1]) for i in range(len(coords)-1))
        routes[vehicle["id"]] = {"bins":route_bins,"load_l":int(result["total_load"]),"capacity_l":vehicle["capacity_l"],"distance_km":km}
    data["routes"] = routes
    data["route_order"] = list(routes)
    return True, f"Created {len(routes)} vehicle routes covering {sum(len(r['bins']) for r in routes.values())} collection points."


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-icon">♻</div><div><div class="brand-name">WasteOps</div><div class="brand-sub">Collection intelligence</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="eyebrow">Workspace</div>', unsafe_allow_html=True)
    pages = ["Overview","Bin network","Route planner","Collection jobs","Fleet","Analytics"]
    selected = st.radio("Navigation", pages, label_visibility="collapsed", key="active_page")
    st.divider()
    st.markdown('<div class="eyebrow">Operations status</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:#dce9e0;font-size:13px;margin:8px 0">● <span style="color:#8fe0b2">All systems operational</span></div>', unsafe_allow_html=True)
    st.caption(f"{len(bins)} collection points · {len(vehicles)} vehicles")
    st.divider()
    st.download_button(
        "↓  Save workspace",
        data=json.dumps(data, indent=2),
        file_name="wasteops-workspace.json",
        mime="application/json",
        use_container_width=True,
    )
    uploaded_workspace = st.file_uploader("Restore workspace", type=["json"], label_visibility="collapsed")
    if uploaded_workspace and st.button("Restore saved workspace", use_container_width=True):
        try:
            restored = json.loads(uploaded_workspace.getvalue().decode("utf-8"))
            required = {"bins", "vehicles", "jobs", "history", "routes", "route_order", "events", "next_job", "next_bin"}
            if not isinstance(restored, dict) or not required.issubset(restored):
                raise ValueError("Workspace file is missing required sections.")
            if not all(isinstance(restored[key], list) for key in ("bins", "vehicles", "jobs", "history", "route_order", "events")):
                raise ValueError("Workspace sections have an invalid format.")
            st.session_state.wasteops = restored
            st.success("Workspace restored.")
            st.rerun()
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            st.error(f"Could not restore workspace: {exc}")
    if st.button("↻  Reset workspace", use_container_width=True, type="secondary"):
        st.session_state.wasteops = make_workspace()
        st.rerun()
    st.caption("WasteOps · Collection operations")


# ---------------------------------------------------------------------------
# Shared header and computed state
# ---------------------------------------------------------------------------
now = datetime.now()
needs = [b for b in bins if b["fill_pct"] >= 80]
attention = [b for b in bins if 65 <= b["fill_pct"] < 80]
completed = [j for j in jobs if j["status"] == "Completed"]
active_jobs = [j for j in jobs if j["status"] in ("Assigned","In progress")]
avg_fill = float(np.mean([b["fill_pct"] for b in bins])) if bins else 0
header_titles = {
    "Overview":("Operations overview","A clear view of collection activity across your service area."),
    "Bin network":("Collection point network","Monitor fill levels, service needs and collection point details."),
    "Route planner":("Route planning","Build capacity-aware collection plans across your fleet."),
    "Collection jobs":("Collection management","Coordinate assignments and keep every collection accountable."),
    "Fleet":("Fleet management","Track vehicle availability, capacity and driver assignments."),
    "Analytics":("Performance analytics","Understand service performance and operational trends."),
}
title, subtitle = header_titles[selected]
left, right = st.columns([3,1])
with left:
    st.markdown('<div class="eyebrow">WASTE COLLECTION MANAGEMENT</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="muted" style="margin-top:-8px">{subtitle}</p>', unsafe_allow_html=True)
with right:
    st.markdown(f'<div style="text-align:right;padding-top:14px;color:#9bb3a3;font-size:12px">{now.strftime("%A, %d %B %Y")}<br><b style="color:#e8f4eb">{now.strftime("%H:%M")}</b></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
if selected == "Overview":
    st.markdown('<div class="section-head"><span>Live operations snapshot</span><span>Updated just now</span></div>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Bins monitored",len(bins),"+2 this week")
    c2.metric("Requiring pickup",len(needs),f"{len(attention)} approaching threshold")
    c3.metric("Active collections",len(active_jobs),f"{len(completed)} completed today")
    c4.metric("Average fill level",f"{avg_fill:.0f}%","Across all collection points")
    a,b = st.columns([1.65,1])
    with a:
        st.markdown('<div class="section-head"><span>Collection point activity</span><span>Service area</span></div>', unsafe_allow_html=True)
        st_folium(build_map(),width=None,height=430,key="overview_map",returned_objects=[])
    with b:
        st.markdown('<div class="section-head"><span>Priority queue</span></div>', unsafe_allow_html=True)
        for row in sorted(bins,key=priority_score,reverse=True)[:6]:
            score=priority_score(row)
            color="#f07878" if score>=80 else "#e6b65f" if score>=60 else "#75d69b"
            st.markdown(f'<div class="panel" style="padding:12px 14px;margin-bottom:9px"><div style="display:flex;justify-content:space-between"><b>{row["id"]}</b><span style="color:{color};font-size:12px;font-weight:700">{score:.0f} priority</span></div><div style="color:#91a99a;font-size:11px;margin:4px 0 8px">{row["area"]} · {row["type"]}</div><div style="height:6px;background:#263c30;border-radius:9px"><div style="height:6px;width:{row["fill_pct"]}%;background:{color};border-radius:9px"></div></div><div style="display:flex;justify-content:space-between;color:#a9c0b1;font-size:11px;margin-top:5px"><span>{row["fill_pct"]:.0f}% full</span><span>{row["capacity_l"]} L</span></div></div>',unsafe_allow_html=True)
    x,y = st.columns([1.2,1])
    with x:
        st.markdown('<div class="section-head"><span>Collection activity · 24 hours</span></div>',unsafe_allow_html=True)
        history=pd.DataFrame(data["history"]).set_index("time")
        st.area_chart(history[["collected"]],height=220,color="#70d69a")
    with y:
        st.markdown('<div class="section-head"><span>Recent activity</span></div>',unsafe_allow_html=True)
        events=data["events"][:5] or [
            {"time":"Today · 09:42","message":"Collection schedule refreshed"},
            {"time":"Today · 09:18","message":"Vehicle TRK-02 started assigned route"},
            {"time":"Today · 08:56","message":"Collection point BIN-019 serviced"},
        ]
        for event in events:
            st.markdown(f'<div style="padding:10px 0;border-bottom:1px solid #20382b"><div style="color:#e4f1e8;font-size:12px">{event["message"]}</div><div style="color:#789382;font-size:10px;margin-top:4px">{event["time"]}</div></div>',unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Bin network
# ---------------------------------------------------------------------------
elif selected == "Bin network":
    filters=st.columns([1.5,1,1,1])
    with filters[0]: search=st.text_input("Search collection points",placeholder="Search by ID or area")
    with filters[1]: status_filter=st.selectbox("Service status",["All","Needs collection","Attention","Normal"])
    with filters[2]: type_filter=st.selectbox("Waste type",["All"]+BIN_TYPES)
    with filters[3]: area_filter=st.selectbox("Area",["All"]+AREAS)
    filtered=[b for b in bins if (not search or search.lower() in b["id"].lower() or search.lower() in b["area"].lower()) and (status_filter=="All" or b["status"]==status_filter) and (type_filter=="All" or b["type"]==type_filter) and (area_filter=="All" or b["area"]==area_filter)]
    m1,m2,m3=st.columns(3)
    m1.metric("Showing collection points",len(filtered))
    m2.metric("Above 80% fill",sum(b["fill_pct"]>=80 for b in filtered))
    m3.metric("Average fill",f'{np.mean([b["fill_pct"] for b in filtered]):.0f}%' if filtered else "—")
    tab1,tab2=st.tabs(["Map view","List view"])
    with tab1:
        st_folium(build_map([b["id"] for b in filtered]),width=None,height=510,key="bins_map",returned_objects=[])
    with tab2:
        table=pd.DataFrame(filtered)
        if not table.empty:
            table["priority"]=table.apply(lambda r:priority_score(r.to_dict()),axis=1)
            st.dataframe(table[["id","area","type","fill_pct","capacity_l","status","priority","battery_pct"]].rename(columns={"id":"Bin ID","area":"Area","type":"Waste type","fill_pct":"Fill %","capacity_l":"Capacity (L)","status":"Status","priority":"Priority","battery_pct":"Battery %"}),use_container_width=True,hide_index=True)
    st.markdown('<div class="section-head"><span>Collection point controls</span></div>',unsafe_allow_html=True)
    ids=[b["id"] for b in bins]
    with st.form("bin_update_form"):
        e1,e2,e3=st.columns([1,1,1])
        with e1: chosen=st.selectbox("Collection point",ids)
        selected_bin=next(b for b in bins if b["id"]==chosen)
        with e2: fill=st.slider("Current fill level",0,100,int(selected_bin["fill_pct"]))
        with e3: battery=st.slider("Battery level",0,100,int(selected_bin["battery_pct"]))
        submitted=st.form_submit_button("Save collection point")
    if submitted:
        selected_bin["fill_pct"]=float(fill);selected_bin["battery_pct"]=int(battery);refresh_bin_status(selected_bin)
        log_event(f'{chosen} updated · {fill}% fill')
        st.success(f"{chosen} updated successfully.")
    with st.expander("Register a collection point"):
        with st.form("add_bin_form"):
            q1,q2,q3=st.columns(3)
            with q1: new_area=st.selectbox("Area",AREAS)
            with q2: new_type=st.selectbox("Waste type",BIN_TYPES)
            with q3: new_capacity=st.selectbox("Capacity", [120,240,360,660])
            add=st.form_submit_button("Add collection point")
        if add:
            rng=np.random.default_rng(data["next_bin"]*7)
            bid=f'BIN-{data["next_bin"]:03d}';data["next_bin"]+=1
            bins.append({"id":bid,"area":new_area,"type":new_type,"latitude":DEPOT[0]+float(rng.uniform(-.02,.02)),"longitude":DEPOT[1]+float(rng.uniform(-.02,.02)),"capacity_l":int(new_capacity),"fill_pct":0.0,"temperature_c":27.0,"criticality":"Medium","last_collected":datetime.now().isoformat(timespec="minutes"),"status":"Normal","battery_pct":100})
            log_event(f"New collection point registered · {bid}")
            st.success(f"{bid} added to the network.")

# ---------------------------------------------------------------------------
# Route planner
# ---------------------------------------------------------------------------
elif selected == "Route planner":
    st.markdown('<div class="panel" style="margin-bottom:16px"><div class="eyebrow">FLEET OPTIMIZATION</div><div style="font:700 17px Manrope;color:#eff8f1;margin:6px 0">Plan the next collection run</div><div style="color:#9bb3a5;font-size:12px">Prioritise collection points, respect vehicle capacity and distribute work across available vehicles.</div></div>',unsafe_allow_html=True)
    eligible=[b for b in bins if b["fill_pct"]>=65]
    k1,k2,k3=st.columns(3)
    k1.metric("Points awaiting service",len(eligible))
    k2.metric("Available vehicles",sum(v["available"] for v in vehicles))
    k3.metric("Estimated collection volume",f'{sum(b["capacity_l"]*b["fill_pct"]/100 for b in eligible):,.0f} L')
    r1,r2=st.columns([1,2])
    with r1:
        st.markdown('<div class="section-head"><span>Planning controls</span></div>',unsafe_allow_html=True)
        threshold=st.slider("Collection threshold",40,95,65,5)
        active_vehicle_count=st.slider("Vehicles to deploy",1,max(1,len([v for v in vehicles if v["available"]])),min(3,max(1,len([v for v in vehicles if v["available"]]))))
        capacity_override=st.selectbox("Vehicle capacity",["Use fleet capacity","600 L","900 L","1,200 L","1,500 L"])
        if st.button("✦  Optimize collection routes",use_container_width=True):
            candidates=[b for b in bins if b["fill_pct"]>=threshold]
            available=[v for v in vehicles if v["available"]][:active_vehicle_count]
            original_capacities=[v["capacity_l"] for v in available]
            if capacity_override!="Use fleet capacity":
                cap=int(capacity_override.replace(" L","").replace(",",""))
                for v in available:v["capacity_l"]=min(cap,v["capacity_l"])
            if not candidates: st.info("No collection points currently meet this threshold.")
            elif not available: st.error("No vehicles are available.")
            elif max(b["capacity_l"]*b["fill_pct"]/100 for b in candidates)>min(v["capacity_l"] for v in available): st.error("A collection point exceeds available vehicle capacity. Adjust the threshold or fleet.")
            else:
                ok,message=make_route_plan(threshold)
                for v,capacity in zip(available,original_capacities):v["capacity_l"]=capacity
                if ok:
                    log_event("Collection routes optimized · "+str(len(data["routes"]))+" vehicles assigned")
                    st.success(message)
                else:st.error(message)
    with r2:
        st.markdown('<div class="section-head"><span>Service area map</span></div>',unsafe_allow_html=True)
        route_lines={v:r["bins"] for v,r in data["routes"].items()}
        st_folium(build_map([b["id"] for b in eligible],route_lines),width=None,height=420,key="routes_map",returned_objects=[])
    if data["routes"]:
        st.markdown('<div class="section-head"><span>Optimized vehicle schedules</span></div>',unsafe_allow_html=True)
        for vehicle_id in data["route_order"]:
            route=data["routes"][vehicle_id]
            vehicle=next(v for v in vehicles if v["id"]==vehicle_id)
            with st.container(border=True):
                a,b,c=st.columns([2,1,1])
                a.markdown(f'**{vehicle_id}** · {vehicle["driver"]}')
                b.metric("Assigned volume",f'{route["load_l"]} L')
                c.metric("Estimated distance",f'{route["distance_km"]:.1f} km')
                st.progress(min(1,route["load_l"]/max(1,route["capacity_l"])))
                st.caption(" → ".join(["Depot"]+route["bins"]+["Depot"]))
                if st.button(f"Create jobs for {vehicle_id}",key=f"jobs_{vehicle_id}"):
                    for bid in route["bins"]:
                        if not any(j["bin_id"]==bid and j["status"] in ("Assigned","In progress") for j in jobs):
                            row=next(b for b in bins if b["id"]==bid)
                            jid=f'JOB-{data["next_job"]}';data["next_job"]+=1
                            jobs.insert(0,{"id":jid,"bin_id":bid,"area":row["area"],"priority":"High" if priority_score(row)>=75 else "Medium","status":"Assigned","vehicle":vehicle_id,"created":datetime.now().strftime("%d %b, %H:%M")})
                    vehicle["available"]=False
                    log_event(f"Collection jobs created for {vehicle_id}")
                    st.success(f"Jobs created and {vehicle_id} assigned.")
    else:
        st.info("Choose your service threshold and optimize routes to generate vehicle schedules.")

# ---------------------------------------------------------------------------
# Collection jobs
# ---------------------------------------------------------------------------
elif selected == "Collection jobs":
    f1,f2=st.columns([1,1])
    with f1: job_status=st.selectbox("Filter by status",["All","Assigned","In progress","Completed"])
    with f2: job_search=st.text_input("Find a job",placeholder="Job ID or bin ID")
    filtered=[j for j in jobs if (job_status=="All" or j["status"]==job_status) and (not job_search or job_search.lower() in j["id"].lower() or job_search.lower() in j["bin_id"].lower())]
    q1,q2,q3=st.columns(3)
    q1.metric("Total jobs",len(jobs));q2.metric("In progress",sum(j["status"]=="In progress" for j in jobs));q3.metric("Completed",len(completed))
    st.dataframe(pd.DataFrame(filtered).rename(columns={"id":"Job ID","bin_id":"Bin","area":"Area","priority":"Priority","status":"Status","vehicle":"Vehicle","created":"Created"}),use_container_width=True,hide_index=True)
    st.markdown('<div class="section-head"><span>Update collection job</span></div>',unsafe_allow_html=True)
    pending=[j for j in jobs if j["status"]!="Completed"]
    if pending:
        with st.form("job_update"):
            a,b,c=st.columns(3)
            with a: jid=st.selectbox("Job", [j["id"] for j in pending])
            with b: action=st.selectbox("New status",["In progress","Completed"])
            with c: note=st.text_input("Service note",placeholder="Collection completed")
            save=st.form_submit_button("Update job")
        if save:
            job=next(j for j in jobs if j["id"]==jid);job["status"]=action
            row=next((b for b in bins if b["id"]==job["bin_id"]),None)
            if action=="Completed" and row:
                row["fill_pct"]=0.0;row["last_collected"]=datetime.now().isoformat(timespec="minutes");refresh_bin_status(row)
                vehicle=next((v for v in vehicles if v["id"]==job["vehicle"]),None)
                if vehicle and not any(j["vehicle"]==vehicle["id"] and j["status"] in ("Assigned","In progress") for j in jobs):vehicle["available"]=True
            log_event(f"{jid} marked {action.lower()}"+(f" · {note}" if note else ""))
            st.success(f"{jid} updated.")
    else: st.success("All collection jobs are complete.")
    with st.expander("Create a manual collection job"):
        due=[b for b in bins if b["fill_pct"]>=40]
        if due:
            with st.form("manual_job"):
                a,b=st.columns(2)
                with a: manual_bin=st.selectbox("Collection point",[b["id"] for b in due])
                with b: manual_priority=st.selectbox("Priority",["High","Medium","Low"])
                create=st.form_submit_button("Create job")
            if create:
                row=next(b for b in bins if b["id"]==manual_bin)
                jid=f'JOB-{data["next_job"]}';data["next_job"]+=1
                jobs.insert(0,{"id":jid,"bin_id":manual_bin,"area":row["area"],"priority":manual_priority,"status":"Assigned","vehicle":"Unassigned","created":datetime.now().strftime("%d %b, %H:%M")})
                log_event(f"Manual collection job created · {jid}")
                st.success(f"{jid} created.")
        else: st.info("No collection points currently need a manual collection job.")

# ---------------------------------------------------------------------------
# Fleet
# ---------------------------------------------------------------------------
elif selected == "Fleet":
    available=sum(v["available"] for v in vehicles)
    a,b,c=st.columns(3);a.metric("Fleet size",len(vehicles));b.metric("Available",available);c.metric("On assignment",len(vehicles)-available)
    for vehicle in vehicles:
        with st.container(border=True):
            l,r=st.columns([3,1])
            with l:
                st.markdown(f"**{vehicle['id']}** · {vehicle['type']}")
                st.caption(f"{vehicle['driver']} · {vehicle['zone']} zone · {vehicle['capacity_l']:,} L capacity")
                st.progress(vehicle["fuel_pct"]/100,text=f"Fuel level · {vehicle['fuel_pct']}%")
            with r:
                st.markdown(f'<span class="pill">{"AVAILABLE" if vehicle["available"] else "ON ROUTE"}</span>',unsafe_allow_html=True)
                if st.button("Release" if not vehicle["available"] else "Set unavailable",key=f"fleet_{vehicle['id']}"):
                    vehicle["available"]=not vehicle["available"]
                    log_event(f'{vehicle["id"]} status changed')
                    st.rerun()
    with st.expander("Register a vehicle"):
        with st.form("new_vehicle"):
            a,b=st.columns(2)
            with a: vid=st.text_input("Vehicle ID",placeholder="TRK-05")
            with b: driver=st.text_input("Driver name")
            c,d=st.columns(2)
            with c: vtype=st.selectbox("Vehicle type",["Compactor","Tipper","Mini truck"])
            with d: vcap=st.selectbox("Capacity (L)",[600,900,1200,1500,2000])
            add=st.form_submit_button("Register vehicle")
        if add:
            if not vid.strip() or not driver.strip() or any(v["id"]==vid.strip() for v in vehicles):st.error("Enter a unique vehicle ID and driver name.")
            else:
                vehicles.append({"id":vid.strip().upper(),"driver":driver.strip(),"type":vtype,"capacity_l":vcap,"available":True,"fuel_pct":100,"zone":"Unassigned"})
                log_event(f"Vehicle registered · {vid.upper()}")
                st.success("Vehicle registered.")

# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
elif selected == "Analytics":
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Collection points",len(bins));c2.metric("Average fill",f"{avg_fill:.1f}%");c3.metric("Jobs completed",len(completed));c4.metric("Service completion",f'{(len(completed)/max(1,len(jobs)))*100:.0f}%')
    st.markdown('<div class="section-head"><span>Fill level distribution</span></div>',unsafe_allow_html=True)
    distribution=pd.DataFrame({"Collection point":[b["id"] for b in bins],"Fill level":[b["fill_pct"] for b in bins]}).set_index("Collection point")
    st.bar_chart(distribution,height=300,color="#72d69d")
    left,right=st.columns(2)
    with left:
        st.markdown('<div class="section-head"><span>Collection volume trend</span></div>',unsafe_allow_html=True)
        st.area_chart(pd.DataFrame(data["history"]).set_index("time")[["collected"]],height=250,color="#65b9df")
    with right:
        st.markdown('<div class="section-head"><span>Service status mix</span></div>',unsafe_allow_html=True)
        status_counts=pd.Series([b["status"] for b in bins]).value_counts()
        st.bar_chart(status_counts,height=250,color="#d6b36b")
    st.markdown('<div class="section-head"><span>Export operational data</span></div>',unsafe_allow_html=True)
    export=pd.DataFrame(bins)
    st.download_button("↓  Download collection point report (CSV)",export.to_csv(index=False).encode("utf-8"),file_name="wasteops-collection-points.csv",mime="text/csv")
    st.download_button("↓  Download collection jobs (CSV)",pd.DataFrame(jobs).to_csv(index=False).encode("utf-8"),file_name="wasteops-collection-jobs.csv",mime="text/csv")

st.markdown("<hr>",unsafe_allow_html=True)
st.markdown('<div style="display:flex;justify-content:space-between;color:#688574;font-size:10px;letter-spacing:1px"><span>WASTEOPS · COLLECTION OPERATIONS</span><span>PLAN · COLLECT · IMPROVE</span></div>',unsafe_allow_html=True)
