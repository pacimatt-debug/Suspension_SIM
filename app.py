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
    h1 { color: #E63946; }
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
    st.header("🗄️ Menu Principale")
    
    # Navigazione Principale
    page = st.radio("Vai a:", ["🧪 Simulatore (Lamelle)", "🔧 Garage (Hardware)"])
    
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
# PAGINA 1: GARAGE (CREAZIONE E MODIFICA HARDWARE)
# ==============================================================================
if page == "🔧 Garage (Hardware)":
    st.subheader("🔧 Gestione Sospensioni (Pistoni & Geometria)")
    
    if not db:
        action = "Crea Nuova"
    else:
        action = st.radio("Azione:", ["Crea Nuova", "Modifica Esistente"], horizontal=True)

    # DATI DI DEFAULT (Vuoti o Pre-compilati)
    if action == "Modifica Esistente" and db:
        susp_to_edit = st.selectbox("Seleziona Sospensione da Modificare", list(db.keys()))
        current_geo = db[susp_to_edit]['geometry']
        current_type = db[susp_to_edit]['type']
        
        # Valori attuali
        def_name = susp_to_edit
        def_type = 0 if current_type == "Fork" else 1
        def_dv = float(current_geo['d_valve'])
        def_dr = float(current_geo['d_rod'])
        def_dc = float(current_geo.get('d_clamp', 12.0))
        def_np = int(current_geo.get('n_port', 4))
        def_rp = float(current_geo.get('r_port', def_dv*0.35))
        def_wp = float(current_geo.get('w_port', 10.0))
        def_dt = float(current_geo.get('d_throat', 10.0))
        def_bl = float(current_geo.get('bleed', 1.5))
        def_visc = float(current_geo.get('oil_visc', 15.0))
        
        st.info(f"Stai modificando: **{susp_to_edit}**")
        
    else: # Crea Nuova
        susp_to_edit = None
        def_name = ""
        def_type = 0
        def_dv = 50.0; def_dr = 18.0; def_dc = 12.0
        def_np = 4; def_rp = 18.0; def_wp = 15.0; def_dt = 15.0
        def_bl = 1.5; def_visc = 15.0
        st.info("Stai creando una nuova sospensione da zero.")

    # --- FORM DI INSERIMENTO DATI ---
    with st.form("hardware_form"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Nome Modello", value=def_name)
        stype = col2.selectbox("Tipo", ["Fork", "Shock"], index=def_type)
        
        st.markdown("##### 📐 Misure Principali")
        c1, c2, c3 = st.columns(3)
        d_v = c1.number_input("Ø Pistone (mm)", value=def_dv, step=1.0)
        d_r = c2.number_input("Ø Stelo (mm)", value=def_dr, step=1.0)
        d_c = c3.number_input("Ø Clamp/Fulcro (mm)", value=def_dc, step=1.0, help="Diametro della rondella su cui piega la lamella")

        st.markdown("##### 🕳️ Porte e Flusso")
        c1, c2, c3, c4 = st.columns(4)
        n_p = c1.number_input("N. Porte", value=def_np, step=1)
        r_p = c2.number_input("Raggio Porta (mm)", value=def_rp, step=0.1, help="Distanza dal centro pistone al centro asola")
        w_p = c3.number_input("Largh. Arco (mm)", value=def_wp, step=0.1, help="Lunghezza della banana/asola")
        d_t = c4.number_input("Ø Minimo (Throat) (mm)", value=def_dt, step=0.1)

        st.markdown("##### 💧 Olio")
        c1, c2 = st.columns(2)
        b_l = c1.number_input("Ø Bleed (mm)", value=def_bl, step=0.1)
        o_v = c2.number_input("Viscosità (cSt)", value=def_visc, step=1.0)
        
        # LOGICA SALVATAGGIO
        if st.form_submit_button("💾 SALVA HARDWARE"):
            if not name:
                st.error("Devi dare un nome alla sospensione!")
            else:
                # Se stiamo modificando e il nome è cambiato, cancelliamo il vecchio
                if action == "Modifica Esistente" and name != susp_to_edit:
                    del db[susp_to_edit] # Rinomina (sposta i dati)
                    # Mantieni gli stack vecchi se esistono
                    old_stacks = db.get(susp_to_edit, {}).get('stacks', {})
                elif action == "Modifica Esistente":
                     old_stacks = db[susp_to_edit]['stacks']
                else:
                    # Nuova creazione
                    old_stacks = {"Base": [{"od": d_v-2, "th": 0.20}]}

                # Aggiorna Database
                db[name] = {
                    "type": stype,
                    "geometry": {
                        'd_valve': d_v, 'd_rod': d_r, 'd_clamp': d_c,
                        'r_port': r_p, 'n_port': n_p, 'w_port': w_p, 'd_throat': d_t,
                        'bleed': b_l, 'oil_visc': o_v, 'oil_density': 870.0
                    },
                    "stacks": old_stacks
                }
                st.session_state['db'] = db
                st.success(f"Hardware '{name}' salvato con successo!")
                # Non fare rerun qui per lasciare vedere il messaggio, l'utente cambierà pagina

# ==============================================================================
# PAGINA 2: SIMULATORE (BANCO PROVA)
# ==============================================================================
elif page == "🧪 Simulatore (Lamelle)":
    
    if not db: 
        st.warning("Il Garage è vuoto! Vai nel menu 'Garage' e crea la tua prima sospensione.")
        st.stop()
    
    # Selezione Hardware
    col_sel, col_info = st.columns([1, 2])
    with col_sel:
        susp_name = st.selectbox("Seleziona Sospensione:", list(db.keys()))
    
    data = db[susp_name]
    geom = data['geometry']
    stacks = data['stacks']

    with col_info:
        # Mini dashboard dati tecnici
        st.info(f"**{data['type']}** | Pistone: **{geom['d_valve']}mm** | Clamp: **{geom['d_clamp']}mm** | Leva: **{geom.get('r_port',0)}mm**")

    st.divider()
    
    col_edit, col_plot = st.columns([1, 1.5])
    
    # --- EDITOR LAMELLE ---
    with col_edit:
        st.subheader("🛠️ Configurazione Stack")
        s_name = st.selectbox("Stack Attivo", list(stacks.keys()) + ["+ Nuovo Stack..."])
        
        if s_name == "+ Nuovo Stack...":
            with st.form("new_stack_create"):
                new_s = st.text_input("Nome Configurazione")
                copy_from = st.selectbox("Copia da", list(stacks.keys()))
                if st.form_submit_button("Crea Stack"):
                    db[susp_name]['stacks'][new_s] = stacks[copy_from].copy()
                    st.rerun()
            curr_stack = []
        else:
            curr_stack = stacks[s_name]
            
            # Editor Tabellare
            edited = st.data_editor(
                pd.DataFrame(curr_stack), 
                num_rows="dynamic", 
                column_config={
                    "od": st.column_config.NumberColumn("Diametro (mm)", format="%.1f", step=1.0), 
                    "th": st.column_config.NumberColumn("Spessore (mm)", format="%.2f", step=0.05)
                },
                use_container_width=True
            )
            
            # CONTROLLI SICUREZZA
            error = False
            if edited is not None and not edited.empty:
                max_sh = edited['od'].max()
                min_sh = edited['od'].min()
                if max_sh >= geom['d_valve']:
                    st.error(f"🚨 ERRORE: Lamella {max_sh}mm >= Pistone {geom['d_valve']}mm!")
                    error = True
                if min_sh <= geom['d_clamp']:
                    st.warning(f"⚠️ Avviso: Lamella {min_sh}mm <= Clamp {geom['d_clamp']}mm.")
            
            if not error:
                if st.button("💾 Salva Modifiche Stack", use_container_width=True):
                    db[susp_name]['stacks'][s_name] = edited.to_dict('records')
                    st.toast("Modifiche salvate!", icon="✅")

    # --- GRAFICI ---
    with col_plot:
        if curr_stack and not error:
            st.subheader("📈 Analisi Grafica")
            
            c1, c2 = st.columns(2)
            max_v = c1.slider("Velocità Max (m/s)", 0.5, 8.0, 3.0)
            clicker = c2.slider("Clicker Aperto %", 0, 100, 100)
            
            fig, ax = plt.subplots(figsize=(8, 5))
            vels = np.linspace(0, max_v, 50)
            
            # Calcolo Live
            solver = SuspensionSolver(geom, edited.to_dict('records'))
            forces = [solver.calculate_force(v, clicker) for v in vels]
            ax.plot(vels, forces, color="#E63946", linewidth=2.5, label=f"ATTUALE: {s_name}")
            
            # Confronti
            others = st.multiselect("Confronta con:", [k for k in stacks.keys() if k != s_name])
            for o in others:
                s_o = SuspensionSolver(geom, stacks[o])
                f_o = [s_o.calculate_force(v, clicker) for v in vels]
                ax.plot(vels, f_o, linestyle="--", linewidth=1.5, label=o)
            
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.set_xlabel("Velocità Asta [m/s]")
            ax.set_ylabel("Forza Smorzante [kgf]")
            
            st.pyplot(fig)
            st.info(f"Rigidezza Stack: **{solver.k_stack:.4e}**")
