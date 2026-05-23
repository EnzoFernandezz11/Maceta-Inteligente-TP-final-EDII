# 🌱 Propuesta de Proyecto: Maceta Inteligente basada en PIC16F887

## 📌 Idea Central
El proyecto consiste en el desarrollo de un sistema de monitoreo para una **"Maceta Inteligente"** programado **100% en lenguaje Assembly** sobre un microcontrolador **PIC16F887**.

El enfoque principal del trabajo es la integración práctica de los distintos periféricos del microcontrolador. Se utilizará el **módulo ADC** para la lectura de sensores analógicos, los **puertos I/O** para el control de actuadores (LEDs y Buzzer) y el **módulo UART** para la comunicación serial bidireccional con una PC.

Como un valor agregado "novedoso" al proyecto, los datos obtenidos por los periféricos no solo se reportarán, sino que se procesarán utilizando un modelo matemático simple (un **Perceptrón Lineal**) programado en Assembly con aritmética de punto fijo, permitiendo clasificar el estado de la planta (`OK`, `NECESITA RIEGO`, `DEMASIADO SOL`).

## 🎯 Objetivos del Proyecto
1. **Adquisición de Datos:** Configurar y utilizar el módulo ADC del PIC para digitalizar señales continuas provenientes de sensores analógicos.
2. **Comunicación Serial:** Implementar una interfaz de comunicación bidireccional utilizando el módulo UART para enviar telemetría a una interfaz gráfica de PC.
3. **Control de Periféricos:** Gestionar entradas y salidas digitales para interactuar con el usuario mediante LEDs de estado y alarmas sonoras.
4. **Programación en Assembly:** Aplicar técnicas estructuradas de programación a bajo nivel, incluyendo como "bonus" el manejo de operaciones aritméticas en punto fijo.
## 🛠️ Tecnologías y Hardware a Utilizar

### Hardware (Capa Física)
*   **Microcontrolador:** PIC16F887 (8KB Flash, operando a 4MHz/20MHz).
*   **Sensores Analógicos:** 
    *   Higrómetro de suelo FC-28 (Humedad).
    *   LM35 (Temperatura).
    *   Fotorresistencia LDR en divisor resistivo (Iluminación).
    *   *Nota técnica:* Estos sensores entregan variaciones de voltaje continuo (0V a 5V) que el módulo Conversor Analógico-Digital (ADC) interno del PIC lee y transforma directamente en un valor numérico digital proporcional de 10 bits (de 0 a 1023).
*   **Interfaz Local (Actuadores e Indicadores):** 
    *   **LEDs de Estado:** Un LED de color diferente dedicado para cada clasificación (ej. Verde = OK, Azul = Riego, Rojo = Sol).
    *   **Buzzer (Alarma Sonora):** Se activará para emitir una alerta sonora cuando el modelo detecte que la planta se encuentra en un estado crítico que requiera atención inmediata.
*   **Comunicación:** Módulo conversor UART a USB (MAX232 o CP2102).

### Software y Tecnologías (Capa Lógica)
*   **Firmware del PIC:** Escrito completamente en **Assembly puro**. Implementará aritmética de punto fijo (escalado x1000) para procesar las ponderaciones del perceptrón sin usar floats.
*   **Entrenamiento (PC):** Script en **Python** (usando `scikit-learn`) para entrenar el perceptrón. Utilizaremos un dataset híbrido (datos reales capturados por los sensores + datos sintéticos) para evitar sobreajustes.
*   **Dashboard Web:** Una interfaz interactiva levantada con **Flask (Python), HTML, CSS y JS**. Mostrará una representación "pixel art" de la planta que reacciona en tiempo real a los datos del PIC, incluyendo un ciclo de día/noche sincronizado con la PC y gráficas.

## 🔄 Protocolos y Flujo de Datos
1.  **Adquisición:** El PIC lee los tres sensores a través de su módulo ADC.
2.  **Inferencia (Assembly):** Se aplican los pesos del perceptrón (pre-calculados y cargados en memoria) usando sumas y multiplicaciones enteras de 16-bits. La función de activación (escalón/umbrales) clasifica el estado.
3.  **Telemetría (UART):** El PIC transmite el estado y los valores crudos a la PC a través de un puerto serial usando un protocolo de texto ligero (ej. `H:820,T:285,L:600,C:1\r\n`).
4.  **Actualización Dinámica (Opcional vía UART):** La arquitectura permite enviar nuevos pesos desde la PC al PIC para re-entrenar el modelo sin tener que re-flashear el firmware.

---
**En resumen:** Buscamos crear un sistema integral que consolide los conocimientos de la materia sobre la manipulación de periféricos del PIC16F887 (ADC, UART, I/O), demostrando su aplicación práctica en un problema real. La inclusión del modelo neuronal funciona como un "bonus" para hacer el proyecto más atractivo y agregarle un desafío extra.
