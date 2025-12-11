import numpy as np
from scipy.optimize import fsolve

class SuspensionSolver:
    def __init__(self, geom, stack_data):
        # --- GEOMETRIA BASE ---
        self.type = geom.get('type', 'Fork')
        self.d_valve = geom.get('d_valve', 34.0) / 1000.0
        self.d_rod = geom.get('d_rod', 12.0) / 1000.0
        self.d_clamp = geom.get('d_clamp', 12.0) / 1000.0
        
        # --- PORTE E FLUSSO ---
        self.n_port = int(geom.get('n_port', 4))
        self.d_throat = geom.get('d_throat', 10.0) / 1000.0
        self.n_throat = int(geom.get('n_throat', 4)) # N.thrt
        self.r_port = geom.get('r_port', self.d_valve*0.35) / 1000.0
        self.w_port = geom.get('w_port', self.d_valve*0.4) / 1000.0
        self.bleed = geom.get('bleed', 1.5) / 1000.0
        
        # --- PRESSURIZZAZIONE (ICS / BLADDER) ---
        self.Pzero = geom.get('p_zero', 0.0) * 6894.76 # PSI -> Pascal
        self.Loil = geom.get('l_oil', 0.0) / 1000.0
        self.Ltravel = geom.get('l_travel', 300.0) / 1000.0
        
        # ICS Specifics
        self.k_ics = geom.get('k_ics', 0.0) * 1000 # kg/mm -> N/m (approx x9.81 ma ReStackor usa unità miste, qui standardizziamo N/m)
        self.flt_ics = geom.get('flt_ics', 0.0) / 1000.0
        self.l_ics = geom.get('l_ics', 0.0) / 1000.0
        self.d_ics = geom.get('d_ics', 0.0) / 1000.0
        self.id_ics = geom.get('id_ics', 0.0) / 1000.0
        
        self.rho = geom.get('oil_density', 870.0)
        
        # --- STACK & FLOAT ---
        self.shims = stack_data.get('shims', [])
        self.h_deck = stack_data.get('h_deck', 0.0) / 1000.0 # Float reale
        
        # Calcolo Aree
        self.A_rod = np.pi * (self.d_rod/2)**2
        self.A_valve = np.pi * (self.d_valve/2)**2
        self.A_active = self.A_valve - self.A_rod # Mid Valve logic
        
        self.k_shims = self._calculate_shim_stiffness()

    def _calculate_shim_stiffness(self):
        k_tot = 0.0
        lever = self.r_port - (self.d_clamp / 2.0)
        if lever <= 0: lever = 0.001
        
        for shim in self.shims:
            od = shim['od'] / 1000.0
            th = shim['th'] / 1000.0
            if (od/2) <= (self.d_clamp/2): continue
            
            r_ratio = (od - self.d_clamp) / 2
            # Modello piastra semplificato
            k_s = (210e9 * th**3) / (lever * r_ratio) * 0.15 
            k_tot += k_s
        return k_tot

    def calculate_back_pressure(self, stroke_mm=0):
        """Calcola la pressione di base (ICS o Gas) in base alla corsa"""
        # Semplificazione statica (a 0mm di corsa o media)
        # Se volessimo dinamica, stroke_mm dovrebbe variare
        
        if self.type == "Shock":
            # Mono: Pressione Gas Serbatoio costante (approx per piccoli spostamenti)
            return self.Pzero # Pascal
            
        elif self.type == "Fork":
            if self.d_ics > 0: # È una cartuccia chiusa (ICS)
                # Forza Molla ICS
                # F_spring = K * (Preload + Compression)
                # Assumiamo compressione iniziale data dal Float ICS
                f_spring = self.k_ics * (self.flt_ics) 
                
                # Area Netta ICS
                a_ics_net = np.pi*((self.d_ics/2)**2 - (self.id_ics/2)**2)
                if a_ics_net <= 0: return self.Pzero
                
                p_spring = f_spring / a_ics_net
                
                if self.l_ics > 0: # Closed Chamber ICS
                    # P_tot = P_gas_initial + P_spring
                    return self.Pzero + p_spring
                else: # Open Chamber ICS
                    # P_tot = P_fork_outer + P_spring
                    # Qui servirebbe calcolo adiabatico aria forcella esterna
                    return self.Pzero + p_spring 
            else:
                # Open Cartridge (Solo aria esterna)
                return self.Pzero

        return 0.0

    def calculate_force(self, v, clicker_pct=100):
        if v == 0: return 0
        
        Q_target = v * self.A_active
        Cd = 0.7
        
        # Aree Bypass
        area_clicker = np.pi * ((self.bleed * clicker_pct/100)/2)**2
        
        # Back Pressure (Forza Gas/Molla che spinge sull'asta)
        p_back = self.calculate_back_pressure()
        f_rod_gas = p_back * self.A_rod

        def pressure_eq(dp):
            if dp <= 0: return -Q_target
            
            # 1. Flusso Bleed
            q_bypass = Cd * area_clicker * np.sqrt(2 * dp / self.rho)
            
            # 2. Flusso Valvola Main
            # Forza Idraulica
            area_force = self.n_port * (self.w_port * (self.r_port - self.d_clamp/2))
            f_hyd = dp * area_force
            
            # Gestione Float (h.deck)
            # Se h.deck > 0, il lift inizia subito. La molla (shims) agisce dopo h.deck
            lift = 0.0
            
            # Fase 1: Float libero
            if self.h_deck > 0:
                # Se c'è float, la pressione spinge ma le lamelle non resistono subito?
                # ReStackor model: h.deck è un gap. 
                lift = self.h_deck # Si apre subito del gap
            
            # Fase 2: Flessione Lamelle
            if self.k_shims > 1:
                shim_flex = f_hyd / self.k_shims
                lift += shim_flex
            
            # Calcolo Area Passaggio (Curtain)
            perim = self.n_port * (2*self.w_port + 2*(self.d_valve/2 - self.r_port))
            area_curtain = perim * lift
            
            # Saturazione Gola (N.thrt)
            # N.thrt definisce quante "gole" limitano il flusso
            area_throat = self.n_throat * np.pi * (self.d_throat/2)**2
            
            area_flow = min(area_curtain, area_throat)
            
            q_valve = Cd * area_flow * np.sqrt(2 * dp / self.rho)
            
            return (q_bypass + q_valve) - Q_target

        try:
            dp = fsolve(pressure_eq, 10e5)[0]
        except:
            dp = 0
            
        f_damping = dp * self.A_active
        
        # La forza totale letta al banco è Damping + Gas Force (su Rod)
        return (f_damping + f_rod_gas) / 9.81
        except:
            dp = 0
            
        return dp * self.A_active / 9.81
