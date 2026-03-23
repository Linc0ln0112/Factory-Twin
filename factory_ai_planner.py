import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_plotly_events2 import plotly_events 
import json
import os
from datetime import date, timedelta
import time

# ------------------------------------------------
# 1. CONFIG
# ------------------------------------------------
GRID_X, GRID_Y, CELL = 60, 30, 20
DATA_FILE = "factory_grid.json"

OCCUPIED_TYPES = {
    "Traffic": "#FFFF00", "Storage": "#0047AB", "Production": "#1e90ff",
    "Buffer": "#87CEEB", "Utilities": "#FFA500", "Safety": "#FF8C00"
}
STATUSES = {"Free": "#d3d3d3", "Blocked": "#444444", **OCCUPIED_TYPES}
SELECTION_COLOR = "#00FF00" 
PENDING_OUTLINE = "#FF0000"

@st.cache_data
def get_grid_coordinates():
    return pd.DataFrame([{"bay": f"B{x}_{y}", "x": x * CELL, "y": y * CELL} 
                         for x in range(GRID_X) for y in range(GRID_Y)])

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data(data_dict):
    with open(DATA_FILE, "w") as f: json.dump(data_dict, f, indent=2)

bays_df = get_grid_coordinates()
STRUCTURAL_IDS = {f"B{x}_{y}" for x in range(GRID_X) for y in range(GRID_Y) if x % 5 == 0 and y % 5 == 0}

# ------------------------------------------------
# 2. SESSION STATE
# ------------------------------------------------
if "selected_bays" not in st.session_state: st.session_state.selected_bays = set()
if "view_date" not in st.session_state: st.session_state.view_date = date.today()
if "playing" not in st.session_state: st.session_state.playing = False

# ------------------------------------------------
# 3. UI HEADER
# ------------------------------------------------
st.set_page_config(layout="wide", page_title="Tesla Digital Twin")
st.title("⚡ Factory Planner: Persistent Status")

data = load_data()

t_col1, t_col2 = st.columns([1, 10])
with t_col1:
    st.write("###")
    if st.button("⏹ Pause" if st.session_state.playing else "▶ Play"):
        st.session_state.playing = not st.session_state.playing
        st.rerun()

with t_col2:
    st.session_state.view_date = st.slider(
        "🗓️ Factory Evolution", 
        min_value=date.today() - timedelta(days=30), 
        max_value=date.today() + timedelta(days=365), 
        value=st.session_state.view_date, format="MMM DD, YYYY"
    )

left, right = st.columns([1, 6])

# ------------------------------------------------
# 4. SIDEBAR: PROPOSALS
# ------------------------------------------------
with left:
    st.subheader("📝 New Proposal")
    p_type = st.selectbox("Proposed Category", list(OCCUPIED_TYPES.keys()) + ["Free"])
    p_start = st.date_input("Start Date", value=st.session_state.view_date)
    p_reason = st.text_input("Project Name/ID", placeholder="e.g., Robot Install")
    
    st.caption("Note: Approved changes persist from Start Date forward.")
    
    if st.button("Submit Proposal", type="primary", use_container_width=True):
        if st.session_state.selected_bays:
            for b_id in st.session_state.selected_bays:
                if b_id in STRUCTURAL_IDS: continue
                if b_id not in data: data[b_id] = {"history": [], "proposals": []}
                data[b_id].setdefault("proposals", []).append({
                    "id": f"P-{int(time.time())}", "type": p_type,
                    "start": p_start.isoformat(), "reason": p_reason
                })
            save_data(data); st.session_state.selected_bays = set(); st.rerun()

    if st.button("Clear Selection", use_container_width=True):
        st.session_state.selected_bays = set(); st.rerun()

# ------------------------------------------------
# 5. RENDER ENGINE (Most Recent State Logic)
# ------------------------------------------------
def create_map():
    v_date = st.session_state.view_date
    colors, texts, l_widths, l_colors = [], [], [], []
    
    for b_id in bays_df['bay']:
        is_selected = b_id in st.session_state.selected_bays
        info = data.get(b_id)
        base_col, label, b_col, b_wid, reason_str = STATUSES["Free"], "Free", "#111", 1, ""
        
        if b_id in STRUCTURAL_IDS:
            base_col, label = STATUSES["Blocked"], "Column"
        elif info:
            # FIND MOST RECENT APPROVED STATE
            # Sort history by date descending to find the latest applicable change
            valid_history = [h for h in info.get("history", []) if date.fromisoformat(h["start"]) <= v_date]
            if valid_history:
                # Get the one with the latest start date
                latest_event = max(valid_history, key=lambda x: x["start"])
                label = latest_event["type"]
                base_col = STATUSES.get(label, "#d3d3d3")
                reason_str = f"<br>Status: {label}<br>Since: {latest_event['start']}"

            # OVERLAY PENDING PROPOSALS
            for p in info.get("proposals", []):
                ps_d = date.fromisoformat(p["start"])
                # Proposal only shows if we are on or after its start date
                if ps_d <= v_date:
                    b_col, b_wid = PENDING_OUTLINE, 3
                    label = f"{label} → {p['type']} (PENDING)"
                    reason_str += f"<br><b>PROPOSED:</b> {p['reason']}"

        colors.append(SELECTION_COLOR if is_selected else base_col)
        l_widths.append(2 if is_selected else b_wid)
        l_colors.append("#FFFFFF" if is_selected else b_col)
        texts.append(f"<b>{b_id}</b><br>{label}{reason_str}")

    fig = go.Figure(go.Scattergl(
        x=bays_df['x'], y=bays_df['y'], mode="markers",
        marker=dict(symbol="square", size=22, color=colors, line=dict(width=l_widths, color=l_colors)),
        text=texts, hoverinfo="text"
    ))
    
    fig.update_layout(
        template="plotly_dark", height=850, margin=dict(l=5, r=5, t=5, b=5),
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True, autorange="reversed"),
        uirevision="constant", dragmode='select', clickmode='event+select'
    )
    return fig

with right:
    ev = plotly_events(create_map(), click_event=True, select_event=True, key="factory_map", override_height=850)
    if ev and not st.session_state.playing:
        new_ids = {bays_df.iloc[p['pointNumber']]['bay'] for p in ev if 'pointNumber' in p}
        st.session_state.selected_bays ^= new_ids; st.rerun()
    
    # LEGEND
    st.write("###")
    cols = st.columns(len(STATUSES) + 1)
    for i, (l, c) in enumerate(list(STATUSES.items()) + [("Selected", SELECTION_COLOR)]):
        cols[i].markdown(f"<div style='border-bottom: 5px solid {c}; text-align: center;'><small><b>{l.upper()}</b></small></div>", unsafe_allow_html=True)

# ------------------------------------------------
# 6. PROPOSAL MANAGEMENT
# ------------------------------------------------
st.divider()
st.subheader("📋 Requests In Review")
all_proposals = []
for b_id, info in data.items():
    for p in info.get("proposals", []):
        all_proposals.append({"Bay": b_id, "Type": p["type"], "Start": p["start"], "Project": p["reason"]})

if all_proposals:
    prop_df = pd.DataFrame(all_proposals)
    for project, group in prop_df.groupby("Project"):
        with st.expander(f"Project: {project} ({len(group)} Bays)"):
            st.table(group[["Bay", "Type", "Start"]])
            if st.button(f"✅ Approve {project}", key=f"app_{project}"):
                for b_id in group["Bay"]:
                    # Create entry: Type and Start date (No End date required now)
                    new_entry = {"type": group.iloc[0]["Type"], "start": str(group.iloc[0]["Start"]), "reason": project}
                    data[b_id].setdefault("history", []).append(new_entry)
                    data[b_id]["proposals"] = [p for p in data[b_id]["proposals"] if p["reason"] != project]
                save_data(data); st.rerun()
else:
    st.info("No pending proposals.")

# ------------------------------------------------
# 7. ANIMATION
# ------------------------------------------------
if st.session_state.playing:
    time.sleep(0.05); st.session_state.view_date += timedelta(days=1)
    if st.session_state.view_date >= date.today() + timedelta(days=365): st.session_state.view_date = date.today()
    st.rerun()
