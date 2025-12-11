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
                'r_port': 11.5, 'n_port': 4, 'w_port': 14.0, 'd_throat': 9.0, 'w_seat': 1.0,
                'bleed': 1.5, 'd_leak': 0.0,
                'p_gas': 1.5, 'oil_visc': 16.0, 
                'k_hsc': 0.0, 'preload_hsc': 0.0
            },
            "stacks": {
                "Base": {"shims": [{"od": 30.0, "th": 0.15}, {"od": 28.0, "th": 0.15}], "h_deck": 0.0}
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
    st.subheader("🔧 Definizione Completa Hardware")
    
    act = st.radio("Azione", ["Modifica Esistente", "Crea Nuova"], horizontal=True)
    if act == "Modifica Esistente" and db:
        name = st.selectbox("Scegli Sospensione", list(db.keys()))
        g = db[name]['geometry']
        def_vals = g
    else:
        name = ""; def_vals = {}
    
    with st.form("hard_form"):
        c1, c2 = st.columns(2)
        new_name = c1.text_input("Nome", name)
        stype = c2.selectbox("Tipo", ["Fork", "Shock"])
        
        st.markdown("##### 📐 Geometria Pistone")
        c1, c2, c3, c4 = st.columns(4)
        dv = c1.number_input("Ø Pistone", value=float(def_vals.get('d_valve', 50.0)))
        dr = c2.number_input("Ø Stelo", value=float(def_vals.get('d_rod', 18.0)))
        dc = c3.number_input("Ø Clamp", value=float(def_vals.get('d_clamp', 12.0)))
        ws = c4.number_input("Largh. Sede (w.seat)", value=float(def_vals.get('w_seat', 1.0)), help="Larghezza del bordo di tenuta")

        st.markdown("##### 🕳️ Porte & Flusso")
        c1, c2, c3, c4 = st.columns(4)
        np_ = c1.number_input("N. Porte", value=int(def_vals.get('n_port', 4)))
        rp = c2.number_input("Raggio Porta (r.port)", value=float(def_vals.get('r_port', 18.0)))
        wp = c3.number_input("Largh. Porta (w.port)", value=float(def_vals.get('w_port', 15.0)))
        dt = c4.number_input("Ø Throat (Minimo)", value=float(def_vals.get('d_throat', 15.0)))

        st.markdown("##### ⚙️ Extra & Molla HSC")
        c1, c2, c3, c4 = st.columns(4)
        bl = c1.number_input("Ø Bleed Clicker", value=float(def_vals.get('bleed', 1.5)))
        dl = c2.number_input("Ø Leak Jet (Fisso)", value=float(def_vals.get('d_leak', 0.0)))
        kh = c3.number_input("K Molla (N/mm)", value=float(def_vals.get('k_hsc', 0.0)))
        ph = c4.number_input("Precarico Molla (mm)", value=float(def_vals.get('preload_hsc', 0.0)))

        st.markdown("##### 🌡️ Gas & Olio")
        c1, c2 = st.columns(2)
        pg = c1.number_input("Pressione Gas (Bar)", value=float(def_vals.get('p_gas', 1.5)))
        ov = c2.number_input("Viscosità Olio", value=float(def_vals.get('oil_visc', 15.0)))

        if st.form_submit_button("💾 SALVA"):
            # Compatibilità vecchi stack
            old_stacks = db.get(name, {}).get('stacks', {"Base": {"shims": [{"od": dv-2, "th": 0.2}], "h_deck": 0.0}})
            # Se è nuova o rinominata
            if act == "Crea Nuova" or new_name != name: 
                save_name = new_name
            else: 
                save_name = name
            
            db[save_name] = {
                "type": stype,
                "geometry": {
                    'd_valve': dv, 'd_rod': dr, 'd_clamp': dc, 'w_seat': ws,
                    'n_port': np_, 'r_port': rp, 'w_port': wp, 'd_throat': dt,
                    'bleed': bl, 'd_leak': dl, 'k_hsc': kh, 'preload_hsc': ph,
                    'p_gas': pg, 'oil_visc': ov
                },
                "stacks": old_stacks
            }
            if act == "Modifica Esistente" and new_name != name: del db[name]
            st.session_state['db'] = db
            st.success("Salvato!")

# --- PAGINA SIMULATORE ---
elif page == "🧪 Simulatore (Stack)":
    if not db: st.warning("Crea prima una sospensione!"); st.stop()
    
    name = st.selectbox("Sospensione", list(db.keys()))
    data = db[name]; g = data['geometry']; stacks = data['stacks']
    
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("🛠️ Stack")
        sname = st.selectbox("Config", list(stacks.keys()) + ["+ Nuova"])
        
        # Gestione Nuova/Esistente
        if sname == "+ Nuova":
            nn = st.text_input("Nome"); copy = st.selectbox("Copia da", list(stacks.keys()))
            if st.button("Crea"):
                db[name]['stacks'][nn] = stacks[copy].copy(); st.rerun()
            curr = {"shims": [], "h_deck": 0.0}
        else:
            # Compatibilità retroattiva (se vecchio formato lista)
            if isinstance(stacks[sname], list): 
                stacks[sname] = {"shims": stacks[sname], "h_deck": 0.0}
            curr = stacks[sname]
            
            # 1. FLOAT (h.deck)
            h_deck = st.number_input("Float / Gioco (h.deck) [mm]", value=float(curr.get('h_deck', 0.0)), step=0.05, format="%.2f")
            
            # 2. TABELLA LAMELLE
            df = pd.DataFrame(curr['shims'])
            edited = st.data_editor(df, num_rows="dynamic", column_config={"od":"Diametro","th":"Spessore"}, use_container_width=True)
            
            # BANNER ERRORI
            err = False
            if not edited.empty:
                if edited['od'].max() >= g['d_valve']: st.error("🚨 Lamella > Pistone!"); err = True
            
            if not err and st.button("💾 Salva Stack"):
                db[name]['stacks'][sname] = {"shims": edited.to_dict('records'), "h_deck": h_deck}
                st.toast("Salvato!")

    with c2:
        if not err and not edited.empty:
            st.subheader("📈 Grafico")
            v_max = st.slider("Velocità", 0.5, 8.0, 4.0)
            clk = st.slider("Clicker %", 0, 100, 100)
            
            fig, ax = plt.subplots(figsize=(8,5))
            vv = np.linspace(0, v_max, 50)
            
            # Solver Attuale
            cur_data = {"shims": edited.to_dict('records'), "h_deck": h_deck}
            sol = SuspensionSolver(g, cur_data)
            ff = [sol.calculate_force(v, clk) for v in vv]
            ax.plot(vv, ff, 'r-', linewidth=3, label="ATTUALE")
            
            # Confronti
            others = st.multiselect("Confronta", [k for k in stacks.keys() if k != sname])
            for o in others:
                # Compatibilità
                if isinstance(stacks[o], list): s_data = {"shims": stacks[o], "h_deck": 0.0}
                else: s_data = stacks[o]
                
                sol_o = SuspensionSolver(g, s_data)
                fo = [sol_o.calculate_force(v, clk) for v in vv]
                ax.plot(vv, fo, '--', label=o)
                
            ax.grid(True, alpha=0.3); ax.legend()
            ax.set_xlabel("Velocità [m/s]"); ax.set_ylabel("Forza [kgf]")
            st.pyplot(fig)
            ax.set_xlabel("Velocità Asta [m/s]")
            ax.set_ylabel("Forza Smorzante [kgf]")
            
            st.pyplot(fig)
            st.info(f"Rigidezza Stack: **{solver.k_stack:.4e}**")
