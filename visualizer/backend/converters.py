def convert_ldr(raw_val):
    """10-bit ADC → porcentaje de luz (0–100%)."""
    return round((raw_val / 1023.0) * 100.0, 1)


def convert_temp(raw_val):
    """10-bit ADC → temperatura en °C (LM35, referencia 5V)."""
    return round(raw_val * 0.48876, 1)


def convert_hum(raw_val):
    """10-bit ADC → porcentaje de humedad (0–100%, sensor invertido)."""
    return round(((1023 - raw_val) / 1023.0) * 100.0, 1)
