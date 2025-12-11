import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from solver import SuspensionSolver

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Suspension Pro Lab", layout="wide", page_icon="⚙️")
st.title("⚙️ Suspension Pro Lab")

# CSS per rendere i messaggi di errore ben visibili
st.markdown("""<style>
    .stAlert { font-weight: bold; }
    div.stButton > button:first-child { width: 100%; }
</style>""", unsafe_allow_html=True)

# --- INIT DATABASE ---
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

# --- SIDEBAR: NAVIGAZIONE E DRIVE ---
with st.sidebar:
    st.header("🗄️ Archivio & Menu")
    mode = st.radio("Seleziona Modalità:", ["🛠️ Banco Prova", "➕ Nuova Sospensione"])
    
    st.divider()
    st.subheader("☁️ Salvataggio Cloud")
    st.info("Scarica il file e salvalo nel tuo Google Drive.")
    
    # TASTO EXPORT (Salvataggio Manuale)
    st.download_button(
        label="📥 Scarica Database (.json)",
        data=json.dumps(db, indent=4),
        file_name="suspension_backup.json",
        mime="application/json"
    )
    
    # TASTO IMPORT
    upload = st.file_uploader("📤 Carica Database", type=['json'])
    if upload:
        try:
            st.session_state['db'] = json.load(upload)
            st.success("Database caricato!")
            st.rerun()
        except:
            st.error("File danneggiato.")

# ==============================================================================
# MODALITÀ 1: CREAZIONE HARDWARE (GEOMETRIA)
# ==============================================================================
if mode == "➕ Nuova Sospensione":
    st.subheader("1. Definizione Hardware")
    st.markdown("Inserisci qui le misure fisse del pistone e dell'asta.")
    
    with st.form("new_hardware"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Nome Modello (es. WP XACT 2025)")
        stype = col2.selectbox("Tipo", ["Fork", "Shock"])
        
        st.markdown("##### 📐 Misure Principali")
        c1, c2, c3 = st.columns(3)
        d_v = c1.number_input("Ø Pistone [mm]", 50.0)
        d_r = c2.number_input("Ø Stelo [mm]", 18.0)
        d_c = c3.number_input("Ø Serraggio (Clamp) [mm]", 12.0)

        st.markdown("##### 🕳️ Porte e Flusso")
        c1, c2, c3, c4 = st.columns(4)
        n_p = c1.number_input("N. Porte", 4, 1, 10)
        r_p = c2.number_input("Raggio Porta [mm]", 18.0)
        w_p = c3.number_input("Largh. Arco [mm]", 15.0)
        d_t = c4.number_input("Ø Minimo (Throat) [mm]", 10.0)

        st.markdown("##### 💧 Olio")
        c1, c2 = st.columns(2)
        b_l = c1.number_input("Ø Bleed [mm]", 1.5)
        o_v = c2.number_input("Viscosità", 15.0)
        
        if st.form_submit_button("💾 Salva Sospensione"):
            if not name:
                st.error("Manca il nome!")
            else:
                db[name] = {
                    "type": stype,
                    "geometry": {
                        'd_valve': d_v, 'd_rod': d_r, 'd_clamp': d_c,
                        'r_port': r_p, 'n_port': n_p, 'w_port': w_p, 'd_throat': d_t,
                        'bleed': b_l, 'oil_visc': o_v, 'oil_density': 870.0
                    },
                    "stacks": {"Base": [{"od": d_v-2, "th": 0.20}]}
                }
                st.success(f"Creato {name}!")
                st.session_state['db'] = db # Forza aggiornamento

# ==============================================================================
# MODALITÀ 2: BANCO PROVA (LAMELLE E GRAFICI)
# ==============================================================================
else:
    if not db: 
        st.warning("Database vuoto. Crea una nuova sospensione.")
        st.stop()
    
    susp_name = st.selectbox("Seleziona Sospensione", list(db.keys()))
    data = db[susp_name]
    geom = data['geometry']
    stacks = data['stacks']
    
    # Info Rapide Hardware
    st.caption(f"Hardware: Pistone {geom['d_valve']}mm | Stelo {geom['d_rod']}mm | Leva {geom.get('r_port',0)}mm")
    st.divider()
    
    col_edit, col_plot = st.columns([1, 1.5])
    
    # --- COLONNA SINISTRA: EDITOR ---
    with col_edit:
        st.subheader("🛠️ Lamelle")
        s_name = st.selectbox("Configurazione", list(stacks.keys()) + ["+ Nuova..."])
        
        if s_name == "+ Nuova...":
            with st.form("new_stack"):
                new_s = st.text_input("Nome Config:"); 
                copy_from = st.selectbox("Copia da", list(stacks.keys()))
                if st.form_submit_button("Crea"):
                    db[susp_name]['stacks'][new_s] = stacks[copy_from].copy()
                    st.rerun()
            curr_stack = []
        else:
            curr_stack = stacks[s_name]
            
            # Editor
            edited = st.data_editor(
                pd.DataFrame(curr_stack), 
                num_rows="dynamic", 
                column_config={
                    "od": st.column_config.NumberColumn("Diametro (mm)", format="%.1f"), 
                    "th": st.column_config.NumberColumn("Spessore (mm)", format="%.2f")
                },
                use_container_width=True
            )
            
            # --- CONTROLLI SICUREZZA (BANNER) ---
            error_found = False
            if edited is not None and not edited.empty:
                max_shim = edited['od'].max()
                min_shim = edited['od'].min()
                
                # 1. Errore Pistone
                if max_shim >= geom['d_valve']:
                    st.error(f"🚨 ERRORE: Lamella {max_shim}mm troppo grande! Il pistone è {geom['d_valve']}mm.")
                    error_found = True
                
                # 2. Avviso Clamp
                if min_shim <= geom.get('d_clamp', 12.0):
                    st.warning(f"⚠️ ATTENZIONE: Lamella {min_shim}mm inutile (minore o uguale al clamp).")

            # Salva solo se non ci sono errori critici
            if not error_found:
                if st.button("💾 Salva Modifiche", use_container_width=True):
                    db[susp_name]['stacks'][s_name] = edited.to_dict('records')
                    st.toast("Salvato!")
            else:
                st.stop() # Blocca il grafico se c'è errore

    # --- COLONNA DESTRA: GRAFICI ---
    with col_plot:
        if curr_stack and not error_found:
            st.subheader("📈 Analisi")
            
            # Controlli
            c1, c2 = st.columns(2)
            max_v = c1.slider("Velocità (m/s)", 0.5, 8.0, 3.0)
            clicker = c2.slider("Clicker %", 0, 100, 100)
            
            # Plot
            fig, ax = plt.subplots(figsize=(8, 5))
            vels = np.linspace(0, max_v, 50)
            
            # Curva Attuale
            solver = SuspensionSolver(geom, edited.to_dict('records'))
            forces = [solver.calculate_force(v, clicker) for v in vels]
            ax.plot(vels, forces, color="#E63946", linewidth=3, label="ATTUALE")
            
            # Confronti
            others = st.multiselect("Confronta con:", [k for k in stacks.keys() if k != s_name])
            for o in others:
                s_o = SuspensionSolver(geom, stacks[o])
                f_o = [s_o.calculate_force(v, clicker) for v in vels]
                ax.plot(vels, f_o, linestyle="--", label=o)
                
            ax.grid(True, alpha=0.3); ax.legend()
            ax.set_xlabel("
            
            st.info(f"Rigidezza Stack: {solver.k_stack:.4e}")
                st.info(f"Rigidezza Pacco Calcolata (Indice): **{solver.k_stack:.2f}**")
        ax.legend()
        st.pyplot(fig)
        st.caption(f"Rigidezza Pacco: {solver.k_stack:.2f}")
