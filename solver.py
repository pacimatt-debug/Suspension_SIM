import numpy as np
from scipy.optimize import fsolve

class SuspensionSolver:
    def __init__(self, geom, stack_data):
        # --- 1. GEOMETRIA BASE ---
        self.d_valve = geom.get('d_valve', 34.0) / 1000.0
        self.d_rod = geom.get('d_rod', 12.0) / 1000.0
        self.d_throat = geom.get('d_throat', 10.0) / 1000.0
        self.bleed = geom.get('bleed', 1.5) / 1000.0
        self.d_leak = geom.get('d_leak', 0.0) / 1000.0 # Leak Jet aggiuntivo
        
        # --- 2. DETTAGLI PORTA & SEDE ---
        self.r_port = geom.get('r_port', self.d_valve*0.35) / 1000.0
        self.w_port = geom.get('w_port', self.d_valve*0.4) / 1000.0
        self.n_port = int(geom.get('n_port', 4))
        self.w_seat = geom.get('w_seat', 1.0) / 1000.0  # Larghezza sede
        self.d_clamp = geom.get('d_clamp', 12.0) / 1000.0
        
        # --- 3. DATI AMBIENTALI & MOLLA ---
        self.P_gas = geom.get('p_gas', 1.5) * 1e5 # Bar -> Pascal (assoluti approx)
        self.k_hsc = geom.get('k_hsc', 0.0) * 1000 # N/mm -> N/m
        self.preload_hsc = geom.get('preload_hsc', 0.0) / 1000.0 # mm -> m
        
        self.rho = geom.get('oil_density', 870.0)
        
        # --- 4. STACK & FLOAT ---
        self.shims = stack_data.get('shims', [])
        self.h_deck = stack_data.get('h_deck', 0.0) / 1000.0 # Float in metri
        
        # Calcolo Aree
        self.A_rod = np.pi * (self.d_rod/2)**2
        self.A_valve = np.pi * (self.d_valve/2)**2
        self.A_active = self.A_valve - self.A_rod # Mid Valve logic
        
        # Calcolo Rigidezza Stack
        self.k_shims = self._calculate_shim_stiffness()

    def _calculate_shim_stiffness(self):
        k_tot = 0.0
        # Braccio di leva effettivo (Centro Porta - Bordo Clamp)
        lever = self.r_port - (self.d_clamp / 2.0)
        if lever <= 0: lever = 0.001
        
        for shim in self.shims:
            od = shim['od'] / 1000.0
            th = shim['th'] / 1000.0
            if (od/2) <= (self.d_clamp/2): continue
            
            # Formula Piastra Circolare (Roark's Formulas semplificata per stack)
            # E (Young) = 210e9 Pa
            # Rigidezza aumenta con spessore^3
            # Diminuisce con (R_ext - R_clamp)^2
            r_ratio = (od - self.d_clamp) / 2
            k_s = (210e9 * th**3) / (lever * r_ratio) * 0.15 # Fattore calibrazione
            k_tot += k_s
            
        return k_tot

    def calculate_force(self, v, clicker_pct=100):
        if v == 0: return 0
        
        Q_target = v * self.A_active
        Cd = 0.7
        
        # Aree di bypass fisse (Clicker + Leak Jet)
        area_clicker = np.pi * ((self.bleed * clicker_pct/100)/2)**2
        area_leak = np.pi * (self.d_leak/2)**2
        area_bypass = area_clicker + area_leak

        def pressure_eq(dp):
            if dp <= 0: return -Q_target
            
            # 1. Flusso Bypass
            q_bypass = Cd * area_bypass * np.sqrt(2 * dp / self.rho)
            
            # 2. Flusso Valvola
            # Forza Idraulica sulla faccia delle lamelle
            # Area efficace = Area Port + (parte del Seat)
            area_force = self.n_port * (self.w_port * (self.r_port - self.d_clamp/2)) # Approx
            f_hyd = dp * area_force
            
            # Lift Totale = Float + (Forza - PrecaricoMolla) / (K_shims + K_molla)
            # Gestione Float (h_deck): è un'apertura gratis iniziale? 
            # In ReStackor h.deck > 0 su MV significa "gap libero".
            
            # Forza che contrasta l'apertura
            f_resist = 0
            # Molla HSC
            f_spring = self.preload_hsc * self.k_hsc
            
            net_force = f_hyd - f_spring
            
            lift = self.h_deck # Parte dal float
            
            if net_force > 0:
                # Rigidezza combinata (Parallelo: Shims + Molla)
                k_tot = self.k_shims + self.k_hsc
                if k_tot > 1:
                    lift += net_force / k_tot
                else:
                    lift += 0.01 # Valvola spalancata senza resistenza
            
            # Calcolo Area di Passaggio (Curtain)
            perim = self.n_port * (2*self.w_port + 2*(self.d_valve/2 - self.r_port)) # Approx perimetro asola
            area_curtain = perim * lift
            
            # Saturazione Gola (Throat)
            area_throat = self.n_port * np.pi * (self.d_throat/2)**2
            area_flow = min(area_curtain, area_throat)
            
            q_valve = Cd * area_flow * np.sqrt(2 * dp / self.rho)
            
            return (q_bypass + q_valve) - Q_target

        try:
            # Check Cavitazione (limite fisico approx)
            # Se la pressione richiesta > P_gas + 1 atm, potrebbe cavitare in estensione
            # Qui risolviamo solo la caduta di pressione (Damping)
            dp = fsolve(pressure_eq, 10e5)[0]
        except:
            dp = 0
            
        return dp * self.A_active / 9.81
