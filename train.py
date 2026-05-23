# -*- coding: utf-8 -*-
"""
train_perceptron.py
Entrenamiento de dos perceptrones binarios en cascada en formato Q8 (escala x256)
para la maceta inteligente basada en PIC16F887.
Implementación en Python puro sin dependencias de scikit-learn y compatible con Windows.
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
        # Inicializar pesos y bias en cero
        self.coef_ = np.zeros(n_features)
        self.intercept_ = 0.0
        
        for epoch in range(self.max_iter):
            errors = 0
            for idx, x_i in enumerate(X):
                linear_output = np.dot(x_i, self.coef_) + self.intercept_
                y_predicted = 1 if linear_output >= 0 else 0
                
                # Regla de aprendizaje del perceptrón
                update = self.lr * (y[idx] - y_predicted)
                if update != 0:
                    self.coef_ += update * x_i
                    self.intercept_ += update
                    errors += 1
            if errors == 0:
                print(f"-> Entrenamiento converge perfectamente en la epoca {epoch}!")
                break
                
    def predict(self, X):
        linear_output = np.dot(X, self.coef_) + self.intercept_
        return np.where(linear_output >= 0, 1, 0)
        
    def score(self, X, y):
        predictions = self.predict(X)
        return np.mean(predictions == y)

# Configuración de rutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "visualizer", "sensor_data.csv")
OUTPUT_ASM = os.path.join(BASE_DIR, "pesos_perceptron.asm")
OUTPUT_JSON = os.path.join(BASE_DIR, "visualizer", "weights.json")

print("[INFO] Iniciando pipeline de entrenamiento para Maceta Inteligente Q8...")

# 1. Cargar y limpiar el dataset real
if not os.path.exists(CSV_FILE):
    # Si no está en visualizer, buscar en el directorio raíz
    CSV_FILE = os.path.join(BASE_DIR, "sensor_data.csv")

if not os.path.exists(CSV_FILE):
    raise FileNotFoundError(f"No se encontró el archivo {CSV_FILE}. Por favor genera datos primero.")

df_real = pd.read_csv(CSV_FILE)
print(f"Cargadas {len(df_real)} muestras reales de sensor_data.csv.")

# Filtrar lecturas ruidosas (por ejemplo, desconexiones del LM35 que marquen 0°C o menos)
df_real = df_real[(df_real["Temperatura_C"] > 5) & (df_real["Temperatura_C"] < 50)]
print(f"Muestras reales limpias de ruido: {len(df_real)}")

# 2. Conversión inversa: De variables físicas a valores crudos del ADC de 8 bits (0-255)
# Esto imita exactamente lo que leerá el PIC16F887 tras descartar los 2 LSB de su ADC de 10 bits.
def physical_to_adc8(row):
    # Luz (0-100%) -> Divisor de tensión directo: 0% = 0 ADC, 100% = 255 ADC
    adc8_luz = int(round(row["Luz_Porcentaje"] * 2.55))
    
    # Temperatura LM35 -> Temp * 2.048 (para 10 bits) / 4 (para 8 bits) = Temp / 1.953
    adc8_temp = int(round(row["Temperatura_C"] / 1.953))
    
    # Humedad (0-100%) -> Higrómetro invertido: 100% = 0 ADC (húmedo), 0% = 255 ADC (seco)
    adc8_hum = int(round(255 - row["Humedad_Porcentaje"] * 2.55))
    
    # Acotar en rango 0-255 por seguridad
    adc8_luz = max(0, min(255, adc8_luz))
    adc8_temp = max(0, min(255, adc8_temp))
    adc8_hum = max(0, min(255, adc8_hum))
    
    return pd.Series([adc8_hum, adc8_temp, adc8_luz], index=["Humedad_ADC8", "Temp_ADC8", "Luz_ADC8"])

df_real_adc = df_real.apply(physical_to_adc8, axis=1)
df_real_adc["clase"] = 0  # Toda la medición en ambiente normal = OK (clase 0)

# 3. Generar datos sintéticos para las clases de Estres (Riego y Sol)
np.random.seed(42)
n_samples_synthetic = 1500

# --- CLASE 1: NECESITA RIEGO (Humedad de suelo criticamente baja -> ADC8 de humedad alto)
# Suculentas en sequia extrema: humedad < 12% (ADC8 de humedad > 224)
syn_riego_hum = np.random.randint(220, 256, n_samples_synthetic)
syn_riego_temp = np.random.randint(10, 30, n_samples_synthetic)  # temperatura templada/comun
syn_riego_luz = np.random.randint(20, 180, n_samples_synthetic)   # luz moderada
df_syn_riego = pd.DataFrame({
    "Humedad_ADC8": syn_riego_hum,
    "Temp_ADC8": syn_riego_temp,
    "Luz_ADC8": syn_riego_luz,
    "clase": 1
})

# --- CLASE 2: DEMASIADO SOL (Luz extrema y Temperatura extrema)
# Insolacion en Suculenta: Luz > 82% (ADC8 > 210), Temp > 43°C (ADC8 > 22)
# La temperatura DEBE ser claramente más alta que lo normal (ADC8 > 22 = >43°C)
# para que el perceptrón aprenda que SOL = luz alta + temp alta (no solo una)
# Humedad normal (no criticamente seca para que no colisione con clase 1)
syn_sol_hum = np.random.randint(50, 180, n_samples_synthetic)
syn_sol_temp = np.random.randint(22, 30, n_samples_synthetic)   # LM35 alto: >43°C -> ADC8 > 22
syn_sol_luz = np.random.randint(210, 256, n_samples_synthetic)   # Luz muy alta -> ADC8 > 210
df_syn_sol = pd.DataFrame({
    "Humedad_ADC8": syn_sol_hum,
    "Temp_ADC8": syn_sol_temp,
    "Luz_ADC8": syn_sol_luz,
    "clase": 2
})

# --- CONTRAEJEMPLOS CLASE 0: Condiciones parciales que NO son SOL ---
# Estos enseñan al perceptrón que necesita AMBAS condiciones (luz + temp) para ser SOL
n_counter = 500

# Contra-ejemplo A: Temperatura alta pero luz baja/media = NO es sol (ej: día caluroso nublado)
counter_a_hum = np.random.randint(50, 180, n_counter)
counter_a_temp = np.random.randint(20, 30, n_counter)   # Temp alta
counter_a_luz = np.random.randint(0, 120, n_counter)     # Luz baja/media
df_counter_a = pd.DataFrame({
    "Humedad_ADC8": counter_a_hum,
    "Temp_ADC8": counter_a_temp,
    "Luz_ADC8": counter_a_luz,
    "clase": 0  # OK, no es SOL
})

# Contra-ejemplo B: Luz alta pero temperatura baja = NO es sol (ej: invierno soleado)
counter_b_hum = np.random.randint(50, 180, n_counter)
counter_b_temp = np.random.randint(0, 15, n_counter)     # Temp baja
counter_b_luz = np.random.randint(200, 256, n_counter)   # Luz alta
df_counter_b = pd.DataFrame({
    "Humedad_ADC8": counter_b_hum,
    "Temp_ADC8": counter_b_temp,
    "Luz_ADC8": counter_b_luz,
    "clase": 0  # OK, no es SOL
})

# 4. Consolidar el dataset hibrido equilibrado
# Tomamos una cantidad similar de muestras reales (clase 0) para evitar desbalance
df_real_subset = df_real_adc.sample(n=n_samples_synthetic, random_state=42)

df_all = pd.concat([df_real_subset, df_syn_riego, df_syn_sol, df_counter_a, df_counter_b], ignore_index=True)
print(f"Dataset combinado consolidado: {len(df_all)} muestras.")
print(f"Distribucion de clases:\n{df_all['clase'].value_counts()}")

# 5. Precomputar Parametros de Normalizacion
# Para el perceptron, la normalizacion es vital.
X_raw = df_all[["Humedad_ADC8", "Temp_ADC8", "Luz_ADC8"]].values

mean_features = np.mean(X_raw, axis=0)
std_features = np.std(X_raw, axis=0)

# Para evitar divisiones flotantes en el PIC, calculamos el multiplicador de escala Q8
# ScaleMultiplier = round(256 / std)
# Asi, normalizar es: (x_raw - mean) * ScaleMultiplier / 256
scale_multipliers = np.round(256.0 / std_features).astype(int)

print("\n--- Parametros de Normalizacion Calculados ---")
features_names = ["Humedad", "Temperatura", "Luz"]
for i, name in enumerate(features_names):
    print(f"{name}: Media = {mean_features[i]:.2f}, Desv.Est. = {std_features[i]:.2f}, Multiplicador Q8 = {scale_multipliers[i]}")

# Aplicar normalizacion simulando el formato Q8
X_norm_q8 = np.zeros_like(X_raw, dtype=float)
for i in range(3):
    # Simulamos el calculo entero del PIC: (x - mean) * multiplier
    X_norm_q8[:, i] = (X_raw[:, i] - int(round(mean_features[i]))) * scale_multipliers[i] / 256.0

# 6. Entrenamiento en Cascada (Dos Perceptrones Binarios)

# --- PERCEPTRON 1: ¿Necesita Riego? (Clase 1 vs Resto [0, 2])
y_riego = (df_all["clase"] == 1).astype(int).values
clf_riego = PurePythonPerceptron(learning_rate=0.01, max_iter=2000)
clf_riego.fit(X_norm_q8, y_riego)
acc_riego = clf_riego.score(X_norm_q8, y_riego)
print(f"Perceptron 1 (Riego) entrenado. Precision (Accuracy): {acc_riego:.2%}")

# --- PERCEPTRON 2: ¿Demasiado Sol? (Clase 2 vs OK [0])
# Filtramos los datos que no son Riego (clase 1) para entrenar el separador Sol vs OK
df_sol_vs_ok = df_all[df_all["clase"] != 1]
X_sol_vs_ok = df_sol_vs_ok[["Humedad_ADC8", "Temp_ADC8", "Luz_ADC8"]].values
X_sol_vs_ok_norm = np.zeros_like(X_sol_vs_ok, dtype=float)
for i in range(3):
    X_sol_vs_ok_norm[:, i] = (X_sol_vs_ok[:, i] - int(round(mean_features[i]))) * scale_multipliers[i] / 256.0

y_sol = (df_sol_vs_ok["clase"] == 2).astype(int).values

clf_sol = PurePythonPerceptron(learning_rate=0.01, max_iter=2000)
clf_sol.fit(X_sol_vs_ok_norm, y_sol)
acc_sol = clf_sol.score(X_sol_vs_ok_norm, y_sol)
print(f"Perceptron 2 (Sol) entrenado. Precision (Accuracy): {acc_sol:.2%}")

# 7. Escalado Q8 de los pesos y biases
# Los pesos originales de sklearn operan sobre X_norm.
# Como en el PIC nuestra entrada ya esta multiplicada por Q8 (desde la normalizacion),
# para mantener la consistencia escalamos los pesos por 256.
w1 = clf_riego.coef_
b1 = clf_riego.intercept_

w2 = clf_sol.coef_
b2 = clf_sol.intercept_

# Multiplicar pesos y biases por 256 para punto fijo Q8.8
W1_Q8 = np.round(w1 * 256.0).astype(int)
B1_Q8 = int(round(b1 * 256.0 * 256.0)) # El bias se escala al cuadrado ya que los productos son Q8 * Q8 = Q16

W2_Q8 = np.round(w2 * 256.0).astype(int)
B2_Q8 = int(round(b2 * 256.0 * 256.0))

print("\n--- Pesos del Perceptron 1 (Riego) en Q8 ---")
print(f"W_HUMEDAD: {W1_Q8[0]}, W_TEMP: {W1_Q8[1]}, W_LUZ: {W1_Q8[2]}, BIAS: {B1_Q8}")
print("--- Pesos del Perceptron 2 (Sol) en Q8 ---")
print(f"W_HUMEDAD: {W2_Q8[0]}, W_TEMP: {W2_Q8[1]}, W_LUZ: {W2_Q8[2]}, BIAS: {B2_Q8}")

# 8. Exportar a codigo Assembly (.ASM)
asm_content = f""";====================================================================
; PESOS Y PARAMETROS DEL PERCEPTRON EN CASCADA (FORMATO Q8 / ESCALA x256)
; Generado automaticamente por train_perceptron.py
; Planta: Suculenta (Ambiente comun / controlado)
;====================================================================

; --- PARAMETROS DE NORMALIZACION DE ENTRADAS ---
; Formula PIC: X_norm_q8 = (X_raw - MEAN) * SCALE_MUL
; Donde X_raw es la lectura directa del ADC desplazada 2 bits a la derecha (0-255)
MEAN_H          EQU     {int(round(mean_features[0]))}      ; Media Humedad (ADC 8 bits)
SCALE_MUL_H     EQU     {scale_multipliers[0]}      ; Multiplicador de Escala Humedad Q8

MEAN_T          EQU     {int(round(mean_features[1]))}      ; Media Temperatura (ADC 8 bits)
SCALE_MUL_T     EQU     {scale_multipliers[1]}      ; Multiplicador de Escala Temperatura Q8

MEAN_L          EQU     {int(round(mean_features[2]))}      ; Media Luz (ADC 8 bits)
SCALE_MUL_L     EQU     {scale_multipliers[2]}      ; Multiplicador de Escala Luz Q8

; --- PERCEPTRON 1: ¿NECESITA RIEGO? (Clase 1 vs Resto) ---
; Inferencia: z1 = (x_h * W1_H) + (x_t * W1_T) + (x_l * W1_L) + B1_BIAS
; Nota: Los pesos estan en Q8, lo que hace que los productos sean Q16. El Bias esta en Q16.
W1_HUMEDAD      EQU     {W1_Q8[0]}       ; Peso Humedad Q8
W1_TEMP         EQU     {W1_Q8[1]}       ; Peso Temperatura Q8
W1_LUZ          EQU     {W1_Q8[2]}       ; Peso Luz Q8
B1_BIAS_H       EQU     {B1_Q8 >> 16}    ; Byte Alto de BIAS (Q16)
B1_BIAS_M       EQU     {(B1_Q8 >> 8) & 0xFF} ; Byte Medio de BIAS (Q16)
B1_BIAS_L       EQU     {B1_Q8 & 0xFF}   ; Byte Bajo de BIAS (Q16)

; --- PERCEPTRON 2: ¿DEMASIADO SOL? (Clase 2 vs OK) ---
; Inferencia: z2 = (x_h * W2_H) + (x_t * W2_T) + (x_l * W2_L) + B2_BIAS
W2_HUMEDAD      EQU     {W2_Q8[0]}       ; Peso Humedad Q8
W2_TEMP         EQU     {W2_Q8[1]}       ; Peso Temperatura Q8
W2_LUZ          EQU     {W2_Q8[2]}       ; Peso Luz Q8
B2_BIAS_H       EQU     {B2_Q8 >> 16}    ; Byte Alto de BIAS (Q16)
B2_BIAS_M       EQU     {(B2_Q8 >> 8) & 0xFF} ; Byte Medio de BIAS (Q16)
B2_BIAS_L       EQU     {B2_Q8 & 0xFF}   ; Byte Bajo de BIAS (Q16)
"""

with open(OUTPUT_ASM, "w", encoding="utf-8") as f:
    f.write(asm_content)
print(f"\nArchivo Assembly exportado exitosamente en: {OUTPUT_ASM}")

# 9. Exportar a JSON para el visualizador / dashboard web
# Esto le permitira al simulador o al dashboard usar los mismos pesos neuronales si se desea
weights_json = {
    "normalization": {
        "mean": {
            "hum": int(round(mean_features[0])),
            "temp": int(round(mean_features[1])),
            "ldr": int(round(mean_features[2]))
        },
        "scale_mul": {
            "hum": int(scale_multipliers[0]),
            "temp": int(scale_multipliers[1]),
            "ldr": int(scale_multipliers[2])
        }
    },
    "perceptron_riego": {
        "w_hum": int(W1_Q8[0]),
        "w_temp": int(W1_Q8[1]),
        "w_luz": int(W1_Q8[2]),
        "bias": int(B1_Q8)
    },
    "perceptron_sol": {
        "w_hum": int(W2_Q8[0]),
        "w_temp": int(W2_Q8[1]),
        "w_luz": int(W2_Q8[2]),
        "bias": int(B2_Q8)
    }
}

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(weights_json, f, indent=4)
print(f"Archivo JSON de configuracion exportado en: {OUTPUT_JSON}")

# 10. Graficar las fronteras de decision tridimensionales
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

# Muestras reales y sinteticas
colors = {0: 'g', 1: 'b', 2: 'r'}
labels = {0: 'Planta OK', 1: 'Necesita Riego', 2: 'Demasiado Sol'}

for c in [0, 1, 2]:
    subset = df_all[df_all["clase"] == c]
    ax.scatter(subset["Humedad_ADC8"], subset["Temp_ADC8"], subset["Luz_ADC8"],
               c=colors[c], label=labels[c], alpha=0.6, edgecolors='none', s=20)

ax.set_xlabel('Humedad (ADC 8 bits)')
ax.set_ylabel('Temperatura (ADC 8 bits)')
ax.set_zlabel('Luz (ADC 8 bits)')
ax.set_title('Visualizacion del Dataset de Suculenta y Clases de Estres')
ax.legend()

# Guardar la imagen en el directorio de salida
graph_output = os.path.join(BASE_DIR, "visualizer", "decision_boundary.png")
plt.savefig(graph_output, dpi=150)
print(f"Grafico de dispersion 3D guardado en: {graph_output}")
plt.close()

print("\n[SUCCESS] Proceso completado con exito! Las neuronas estan listas para el PIC16F887.")
