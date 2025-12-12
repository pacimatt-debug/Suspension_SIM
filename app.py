import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from solver import SuspensionSolver

st.set_page_config(page_title="Suspension Lab (Bernoulli)", layout="wide", page_icon="📈")
st.title("📈 Suspension Lab: Bernoulli Analytics")

# --- 1. MAGAZZINO LAMELLE (SMART DATABASE) ---
INVENTORY = {
    6:  [12, 13, 14, 15, 16, 17, 18, 19, 20],
    8:  [16, 18, 20, 22, 24, 26, 28, 30, 32],
    10: [20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40],
    12: [24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44],
    16: [28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50]
}
THICKNESSES = [0.10, 0.15, 0.20, 0.25, 0.30]

# --- INIT SESSION ---
if 'db' not in st.session_state:
    st.session_state['db'] = {
        "WP AER 48 (2024)": {
            "type": "Fork",
            "geometry": {
                'd_valve': 34.0, 'd_rod': 12.0, 'd_clamp': 12.0,
                'n_port': 4, 'd_throat': 9.0, 'n_throat': 4,
                'r_port': 11.5, 'w_port': 14.0, 'h_deck': 2.0, 
                'bleed': 1.5, 'd_leak': 0.0, 'p_zero': 1.5
            },
            "stacks": {"Base": {"shims": [{"id":12, "od":30, "th":0.15}], "stack_float": 0.0}}
        }
    }

db = st.session_state['db']

# --- SIDEBAR: HARDWARE & MAGAZZINO ---
with st.sidebar:
    st.header("🗄️ Progetto")
    susp_name = st.selectbox("Sospensione", list(db.keys()))
    curr_susp = db[susp_name]
    geom = curr_susp['geometry']
    
    st.divider()
    
    # Sezione Magazzino
    st.subheader("➕ Aggiungi Lamelle")
    with st.container(border=True):
        sel_id = st.selectbox("1. ID (mm)", list(INVENTORY.keys()))
        
        # Filtra OD in base all'ID
        ods = INVENTORY.get(sel_id, [])
        c1, c2 = st.columns(2)
        sel_od = c1.selectbox("2. OD (mm)", ods)
        sel_th = c2.selectbox("3. Spess (mm)", THICKNESSES)
        
        qty = st.number_input("Quantità", 1, 20, 1)
        
        if st.button("⬇️ AGGIUNGI ALLO STACK", type="primary", use_container_width=True):
            if 'temp_stack' not in st.session_state: st.session_state['temp_stack'] = []
            for _ in range(qty):
                st.session_state['temp_stack'].append({"id": sel_id, "od": sel_od, "th": sel_th})
            st.success("Aggiunte!")

# --- MAIN: EDITOR E ANALISI ---
col_L, col_R = st.columns([1, 1.5])

with col_L:
    st.subheader("🛠️ Composizione Pacco")
    
    stacks = curr_susp['stacks']
    active_s = st.selectbox("Configurazione", list(stacks.keys()) + ["+ Nuova..."])
    
    if active_s == "+ Nuova...":
        nn = st.text_input("Nome")
        if st.button("Crea") and nn:
            curr_susp['stacks'][nn] = {"shims":[], "stack_float":0.0}
            st.rerun()
        curr_data = {"shims":[], "stack_float":0.0}
    else:
        curr_data = stacks[active_s]

    # Sync con Temp Stack
    if 'temp_stack' not in st.session_state:
        st.session_state['temp_stack'] = curr_data['shims'].copy()
        
    # Input Float
    st_float = st.number_input("Float / Gioco (mm)", value=float(curr_data.get('stack_float', 0.0)), step=0.05)
    
    # Editor Tabellare
    df_stack = pd.DataFrame(st.session_state['temp_stack'])
    edited = st.data_editor(
        df_stack, 
        num_rows="dynamic",
        column_config={
            "id": st.column_config.NumberColumn("ID", format="%d"),
            "od": st.column_config.NumberColumn("OD", format="%d"),
            "th": st.column_config.NumberColumn("Th", format="%.2f")
        },
        use_container_width=True
    )
    
    if st.button("💾 Salva Configurazione", use_container_width=True):
        curr_susp['stacks'][active_s] = {"shims": edited.to_dict('records'), "stack_float": st_float}
        st.session_state['temp_stack'] = edited.to_dict('records')
        st.toast("Salvato!")

    # Dati Hardware Rapidi
    with st.expander("🔍 Geometria Hardware (Sola Lettura)"):
        st.write(f"**Pistone:** {geom['d_valve']}mm | **Porte:** {geom['n_port']}")
        st.write(f"**h.deck (Ingresso):** {geom.get('h_deck',0)}mm")
        st.write(f"**Throat (Gola):** {geom.get('d_throat',0)}mm")
        st.write(f"**Clamp (Fulcro):** {geom.get('d_clamp',0)}mm")

with col_R:
    st.subheader("📊 Analisi Fisica")
    
    if not edited.empty:
        # Controlli Simulazione
        c1, c2 = st.columns(2)
        max_v = c1.slider("Velocità Max (m/s)", 0.5, 8.0, 4.0)
        clk = c2.slider("Clicker %", 0, 100, 100)
        
        # Solver Run
        solver = SuspensionSolver(geom, {"shims": edited.to_dict('records'), "stack_float": st_float})
        
        vv = np.linspace(0, max_v, 25)
        results = [solver.solve_point(v, clk) for v in vv]
        df_res = pd.DataFrame(results)
        
        # TABS DI ANALISI
        tab1, tab2 = st.tabs(["📈 Curve", "🔢 Dati Analitici"])
        
        with tab1:
            fig, ax1 = plt.subplots(figsize=(8,5))
            
            # Forza (Asse Sx)
            ax1.plot(df_res['v'], df_res['force_kg'], 'r-', linewidth=2.5, label="Forza (kgf)")
            ax1.set_xlabel("Velocità (m/s)")
            ax1.set_ylabel("Forza (kgf)", color='r')
            ax1.tick_params(axis='y', labelcolor='r')
            ax1.grid(True, alpha=0.3)
            
            # Pressione (Asse Dx)
            ax2 = ax1.twinx()
            ax2.plot(df_res['v'], df_res['pressure_bar'], 'b--', alpha=0.6, label="Pressione (bar)")
            ax2.set_ylabel("Pressione (bar)", color='b')
            ax2.tick_params(axis='y', labelcolor='b')
            
            st.pyplot(fig)
            st.info(f"Rigidezza Equivalente Stack: **{solver.k_stack_equiv:.2f}**")
            
        with tab2:
            st.write("Analisi punto-punto per debug (Nodo)")
            # Formattazione bella
            st.dataframe(
                df_res.style.format({
                    "v": "{:.2f}",
                    "force_kg": "{:.1f}",
                    "lift_mm": "{:.3f}",
                    "pressure_bar": "{:.1f}",
                    "area_eff_mm2": "{:.1f}"
                }),
                use_container_width=True,
                height=400
            )
    else:
        st.warning("Aggiungi lamelle dal magazzino per calcolare.")
