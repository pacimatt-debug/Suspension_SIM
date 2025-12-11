import numpy as np
from scipy.optimize import fsolve

class SuspensionSolver:
    def __init__(self, geom_data, shim_stack):
        self.d_valve = geom_data['d_valve'] / 1000.0
        self.d_rod = geom_data['d_rod'] / 1000.0
        self.d_throat = geom_data['d_throat'] / 1000.0
        self.w_port = geom_data.get('w_port', 10.0) / 1000.0
        self.bleed = geom_data['bleed'] / 1000.0
        self.shims = shim_stack
        self.k_stack = self._calculate_stiffness()
        self.A_rod = np.pi * (self.d_rod/2)**2
        self.A_valve = np.pi * (self.d_valve/2)**2
        self.A_annulus = self.A_valve - self.A_rod

    def _calculate_stiffness(self):
        k_total = 0.0
        clamp_d = 12.0 
        for shim in self.shims:
            od = shim['od']
            th = shim['th']
            if od <= clamp_d: continue
            r_ratio = (od - clamp_d) / 2
            if r_ratio <= 0: continue
            k_shim = (th**3) / (r_ratio**2) * 1e7
            k_total += k_shim
        return k_total

    def calculate_force(self, velocity, clicker_openness_percent=100):
        if velocity == 0: return 0
        flow_rate = velocity * self.A_annulus
        rho = 870.0; Cd = 0.7
        eff_bleed_dia = self.bleed * (clicker_openness_percent / 100.0)
        area_bleed = np.pi * (eff_bleed_dia/2)**2

        def pressure_balance(dp):
            if dp <= 0: return -flow_rate
            q_bleed = Cd * area_bleed * np.sqrt(2 * dp / rho)
            f_hyd = dp * (self.A_valve * 0.4) / 9.81
            lift = f_hyd / self.k_stack if self.k_stack > 0 else 0.5
            perimeter = 4 * (self.w_port)
            area_shim = perimeter * (lift / 1000.0)
            max_area = np.pi * (self.d_throat/2)**2
            if area_shim > max_area: area_shim = max_area
            q_stack = Cd * area_shim * np.sqrt(2 * dp / rho)
            return (q_bleed + q_stack) - flow_rate

        try:
            dp_sol = fsolve(pressure_balance, 1e5)[0]
        except:
            dp_sol = 0
        force = dp_sol * self.A_annulus
        return force / 9.81
