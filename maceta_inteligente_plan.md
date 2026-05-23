# 🌱 Maceta Inteligente — Plan de Implementación Completo
### Clasificador de bienestar vegetal mediante Perceptrón Artificial en PIC16F887

---

## Índice

1. [Resumen del Proyecto](#1-resumen-del-proyecto)
2. [Conceptos Teóricos](#2-conceptos-teóricos)
3. [Hardware](#3-hardware)
4. [Entrenamiento en PC (Python)](#4-entrenamiento-en-pc-python)
5. [Arquitectura del Firmware](#5-arquitectura-del-firmware)
6. [Módulos de Software (Assembly)](#6-módulos-de-software-implementación-en-assembly)
7. [Comunicación UART](#7-comunicación-uart)
8. [Integración y Pruebas](#8-integración-y-pruebas)
9. [Plan de Trabajo Semana a Semana](#9-plan-de-trabajo-semana-a-semana)
10. [Estructura del Informe](#10-estructura-del-informe)

---

## 1. Resumen del Proyecto

### Idea central

Un sistema embebido basado en el **PIC16F887** que monitorea las condiciones de una planta (humedad de suelo, temperatura ambiente e iluminación) y, mediante un **perceptrón artificial**, clasifica su estado en tiempo real: `OK`, `NECESITA RIEGO` o `DEMASIADO SOL`.

El modelo neuronal es **entrenado offline en Python** (en la PC) con datos sintéticos + reales, y los pesos resultantes se convierten a **punto fijo (×1000)** y se cargan al microcontrolador vía **UART**. El **firmware del PIC está completamente en Assembly**, implementando aritmética de punto fijo puro en 8 bits. Además, los datos del PIC se muestran en **una página HTML interactiva** que visualiza una maceta animada que cambia según el estado de la planta y el ciclo día/noche del PC.

### Diagrama general

```
┌─────────────────────────────────────────────┐
│                   MACETA                     │
│                                             │
│  [Higrómetro]──────────────────────ADC AN0  │
│  [LM35 Temp] ──────────────────────ADC AN1  │──→ PIC16F887
│  [LDR Luz]   ──────────────────────ADC AN2  │    (Firmware 100% Assembly)
│                                             │
└─────────────────────────────────────────────┘
                      │
              ┌───────▼──────────┐
              │   PIC16F887      │
              │                 │
              │[ PERCEPTRÓN ]   │──→ LCD 16x2 ("NECESITA RIEGO 💧")
              │ (Punto Fijo)    │──→ LED / Buzzer
              │                 │──→ UART TX/RX
              └────────┬─────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
    Python PC                   (HTML + JS)
    (Entrenamiento)            (Navegador)
    (Monitor Serie)                 │
         │                          │
    ┌────▼─────────┐         ┌──────▼────────┐
    │ Datos:       │         │ Maceta Animada│
    │ - CSV        │         │ - Estado OK   │
    │ - Sintético  │         │ - RIEGO 💧    │
    │ - Real       │         │ - SOL ☀️      │
    │ - Pesos      │         │ - Día/Noche   │
    │ - Gráficas   │         │ - Gráficas    │
    └──────────────┘         └───────────────┘
```

### ¿Por qué este enfoque es correcto?

Este modelo se llama **"offline training, online inference"** y es exactamente el pipeline usado en producción industrial con microcontroladores (ej: TinyML). Se entrena donde hay recursos, se deploya donde los recursos son limitados. El PIC solo suma, multiplica y evalúa una función de activación: operaciones perfectamente viables en 8 bits.

### Características principales del proyecto

1. **100% Assembly en el PIC** - Sin librerías de C, máxima eficiencia
2. **Aritmética de punto fijo (×1000)** - Precisión sin FPU
3. **Datos sintéticos + reales** - Dataset robusto y rápido de generar
4. **Interfaz web interactiva** - Maceta animada con cambios visuales
5. **Ciclo día/noche** - Sincronizado con reloj del PC
6. **Carga dinámica de pesos** - Reentrenamiento sin reprogramar PIC
7. **Telemetría UART** - Streaming de datos en tiempo real

### Justificación de decisiones técnicas

| Decisión | Razón |
|---|---|
| **Assembly puro** | Máximo control, mínimo overhead, educativo |
| **Punto fijo ×1000** | Velocidad 100× mayor que float en 8 bits, precisión suficiente |
| **Datos sintéticos + reales** | Entrenamiento rápido + robustez a ruido real |
| **HTML/JavaScript** | Visualización atractiva, sin dependencias complejas |
| **Ciclo día/noche** | Realismo, mejora interfaz educativa |
| **Perceptrón lineal** | Clasificación simple, separación lineal suficiente |

### Ajustes para implementación en Assembly puro (PIC16F887)

Para garantizar una implementación realista en Assembly, se aplican estos cambios de alcance:

1. **Aritmética de punto fijo obligatoria** (escala ×1000) - Todas las operaciones con enteros de 16 bits
2. **Perceptrón simple lineal** - Una sola neurona binaria (OK/NO OK) 
3. **Inferencia primitiva** - Solo operaciones base de Assembly: MULWF, ADDWF, SUBWF, BTFSC, GOTO
4. **Normalización precomputada** - Los parámetros de media/escala vienen de Python como constantes EQU
5. **Tablas de búsqueda en Flash** - Para divisiones costosas, usar ADDWF en loop o tablas
6. **Sin librerías dinámicas** - Todo hardcodeado o en EEPROM (máximo 256 bytes)
7. **Pesos fijos en firmware inicialmente** - Opción de carga UART como mejora incremental
8. **Telemetría UART simplificada** - Formato: `H:820,T:285,L:600,C:1\r\n` sin parseo complejo

**Resultado esperado:**
- Firmware Assembly: ~3-4 KB de Flash (el PIC tiene 8 KB)
- Ciclo de inferencia: ~100-200 ciclos de máquina (~50-100 µs a 4 MHz)
- Precisión: ±2-3% en clasificación

---

## 2. Conceptos Teóricos

### 2.1 El Perceptrón (Rosenblatt, 1957)

El perceptrón es la unidad más simple de una red neuronal. Toma N entradas, las pondera y produce una salida binaria (o continua con la función de activación correcta).

```
x1 ──(w1)──┐
x2 ──(w2)──┤──→ Σ + bias ──→ f(z) ──→ salida
x3 ──(w3)──┘
```

**Fórmula matemática:**

```
z = (x1 × w1) + (x2 × w2) + (x3 × w3) + bias
salida = f(z)
```

### 2.1.1 Aritmética de Punto Fijo (crítico para Assembly en PIC)

Puesto que **todo el firmware se implementará en Assembly**, no tenemos acceso a librerías de punto flotante eficientes. Usamos **punto fijo escalado** para mantener precisión sin overhead:

**Conversión a punto fijo (escala ×1000):**
- Peso en Python: `w = 0.752` → En PIC: `w_fixed = 752` (entero de 16 bits)
- Entrada normalizada: `x = 28.5` → En PIC: `x_fixed = 285` (representa 28.5 × 10)
- Multiplicación: `(x_fixed × w_fixed) / 1000` → retorna resultado escalado ×1000

**Ventajas:**
- Operaciones puras de enteros (MUL, ADD, SUB en Assembly)
- Precisión suficiente para clasificación lineal
- No requiere coprocessador matemático (FPU)
- En Assembly: `MOVF x_fixed, W` → `MULWF w_fixed` → `resultado en PROD`

### 2.2 Función de activación

Para clasificación binaria (`OK` vs `NO OK`) se usa la función **escalón (step)**:

```
f(z) = 1  si z >= 0
f(z) = 0  si z < 0
```

Para clasificación multiclase (`OK`, `RIEGO`, `SOL`) se usan múltiples neuronas con **softmax**, o más simple: **thresholds sobre z** con neuronas separadas.

### 2.3 Implementación en Assembly del Punto Fijo

En el PIC16F887 con Assembly puro, la aritmética de punto fijo se implementa así:

```asm
; Ejemplo: Multiplicar dos valores en punto fijo (×1000)
; x_fixed = 285 (representa 28.5)
; w_fixed = 752 (representa 0.752)
; Resultado esperado: 214.2 → 214200 en punto fijo

MOVF    x_fixed, W      ; W = 285
MULWF   w_fixed         ; (x * w) → PRODH:PRODL = 214320

; Dividir por 1000 usando bit shifts y restas
; Para dividir entre 1000 en Assembly: usar tabla de búsqueda o loops

MOVF    PRODL, W        ; Resultado en registro WREG
; Ajuste: PRODL × 256 + PRODH contiene el resultado de 16 bits
```

La estrategia es usar **tablas de búsqueda precomputadas** en Flash para evitar divisiones costosas, o implementar divisiones iterativas que tomen algunos ciclos de máquina.

#### Ejemplo práctico: Inferencia en Assembly

Supongamos que tenemos:
- `sensor_humedad_H:L = 0x0330` (820 en decimal, muy seco)
- `W_HUMEDAD = 752` (punto fijo)

En Assembly:
```asm
MOVF    sensor_humedad_L, W     ; W = 0x30
MOVWF   multiplicand_L          ; multiplicand = 0x0330
MOVF    sensor_humedad_H, W     ; W = 0x03
MOVWF   multiplicand_H

MOVLW   752                      ; w = 752
MOVWF   multiplier_L
CLRF    multiplier_H

CALL    Mult16x16               ; PROD_H:PROD_M:PROD_L = 820 × 752 = 616640

; Resultado en punto fijo ×1000: 616640 ÷ 1000 = 616 (representa 0.616)
```

Esto es mucho **más rápido en Assembly que simular punto flotante**, y ocupa menos Flash.

### 2.4 Clasificación multiclase con un perceptrón

Con 3 clases se pueden usar **3 neuronas independientes** (una por clase), cada una con sus propios pesos, y se elige la clase cuya neurona da mayor z (winner-takes-all):

```
Neurona_OK     → z0 = x·w0 + b0
Neurona_RIEGO  → z1 = x·w1 + b1
Neurona_SOL    → z2 = x·w2 + b2

clase = argmax(z0, z1, z2)
```

O más simple: usar **dos perceptrones binarios en cascada**:

```
Perceptrón 1: ¿Necesita riego? (humedad_suelo < umbral)
Perceptrón 2: ¿Demasiado sol?  (luz > umbral Y temp > umbral)
Si ninguno → OK
```

---

## 3. Hardware

### 3.1 Componentes necesarios

| Componente | Función | Cantidad | Observaciones |
|---|---|---|---|
| PIC16F887 | Microcontrolador principal | 1 | 40 pines, 8KB Flash, 256B EEPROM |
| Crystal 4MHz o 20MHz | Clock del PIC | 1 | Con capacitores 22pF |
| LCD 16x2 (HD44780) | Display de resultados | 1 | Modo 4 bits para ahorrar pines |
| Teclado matricial 4x4 | Interacción del usuario | 1 | Para modo config y UART manual |
| Higrómetro de suelo | Humedad de tierra | 1 | Módulo FC-28, salida analógica |
| LM35 | Temperatura ambiente | 1 | Salida 10mV/°C, directo al ADC |
| LDR + resistor 10kΩ | Nivel de luz | 1 | Divisor de tensión al ADC |
| MAX232 o CP2102 | Conversión UART-USB | 1 | Para comunicar con PC |
| LED RGB o 3 LEDs | Indicador visual de clase | 3 | Verde=OK, Azul=riego, Rojo=sol |
| Buzzer | Alerta sonora | 1 | Activo o pasivo |
| Resistores, capacitores | Circuito de soporte | varios | Ver esquemático |
| Fuente 5V regulada (7805) | Alimentación | 1 | |

### 3.2 Pines del PIC16F887

```
PIC16F887 — Asignación de pines
─────────────────────────────────────────────

PUERTO A (ADC):
  RA0 / AN0  →  Higrómetro de suelo
  RA1 / AN1  →  LM35 (temperatura)
  RA2 / AN2  →  LDR (luz)

PUERTO B (Teclado matricial):
  RB0–RB3   →  Filas del teclado    (salidas)
  RB4–RB7   →  Columnas del teclado (entradas con pull-up)

PUERTO C (LCD y UART):
  RC6 / TX   →  UART TX → MAX232 → PC
  RC7 / RX   →  UART RX ← MAX232 ← PC
  RC0–RC1    →  LCD RS, EN

PUERTO D (LCD datos):
  RD4–RD7   →  LCD D4-D7 (modo 4 bits)

PUERTO E (LEDs y Buzzer):
  RE0        →  LED Verde  (OK)
  RE1        →  LED Azul   (RIEGO)
  RE2        →  LED Rojo   (SOL)
  RC2/CCP1   →  Buzzer (PWM opcional)
```

### 3.3 Circuito de sensores

**Higrómetro FC-28:**
```
VCC (5V) ──→ VCC del módulo
GND      ──→ GND del módulo
AO       ──→ RA0 del PIC
(DO no se usa — salida digital opcional)
```
Valor ADC: 0 = muy húmedo, 1023 = muy seco

**LM35 (Temperatura):**
```
VCC (5V) ──→ pin + del LM35
GND      ──→ pin - del LM35
Vout     ──→ RA1 del PIC
```
Conversión: Temperatura (°C) = (ADC × 5.0 / 1024.0) × 100

**LDR (Divisor de tensión):**
```
VCC (5V) ──→ LDR ──→ nodo A ──→ RA2 del PIC
                       │
                    10kΩ
                       │
                      GND
```
Valor ADC: 0 = oscuridad total, 1023 = luz plena

### 3.4 Esquema de comunicación UART

```
PIC TX (RC6) ──→ MAX232 T1IN → T1OUT ──→ DB9 pin 2 (RXD) ──→ PC
PIC RX (RC7) ←── MAX232 R1OUT ← R1IN ←── DB9 pin 3 (TXD) ←── PC

(o con CP2102 USB-UART directamente sin MAX232)
```

---

## 4. Entrenamiento en PC (Python)

### 4.1 Recolección de datos — Estrategia Híbrida

Dos enfoques combinados para generar dataset de entrenamiento:

#### Opción A: Datos Sintéticos Generados (Rápido, para prototipado)

```python
# generate_synthetic_dataset.py
import numpy as np
import pandas as pd

np.random.seed(42)
n_samples = 200

# Clase 0: OK (humedad media, temperatura normal, luz media)
ok_data = np.random.normal(
    loc=[500, 25, 400],       # media de (humedad, temp×10, luz)
    scale=[80, 30, 150],      # desviación estándar
    size=(n_samples//3, 3)
)

# Clase 1: NECESITA RIEGO (humedad baja)
riego_data = np.random.normal(
    loc=[850, 22, 350],
    scale=[60, 25, 120],
    size=(n_samples//3, 3)
)

# Clase 2: DEMASIADO SOL (luz alta, temperatura alta)
sol_data = np.random.normal(
    loc=[300, 38, 850],
    scale=[70, 20, 100],
    size=(n_samples//3, 3)
)

# Ensamblar y guardar
X = np.vstack([ok_data, riego_data, sol_data])
y = np.hstack([np.zeros(n_samples//3),
               np.ones(n_samples//3),
               np.ones(n_samples//3) * 2])

df = pd.DataFrame(X, columns=['humedad', 'temp_x10', 'luz'])
df['clase'] = y
df.to_csv('dataset_sintético.csv', index=False)
print(f"Dataset sintético: {n_samples} muestras generadas")
```

**Ventajas:**
- Rápido, reproducible, sin hardware real
- Bueno para validar flujo de entrenamiento

**Desventajas:**
- Puede no reflejar ruido real de sensores
- Perceptrón puede overfitear a distribuciones ideales

#### Opción B: Datos Reales Capturados (Más confiable, toma tiempo)

1. **Conectar sensores al PIC** (con firmware básico para leer ADC)
2. **Script Python recibe datos por UART:**
   ```python
   # capture_realdata.py
   import serial
   import pandas as pd
   from datetime import datetime
   
   port = serial.Serial('COM3', 9600)
   data_log = []
   
   print("Capturando datos reales (60 segundos)...")
   print("Presiona: 0=OK, 1=RIEGO, 2=SOL para etiquetar")
   
   for i in range(60):
       line = port.readline().decode().strip()
       # Formato: "H:820,T:285,L:600"
       parts = dict(p.split(':') for p in line.split(','))
       
       clase = input(f"Muestra {i}: {parts} → Clase [0/1/2]: ")
       data_log.append({
           'humedad': int(parts['H']),
           'temp_x10': int(parts['T']),
           'luz': int(parts['L']),
           'clase': int(clase)
       })
   
   df = pd.DataFrame(data_log)
   df.to_csv(f'dataset_real_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', index=False)
   print(f"Guardado: {len(df)} muestras")
   ```

3. **Etiquetado manual mientras se captura:** Observar planta y anotar clase para cada medida
4. **Con 40–80 ejemplos** ya es suficiente para entrenar un perceptrón lineal

#### Opción C: Combinación Híbrida (Recomendado)

Generar **50% datos sintéticos** (para rellenar) + **50% datos reales capturados** (para anclar en realidad)

```python
# merge_datasets.py
df_syn = pd.read_csv('dataset_sintético.csv')
df_real = pd.read_csv('dataset_real_20260427_102030.csv')

df_train = pd.concat([df_syn.iloc[:100], df_real], ignore_index=True)
df_train.to_csv('dataset_combined.csv', index=False)
print(f"Dataset combinado: {len(df_train)} muestras")
```

**Formato final del CSV:**
```
humedad,temp_x10,luz,clase
820,285,150,1
350,220,900,2
430,220,500,0
...
```
(0=OK, 1=NECESITA RIEGO, 2=DEMASIADO SOL)

#### Comparativa: Sintético vs Real

| Aspecto | Sintético | Real | Recomendación |
|---|---|---|---|
| Tiempo para generar | < 1 min | 60-90 min | Usar sintético para prototipado rápido |
| Exactitud | ~70% (idealizado) | ~85% (con ruido real) | Real es más confiable |
| Ruido de sensores | No | Sí | Real captura comportamiento real |
| Reproducibilidad | 100% | Depende de condiciones | Sintético para debugging |
| Desbalance de clases | Controlable fácil | Manual | Sintético mejor para balance |
| **Flujo óptimo** | **Combinar ambos** | **50-50 mix** | **Lo mejor de ambos mundos** |

**Recomendación final:**
```
Dataset final = Datos_Sintéticos (100 muestras) + Datos_Reales_Capturados (100 muestras)
                = 200 muestras totales, equilibradas, con ruido y sin ruido
```

### 4.2 Script de entrenamiento

```python
# train_perceptron.py
import numpy as np
from sklearn.linear_model import Perceptron
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import pandas as pd

# Cargar datos
df = pd.read_csv("dataset_planta.csv")
X = df[["humedad_suelo", "temperatura", "luz"]].values
y = df["clase"].values

# Normalización (importante para el perceptrón)
scaler = StandardScaler()
X_norm = scaler.fit_transform(X)

# División train/test
X_train, X_test, y_train, y_test = train_test_split(X_norm, y, test_size=0.2)

# Entrenamiento
clf = Perceptron(max_iter=1000, random_state=42)
clf.fit(X_train, y_train)

# Evaluación
acc = clf.score(X_test, y_test)
print(f"Accuracy: {acc:.2%}")
print(f"Pesos:    {clf.coef_}")
print(f"Bias:     {clf.intercept_}")
print(f"Media normalización: {scaler.mean_}")
print(f"Escala:   {scaler.scale_}")
```

### 4.3 Exportar pesos al PIC en Assembly

Los pesos que da sklearn son floats. Los convertimos a **enteros escalados (×1000)** para Assembly:

```python
# export_weights_asm.py
import serial
import time

# Pesos del entrenamiento (ejemplo)
weights = clf.coef_[0]   # array [w_humedad, w_temp, w_luz]
bias    = clf.intercept_[0]
normalization_params = {
    'mean_h': scaler.mean_[0],
    'mean_t': scaler.mean_[1],
    'mean_l': scaler.mean_[2],
    'scale_h': scaler.scale_[0],
    'scale_t': scaler.scale_[1],
    'scale_l': scaler.scale_[2]
}

# Escalar a enteros (×1000)
scale = 1000
w_int = [int(w * scale) for w in weights]
b_int = int(bias * scale)

# Normalización también escalada
mean_int = [int(m * 10) for m in normalization_params.values()[:3]]
scale_int = [int(s * 10) for s in normalization_params.values()[3:]]

print("=== CÓDIGO ASSEMBLY PARA PIC16F887 ===")
print(f"\n; Pesos del perceptrón (punto fijo ×1000)")
print(f"W_HUMEDAD   EQU {w_int[0]}    ; Peso humedad")
print(f"W_TEMP      EQU {w_int[1]}    ; Peso temperatura")
print(f"W_LUZ       EQU {w_int[2]}    ; Peso luz")
print(f"BIAS        EQU {b_int}       ; Bias del perceptrón")
print(f"\n; Parámetros de normalización")
print(f"MEAN_H      EQU {mean_int[0]}  ; Media humedad ×10")
print(f"MEAN_T      EQU {mean_int[1]}  ; Media temperatura ×10")
print(f"MEAN_L      EQU {mean_int[2]}  ; Media luz ×10")
print(f"SCALE_H     EQU {scale_int[0]} ; Escala humedad ×10")
print(f"SCALE_T     EQU {scale_int[1]} ; Escala temperatura ×10")
print(f"SCALE_L     EQU {scale_int[2]} ; Escala luz ×10")

# Opción: mandar por UART para cargar dinámicamente
port = serial.Serial('COM3', 9600)
msg = f"W:{w_int[0]},{w_int[1]},{w_int[2]},B:{b_int}\n"
port.write(msg.encode())
response = port.readline().decode().strip()
print(f"\nRespuesta del PIC: {response}")
port.close()
```

**Los pesos se guardan como EQU (constantes) en el archivo `.asm` del PIC**, o se cargan dinámicamente vía UART a la EEPROM del microcontrolador.

### 4.4 Monitor en tiempo real (Python - Consola)

```python
# monitor_simple.py
import serial
from datetime import datetime

port = serial.Serial('COM3', 9600)
CLASES = {0: "✓ OK", 1: "⚠ RIEGO", 2: "✗ SOL"}

print("Maceta Inteligente - Monitor Serial")
print("=" * 50)

while True:
    try:
        line = port.readline().decode().strip()
        if line:
            parts = dict(p.split(':') for p in line.split(','))
            h = int(parts['H'])
            t = int(parts['T']) / 10
            l = int(parts['L'])
            c = int(parts['C'])
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Humedad: {h:3d}  Temp: {t:5.1f}°C  Luz: {l:3d}  "
                  f"Estado: {CLASES[c]}")
    except KeyboardInterrupt:
        break
    except Exception as e:
        pass

port.close()
```

---

## 4.5 Interfaz Web Interactiva (HTML + JavaScript + Flask)

### Características principales:
- 🌿 **Maceta animada** en balcón pixel art
- 🌞 **Ciclo día/noche** automático según hora del PC (cambia cielo y luz ambiente)
- 😊 **Animaciones de estado:**
  - ✅ **PLANTA OK**: Fuerte, erecta, hojas levantadas, color verde vibrante
  - 😰 **NECESITA RIEGO**: Marchita, hojas caídas, color desaturado, temblor
  - 🔥 **DEMASIADO SOL**: Quemada, hojas marchitas, color marrón-gris
- 📊 **Gráficas en tiempo real** de sensores (Chart.js)
- 🔄 **Actualización cada 500ms** desde el UART del PIC

**Script Python con servidor Flask:**

```python
# dashboard_server.py
import serial
import threading
import json
from flask import Flask, jsonify, render_template_string
from datetime import datetime
import os

app = Flask(__name__)

# Variables globales
sensor_data = {'humedad': 0, 'temp': 0, 'luz': 0, 'clase': 0}
sensor_history = {'humedad': [], 'temp': [], 'luz': [], 'timestamp': []}
max_history = 120  # 60 segundos a 500ms

def read_uart():
    """Thread que lee datos del puerto UART"""
    try:
        port = serial.Serial('COM3', 9600, timeout=1)
        while True:
            try:
                line = port.readline().decode().strip()
                if line:
                    parts = dict(p.split(':') for p in line.split(','))
                    sensor_data['humedad'] = int(parts['H'])
                    sensor_data['temp'] = int(parts['T'])
                    sensor_data['luz'] = int(parts['L'])
                    sensor_data['clase'] = int(parts['C'])
                    
                    # Guardar histórico
                    sensor_history['humedad'].append(sensor_data['humedad'])
                    sensor_history['temp'].append(sensor_data['temp'])
                    sensor_history['luz'].append(sensor_data['luz'])
                    sensor_history['timestamp'].append(datetime.now().strftime('%H:%M:%S'))
                    
                    # Mantener tamaño máximo
                    if len(sensor_history['humedad']) > max_history:
                        for key in sensor_history:
                            sensor_history[key].pop(0)
            except:
                pass
    except:
        print("Error: No se pudo abrir puerto COM3")

@app.route('/api/sensor-data')
def get_sensor_data():
    """API REST para obtener datos actuales"""
    # Convertir a porcentajes (0-1023 → 0-100%)
    return jsonify({
        'humedad': (sensor_data['humedad'] * 100) // 1023,
        'temp': sensor_data['temp'] / 10,
        'luz': (sensor_data['luz'] * 100) // 1023,
        'clase': sensor_data['clase'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/history')
def get_history():
    """API REST para obtener histórico"""
    return jsonify(sensor_history)

@app.route('/')
def dashboard():
    """Servir página HTML del dashboard"""
    return render_template_string(HTML_TEMPLATE)

# Iniciar thread de lectura UART
uart_thread = threading.Thread(target=read_uart, daemon=True)
uart_thread.start()

if __name__ == '__main__':
    print("🌱 Dashboard Maceta Inteligente")
    print("📍 Abre: http://localhost:5000")
    print("🔌 Buscando puerto COM3...")
    import webbrowser
    webbrowser.open('http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=False)
```

**HTML + CSS + JavaScript del Dashboard:**

```python
# Continuación de dashboard_server.py - Template HTML
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌱 Maceta Inteligente</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 2.5em;
        }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        /* ===== BALCÓN CON MACETA ===== */
        .balcon-container {
            display: flex;
            justify-content: center;
            align-items: flex-end;
        }
        
        .balcon {
            position: relative;
            width: 350px;
            height: 450px;
            border: 4px solid #333;
            border-radius: 10px 10px 0 0;
            overflow: hidden;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.2);
        }
        
        /* Cielo - Cambios día/noche */
        .cielo {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 60%;
            transition: background 1s ease;
        }
        
        .cielo.manana { background: linear-gradient(180deg, #87CEEB 0%, #E0F6FF 100%); }
        .cielo.tarde { background: linear-gradient(180deg, #FFB347 0%, #FFCC99 100%); }
        .cielo.noche { background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%); }
        
        /* Suelo del balcón */
        .suelo {
            position: absolute;
            bottom: 0;
            width: 100%;
            height: 40%;
            background: linear-gradient(180deg, #8B7355 0%, #654321 100%);
            border-top: 3px solid #5C4033;
        }
        
        /* Líneas decorativas pixel art */
        .suelo::before {
            content: '';
            position: absolute;
            width: 100%;
            height: 100%;
            background-image: 
                repeating-linear-gradient(90deg, transparent, transparent 15px, rgba(0,0,0,0.1) 15px, rgba(0,0,0,0.1) 30px),
                repeating-linear-gradient(0deg, transparent, transparent 15px, rgba(0,0,0,0.1) 15px, rgba(0,0,0,0.1) 30px);
        }
        
        /* MACETA */
        .maceta-wrapper {
            position: absolute;
            bottom: 45px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 20;
        }
        
        .maceta {
            width: 100px;
            height: 70px;
            background: linear-gradient(135deg, #D2691E 0%, #8B4513 100%);
            border-radius: 0 0 15px 15px;
            border: 3px solid #654321;
            position: relative;
            box-shadow: -5px 5px 15px rgba(0,0,0,0.3);
        }
        
        .maceta::before {
            content: '';
            position: absolute;
            top: -12px;
            left: 50%;
            transform: translateX(-50%);
            width: 110px;
            height: 15px;
            background: linear-gradient(90deg, #8B4513 0%, #A0522D 50%, #8B4513 100%);
            border-radius: 50%;
            box-shadow: inset 0 2px 3px rgba(0,0,0,0.3);
        }
        
        /* TIERRA en la maceta */
        .tierra {
            position: absolute;
            top: 10px;
            left: 5px;
            right: 5px;
            height: 35px;
            background: #5D4E37;
            border-radius: 3px;
            z-index: 5;
        }
        
        /* PLANTA - Contenedor */
        .planta {
            position: absolute;
            bottom: 75px;
            left: 50%;
            transform: translateX(-50%);
            width: 80px;
            height: 100px;
            z-index: 30;
            transition: all 0.5s ease;
        }
        
        /* Estados visuales de la planta */
        .planta.ok {
            --hoja-color: #22AA22;
            --tallo-color: #228822;
            --rotacion: 0deg;
            --escala: 1;
            --opacidad: 1;
        }
        
        .planta.riego {
            --hoja-color: #FF69B4;
            --tallo-color: #FFB6C1;
            --rotacion: 15deg;
            --escala: 0.85;
            --opacidad: 0.7;
        }
        
        .planta.sol {
            --hoja-color: #DAA520;
            --tallo-color: #8B7500;
            --rotacion: 25deg;
            --escala: 0.7;
            --opacidad: 0.6;
        }
        
        /* Tallo */
        .tallo {
            position: absolute;
            bottom: 0;
            left: 50%;
            width: 6px;
            height: 60px;
            background: var(--tallo-color);
            transform: translateX(-50%);
            border-radius: 3px;
            transition: all 0.3s ease;
        }
        
        .planta.riego .tallo,
        .planta.sol .tallo {
            animation: temblor 0.2s infinite;
        }
        
        @keyframes temblor {
            0%, 100% { transform: translateX(-50%) rotateZ(0deg); }
            25% { transform: translateX(-48%) rotateZ(-2deg); }
            75% { transform: translateX(-52%) rotateZ(2deg); }
        }
        
        /* Hoja */
        .hoja {
            position: absolute;
            width: 35px;
            height: 25px;
            background: var(--hoja-color);
            border-radius: 50% 0;
            transition: all 0.3s ease;
            opacity: var(--opacidad);
        }
        
        .hoja-izq {
            bottom: 40px;
            left: -5px;
            transform: rotate(-35deg) scaleY(var(--escala));
            animation: hoja-izq-anim 2s ease-in-out infinite;
        }
        
        .hoja-der {
            bottom: 40px;
            right: -5px;
            transform: rotate(35deg) scaleY(var(--escala));
            animation: hoja-der-anim 2s ease-in-out infinite;
        }
        
        .hoja-top {
            bottom: 70px;
            left: 50%;
            transform: translateX(-50%) scaleY(var(--escala));
            animation: hoja-top-anim 2.5s ease-in-out infinite;
        }
        
        @keyframes hoja-izq-anim {
            0%, 100% { transform: rotate(-35deg) scaleY(var(--escala)); }
            50% { transform: rotate(-45deg) scaleY(var(--escala)); }
        }
        
        @keyframes hoja-der-anim {
            0%, 100% { transform: rotate(35deg) scaleY(var(--escala)); }
            50% { transform: rotate(45deg) scaleY(var(--escala)); }
        }
        
        @keyframes hoja-top-anim {
            0%, 100% { transform: translateX(-50%) scaleY(var(--escala)); }
            50% { transform: translateX(-50%) scaleY(var(--escala) * 1.1); }
        }
        
        /* INDICADORES */
        .stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            border-radius: 15px;
            border-left: 5px solid #667eea;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-label {
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
            margin-top: 8px;
        }
        
        .stat-unit {
            font-size: 0.8em;
            color: #999;
            margin-left: 5px;
        }
        
        /* Estado General */
        .status-section {
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
            transition: all 0.3s ease;
        }
        
        .status-icon {
            font-size: 3em;
            margin-bottom: 10px;
        }
        
        .status-text {
            font-size: 1.8em;
            font-weight: bold;
        }
        
        .status-desc {
            font-size: 0.9em;
            opacity: 0.9;
            margin-top: 8px;
        }
        
        /* Chart */
        .chart-section {
            margin-top: 30px;
            background: #f9f9f9;
            padding: 20px;
            border-radius: 15px;
        }
        
        .chart-section h3 {
            color: #333;
            margin-bottom: 15px;
        }
        
        canvas {
            display: block;
            margin: 0 auto;
        }
        
        .timestamp {
            text-align: center;
            color: #999;
            font-size: 0.85em;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌱 Maceta Inteligente</h1>
        
        <div class="main-grid">
            <!-- BALCÓN -->
            <div class="balcon-container">
                <div class="balcon">
                    <div class="cielo manana"></div>
                    <div class="suelo"></div>
                    
                    <div class="maceta-wrapper">
                        <div class="maceta">
                            <div class="tierra"></div>
                        </div>
                        <div class="planta ok" id="planta">
                            <div class="hoja hoja-izq"></div>
                            <div class="hoja hoja-der"></div>
                            <div class="hoja hoja-top"></div>
                            <div class="tallo"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- INDICADORES -->
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-label">💧 Humedad</div>
                    <div class="stat-value">
                        <span id="humedad">0</span><span class="stat-unit">%</span>
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-label">🌡️ Temperatura</div>
                    <div class="stat-value">
                        <span id="temp">0</span><span class="stat-unit">°C</span>
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-label">☀️ Luz</div>
                    <div class="stat-value">
                        <span id="luz">0</span><span class="stat-unit">%</span>
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-label">⏰ Hora</div>
                    <div class="stat-value">
                        <span id="hora">--:--</span>
                    </div>
                </div>
                
                <div class="status-section">
                    <div class="status-icon" id="status-icon">🌿</div>
                    <div class="status-text" id="status-text">PLANTA OK</div>
                    <div class="status-desc" id="status-desc">Condiciones óptimas</div>
                </div>
            </div>
        </div>
        
        <!-- GRÁFICO -->
        <div class="chart-section">
            <h3>📊 Histórico (últimos 2 minutos)</h3>
            <canvas id="chart"></canvas>
            <div class="timestamp" id="timestamp">Conectando...</div>
        </div>
    </div>
    
    <script>
        let chart = null;
        
        // Estado visual por clase
        const ESTADOS = {
            0: {
                icon: '🌿',
                text: 'PLANTA OK',
                desc: 'Condiciones óptimas',
                clase: 'ok'
            },
            1: {
                icon: '💧',
                text: 'NECESITA RIEGO',
                desc: 'Humedad muy baja',
                clase: 'riego'
            },
            2: {
                icon: '☀️',
                text: 'DEMASIADO SOL',
                desc: 'Luz y temperatura altas',
                clase: 'sol'
            }
        };
        
        // Ciclos del día
        const CICLOS = [
            { hora: 6, clase: 'manana' },
            { hora: 12, clase: 'tarde' },
            { hora: 18, clase: 'noche' }
        ];
        
        function getCiclo() {
            const hora = new Date().getHours();
            if (hora >= 6 && hora < 12) return 'manana';
            if (hora >= 12 && hora < 18) return 'tarde';
            return 'noche';
        }
        
        async function actualizarDatos() {
            try {
                const res = await fetch('/api/sensor-data');
                const data = await res.json();
                
                // Actualizar indicadores
                document.getElementById('humedad').textContent = data.humedad;
                document.getElementById('temp').textContent = data.temp.toFixed(1);
                document.getElementById('luz').textContent = data.luz;
                document.getElementById('hora').textContent = new Date().toLocaleTimeString('es-ES', {hour: '2-digit', minute: '2-digit'});
                
                // Actualizar estado visual
                const estado = ESTADOS[data.clase];
                document.getElementById('planta').className = 'planta ' + estado.clase;
                document.getElementById('status-icon').textContent = estado.icon;
                document.getElementById('status-text').textContent = estado.text;
                document.getElementById('status-desc').textContent = estado.desc;
                
                // Ciclo día/noche
                document.querySelector('.cielo').className = 'cielo ' + getCiclo();
                
                // Timestamp
                document.getElementById('timestamp').textContent = 'Actualizado: ' + new Date().toLocaleTimeString('es-ES');
                
            } catch (e) {
                document.getElementById('timestamp').textContent = 'Conectando...';
            }
        }
        
        // Inicializar gráfico
        const ctx = document.getElementById('chart').getContext('2d');
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Humedad (%)',
                        data: [],
                        borderColor: '#4169E1',
                        backgroundColor: 'rgba(65, 105, 225, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Temperatura (°C)',
                        data: [],
                        borderColor: '#FF6B6B',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Luz (%)',
                        data: [],
                        borderColor: '#FFD700',
                        backgroundColor: 'rgba(255, 215, 0, 0.1)',
                        tension: 0.4,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: { min: 0, max: 100 }
                }
            }
        });
        
        async function actualizarGrafico() {
            try {
                const res = await fetch('/api/history');
                const history = await res.json();
                
                chart.data.labels = history.timestamp.slice(-120);
                chart.data.datasets[0].data = history.humedad.slice(-120);
                chart.data.datasets[1].data = history.temp.slice(-120);
                chart.data.datasets[2].data = history.luz.slice(-120);
                chart.update();
            } catch (e) {}
        }
        
        // Actualizar cada 500ms
        setInterval(actualizarDatos, 500);
        setInterval(actualizarGrafico, 1000);
        
        actualizarDatos();
        actualizarGrafico();
    </script>
</body>
</html>
"""
```

**Instalación y ejecución:**

```bash
# Instalar dependencias
pip install flask pyserial chart.js

# Ejecutar servidor
python dashboard_server.py

# Abre automáticamente en http://localhost:5000
```

---

## 5. Arquitectura del Firmware

### 5.1 Estructura general del programa

```
main()
  │
  ├── init_system()          // Configura oscilador, puertos, ADC, UART, LCD
  │
  ├── load_weights_eeprom()  // Lee pesos guardados (o usa defaults)
  │
  └── loop infinito
        │
        ├── leer_sensores()       // 3 lecturas ADC
        │
        ├── normalizar_entradas() // Escala los ADC a rango del perceptrón
        │
        ├── inferencia()          // Suma ponderada + activación
        │
        ├── actualizar_display()  // LCD con valores y clase
        │
        ├── actualizar_leds()     // LED según clase
        │
        ├── enviar_uart()         // Stream de datos a PC
        │
        └── recibir_uart()        // ¿Llegaron nuevos pesos?
```

### 5.2 Máquina de estados del sistema

```
                    ┌──────────────────┐
         inicio ──→ │  MODO NORMAL     │ ←── tecla #
                    │  (inferencia)    │
                    └────────┬─────────┘
                             │ tecla *
                    ┌────────▼─────────┐
                    │  MODO CONFIG     │
                    │  (ajustar pesos  │
                    │   manualmente)   │
                    └────────┬─────────┘
                             │ tecla *
                    ┌────────▼─────────┐
                    │  MODO UART       │
                    │  (esperar pesos  │
                    │   desde PC)      │
                    └──────────────────┘
```

---

## 6. Módulos de Software (Implementación en Assembly)

### 6.1 Módulo ADC (Assembly)

```asm
;=======================================================
; ADC.ASM - Lectura de canales analógicos
;=======================================================

; Configuración del ADC
ADC_Init:
    ; ADCON1: VREF = VCC, formato justificado derecha
    MOVLW   0x80
    MOVWF   ADCON1
    
    ; ADCON0: Canal AN0, ADC ON
    MOVLW   0x01
    MOVWF   ADCON0
    
    ; ADCON2: Fosc/4, 12 TAD
    MOVLW   0xA9
    MOVWF   ADCON2
    
    RETURN

; Lee canal ADC especificado en W
; Retorna valor 10 bits en ADRESH:ADRESL
ADC_Read:
    ; W contiene número de canal (0-2)
    MOVWF   temp_channel
    
    ; Limpiar bits de selección de canal
    MOVF    ADCON0, W
    ANDLW   0xC5        ; Mantener otros bits
    MOVWF   ADCON0
    
    ; Insertar nuevo canal
    MOVF    temp_channel, W
    MOVWF   ADCON0        ; ADCON0 |= (channel << 2)
    
    ; Tiempo de adquisición
    MOVLW   0x0A
    MOVWF   contador
loop_acq:
    DECFSZ  contador, F
    GOTO    loop_acq
    
    ; Iniciar conversión
    BSF     ADCON0, GO_DONE
    
    ; Esperar fin de conversión
loop_conv:
    BTFSC   ADCON0, GO_DONE
    GOTO    loop_conv
    
    ; Retorna con ADRESH:ADRESL listos
    RETURN

temp_channel    RES 1
contador        RES 1
```


### 6.2 Módulo Sensores (Assembly)

```asm
;=======================================================
; SENSORS.ASM - Lectura de tres sensores
;=======================================================

read_sensors:
    ; Leer Higrómetro (AN0)
    MOVLW   0x00
    CALL    ADC_Read
    MOVF    ADRESL, W
    MOVWF   sensor_humedad_L
    MOVF    ADRESH, W
    MOVWF   sensor_humedad_H
    
    ; Delay entre lecturas
    MOVLW   0x05
    CALL    Delay_ms
    
    ; Leer LM35 (AN1)
    MOVLW   0x01
    CALL    ADC_Read
    MOVF    ADRESL, W
    MOVWF   sensor_temp_L
    MOVF    ADRESH, W
    MOVWF   sensor_temp_H
    
    MOVLW   0x05
    CALL    Delay_ms
    
    ; Leer LDR (AN2)
    MOVLW   0x02
    CALL    ADC_Read
    MOVF    ADRESL, W
    MOVWF   sensor_luz_L
    MOVF    ADRESH, W
    MOVWF   sensor_luz_H
    
    RETURN

sensor_humedad_L    RES 1
sensor_humedad_H    RES 1
sensor_temp_L       RES 1
sensor_temp_H       RES 1
sensor_luz_L        RES 1
sensor_luz_H        RES 1
```


### 6.3 Módulo Perceptrón (Assembly - Punto Fijo)

```asm
;=======================================================
; PERCEPTRON.ASM - Inferencia en punto fijo
; Todo escalado ×1000 para mantener precisión
;=======================================================

; Pesos (punto fijo ×1000)
W_HUMEDAD   EQU 752       ; Peso humedad
W_TEMP      EQU 180       ; Peso temperatura
W_LUZ       EQU 95        ; Peso luz
BIAS        EQU 500       ; Bias del perceptrón

; Parámetros de normalización
MEAN_H      EQU 5000      ; Media humedad ×10
SCALE_H     EQU 2000      ; Escala humedad ×10
MEAN_T      EQU 220       ; Media temperatura ×10
SCALE_T     EQU 50        ; Escala temperatura ×10
MEAN_L      EQU 5000      ; Media luz ×10
SCALE_L     EQU 3000      ; Escala luz ×10

inferencia:
    ; Normalizar humedad: (x - media) / escala
    ; x_norm_h = ((sensor_humedad * 10 - MEAN_H) * 1000) / SCALE_H
    
    MOVF    sensor_humedad_L, W
    MOVWF   x_raw
    
    ; Restar media
    MOVLW   MEAN_H & 0xFF
    SUBWF   x_raw, F
    
    ; Multiplicar por 1000 (en 16 bits)
    MOVF    x_raw, W
    MOVWF   multiplicand_L
    CLRF    multiplicand_H
    
    MOVLW   LOW(1000)
    MOVWF   multiplier_L
    MOVLW   HIGH(1000)
    MOVWF   multiplier_H
    
    CALL    Mult16x16    ; Resultado en prod_H:prod_M:prod_L
    
    ; Dividir por SCALE_H
    MOVLW   SCALE_H & 0xFF
    MOVWF   divisor
    CALL    Div24by8
    
    MOVF    quotient_H, W
    MOVWF   x_norm_h
    
    ; Similarmente: normalizar temp y luz
    ; (Code para x_norm_t y x_norm_l)
    
    ; Suma ponderada: z = w_h * x_h + w_t * x_t + w_l * x_l + bias
    
    CLRF    z_H
    CLRF    z_L
    
    ; z += W_HUMEDAD * x_norm_h
    MOVF    x_norm_h, W
    MOVWF   multiplicand_L
    CLRF    multiplicand_H
    
    MOVLW   W_HUMEDAD
    MOVWF   multiplier_L
    CLRF    multiplier_H
    
    CALL    Mult16x16
    
    ; Sumar a z
    MOVF    prod_L, W
    ADDWF   z_L, F
    MOVF    prod_M, W
    ADDWFC  z_H, F
    
    ; ... similarmente para w_temp * x_norm_t y w_luz * x_norm_l
    
    ; Agregar bias
    MOVLW   BIAS & 0xFF
    ADDWF   z_L, F
    MOVLW   BIAS >> 8
    ADDWFC  z_H, F
    
    ; Activación: si z >= 0 → clase = 1, sino clase = 0
    BTFSC   z_H, 7       ; Bit de signo de z_H
    GOTO    clase_cero
    
    MOVLW   1
    MOVWF   clase
    GOTO    inf_done
    
clase_cero:
    CLRF    clase
    
inf_done:
    RETURN

x_raw           RES 1
x_norm_h        RES 1
x_norm_t        RES 1
x_norm_l        RES 1
z_H             RES 1
z_L             RES 1
clase           RES 1
multiplicand_L  RES 1
multiplicand_H  RES 1
multiplier_L    RES 1
multiplier_H    RES 1
prod_L          RES 1
prod_M          RES 1
prod_H          RES 1
```


### 6.4 Módulo LCD (Assembly)

```asm
;=======================================================
; LCD.ASM - Control de LCD 16x2 (modo 4 bits)
;=======================================================

LCD_Init:
    ; Configurar PORTD como salida
    CLRF    TRISD
    
    ; Inicialización HD44780 (3 veces 8 bits, luego cambiar a 4 bits)
    MOVLW   0x33
    CALL    LCD_Send8
    MOVLW   0x05
    CALL    Delay_ms
    
    CALL    LCD_Send8
    MOVLW   0x05
    CALL    Delay_ms
    
    CALL    LCD_Send8
    MOVLW   0x05
    CALL    Delay_ms
    
    ; Cambiar a modo 4 bits
    MOVLW   0x22
    CALL    LCD_Send8
    
    ; Configuración
    MOVLW   0x28    ; 4 bits, 2 líneas
    CALL    LCD_WriteCmd
    
    MOVLW   0x0C    ; Display ON, cursor OFF
    CALL    LCD_WriteCmd
    
    CALL    LCD_Clear
    
    RETURN

LCD_Clear:
    MOVLW   0x01
    CALL    LCD_WriteCmd
    MOVLW   0x02    ; Delay para Clear
    CALL    Delay_ms
    RETURN

LCD_WriteCmd:
    BCF     RC0     ; RS = 0 (comando)
    CALL    LCD_Write4bit
    RETURN

LCD_WriteChar:
    BSF     RC0     ; RS = 1 (dato)
    CALL    LCD_Write4bit
    RETURN

LCD_Write4bit:
    ; Enviar nibble alto
    MOVWF   lcd_data
    ANDLW   0xF0
    IORWF   PORTD, F
    
    ; Pulso EN
    BSF     RC1
    CALL    LCD_Delay
    BCF     RC1
    CALL    LCD_Delay
    
    ; Enviar nibble bajo
    MOVF    lcd_data, W
    SWAPF   W, W
    ANDLW   0xF0
    IORWF   PORTD, F
    
    ; Pulso EN
    BSF     RC1
    CALL    LCD_Delay
    BCF     RC1
    CALL    LCD_Delay
    
    RETURN

LCD_Delay:
    MOVLW   0x10
    MOVWF   delay_counter
lcd_delay_loop:
    DECFSZ  delay_counter, F
    GOTO    lcd_delay_loop
    RETURN

lcd_data        RES 1
delay_counter   RES 1
```


### 6.5 Módulo UART (Assembly)

```asm
;=======================================================
; UART.ASM - Comunicación serie con PC
;=======================================================

UART_Init:
    ; Baudrate 9600 bps con Fosc=4MHz: SPBRG = 25
    MOVLW   25
    MOVWF   SPBRG
    
    ; TXSTA: TX habilitado, modo asíncrono
    MOVLW   0x24
    MOVWF   TXSTA
    
    ; RCSTA: RX habilitado
    MOVLW   0x90
    MOVWF   RCSTA
    
    RETURN

UART_SendByte:
    ; W contiene byte a enviar
    MOVWF   TXREG
    
wait_tx:
    BTFSS   TXIF
    GOTO    wait_tx
    
    RETURN

UART_SendString:
    ; FSR apunta a string terminado en NULL
    MOVF    INDF, W
    BTFSC   STATUS, Z       ; Si es NULL, fin
    RETURN
    
    CALL    UART_SendByte
    INCF    FSR, F
    GOTO    UART_SendString

UART_SendData:
    ; Enviar formato: H:820,T:285,L:600,C:1
    ; Este es pseudocódigo; en Assembly puro se hace carácter a carácter
    
    MOVLW   'H'
    CALL    UART_SendByte
    MOVLW   ':'
    CALL    UART_SendByte
    
    ; Enviar valor de humedad (3 dígitos)
    MOVF    sensor_humedad_H, W
    CALL    UART_SendHex
    
    ; ... continuar con otros valores
    
    MOVLW   0x0D    ; CR
    CALL    UART_SendByte
    MOVLW   0x0A    ; LF
    CALL    UART_SendByte
    
    RETURN
```


### 6.6 Módulo EEPROM (Assembly)

```asm
;=======================================================
; EEPROM.ASM - Lectura/escritura de EEPROM de datos
;=======================================================

EEPROM_Write:
    ; W = dirección
    ; Valor en reg_to_write
    MOVWF   EEADR
    MOVF    reg_to_write, W
    MOVWF   EEDATA
    
    ; EECON1: WREN = 1
    MOVLW   0x04
    MOVWF   EECON1
    
    ; Secuencia de desbloqueo requerida
    MOVLW   0x55
    MOVWF   EECON2
    MOVLW   0xAA
    MOVWF   EECON2
    
    ; WR = 1
    BSF     EECON1, WR
    
    ; Esperar a que termine
ee_wait:
    BTFSC   EECON1, WR
    GOTO    ee_wait
    
    RETURN

EEPROM_Read:
    ; W = dirección
    MOVWF   EEADR
    
    ; RD = 1
    MOVLW   0x01
    MOVWF   EECON1
    
    ; Esperar (máximo 1-2 ciclos)
    NOP
    NOP
    
    ; Resultado en EEDATA
    MOVF    EEDATA, W
    
    RETURN

reg_to_write    RES 1
```

### 6.7 Programa Principal (Main.asm)

```asm
;=======================================================
; MAIN.ASM - Programa principal
;=======================================================

    INCLUDE "p16f887.inc"
    __CONFIG _FOSC_XT & _WDTE_OFF & _PWRTE_ON & _MCLRE_ON

    #DEFINE _XTAL_FREQ 4000000
    CBLOCK 0x20
        sensor_humedad_L
        sensor_humedad_H
        sensor_temp_L
        sensor_temp_H
        sensor_luz_L
        sensor_luz_H
        clase
        ; ... otros registros
    ENDCBLOCK

    ORG 0
    GOTO    main
    
    ORG 4
    RETFIE

main:
    ; Inicializar sistema
    CALL    ADC_Init
    CALL    LCD_Init
    CALL    UART_Init
    
    ; Mostrar mensaje inicial
    CALL    LCD_Clear
    
    ; Loop principal
main_loop:
    ; Leer sensores
    CALL    read_sensors
    
    ; Inferencia
    CALL    inferencia
    
    ; Mostrar en LCD
    CALL    LCD_UpdateDisplay
    
    ; Actualizar LEDs
    CALL    UpdateLEDs
    
    ; Enviar por UART
    CALL    UART_SendData
    
    ; Delay
    MOVLW   100
    CALL    Delay_ms
    
    GOTO    main_loop

End
```

### 6.8 Herramientas y Compilación

**Editor de Assembly para PIC:**
- MPLAB X IDE (Microchip) - Oficial
- Ensamblador: MPASM (Microchip Assembler)
- Compilación: `mpasm.exe main.asm -l main.lst`
- Programación: PICKit 3 + MicroChip IPEPROGRAMMER

**Flujo de desarrollo:**
```
codigo.asm → MPASM → codigo.hex → PICKit 3 → PIC16F887
```

---

## 7. Comunicación UART

### 7.1 Protocolo definido

**PIC → PC (telemetría cada 1 segundo):**
```
H:820,T:285,L:300,C:1\r\n
│     │     │     └── Clase (0=OK, 1=RIEGO, 2=SOL)
│     │     └──────── Luz (ADC raw 0-1023)
│     └────────────── Temperatura × 10 (285 = 28.5°C)
└──────────────────── Humedad suelo (ADC raw 0-1023)
```

**PC → PIC (cargar nuevos pesos):**
```
W:-850,120,90,-400,750,900,500,-400\r\n
│  w_hum_riego
│        w_temp_riego
│              w_luz_riego
│                    bias_riego
│                          w_hum_sol
│                                ...
```

**PIC responde:**
```
OK:PESOS_GUARDADOS\r\n
```

### 7.2 Configuración del puerto serie en PC

| Parámetro | Valor |
|---|---|
| Baudrate | 9600 |
| Data bits | 8 |
| Stop bits | 1 |
| Paridad | Ninguna |
| Flow control | Ninguno |

Se puede usar: **PuTTY**, **Arduino Serial Monitor**, o el **script Python monitor.py**.

---

## 8. Integración y Pruebas

### 8.1 Plan de pruebas por módulo

| Módulo | Prueba | Criterio de éxito |
|---|---|---|
| ADC | Medir V en RA0 con multímetro vs valor ADC | Error < 2% |
| Sensores | Calentar LM35 con la mano, ver si sube | Responde en < 2s |
| LCD | Mostrar "HOLA" en pantalla | Sin caracteres raros |
| UART | Mandar string y ver en PuTTY | Recibe correcto |
| EEPROM | Escribir valor, apagar, leer | Persiste el valor |
| Perceptrón | Valores extremos de sensores → clase esperada | 100% en casos extremos |
| Integración | Sistema completo corriendo 10 min | Sin cuelgues |

### 8.2 Casos de prueba del perceptrón

| Humedad | Temperatura | Luz | Clase esperada |
|---|---|---|---|
| 950 (muy seca) | 22°C | 400 | NECESITA RIEGO |
| 300 (húmeda) | 38°C | 950 | DEMASIADO SOL |
| 400 (normal) | 22°C | 500 | OK |
| 900 (seca) | 40°C | 950 | NECESITA RIEGO (prioridad) |

### 8.3 Demo para la entrega

1. Mostrar sistema en MODO NORMAL con planta real
2. Secar artificialmente el sensor (sacarlo de la tierra) → debe aparecer RIEGO
3. Apuntar una lámpara fuerte → debe aparecer SOL
4. Mostrar en PC la gráfica de telemetría en tiempo real
5. Desde PC, mandar nuevos pesos y mostrar que el sistema los acepta y se comporta diferente

---

## 9. Plan de Trabajo Semana a Semana

### Semana 1 — Hardware y módulos básicos

| Día | Tarea |
|---|---|
| Lunes | Armar circuito en protoboard: PIC + crystal + regulador de tensión. Probar que prende con LED blink. |
| Martes | Conectar LCD, probar módulo LCD (escribir texto). |
| Miércoles | Conectar sensores (LM35, LDR, Higrómetro). Probar módulo ADC con display. |
| Jueves | Conectar UART (CP2102/MAX232). Probar módulo UART con PuTTY. |
| Viernes | Conectar teclado matricial. Probar lectura de teclas con LCD. |
| Fin de semana | Integrar todos los módulos básicos. Leer sensores y mostrar en LCD. |

### Semana 2 — Dataset, entrenamiento y firmware en Assembly

| Día | Tarea |
|---|---|
| Lunes | Escribir script Python de telemetría. Recolectar datos: 50% sintéticos (generados) + 50% reales con sensores. |
| Martes | Entrenar perceptrón en Python (sklearn). Evaluar accuracy. Exportar pesos a constantes Assembly. |
| Miércoles | Implementar módulos ADC, Sensores y UART en Assembly. Probar lectura de sensores. |
| Jueves | Implementar módulo Perceptrón en Assembly (punto fijo ×1000). Compilar con MPASM. Probar inferencia. |
| Viernes | Implementar EEPROM: guardar y cargar pesos entre resets en Assembly. |
| Fin de semana | Integrar perceptrón con sensores reales en Assembly. Validar clasificación correcta. |

### Semana 3 — Interfaz web, pulido y presentación

| Día | Tarea |
|---|---|
| Lunes | Generar página HTML con maceta animada (Flask + JavaScript). Conectar con datos del UART. |
| Martes | Implementar ciclo día/noche según hora del PC en la interfaz web. Cambios visuales de la maceta. |
| Miércoles | Script Python que abre HTML automáticamente desde UART. Gráfica en tiempo real de sensores. |
| Jueves | Pruebas finales: Assembly compilando correctamente, HTML cambiando de estado, pesos cargables. |
| Viernes | Redacción del informe técnico. Capturas de pantalla del HTML y datos en PC. |
| Fin de semana | Presentación, ensayo de la demo completa (hardware → firmware → interfaz web). |

---

## 10. Estructura del Informe

### Secciones recomendadas

**1. Introducción**
- Motivación del proyecto
- Objetivo general y objetivos específicos
- Alcance del trabajo

**2. Marco Teórico**
- El perceptrón de Rosenblatt (1957)
- Aritmética de punto fijo en microcontroladores
- Sensores utilizados (principio de funcionamiento)
- Protocolo UART

**3. Diseño del Hardware**
- Diagrama esquemático completo
- Justificación de la elección de cada componente
- Tabla de asignación de pines

**4. Pipeline de Entrenamiento (PC)**
- Estrategia de recolección: datos sintéticos + datos reales
- Proceso de normalización
- Código de entrenamiento (sklearn Perceptron)
- Métricas obtenidas (accuracy, confusion matrix)
- Exportación de pesos a formato Assembly (punto fijo ×1000)

**5. Diseño del Firmware (Assembly)**
- Arquitectura general (diagrama de bloques)
- Descripción de cada módulo en Assembly
- Implementación de aritmética de punto fijo (×1000)
- Operaciones críticas: multiplicación 16×16, división en enteros
- Optimizaciones para Assembly 8 bits
- Compilación con MPASM

**6. Interfaz Web Interactiva**
- Dashboard HTML con maceta animada
- Cambios visuales según estado (OK, RIEGO, SOL)
- Ciclo día/noche sincronizado con reloj del PC
- Gráficas en tiempo real de sensores
- Servidor Flask para comunicación PC ↔ Navegador ↔ UART

**7. Resultados**
- Tabla de pruebas del clasificador
- Capturas de pantalla del HTML en diferentes estados
- Gráficas de telemetría en tiempo real
- Comparación: predicción vs valor esperado
- Ejemplo de carga de nuevos pesos desde PC

**8. Conclusiones**
- Qué funcionó, qué no
- Limitaciones del perceptrón lineal
- Limitaciones de Assembly 8 bits (velocidad, tamaño de Flash)
- Ventajas de punto fijo vs punto flotante en microcontroladores
- Posibles mejoras (red multicapa, más sensores, etc.)
- Viabilidad de Machine Learning en PICs

**9. Referencias**
- Datasheet PIC16F887 (Microchip)
- Rosenblatt, F. (1957). The Perceptron: A Perceiving and Recognizing Automaton.
- Datasheet LM35, FC-28
- Documentación sklearn
- MPLAB X IDE - PIC Assembly Development Guide
- PIC16F887 Instruction Set (Microchip)
- Hardware Design Considerations for Fixed-Point Arithmetic

---

## Recursos útiles

| Recurso | Link / Referencia |
|---|---|
| Datasheet PIC16F887 | microchip.com → PIC16F887 |
| MPLAB X IDE | microchip.com/mplab |
| MPASM Assembler | Incluido en MPLAB X |
| PICKit 3 Programmer | microchip.com/development-tools |
| sklearn Perceptron | scikit-learn.org/stable/modules/generated/sklearn.linear_model.Perceptron |
| pySerial | pip install pyserial |
| Flask Web Framework | pip install flask |
| Proteus (simulación) | labcenter.com |
| Assembly Language for PIC | microchip.com/development-tools/pic-mcu-series |

---

*Documento generado como plan de implementación para TP Final — Electrónica Digital 2*
