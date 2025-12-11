import numpy as np
from scipy.optimize import fsolve

class SuspensionSolver:
    def __init__(self, geom, stack_data):
        # --- 1. GEOMETRIA BASE ---
        self.type = geom.get('type', 'Fork')
        self.d_valve = float(geom.get('d_valve', 34.0)) / 1000.0
        self.d_rod = float(geom.get('d_rod', 12.0)) / 1000.0
        self.d_clamp = float(geom.get('d_clamp', 12.0)) / 1000.0
        
        # --- 2. PORTE, DECK E FLUSSO ---
        self.n_port = int(geom.get('n_port', 4))
        self.d_throat = float(geom.get('d_throat', 10.0)) / 1000.0
        self.n_throat = int(geom.get('n_throat', 4)) 
        self.r_port = float(geom.get('r_port', self.d_valve*0.35)) / 1000.0
        self.w_port = float(geom.get('w_port', self.d_valve*0.4)) / 1000.0
        
        # CORREZIONE: h.deck è geometria fissa (altezza ingresso porta)
        self.h_deck = float(geom.get('h_deck', 2.0)) / 1000.0 
        
        self.bleed = float(geom.get('bleed', 1.5)) / 1000.0
        self.d_leak = float(geom.get('d_leak', 0.0)) / 1000.0

        # --- 3. PRESSURIZZAZIONE ---
        self.p_zero = float(geom.get('p_zero', 1.5)) * 100000 
        self.k_ics = float(geom.get('k_ics', 0.0)) * 9800 
        self.flt_ics = float(geom.get('flt_ics', 0.0)) / 1000.0
        self.l_ics = float(geom.get('l_ics', 0.0)) / 1000.0
        self.d_ics = float(geom.get('d_ics', 24.0)) / 1000.0
        self.id_ics = float(geom.get('id_ics', 10.0)) / 1000.0
        self.rho = float(geom.get('oil_density', 870.0))
        
        # --- 4. STACK & FLOAT (GIOCO) ---
        if isinstance(stack_data, list):
            self.shims = stack_data
            self.stack_float = 0.0
        else:
            self.shims = stack_data.get('shims', [])
            # CORREZIONE: Questo è il gioco del pacco (ex h.deck nel simulatore)
            self.stack_float = float(stack_data.get('stack_float', 0.0)) / 1000.0
        
        # Aree
        self.A_rod = np.pi * (self.d_rod/2)**2
        self.A_valve = np.pi * (self.d_valve/2)**2
        self.A_active = self.A_valve - self.A_rod
        
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
            k_s = (210e9 * th**3) / (lever * r_ratio) * 0.15 
            k_tot += k_s
        return k_tot

    def calculate_back_pressure(self):
        if self.type == "Shock": return self.p_zero 
        elif self.type == "Fork":
            if self.l_ics > 0 and self.d_ics > 0:
                f_spring = self.k_ics * self.flt_ics
                a_ics = np.pi*((self.d_ics/2)**2 - (self.id_ics/2)**2)
                return self.p_zero + (f_spring / a_ics if a_ics > 0 else 0)
            else: return self.p_zero
        return 0.0

    def calculate_force(self, v, clicker_pct=100):
        if v == 0: return 0
        Q_target = v * self.A_active
        Cd = 0.7
        
        area_clicker = np.pi * ((self.bleed * clicker_pct/100)/2)**2
        area_leak = np.pi * (self.d_leak/2)**2
        area_bypass = area_clicker + area_leak
        
        p_back = self.calculate_back_pressure()
        f_rod_gas = p_back * self.A_rod

        # CALCOLO AREE FISSE DI RESTRIZIONE
        # 1. Throat Area (Gola interna)
        A_throat = self.n_throat * np.pi * (self.d_throat/2)**2
        
        # 2. Deck Area (Ingresso Porta - Parametro h.deck)
        # Area rettangolare equivalente ingresso
        A_deck = self.n_port * (self.w_port * self.h_deck)

        def pressure_eq(dp):
            if dp <= 0: return -Q_target
            
            # Flusso Bypass
            q_bypass = Cd * area_bypass * np.sqrt(2 * dp / self.rho)
            
            # Flusso Main
            # Forza idraulica
            area_force = self.n_port * (self.w_port * (self.r_port - self.d_clamp/2))
            f_hyd = dp * area_force
            
            # Lift = Float (Gioco) + Flessione
            lift = self.stack_float # Inizia dal gioco libero
            
            if self.k_shims > 1:
                lift += f_hyd / self.k_shims
            elif self.k_shims <= 1 and self.stack_float <= 0:
                lift += 0.005 # Minima apertura
            
            # 3. Curtain Area (Tenda variabile)
            perim = self.n_port * (2*self.w_port + 2*(self.d_valve/2 - self.r_port))
            A_curtain = perim * lift
            
            # IL FLUSSO È LIMITATO DALL'AREA PIÙ PICCOLA
            # Se h.deck è piccolo, strozza il flusso anche se le lamelle aprono tanto
            A_effective = min(A_curtain, A_throat, A_deck)
            
            q_valve = Cd * A_effective * np.sqrt(2 * dp / self.rho)
            
            return (q_bypass + q_valve) - Q_target

        try:
            dp = fsolve(pressure_eq, 10e5)[0]
        except:
            dp = 0
            
        return (dp * self.A_active + f_rod_gas) / 9.81
