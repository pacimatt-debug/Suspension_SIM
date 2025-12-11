import numpy as np
from scipy.optimize import fsolve

class SuspensionSolver:
    def __init__(self, geom_data, shim_stack):
        # --- 1. DATI GEOMETRICI (Conversioni mm -> metri) ---
        self.d_valve = geom_data['d_valve'] / 1000.0
        self.d_rod = geom_data['d_rod'] / 1000.0
        
        # Geometria Porte (Cruciale per il calcolo della forza)
        self.r_port = geom_data['r_port'] / 1000.0   # Raggio di applicazione forza
        self.w_port = geom_data['w_port'] / 1000.0   # Larghezza arco (lunghezza asola)
        self.n_port = int(geom_data['n_port'])       # Numero di porte
        self.d_clamp = geom_data['d_clamp'] / 1000.0 # Diametro del fulcro (clamp)
        
        # Passaggi Olio
        self.d_throat = geom_data['d_throat'] / 1000.0
        self.bleed = geom_data['bleed'] / 1000.0
        
        # Dati Olio (Default W5 se mancano)
        self.rho = geom_data.get('oil_density', 870.0) 
        self.visc = geom_data.get('oil_visc', 15.0) # cSt (non usato in Bernoulli puro ma utile per estensioni)

        # --- 2. CALCOLO AREE FISSE ---
        self.A_rod = np.pi * (self.d_rod/2)**2
        self.A_valve = np.pi * (self.d_valve/2)**2
        # Area attiva (Mid Valve = Anello, Base Valve = Stelo)
        # Qui assumiamo logica Mid-Valve per default, ma è parametrizzabile
        self.A_piston_active = self.A_valve - self.A_rod 

        # --- 3. INIZIALIZZAZIONE STACK ---
        self.shims = shim_stack
        self.k_stack = self._calculate_stiffness_precise()

    def _calculate_stiffness_precise(self):
        """
        Calcola la rigidezza basandosi sulla Teoria delle Piastre.
        Usa il raggio di applicazione forza (r_port) e il fulcro (d_clamp).
        """
        k_total = 0.0
        
        # Punto di applicazione della forza idraulica (centro della porta)
        load_radius = self.r_port 
        clamp_radius = self.d_clamp / 2.0
        
        # Braccio di leva effettivo
        lever_arm = load_radius - clamp_radius
        if lever_arm <= 0: lever_arm = 0.001 # Evita div by zero
        
        for shim in self.shims:
            od = shim['od'] / 1000.0 # Converti in metri
            th = shim['th'] / 1000.0
            id_shim = 0.006 # Diametro interno standard (es. 6mm o 8mm), ininfluente per la flessione esterna
            
            shim_radius = od / 2.0
            
            # Se la lamella è più piccola del clamp, o non copre i port, non lavora a flessione
            if shim_radius <= clamp_radius: continue
            
            # Modello Cubico Semplificato (Beam Theory su piastra circolare)
            # K = (E * t^3) / (Costante * Leva^2)
            # E (Modulo Young Acciaio) ~ 210 GPa
            E = 210e9 
            
            # Fattore geometrico empirico per piastre anulari (ReStackor approssimazione)
            # Più la lamella è grande rispetto al carico, più è morbida
            geometry_factor = (shim_radius - clamp_radius) / lever_arm
            
            k_shim = (E * th**3) / (lever_arm**2 * geometry_factor) * 0.05 # 0.05 fattore correttivo shape
            
            k_total += k_shim
            
        return k_total

    def calculate_force(self, velocity, clicker_openness_percent=100):
        if velocity == 0: return 0
        
        # Flusso Volumetrico Q [m^3/s]
        flow_rate = velocity * self.A_piston_active
        Cd = 0.7 # Coefficiente di scarico turbolento
        
        # Area Bleed (Clicker)
        eff_bleed_dia = self.bleed * (clicker_openness_percent / 100.0)
        area_bleed = np.pi * (eff_bleed_dia/2)**2

        # Risolutore Pressione (Bernoulli modificato)
        def pressure_balance(dp):
            if dp <= 0: return -flow_rate
            
            # 1. Flusso Bleed (Regime Turbolento)
            q_bleed = Cd * area_bleed * np.sqrt(2 * dp / self.rho)
            
            # 2. Flusso Main Stack
            # Forza idraulica che agisce sulle lamelle
            # La pressione agisce solo sull'area delle porte, non su tutto il pistone!
            area_ports_total = self.n_port * (self.w_port * (self.d_valve/2 - self.d_clamp/2)) # Stima area porte rettangolari
            f_hyd = dp * area_ports_total
            
            # Lift (Apertura) in metri
            if self.k_stack > 1:
                lift = f_hyd / self.k_stack
            else:
                lift = 0.005 # Se stack nullo, apri tutto
            
            # Calcolo Area di Passaggio (Curtain Area)
            # Area = Perimetro Porte * Lift
            port_perimeter = self.n_port * (2 * self.w_port + 2 * (self.d_valve - self.d_clamp)/4) # Perimetro approx
            area_shim_curtain = port_perimeter * lift
            
            # Saturazione: L'olio non può passare più dell'area geometrica dei buchi (Throat)
            area_throat_max = np.pi * (self.d_throat/2)**2 * self.n_port # N tubi
            
            # L'area effettiva è il minimo tra quella generata dal lift e quella fisica del buco
            area_flow_stack = min(area_shim_curtain, area_throat_max)
            
            q_stack = Cd * area_flow_stack * np.sqrt(2 * dp / self.rho)
            
            return (q_bleed + q_stack) - flow_rate

        try:
            dp_sol = fsolve(pressure_balance, 10e5)[0] # Start guess 10 bar
        except:
            dp_sol = 0
        
        # Forza Smorzante = DeltaP * Area Attiva Pistone
        force = dp_sol * self.A_piston_active
        return force / 9.81 # kgf
