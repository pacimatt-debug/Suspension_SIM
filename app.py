import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import os
from solver import SuspensionSolver

st.set_page_config(page_title="Suspension Cloud Lab", layout="wide")
st.title("☁️ Suspension Cloud Lab")

# --- DATABASE TEMPORANEO (SESSION STATE) ---
# Su Cloud Gratis, usiamo la memoria temporanea.
# Per salvare davvero serve scaricare il JSON o collegare un DB esterno.
def init_db():
    return {
        "KTM AER 48 (2024)": {
            "type": "Fork",
            "geometry": {'d_valve': 34.0, 'd_rod': 12.0, 'd_throat': 9.0, 'bleed': 1.5},
            "stacks": {
                "Originale": [
                    {"od": 30.0, "th": 0.15}, {"od": 30.0, "th": 0.15}, 
                    {"od": 28.0, "th": 0.15}, {"od": 26.0, "th": 0.15},
                    {"od": 24.0, "th": 0.15}, {"od": 22.0, "th": 0.10}
                ]
            }
        },
        "Mono WP Linkage": {
            "type": "Shock",
            "geometry": {'d_valve': 50.0, 'd_rod': 18.0, 'd_throat': 15.0, 'bleed': 1.0},
            "stacks": {
                "Base": [{"od": 44.0, "th": 0.20}, {"od": 44.0, "th": 0.20}, {"od": 40.0, "th": 0.20}]
            }
        }
    }

if 'db' not in st.session_state:
    st.session_state['db'] = init_db()
db = st.session_state['db']

# --- SIDEBAR ---
with st.sidebar:
    st.header("Garage Sospensioni")
    selected_susp = st.selectbox("Seleziona Modello", list(db.keys()) + ["Crea Nuova..."])
    
    if selected_susp == "Crea Nuova...":
        new_name = st.text_input("Nome Modello")
        c1, c2 = st.columns(2)
        d_v = c1.number_input("Ø Pistone", 34.0)
        d_r = c2.number_input("Ø Stelo", 12.0)
        if st.button("Crea"):
            db[new_name] = {"type":"Custom", "geometry":{'d_valve':d_v, 'd_rod':d_r, 'd_throat':d_v/3, 'bleed':1.5}, "stacks":{"Base": [{"od":d_v-4, "th":0.15}]}}
            st.rerun()
        current_data = None
    else:
        current_data = db[selected_susp]
    
    st.divider()
    # TASTO EXPORT DATI (Fondamentale per il Cloud)
    st.download_button(
        label="📥 Scarica Database (JSON)",
        data=json.dumps(db, indent=4),
        file_name="suspension_db.json",
        mime="application/json"
    )

# --- MAIN ---
if current_data:
    st.subheader(f"Banco Prova: {selected_susp}")
    geom = current_data['geometry']
    stacks = current_data['stacks']
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.info(f"Geometria: Valvola {geom['d_valve']}mm | Stelo {geom['d_rod']}mm")
        sel_stack = st.selectbox("Configurazione", list(stacks.keys()) + ["Nuova..."])
        
        if sel_stack == "Nuova...":
            new_stack_name = st.text_input("Nome Configurazione", "Modifica")
            base = list(stacks.values())[0]
            if st.button("Aggiungi"):
                stacks[new_stack_name] = base
                st.rerun()
            curr_stack_data = base
        else:
            curr_stack_data = stacks[sel_stack]
            
        # Editor
        df = pd.DataFrame(curr_stack_data)
        edited_df = st.data_editor(df, num_rows="dynamic", column_config={"od": "Diametro", "th": "Spessore"})
        
        if st.button("💾 Aggiorna Stack"):
            stacks[sel_stack] = edited_df.to_dict('records')
            st.success("Aggiornato in memoria!")

    with col2:
        max_v = st.slider("Velocità Max (m/s)", 1.0, 8.0, 3.0)
        clicker = st.slider("Clicker %", 0, 100, 100)
        
        fig, ax = plt.subplots()
        vels = np.linspace(0, max_v, 50)
        
        # Calcolo Corrente
        solver = SuspensionSolver(geom, edited_df.to_dict('records'))
        forces = [solver.calculate_force(v, clicker) for v in vels]
        ax.plot(vels, forces, 'r-', linewidth=2, label="Attuale")
        
        # Confronti
        confronti = st.multiselect("Confronta con:", [k for k in stacks.keys() if k != sel_stack])
        for conf in confronti:
            s_conf = SuspensionSolver(geom, stacks[conf])
            f_conf = [s_conf.calculate_force(v, clicker) for v in vels]
            ax.plot(vels, f_conf, '--', label=conf)
            
        ax.grid(True, alpha=0.5)
        ax.legend()
        st.pyplot(fig)
        st.caption(f"Rigidezza Pacco: {solver.k_stack:.2f}")
