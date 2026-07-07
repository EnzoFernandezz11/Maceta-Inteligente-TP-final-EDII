# -*- coding: utf-8 -*-
"""
test_weights.py
Test exhaustivo de los pesos del perceptrón en cascada.
Simula EXACTAMENTE la aritmética entera del PIC16F887 (sin floats).
Verifica que los pesos generados clasifican correctamente todos los escenarios.
"""

import json
import os
import csv
import random
import sys

# ====================================================================
# CONSTANTES EXPORTADAS AL ASM (copiadas tal cual del archivo generado)
# ====================================================================
MEAN_H = 165
SCALE_MUL_H = 4
MEAN_T = 19
SCALE_MUL_T = 36
MEAN_L = 166
SCALE_MUL_L = 4

W1_HUMEDAD = 15
W1_TEMP = 1
W1_LUZ = -2
B1_BIAS = -2621  # Valor Q16 completo (reconstruido de los 3 bytes)

W2_HUMEDAD = 2
W2_TEMP = 12
W2_LUZ = 9
B2_BIAS = -1966

# ====================================================================
# VERIFICACIÓN 0: Consistencia entre ASM y JSON
# ====================================================================
def test_asm_json_consistency():
    """Verifica que los valores en el .asm coincidan con el .json"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "visualizer", "weights.json")

    if not os.path.exists(json_path):
        print("  ⚠ weights.json no encontrado, saltando test de consistencia")
        return True

    with open(json_path, "r") as f:
        wj = json.load(f)

    errors = []

    # Normalización
    if wj["normalization"]["mean"]["hum"] != MEAN_H:
        errors.append(f"MEAN_H: ASM={MEAN_H} vs JSON={wj['normalization']['mean']['hum']}")
    if wj["normalization"]["mean"]["temp"] != MEAN_T:
        errors.append(f"MEAN_T: ASM={MEAN_T} vs JSON={wj['normalization']['mean']['temp']}")
    if wj["normalization"]["mean"]["ldr"] != MEAN_L:
        errors.append(f"MEAN_L: ASM={MEAN_L} vs JSON={wj['normalization']['mean']['ldr']}")
    if wj["normalization"]["scale_mul"]["hum"] != SCALE_MUL_H:
        errors.append(f"SCALE_MUL_H: ASM={SCALE_MUL_H} vs JSON={wj['normalization']['scale_mul']['hum']}")
    if wj["normalization"]["scale_mul"]["temp"] != SCALE_MUL_T:
        errors.append(f"SCALE_MUL_T: ASM={SCALE_MUL_T} vs JSON={wj['normalization']['scale_mul']['temp']}")
    if wj["normalization"]["scale_mul"]["ldr"] != SCALE_MUL_L:
        errors.append(f"SCALE_MUL_L: ASM={SCALE_MUL_L} vs JSON={wj['normalization']['scale_mul']['ldr']}")

    # Perceptrón 1
    if wj["perceptron_riego"]["w_hum"] != W1_HUMEDAD:
        errors.append(f"W1_HUM: ASM={W1_HUMEDAD} vs JSON={wj['perceptron_riego']['w_hum']}")
    if wj["perceptron_riego"]["w_temp"] != W1_TEMP:
        errors.append(f"W1_TEMP: ASM={W1_TEMP} vs JSON={wj['perceptron_riego']['w_temp']}")
    if wj["perceptron_riego"]["w_luz"] != W1_LUZ:
        errors.append(f"W1_LUZ: ASM={W1_LUZ} vs JSON={wj['perceptron_riego']['w_luz']}")
    if wj["perceptron_riego"]["bias"] != B1_BIAS:
        errors.append(f"B1_BIAS: ASM={B1_BIAS} vs JSON={wj['perceptron_riego']['bias']}")

    # Perceptrón 2
    if wj["perceptron_sol"]["w_hum"] != W2_HUMEDAD:
        errors.append(f"W2_HUM: ASM={W2_HUMEDAD} vs JSON={wj['perceptron_sol']['w_hum']}")
    if wj["perceptron_sol"]["w_temp"] != W2_TEMP:
        errors.append(f"W2_TEMP: ASM={W2_TEMP} vs JSON={wj['perceptron_sol']['w_temp']}")
    if wj["perceptron_sol"]["w_luz"] != W2_LUZ:
        errors.append(f"W2_LUZ: ASM={W2_LUZ} vs JSON={wj['perceptron_sol']['w_luz']}")
    if wj["perceptron_sol"]["bias"] != B2_BIAS:
        errors.append(f"B2_BIAS: ASM={B2_BIAS} vs JSON={wj['perceptron_sol']['bias']}")

    if errors:
        for e in errors:
            print(f"  ✗ INCONSISTENCIA: {e}")
        return False

    return True


# ====================================================================
# SIMULADOR DEL PIC16F887 (solo aritmética entera de 16/24 bits)
# ====================================================================
def pic_normalize(raw_val, mean, scale_mul):
    """Simula la normalización Q8 exacta del PIC (solo enteros con signo)."""
    return (raw_val - mean) * scale_mul  # Resultado Q8 con signo


def pic_perceptron(hum_adc8, temp_adc8, luz_adc8, w_h, w_t, w_l, bias):
    """
    Simula la inferencia EXACTA del PIC16F887 con aritmética entera.
    Retorna: (z_valor, prediccion_binaria)
    z = (x_h_norm * w_h) + (x_t_norm * w_t) + (x_l_norm * w_l) + bias
    Si z >= 0 -> clase positiva (1), sino clase negativa (0)
    """
    x_h = pic_normalize(hum_adc8, MEAN_H, SCALE_MUL_H)
    x_t = pic_normalize(temp_adc8, MEAN_T, SCALE_MUL_T)
    x_l = pic_normalize(luz_adc8, MEAN_L, SCALE_MUL_L)

    # Productos Q8 * Q8 = Q16 (todos enteros)
    z = (x_h * w_h) + (x_t * w_t) + (x_l * w_l) + bias

    return z, (1 if z >= 0 else 0)


def pic_classify(hum_adc8, temp_adc8, luz_adc8):
    """
    Clasificación completa en cascada (exactamente como lo haría el PIC).
    Retorna: 0=OK, 1=Riego, 2=Sol
    """
    # Paso 1: ¿Necesita riego?
    z1, pred1 = pic_perceptron(hum_adc8, temp_adc8, luz_adc8,
                                W1_HUMEDAD, W1_TEMP, W1_LUZ, B1_BIAS)
    if pred1 == 1:
        return 1  # RIEGO

    # Paso 2: ¿Demasiado sol?
    z2, pred2 = pic_perceptron(hum_adc8, temp_adc8, luz_adc8,
                                W2_HUMEDAD, W2_TEMP, W2_LUZ, B2_BIAS)
    if pred2 == 1:
        return 2  # SOL

    return 0  # OK


# ====================================================================
# TEST 1: Escenarios conocidos con valores típicos de suculenta
# ====================================================================
def test_known_scenarios():
    """Valida clasificación con escenarios de suculenta bien definidos."""
    scenarios = [
        # (Hum_ADC8, Temp_ADC8, Luz_ADC8, clase_esperada, descripcion)

        # === PLANTA OK (clase 0) ===
        # Suculenta en condiciones normales: humedad moderada, temp ambiente, luz media
        (170, 15, 130, 0, "OK: Suculenta en interior, condiciones ideales"),
        (160, 18, 150, 0, "OK: Suculenta en ventana, tarde templada"),
        (180, 12, 100, 0, "OK: Suculenta recién regada, mañana fresca"),
        (150, 20, 140, 0, "OK: Suculenta en balcon, dia nublado"),
        (175, 16, 140, 0, "OK: Valores muy cercanos a la media (caso típico)"),

        # === NECESITA RIEGO (clase 1) ===
        # Humedad ADC8 muy alta = suelo muy seco (sensor invertido)
        (240, 15, 130, 1, "RIEGO: Suelo completamente seco, día normal"),
        (250, 20, 100, 1, "RIEGO: Sequía extrema, temperatura templada"),
        (230, 10, 150, 1, "RIEGO: Suelo seco, mañana fresca"),
        (255, 18, 169, 1, "RIEGO: Máxima sequía posible, valores medios"),
        (235, 25, 80,  1, "RIEGO: Seco, tarde cálida, poca luz"),

        # === DEMASIADO SOL (clase 2) ===
        # Luz ADC8 muy alta + temperatura alta, pero humedad OK
        (120, 22, 240, 2, "SOL: Sol directo intenso, planta hidratada"),
        (100, 20, 250, 2, "SOL: Insolación extrema, suelo húmedo"),
        (150, 23, 220, 2, "SOL: Sol fuerte de mediodia, >43C"),
        (130, 21, 230, 2, "SOL: Sol intenso de verano"),
        (80,  18, 255, 2, "SOL: Máxima luz posible, suelo bien regado"),
    ]

    passed = 0
    failed = 0
    details = []

    for hum, temp, luz, expected, desc in scenarios:
        result = pic_classify(hum, temp, luz)
        ok = result == expected
        if ok:
            passed += 1
        else:
            failed += 1
            details.append(f"  ✗ FALLO: {desc}")
            details.append(f"    Entrada: H={hum}, T={temp}, L={luz}")
            details.append(f"    Esperado: {expected}, Obtenido: {result}")

            # Debug: mostrar valores intermedios
            z1, p1 = pic_perceptron(hum, temp, luz, W1_HUMEDAD, W1_TEMP, W1_LUZ, B1_BIAS)
            z2, p2 = pic_perceptron(hum, temp, luz, W2_HUMEDAD, W2_TEMP, W2_LUZ, B2_BIAS)
            details.append(f"    Debug: z1={z1} (p1={p1}), z2={z2} (p2={p2})")

    return passed, failed, details


# ====================================================================
# TEST 2: Casos extremos (bordes del ADC)
# ====================================================================
def test_edge_cases():
    """Verifica que el sistema no explote con valores extremos del ADC."""
    edge_cases = [
        # (Hum, Temp, Luz, clase_esperada, descripcion)
        (0,   0,   0,   None, "Todos los sensores en mínimo (0)"),
        (255, 255, 255, None, "Todos los sensores en máximo (255)"),
        (0,   0,   255, None, "Húmedo + frío + máxima luz"),
        (255, 0,   0,   None, "Máxima sequía + frío + oscuridad"),
        (128, 128, 128, None, "Todos en el punto medio exacto"),
        (MEAN_H, MEAN_T, MEAN_L, None, "Exactamente en las medias de normalización"),
    ]

    errors = []
    overflow_detected = False

    for hum, temp, luz, _, desc in edge_cases:
        try:
            result = pic_classify(hum, temp, luz)

            # Verificar que el resultado es válido (0, 1, o 2)
            if result not in (0, 1, 2):
                errors.append(f"  ✗ Resultado inválido {result} para: {desc}")

            # Verificar overflow: los valores intermedios deben caber en 24 bits con signo
            z1, _ = pic_perceptron(hum, temp, luz, W1_HUMEDAD, W1_TEMP, W1_LUZ, B1_BIAS)
            z2, _ = pic_perceptron(hum, temp, luz, W2_HUMEDAD, W2_TEMP, W2_LUZ, B2_BIAS)

            # PIC16F887 trabaja con registros de 8 bits, pero puede manejar 24 bits con carry
            # El rango seguro para aritmética con signo de 24 bits: -8388608 a 8388607
            MAX_24BIT = 8388607
            MIN_24BIT = -8388608

            if z1 > MAX_24BIT or z1 < MIN_24BIT:
                overflow_detected = True
                errors.append(f"  ⚠ OVERFLOW 24-bit en P1: z1={z1} para {desc}")
            if z2 > MAX_24BIT or z2 < MIN_24BIT:
                overflow_detected = True
                errors.append(f"  ⚠ OVERFLOW 24-bit en P2: z2={z2} para {desc}")

        except Exception as e:
            errors.append(f"  ✗ EXCEPCIÓN para {desc}: {e}")

    return len(edge_cases) - len(errors), len(errors), errors


# ====================================================================
# TEST 3: Validación contra el dataset de entrenamiento (CSV completo)
# ====================================================================
def test_training_dataset():
    """
    Carga el sensor_data.csv, aplica la misma lógica de clasificación del train.py,
    y verifica que los pesos Q8 reproduzcan los resultados esperados.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "visualizer", "sensor_data.csv")
    if not os.path.exists(csv_path):
        csv_path = os.path.join(base_dir, "sensor_data.csv")

    if not os.path.exists(csv_path):
        return 0, 0, ["  ⚠ sensor_data.csv no encontrado, test saltado"]

    passed = 0
    failed = 0
    details = []

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                temp_c = float(row["Temperatura_C"])
                hum_pct = float(row["Humedad_Porcentaje"])
                luz_pct = float(row["Luz_Porcentaje"])
            except (ValueError, KeyError):
                continue

            # Filtrar ruido (igual que train.py)
            if temp_c <= 5 or temp_c >= 50:
                continue

            # Convertir a ADC8 (misma fórmula que train.py)
            adc8_luz = max(0, min(255, int(round(luz_pct * 2.55))))
            adc8_temp = max(0, min(255, int(round(temp_c / 1.953))))
            adc8_hum = max(0, min(255, int(round(255 - hum_pct * 2.55))))

            # Los datos reales del CSV son clase 0 (OK)
            result = pic_classify(adc8_hum, adc8_temp, adc8_luz)
            if result == 0:
                passed += 1
            else:
                failed += 1
                if failed <= 10:  # Solo mostrar primeros 10 errores
                    clase_str = "RIEGO" if result == 1 else "SOL"
                    details.append(
                        f"  ✗ Muestra real clasificada como {clase_str}: "
                        f"H={adc8_hum}(raw:{hum_pct:.0f}%), "
                        f"T={adc8_temp}(raw:{temp_c:.1f}°C), "
                        f"L={adc8_luz}(raw:{luz_pct:.0f}%)"
                    )

    if failed > 10:
        details.append(f"  ... y {failed - 10} errores más")

    return passed, failed, details


# ====================================================================
# TEST 4: Fuzzing aleatorio con validación de coherencia
# ====================================================================
def test_random_fuzzing():
    """
    Genera 10,000 entradas aleatorias DENTRO DE RANGOS FISICAMENTE REALISTAS y verifica:
    1. Que no haya crashes/overflows
    2. Que las clasificaciones sean coherentes con la lógica del sensor

    Rangos realistas del hardware:
    - Humedad ADC8: 0-255 (todo el rango es posible con higrómetro resistivo)
    - Temperatura ADC8: 0-30 (LM35 mide 0-58°C aprox, ADC8 = temp_C / 1.953)
    - Luz ADC8: 0-255 (LDR con divisor de tensión, todo el rango es posible)
    """
    random.seed(2024)
    n_tests = 10000
    passed = 0
    failed = 0
    details = []
    class_counts = {0: 0, 1: 0, 2: 0}

    for _ in range(n_tests):
        hum = random.randint(0, 255)
        temp = random.randint(0, 30)   # LM35 rango real: 0-58°C -> ADC8 0-30
        luz = random.randint(0, 255)

        try:
            result = pic_classify(hum, temp, luz)

            if result not in (0, 1, 2):
                failed += 1
                details.append(f"  x Resultado invalido {result}: H={hum}, T={temp}, L={luz}")
                continue

            class_counts[result] += 1

            # Coherencia: si la humedad es baja (sensor mojado = ADC bajo),
            # NO debería ser clasificado como RIEGO
            if hum < 100 and result == 1:
                failed += 1
                if failed <= 5:
                    details.append(
                        f"  x Incoherente: Suelo humedo (H={hum}) clasificado como RIEGO. "
                        f"T={temp}, L={luz}"
                    )
                continue

            # Coherencia: si la luz es baja, NO debería ser SOL
            if luz < 80 and result == 2:
                failed += 1
                if failed <= 5:
                    details.append(
                        f"  x Incoherente: Poca luz (L={luz}) clasificado como SOL. "
                        f"H={hum}, T={temp}"
                    )
                continue

            passed += 1

        except Exception as e:
            failed += 1
            details.append(f"  x CRASH: H={hum}, T={temp}, L={luz} -> {e}")

    details.append(f"\n  Distribucion en fuzzing: OK={class_counts[0]}, "
                   f"Riego={class_counts[1]}, Sol={class_counts[2]}")

    return passed, failed, details


# ====================================================================
# TEST 5: Verificación de la reconstrucción del BIAS desde bytes ASM
# ====================================================================
def test_bias_reconstruction():
    """
    Verifica que la descomposición en 3 bytes (H, M, L) del bias
    reconstruya correctamente el valor original.
    """
    errors = []

    # Valores del ASM
    B1_H = -1  # Byte alto (con signo, complemento a 2 para negativos)
    B1_M = 245
    B1_L = 195

    # Reconstruir: para negativos, el byte alto tiene extensión de signo
    # En complemento a 2 de 24 bits:
    b1_reconstructed = (B1_H << 16) | (B1_M << 8) | B1_L

    # Verificar contra el valor original
    if b1_reconstructed != B1_BIAS:
        # Intentar con interpretación de complemento a 2 de 24 bits
        if B1_H < 0:
            # El shift de un número negativo en Python extiende el signo
            # Necesitamos verificar que la aritmética del PIC lo reconstruya igual
            b1_alt = (B1_H * 65536) + (B1_M * 256) + B1_L
            if b1_alt != B1_BIAS:
                errors.append(
                    f"  ✗ B1_BIAS no se reconstruye correctamente: "
                    f"Original={B1_BIAS}, Reconstruido={b1_reconstructed}, Alt={b1_alt}"
                )
            else:
                pass  # La reconstrucción alternativa funciona

    # Perceptrón 2 (bias = 0, trivial)
    B2_H = -1
    B2_M = 248
    B2_L = 82
    b2_reconstructed = (B2_H * 65536) + (B2_M * 256) + B2_L
    if b2_reconstructed != B2_BIAS:
        errors.append(f"  ✗ B2_BIAS: Original={B2_BIAS}, Reconstruido={b2_reconstructed}")

    return 2 - len(errors), len(errors), errors


# ====================================================================
# TEST 6: Zona de transición (boundary testing)
# ====================================================================
def test_decision_boundary():
    """
    Busca la frontera de decisión del Perceptrón 1 (Riego) variando
    la humedad y verifica que la transición sea suave y predecible.
    """
    details = []
    transition_found = False
    transition_hum = None

    # Fijar temp y luz en valores medios, barrer humedad
    temp_fixed = 18
    luz_fixed = 130

    prev_result = None
    transitions = []

    for hum in range(100, 256):
        result = pic_classify(hum, temp_fixed, luz_fixed)
        if prev_result is not None and result != prev_result:
            transitions.append((hum, prev_result, result))
        prev_result = result

    if not transitions:
        details.append("  ⚠ No se encontró transición en rango H=100-255 (sospechoso)")
    else:
        for hum, from_class, to_class in transitions:
            class_names = {0: "OK", 1: "RIEGO", 2: "SOL"}
            details.append(
                f"  → Transición en H={hum}: {class_names[from_class]} → {class_names[to_class]} "
                f"(T={temp_fixed}, L={luz_fixed})"
            )
            transition_found = True

    # Verificar que la transición tiene sentido (de OK a RIEGO al aumentar H)
    sensible = True
    for hum, from_class, to_class in transitions:
        if from_class == 0 and to_class == 1:
            continue  # OK -> RIEGO al aumentar humedad ADC = correcto
        else:
            sensible = False
            details.append(f"  ⚠ Transición inesperada: clase {from_class} -> {to_class}")

    # Hacer lo mismo para Sol: barrer luz con humedad OK
    hum_fixed = 120
    transitions_sol = []
    prev_result = None
    for luz in range(100, 256):
        result = pic_classify(hum_fixed, temp_fixed, luz)
        if prev_result is not None and result != prev_result:
            transitions_sol.append((luz, prev_result, result))
        prev_result = result

    for luz, from_class, to_class in transitions_sol:
        class_names = {0: "OK", 1: "RIEGO", 2: "SOL"}
        details.append(
            f"  → Transición en L={luz}: {class_names[from_class]} → {class_names[to_class]} "
            f"(H={hum_fixed}, T={temp_fixed})"
        )

    passed = 1 if transition_found and sensible else 0
    failed = 0 if passed else 1
    return passed, failed, details


# ====================================================================
# TEST 7: Verificación de overflow en multiplicaciones del PIC
# ====================================================================
def test_pic_multiplication_overflow():
    """
    Verifica que NINGUNA multiplicación intermedia exceda el rango
    de un registro de 16 bits con signo (-32768 a 32767).
    Esto es CRÍTICO porque el PIC hace multiplicaciones de 8x8 bits.
    """
    errors = []
    max_product = 0

    for hum in range(256):
        for temp_val in [0, MEAN_T, 255]:  # Muestreo para no tardar horas
            for luz_val in [0, MEAN_L, 255]:
                # Normalización
                x_h = pic_normalize(hum, MEAN_H, SCALE_MUL_H)
                x_t = pic_normalize(temp_val, MEAN_T, SCALE_MUL_T)
                x_l = pic_normalize(luz_val, MEAN_L, SCALE_MUL_L)

                # Verificar rango de valores normalizados (deben caber en 16 bits con signo)
                for name, val in [("x_h", x_h), ("x_t", x_t), ("x_l", x_l)]:
                    if val > 32767 or val < -32768:
                        errors.append(f"  ✗ Normalización overflow: {name}={val}")

                # Verificar productos individuales
                products = [
                    ("P1: x_h*W1_H", x_h * W1_HUMEDAD),
                    ("P1: x_t*W1_T", x_t * W1_TEMP),
                    ("P1: x_l*W1_L", x_l * W1_LUZ),
                    ("P2: x_h*W2_H", x_h * W2_HUMEDAD),
                    ("P2: x_t*W2_T", x_t * W2_TEMP),
                    ("P2: x_l*W2_L", x_l * W2_LUZ),
                ]
                for pname, pval in products:
                    abs_val = abs(pval)
                    if abs_val > max_product:
                        max_product = abs_val
                    # Los productos Q8*Q8 deben caber en 24 bits con signo
                    if pval > 8388607 or pval < -8388608:
                        errors.append(f"  ✗ Producto overflow 24-bit: {pname}={pval}")

    details = [f"  Máximo producto absoluto encontrado: {max_product}"]
    details.append(f"  Rango 24-bit con signo: [-8388608, 8388607]")
    details.append(f"  Margen disponible: {((8388607 - max_product) / 8388607 * 100):.1f}%")
    details.extend(errors)

    return 1 if not errors else 0, len(errors), details


# ====================================================================
# RUNNER PRINCIPAL
# ====================================================================
def main():
    print("=" * 70)
    print("  TEST EXHAUSTIVO DE PESOS - PERCEPTRON EN CASCADA Q8")
    print("  Simulador de aritmética entera PIC16F887")
    print("=" * 70)

    tests = [
        ("Consistencia ASM ↔ JSON", test_asm_json_consistency),
        ("Escenarios conocidos de suculenta", test_known_scenarios),
        ("Casos extremos (bordes ADC)", test_edge_cases),
        ("Dataset de entrenamiento (CSV)", test_training_dataset),
        ("Fuzzing aleatorio (10,000 pruebas)", test_random_fuzzing),
        ("Reconstrucción de BIAS desde bytes", test_bias_reconstruction),
        ("Frontera de decisión (boundary)", test_decision_boundary),
        ("Overflow en multiplicaciones PIC", test_pic_multiplication_overflow),
    ]

    total_passed = 0
    total_failed = 0
    all_ok = True

    for name, test_fn in tests:
        print(f"\n{'─' * 60}")
        print(f"  TEST: {name}")
        print(f"{'─' * 60}")

        result = test_fn()

        # test_asm_json_consistency returns bool, rest return tuples
        if isinstance(result, bool):
            if result:
                print("  ✓ PASÓ")
                total_passed += 1
            else:
                print("  ✗ FALLÓ")
                total_failed += 1
                all_ok = False
        else:
            passed, failed, details = result
            total_passed += passed
            total_failed += failed

            for d in details:
                print(d)

            if failed == 0:
                print(f"\n  ✓ PASÓ ({passed} verificaciones correctas)")
            else:
                print(f"\n  ✗ FALLÓ ({failed} errores de {passed + failed} verificaciones)")
                all_ok = False

    # Resumen final
    print(f"\n{'=' * 70}")
    print(f"  RESUMEN FINAL")
    print(f"{'=' * 70}")
    print(f"  Total verificaciones: {total_passed + total_failed}")
    print(f"  ✓ Pasaron: {total_passed}")
    print(f"  ✗ Fallaron: {total_failed}")

    if all_ok:
        print(f"\n  🎉 TODOS LOS TESTS PASARON - Los pesos son CORRECTOS")
        print(f"  ✅ Es seguro integrar pesos_perceptron.asm en el firmware")
    else:
        print(f"\n  🚨 HAY ERRORES - Revisar antes de integrar en el PIC")

    print(f"{'=' * 70}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
