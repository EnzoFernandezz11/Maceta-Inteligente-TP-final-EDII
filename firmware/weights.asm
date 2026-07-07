;====================================================================
; PESOS Y PARAMETROS DEL PERCEPTRON EN CASCADA (FORMATO Q8 / ESCALA x256)
; Generado automaticamente por ml/train.py
; Planta: Suculenta (Ambiente comun / controlado)
;====================================================================

; --- PARAMETROS DE NORMALIZACION DE ENTRADAS ---
; Formula PIC: X_norm_q8 = (X_raw - MEAN) * SCALE_MUL
; Donde X_raw es la lectura directa del ADC desplazada 2 bits a la derecha (0-255)
MEAN_H          EQU     165      ; Media Humedad (ADC 8 bits)
SCALE_MUL_H     EQU     4        ; Multiplicador de Escala Humedad Q8

MEAN_T          EQU     19       ; Media Temperatura (ADC 8 bits)
SCALE_MUL_T     EQU     36       ; Multiplicador de Escala Temperatura Q8

MEAN_L          EQU     166      ; Media Luz (ADC 8 bits)
SCALE_MUL_L     EQU     4        ; Multiplicador de Escala Luz Q8

; --- PERCEPTRON 1: ¿NECESITA RIEGO? (Clase 1 vs Resto) ---
; Inferencia: z1 = (x_h * W1_H) + (x_t * W1_T) + (x_l * W1_L) + B1_BIAS
; Pesos en Q8 -> productos en Q16. Bias en Q16.
W1_HUMEDAD      EQU     15       ; Peso Humedad Q8
W1_TEMP         EQU     1        ; Peso Temperatura Q8
W1_LUZ          EQU     -2       ; Peso Luz Q8
B1_BIAS_H       EQU     -1       ; Byte Alto de BIAS (Q16)
B1_BIAS_M       EQU     245      ; Byte Medio de BIAS (Q16)
B1_BIAS_L       EQU     195      ; Byte Bajo de BIAS (Q16)

; --- PERCEPTRON 2: ¿DEMASIADO SOL? (Clase 2 vs OK) ---
; Inferencia: z2 = (x_h * W2_H) + (x_t * W2_T) + (x_l * W2_L) + B2_BIAS
W2_HUMEDAD      EQU     2        ; Peso Humedad Q8
W2_TEMP         EQU     12       ; Peso Temperatura Q8
W2_LUZ          EQU     9        ; Peso Luz Q8
B2_BIAS_H       EQU     -1       ; Byte Alto de BIAS (Q16)
B2_BIAS_M       EQU     248      ; Byte Medio de BIAS (Q16)
B2_BIAS_L       EQU     82       ; Byte Bajo de BIAS (Q16)
