import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from solver import SuspensionSolver

st.set_page_config(page_title="Suspension Pro Lab", layout="wide", page_icon="⚙️")
st.title("⚙️ Suspension Pro Lab - Advanced Solver")

# --- CSS per compattezza ---
st.markdown("""<style>
    div[data-testid="stExpander"] div[role="button"] p { font-size: 1.1rem; font-weight: bold; }
</style>""", unsafe_allow_html=True)

# --- INIT DATABASE ---
def init_db():
    return {
        "WP AER 48 (2024) - Stock": {
            "type": "Fork",
            "geometry": {
                'd_valve': 34.0, 'd_rod': 12.0, 
                'r_port': 11.5, 'n_port': 4, 'w_port': 14.0, 'd_throat': 9.0, # Dati avanzati
                'd_clamp': 12.0, 'bleed': 1.5,
                'oil_visc': 16.0, 'oil_density': 870.0
            },
            "stacks": {
                "Base": [{"od": 30.0, "th": 0.15}, {"od": 28.0, "th": 0.15}, {"od": 26.0, "th": 0.15}]
            }
        }
    }

if 'db' not in st.session_state: st.session_state['db'] = init_db()
db = st.session_state['db']

# --- SIDEBAR: NAVIGAZIONE ---
with st.sidebar:
    mode = st.radio("Menu", ["🛠️ Banco Prova", "➕ Nuova Sospensione"])
    st.divider()
    st.download_button("📥 Backup Dati", json.dumps(db, indent=4), "suspension_db.json", "application/json")
    
    upload = st.file_uploader("📤 Ripristina Dati", type=['json'])
    if upload:
        st.session_state['db'] = json.load(upload)
        st.rerun()

# --- MODALITÀ 1: CREAZIONE HARDWARE DETTAGLIATA ---
if mode == "➕ Nuova Sospensione":
    st.subheader("1. Definizione Hardware Completo")
    st.info("Inserisci i dati tecnici dal manuale o dal calibro. Questi dati definiscono la fisica del flusso.")
    
    with st.form("new_hardware"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Nome Modello (es. Mono Showa BFRC)")
        stype = col2.selectbox("Tipo", ["Fork", "Shock"])
        
        st.markdown("### 📐 1. Dimensioni Principali")
        c1, c2, c3 = st.columns(3)
        d_v = c1.number_input("Ø Pistone (D.valve) [mm]", 50.0)
        d_r = c2.number_input("Ø Stelo (D.rod) [mm]", 18.0)
        d_c = c3.number_input("Ø Serraggio (d.clamp) [mm]", 12.0, help="Diametro della rondella/dado che tiene il pacco")

        st.markdown("### 🕳️ 2. Geometria Porte (Valve Ports)")
        c1, c2, c3, c4 = st.columns(4)
        n_p = c1.number_input("N. Porte", 4, 1, 10)
        r_p = c2.number_input("Raggio Porta (r.port) [mm]", 18.0, help="Distanza dal centro pistone al centro asola")
        w_p = c3.number_input("Largh. Arco (w.port) [mm]", 15.0, help="Lunghezza curva dell'asola")
        d_t = c4.number_input("Ø Minimo (Throat) [mm]", 10.0, help="Diametro equivalente del passaggio più stretto")

        st.markdown("### 💧 3. Olio e Bleed")
        c1, c2 = st.columns(2)
        b_l = c1.number_input("Ø Bleed/Clicker [mm]", 1.5)
        o_v = c2.number_input("Viscosità (cSt@40°)", 15.0)
        
        if st.form_submit_button("💾 Salva Hardware"):
            db[name] = {
                "type": stype,
                "geometry": {
                    'd_valve': d_v, 'd_rod': d_r, 'd_clamp': d_c,
                    'r_port': r_p, 'n_port': n_p, 'w_port': w_p, 'd_throat': d_t,
                    'bleed': b_l, 'oil_visc': o_v, 'oil_density': 870.0
                },
                "stacks": {"Default": [{"od": d_v-2, "th": 0.20}]}
            }
            st.success(f"Sospensione {name} salvata!")
            st.session_state['db'] = db

# --- MODALITÀ 2: BANCO PROVA ---
else:
    if not db: st.warning("Database vuoto."); st.stop()
    
    susp_name = st.selectbox("Seleziona Hardware", list(db.keys()))
    data = db[susp_name]
    geom = data['geometry']
    stacks = data['stacks']
    
    # --- VISUALIZZATORE GEOMETRIA ---
    with st.expander("🔍 Dati Tecnici Hardware (Sola Lettura)", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pistone", f"{geom['d_valve']} mm")
        c2.metric("Leva (r.port)", f"{geom['r_port']} mm")
        c3.metric("Perimetro Flusso", f"{geom['n_port']*geom['w_port']:.0f} mm")
        c4.metric("Fulcro (Clamp)", f"{geom['d_clamp']} mm")
        st.caption("*Per modificare questi dati, crea una nuova sospensione.")

    st.divider()
    
    col_edit, col_plot = st.columns([1, 1.5])
    
    with col_edit:
        st.subheader("🛠️ Lamelle")
        s_name = st.selectbox("Configurazione", list(stacks.keys()) + ["+ Nuova..."])
        
        if s_name == "+ Nuova...":
            new_s = st.text_input("Nome:"); copy_from = st.selectbox("Copia da", list(stacks.keys()))
            if st.button("Crea") and new_s:
                db[susp_name]['stacks'][new_s] = stacks[copy_from].copy(); st.rerun()
            curr_stack = []
        else:
            curr_stack = stacks[s_name]
            edited = st.data_editor(
                pd.DataFrame(curr_stack), 
                num_rows="dynamic", 
                column_config={"od": st.column_config.NumberColumn("Diametro (mm)", format="%.1f"), "th": st.column_config.NumberColumn("Spessore (mm)", format="%.2f")}
            )
            if st.button("💾 Salva Modifiche", use_container_width=True):
                db[susp_name]['stacks'][s_name] = edited.to_dict('records')
                st.toast("Salvato!")

    with col_plot:
        if curr_stack:
            st.subheader("📈 Risposta Idraulica")
            max_v = st.slider("Velocità (m/s)", 0.5, 8.0, 3.0)
            clicker = st.slider("Clicker %", 0, 100, 100)
            
            fig, ax = plt.subplots(figsize=(8, 5))
            vels = np.linspace(0, max_v, 50)
            
            # ATTUALE
            solver = SuspensionSolver(geom, edited.to_dict('records'))
            forces = [solver.calculate_force(v, clicker) for v in vels]
            ax.plot(vels, forces, color="#E63946", linewidth=3, label="ATTUALE")
            
            # CONFRONTI
            others = st.multiselect("Confronta", [k for k in stacks.keys() if k != s_name])
            for o in others:
                s_o = SuspensionSolver(geom, stacks[o])
                f_o = [s_o.calculate_force(v, clicker) for v in vels]
                ax.plot(vels, f_o, linestyle="--", label=o)
                
            ax.grid(True, alpha=0.3); ax.legend()
            ax.set_xlabel("Velocità [m/s]"); ax.set_ylabel("Forza [kgf]")
            st.pyplot(fig)
            
            # DATI CALCOLATI
            st.info(f"Rigidezza Stack Reale: **{solver.k_stack:.4e}** (N/m)")
                # Info Tecniche Rapide
                st.info(f"Rigidezza Pacco Calcolata (Indice): **{solver.k_stack:.2f}**")
        ax.legend()
        st.pyplot(fig)
        st.caption(f"Rigidezza Pacco: {solver.k_stack:.2f}")
