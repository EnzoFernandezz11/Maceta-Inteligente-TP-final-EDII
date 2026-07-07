; ====================================================================
; MACETA INTELIGENTE EN CASCADA — PIC16F887
; Trabajo Practico Final — Electronica Digital II
; ====================================================================

        LIST    P=16F887
        #include <p16f887.inc>

        __CONFIG _CONFIG1, _FOSC_XT & _WDT_OFF & _PWRTE_ON & _MCLRE_ON & _CP_OFF & _CPD_OFF & _BOREN_OFF & _IESO_OFF & _FCMEN_OFF & _LVP_OFF
        __CONFIG _CONFIG2, _BOR21V & _WRT_OFF

; ====================================================================
; REGISTROS DE RESPALDO PARA CONTEXTO (En RAM Compartida 0x70-0x7F)
; ====================================================================
W_TEMP          EQU     0x70
STATUS_TEMP     EQU     0x71

; ====================================================================
; PESOS PRE-MULTIPLICADOS Y MEDIAS (generados por ml/train.py)
; ====================================================================
PRE_W1_H        EQU     .60
PRE_W1_T        EQU     .36
PRE_W1_L        EQU     0xF8         
PRE_W2_H        EQU     .8
PRE_W2_L        EQU     .36
MEAN_H_VAL      EQU     .165
MEAN_T_VAL      EQU     .19
MEAN_L_VAL      EQU     .166
BIAS1_H_VAL     EQU     0xF5
BIAS1_L_VAL     EQU     0xC3
BIAS2_H_VAL     EQU     0xF8
BIAS2_L_VAL     EQU     0x52

; ====================================================================
; VARIABLES EN RAM - Bank 0 (0x20-0x6F)
; ====================================================================
        CBLOCK  0x20
            ; ADC raw e indicación de 8 bits
            LUZ_H, LUZ_L, TEMP_H, TEMP_L, HUM_H, HUM_L
            LUZ_8, TEMP_8, HUM_8
            CLASE, CLASE_ANT       
            PORTB_S, TMP_PORTB
            ; Acumuladores y multiplicador
            ZH, ZL, MA, MBH, MBL, MRH, MRL, MC, MSIGN           
            TMP_H, TMP_L
            
            ; --- VARIABLES PARA TIMERS DE INTERRUPCIÓN ---
            FLAGS           ; Bit 0: RUN_INFERENCE (Indica que pasaron 500ms)
            TMR_500_A       ; Contador base 1ms (hasta 250)
            TMR_500_B       ; Multiplicador (hasta 2) -> 250 * 2 = 500ms
            BEEP_TMR        ; Temporizador para el ritmo del buzzer (ms)
            BEEP_CNT        ; Contador de cambios de estado del buzzer

        ENDC

; ====================================================================
; VECTORES DE INICIO Y DE INTERRUPCIÓN
; ====================================================================
        ORG     0x000
        GOTO    INICIO

        ORG     0x004
        GOTO    ISR_ROUTINE         ; Salto a la rutina de interrupción

; ====================================================================
; RUTINA DE SERVICIO DE INTERRUPCIÓN (ISR) - Ejecuta cada 1 ms
; ====================================================================
ISR_ROUTINE:
        ; ---- Guardar Contexto ----
        MOVWF   W_TEMP
        SWAPF   STATUS, W
        MOVWF   STATUS_TEMP

        ; ---- Recargar Timer0 (Para 1ms exacto a 4MHz con Prescaler 1:4) ----
        MOVLW   .6
        MOVWF   TMR0
        BCF     INTCON, T0IF        ; Limpiar bandera de interrupción

        ; ------------------------------------------------------------
        ; TEMPORIZADOR DE INFERENCIA (Mide 500ms de forma asíncrona)
        ; ------------------------------------------------------------
        DECFSZ  TMR_500_A, F
        GOTO    CHECK_BEEP
        MOVLW   .250
        MOVWF   TMR_500_A
        DECFSZ  TMR_500_B, F
        GOTO    CHECK_BEEP
        MOVLW   .2
        MOVWF   TMR_500_B
        BSF     FLAGS, 0            ; ¡Pasaron 500ms! Avisar al bucle principal

        ; ------------------------------------------------------------
        ; CONTROL DEL BUZZER EN SEGUNDO PLANO (No Bloqueante)
        ; ------------------------------------------------------------
CHECK_BEEP:
        MOVF    BEEP_CNT, W
        BTFSC   STATUS, Z
        GOTO    ISR_END             ; Si es cero, el buzzer está apagado
        DECFSZ  BEEP_TMR, F
        GOTO    ISR_END
        MOVLW   .100                ; Ritmo de 100ms por cambio
        MOVWF   BEEP_TMR
        
        MOVLW   b'00001000'         ; Conmutar bit 3 (RB3 - Buzzer)
        XORWF   PORTB_S, F
        DECFSZ  BEEP_CNT, F
        GOTO    ISR_END
        BCF     PORTB_S, 3          ; Forzar apagado al terminar el conteo

ISR_END:
        ; ---- Restaurar Contexto y Salir ----
        SWAPF   STATUS_TEMP, W
        MOVWF   STATUS
        SWAPF   W_TEMP, F
        SWAPF   W_TEMP, W
        RETFIE

; ====================================================================
; INICIALIZACIÓN DE PERIFÉRICOS
; ====================================================================
INICIO:
        BANKSEL TRISA
        MOVLW   b'00000111'         
        MOVWF   TRISA
        CLRF    TRISB               ; Todos los pines de PORTB como salidas (LEDs y Buzzer)
        BCF     TRISC, 6            

        MOVLW   b'10000000'         
        MOVWF   ADCON1

        MOVLW   b'00100100'         
        MOVWF   TXSTA
        MOVLW   .25                 
        MOVWF   SPBRG

        BANKSEL ANSEL
        MOVLW   b'00000111'
        MOVWF   ANSEL
        CLRF    ANSELH
        
        ; ---- Configuración del TIMER0 ----
        BANKSEL OPTION_REG
        MOVLW   b'10000001'         ; Pull-ups desc., Prescaler asignado a TMR0 (1:4)
        MOVWF   OPTION_REG

        BANKSEL ADCON0
        MOVLW   b'01000001'         
        MOVWF   ADCON0
        MOVLW   b'10000000'         
        MOVWF   RCSTA

        ; ---- Inicializar Variables del Sistema ----
        BANKSEL PORTB
        CLRF    PORTB
        CLRF    PORTB_S
        CLRF    CLASE
        CLRF    FLAGS
        MOVLW   0xFF                
        MOVWF   CLASE_ANT           
        
        ; Inicializar Timers de Software
        MOVLW   .250
        MOVWF   TMR_500_A
        MOVLW   .2
        MOVWF   TMR_500_B

        ; ---- Habilitar Interrupciones ----
        MOVLW   b'10100000'         ; Habilitar GIE (Globales) y T0IE (Timer0)
        MOVWF   INTCON

; ====================================================================
; BUCLE PRINCIPAL (No Bloqueante)
; ====================================================================
MAIN_LOOP:
        ; El procesador se queda aquí esperando pacientemente la bandera.
        ; Mientras espera, la interrupción sigue moviendo los LEDs fluidamente.
        BTFSS   FLAGS, 0            
        GOTO    MAIN_LOOP
        BCF     FLAGS, 0            ; Borrar bandera de 500ms

        ; MIENTRAS SE HACE ESTA LECTURA Y TODO EL CÁLCULO MATEMÁTICO ABAJO,
        ; LA INTERRUPCIÓN SE DISPARARÁ EN EL MEDIO Y MOVERÁ LOS LEDS.
        CALL    READ_AN0            
        CALL    READ_AN1            
        CALL    READ_AN2            
        CALL    CONVERT_8

        ; --- INFERENCIA EN CASCADA ---
        CALL    EVAL_P1             
        BTFSS   ZH, 7
        GOTO    SET_RIEGO           

        ; --- NEURONA 2 ---
        CALL    EVAL_P2             
        BTFSS   ZH, 7
        GOTO    SET_SOL             

        ; --- PLANTA OK ---
        CLRF    CLASE               
        GOTO    ACTUALIZAR_HW

SET_RIEGO:
        MOVLW   .1
        MOVWF   CLASE
        GOTO    ACTUALIZAR_HW

SET_SOL:
        MOVLW   .2
        MOVWF   CLASE

; ====================================================================
; ACTUALIZACIÓN DE HARDWARE (Protección de memoria compartida)
; ====================================================================
ACTUALIZAR_HW:
        CLRF    TMP_PORTB
        
        ; Evaluar indicador de estado de la planta
        MOVF    CLASE, W
        BTFSC   STATUS, Z
        BSF     TMP_PORTB, 0        ; CLASE = 0 -> LED Verde en RB0

        MOVF    CLASE, W
        SUBLW   .1
        BTFSC   STATUS, Z
        BSF     TMP_PORTB, 1        ; CLASE = 1 -> LED Azul en RB1

        MOVF    CLASE, W
        SUBLW   .2
        BTFSC   STATUS, Z
        BSF     TMP_PORTB, 2        ; CLASE = 2 -> LED Amarillo en RB2

        ; --- ZONA CRÍTICA ---
        ; Evitamos que la interrupción altere PORTB mientras unimos las lógicas
        BCF     INTCON, GIE
        MOVF    PORTB_S, W
        ANDLW   b'00001000'         ; Conservar bit 3 (Buzzer)
        IORWF   TMP_PORTB, W        ; Fusionar con bits de Clases (0 a 2)
        MOVWF   PORTB_S
        MOVWF   PORTB
        BSF     INTCON, GIE

        ; ============================================================
        ; FILTRO DISPARADOR DEL BUZZER (Asíncrono y No Bloqueante)
        ; ============================================================
        MOVF    CLASE, W
        SUBWF   CLASE_ANT, W        
        BTFSC   STATUS, Z           
        GOTO    TRANSMISION_UART    

        MOVF    CLASE, W
        MOVWF   CLASE_ANT           

        ; Cargar ráfagas sin usar Delays. (1 Beep = 2 cambios de estado)
        MOVF    CLASE, W
        BTFSC   STATUS, Z
        GOTO    B_OK
        MOVF    CLASE, W
        SUBLW   .1
        BTFSC   STATUS, Z
        GOTO    B_RIEGO
        MOVLW   .6                  ; Clase 2 -> 3 beeps (6 cambios de estado)
        GOTO    B_GO
B_OK:   MOVLW   .2                  ; Clase 0 -> 1 beep (2 cambios)
        GOTO    B_GO
B_RIEGO:
        MOVLW   .4                  ; Clase 1 -> 2 beeps (4 cambios)
B_GO:   
        BCF     INTCON, GIE
        MOVWF   BEEP_CNT
        MOVLW   .1                  ; Forzar disparo inmediato en el próximo ms
        MOVWF   BEEP_TMR
        BSF     INTCON, GIE

        ; ============================================================
        ; TELEMETRÍA UART
        ; ============================================================
TRANSMISION_UART:
        MOVLW   0xFF
        CALL    UART_TX
        MOVF    LUZ_H, W
        CALL    UART_TX
        MOVF    LUZ_L, W
        CALL    UART_TX
        MOVF    TEMP_H, W
        CALL    UART_TX
        MOVF    TEMP_L, W
        CALL    UART_TX
        MOVF    HUM_H, W
        CALL    UART_TX
        MOVF    HUM_L, W
        CALL    UART_TX
        MOVF    CLASE, W
        CALL    UART_TX

        GOTO    MAIN_LOOP           ; Vuelve arriba inmediatamente a esperar los próximos 500ms

; ====================================================================
; LECTURA DE CANALES ANALÓGICOS
; ====================================================================
READ_AN0:
        BANKSEL ADCON0
        MOVLW   b'01000001'         
        MOVWF   ADCON0
        CALL    DELAY_ACQ
        BSF     ADCON0, GO
RAN0_W: BTFSC   ADCON0, GO
        GOTO    RAN0_W
        MOVF    ADRESH, W
        MOVWF   LUZ_H
        BANKSEL ADRESL
        MOVF    ADRESL, W
        BANKSEL PORTB
        MOVWF   LUZ_L
        RETURN

READ_AN1:
        BANKSEL ADCON0
        MOVLW   b'01000101'         
        MOVWF   ADCON0
        CALL    DELAY_ACQ
        BSF     ADCON0, GO
RAN1_W: BTFSC   ADCON0, GO
        GOTO    RAN1_W
        MOVF    ADRESH, W
        MOVWF   TEMP_H
        BANKSEL ADRESL
        MOVF    ADRESL, W
        BANKSEL PORTB
        MOVWF   TEMP_L
        RETURN

READ_AN2:
        BANKSEL ADCON0
        MOVLW   b'01001001'         
        MOVWF   ADCON0
        CALL    DELAY_ACQ
        BSF     ADCON0, GO
RAN2_W: BTFSC   ADCON0, GO
        GOTO    RAN2_W
        MOVF    ADRESH, W
        MOVWF   HUM_H
        BANKSEL ADRESL
        MOVF    ADRESL, W
        BANKSEL PORTB
        MOVWF   HUM_L
        RETURN

; ====================================================================
; CONVERSIÓN ADC 10-BIT → 8-BIT (descarta los 2 LSB)
; ====================================================================
CONVERT_8:
        MOVF    LUZ_H, W
        MOVWF   TMP_H
        MOVF    LUZ_L, W
        MOVWF   TMP_L
        BCF     STATUS, C
        RRF     TMP_H, F
        RRF     TMP_L, F
        BCF     STATUS, C
        RRF     TMP_H, F
        RRF     TMP_L, F
        MOVF    TMP_L, W
        MOVWF   LUZ_8

        MOVF    TEMP_H, W
        MOVWF   TMP_H
        MOVF    TEMP_L, W
        MOVWF   TMP_L
        BCF     STATUS, C
        RRF     TMP_H, F
        RRF     TMP_L, F
        BCF     STATUS, C
        RRF     TMP_H, F
        RRF     TMP_L, F
        MOVF    TMP_L, W
        MOVWF   TEMP_8

        MOVF    HUM_H, W
        MOVWF   TMP_H
        MOVF    HUM_L, W
        MOVWF   TMP_L
        BCF     STATUS, C
        RRF     TMP_H, F
        RRF     TMP_L, F
        BCF     STATUS, C
        RRF     TMP_H, F
        RRF     TMP_L, F
        MOVF    TMP_L, W
        MOVWF   HUM_8
        RETURN

; ====================================================================
; EVALUACIÓN DE PERCEPTRONES
; ====================================================================
EVAL_P1:
        MOVLW   BIAS1_H_VAL
        MOVWF   ZH
        MOVLW   BIAS1_L_VAL
        MOVWF   ZL
        MOVLW   MEAN_H_VAL
        SUBWF   HUM_8, W            
        MOVWF   MBL
        CALL    Ajustar_Signo_MB
        MOVLW   PRE_W1_H
        MOVWF   MA
        CALL    SMUL_8x16
        CALL    Z_ADD_MR
        MOVLW   MEAN_T_VAL
        SUBWF   TEMP_8, W           
        MOVWF   MBL
        CALL    Ajustar_Signo_MB
        MOVLW   PRE_W1_T
        MOVWF   MA
        CALL    SMUL_8x16
        CALL    Z_ADD_MR
        MOVLW   MEAN_L_VAL
        SUBWF   LUZ_8, W            
        MOVWF   MBL
        CALL    Ajustar_Signo_MB
        MOVLW   PRE_W1_L
        MOVWF   MA
        CALL    SMUL_8x16
        CALL    Z_ADD_MR
        RETURN

EVAL_P2:
        MOVLW   BIAS2_H_VAL
        MOVWF   ZH
        MOVLW   BIAS2_L_VAL
        MOVWF   ZL
        MOVLW   MEAN_H_VAL
        SUBWF   HUM_8, W            
        MOVWF   MBL
        CALL    Ajustar_Signo_MB
        MOVLW   PRE_W2_H
        MOVWF   MA
        CALL    SMUL_8x16
        CALL    Z_ADD_MR
        MOVLW   MEAN_L_VAL
        SUBWF   LUZ_8, W            
        MOVWF   MBL
        CALL    Ajustar_Signo_MB
        MOVLW   PRE_W2_L
        MOVWF   MA
        CALL    SMUL_8x16
        CALL    Z_ADD_MR
        RETURN

; ====================================================================
; SUBRUTINAS ARITMÉTICAS (Punto Fijo Q8, 16 bits con signo)
; ====================================================================
Ajustar_Signo_MB:
        CLRF    MBH
        BTFSS   STATUS, C           
        DECF    MBH, F              
        RETURN

SMUL_8x16:
        CLRF    MSIGN
        BTFSC   MA, 7
        GOTO    SM_A_NEG
        GOTO    SM_CHK_B
SM_A_NEG:
        BSF     MSIGN, 0
        COMF    MA, F
        INCF    MA, F               
SM_CHK_B:
        BTFSS   MBH, 7
        GOTO    SM_INIT
        MOVLW   .1
        XORWF   MSIGN, F
        COMF    MBH, F
        COMF    MBL, F
        INCF    MBL, F
        BTFSC   STATUS, Z
        INCF    MBH, F
SM_INIT:
        CLRF    MRH
        CLRF    MRL
        MOVLW   .8
        MOVWF   MC
SM_LOOP:
        BCF     STATUS, C
        RLF     MRL, F
        RLF     MRH, F
        BCF     STATUS, C
        RLF     MA, F
        BTFSS   STATUS, C
        GOTO    SM_NEXT
        MOVF    MBL, W
        ADDWF   MRL, F
        BTFSC   STATUS, C
        INCF    MRH, F
        MOVF    MBH, W
        ADDWF   MRH, F
SM_NEXT:
        DECFSZ  MC, F
        GOTO    SM_LOOP
        BTFSS   MSIGN, 0
        RETURN
        COMF    MRH, F
        COMF    MRL, F
        INCF    MRL, F
        BTFSC   STATUS, Z
        INCF    MRH, F
        RETURN

Z_ADD_MR:
        MOVF    MRL, W
        ADDWF   ZL, F
        BTFSC   STATUS, C
        INCF    ZH, F
        MOVF    MRH, W
        ADDWF   ZH, F
        RETURN

; ====================================================================
; UART Y DELAY DE ADQUISICIÓN
; ====================================================================
UART_TX:
        BANKSEL PIR1
UART_W: BTFSS   PIR1, TXIF          
        GOTO    UART_W
        BANKSEL TXREG
        MOVWF   TXREG
        BANKSEL PORTB
        RETURN

DELAY_ACQ:
        NOP
        NOP
        NOP
        NOP
        NOP
        RETURN

        END
