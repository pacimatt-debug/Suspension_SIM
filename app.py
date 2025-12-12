import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve

# ==============================================================================
# 1. IL MOTORE FISICO (BERNOULLI SOLVER)
# ==============================================================================
class SuspensionSolver:
    def __init__(self, geom, stack_data):
        # --- 1. GEOMETRIA (Metri) ---
        self.d_valve = float(geom.get('d_valve', 34.0)) / 1000.0
        self.d_rod = float(geom.get('d_rod', 12.0)) / 1000.0
        self.d_clamp = float(geom.get('d_clamp', 12.0)) / 1000.0
        
        # Geometria Porte (Restrizioni)
        self.n_port = int(geom.get('n_port', 4))
        self.d_throat = float(geom.get('d_throat', 10.0)) / 1000.0 
        self.n_throat = int(geom.get('n_throat', 4))
        
        self.r_port = float(geom.get('r_port', 12.0)) / 1000.0 
        self.w_port = float(geom.get('w_port', 14.0)) / 1000.0 
        self.h_deck = float(geom.get('h_deck', 2.0)) / 1000.0 # Ingresso flusso
        
        self.bleed = float(geom.get('bleed', 1.5)) / 1000.0
        self.d_leak = float(geom.get('d_leak', 0.0)) / 1000.0
        
        # Fisica Fluido
        self.p_zero = float(geom.get('p_zero', 1.5)) * 100000 
        self.rho = float(geom.get('oil_density', 870.0))
        
        # --- 2. STACK ---
        self.shims = stack_data.get('shims', [])
        self.stack_float = float(stack_data.get('stack_float', 0.0)) / 1000.0
        
        # Rigidezza Stack (Roark)
        self.k_stack_equiv = self._calculate_stiffness()
        
        # Aree Attive
        self.A_rod = np.pi * (self.d_rod/2)**2
        self.A_valve = np.pi * (self.d_valve/2)**2
        self.A_piston = self.A_valve - self.A_rod 

    def _calculate_stiffness(self):
        k_tot = 0.0
        lever_arm = self.r_port - (self.d_clamp / 2.0)
        if lever_arm <= 0: lever_arm = 0.001
        
        for s in self.shims:
            od = float(s['od']) / 1000.0
            th = float(s['th']) / 1000.0
            if od/2 <= self.d_clamp/2: continue 
            
            r_ratio = (od - self.d_clamp) / 2
            if r_ratio <= 0: continue
            
            # Formula cubica spessore (Approx FEM Piastra Circolare)
            k_shim = (210e9 * th**3 * 0.15) / (lever_arm * r_ratio**1.5) 
            k_tot += k_shim
        return k_tot

    def solve_point(self, v_shaft, clicker_pct=100):
        if v_shaft == 0: 
            return {"v":0, "force":0, "lift":0, "pressure":0, "area_open":0}
        
        Q_target = v_shaft * self.A_piston
        Cd = 0.7 
        
        # Aree Fisse
        A_bleed = np.pi * ((self.bleed * clicker_pct/100)/2)**2 + np.pi*(self.d_leak/2)**2
        A_throat = self.n_throat * np.pi * (self.d_throat/2)**2
        A_deck = self.n_port * (self.w_port * self.h_deck)

        # Risolutore Bernoulli
        def flow_eq(dp):
            if dp <= 0: return -Q_target
            
            Q_bleed = Cd * A_bleed * np.sqrt(2 * dp / self.rho)
            
            # Forza sulle lamelle
            area_force = self.n_port * (self.w_port * (self.r_port - self.d_clamp/2))
            F_hyd = dp * area_force
            
            # Lift
            lift = self.stack_float 
            if self.k_stack_equiv > 10: 
                lift += F_hyd / self.k_stack_equiv
            elif self.stack_float <= 0:
                lift += 0.005
            
            # Area Variabile (Curtain)
            perim = self.n_port * (2*self.w_port + 2*(self.d_valve/2 - self.r_port))
            A_curtain = perim * lift
            
            # Restrizioni in Serie (Il minimo vince)
            A_effective = min(A_deck, A_throat, A_curtain)
            
            Q_main = Cd * A_effective * np.sqrt(2 * dp / self.rho)
            return (Q_bleed + Q_main) - Q_target

        try:
            dp_sol = fsolve(flow_eq, 10e5)[0] 
        except:
            dp_sol = 0
            
        force_damp = dp_sol * self.A_piston
        
        # Recalcolo valori display
        area_f = self.n_port * (self.w_port * (self.r_port - self.d_clamp/2))
        lift_final = self.stack_float + (dp_sol * area_f / self.k_stack_equiv if self.k_stack_equiv > 10 else 0)
        
        return {
            "v": v_shaft,
            "force": force_damp / 9.81, 
            "lift_mm": lift_final * 1000,
            "pressure_bar": dp_sol / 100000,
            "area_eff_mm2": (min(A_deck, A_throat, self.n_port*(2*self.w_port + 2*(self.d_valve/2 - self.r_port))*lift_final)) * 1e6
        }

# ==============================================================================
# 2. INTERFACCIA GRAFICA (STREAMLIT)
# ==============================================================================
st.set_page_config(page_title="Suspension Lab", layout="wide", page_icon="🛠️")
st.title("🛠️ Suspension Lab: Analisi e Magazzino")

# MAGAZZINO LAMELLE
INVENTORY = {
    6:  [12, 13, 14, 15, 16, 17, 18, 19, 20],
    8:  [16, 18, 20, 22, 24, 26, 28, 30, 32],
    10: [20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40],
    12: [24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44],
    16: [28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50]
}
THICKNESSES = [0.10, 0.15, 0.20, 0.25, 0.30]

# DB Iniziale
if 'db' not in st.session_state:
    st.session_state['db'] = {
        "WP AER 48 (2024)": {
            "type": "Fork",
            "geometry": {
                'd_valve': 34.0, 'd_rod': 12.0, 'd_clamp': 12.0,
                'n_port': 4, 'd_throat': 9.0, 'n_throat': 4,
                'r_port': 11.5, 'w_port': 14.0, 'h_deck': 2.0, 
                'bleed': 1.5, 'd_leak': 0.0, 'p_zero': 22.0
            },
            "stacks": {"Base": {"shims": [{"id":12, "od":30, "th":0.15}], "stack_float": 0.0}}
        }
    }
db = st.session_state['db']

# --- SIDEBAR ---
with st.sidebar:
    st.header("🗄️ Progetto")
    susp_name = st.selectbox("Sospensione", list(db.keys()))
    curr_susp = db[susp_name]
    geom = curr_susp['geometry']
    
    st.divider()
    st.subheader("➕ Aggiungi Lamelle")
    
    sel_id = st.selectbox("1. ID (mm)", list(INVENTORY.keys()))
    c1, c2 = st.columns(2)
    sel_od = c1.selectbox("2. OD (mm)", INVENTORY.get(sel_id, []))
    sel_th = c2.selectbox("3. Spessore", THICKNESSES)
    qty = st.number_input("Quantità", 1, 10, 1)
    
    if st.button("⬇️ AGGIUNGI ALLO STACK", use_container_width=True):
        if 'temp_stack' not in st.session_state: st.session_state['temp_stack'] = []
        for _ in range(qty):
            st.session_state['temp_stack'].append({"id": sel_id, "od": sel_od, "th": sel_th})
        st.success(f"Aggiunte {qty} lamelle!")

# --- MAIN ---
col_L, col_R = st.columns([1, 1.5])

with col_L:
    st.subheader("🛠️ Composizione Pacco")
    stacks = curr_susp['stacks']
    active_s = st.selectbox("Configurazione", list(stacks.keys()) + ["+ Nuova..."])
    
    if active_s == "+ Nuova...":
        nn = st.text_input("Nome")
        if st.button("Crea"):
            curr_susp['stacks'][nn] = {"shims": [], "stack_float": 0.0}
            st.rerun()
        curr_data = {"shims": [], "stack_float": 0.0}
    else:
        curr_data = stacks[active_s]

    if 'temp_stack' not in st.session_state:
        st.session_state['temp_stack'] = curr_data['shims'].copy()
        
    st_float = st.number_input("Float / Gioco (mm)", value=float(curr_data.get('stack_float', 0.0)), step=0.05)
    
    df_stack = pd.DataFrame(st.session_state['temp_stack'])
    edited = st.data_editor(
        df_stack, 
        num_rows="dynamic",
        column_config={
            "id": st.column_config.NumberColumn("ID", format="%d"),
            "od": st.column_config.NumberColumn("OD", format="%d"),
            "th": st.column_config.NumberColumn("Th", format="%.2f")
        },
        use_container_width=True
    )
    
    if st.button("💾 Salva Configurazione", use_container_width=True):
        curr_susp['stacks'][active_s] = {"shims": edited.to_dict('records'), "stack_float": st_float}
        st.session_state['temp_stack'] = edited.to_dict('records')
        st.toast("Salvato!")

    with st.expander("🔍 Geometria Hardware (Sola Lettura)"):
        st.write(f"**Pistone:** {geom['d_valve']}mm | **h.deck:** {geom.get('h_deck',0)}mm")
        st.write(f"**Throat:** {geom.get('d_throat',0)}mm")

with col_R:
    st.subheader("📊 Analisi Fisica")
    if not edited.empty:
        c1, c2 = st.columns(2)
        max_v = c1.slider("Velocità Max (m/s)", 0.5, 10.0, 4.0)
        clk = c2.slider("Clicker %", 0, 100, 100)
        
        solver = SuspensionSolver(geom, {"shims": edited.to_dict('records'), "stack_float": st_float})
        
        vv = np.linspace(0, max_v, 20)
        results = [solver.solve_point(v, clk) for v in vv]
        df_res = pd.DataFrame(results)
        
        tab1, tab2 = st.tabs(["📈 Curve", "🔢 Dati Analitici"])
        
        with tab1:
            fig, ax1 = plt.subplots(figsize=(8,5))
            ax1.plot(df_res['v'], df_res['force'], 'r-', linewidth=2.5, label="Forza (kgf)")
            ax1.set_xlabel("Velocità (m/s)"); ax1.set_ylabel("Forza (kgf)", color='r')
            ax1.grid(True, alpha=0.3)
            
            ax2 = ax1.twinx()
            ax2.plot(df_res['v'], df_res['pressure_bar'], 'b--', alpha=0.6, label="Pressione (bar)")
            ax2.set_ylabel("Pressione (bar)", color='b')
            st.pyplot(fig)
            
        with tab2:
            st.dataframe(df_res.style.format("{:.2f}"), use_container_width=True)
    else:
        st.warning("Aggiungi lamelle dal magazzino.")
