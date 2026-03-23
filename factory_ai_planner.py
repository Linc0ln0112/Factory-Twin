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
st.title("⚡ Factory Planner")

data = load_data()

t_col1, t_col2 = st.columns([1, 8])
with t_col1:
    st.write("###")
    if st.button("⏹ Pause" if st.session_state.playing else "▶ Play"):
        st.session_state.playing = not st.session_state.playing
        st.rerun()

with t_col2:
    st.session_state.view_date = st.slider(
        "🗓️ Factory Evolution", 
        min_value=date.today(), max_value=date.today() + timedelta(days=365), 
        value=st.session_state.view_date, format="MMM DD, YYYY"
    )

st.divider()
left, right = st.columns([1, 4])

# ------------------------------------------------
# 4. SIDEBAR: CONTROLS & LEGEND
# ------------------------------------------------
with left:
    st.subheader("📝 New Proposal")
    p_type = st.selectbox("Proposed Category", list(OCCUPIED_TYPES.keys()) + ["Free"])
    p_start = st.date_input("Start Date", value=st.session_state.view_date)
    p_end = st.date_input("End Date", value=p_start + timedelta(days=14))
    p_reason = st.text_input("Project Name/ID", placeholder="e.g., Model Y Line Expansion")
    
    if st.button("Submit Proposal", type="primary", use_container_width=True):
        if st.session_state.selected_bays:
            for b_id in st.session_state.selected_bays:
                if b_id in STRUCTURAL_IDS: continue
                if b_id not in data: data[b_id] = {"history": [], "proposals": []}
                if "proposals" not in data[b_id]: data[b_id]["proposals"] = []
                
                data[b_id]["proposals"].append({
                    "id": f"P-{int(time.time())}",
                    "type": p_type,
                    "start": p_start.isoformat(),
                    "end": p_end.isoformat(),
                    "reason": p_reason
                })
            save_data(data)
            st.session_state.selected_bays = set()
            st.rerun()

    if st.button("Clear Selection", use_container_width=True):
        st.session_state.selected_bays = set()
        st.rerun()

    # --- THE LEGEND ---
    st.divider()
    with st.expander("🎨 Map Legend", expanded=True):
        st.markdown("### Categories")
        # Loop through our types to create the color labels
        for label, color in OCCUPIED_TYPES.items():
            st.markdown(f"<span style='color:{color}; font-size:20px;'>■</span> {label}", unsafe_allow_html=True)
        
        st.markdown(f"<span style='color:{STATUSES['Free']}; font-size:20px;'>■</span> Free Space", unsafe_allow_html=True)
        st.markdown(f"<span style='color:{STATUSES['Blocked']}; font-size:20px;'>■</span> Columns/Walls", unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### Status Indicators")
        st.markdown(f"<span style='color:{SELECTION_COLOR}; font-size:20px;'>■</span> **Active Selection**", unsafe_allow_html=True)
        st.markdown(f"<span style='border:2px solid {PENDING_OUTLINE}; padding:1px 5px; color:white;'>Red Border</span> **Pending Proposal**", unsafe_allow_html=True)

    # Display selection count for clarity
    if st.session_state.selected_bays:
        st.success(f"Selected: {len(st.session_state.selected_bays)} bays")

# ------------------------------------------------
# 5. RENDER ENGINE (Timeline Logic)
# ------------------------------------------------
def create_map():
    v_date = st.session_state.view_date
    colors, texts, l_widths, l_colors = [], [], [], []
    
    for b_id in bays_df['bay']:
        is_selected = b_id in st.session_state.selected_bays
        info = data.get(b_id)
        
        # Defaults
        base_col, label, b_col, b_wid, reason_str = STATUSES["Free"], "Free", "#222", 1, ""
        
        if b_id in STRUCTURAL_IDS:
            base_col, label = STATUSES["Blocked"], "Column"
        elif info:
            # 1. Search History for a valid match for the current "Clock" date
            active_event = None
            for event in info.get("history", []):
                h_s, h_e = date.fromisoformat(event["start"]), date.fromisoformat(event["end"])
                if h_s <= v_date <= h_e:
                    active_event = event
                    break
            
            if active_event:
                label = active_event["type"]
                base_col = STATUSES.get(label, "#d3d3d3")
                reason_str = f"<br>Current: {active_event.get('reason', 'N/A')}"

            # 2. Check for Proposals (Red Border)
            for p in info.get("proposals", []):
                ps_d, pe_d = date.fromisoformat(p["start"]), date.fromisoformat(p["end"])
                if ps_d <= v_date <= pe_d:
                    b_col, b_wid = PENDING_OUTLINE, 3
                    label = f"{label} → {p['type']} (PENDING)"
                    reason_str += f"<br>Projected: {p['reason']}"

        colors.append(SELECTION_COLOR if is_selected else base_col)
        l_widths.append(2 if is_selected else b_wid)
        l_colors.append("#FFFFFF" if is_selected else b_col)
        texts.append(f"<b>{b_id}</b><br>{label}{reason_str}")

    fig = go.Figure(go.Scattergl(
        x=bays_df['x'], y=bays_df['y'], mode="markers",
        marker=dict(symbol="square", size=17, color=colors, line=dict(width=l_widths, color=l_colors)),
        text=texts, hoverinfo="text"
    ))
    fig.update_layout(template="plotly_dark", height=700, margin=dict(l=0,r=0,t=0,b=0),
                      xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False, autorange="reversed"),
                      uirevision="constant", dragmode='select', clickmode='event+select')
    return fig

with right:
    ev = plotly_events(create_map(), click_event=True, select_event=True, key="factory_map", override_height=700)
    if ev and not st.session_state.playing:
        new_ids = {bays_df.iloc[p['pointNumber']]['bay'] for p in ev if 'pointNumber' in p}
        st.session_state.selected_bays ^= new_ids
        st.rerun()

# ------------------------------------------------
# 6. PROPOSAL MANAGEMENT
# ------------------------------------------------
st.divider()
st.subheader("📋 Requests In Review")

all_proposals = []
for b_id, info in data.items():
    for p in info.get("proposals", []):
        all_proposals.append({
            "Bay": b_id, "Type": p["type"], "Start": p["start"], "End": p["end"], 
            "Project": p["reason"], "internal_id": p["id"]
        })

if all_proposals:
    prop_df = pd.DataFrame(all_proposals)
    for project, group in prop_df.groupby("Project"):
        with st.expander(f"Project: {project} ({len(group)} Bays)"):
            st.table(group[["Bay", "Type", "Start", "End"]])
            c1, c2 = st.columns(2)
            
            if c1.button(f"✅ Approve {project}", key=f"app_{project}"):
                for idx, row in group.iterrows():
                    b_id = row["Bay"]
                    # Add to history list instead of overwriting a single value
                    if "history" not in data[b_id]: data[b_id]["history"] = []
                    data[b_id]["history"].append({
                        "type": row["Type"],
                        "start": row["Start"],
                        "end": row["End"],
                        "reason": project
                    })
                    # Remove from proposal list
                    data[b_id]["proposals"] = [p for p in data[b_id]["proposals"] if p["reason"] != project]
                save_data(data); st.rerun()
                
            if c2.button(f"❌ Reject {project}", key=f"rej_{project}"):
                for b_id in group["Bay"]:
                    data[b_id]["proposals"] = [p for p in data[b_id]["proposals"] if p["reason"] != project]
                save_data(data); st.rerun()
else:
    st.info("No pending proposals.")

# ------------------------------------------------
# 7. ANIMATION
# ------------------------------------------------
if st.session_state.playing:
    time.sleep(0.08); st.session_state.view_date += timedelta(days=1)
    if st.session_state.view_date >= date.today() + timedelta(days=365): st.session_state.view_date = date.today()
    st.rerun()
