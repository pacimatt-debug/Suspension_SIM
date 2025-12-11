import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import io
from solver import SuspensionSolver

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Suspension Cloud Lab", layout="wide", page_icon="🔧")

# --- CSS PERSONALIZZATO (Per renderlo più carino) ---
st.markdown("""
    <style>
    .big-font { font-size:20px !important; font-weight: bold; }
    .stButton>button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

st.title("☁️ Suspension Cloud Lab")

# --- GESTIONE DATABASE (Session State) ---
# Al primo avvio, crea un database vuoto o di esempio
def init_db():
    return {
        "Esempio: WP AER 48 (2024)": {
            "type": "Fork",
            "geometry": {'d_valve': 34.0, 'd_rod': 12.0, 'd_throat': 9.0, 'bleed': 1.5},
            "stacks": {
                "Standard": [
                    {"od": 30.0, "th": 0.15}, {"od": 28.0, "th": 0.15}, 
                    {"od": 26.0, "th": 0.15}, {"od": 24.0, "th": 0.15}
                ]
            }
        }
    }

if 'db' not in st.session_state:
    st.session_state['db'] = init_db()
db = st.session_state['db']

# --- SIDEBAR: NAVIGAZIONE ---
with st.sidebar:
    st.header("Menu Principale")
    
    # Due modalità distinte: Lavora su esistente o Crea Nuovo
    app_mode = st.radio("Cosa vuoi fare?", ["🛠️ Banco Prova (Simulazione)", "➕ Aggiungi Nuova Sospensione"])
    
    st.divider()
    
    # EXPORT / IMPORT (Per salvare i dati)
    st.subheader("Archivio Dati")
    # Tasto Scarica
    st.download_button(
        label="📥 Scarica Database (Backup)",
        data=json.dumps(db, indent=4),
        file_name="suspension_db.json",
        mime="application/json"
    )
    # Tasto Carica
    uploaded_file = st.file_uploader("Carica Database Salvato", type=['json'])
    if uploaded_file is not None:
        try:
            loaded_db = json.load(uploaded_file)
            st.session_state['db'] = loaded_db
            st.success("Database caricato!")
            st.rerun()
        except:
            st.error("File non valido.")

# ==============================================================================
# MODALITÀ 1: AGGIUNGI NUOVA SOSPENSIONE (GEOMETRIA)
# ==============================================================================
if app_mode == "➕ Aggiungi Nuova Sospensione":
    st.subheader("Definizione Nuovo Hardware")
    st.info("Qui definisci la geometria fissa della forcella o del mono. Lo fai una volta sola.")
    
    with st.form("new_suspension_form"):
        col1, col2 = st.columns(2)
        
        # Nome e Tipo
        new_name = col1.text_input("Nome Modello (es. Mono YZ250F 2023)")
        susp_type = col2.selectbox("Tipo Sospensione", ["Fork (Forcella)", "Shock (Mono)"])
        
        st.divider()
        st.markdown("##### 📐 Geometria Idraulica")
        
        # Valori suggeriti in base al tipo
        if susp_type == "Fork (Forcella)":
            def_v, def_r, def_t = 34.0, 12.0, 9.0
        else:
            def_v, def_r, def_t = 50.0, 18.0, 15.0
            
        c1, c2, c3, c4 = st.columns(4)
        in_valve = c1.number_input("Ø Pistone (mm)", value=def_v, step=1.0)
        in_rod = c2.number_input("Ø Stelo (mm)", value=def_r, step=1.0)
        in_throat = c3.number_input("Ø Port Minimo (mm)", value=def_t, help="Diametro della strozzatura più piccola della valvola")
        in_bleed = c4.number_input("Ø Bleed/Clicker (mm)", value=1.5, step=0.1)
        
        submitted = st.form_submit_button("💾 Salva nel Garage")
        
        if submitted:
            if new_name == "":
                st.error("Inserisci un nome per la sospensione!")
            elif new_name in db:
                st.error("Esiste già una sospensione con questo nome.")
            else:
                # Crea la struttura nel DB
                db[new_name] = {
                    "type": susp_type,
                    "geometry": {
                        'd_valve': in_valve, 
                        'd_rod': in_rod, 
                        'd_throat': in_throat, 
                        'bleed': in_bleed
                    },
                    "stacks": {
                        "Base": [{"od": in_valve-4, "th": 0.20}] # Stack fittizio di partenza
                    }
                }
                st.success(f"Sospensione '{new_name}' creata! Vai al Banco Prova per modificarla.")
                st.session_state['db'] = db # Forza aggiornamento

# ==============================================================================
# MODALITÀ 2: BANCO PROVA (SIMULAZIONE E STACK)
# ==============================================================================
else: # Banco Prova
    if not db:
        st.warning("Il database è vuoto. Vai su 'Aggiungi Nuova Sospensione' per iniziare.")
    else:
        # 1. SELEZIONE SOSPENSIONE
        selected_susp = st.selectbox("Seleziona Sospensione su cui lavorare:", list(db.keys()))
        current_data = db[selected_susp]
        geom = current_data['geometry']
        stacks = current_data['stacks']
        
        st.divider()
        
        # Layout a due colonne: Editor a Sinistra, Grafici a Destra
        col_editor, col_graph = st.columns([1, 1.5])
        
        # --- COLONNA SINISTRA: EDITOR LAMELLE ---
        with col_editor:
            st.markdown("### 🛠️ Configurazione Lamelle")
            st.caption(f"Hardware: Pistone {geom['d_valve']}mm | Stelo {geom['d_rod']}mm")
            
            # Gestione Stacks (Configurazioni)
            stack_options = list(stacks.keys()) + ["➕ Crea Nuova Configurazione..."]
            selected_stack_key = st.selectbox("Configurazione Attuale:", stack_options)
            
            # Logica per Nuova Configurazione
            if selected_stack_key == "➕ Crea Nuova Configurazione...":
                with st.form("new_stack_form"):
                    new_stack_name = st.text_input("Nome Nuova Configurazione (es. Modifica Soft)")
                    base_stack_name = st.selectbox("Copia da:", list(stacks.keys()))
                    create_btn = st.form_submit_button("Crea")
                    
                    if create_btn and new_stack_name:
                        # Copia i dati e salva
                        db[selected_susp]['stacks'][new_stack_name] = stacks[base_stack_name].copy()
                        st.success(f"Configurazione '{new_stack_name}' creata!")
                        st.rerun() # Ricarica per mostrare la nuova selezione
                
                # Non mostrare l'editor finché non è creata
                current_stack_data = [] 
            else:
                current_stack_data = stacks[selected_stack_key]
                
                # EDITOR TABELLA
                df = pd.DataFrame(current_stack_data)
                edited_df = st.data_editor(
                    df, 
                    num_rows="dynamic",
                    column_config={
                        "od": st.column_config.NumberColumn("Diametro Esterno (mm)", format="%.1f", step=1.0),
                        "th": st.column_config.NumberColumn("Spessore (mm)", format="%.2f", step=0.05),
                    },
                    use_container_width=True
                )
                
                # Tasto Salva Rapido
                if st.button("💾 Salva Modifiche", use_container_width=True):
                    db[selected_susp]['stacks'][selected_stack_key] = edited_df.to_dict('records')
                    st.toast("Modifiche salvate con successo!", icon="✅")

        # --- COLONNA DESTRA: GRAFICI ---
        with col_graph:
            if current_stack_data: # Mostra solo se c'è uno stack selezionato
                st.markdown("### 📈 Analisi Curve")
                
                # Controlli Simulazione
                c1, c2 = st.columns(2)
                max_vel = c1.slider("Velocità Max (m/s)", 0.5, 10.0, 4.0)
                clicker = c2.slider("Apertura Clicker (%)", 0, 100, 100)
                
                # Motore Grafico
                fig, ax = plt.subplots(figsize=(8, 5))
                vels = np.linspace(0, max_vel, 50)
                
                # 1. Calcola e Disegna Curva Attuale
                # Nota: Calcoliamo in tempo reale dalla tabella modificata (edited_df), non dal DB
                current_stack_live = edited_df.to_dict('records')
                solver = SuspensionSolver(geom, current_stack_live)
                forces = [solver.calculate_force(v, clicker) for v in vels]
                
                ax.plot(vels, forces, color="#E63946", linewidth=2.5, label=f"ATTUALE: {selected_stack_key}")
                
                # 2. Confronti
                compare_list = st.multiselect("Confronta con:", [k for k in stacks.keys() if k != selected_stack_key])
                colors = ['#457B9D', '#1D3557', '#A8DADC', '#2A9D8F']
                
                for i, comp_name in enumerate(compare_list):
                    s_conf = SuspensionSolver(geom, stacks[comp_name])
                    f_conf = [s_conf.calculate_force(v, clicker) for v in vels]
                    color = colors[i % len(colors)]
                    ax.plot(vels, f_conf, linestyle="--", linewidth=1.5, color=color, label=comp_name)
                
                # 3. Formattazione Grafico (UNITÀ DI MISURA)
                ax.set_title(f"Forza Smorzante - {selected_susp}", fontsize=12, fontweight='bold')
                ax.set_xlabel("Velocità Asta [m/s]", fontsize=10)   # Unità Asse X
                ax.set_ylabel("Forza [kgf]", fontsize=10)           # Unità Asse Y
                ax.grid(True, which='both', linestyle='--', alpha=0.5)
                ax.legend()
                
                st.pyplot(fig)
                
                # Info Tecniche Rapide
                st.info(f"Rigidezza Pacco Calcolata (Indice): **{solver.k_stack:.2f}**")
        ax.legend()
        st.pyplot(fig)
        st.caption(f"Rigidezza Pacco: {solver.k_stack:.2f}")
