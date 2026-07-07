# -*- coding: utf-8 -*-
"""
train.py
Entrenamiento de dos perceptrones binarios en cascada en formato Q8 (escala x256)
para la maceta inteligente basada en PIC16F887.
Implementación en Python puro sin dependencias de scikit-learn.

Salida:
  - ../firmware/weights.asm  (constantes EQU para el firmware)
  - ../visualizer/data/weights.json (pesos para el dashboard web)
  - decision_boundary.png (gráfico 3D del dataset)
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# --------------------------------------------------------------------
# CLASE DE PERCEPTRÓN EN PYTHON PURO (Rosenblatt Perceptron)
# --------------------------------------------------------------------
class PurePythonPerceptron:
    def __init__(self, learning_rate=0.01, max_iter=2000):
        self.lr = learning_rate
        self.max_iter = max_iter
        self.coef_ = None
        self.intercept_ = None
        
    def fit(self, X, y):
        n_samples, n_features = X.shape
        self.coef_ = np.zeros(n_features)
        self.intercept_ = 0.0
        
        for epoch in range(self.max_iter):
            errors = 0
            for idx, x_i in enumerate(X):
                linear_output = np.dot(x_i, self.coef_) + self.intercept_
                y_predicted = 1 if linear_output >= 0 else 0
                update = self.lr * (y[idx] - y_predicted)
                if update != 0:
                    self.coef_ += update * x_i
                    self.intercept_ += update
                    errors += 1
            if errors == 0:
                print(f"-> Entrenamiento converge en la epoca {epoch}!")
                break
                
    def predict(self, X):
        linear_output = np.dot(X, self.coef_) + self.intercept_
        return np.where(linear_output >= 0, 1, 0)
        
    def score(self, X, y):
        predictions = self.predict(X)
        return np.mean(predictions == y)

# Configuración de rutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "sensor_data.csv")
OUTPUT_ASM = os.path.join(BASE_DIR, "..", "firmware", "weights.asm")
OUTPUT_JSON = os.path.join(BASE_DIR, "..", "visualizer", "data", "weights.json")

print("[INFO] Iniciando pipeline de entrenamiento para Maceta Inteligente Q8...")

# 1. Cargar y limpiar el dataset real
if not os.path.exists(CSV_FILE):
    raise FileNotFoundError(f"No se encontro el archivo {CSV_FILE}. Por favor genera datos primero.")

df_real = pd.read_csv(CSV_FILE)
print(f"Cargadas {len(df_real)} muestras reales de sensor_data.csv.")

df_real = df_real[(df_real["Temperatura_C"] > 5) & (df_real["Temperatura_C"] < 50)]
print(f"Muestras reales limpias de ruido: {len(df_real)}")

# 2. Conversión inversa: De variables físicas a valores crudos del ADC de 8 bits (0-255)
def physical_to_adc8(row):
    adc8_luz = int(round(row["Luz_Porcentaje"] * 2.55))
    adc8_temp = int(round(row["Temperatura_C"] / 1.953))
    adc8_hum = int(round(255 - row["Humedad_Porcentaje"] * 2.55))
    adc8_luz = max(0, min(255, adc8_luz))
    adc8_temp = max(0, min(255, adc8_temp))
    adc8_hum = max(0, min(255, adc8_hum))
    return pd.Series([adc8_hum, adc8_temp, adc8_luz], index=["Humedad_ADC8", "Temp_ADC8", "Luz_ADC8"])

df_real_adc = df_real.apply(physical_to_adc8, axis=1)
df_real_adc["clase"] = 0  # Ambiente normal = OK (clase 0)

# 3. Generar datos sintéticos para las clases de estrés
np.random.seed(42)
n_samples_synthetic = 1500

# CLASE 1: NECESITA RIEGO (humedad critica -> ADC8 alto)
syn_riego_hum  = np.random.randint(220, 256, n_samples_synthetic)
syn_riego_temp = np.random.randint(10, 30, n_samples_synthetic)
syn_riego_luz  = np.random.randint(20, 180, n_samples_synthetic)
df_syn_riego = pd.DataFrame({
    "Humedad_ADC8": syn_riego_hum, "Temp_ADC8": syn_riego_temp,
    "Luz_ADC8": syn_riego_luz, "clase": 1
})

# CLASE 2: DEMASIADO SOL (luz extrema Y temperatura extrema)
syn_sol_hum  = np.random.randint(50, 180, n_samples_synthetic)
syn_sol_temp = np.random.randint(22, 30, n_samples_synthetic)   # >43°C
syn_sol_luz  = np.random.randint(210, 256, n_samples_synthetic)
df_syn_sol = pd.DataFrame({
    "Humedad_ADC8": syn_sol_hum, "Temp_ADC8": syn_sol_temp,
    "Luz_ADC8": syn_sol_luz, "clase": 2
})

# Contraejemplos: condiciones parciales que NO son SOL
n_counter = 500
# A: Temp alta + luz baja = NO es sol
counter_a_hum  = np.random.randint(50, 180, n_counter)
counter_a_temp = np.random.randint(20, 30, n_counter)
counter_a_luz  = np.random.randint(0, 120, n_counter)
df_counter_a = pd.DataFrame({
    "Humedad_ADC8": counter_a_hum, "Temp_ADC8": counter_a_temp,
    "Luz_ADC8": counter_a_luz, "clase": 0
})

# B: Luz alta + temp baja = NO es sol
counter_b_hum  = np.random.randint(50, 180, n_counter)
counter_b_temp = np.random.randint(0, 15, n_counter)
counter_b_luz  = np.random.randint(200, 256, n_counter)
df_counter_b = pd.DataFrame({
    "Humedad_ADC8": counter_b_hum, "Temp_ADC8": counter_b_temp,
    "Luz_ADC8": counter_b_luz, "clase": 0
})

# 4. Consolidar dataset híbrido equilibrado
df_real_subset = df_real_adc.sample(n=n_samples_synthetic, random_state=42)
df_all = pd.concat([df_real_subset, df_syn_riego, df_syn_sol, df_counter_a, df_counter_b], ignore_index=True)
print(f"Dataset combinado: {len(df_all)} muestras.")
print(f"Distribucion de clases:\n{df_all['clase'].value_counts()}")

# 5. Normalización (precomputa parámetros para el PIC)
X_raw = df_all[["Humedad_ADC8", "Temp_ADC8", "Luz_ADC8"]].values
mean_features = np.mean(X_raw, axis=0)
std_features  = np.std(X_raw, axis=0)
scale_multipliers = np.round(256.0 / std_features).astype(int)

print("\n--- Parametros de Normalizacion ---")
for i, name in enumerate(["Humedad", "Temperatura", "Luz"]):
    print(f"{name}: Media={mean_features[i]:.1f}, Std={std_features[i]:.1f}, ScaleMul={scale_multipliers[i]}")

X_norm_q8 = np.zeros_like(X_raw, dtype=float)
for i in range(3):
    X_norm_q8[:, i] = (X_raw[:, i] - int(round(mean_features[i]))) * scale_multipliers[i] / 256.0

# 6. Entrenamiento en Cascada
y_riego = (df_all["clase"] == 1).astype(int).values
clf_riego = PurePythonPerceptron(learning_rate=0.01, max_iter=2000)
clf_riego.fit(X_norm_q8, y_riego)
print(f"Perceptron 1 (Riego) - Accuracy: {clf_riego.score(X_norm_q8, y_riego):.2%}")

df_sol_vs_ok = df_all[df_all["clase"] != 1]
X_sol_vs_ok  = df_sol_vs_ok[["Humedad_ADC8", "Temp_ADC8", "Luz_ADC8"]].values
X_sol_norm   = np.zeros_like(X_sol_vs_ok, dtype=float)
for i in range(3):
    X_sol_norm[:, i] = (X_sol_vs_ok[:, i] - int(round(mean_features[i]))) * scale_multipliers[i] / 256.0
y_sol = (df_sol_vs_ok["clase"] == 2).astype(int).values
clf_sol = PurePythonPerceptron(learning_rate=0.01, max_iter=2000)
clf_sol.fit(X_sol_norm, y_sol)
print(f"Perceptron 2 (Sol)   - Accuracy: {clf_sol.score(X_sol_norm, y_sol):.2%}")

# 7. Escalado Q8
W1_Q8 = np.round(clf_riego.coef_ * 256.0).astype(int)
B1_Q8 = int(round(clf_riego.intercept_ * 256.0 * 256.0))
W2_Q8 = np.round(clf_sol.coef_ * 256.0).astype(int)
B2_Q8 = int(round(clf_sol.intercept_ * 256.0 * 256.0))

print(f"\nP1 (Riego): W_HUM={W1_Q8[0]}, W_TEMP={W1_Q8[1]}, W_LUZ={W1_Q8[2]}, BIAS={B1_Q8}")
print(f"P2 (Sol):   W_HUM={W2_Q8[0]}, W_TEMP={W2_Q8[1]}, W_LUZ={W2_Q8[2]}, BIAS={B2_Q8}")

# 8. Exportar a Assembly
asm_content = f""";====================================================================
; PESOS Y PARAMETROS DEL PERCEPTRON EN CASCADA (FORMATO Q8 / ESCALA x256)
; Generado automaticamente por ml/train.py
; Planta: Suculenta (Ambiente comun / controlado)
;====================================================================

MEAN_H          EQU     {int(round(mean_features[0]))}
SCALE_MUL_H     EQU     {scale_multipliers[0]}
MEAN_T          EQU     {int(round(mean_features[1]))}
SCALE_MUL_T     EQU     {scale_multipliers[1]}
MEAN_L          EQU     {int(round(mean_features[2]))}
SCALE_MUL_L     EQU     {scale_multipliers[2]}

W1_HUMEDAD      EQU     {W1_Q8[0]}
W1_TEMP         EQU     {W1_Q8[1]}
W1_LUZ          EQU     {W1_Q8[2]}
B1_BIAS_H       EQU     {B1_Q8 >> 16}
B1_BIAS_M       EQU     {(B1_Q8 >> 8) & 0xFF}
B1_BIAS_L       EQU     {B1_Q8 & 0xFF}

W2_HUMEDAD      EQU     {W2_Q8[0]}
W2_TEMP         EQU     {W2_Q8[1]}
W2_LUZ          EQU     {W2_Q8[2]}
B2_BIAS_H       EQU     {B2_Q8 >> 16}
B2_BIAS_M       EQU     {(B2_Q8 >> 8) & 0xFF}
B2_BIAS_L       EQU     {B2_Q8 & 0xFF}
"""

os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_ASM)), exist_ok=True)
with open(OUTPUT_ASM, "w", encoding="utf-8") as f:
    f.write(asm_content)
print(f"\nASM exportado: {OUTPUT_ASM}")

# 9. Exportar a JSON para el dashboard
weights_json = {
    "normalization": {
        "mean":      {"hum": int(round(mean_features[0])), "temp": int(round(mean_features[1])), "ldr": int(round(mean_features[2]))},
        "scale_mul": {"hum": int(scale_multipliers[0]),    "temp": int(scale_multipliers[1]),    "ldr": int(scale_multipliers[2])}
    },
    "perceptron_riego": {"w_hum": int(W1_Q8[0]), "w_temp": int(W1_Q8[1]), "w_luz": int(W1_Q8[2]), "bias": int(B1_Q8)},
    "perceptron_sol":   {"w_hum": int(W2_Q8[0]), "w_temp": int(W2_Q8[1]), "w_luz": int(W2_Q8[2]), "bias": int(B2_Q8)}
}
os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_JSON)), exist_ok=True)
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(weights_json, f, indent=4)
print(f"JSON exportado: {OUTPUT_JSON}")

# 10. Gráfico 3D
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')
colors = {0: 'g', 1: 'b', 2: 'r'}
labels = {0: 'Planta OK', 1: 'Necesita Riego', 2: 'Demasiado Sol'}
for c in [0, 1, 2]:
    subset = df_all[df_all["clase"] == c]
    ax.scatter(subset["Humedad_ADC8"], subset["Temp_ADC8"], subset["Luz_ADC8"],
               c=colors[c], label=labels[c], alpha=0.6, edgecolors='none', s=20)
ax.set_xlabel('Humedad (ADC 8 bits)')
ax.set_ylabel('Temperatura (ADC 8 bits)')
ax.set_zlabel('Luz (ADC 8 bits)')
ax.set_title('Dataset de Suculenta — Clases de Estres')
ax.legend()

graph_output = os.path.join(BASE_DIR, "decision_boundary.png")
plt.savefig(graph_output, dpi=150)
print(f"Grafico 3D guardado: {graph_output}")
plt.close()

print("\n[SUCCESS] Proceso completado. Los pesos estan listos para el PIC16F887.")
