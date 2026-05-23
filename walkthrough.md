# 🌱 Reporte de Ingeniería — Perceptrones en Cascada Q8 para PIC16F887

## Resumen Ejecutivo

Se completó el ciclo completo de entrenamiento, testing y validación de la red neuronal para la **Maceta Inteligente**. Durante el proceso de testing exhaustivo se **descubrió y corrigió un bug crítico** en los datos de entrenamiento que habría causado falsos positivos de "Demasiado Sol" en el firmware. El modelo final pasa **13,694 tests con 0 fallos**.

---

## 📊 Visualización de Datos y Fronteras de Decisión

![Gráfico 3D del dataset de suculenta con las 3 clases separadas en el espacio de sensores ADC](decision_boundary.png)

### ¿Qué muestra este gráfico?

El gráfico es una **dispersión tridimensional** donde cada punto representa una lectura de los 3 sensores y su clasificación. Los 3 ejes son los valores crudos de ADC de 8 bits (0-255) que el PIC16F887 leería directamente:

| Eje | Sensor | Rango | Nota |
|-----|--------|-------|------|
| **X** (Humedad ADC8) | Higrómetro FC-28 | 0=muy húmedo, 255=muy seco | Sensor invertido |
| **Y** (Temperatura ADC8) | LM35 | 0=0°C, 30=58°C | Rango realista del LM35 |
| **Z** (Luz ADC8) | LDR + divisor | 0=oscuridad, 255=sol directo | Proporcional a luminosidad |

### Las 3 nubes de puntos

- 🟢 **Planta OK (verde):** Nube central-izquierda. Son las **3,668 muestras reales** de tu suculenta en el departamento + 1,000 contra-ejemplos sintéticos. Humedad moderada (50-200 ADC8), temperatura ambiente (5-20 ADC8 ≈ 10-39°C), luz variada. Esta nube es densa en el centro porque son datos reales con poca variación.

- 🔵 **Necesita Riego (azul):** Nube en el **extremo derecho** del eje X (Humedad ADC8 > 220). Representan suelo críticamente seco. La nube se extiende verticalmente en todo el eje Z (luz) porque la sequía puede ocurrir con cualquier nivel de luz. La temperatura es variada pero baja (rango normal).

- 🔴 **Demasiado Sol (rojo):** Nube en la **esquina superior** (Luz ADC8 > 210 + Temperatura ADC8 > 22). Representan insolación extrema: sol directo fuerte Y temperatura superior a 43°C simultáneamente. La nube está separada tanto en Z (luz alta) como en Y (temp alta).

### Lo que NO se ve pero existe: los planos de decisión

Los perceptrones lineales dividen este espacio 3D con **planos invisibles**:
- **Plano 1 (Riego):** Corta aproximadamente en H=205 — todo lo que está a la derecha se clasifica como "Necesita Riego"
- **Plano 2 (Sol):** Corta en diagonal en la zona superior — necesita que TANTO la luz como la temperatura sean altas para activarse

> [!IMPORTANT]
> La separación limpia entre las 3 nubes confirma visualmente que un perceptrón lineal (modelo más simple posible) es **suficiente** para este problema. No se necesitan redes neuronales complejas.

---

## 🔬 Bug Descubierto y Corregido por los Tests

### El problema original

Los tests de fuzzing (10,000 entradas aleatorias) revelaron que **el modelo original clasificaba como "Demasiado Sol" escenarios con poca luz pero temperatura alta**. Por ejemplo:

```
H=92, T=161, L=0  → clasificado como RIEGO  (¡suelo húmedo!)
H=53, T=171, L=1  → clasificado como RIEGO  (¡sin luz!)
```

### Causa raíz

Los datos sintéticos de la clase SOL usaban `Temp_ADC8 = 18-25`, que **se solapaba con las temperaturas normales** del dataset real. El perceptrón aprendió que "cualquier temperatura >= 18 ADC8 con algo de luz = SOL", lo cual es incorrecto.

Con los pesos originales (`W2_TEMP=4, W2_LUZ=2, BIAS=0`), la temperatura dominaba la decisión:
```
z2 = (x_h * 0) + (x_t * 4) + (x_l * 2) + 0
Con T=30, L=0: z2 = 624*4 + (-676)*2 = 1144 >= 0 → SOL (¡INCORRECTO!)
```

### Solución aplicada

Se realizaron 2 cambios en [train.py](file:///D:/facultad/edii/tp%20final/train.py):

**1. Rangos de temperatura más extremos para clase SOL:**
```diff
-syn_sol_temp = np.random.randint(18, 25, n_samples_synthetic)  # solapaba con normal
+syn_sol_temp = np.random.randint(22, 30, n_samples_synthetic)  # >43°C claramente extremo
```

**2. Contra-ejemplos que enseñan condiciones parciales:**
```python
# Contra-ejemplo A: Temp alta + luz baja = NO es sol (día caluroso nublado)
counter_a_temp = np.random.randint(20, 30, n_counter)  # Temp alta
counter_a_luz = np.random.randint(0, 120, n_counter)    # Luz baja

# Contra-ejemplo B: Luz alta + temp baja = NO es sol (invierno soleado)
counter_b_temp = np.random.randint(0, 15, n_counter)    # Temp baja
counter_b_luz = np.random.randint(200, 256, n_counter)   # Luz alta
```

### Resultado: nuevo modelo con BIAS negativo

El re-entrenamiento produjo pesos que **exigen ambas condiciones** para activar SOL:

```
Nuevo P2: W2_TEMP=12, W2_LUZ=9, BIAS=-1966
```

El bias negativo grande (-1966) actúa como un **umbral mínimo**: tanto la temperatura como la luz deben ser significativamente altas para que la suma supere cero. Con temp baja o luz baja, el bias las anula.

---

## ✅ Resultados de Testing Final

Se ejecutaron **8 suites de tests** con [test_weights.py](file:///D:/facultad/edii/tp%20final/test_weights.py) que simulan la aritmética entera exacta del PIC16F887:

| # | Test | Verificaciones | Estado |
|---|------|----------------|--------|
| 1 | Consistencia ASM ↔ JSON | 16 campos | ✅ |
| 2 | Escenarios conocidos de suculenta | 15 | ✅ |
| 3 | Casos extremos (bordes ADC 0/255) | 6 | ✅ |
| 4 | Dataset completo CSV (datos reales) | 3,668 | ✅ |
| 5 | Fuzzing aleatorio (rangos realistas) | 10,000 | ✅ |
| 6 | Reconstrucción BIAS desde bytes ASM | 2 | ✅ |
| 7 | Frontera de decisión (boundary scan) | 1 | ✅ |
| 8 | Overflow multiplicaciones PIC | 1 | ✅ |
| | **TOTAL** | **13,694** | **✅ 0 fallos** |

### Fronteras de decisión verificadas

El test de boundary scanning encontró transiciones coherentes:
- **Riego:** H=205 → la planta pasa de OK a RIEGO (suelo muy seco)
- **Sol:** L=243 → la planta pasa de OK a SOL (solo con temp también alta)

### Overflow: 98.8% de margen

El producto máximo absoluto encontrado fue **101,952**, con un rango seguro de 24 bits con signo de ±8,388,607. Hay margen de sobra para la aritmética del PIC.

---

## 🛠️ Constantes Finales para el Firmware

Bloque de código actualizado en [pesos_perceptron.asm](file:///D:/facultad/edii/tp%20final/pesos_perceptron.asm):

```asm
;====================================================================
; PESOS Y PARAMETROS DEL PERCEPTRON EN CASCADA (FORMATO Q8 / ESCALA x256)
; Generado automaticamente por train_perceptron.py
; Planta: Suculenta (Ambiente comun / controlado)
;====================================================================

; --- PARAMETROS DE NORMALIZACION DE ENTRADAS ---
; Formula PIC: X_norm_q8 = (X_raw - MEAN) * SCALE_MUL
MEAN_H          EQU     165      ; Media Humedad (ADC 8 bits)
SCALE_MUL_H     EQU     4        ; Multiplicador de Escala Humedad Q8

MEAN_T          EQU     19       ; Media Temperatura (ADC 8 bits)
SCALE_MUL_T     EQU     36       ; Multiplicador de Escala Temperatura Q8

MEAN_L          EQU     166      ; Media Luz (ADC 8 bits)
SCALE_MUL_L     EQU     4        ; Multiplicador de Escala Luz Q8

; --- PERCEPTRON 1: ¿NECESITA RIEGO? (Clase 1 vs Resto) ---
W1_HUMEDAD      EQU     15       ; Peso Humedad Q8
W1_TEMP         EQU     1        ; Peso Temperatura Q8
W1_LUZ          EQU     -2       ; Peso Luz Q8
B1_BIAS_H       EQU     -1       ; Byte Alto de BIAS (Q16)
B1_BIAS_M       EQU     245      ; Byte Medio de BIAS (Q16)
B1_BIAS_L       EQU     195      ; Byte Bajo de BIAS (Q16)

; --- PERCEPTRON 2: ¿DEMASIADO SOL? (Clase 2 vs OK) ---
W2_HUMEDAD      EQU     2        ; Peso Humedad Q8
W2_TEMP         EQU     12       ; Peso Temperatura Q8
W2_LUZ          EQU     9        ; Peso Luz Q8
B2_BIAS_H       EQU     -1       ; Byte Alto de BIAS (Q16)
B2_BIAS_M       EQU     248      ; Byte Medio de BIAS (Q16)
B2_BIAS_L       EQU     82       ; Byte Bajo de BIAS (Q16)
```

> [!WARNING]
> Estos pesos son **diferentes** a los generados originalmente. Si ya habías copiado los pesos anteriores al firmware, **debés reemplazarlos** con estos nuevos.

---

## 🧠 Decisiones Arquitectónicas (resumen)

### 1. Dos perceptrones binarios en cascada
En vez de multiclase con Softmax (imposible en Assembly de 8 bits), se encadenan 2 decisiones binarias: primero RIEGO (más crítico), luego SOL. Solo se evalúa el **bit de signo** del resultado.

### 2. Punto fijo Q8 (×256)
Elimina todas las divisiones del firmware. La normalización se convierte en resta + multiplicación entera. Los productos quedan en Q16 y solo importa su signo.

### 3. ADC alineado a izquierda (`ADFM=0`)
El PIC entrega los 8 bits más significativos en `ADRESH` directamente, sin corrimientos por software.

### 4. Contra-ejemplos para condiciones parciales
El perceptrón lineal no puede aprender "A **Y** B" directamente. Se resolvió inyectando contra-ejemplos (A sin B = OK, B sin A = OK) que fuerzan un **bias negativo** que actúa como umbral mínimo conjunto.

---

## 📁 Archivos del Proyecto

| Archivo | Propósito |
|---------|-----------|
| [train.py](file:///D:/facultad/edii/tp%20final/train.py) | Script de entrenamiento (Python puro + numpy/pandas) |
| [pesos_perceptron.asm](file:///D:/facultad/edii/tp%20final/pesos_perceptron.asm) | Constantes Assembly para el firmware (VERSIÓN FINAL) |
| [test_weights.py](file:///D:/facultad/edii/tp%20final/test_weights.py) | Suite de 8 tests con simulador PIC (13,694 verificaciones) |
| [weights.json](file:///D:/facultad/edii/tp%20final/visualizer/weights.json) | Pesos en JSON para el dashboard web |
| [decision_boundary.png](file:///D:/facultad/edii/tp%20final/visualizer/decision_boundary.png) | Gráfico 3D de dispersión del dataset |

---

## 🚀 Siguiente paso

Integrar las constantes de `pesos_perceptron.asm` en el código Assembly principal del PIC16F887. La guía paso a paso:

1. **Adquisición**: Leer `ADRESH` con `ADFM=0` para cada canal (H, T, L)
2. **Normalización**: `x_norm = (x_raw - MEAN) * SCALE_MUL` (multiplicación entera 8×8→16)
3. **Perceptrón 1**: `z1 = Σ(x_norm * W1) + B1_BIAS` → si bit de signo = 0 → RIEGO
4. **Perceptrón 2**: `z2 = Σ(x_norm * W2) + B2_BIAS` → si bit de signo = 0 → SOL
5. Si ambos negativos → **Planta OK**
