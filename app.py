import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="ReStackor Web", layout="wide", page_icon="🔧")

st.title("🔧 Advanced Suspension Simulation (ReStackor Logic)")
st.markdown("---")

# --- SIDEBAR: CONTESTO GENERALE ---
with st.sidebar:
    st.header("1. Configurazione Globale")
    unit_system = st.selectbox("Sistema Unità", ["Metric (mm, kg, cSt)", "Imperial (in, lbs, SUS)"])
    valvola_type = st.selectbox("Tipo Valvola", ["Base Valve (Compression)", "Mid Valve (Comp/Reb)", "Rebound Valve"])
    
    st.markdown("### 🛢️ Fluido")
    oil_viscosity_40 = st.number_input("Viscosità 40°C (cSt)", value=14.0)
    oil_viscosity_100 = st.number_input("Viscosità 100°C (cSt)", value=5.6)
    oil_temp = st.slider("Temp. Operativa (°C)", 20, 100, 50)
    
    st.markdown("### 🏎️ Veicolo")
    linkage_ratio = st.number_input("Linkage Ratio (Media)", value=1.0, help="Per forcelle è 1.0. Per mono usare la media o caricare curva.")

# --- LAYOUT PRINCIPALE A TAB (FLUSSO OPERATIVO) ---
tab_geom, tab_stack, tab_hous, tab_sim = st.tabs([
    "📐 2. Geometria Valvola", 
    "🥞 3. Shim Stack", 
    "🏠 4. Housing & Pressure", 
    "📈 5. Simulazione"
])

# --- TAB 2: GEOMETRIA VALVOLA (Il cuore idraulico) ---
with tab_geom:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Faccia Pistone")
        # I parametri r.port, d.port non bastano. Serve w.seat per il distacco del flusso.
        r_port = st.number_input("r.port - Raggio baricentro porta (mm)", value=12.0)
        d_port = st.number_input("d.port - Lunghezza arco porta (mm)", value=14.0)
        w_port = st.number_input("w.port - Larghezza porta radiale (mm)", value=6.0)
        w_seat = st.number_input("w.seat - Larghezza tenuta (mm)", value=1.5, help="Fondamentale: determina la forza di apertura iniziale")
    
    with col2:
        st.subheader("Passaggi Interni (Throat)")
        # Qui si definiscono le strozzature che causano cavitazione
        d_thrt = st.number_input("d.thrt - Diametro minimo gola (mm)", value=8.0)
        n_thrt = st.number_input("n.thrt - Numero di porte", value=3, step=1)
        d_leak = st.number_input("d.leak - Bleed fisso/Leakage (mm)", value=0.0, help="Foro sul pistone sempre aperto o tolleranza fascia")
    
    with col3:
        st.subheader("Configurazione Clicker & Bypass")
        # Il clicker non è solo un buco, è un ago con un profilo
        d_bleed = st.number_input("d.bleed - Diametro max bypass (mm)", value=3.0)
        needle_taper = st.selectbox("Profilo Spillo", ["Standard (Linear)", "Fine Taper", "Parabolic", "Custom"])
        clicks_out = st.slider("Click Aperti (da tutto chiuso)", 0, 30, 10)
        
        st.info(f"Area Bypass Calcolata: {np.pi * ((d_bleed/2)**2) * (clicks_out/30):.2f} mm² (Stimata)")

# --- TAB 3: SHIM STACK (Data Editor interattivo) ---
with tab_stack:
    col_s1, col_s2 = st.columns([1, 2])
    
    with col_s1:
        st.subheader("Parametri Stack")
        # Parametri spesso dimenticati ma presenti nel manuale
        d_rod = st.number_input("d.rod - Diametro Asta (mm)", value=12.0, help="Definisce quanto olio sposta la Mid-Valve")
        stack_float = st.number_input("Float / Gioco (mm)", value=0.0, step=0.05, help="Cruciale per Mid-Valve: corsa a vuoto prima di piegare le lamelle")
        h_deck = st.number_input("h.deck / Dish (mm)", value=0.0, help="Concavità del pistone (Precarico negativo)")
        clamp_id = st.number_input("Clamp ID (mm)", value=8.0, help="Diametro della rondella di battuta o dado")

    with col_s2:
        st.subheader("Composizione Lamelle")
        st.caption("Inserisci le lamelle dalla faccia del pistone verso il dado (Clamp)")
        
        # Struttura dati iniziale per l'editor
        default_stack = pd.DataFrame([
            {"Qty": 1, "OD (mm)": 30.0, "ID (mm)": 8.0, "Thick (mm)": 0.15, "Type": "Metric"},
            {"Qty": 1, "OD (mm)": 28.0, "ID (mm)": 8.0, "Thick (mm)": 0.15, "Type": "Metric"},
            {"Qty": 1, "OD (mm)": 26.0, "ID (mm)": 8.0, "Thick (mm)": 0.15, "Type": "Metric"},
            {"Qty": 1, "OD (mm)": 18.0, "ID (mm)": 8.0, "Thick (mm)": 0.15, "Type": "Clamp"},
        ])
        
        # L'editor potente di Streamlit
        edited_stack = st.data_editor(default_stack, num_rows="dynamic", use_container_width=True)
        
        # Qui potremmo inserire la visualizzazione grafica live (matplotlib) dello stack

# --- TAB 4: HOUSING & PRESSIONE (Per calcolo cavitazione) ---
with tab_hous:
    st.markdown("#### Sistema di Compensazione (Reservoir)")
    st.markdown("ReStackor usa questi dati per calcolare se la pressione scende sotto zero (Cavitazione) nella Mid-Valve.")
    
    h_col1, h_col2 = st.columns(2)
    
    with h_col1:
        reservoir_type = st.radio("Tipo Compensazione", ["Bladder (Membrana)", "ICS (Molla Integrata)", "Emulsione (No separatore)"])
        p_gas = st.number_input("Pressione Gas (bar/psi)", value=10.0)
        
    with h_col2:
        if reservoir_type == "Bladder":
            v_res = st.number_input("Volume Serbatoio (cc)", value=100.0)
        elif reservoir_type == "ICS":
            k_ics = st.number_input("K Molla ICS (N/mm)", value=2.0)
            preload_ics = st.number_input("Precarico ICS (mm)", value=5.0)

# --- TAB 5: SIMULAZIONE ---
with tab_sim:
    st.success("Tutti i dati sono pronti per il calcolo.")
    
    sim_col1, sim_col2 = st.columns([1,3])
    with sim_col1:
        v_max = st.slider("Velocità Max Stelo (m/s)", 0.5, 10.0, 4.0)
        n_points = st.number_input("Punti Risoluzione", value=50)
        run_btn = st.button("LANCIA SIMULAZIONE 🚀", type="primary", use_container_width=True)
    
    with sim_col2:
        if run_btn:
            # Qui chiameremo il tuo modulo Python futuro
            # results = calculations.run_restackor_logic(inputs...)
            st.warning("⚠️ Motore di calcolo in costruzione. Visualizzazione dati simulati...")
            
            # Placeholder grafico
            chart_data = pd.DataFrame(
                np.random.randn(20, 3),
                columns=['Forza Totale', 'Base Valve', 'Mid Valve'])
            st.line_chart(chart_data)
            
            st.markdown("""
            **Output previsti dal manuale:**
            - Damping Force vs Velocity
            - Shim Deflection (mm)
            - Pressure Drop (Base vs Mid)
            - Cavitation Limit Check
            """)

# --- FINE UI ---
