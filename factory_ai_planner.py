import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_plotly_events2 import plotly_events 
import json
import os
from datetime import date, timedelta
import time

# ------------------------------------------------
# 1. CONFIG & REFINED COLORS
# ------------------------------------------------
GRID_X, GRID_Y, CELL = 60, 30, 20
DATA_FILE = "factory_grid.json"

OCCUPIED_TYPES = {
    "Traffic": "#FFFF00",    # Bright Yellow
    "Storage": "#0047AB",    # Cobalt Blue
    "Production": "#1e90ff", # Tesla Blue
    "Buffer": "#87CEEB",     # Sky Blue
    "Utilities": "#4682B4",  # Steel Blue
    "Safety": "#00FFFF"      # Cyan
}

STATUSES = {
    "Free": "#d3d3d3",
    "Pending": "#ff4d4d",
    "Blocked": "#444444",
    **OCCUPIED_TYPES
}

SELECTION_COLOR = "#00FF00" # High-visibility Lime Green

@st.cache_data
def get_grid_coordinates():
    return pd.DataFrame([{"bay": f"B{x}_{y}", "x": x * CELL, "y": y * CELL} 
                         for x in range(GRID_X) for y in range(GRID_Y)])

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

bays_df = get_grid_coordinates()
data = load_data()
STRUCTURAL_IDS = {f"B{x}_{y}" for x in range(GRID_X) for y in range(GRID_Y) if x % 5 == 0 and y % 5 == 0}

# ------------------------------------------------
# 2. SESSION STATE & ANIMATION LOGIC
# ------------------------------------------------
if "selected_bays" not in st.session_state: st.session_state.selected_bays = set()
if "view_date" not in st.session_state: st.session_state.view_date = date.today()
if "playing" not in st.session_state: st.session_state.playing = False

# ------------------------------------------------
# 3. UI HEADER & TIMELINE
# ------------------------------------------------
st.set_page_config(layout="wide", page_title="Tesla Digital Twin")
st.title("⚡ Factory Digital Twin")

today = date.today()
one_year_out = today + timedelta(days=365)

# --- TOP ANIMATION BAR ---
t_col1, t_col2 = st.columns([1, 8])
with t_col1:
    st.write("###")
    if st.button("⏹ Pause" if st.session_state.playing else "▶ Play Timeline", use_container_width=True):
        st.session_state.playing = not st.session_state.playing
        st.rerun()

with t_col2:
    st.session_state.view_date = st.slider(
        "🗓️ Factory Timeline", 
        min_value=today, max_value=one_year_out, 
        value=st.session_state.view_date, format="MMM DD, YYYY"
    )

st.divider()
left, right = st.columns([1, 4])

# ------------------------------------------------
# 4. SIDEBAR CONTROLS
# ------------------------------------------------
with left:
    st.subheader("Inventory Setup")
    base_status = st.selectbox("Assign Category", ["Occupied", "Pending", "Free"])
    
    sub_type = None
    if base_status == "Occupied":
        sub_type = st.selectbox("Occupancy Type", list(OCCUPIED_TYPES.keys()))
    
    c1, c2 = st.columns(2)
    start_res = c1.date_input("Start", value=st.session_state.view_date)
    end_res = c2.date_input("End", value=st.session_state.view_date + timedelta(days=14))
    
    if st.button("Apply to Selection", type="primary", use_container_width=True):
        if st.session_state.selected_bays:
            for b_id in st.session_state.selected_bays:
                if b_id in STRUCTURAL_IDS: continue 
                if base_status == "Free":
                    data.pop(b_id, None)
                else:
                    data[b_id] = {
                        "status": sub_type if base_status == "Occupied" else "Pending",
                        "category": base_status,
                        "start": start_res.isoformat(),
                        "end": end_res.isoformat()
                    }
            with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)
            st.session_state.selected_bays = set()
            st.rerun()

    if st.button("Clear Selection", use_container_width=True):
        st.session_state.selected_bays = set()
        st.rerun()
        
    st.divider()
    st.metric("Bays Highlighted", len(st.session_state.selected_bays))
    
    for s, c in STATUSES.items():
        st.markdown(f"<span style='color:{c}'>■</span> {s}", unsafe_allow_html=True)
    st.markdown(f"<span style='color:{SELECTION_COLOR}'>■</span> **Current Selection**", unsafe_allow_html=True)

# ------------------------------------------------
# 5. HIGH-SPEED PLOT ENGINE
# ------------------------------------------------
def create_fast_plot():
    v_date = st.session_state.view_date
    colors, texts = [], []
    
    for b_id in bays_df['bay']:
        if b_id in st.session_state.selected_bays:
            colors.append(SELECTION_COLOR); texts.append(f"<b>{b_id}</b> (Selected)")
            continue
        if b_id in STRUCTURAL_IDS:
            colors.append(STATUSES["Blocked"]); texts.append(f"<b>{b_id}</b><br>Column")
            continue

        info = data.get(b_id)
        if info:
            s_d, e_d = date.fromisoformat(info["start"]), date.fromisoformat(info["end"])
            if s_d <= v_date <= e_d:
                colors.append(STATUSES.get(info["status"], "#d3d3d3"))
                texts.append(f"<b>{b_id}</b><br>Type: {info['status']}<br>{s_d} to {e_d}")
                continue
        
        colors.append(STATUSES["Free"]); texts.append(f"<b>{b_id}</b><br>Free")

    fig = go.Figure(go.Scattergl(
        x=bays_df['x'], y=bays_df['y'], mode="markers",
        marker=dict(symbol="square", size=17, color=colors, line=dict(width=1, color="#111"), opacity=1.0),
        text=texts, hoverinfo="text",
        unselected=dict(marker=dict(opacity=1.0)), selected=dict(marker=dict(opacity=1.0))
    ))
    
    fig.update_layout(
        template="plotly_dark", height=800, margin=dict(l=0,r=0,t=0,b=0),
        xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False, autorange="reversed"),
        uirevision="fixed_zoom", dragmode='select', clickmode='event+select'
    )
    return fig

with right:
    # Key change: We use plotly_events with a unique key to prevent re-rendering loops
    event_data = plotly_events(create_fast_plot(), click_event=True, select_event=True, key="tesla_v4_map", override_height=800)
    
    if event_data:
        # Get point indices from the selection/click
        points = {p['pointNumber'] for p in event_data if 'pointNumber' in p}
        new_ids = {bays_df.iloc[p]['bay'] for p in points}
        
        # Performance trick: Update session state without a full rerun if possible, 
        # but Streamlit usually requires a rerun to show the Lime color change.
        if new_ids.issubset(st.session_state.selected_bays) and len(new_ids) == 1:
            st.session_state.selected_bays -= new_ids
        else:
            st.session_state.selected_bays |= new_ids
        st.rerun()

# ------------------------------------------------
# 6. FILTERED RESERVATIONS TABLE
# ------------------------------------------------
st.divider()
st.subheader("📋 Active Factory Log")

# Table strictly excludes "Blocked" (Columns)
table_rows = [
    {"Bay ID": b_id, "Category": info.get("category", "Occupied"), "Type": info["status"], "Arrival": info["start"], "Departure": info["end"]}
    for b_id, info in data.items() 
    if b_id not in STRUCTURAL_IDS
]

if table_rows:
    res_df = pd.DataFrame(table_rows)
    st.dataframe(res_df.sort_values("Bay ID"), use_container_width=True, hide_index=True)
else:
    st.info("No active reservations in the selected timeframe.")

# ------------------------------------------------
# 7. THE ANIMATION ENGINE (Looping)
# ------------------------------------------------
if st.session_state.playing:
    time.sleep(0.05) # Control speed of animation
    st.session_state.view_date += timedelta(days=1)
    if st.session_state.view_date >= one_year_out:
        st.session_state.view_date = today # Reset loop
    st.rerun()