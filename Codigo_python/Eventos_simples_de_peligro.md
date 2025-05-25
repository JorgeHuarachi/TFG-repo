# Condiciones Ambientales y de Seguridad Simples

Este documento muestra las **variables ambientales** que se pueden medir (creo, en principio) y las **condiciones de peligro Simples** asociadas a ellas.

---

## Variables Ambientales Monitoreadas (las que creo que quizas se pueden medir)

Las variables que se pueden medir con sus respectivas unidades y descripciones:

| **Parámetro**                     | **Unidad** | **Descripción**                                                                 |
|-----------------------------------|------------|---------------------------------------------------------------------------------|
| Air Temperature                  | °C         | Temperatura del aire ambiente. Afecta el confort y el riesgo de estrés térmico. |
| Air Humidity                     | %          | Humedad relativa del aire. Influye en el confort y el riesgo de moho.           |
| Barometric Pressure              | hPa        | Presión atmosférica. Útil para detectar cambios bruscos (explosiones, fugas).   |
| Battery Voltage                  | V          | Voltaje de la batería del sensor. Indica la salud del dispositivo.              |
| Activity Counter                 | counts     | Conteo de actividad detectada. Indica movimiento o presencia.                   |
| Ambient Light (Visible + IR)     | adim       | Luz ambiental (visible + infrarroja). Para evaluar iluminación.                 |
| Total VOC                        | ppb        | Compuestos orgánicos volátiles totales. Indica presencia de químicos.           |
| CO₂ Concentration                | ppm        | Nivel de dióxido de carbono. Indica calidad de ventilación.                     |
| Illuminance                      | lx         | Intensidad de luz visible. Afecta la visibilidad y el confort.                  |
| Indoor Air Quality (IAQ)         | adim       | Índice de calidad del aire basado en gases, humedad y CO₂.                      |
| IAQ Calibration                  | adim       | Valor interno para calibrar el IAQ. No es útil para alertas directas.          |
| PIR Count                        | counts     | Detección de movimiento por sensor PIR. Indica presencia reciente.              |
| Battery Level                    | %          | Porcentaje de carga de la batería del sensor.                                   |

---

## Condiciones de Peligro (de los que hay)

Las condiciones de peligro se evalúan según **dos criterios**:
1. **Valor de la variable**: Si supera los límites aceptables.
2. **Tiempo de exposición**: Duración máxima tolerable en la condición.

> **Nota**: Las recomendaciones asumen que el objetivo es atravesar una zona peligrosa rápidamente. Los tiempos de exposición son estimaciones basadas en riesgos para la salud.

### Temperatura Alta (> 50°C) o Estrés Térmico (WBGT > 30°C)
**Efecto**: Calor extremo que puede causar quemaduras, deshidratación o golpe de calor.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 50-60°C o WBGT 30-32°C           | 2-3 minutos                     | Cruza en <3 min. Usa ropa protectora (mangas largas) y evita superficies calientes. |
| 60-70°C o WBGT 32-35°C           | 1 minuto                        | Cruza en <60 seg. Riesgo alto de quemaduras.                                      |
| >70°C o WBGT >35°C               | 30 segundos                     | Evita el área. Riesgo inminente de colapso por calor.                             |

### Dióxido de Carbono (CO₂ > 5,000 ppm)
**Efecto**: Hiperventilación, desorientación y fatiga.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 5,000-10,000 ppm                 | 5-10 minutos                    | Cruza en <5 min. Respira controladamente, evita esfuerzos físicos intensos.       |
| >10,000 ppm                      | 2-3 minutos                     | Cruza en <3 min. Riesgo de desorientación.                                       |

### Monóxido de Carbono (CO > 50 ppm)
**Efecto**: Gas tóxico que causa mareos, náuseas y pérdida de conciencia.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 50-100 ppm                       | 10-15 minutos                   | Cruza en <10 min. Respira controladamente, agáchate (CO se acumula arriba).       |
| 100-200 ppm                      | 2-5 minutos                     | Cruza en <2 min. Riesgo de síntomas graves.                                      |
| >200 ppm                         | 1 minuto                        | Evita el área o cruza en <60 seg. Riesgo letal.                                  |

### Falta de Oxígeno (O₂ < 19.5%)
**Efecto**: Mareos, desorientación y pérdida de conciencia.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 17-19.5%                         | 5 minutos                       | Cruza en <5 min. Evita esfuerzos físicos intensos.                                |
| 12-17%                           | 1-2 minutos                     | Cruza en <2 min. Riesgo de desorientación.                                       |
| <12%                             | 30 segundos                     | Evita el área. Riesgo de pérdida de conciencia.                                   |

### Sulfuro de Hidrógeno (H₂S > 10 ppm)
**Efecto**: Colapso respiratorio, irritación y pérdida de conciencia.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 10-20 ppm                        | 5 minutos                       | Cruza en <5 min. Contén la respiración si detectas olor a huevos podridos.        |
| 20-50 ppm                        | 1-2 minutos                     | Cruza en <2 min. Riesgo de síntomas graves.                                      |
| >50 ppm                          | 30 segundos                     | Evita el área. Riesgo letal.                                                     |

### Gases Inflamables (> 10% del LEL)
**Efecto**: Riesgo de explosión si se alcanza el límite de explosividad.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 10-25% del LEL                   | 5 minutos                       | Cruza en <5 min. Apaga dispositivos eléctricos para evitar chispas.               |
| 25-50% del LEL                   | 1-2 minutos                     | Cruza en <2 min. Evita fuentes de ignición.                                      |
| >50% del LEL                     | Evitar                          | No uses el área. Riesgo inminente de explosión.                                  |

### Amoníaco (NH₃ > 25 ppm)
**Efecto**: Irritación severa en ojos, garganta y pulmones.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 25-50 ppm                        | 2-3 minutos                     | Cruza en <3 min. Usa pañuelo para cubrir la cara.                                |
| >50 ppm                          | 1 minuto                        | Evita el área o cruza en <60 seg. Riesgo de dificultad respiratoria.              |

### Radiación (> 1 mSv/h)
**Efecto**: Daño celular acumulativo, riesgo de cáncer a largo plazo.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 1-5 mSv/h                        | 5 minutos                       | Cruza en <5 min. Busca atención médica tras exposición.                          |
| >5 mSv/h                         | 1 minuto                        | Evita el área. Daño significativo incluso en exposiciones cortas.                 |

---

## Eventos Simples Monitoreados

### CO₂ (> 1,000 ppm)
**Efecto**: Afecta la capacidad cognitiva, provoca fatiga, cefaleas y desorientación.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 1,000-2,000 ppm                  | 10-30 minutos                   | Cruza en <10 min. Puede causar somnolencia.                                      |
| 2,000-5,000 ppm                  | 5-10 minutos                    | Cruza en <5 min. Evita exposiciones prolongadas.                                 |
| >5,000 ppm                       | 2-3 minutos                     | Cruza en <3 min. Riesgo de hiperventilación.                                     |

> **Recomendación**: Mejora la ventilación. Cruza sin correr para evitar hiperventilar.

### Calidad del Aire Interior (IAQ > 100 adim)
**Efecto**: Aire viciado o contaminado.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 100-150 adim                     | 10-20 minutos                   | Cruza en <10 min. Usa mascarilla si es posible.                                  |
| >150 adim                        | 5 minutos                       | Evita zonas con IAQ > 150. Ventila si puedes.                                    |

### Compuestos Orgánicos Volátiles (TVOC > 500 ppb)
**Efecto**: Irritación ocular, dolor de cabeza, daños hepáticos.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 500-1,000 ppb                    | 10 minutos                      | Cruza en <10 min. Leve irritación para personas sensibles.                       |
| 1,000-3,000 ppb                  | 3-5 minutos                     | Cruza en <3 min. Riesgo de malestar.                                             |
| >3,000 ppb                       | 1-2 minutos                     | Evita el área o usa protección respiratoria.                                     |

### Temperatura
**Valor actual**: 20.19°C (normal)  
**Efecto**: <15°C puede causar hipotermia; >30°C genera fatiga térmica.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| <10°C                            | 30 minutos (sin abrigo)         | Usa abrigo para evitar temblores o entumecimiento.                               |
| >30°C                            | 15 minutos                      | Hidrátate y evita esfuerzos prolongados.                                         |

### Humedad del Aire
**Valor actual**: 55% (normal)  
**Efecto**: >70% evita evaporación del sudor; <30% reseca mucosas.

| **Condición**                     | **Tiempo Máximo de Exposición** | **Recomendación**                                                                 |
|-----------------------------------|----------------------------------|----------------------------------------------------------------------------------|
| 70-80%                           | 10-15 minutos                   | Ventila o usa deshumidificadores. Riesgo de fatiga.                              |
| >80%                             | 5 minutos                       | Evita si la temperatura es alta. Riesgo de golpe de calor.                       |

### Presión Barométrica
**Valor actual**: 947.18 hPa (bajo)  
**Efecto**: Puede indicar tormentas o baja disponibilidad de oxígeno.

> **Recomendación**: Monitorea síntomas como mareos. No es riesgosa por sí misma.

### Movimiento Detectado (PIR Count > 0)
**Efecto**: Indica presencia de personas. No es peligroso, pero puede activar alertas en zonas restringidas.

### Luz Ambiental
**Valor actual**: 164 (bajo-moderado)  
**Efecto**: Niveles bajos pueden causar fatiga visual o caídas.

> **Recomendación**: No es peligroso, pero asegúrate de tener visibilidad adecuada.

### Voltaje de Batería
**Valor actual**: 3.71V  
**Efecto**: Asegura el funcionamiento del sensor. No afecta a las personas.

### Calibración IAQ
**Valor actual**: 0 (sin calibrar)  
**Comentario**: La falta de calibración puede afectar la precisión del IAQ. Calibra periódicamente.

---

## Resumen de Recomendaciones Generales
- **Muévete rápido** en zonas con condiciones peligrosas.
- **Usa protección** (mascarilla, ropa) cuando sea necesario.
- **Monitorea síntomas** como mareos, fatiga o dificultad para respirar.
- **Mejora la ventilación** en áreas con alta concentración de CO₂ o TVOC.
- **Evita esfuerzos físicos intensos** en condiciones de baja oxigenación o alta temperatura.
