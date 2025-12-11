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
                'r_port': 11.0, 'w_port': 14.0, 'h_deck': 2.0, # h.deck geometrico
                'bleed': 1.5, 'd_leak': 0.0,
                'k_ics': 2.2, 'flt_ics': 40.0, 'l_ics': 200.0, 'd_ics': 24.0, 'id_ics': 10.0,
                'p_zero': 22.0
            },
            "stacks": {
                "Base": {"shims": [{"od": 30.0, "th": 0.15}], "stack_float": 0.0} # Float lamelle
            }
        }
    }

if 'db' not in st.session_state: st.session_state['db'] = init_db()
db = st.session_state['db']

with st.sidebar:
    st.header("Menu")
    page = st.radio("Vai a:", ["🔧 Garage (Hardware)", "🧪 Simulatore (Analisi)"])
    st.divider()
    st.subheader("💾 Database (Drive)")
    st.info("Scarica il file e salvalo nel tuo Google Drive per non perdere i dati.")
    st.download_button("📥 Scarica JSON", json.dumps(db, indent=4), "suspension_db.json", "application/json")
    up = st.file_uploader("📤 Carica JSON", type=['json'])
    if up: st.session_state['db'] = json.load(up); st.rerun()

# --- GARAGE ---
if page == "🔧 Garage (Hardware)":
    st.subheader("🔧 Definizione Hardware")
    act = st.radio("Azione", ["Modifica Esistente", "Crea Nuova"], horizontal=True)
    
    if act == "Modifica Esistente" and db:
        name = st.selectbox("Scegli Sospensione", list(db.keys()))
        d = db[name]['geometry']
    else: name = ""; d = {}
    
    with st.form("hard_form"):
        c1, c2 = st.columns(2)
        new_name = c1.text_input("Nome Modello", name)
        stype = c2.selectbox("Tipo", ["Fork", "Shock"], index=0 if d.get('type','Fork')=='Fork' else 1)
        
        tab1, tab2, tab3 = st.tabs(["📐 1. Geometria", "🕳️ 2. Porte & Deck", "🔋 3. Pressurizzazione"])
        
        with tab1:
            c1, c2, c3 = st.columns(3)
            dv = c1.number_input("Ø Pistone", value=float(d.get('d_valve', 34.0)))
            dr = c2.number_input("Ø Stelo", value=float(d.get('d_rod', 12.0)))
            dc = c3.number_input("Ø Clamp", value=float(d.get('d_clamp', 12.0)))

        with tab2:
            c1, c2, c3, c4 = st.columns(4)
            np_ = c1.number_input("N. Porte", value=int(d.get('n_port', 4)))
            nt = c2.number_input("N. Gole (N.thrt)", value=int(d.get('n_throat', 4)))
            rp = c3.number_input("Raggio (r.port)", value=float(d.get('r_port', 11.0)))
            wp = c4.number_input("Largh. (w.port)", value=float(d.get('w_port', 14.0)))
            
            c5, c6, c7 = st.columns(3)
            hd = c5.number_input("h.deck (Deck Height) [mm]", value=float(d.get('h_deck', 2.0)), help="Altezza ingresso porta")
            dt = c6.number_input("Ø Throat Minimo", value=float(d.get('d_throat', 9.0)))
            bl = c7.number_input("Ø Bleed", value=float(d.get('bleed', 1.5)))

        with tab3:
            c1, c2, c3 = st.columns(3)
            pz = c1.number_input("P.zero (Gas) [Bar]", value=float(d.get('p_zero', 1.5)))
            kics = c2.number_input("K.ics [kg/mm]", value=float(d.get('k_ics', 0.0)))
            lics = c3.number_input("L.ics [mm]", value=float(d.get('l_ics', 0.0)))
            
            c4, c5, c6 = st.columns(3)
            fics = c4.number_input("Float ICS [mm]", value=float(d.get('flt_ics', 0.0)))
            dics = c5.number_input("Ø Pistone ICS", value=float(d.get('d_ics', 24.0)))
            idics = c6.number_input("Ø Asta ICS", value=float(d.get('id_ics', 10.0)))

        if st.form_submit_button("💾 SALVA"):
            if not new_name: st.error("Manca Nome"); st.stop()
            final_name = new_name if act=="Crea Nuova" else name
            old_stacks = db.get(name, {}).get('stacks', {"Base": {"shims":[{"od":dv-2,"th":0.2}], "stack_float":0.0}})
            
            db[final_name] = {
                "type": stype,
                "geometry": {
                    'd_valve':dv, 'd_rod':dr, 'd_clamp':dc,
                    'n_port':np_, 'n_throat':nt, 'r_port':rp, 'w_port':wp, 'h_deck':hd,
                    'd_throat':dt, 'bleed':bl, 'd_leak':0.0,
                    'p_zero':pz, 'k_ics':kics, 'l_ics':lics, 'flt_ics':fics, 'd_ics':dics, 'id_ics':idics
                },
                "stacks": old_stacks
            }
            if act=="Modifica Esistente" and new_name!=name: del db[name]
            st.session_state['db'] = db
            st.success("Salvato!")

# --- SIMULATORE ---
elif page == "🧪 Simulatore (Analisi)":
    if not db: st.stop()
    name = st.selectbox("Sospensione", list(db.keys()))
    data = db[name]; g = data['geometry']; stacks = data['stacks']
    
    col1, col2 = st.columns([1, 1.5])
    with col1:
        sname = st.selectbox("Config", list(stacks.keys()) + ["+ Nuova"])
        if sname == "+ Nuova":
            nn = st.text_input("Nome"); copy = st.selectbox("Copia", list(stacks.keys()))
            if st.button("Crea"): db[name]['stacks'][nn] = stacks[copy].copy(); st.rerun()
            curr = {"shims":[], "stack_float":0}
        else:
            if isinstance(stacks[sname], list): stacks[sname] = {"shims":stacks[sname], "stack_float":0}
            curr = stacks[sname]
            
            # FLOAT DEL PACCO (Gioco)
            flt = st.number_input("Stack Float (Gioco) [mm]", value=float(curr.get('stack_float', 0.0)), step=0.05)
            
            df = pd.DataFrame(curr['shims'])
            edited = st.data_editor(df, num_rows="dynamic", column_config={"od":"Diametro","th":"Spessore"}, use_container_width=True)
            
            if st.button("💾 Salva Stack"):
                db[name]['stacks'][sname] = {"shims": edited.to_dict('records'), "stack_float": flt}
                st.toast("Salvato!")

    with col2:
        if not edited.empty:
            c1, c2 = st.columns(2)
            max_v = c1.slider("u.wheel [m/s]", 0.5, 8.0, 4.0)
            clk = c2.slider("Clicker %", 0, 100, 100)
            
            fig, ax = plt.subplots(figsize=(8,5))
            vv = np.linspace(0, max_v, 50)
            
            cur_d = {"shims": edited.to_dict('records'), "stack_float": flt}
            g['type'] = data['type']
            
            sol = SuspensionSolver(g, cur_d)
            ff = [sol.calculate_force(v, clk) for v in vv]
            ax.plot(vv, ff, 'r-', linewidth=3, label="ATTUALE")
            
            others = st.multiselect("Confronta", [k for k in stacks.keys() if k != sname])
            for o in others:
                if isinstance(stacks[o], list): s_o = {"shims":stacks[o], "stack_float":0}
                else: s_o = stacks[o]
                sol_o = SuspensionSolver(g, s_o)
                fo = [sol_o.calculate_force(v, clk) for v in vv]
                ax.plot(vv, fo, '--', label=o)
            
            ax.grid(True, alpha=0.3); ax.legend()
            ax.set_xlabel("u.wheel [m/s]"); ax.set_ylabel("Force [kgf]")
            st.pyplot(fig)
            
            bp = sol.calculate_back_pressure() / 100000
            st.caption(f"Back Pressure: **{bp:.2f} bar** | h.deck (Geo): **{g.get('h_deck',0)}mm**")
