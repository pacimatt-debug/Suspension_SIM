import numpy as np
import pandas as pd
from scipy.optimize import fsolve

class SuspensionSolver:
    def __init__(self, geom, stack_data):
        # --- 1. GEOMETRIA & UNITÀ (SI: Metri, Pascal, Newton) ---
        self.d_valve = float(geom.get('d_valve', 34.0)) / 1000.0
        self.d_rod = float(geom.get('d_rod', 12.0)) / 1000.0
        self.d_clamp = float(geom.get('d_clamp', 12.0)) / 1000.0
        
        # Geometria Porte
        self.n_port = int(geom.get('n_port', 4))
        self.d_throat = float(geom.get('d_throat', 10.0)) / 1000.0
        self.n_throat = int(geom.get('n_throat', 4))
        self.r_port = float(geom.get('r_port', 12.0)) / 1000.0 # Raggio applicazione forza
        self.w_port = float(geom.get('w_port', 14.0)) / 1000.0 # Larghezza arco
        self.h_deck = float(geom.get('h_deck', 2.0)) / 1000.0  # Altezza ingresso flusso
        
        self.bleed = float(geom.get('bleed', 1.5)) / 1000.0
        self.d_leak = float(geom.get('d_leak', 0.0)) / 1000.0
        
        # Fisica Fluido
        self.p_zero = float(geom.get('p_zero', 1.5)) * 100000 # Bar -> Pascal
        self.rho = float(geom.get('oil_density', 870.0)) # kg/m^3
        
        # --- 2. STACK LAMELLE ---
        self.shims = stack_data.get('shims', [])
        self.stack_float = float(stack_data.get('stack_float', 0.0)) / 1000.0
        
        # Calcolo Rigidezza (K_stack) usando Roark's Formulas
        self.k_stack_equiv = self._calculate_stiffness()
        
        # Calcolo Aree Idrauliche (Mid Valve = Annulus)
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
            
            # Modello analitico piastra circolare (FEM approx)
            # E = 210 GPa (Acciaio armonico)
            k_shim = (210e9 * th**3 * 0.15) / (lever_arm * r_ratio**1.5) 
            k_tot += k_shim
        return k_tot

    def solve_point(self, v_shaft, clicker_pct=100):
        """
        Risolve l'equilibrio idraulico usando Bernoulli.
        Trova la Pressione (dP) tale che: Flusso_Calcolato(dP) == Flusso_Target(v_shaft)
        """
        if v_shaft == 0: 
            return {"v":0, "force":0, "lift":0, "pressure_bar":0, "area_eff_mm2":0}
        
        # Flusso Target Q [m^3/s] = Velocità * Area Pistone
        Q_target = v_shaft * self.A_piston
        Cd = 0.7 # Coefficiente di scarico (forma orifizio)
        
        # --- AREE GEOMETRICHE FISSE ---
        # 1. Bypass (Clicker + Leak)
        A_bleed = np.pi * ((self.bleed * clicker_pct/100)/2)**2 + np.pi*(self.d_leak/2)**2
        
        # 2. Throat (Gola interna del pistone)
        A_throat = self.n_throat * np.pi * (self.d_throat/2)**2
        
        # 3. Deck (Ingresso porta rettangolare)
        A_deck = self.n_port * (self.w_port * self.h_deck)

        # --- EQUAZIONE DI BERNOULLI DA RISOLVERE ---
        def flow_equilibrium(dp):
            if dp <= 0: return -Q_target
            
            # A. Flusso attraverso Bleed (Sempre aperto)
            # Bernoulli: Q = Cd * A * sqrt(2 * dP / rho)
            Q_bleed = Cd * A_bleed * np.sqrt(2 * dp / self.rho)
            
            # B. Flusso attraverso Main Stack (Variabile)
            # 1. Calcolo Forza Idraulica che spinge le lamelle
            #    F = Pressione * Area_Porta_Esposta
            area_force = self.n_port * (self.w_port * (self.r_port - self.d_clamp/2))
            F_hyd = dp * area_force
            
            # 2. Calcolo Lift (Apertura) in base alla forza
            lift = self.stack_float # Inizia dal gioco libero (Float)
            if self.k_stack_equiv > 100: 
                lift += F_hyd / self.k_stack_equiv
            elif self.stack_float <= 0:
                lift += 0.005 # Minimo spiraglio fisico
            
            # 3. Calcolo Area Tenda (Curtain Area) generata dal Lift
            perimeter = self.n_port * (2*self.w_port + 2*(self.d_valve/2 - self.r_port))
            A_curtain = perimeter * lift
            
            # 4. RESTRIZIONI IN SERIE (Il collo di bottiglia)
            # L'olio deve passare da Deck -> Throat -> Curtain.
            # L'area efficace è dominata dalla più piccola.
            # Formula idraulica: 1/A_eff^2 = 1/A1^2 + 1/A2^2 ...
            
            inv_sq_sum = 0
            if A_deck > 0: inv_sq_sum += 1/(A_deck**2)
            if A_throat > 0: inv_sq_sum += 1/(A_throat**2)
            if A_curtain > 0: inv_sq_sum += 1/(A_curtain**2)
            
            if inv_sq_sum > 0:
                A_effective_main = np.sqrt(1 / inv_sq_sum)
            else:
                A_effective_main = 0
            
            # Bernoulli sul Main Stack
            Q_main = Cd * A_effective_main * np.sqrt(2 * dp / self.rho)
            
            # Residuo (deve essere 0)
            return (Q_bleed + Q_main) - Q_target

        # Risolutore numerico (Trova la dP corretta)
        try:
            # Start guess: 10 bar (1e6 Pa)
            dp_sol = fsolve(flow_equilibrium, 1e6)[0] 
        except:
            dp_sol = 0
            
        # --- CALCOLO OUTPUT FINALI ---
        # Forza Smorzante Idraulica = dP * Area Pistone
        force_damp = dp_sol * self.A_piston
        
        # Forza Back Pressure (Gas/ICS sull'asta)
        force_rod = self.p_zero * self.A_rod
        
        # Ricalcolo Lift finale per visualizzazione
        area_force = self.n_port * (self.w_port * (self.r_port - self.d_clamp/2))
        lift_final = self.stack_float + (dp_sol * area_force / self.k_stack_equiv if self.k_stack_equiv>0 else 0)
        
        # Ricalcolo Area Efficace totale
        total_flow = Q_target
        if dp_sol > 0:
            area_eff_total = total_flow / (Cd * np.sqrt(2*dp_sol/self.rho))
        else:
            area_eff_total = 0

        return {
            "v": v_shaft,
            "force_kg": (force_damp + force_rod) / 9.81, 
            "lift_mm": lift_final * 1000,
            "pressure_bar": dp_sol / 100000,
            "area_eff_mm2": area_eff_total * 1e6
        }
