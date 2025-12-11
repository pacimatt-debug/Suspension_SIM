import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import io
from solver import SuspensionSolver

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Suspension Cloud Pro", layout="wide", page_icon="☁️")
st.markdown("""<style>
    .stAlert { font-weight: bold; }
    div.stButton > button:first-child { width: 100%; font-weight: bold; }
    h1 { color: #E63946; }
</style>""", unsafe_allow_html=True)

st.title("☁️ Suspension Cloud Pro")

# --- GESTIONE DRIVE (CONNESSIONE DIRETTA CARTELLA) ---
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
    DRIVE_LIBS = True
except ImportError:
    DRIVE_LIBS = False

def get_drive_service():
    if not DRIVE_LIBS or "gcp_service_account" not in st.secrets: return None
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/drive'])
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Errore Auth Google: {e}")
        return None

def load_db():
    folder_id = st.secrets.get("drive_folder_id") # Prende l'ID dai secrets
    service = get_drive_service()
    
    if service and folder_id:
        try:
            # CERCA SOLO NELLA CARTELLA SPECIFICA
            query = f"'{folder_id}' in parents and name='suspension_db.json' and trashed=false"
            results = service.files().list(q=query).execute()
            items = results.get('files', [])
            
            if items:
                file_id = items[0]['id']
                request = service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done: status, done = downloader.next_chunk()
                fh.seek(0)
                st.toast("✅ Database sincronizzato dal Cloud!", icon="☁️")
                return json.load(fh)
            else:
                st.warning("⚠️ File non trovato nella cartella. Al primo salvataggio verrà creato.")
        except Exception as e:
            st.error(f"Errore lettura Drive: {e}")

    # Fallback: DB Vuoto
    return {
        "WP AER 48 (2024)": {
            "type": "Fork",
            "geometry": {
                'd_valve': 34.0, 'd_rod': 12.0, 'd_clamp': 12.0,
                'n_port': 4, 'd_throat': 9.0, 'n_throat': 4,
                'r_port': 11.0, 'w_port': 14.0, 'h_deck': 2.0,
                'bleed': 1.5, 'd_leak': 0.0,
                'p_zero': 22.0, 'k_ics': 2.2, 'flt_ics': 40.0, 'l_ics': 200.0, 'd_ics': 24.0, 'id_ics': 10.0
            },
            "stacks": {"Base": {"shims": [{"od": 30.0, "th": 0.15}], "stack_float": 0.0}}
        }
    }

def save_db(db_data):
    st.session_state['db'] = db_data
    folder_id = st.secrets.get("drive_folder_id")
    service = get_drive_service()
    
    if service and folder_id:
        try:
            fh = io.BytesIO(json.dumps(db_data, indent=4).encode('utf-8'))
            media = MediaIoBaseUpload(fh, mimetype='application/json')
            
            # Cerca se esiste GIA' nella cartella
            query = f"'{folder_id}' in parents and name='suspension_db.json' and trashed=false"
            results = service.files().list(q=query).execute()
            items = results.get('files', [])
            
            if not items:
                # Crea NUOVO file DENTRO la cartella specifica
                file_metadata = {
                    'name': 'suspension_db.json',
                    'parents': [folder_id] # <--- QUI STA LA MAGIA
                }
                service.files().create(body=file_metadata, media_body=media).execute()
                st.success(f"File CREATO nella cartella Drive corretta!")
            else:
                # Aggiorna ESISTENTE
                service.files().update(fileId=items[0]['id'], media_body=media).execute()
                st.toast("Salvato su Drive!", icon="✅")
            return True
        except Exception as e:
            st.error(f"Errore Scrittura Drive: {e}")
            return False
    else:
        st.warning("⚠️ Configurazione Drive incompleta (Manca ID cartella nei Secrets). Salvataggio solo locale.")
        return False

# --- CARICAMENTO AVVIO ---
if 'db' not in st.session_state:
    st.session_state['db'] = load_db()
db = st.session_state['db']

# --- SIDEBAR ---
with st.sidebar:
    st.header("Menu")
    page = st.radio("Navigazione:", ["🛠️ Simulatore", "➕ Nuova Sospensione", "🔧 Modifica Hardware"])
    st.divider()
    
    # Stato Connessione
    if DRIVE_LIBS and "gcp_service_account" in st.secrets and "drive_folder_id" in st.secrets:
        st.success("🟢 Cloud Attivo")
        if st.button("🔄 Sincronizza Ora"):
            st.session_state['db'] = load_db()
            st.rerun()
    else:
        st.error("🔴 Cloud Disconnesso")
        st.info("Aggiungi 'drive_folder_id' nei secrets.")
        st.download_button("📥 Backup Locale", json.dumps(db, indent=4), "backup.json", "application/json")

# ==============================================================================
# 1. NUOVA SOSPENSIONE
# ==============================================================================
if page == "➕ Nuova Sospensione":
    st.subheader("Crea Nuova")
    with st.form("new_s"):
        c1,c2 = st.columns(2)
        name = c1.text_input("Nome")
        typ = c2.selectbox("Tipo", ["Fork", "Shock"])
        
        c3,c4,c5 = st.columns(3)
        dv = c3.number_input("Ø Pistone", value=50.0 if typ=="Shock" else 34.0)
        dr = c4.number_input("Ø Stelo", value=18.0 if typ=="Shock" else 12.0)
        dc = c5.number_input("Ø Clamp", 12.0)
        
        if st.form_submit_button("Crea e Salva"):
            if not name: st.error("Manca nome")
            else:
                db[name] = {
                    "type": typ,
                    "geometry": {
                        'd_valve': dv, 'd_rod': dr, 'd_clamp': dc,
                        'n_port':4, 'n_throat':4, 'd_throat':dv*0.3, 'r_port':dv*0.35, 'w_port':dv*0.4, 'h_deck':2.0,
                        'bleed':1.5, 'd_leak':0.0, 'p_zero':145.0 if typ=="Shock" else 22.0,
                        'k_ics':0.0, 'l_ics':0.0, 'flt_ics':0.0, 'd_ics':0.0, 'id_ics':0.0
                    },
                    "stacks": {"Base": {"shims": [{"od": dv-2, "th": 0.2}], "stack_float": 0.0}}
                }
                save_db(db)
                st.success("Creata!")

# ==============================================================================
# 2. MODIFICA HARDWARE
# ==============================================================================
elif page == "🔧 Modifica Hardware":
    if not db: st.warning("Nessun dato"); st.stop()
    target = st.selectbox("Modifica:", list(db.keys()))
    d = db[target]['geometry']
    
    with st.form("edit_h"):
        t1, t2, t3 = st.tabs(["Dimensioni", "Porte", "Gas/ICS"])
        with t1:
            c1,c2,c3 = st.columns(3)
            dv = c1.number_input("Pistone", value=float(d.get('d_valve', 34.0)))
            dr = c2.number_input("Stelo", value=float(d.get('d_rod', 12.0)))
            dc = c3.number_input("Clamp", value=float(d.get('d_clamp', 12.0)))
        with t2:
            c1,c2,c3 = st.columns(3)
            rp = c1.number_input("Raggio Porta", value=float(d.get('r_port', 12.0)))
            wp = c2.number_input("Largh. Porta", value=float(d.get('w_port', 14.0)))
            hd = c3.number_input("h.deck", value=float(d.get('h_deck', 2.0)))
            c4,c5 = st.columns(2)
            np_ = c4.number_input("N. Porte", value=int(d.get('n_port', 4)))
            dt = c5.number_input("Throat", value=float(d.get('d_throat', 9.0)))
        with t3:
            pz = st.number_input("P.Gas/ICS (PSI)", value=float(d.get('p_zero', 22.0)))
            st.caption("Parametri ICS (Solo Forcella)")
            c1,c2 = st.columns(2)
            ki = c1.number_input("K.ics", value=float(d.get('k_ics', 0.0)))
            li = c2.number_input("L.ics", value=float(d.get('l_ics', 0.0)))
            
        if st.form_submit_button("Salva Modifiche"):
            # Aggiorna geometria mantenendo il resto
            db[target]['geometry'].update({
                'd_valve': dv, 'd_rod': dr, 'd_clamp': dc, 'r_port': rp, 'w_port': wp, 
                'h_deck': hd, 'n_port': np_, 'd_throat': dt, 'p_zero': pz, 'k_ics': ki, 'l_ics': li
            })
            save_db(db)
            st.success("Aggiornato!")

# ==============================================================================
# 3. SIMULATORE
# ==============================================================================
elif page == "🛠️ Simulatore":
    if not db: st.stop()
    name = st.selectbox("Sospensione", list(db.keys()))
    data = db[name]; g = data['geometry']; stacks = data['stacks']
    
    c1, c2 = st.columns([1, 1.5])
    with c1:
        sname = st.selectbox("Stack", list(stacks.keys()) + ["+ Nuovo"])
        if sname == "+ Nuovo":
            nn = st.text_input("Nome Stack"); cp = st.selectbox("Copia", list(stacks.keys()))
            if st.button("Crea"): 
                db[name]['stacks'][nn] = stacks[cp].copy(); save_db(db); st.rerun()
            curr = {"shims":[], "stack_float":0.0}
        else:
            if isinstance(stacks[sname], list): stacks[sname] = {"shims":stacks[sname], "stack_float":0.0}
            curr = stacks[sname]
            flt = st.number_input("Float (Gioco)", value=float(curr.get('stack_float', 0.0)), step=0.05)
            edited = st.data_editor(pd.DataFrame(curr['shims']), num_rows="dynamic", column_config={"od":"Diametro","th":"Spessore"}, use_container_width=True)
            
            if st.button("💾 Salva su Drive"):
                db[name]['stacks'][sname] = {"shims": edited.to_dict('records'), "stack_float": flt}
                save_db(db) # Salva e Sincronizza

    with c2:
        if not edited.empty:
            st.subheader("Grafico")
            mx = st.slider("Velocità (m/s)", 0.5, 8.0, 4.0)
            ck = st.slider("Clicker %", 0, 100, 100)
            
            fig, ax = plt.subplots(figsize=(8,5))
            vv = np.linspace(0, mx, 50)
            
            g['type'] = data['type']
            sol = SuspensionSolver(g, {"shims":edited.to_dict('records'), "stack_float":flt})
            ff = [sol.calculate_force(v, ck) for v in vv]
            ax.plot(vv, ff, 'r-', linewidth=3, label="ATTUALE")
            
            others = st.multiselect("Confronta", [k for k in stacks.keys() if k != sname])
            for o in others:
                if isinstance(stacks[o], list): so = {"shims":stacks[o], "stack_float":0}
                else: so = stacks[o]
                sol_o = SuspensionSolver(g, so)
                fo = [sol_o.calculate_force(v, ck) for v in vv]
                ax.plot(vv, fo, '--', label=o)
            
            ax.grid(True, alpha=0.3); ax.legend()
            st.pyplot(fig)
