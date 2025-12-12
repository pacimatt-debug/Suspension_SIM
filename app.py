import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import io
from scipy.optimize import fsolve

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Suspension Cloud Master", layout="wide", page_icon="☁️")
st.markdown("""<style>
    .stAlert { font-weight: bold; }
    h1 { color: #E63946; }
    div.stButton > button:first-child { width: 100%; font-weight: bold; border-radius: 8px; }
</style>""", unsafe_allow_html=True)

st.title("☁️ Suspension Cloud Master")

# ==============================================================================
# 1. GESTIONE GOOGLE DRIVE (INTEGRATA)
# ==============================================================================
DRIVE_OK = False
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
    
    if "gcp_service_account" in st.secrets and "drive_folder_id" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=['https://www.googleapis.com/auth/drive']
        )
        drive_service = build('drive', 'v3', credentials=creds)
        FOLDER_ID = st.secrets["drive_folder_id"]
        DRIVE_OK = True
except Exception as e:
    st.warning(f"⚠️ Drive disabilitato (Errore o Locale): {e}")

def load_db():
    # 1. Tenta download da Drive
    if DRIVE_OK:
        try:
            q = f"'{FOLDER_ID}' in parents and name='suspension_db.json' and trashed=false"
            res = drive_service.files().list(q=q).execute()
            files = res.get('files', [])
            if files:
                fid = files[0]['id']
                req = drive_service.files().get_media(fileId=fid)
                fh = io.BytesIO()
                dl = MediaIoBaseDownload(fh, req)
                done = False
                while not done: s, done = dl.next_chunk()
                fh.seek(0)
                return json.load(fh)
        except Exception as e:
            st.error(f"Errore lettura Drive: {e}")
    
    # 2. Database Default (Se Drive fallisce o è vuoto)
    return {
        "WP AER 48 (Example)": {
            "type": "Fork",
            "geometry": {
                'd_valve': 34.0, 'd_rod': 12.0, 'd_clamp': 12.0,
                'n_port': 4, 'd_throat': 9.0, 'n_throat': 4,
                'r_port': 11.5, 'w_port': 14.0, 'h_deck': 2.0,
                'bleed': 1.5, 'd_leak': 0.0,
                'p_zero': 22.0, 'k_ics': 2.2, 'flt_ics': 40.0, 'l_ics': 200.0, 'd_ics': 24.0, 'id_ics': 10.0
            },
            "stacks": {"Base": {"shims": [{"id":12, "od":30, "th":0.15}], "stack_float": 0.0}}
        }
    }

def save_db(data):
    st.session_state['db'] = data
    if DRIVE_OK:
        try:
            fh = io.BytesIO(json.dumps(data, indent=4).encode('utf-8'))
            media = MediaIoBaseUpload(fh, mimetype='application/json')
            q = f"'{FOLDER_ID}' in parents and name='suspension_db.json' and trashed=false"
            res = drive_service.files().list(q=q).execute()
            files = res.get('files', [])
            
            if files:
                drive_service.files().update(fileId=files[0]['id'], media_body=media).execute()
            else:
                drive_service.files().create(body={'name':'suspension_db.json', 'parents':[FOLDER_ID]}, media_body=media).execute()
            st.toast("✅ Salvato su Drive!", icon="☁️")
        except Exception as e:
            st.error(f"Errore Scrittura Drive: {e}")
    else:
        st.toast("💾 Salvato in Locale", icon="PC")

# Caricamento Iniziale
if 'db' not in st.session_state:
    st.session_state['db'] = load_db()
db = st.session_state['db']

# ==============================================================================
# 2. IL MOTORE FISICO (BERNOULLI + SERIES RESTRICTION)
# ==============================================================================
class SuspensionSolver:
    def __init__(self, geom, stack_data):
        # Geometria (SI Units)
        self.type = geom.get('type', 'Fork')
        self.d_valve = float(geom.get('d_valve', 34.0)) / 1000.0
        self.d_rod = float(geom.get('d_rod', 12.0)) / 1000.0
        self.d_clamp = float(geom.get('d_clamp', 12.0)) / 1000.0
        
        # Porte
        self.n_port = int(geom.get('n_port', 4))
        self.r_port = float(geom.get('r_port', 12.0)) / 1000.0
        self.w_port = float(geom.get('w_port', 14.0)) / 1000.0
        self.h_deck = float(geom.get('h_deck', 2.0)) / 1000.0
        self.d_throat = float(geom.get('d_throat', 10.0)) / 1000.0
        self.n_throat = int(geom.get('n_throat', 4))
        
        self.bleed = float(geom.get('bleed', 1.5)) / 1000.0
        self.d_leak = float(geom.get('d_leak', 0.0)) / 1000.0
        
        # Pressioni (ICS/Gas)
        self.p_zero = float(geom.get('p_zero', 1.5)) * 100000 
        self.k_ics = float(geom.get('k_ics', 0.0)) * 9800 
        self.flt_ics = float(geom.get('flt_ics', 0.0)) / 1000.0
        self.l_ics = float(geom.get('l_ics', 0.0)) / 1000.0
        self.d_ics = float(geom.get('d_ics', 24.0)) / 1000.0
        self.id_ics = float(geom.get('id_ics', 10.0)) / 1000.0
        self.rho = float(geom.get('oil_density', 870.0))
        
        # Stack
        self.shims = stack_data.get('shims', [])
        self.stack_float = float(stack_data.get('stack_float', 0.0)) / 1000.0
        
        # Calcoli Preliminari
        self.k_stack = self._calc_stiffness()
        self.A_rod = np.pi * (self.d_rod/2)**2
        self.A_valve = np.pi * (self.d_valve/2)**2
        self.A_piston = self.A_valve - self.A_rod 

    def _calc_stiffness(self):
        k_tot = 0.0
        lev = self.r_port - self.d_clamp/2
        if lev <= 0: lev = 0.001
        for s in self.shims:
            od = float(s['od'])/1000; th = float(s['th'])/1000
            if od/2 <= self.d_clamp/2: continue
            r_rat = (od - self.d_clamp)/2
            if r_rat>0: k_tot += (210e9 * th**3 * 0.15) / (lev * r_rat**1.5)
        return k_tot

    def get_back_pressure(self):
        if self.type == "Shock": return self.p_zero
        if self.l_ics > 0 and self.d_ics > 0: # Closed Cartridge
            a_ics = np.pi*((self.d_ics/2)**2 - (self.id_ics/2)**2)
            if a_ics>0: return self.p_zero + (self.k_ics*self.flt_ics)/a_ics
        return self.p_zero

    def solve(self, v, clk=100):
        if v == 0: return {"v":0, "force":0, "lift":0, "pres":0}
        Qt = v * self.A_piston
        Cd = 0.7
        
        # Aree Fisse
        Abyp = np.pi*((self.bleed*clk/100)/2)**2 + np.pi*(self.d_leak/2)**2
        Athr = self.n_throat * np.pi*(self.d_throat/2)**2
        Adck = self.n_port * (self.w_port * self.h_deck)
        
        # Equazione Flusso
        def eq(dp):
            if dp<=0: return -Qt
            Qb = Cd * Abyp * np.sqrt(2*dp/self.rho)
            Fh = dp * self.n_port * (self.w_port * (self.r_port - self.d_clamp/2))
            
            lift = self.stack_float
            if self.k_stack > 10: lift += Fh / self.k_stack
            elif self.stack_float <= 0: lift += 0.005
            
            Acurt = self.n_port * (2*self.w_port)*lift
            Aeff = min(Acurt, Athr, Adck) # Restriction Logic
            
            Qv = Cd * Aeff * np.sqrt(2*dp/self.rho)
            return (Qb + Qv) - Qt
            
        try: dp = fsolve(eq, 10e5)[0]
        except: dp = 0
        
        Pb = self.get_back_pressure()
        return {
            "v": v,
            "force": (dp*self.A_piston + Pb*self.A_rod)/9.81,
            "lift": (self.stack_float + dp * (self.n_port * self.w_port * (self.r_port - self.d_clamp/2)) / self.k_stack) * 1000 if self.k_stack > 10 else 0,
            "pres": dp/100000
        }

# ==============================================================================
# 3. INTERFACCIA GRAFICA COMPLETA
# ==============================================================================

# --- MAGAZZINO DATI ---
INVENTORY = {
    6:  [12, 13, 14, 15, 16, 17, 18, 19, 20],
    8:  [16, 18, 20, 22, 24, 26, 28, 30, 32],
    10: [20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40],
    12: [24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44],
    16: [28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50]
}
THICKNESSES = [0.10, 0.15, 0.20, 0.25, 0.30]

with st.sidebar:
    st.header("🗄️ Menu")
    if DRIVE_OK: st.success("🟢 Drive Connesso")
    else: st.error("🔴 Drive Disconnesso (Mode Locale)")
    
    page = st.radio("Navigazione:", ["🔧 Garage (Hardware)", "🧪 Simulatore (Stack)"])
    
    st.divider()
    # Backup Manuale
    st.download_button("📥 Scarica JSON", json.dumps(db, indent=4), "backup.json")

# --- PAGINA 1: GARAGE (Hardware Creator) ---
if page == "🔧 Garage (Hardware)":
    st.subheader("🔧 Gestione Sospensioni & Geometria")
    
    mode = st.radio("Azione:", ["Modifica Esistente", "Crea Nuova"], horizontal=True)
    
    if mode == "Modifica Esistente" and db:
        target = st.selectbox("Seleziona Sospensione", list(db.keys()))
        d = db[target]['geometry']
        def_name = target
    else:
        target = None
        def_name = ""
        d = {}
    
    with st.form("hardware_form"):
        c1, c2 = st.columns(2)
        new_name = c1.text_input("Nome Modello", def_name)
        stype = c2.selectbox("Tipo", ["Fork", "Shock"], index=0 if d.get('type','Fork')=='Fork' else 1)
        
        # TAB 1: GEOMETRIA BASE
        st.markdown("##### 📐 Dimensioni Principali")
        c1, c2, c3 = st.columns(3)
        dv = c1.number_input("Ø Pistone", value=float(d.get('d_valve', 34.0)))
        dr = c2.number_input("Ø Stelo", value=float(d.get('d_rod', 12.0)))
        dc = c3.number_input("Ø Clamp (Fulcro)", value=float(d.get('d_clamp', 12.0)))
        
        # TAB 2: PORTE E FLUSSO
        st.markdown("##### 🕳️ Porte, Deck & Gola")
        c1, c2, c3 = st.columns(3)
        rp = c1.number_input("r.port (Leva)", value=float(d.get('r_port', 11.5)))
        wp = c2.number_input("w.port (Largh)", value=float(d.get('w_port', 14.0)))
        hd = c3.number_input("h.deck (Ingresso)", value=float(d.get('h_deck', 2.0)))
        
        c4, c5, c6 = st.columns(3)
        np_ = c4.number_input("N. Porte", value=int(d.get('n_port', 4)))
        nt = c5.number_input("N. Gole (Thrt)", value=int(d.get('n_throat', 4)))
        dt = c6.number_input("Ø Throat (Minimo)", value=float(d.get('d_throat', 9.0)))
        
        # TAB 3: EXTRA
        st.markdown("##### 🔋 Pressurizzazione & Extra")
        c1, c2, c3 = st.columns(3)
        pz = c1.number_input("P.zero (Gas/ICS)", value=float(d.get('p_zero', 1.5)))
        bl = c2.number_input("Ø Bleed", value=float(d.get('bleed', 1.5)))
        dl = c3.number_input("Ø Leak Jet", value=float(d.get('d_leak', 0.0)))
        
        if stype == "Fork":
            st.caption("Dati Cartuccia Chiusa (ICS):")
            c1, c2, c3 = st.columns(3)
            ki = c1.number_input("K.ics (kg/mm)", value=float(d.get('k_ics', 0.0)))
            li = c2.number_input("L.ics (mm)", value=float(d.get('l_ics', 0.0)))
            fi = c3.number_input("Float ICS", value=float(d.get('flt_ics', 0.0)))
            c4, c5 = st.columns(2)
            di = c4.number_input("Ø Pistone ICS", value=float(d.get('d_ics', 24.0)))
            ii = c5.number_input("Ø Asta ICS", value=float(d.get('id_ics', 10.0)))
        else:
            ki=0; li=0; fi=0; di=0; ii=0

        if st.form_submit_button("💾 SALVA HARDWARE"):
            if not new_name: st.error("Inserisci un nome!"); st.stop()
            
            final_name = new_name if mode=="Crea Nuova" else target
            prev_stacks = db.get(target, {}).get('stacks', {"Base":{"shims":[],"stack_float":0}}) if target else {"Base":{"shims":[],"stack_float":0}}
            
            db[final_name] = {
                "type": stype,
                "geometry": {
                    'd_valve':dv, 'd_rod':dr, 'd_clamp':dc,
                    'n_port':np_, 'n_throat':nt, 'r_port':rp, 'w_port':wp, 'h_deck':hd, 'd_throat':dt,
                    'bleed':bl, 'd_leak':dl, 'p_zero':pz,
                    'k_ics':ki, 'l_ics':li, 'flt_ics':fi, 'd_ics':di, 'id_ics':ii
                },
                "stacks": prev_stacks
            }
            if mode=="Modifica Esistente" and new_name!=target: del db[target]
            save_db(db)
            st.success("Salvato!")

# --- PAGINA 2: SIMULATORE (STACK & ANALISI) ---
elif page == "🧪 Simulatore (Stack)":
    if not db: st.warning("Crea prima una sospensione!"); st.stop()
    
    col_inv, col_main = st.columns([1, 2])
    
    # --- COLONNA SINISTRA: MAGAZZINO ---
    with col_inv:
        st.subheader("➕ Magazzino")
        sel_id = st.selectbox("ID (mm)", list(INVENTORY.keys()))
        sel_od = st.selectbox("OD (mm)", INVENTORY.get(sel_id, []))
        sel_th = st.selectbox("Th (mm)", THICKNESSES)
        qty = st.number_input("Qtà", 1, 10, 1)
        if st.button("Aggiungi ↓"):
            if 'temp_stack' not in st.session_state: st.session_state['temp_stack'] = []
            for _ in range(qty): st.session_state['temp_stack'].append({"id":sel_id, "od":sel_od, "th":sel_th})
            st.success("Aggiunto!")

    # --- COLONNA DESTRA: EDITOR E ANALISI ---
    with col_main:
        susp_name = st.selectbox("Sospensione Attiva", list(db.keys()))
        data = db[susp_name]; geom = data['geometry']; stacks = data['stacks']
        
        # Gestione Stack
        c1, c2 = st.columns([2, 1])
        sname = c1.selectbox("Configurazione", list(stacks.keys()) + ["+ Nuova..."])
        
        if sname == "+ Nuova...":
            nn = c2.text_input("Nome")
            if c2.button("Crea"): 
                db[susp_name]['stacks'][nn] = {"shims":[], "stack_float":0.0}; st.rerun()
            curr = {"shims":[], "stack_float":0.0}
        else:
            curr = stacks[sname]

        # Sync Temp
        if 'temp_stack' not in st.session_state: st.session_state['temp_stack'] = curr['shims'].copy()
        
        # Editor Tabellare
        st_float = st.number_input("Float / Gioco (mm)", value=float(curr.get('stack_float', 0.0)), step=0.05)
        df_stack = pd.DataFrame(st.session_state['temp_stack'])
        
        edited = st.data_editor(df_stack, num_rows="dynamic", column_config={
            "id": st.column_config.NumberColumn("ID", format="%d"),
            "od": st.column_config.NumberColumn("OD", format="%d"),
            "th": st.column_config.NumberColumn("Th", format="%.2f")
        }, use_container_width=True)
        
        if st.button("💾 Salva Configurazione"):
            db[susp_name]['stacks'][sname] = {"shims": edited.to_dict('records'), "stack_float": st_float}
            st.session_state['temp_stack'] = edited.to_dict('records')
            save_db(db)
        
        st.divider()
        
        # --- ZONA ANALISI ---
        if not edited.empty:
            c1, c2 = st.columns(2)
            max_v = c1.slider("Velocità (m/s)", 0.5, 10.0, 4.0)
            clk = c2.slider("Clicker %", 0, 100, 100)
            
            # Calcolo
            solver = SuspensionSolver(geom, {"shims":edited.to_dict('records'), "stack_float":st_float})
            vv = np.linspace(0, max_v, 20)
            res = [solver.solve(v, clk) for v in vv]
            df_res = pd.DataFrame(res)
            
            t1, t2 = st.tabs(["📈 Grafico", "🔢 Dati Analitici"])
            with t1:
                fig, ax = plt.subplots(figsize=(8,4))
                ax.plot(df_res['v'], df_res['force'], 'r-', linewidth=2, label="Forza")
                ax.grid(True, alpha=0.3); ax.legend()
                ax2 = ax.twinx()
                ax2.plot(df_res['v'], df_res['lift'], 'b--', label="Lift")
                st.pyplot(fig)
            with t2:
                st.dataframe(df_res.style.format("{:.2f}"), use_container_width=True)
