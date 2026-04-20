import sys

filename = r'c:\Users\xhuju\Desktop\billiards-analytics-v1.5\backend\tracking\tracking_engine.py'
with open(filename, 'r', encoding='utf-8') as f:
    content = f.read()

replaces = [
    (
        """        self.COLOR_SAT_REF = {
            "Yellow": 165.0,
            "Blue": 150.0,
            "Red": 155.0,
            "Purple": 140.0,
            "Orange": 165.0,
            "Green": 145.0,
            "Brown": 125.0,
        }
        self.DEFAULT_COLOR_HUE_CENTER = dict(self.COLOR_HUE_CENTER)""",
        """        self.COLOR_SAT_REF = {
            "Yellow": 165.0,
            "Blue": 150.0,
            "Red": 155.0,
            "Purple": 140.0,
            "Orange": 165.0,
            "Green": 145.0,
            "Brown": 125.0,
        }
        self.COLOR_VAL_REF = {
            "Yellow": 220.0,
            "Blue": 200.0,
            "Red": 200.0,
            "Purple": 180.0,
            "Orange": 220.0,
            "Green": 180.0,
            "Brown": 150.0,
        }
        self.DEFAULT_COLOR_HUE_CENTER = dict(self.COLOR_HUE_CENTER)"""
    ),
    (
        """        self.DEFAULT_COLOR_SAT_REF = dict(self.COLOR_SAT_REF)
        self.DEFAULT_COLOR_LAB = {k: v.copy() for k, v in self.COLOR_LAB.items()}""",
        """        self.DEFAULT_COLOR_SAT_REF = dict(self.COLOR_SAT_REF)
        self.DEFAULT_COLOR_VAL_REF = dict(self.COLOR_VAL_REF)
        self.DEFAULT_COLOR_LAB = {k: v.copy() for k, v in self.COLOR_LAB.items()}"""
    ),
    (
        """            self.COLOR_HUE_CENTER[sys_color] = h_center
            self.COLOR_SAT_REF[sys_color] = s_ref

            hsv_pixel = np.uint8([[[int(h_center), int(s_ref), v_ref]]])""",
        """            self.COLOR_HUE_CENTER[sys_color] = h_center
            self.COLOR_SAT_REF[sys_color] = s_ref
            self.COLOR_VAL_REF[sys_color] = float(v_ref)

            hsv_pixel = np.uint8([[[int(h_center), int(s_ref), v_ref]]])"""
    ),
    (
        """    def reset_color_calibration(self) -> None:
        \"\"\"回復系統預設顏色模板。\"\"\"
        self.COLOR_HUE_CENTER = dict(self.DEFAULT_COLOR_HUE_CENTER)
        self.COLOR_SAT_REF = dict(self.DEFAULT_COLOR_SAT_REF)
        self.COLOR_LAB = {k: v.copy() for k, v in self.DEFAULT_COLOR_LAB.items()}""",
        """    def reset_color_calibration(self) -> None:
        \"\"\"回復系統預設顏色模板。\"\"\"
        self.COLOR_HUE_CENTER = dict(self.DEFAULT_COLOR_HUE_CENTER)
        self.COLOR_SAT_REF = dict(self.DEFAULT_COLOR_SAT_REF)
        self.COLOR_VAL_REF = dict(self.DEFAULT_COLOR_VAL_REF)
        self.COLOR_LAB = {k: v.copy() for k, v in self.DEFAULT_COLOR_LAB.items()}"""
    ),
    (
        """    def _template_distance(self, name: str, hue: float, sat_med: float, lab_med: np.ndarray) -> float:
        ref_h = self.COLOR_HUE_CENTER.get(name, -1.0)
        ref_s = self.COLOR_SAT_REF.get(name, 140.0)
        ref_lab = self.COLOR_LAB.get(name)
        if ref_h < 0 or ref_lab is None:
            return 999.0

        hue_d = self._circular_hue_diff(hue, ref_h) / 90.0
        sat_d = abs(float(sat_med) - float(ref_s)) / 255.0
        lab_d = float(np.linalg.norm(lab_med.astype(np.float32) - ref_lab.astype(np.float32))) / 64.0
        return 0.48 * hue_d + 0.12 * sat_d + 0.40 * lab_d""",
        """    def _template_distance(self, name: str, hue: float, sat_med: float, val_med: float, lab_med: np.ndarray) -> float:
        ref_h = self.COLOR_HUE_CENTER.get(name, -1.0)
        ref_s = self.COLOR_SAT_REF.get(name, 140.0)
        ref_v = self.COLOR_VAL_REF.get(name, 180.0)
        ref_lab = self.COLOR_LAB.get(name)
        if ref_h < 0 or ref_lab is None:
            return 999.0

        hue_d = self._circular_hue_diff(hue, ref_h) / 90.0
        sat_d = abs(float(sat_med) - float(ref_s)) / 255.0
        val_d = abs(float(val_med) - float(ref_v)) / 255.0
        lab_d = float(np.linalg.norm(lab_med.astype(np.float32) - ref_lab.astype(np.float32))) / 64.0
        
        # 增加 S 與 V 的權重，降低單純 H 的權重
        return 0.35 * hue_d + 0.20 * sat_d + 0.15 * val_d + 0.30 * lab_d"""
    ),
    (
        """    def _dominant_cluster_stats(
        self,
        Hf: np.ndarray,
        Sf: np.ndarray,
        Vf: np.ndarray,
        labf: np.ndarray,
    ) -> Tuple[float, float, np.ndarray]:
        n = Hf.size
        if n < 20:
            hue = self._circular_hue_mean(Hf, (Sf * Vf) + 1e-3)
            return hue, float(np.median(Sf)), np.median(labf, axis=0).astype(np.float32)""",
        """    def _dominant_cluster_stats(
        self,
        Hf: np.ndarray,
        Sf: np.ndarray,
        Vf: np.ndarray,
        labf: np.ndarray,
    ) -> Tuple[float, float, float, np.ndarray]:
        n = Hf.size
        if n < 20:
            hue = self._circular_hue_mean(Hf, (Sf * Vf) + 1e-3)
            return hue, float(np.median(Sf)), float(np.median(Vf)), np.median(labf, axis=0).astype(np.float32)"""
    ),
    (
        """        if K <= 1:
            hue = self._circular_hue_mean(Hf, (Sf * Vf) + 1e-3)
            return hue, float(np.median(Sf)), np.median(labf, axis=0).astype(np.float32)""",
        """        if K <= 1:
            hue = self._circular_hue_mean(Hf, (Sf * Vf) + 1e-3)
            return hue, float(np.median(Sf)), float(np.median(Vf)), np.median(labf, axis=0).astype(np.float32)"""
    ),
    (
        """        hue = self._circular_hue_mean(Hf[sel_full], (Sf[sel_full] * Vf[sel_full]) + 1e-3)
        sat = float(np.median(Sf[sel_full])) if np.any(sel_full) else float(np.median(Sf))
        lab_med = np.median(labf[sel_full], axis=0).astype(np.float32) if np.any(sel_full) else np.median(labf, axis=0).astype(np.float32)
        return hue, sat, lab_med""",
        """        hue = self._circular_hue_mean(Hf[sel_full], (Sf[sel_full] * Vf[sel_full]) + 1e-3)
        sat = float(np.median(Sf[sel_full])) if np.any(sel_full) else float(np.median(Sf))
        val = float(np.median(Vf[sel_full])) if np.any(sel_full) else float(np.median(Vf))
        lab_med = np.median(labf[sel_full], axis=0).astype(np.float32) if np.any(sel_full) else np.median(labf, axis=0).astype(np.float32)
        return hue, sat, val, lab_med"""
    ),
    (
        """        wgt = (Sf / 255.0) * (Vf / 255.0) + 1e-3
        hue_a = self._circular_hue_mean(Hf, wgt)
        sat_a = float(np.median(Sf))
        lab_a = np.median(labf, axis=0).astype(np.float32)

        hue_b, sat_b, lab_b = self._dominant_cluster_stats(Hf, Sf, Vf, labf)

        best_name = "Unknown"
        best_score = 999.0
        for name in self.COLOR_HUE_CENTER.keys():
            score_a = self._template_distance(name, hue_a, sat_a, lab_a)
            score_b = self._template_distance(name, hue_b, sat_b, lab_b)""",
        """        wgt = (Sf / 255.0) * (Vf / 255.0) + 1e-3
        hue_a = self._circular_hue_mean(Hf, wgt)
        sat_a = float(np.median(Sf))
        val_a = float(np.median(Vf))
        lab_a = np.median(labf, axis=0).astype(np.float32)

        hue_b, sat_b, val_b, lab_b = self._dominant_cluster_stats(Hf, Sf, Vf, labf)

        best_name = "Unknown"
        best_score = 999.0
        for name in self.COLOR_HUE_CENTER.keys():
            score_a = self._template_distance(name, hue_a, sat_a, val_a, lab_a)
            score_b = self._template_distance(name, hue_b, sat_b, val_b, lab_b)"""
    )
]

for i, (t, r) in enumerate(replaces):
    if t not in content:
        print(f"FAILED to find block {i}")
        sys.exit(1)
    content = content.replace(t, r)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(content)

print("Modification complete.")
