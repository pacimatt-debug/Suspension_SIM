import numpy as np
from scipy.optimize import fsolve

class SuspensionSolver:
    def __init__(self, geom, stack_data):
        # --- 1. GEOMETRIA BASE ---
        self.type = geom.get('type', 'Fork')
        self.d_valve = float(geom.get('d_valve', 34.0)) / 1000.0
        self.d_rod = float(geom.get('d_rod', 12.0)) / 1000.0
        self.d_clamp = float(geom.get('d_clamp', 12.0)) / 1000.0
        
        # --- 2. PORTE E FLUSSO ---
        self.n_port = int(geom.get('n_port', 4))
        self.d_throat = float(geom.get('d_throat', 10.0)) / 1000.0
        self.n_throat = int(geom.get('n_throat', 4)) # N.thrt
        self.r_port = float(geom.get('r_port', self.d_valve*0.35)) / 1000.0
        self.w_port = float(geom.get('w_port', self.d_valve*0.4)) / 1000.0
        self.bleed = float(geom.get('bleed', 1.5)) / 1000.0
        self.d_leak = float(geom.get('d_leak', 0.0)) / 1000.0

        # --- 3. PRESSURIZZAZIONE (ICS / BLADDER) ---
        # Pressione base in Pascal (1 bar = 100000 Pa approx per semplicità)
        self.p_zero = float(geom.get('p_zero', 1.5)) * 100000 
        
        # Dati Forcella
        self.l_oil = float(geom.get('l_oil', 0.0)) / 1000.0
        self.l_travel = float(geom.get('l_travel', 300.0)) / 1000.0
        
        # Dati ICS (Closed Cartridge)
        self.k_ics = float(geom.get('k_ics', 0.0)) * 9800 # kg/mm -> N/m (x9.8 x1000)
        self.flt_ics = float(geom.get('flt_ics', 0.0)) / 1000.0
        self.l_ics = float(geom.get('l_ics', 0.0)) / 1000.0
        self.d_ics = float(geom.get('d_ics', 24.0)) / 1000.0
        self.id_ics = float(geom.get('id_ics', 10.0)) / 1000.0
        
        self.rho = float(geom.get('oil_density', 870.0))
        
        # --- 4. STACK & FLOAT ---
        # Se stack_data è una lista (vecchio formato), lo convertiamo
        if isinstance(stack_data, list):
            self.shims = stack_data
            self.h_deck = 0.0
        else:
            self.shims = stack_data.get('shims', [])
            self.h_deck = float(stack_data.get('h_deck', 0.0)) / 1000.0
        
        # Calcolo Aree
        self.A_rod = np.pi * (self.d_rod/2)**2
        self.A_valve = np.pi * (self.d_valve/2)**2
        self.A_active = self.A_valve - self.A_rod # Mid Valve area
        
        self.k_shims = self._calculate_shim_stiffness()

    def _calculate_shim_stiffness(self):
        k_tot = 0.0
        lever = self.r_port - (self.d_clamp / 2.0)
        if lever <= 0: lever = 0.001
        
        for shim in self.shims:
            od = float(shim['od']) / 1000.0
            th = float(shim['th']) / 1000.0
            if (od/2) <= (self.d_clamp/2): continue
            
            r_ratio = (od - self.d_clamp) / 2
            if r_ratio <= 0: continue
            
            # Modello piastra semplificato
            k_s = (210e9 * th**3) / (lever * r_ratio) * 0.15 
            k_tot += k_s
        return k_tot

    def calculate_back_pressure(self):
        """Calcola la pressione statica di base (ICS o Bladder)"""
        # Se Mono (Shock)
        if self.type == "Shock":
            return self.p_zero # Assumiamo pressione costante per il grafico damping
            
        # Se Forcella
        elif self.type == "Fork":
            # Caso 1: Cartuccia Chiusa (ICS) -> Se L.ics > 0
            if self.l_ics > 0 and self.d_ics > 0:
                # Forza Molla ICS iniziale (Preload)
                f_spring = self.k_ics * self.flt_ics
                
                # Area Netta Pistone ICS
                a_ics = np.pi*((self.d_ics/2)**2 - (self.id_ics/2)**2)
                if a_ics <= 0: return self.p_zero
                
                p_ics_mech = f_spring / a_ics
                return self.p_zero + p_ics_mech
            
            # Caso 2: Cartuccia Aperta (Open)
            else:
                return self.p_zero # Solo pressione aria statica
        
        return 0.0

    def calculate_force(self, v, clicker_pct=100):
        if v == 0: return 0
        
        Q_target = v * self.A_active
        Cd = 0.7
        
        # Aree Bypass (Bleed + Leak)
        area_clicker = np.pi * ((self.bleed * clicker_pct/100)/2)**2
        area_leak = np.pi * (self.d_leak/2)**2
        area_bypass = area_clicker + area_leak
        
        # Forza Gas/Molla che spinge sull'asta (Back Pressure)
        p_back = self.calculate_back_pressure()
        f_rod_gas = p_back * self.A_rod

        def pressure_eq(dp):
            if dp <= 0: return -Q_target
            
            # 1. Flusso Bypass
            q_bypass_flow = Cd * area_bypass * np.sqrt(2 * dp / self.rho)
            
            # 2. Flusso Valvola Main
            area_force = self.n_port * (self.w_port * (self.r_port - self.d_clamp/2))
            f_hyd = dp * area_force
            
            # Lift = Float + Flessione
            lift = 0.0
            
            # a) Float libero
            if self.h_deck > 0:
                lift += self.h_deck 
            
            # b) Flessione
            if self.k_shims > 1:
                lift += f_hyd / self.k_shims
            elif self.k_shims <= 1 and self.h_deck <= 0:
                lift += 0.005 # Minima apertura se stack nullo
            
            # Area Tenda (Curtain)
            perim = self.n_port * (2*self.w_port + 2*(self.d_valve/2 - self.r_port))
            area_curtain = perim * lift
            
            # Saturazione Gola (N.thrt)
            area_throat = self.n_throat * np.pi * (self.d_throat/2)**2
            
            area_flow = min(area_curtain, area_throat)
            
            q_valve = Cd * area_flow * np.sqrt(2 * dp / self.rho)
            
            return (q_bypass_flow + q_valve) - Q_target

        try:
            dp = fsolve(pressure_eq, 10e5)[0]
        except:
            dp = 0
            
        f_damping = dp * self.A_active
        
        # Forza Totale = Idraulica + Spinta Gas sull'asta
        return (f_damping + f_rod_gas) / 9.81 # kgf
