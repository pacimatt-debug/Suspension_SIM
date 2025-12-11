import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from solver import SuspensionSolver

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Suspension Pro Lab", layout="wide", page_icon="⚙️")
st.title("⚙️ Suspension Pro Lab")

# CSS: Stile pulsanti e messaggi
st.markdown("""<style>
    .stAlert { font-weight: bold; }
    div.stButton > button:first-child { width: 100%; }
</style>""", unsafe_allow_html=True)

# --- DATABASE INIZIALE ---
def init_db():
    return {
        "WP AER 48 (2024) - Stock": {
            "type": "Fork",
            "geometry": {
                'd_valve': 34.0, 'd_rod': 12.0, 'd_clamp': 12.0,
                'r_port': 11.5, 'n_port': 4, 'w_port': 14.0, 'd_throat': 9.0, 
                'bleed': 1.5, 'oil_visc': 16.0, 'oil_density': 870.0
            },
            "stacks": {
                "Base": [{"od": 30.0, "th": 0.15}, {"od": 28.0, "th": 0.15}, {"od": 26.0, "th": 0.15}]
            }
        }
    }

if 'db' not in st.session_state: st.session_state['db'] = init_db()
db = st.session_state['db']

# --- SIDEBAR ---
with st.sidebar:
    st.header("🗄️ Menu")
    mode = st.radio("Seleziona:", ["🛠️ Banco Prova", "➕ Nuova Sospensione"])
    
    st.divider()
    st.subheader("☁️ Backup Drive")
    
    # DOWNLOAD
    st.download_button(
        label="📥 Scarica Database (.json)",
        data=json.dumps(db, indent=4),
        file_name="suspension_backup.json",
        mime="application/json"
    )
    
    # UPLOAD
    upload = st.file_uploader("📤 Carica Database", type=['json'])
    if upload:
        try:
            st.session_state['db'] = json.load(upload)
            st.success("Caricato!")
            st.rerun()
        except:
            st.error("Errore File")

# ==============================================================================
# MODALITÀ 1: NUOVA SOSPENSIONE
# ==============================================================================
if mode == "➕ Nuova Sospensione":
    st.subheader("1. Definizione Hardware")
    
    with st.form("new_hardware"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Nome Modello")
        stype = col2.selectbox("Tipo", ["Fork", "Shock"])
        
        st.markdown("##### 📐 Misure")
        c1, c2, c3 = st.columns(3)
        d_v = c1.number_input("Ø Pistone", 50.0)
        d_r = c2.number_input("Ø Stelo", 18.0)
        d_c = c3.number_input("Ø Clamp", 12.0)

        st.markdown("##### 🕳️ Porte")
        c1, c2, c3, c4 = st.columns(4)
        n_p = c1.number_input("N. Porte", 4)
        r_p = c2.number_input("Raggio Porta", 18.0)
        w_p = c3.number_input("Largh. Arco", 15.0)
        d_t = c4.number_input("Ø Minimo", 10.0)

        st.markdown("##### 💧 Olio")
        c1, c2 = st.columns(2)
        b_l = c1.number_input("Ø Bleed", 1.5)
        o_v = c2.number_input("Viscosità", 15.0)
        
        if st.form_submit_button("💾 Salva"):
            if name:
                db[name] = {
                    "type": stype,
                    "geometry": {
                        'd_valve': d_v, 'd_rod': d_r, 'd_clamp': d_c,
                        'r_port': r_p, 'n_port': n_p, 'w_port': w_p, 'd_throat': d_t,
                        'bleed': b_l, 'oil_visc': o_v, 'oil_density': 870.0
                    },
                    "stacks": {"Base": [{"od": d_v-2, "th": 0.20}]}
                }
                st.success("Salvato!")
                st.session_state['db'] = db

# ==============================================================================
# MODALITÀ 2: BANCO PROVA
# ==============================================================================
else:
    if not db: 
        st.warning("Database vuoto.")
        st.stop()
    
    susp_name = st.selectbox("Hardware", list(db.keys()))
    data = db[susp_name]
    geom = data['geometry']
    stacks = data['stacks']
    
    st.caption(f"Pistone: {geom['d_valve']}mm | Stelo: {geom['d_rod']}mm")
    st.divider()
    
    col_edit, col_plot = st.columns([1, 1.5])
    
    # EDITOR
    with col_edit:
        st.subheader("🛠️ Lamelle")
        s_name = st.selectbox("Configurazione", list(stacks.keys()) + ["+ Nuova..."])
        
        if s_name == "+ Nuova...":
            with st.form("new_stack"):
                new_s = st.text_input("Nome")
                copy_from = st.selectbox("Copia da", list(stacks.keys()))
                if st.form_submit_button("Crea"):
                    db[susp_name]['stacks'][new_s] = stacks[copy_from].copy()
                    st.rerun()
            curr_stack = []
        else:
            curr_stack = stacks[s_name]
            
            edited = st.data_editor(
                pd.DataFrame(curr_stack), 
                num_rows="dynamic", 
                column_config={
                    "od": st.column_config.NumberColumn("Diametro", format="%.1f"), 
                    "th": st.column_config.NumberColumn("Spessore", format="%.2f")
                },
                use_container_width=True
            )
            
            # CONTROLLI
            error = False
            if edited is not None and not edited.empty:
                if edited['od'].max() >= geom['d_valve']:
                    st.error("🚨 Lamella troppo grande!")
                    error = True
            
            if not error:
                if st.button("💾 Salva Modifiche"):
                    db[susp_name]['stacks'][s_name] = edited.to_dict('records')
                    st.toast("Salvato!")

    # GRAFICI
    with col_plot:
        if curr_stack and not error:
            st.subheader("📈 Grafico")
            
            c1, c2 = st.columns(2)
            max_v = c1.slider("Velocità (m/s)", 0.5, 8.0, 3.0)
            clicker = c2.slider("Clicker %", 0, 100, 100)
            
            fig, ax = plt.subplots(figsize=(8, 5))
            vels = np.linspace(0, max_v, 50)
            
            # Solver Attuale
            solver = SuspensionSolver(geom, edited.to_dict('records'))
            forces = [solver.calculate_force(v, clicker) for v in vels]
            ax.plot(vels, forces, color="#E63946", linewidth=3, label="ATTUALE")
            
            # Confronti
            others = st.multiselect("Confronta", [k for k in stacks.keys() if k != s_name])
            for o in others:
                s_o = SuspensionSolver(geom, stacks[o])
                f_o = [s_o.calculate_force(v, clicker) for v in vels]
                ax.plot(vels, f_o, linestyle="--", label=o)
            
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.set_xlabel("Velocità [m/s]")
            ax.set_ylabel("Forza [kgf]")
            
            st.pyplot(fig)
            st.info(f"Rigidezza: {solver.k_stack:.4e}")
        st.caption(f"Rigidezza Pacco: {solver.k_stack:.2f}")
