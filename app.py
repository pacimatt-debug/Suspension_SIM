import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from solver import SuspensionSolver

st.set_page_config(page_title="Suspension Pro Lab", layout="wide", page_icon="⚙️")
st.markdown("""<style>.stAlert {font-weight:bold;} h1 {color:#E63946;}</style>""", unsafe_allow_html=True)
st.title("⚙️ Suspension Pro Lab")

def init_db():
    return {
        "WP AER 48 (2024) - Stock": {
            "type": "Fork",
            "geometry": {
                'd_valve': 34.0, 'd_rod': 12.0, 'd_clamp': 12.0,
                'n_port': 4, 'd_throat': 9.0, 'n_throat': 4,
                'bleed': 1.5, 
                # ICS Data
                'k_ics': 2.2, 'flt_ics': 40.0, 'l_ics': 200.0, 'd_ics': 24.0, 'id_ics': 10.0,
                'p_zero': 22.0 # PSI
            },
            "stacks": {
                "Base": {"shims": [{"od": 30.0, "th": 0.15}], "h_deck": 0.25}
            }
        }
    }

if 'db' not in st.session_state: st.session_state['db'] = init_db()
db = st.session_state['db']

# --- SIDEBAR ---
with st.sidebar:
    st.header("Menu")
    page = st.radio("Vai a:", ["🔧 Garage (Hardware)", "🧪 Simulatore (Stack)"])
    st.divider()
    st.download_button("📥 Backup Dati", json.dumps(db, indent=4), "data.json", "application/json")
    up = st.file_uploader("📤 Ripristina", type=['json'])
    if up: st.session_state['db'] = json.load(up); st.rerun()

# --- PAGINA GARAGE ---
if page == "🔧 Garage (Hardware)":
    st.subheader("🔧 Definizione Hardware")
    
    act = st.radio("Azione", ["Modifica Esistente", "Crea Nuova"], horizontal=True)
    if act == "Modifica Esistente" and db:
        name = st.selectbox("Scegli Sospensione", list(db.keys()))
        d = db[name]['geometry']
    else:
        name = ""; d = {}
    
    with st.form("hard_form"):
        c1, c2 = st.columns(2)
        new_name = c1.text_input("Nome", name)
        stype = c2.selectbox("Tipo", ["Fork", "Shock"])
        
        tab1, tab2, tab3 = st.tabs(["📐 1. Geometria Base", "🕳️ 2. Porte & Flusso", "🔋 3. Pressurizzazione (ICS/Bladder)"])
        
        with tab1:
            c1, c2, c3 = st.columns(3)
            dv = c1.number_input("Ø Pistone", value=float(d.get('d_valve', 34.0)))
            dr = c2.number_input("Ø Stelo", value=float(d.get('d_rod', 12.0)))
            dc = c3.number_input("Ø Clamp", value=float(d.get('d_clamp', 12.0)))

        with tab2:
            c1, c2, c3, c4 = st.columns(4)
            np_ = c1.number_input("N. Porte", value=int(d.get('n_port', 4)))
            nt = c2.number_input("N. Gole (N.thrt)", value=int(d.get('n_throat', 4)), help="Numero di passaggi stretti che limitano il flusso")
            dt = c3.number_input("Ø Throat Minimo", value=float(d.get('d_throat', 9.0)))
            bl = c4.number_input("Ø Bleed Clicker", value=float(d.get('bleed', 1.5)))

        with tab3:
            st.caption("Configura ICS (Fork) o Bladder (Shock)")
            if stype == "Fork":
                c1, c2, c3 = st.columns(3)
                k_ics = c1.number_input("K.ics (Molla ICS) [kg/mm]", value=float(d.get('k_ics', 0.0))) # Input in kg/mm
                l_ics = c2.number_input("L.ics (Lungh. Camera) [mm]", value=float(d.get('l_ics', 0.0)), help="0.0 = Open Chamber, >0 = Closed")
                flt_ics = c3.number_input("FLT.ics (Preload/Float) [mm]", value=float(d.get('flt_ics', 0.0)))
                
                c4, c5, c6 = st.columns(3)
                d_ics = c4.number_input("D.ics (Ø Pistone ICS) [mm]", value=float(d.get('d_ics', 0.0)))
                id_ics = c5.number_input("ID.ics (Ø Asta passante) [mm]", value=float(d.get('id_ics', 0.0)))
                pzero = c6.number_input("Pzero (Press. Iniziale) [PSI]", value=float(d.get('p_zero', 0.0)))
            else:
                pzero = st.number_input("Pzero (Press. Bladder) [PSI]", value=float(d.get('p_zero', 145.0)))
                k_ics=0; l_ics=0; flt_ics=0; d_ics=0; id_ics=0

        if st.form_submit_button("💾 SALVA HARDWARE"):
            if not new_name: st.error("Manca Nome"); st.stop()
            
            # Converti in salvataggio
            final_name = new_name if act=="Crea Nuova" else name
            old_stacks = db.get(name, {}).get('stacks', {"Base": {"shims":[{"od":dv-2,"th":0.2}], "h_deck":0.0}})
            
            db[final_name] = {
                "type": stype,
                "geometry": {
                    'd_valve':dv, 'd_rod':dr, 'd_clamp':dc,
                    'n_port':np_, 'n_throat':nt, 'd_throat':dt, 'bleed':bl,
                    'k_ics': k_ics, 'l_ics': l_ics, 'flt_ics': flt_ics, 'd_ics': d_ics, 'id_ics': id_ics,
                    'p_zero': pzero
                },
                "stacks": old_stacks
            }
            if act=="Modifica Esistente" and new_name!=name: del db[name]
            st.session_state['db'] = db
            st.success("Salvato!")

# --- PAGINA SIMULATORE ---
elif page == "🧪 Simulatore (Stack)":
    if not db: st.stop()
    name = st.selectbox("Sospensione", list(db.keys()))
    data = db[name]; g = data['geometry']; stacks = data['stacks']
    
    col1, col2 = st.columns([1, 1.5])
    with col1:
        sname = st.selectbox("Config", list(stacks.keys()) + ["+ Nuova"])
        if sname == "+ Nuova":
            nn = st.text_input("Nome"); copy = st.selectbox("Copia", list(stacks.keys()))
            if st.button("Crea"): db[name]['stacks'][nn] = stacks[copy].copy(); st.rerun()
            curr = {"shims":[], "h_deck":0}
        else:
            if isinstance(stacks[sname], list): stacks[sname] = {"shims":stacks[sname], "h_deck":0}
            curr = stacks[sname]
            
            # CAMPO h.deck (FLOAT)
            h_deck = st.number_input("h.deck (Float) [mm]", value=float(curr.get('h_deck', 0.0)), step=0.05)
            
            df = pd.DataFrame(curr['shims'])
            edited = st.data_editor(df, num_rows="dynamic", column_config={"od":"Diametro","th":"Spessore"}, use_container_width=True)
            
            if st.button("💾 Salva"):
                db[name]['stacks'][sname] = {"shims": edited.to_dict('records'), "h_deck": h_deck}
                st.toast("Salvato!")

    with col2:
        if not edited.empty:
            c1, c2 = st.columns(2)
            max_v = c1.slider("u.wheel (Max Speed) [m/s]", 0.5, 8.0, 4.0) # Rinominato come richiesto
            clk = c2.slider("Clicker %", 0, 100, 100)
            
            fig, ax = plt.subplots(figsize=(8,5))
            vv = np.linspace(0, max_v, 50)
            
            cur_d = {"shims": edited.to_dict('records'), "h_deck": h_deck}
            # Passiamo anche il TIPO per gestire BackPressure corretta
            g['type'] = data['type'] 
            
            sol = SuspensionSolver(g, cur_d)
            ff = [sol.calculate_force(v, clk) for v in vv]
            ax.plot(vv, ff, 'r-', linewidth=3, label="ATTUALE")
            
            # Confronti
            others = st.multiselect("Confronta", [k for k in stacks.keys() if k != sname])
            for o in others:
                if isinstance(stacks[o], list): s_o = {"shims":stacks[o], "h_deck":0}
                else: s_o = stacks[o]
                sol_o = SuspensionSolver(g, s_o)
                fo = [sol_o.calculate_force(v, clk) for v in vv]
                ax.plot(vv, fo, '--', label=o)
            
            ax.grid(True, alpha=0.3); ax.legend()
            ax.set_xlabel("u.wheel [m/s]"); ax.set_ylabel("F.stack + P.gas [kgf]")
            st.pyplot(fig)
            
            # Info Pressurizzazione
            pb = sol.calculate_back_pressure() / 6894.76
            st.caption(f"Back Pressure stimata (Static): **{pb:.1f} psi**")
