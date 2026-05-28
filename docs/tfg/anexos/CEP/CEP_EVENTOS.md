# Módulo CEP (simulado) para evaluación de peligrosidad de salas

Este apartado describe cómo **simular** un sistema de *Complex Event Processing* (CEP) para analizar condiciones ambientales interiores y **estimar la peligrosidad de salas** durante una evacuación. El objetivo es **centrarse en la arquitectura** del proyecto (grafo de navegación, cálculo de rutas, etc.), usando **datos simulados** y **reglas básicas** en lugar de instrumentación real.

---

## 1. Alcance y enfoque

* **Datos**: se trabajará con **streams simulados** de variables ambientales (CO₂, IAQ, TVOC, temperatura, etc.).
* **CEP “ligero”**: reglas sencillas y ventanas temporales cortas; no se pretende un gemelo digital clínicamente exacto.
* **Resultado**: para cada **sala** se calcula un **estado de peligrosidad** y un **tiempo máximo de exposición permitido**; estos valores se integran con el grafo para **penalizar** o **bloquear** rutas.

> Nota: algunas amenazas (CO, O₂, H₂S, radiación, LEL) **no están disponibles** en las métricas actuales; se dejan documentadas como *out of scope* (o se simulan con valores ficticios si hace falta ilustrar escenarios).

---

## 2. Catálogo de variables y unidades

Variables principales que **sí** usaremos en reglas:

| Código                | Nombre (display)    | Unidad | Uso en CEP                                                           |
| --------------------- | ------------------- | ------ | -------------------------------------------------------------------- |
| `co2`                 | CO₂                 | ppm    | Calidad de ventilación / riesgo de hipercapnia.                      |
| `iaq`                 | Indoor Air Quality  | adim   | Índice compuesto; proxy de “aire viciado”.                           |
| `tvoc`                | TVOC                | ppb    | Volátiles totales; proxy de químicos/gas.                            |
| `air_temperature`     | Air Temperature     | °C     | Calor/estrés térmico.                                                |
| `air_humidity`        | Air Humidity        | %      | Confort térmico; condiciona estrés térmico.                          |
| `barometric_pressure` | Barometric Pressure | hPa    | Cambios bruscos (explosiones/choques de presión) — uso como *proxy*. |
| `pir_count`           | PIR Count           | counts | Presencia/movimiento reciente (contexto).                            |
| `ambient_light`       | Ambient Light       | counts | Visibilidad (riesgo de tropiezos).                                   |
| `battery_voltage`     | Battery Voltage     | V      | Salud del sensor (solo para diagnóstico).                            |

Variables auxiliares (solo monitorización / sin reglas de peligro directas):
`Activity counter`, `Ambient light (vis+IR)`, `Ambient light (IR)`, `CO2 sensor status`, `Raw IR reading`, `Indoor Air Quality calibration`, `Light intensity`, `airQuality`, `Occupancy`, `Battery level`, `Unknown`.

---

## 3. Eventos simples (reglas por variable)

Cada regla se evalúa en una **ventana deslizante** (p.ej., últimos 30–60 s, mediana o percentil 75 para robustez) y produce un **nivel de severidad** y, si aplica, un **tiempo máximo de exposición**.

### 3.1 CO₂ (calidad de ventilación)

* **Umbrales**:

  * 1 000–2 000 ppm → *Moderado* (paso breve).
  * 2 000–5 000 ppm → *Alto* (evitar estancias; paso rápido).
  * > 5 000 ppm → *Crítico* (2–3 min máx. de exposición).
* **Tiempo máximo recomendado**:

  * 5 000–10 000 ppm: 5–10 min.
  * > 10 000 ppm: 2–3 min.

### 3.2 IAQ (índice compuesto)

* **Umbrales**:

  * > 100 → *Moderado* (10–20 min).
  * > 150 → *Alto* / *Crítico* (≤ 5 min).
* **Notas**: si `calib_iaq` indica falta de calibración, **reducir confianza** (p. ej., bajar severidad un nivel o marcar *incertidumbre alta*).

### 3.3 TVOC (volátiles)

* **Umbrales**:

  * 500–1 000 ppb → *Moderado* (≤ 10 min).
  * 1 000–3 000 ppb → *Alto* (3–5 min).
  * > 3 000 ppb → *Crítico* (1–2 min).

### 3.4 Temperatura / Estrés térmico (WBGT proxy)

* **Umbrales** (temperatura como proxy, combinado con humedad alta):

  * 50–60 °C → *Alto* (≤ 3 min).
  * 60–70 °C → *Crítico* (≤ 1 min).
  * > 70 °C → *Crítico extremo* (≤ 30 s).
* **Humedad**: > 80 % **agrava**; si `air_temperature` > 30 °C y `air_humidity` > 70 % → elevar severidad 1 nivel.

### 3.5 Humedad

* < 30 % o > 70 % → *Moderado* (incomodidad / estrés térmico).
* > 80 % con T alta → agrava riesgo de *golpe de calor*.

### 3.6 Presión barométrica (proxy de choque)

* **Detección de eventos**: Δpresión > X hPa en ≤ N s → *Evento súbito* (explosión/choque).
  Sugerencia: X=5–10 hPa en < 10 s (ajustable en simulación).

### 3.7 Visibilidad y presencia

* **Luz**: valores muy bajos → *Riesgo de caídas* (penalización leve).
* **PIR**: si hay presencia (`pir_count>0`) y la sala está en estado *Alto/Crítico*, **priorizar rutas alternativas**.

---

## 4. Eventos complejos (combinaciones)

Se componen a partir de **patrones** en ventanas temporales:

* **Incendio**
  `air_temperature` > 50 °C **Y** (TVOC alto **O** IAQ alto) **Y/O** cambios en IR
  → Estado **Crítico**, exposición ≤ 1–3 min (según T).

* **Fuga de gas**
  TVOC alto **Y** (CO₂ elevado **O** caída de presión)
  → Estado **Alto/Crítico** según TVOC; exposición ≤ 1–5 min.

* **Explosión / onda de choque**
  Δpresión súbita **Y** subida brusca de T
  → **Bloqueo inmediato** hasta estabilización.

* **Condiciones extremas**
  T > 40 °C (WBGT proxy) **Y** humedad > 80 %
  → **Crítico**, exposición ≤ 1–3 min.

> **Fuera de alcance** actual (no hay sensores): CO, O₂, H₂S, radiación, %LEL. Se documentan pero no se procesan salvo simulación explícita.

---

## 5. Severidad, exposición y *score* de peligrosidad

### 5.1 Niveles de severidad

* **Verde** (Seguro): sin umbrales superados.
* **Amarillo** (Moderado): umbrales bajos superados; paso breve permitido.
* **Naranja** (Alto): riesgo significativo; exposición limitada (≤ 3–10 min según variable).
* **Rojo** (Crítico): exposición mínima (≤ 0.5–3 min) o bloqueo.

### 5.2 Tiempo de exposición permitido `T_max`

Por evento simple se calcula un `T_max` (tablas anteriores).
Para **combinaciones**, usar el **mínimo** de los `T_max` activos.

### 5.3 Índice de peligrosidad `R ∈ [0,1]`

Combina señales normalizadas:

```
R = 1 - ∏(1 - w_i * s_i)
```

* `s_i`: severidad normalizada por variable (0, 0.33, 0.66, 1.0).
* `w_i`: peso por importancia (p. ej., CO₂=0.25, TVOC=0.25, T/H=0.35, presión=0.15).
* Si un evento complejo está activo (Incendio, Explosión) → forzar `R=1`.

---

## 6. Integración con el grafo de navegación

Conectamos el CEP con el cálculo de rutas:

1. **Filtrado por movilidad (ya implementado)**
   En el grafo dual, mantener solo nodos `WALK` y `RAMP` (o enmascarar otros a 0).

2. **Penalización por peligrosidad**
   Para cada **nodo** (sala) con índice `R`:

   * **Penalización suave**: `w' = w * (1 + k * R)` (p. ej., `k=3`).
   * **Bloqueo**: si `R ≥ R_bloqueo` (p. ej., 0.85) o si `tiempo_travesía > T_max` → **eliminar aristas** incidentes o fijarlas a 0 (como ya haces con el “masking”).

3. **Chequeo de exposición** en rutas:

   * Suma de tiempos esperados en nodos/aristas con riesgo **no debe superar** su `T_max`.
   * Si se supera, el planificador debe escoger alternativa o partir la ruta en segmentos seguros.

---

## 7. Simulación del stream de sensores (para pruebas)

**Estrategia simple** (reproducible y suficiente para ensayos):

* **Base**: para cada sala, generar un valor medio realista por variable + ruido blanco (p. ej., ±5%).
* **Eventos**: inyectar “picos” o “mesetas” durante ventanas temporales:

  * Incendio: subida de T (60–80 °C) + TVOC alto + caída de luz opcional.
  * Fuga: TVOC alto + CO₂ en alza + leve caída de presión.
  * Choque: Δpresión súbita + subida breve de T.
* **Frecuencia**: 1 Hz–0.1 Hz por sensor (ajustable).
* **Calidad**: simular *dropouts*, latencia y deriva (para IAQ: opción *sin calibrar*).
* **Etiquetado**: para cada *tick*: `{sala, timestamp, lecturas, eventos_simples, eventos_complejos, R, T_max}`.

---

## 8. Reglas CEP (pseudocódigo)

**Ventanas**: `Wshort=30s`, `Wlong=120s`.

```pseudo
for each sala, cada segundo:
  x = median(last 30s de co2, iaq, tvoc, temp, hum, pres, light)
  # Eventos simples
  sev_co2  = bucket_CO2(x.co2)
  sev_iaq  = bucket_IAQ(x.iaq, calib_iaq)
  sev_tvoc = bucket_TVOC(x.tvoc)
  sev_temp = bucket_TEMP(x.temp, x.hum)
  sev_light= bucket_LIGHT(x.light)
  sev_pres = delta_pressure(last 10s de pres) ? ALTO : VERDE

  # Eventos complejos
  incendio = (sev_temp >= ALTO) AND (sev_tvoc >= MODERADO OR sev_iaq >= MODERADO)
  fuga     = (sev_tvoc >= ALTO) AND (sev_co2 >= MODERADO OR sev_pres == ALTO)
  choque   = (sev_pres == ALTO AND sev_temp >= MODERADO)

  # Severidad final y T_max
  sev_final = max(sev_co2, sev_iaq, sev_tvoc, sev_temp, sev_light, sev_pres)
  if incendio or fuga or choque: sev_final = CRITICO

  T_max = min( T_co2, T_tvoc, T_temp, ... )  # ignorar None
  R = severity_to_score(sev_final, eventos_complejos)
```

---

## 9. Estados y visualización

Para cada sala:

* **Estado**: Verde / Amarillo / Naranja / Rojo.
* **Etiquetas**: `R` (0–1), `T_max` (min), eventos activos.
* **Mapa**: colorear nodos; **grisar** nodos bloqueados; **ensanchar** aristas seguras.

---

## 10. Consideraciones de calidad

* **Suavizado**: usar mediana/percentiles en ventana para evitar falsos positivos por ruido.
* **Histeresis**: activar un evento al subir el umbral y desactivarlo al bajar por debajo de un umbral *inferior* (evita parpadeos).
* **Sensor health**: si `battery_voltage` bajo o `calib_iaq` inválida → marcar **incertidumbre** y reducir el peso de esa variable en `R`.

---

## 11. Lo que **no** se procesa (pero se documenta)

* **CO**, **O₂**, **H₂S**, **%LEL**, **radiación**.
  Se dejan como **amenazas conocidas** sin sensor real en esta fase. Se podrían **simular** como variables adicionales si se desea evaluar la arquitectura completa.

---

## 12. Ejemplo (sala S-101, instante t)

* Lecturas (mediana 30 s): `co2=5 600 ppm`, `tvoc=1 250 ppb`, `temp=32 °C`, `hum=78%`, `pres Δ10s=+1 hPa`.
* Eventos simples: `CO₂=Crítico`, `TVOC=Alto`, `TEMP=Moderado(agravado por hum)`.
* Evento complejo: `Fuga de gas = TRUE` (TVOC alto + CO₂ alto).
* `T_max = min(3 min por CO₂, 5 min por TVOC, …) = 3 min`.
* `R ≈ 0.9` → **Rojo**.
* Integración en ruta: nodo **bloqueado** (o `w'` muy alto); si una arista implica estancia estimada > 3 min en S-101 → **descartada**.

---

## 13. Ontología (mínima) de sensores de evacuación

* **Sensor**: (id, sala, variables[], unidad, estado).
* **Lectura**: (sensor_id, variable, valor, unidad, t).
* **Sala**: (id, nodo_grafo, atributos).
* **EventoSimple**: (sala_id, tipo, severidad, t_inicio, t_fin).
* **EventoComplejo**: (sala_id, tipo, severidad, t_inicio, t_fin, causas[]).
* **EvaluaciónSala**: (sala_id, `R`, `T_max`, estado, justificación, timestamp).

Relaciones:

* `Sensor` **mide** `Variable`.
* `Lectura` **alimenta** `EventoSimple`.
* `EventoComplejo` **agrega** `EventoSimple`.
* `EvaluaciónSala` **resume** el estado y **alimenta** el **grafo** (pesos/bloqueos).

---

## 14. Resumen

* Se propone un **CEP simulado** con **reglas básicas** y **ventanas cortas** para etiquetar salas en **tiempo (casi) real**.
* El sistema produce un índice `R` y un `T_max` por sala, integrándose con el grafo (penalizaciones/bloqueos) y respetando el **filtro de movilidad** (solo `WALK` y `RAMP`).
* Las amenazas sin sensor se mantienen **fuera de alcance**, aunque pueden **simularse** si se requiere validar la arquitectura extremo a extremo.

> Este diseño permite **probar la arquitectura de rutas y visualización** sin necesitar instrumentación física, manteniendo un modelo de riesgo **coherente y justificable** para el TFG.

---
---
---
# Módulo de *CEP* con datos simulados para balizas LoRaWAN (forma y flujo realistas)

> **Objetivo del apartado (TFG).** Documentar cómo **habríamos ingerido datos reales** de balizas IoT LoRaWAN y, dado que no ha sido posible desplegarlas a tiempo, **definir una simulación** con el **mismo formato** de mensajes y un **conjunto simple de reglas CEP** para evaluar peligrosidad de salas. La simulación alimenta el backend y permite probar el resto de la arquitectura (almacenamiento, analítica, visualización y enrutado).

---

## 1) Contexto y arquitectura de referencia

El sistema contempla sensores ambientales instalados en edificios del campus; éstos envían tramas LoRaWAN que llegan a un **gateway** (p. ej. Dragino LPS8-N), se entregan a **The Things Stack/TTN** y, desde allí, a un **webhook HTTP** en nuestro servidor (*middleware*) para decodificar y almacenar (InfluxDB/Cloudant) y disparar reglas CEP. Esta vista está alineada con la arquitectura que ya se trabajó (URJC/SENIALAB) y el despliegue de balizas Deep-Insight (DBLITE).  

* **Gateway Dragino LPS8-N.** Puente LoRaWAN→IP, compatible con TTN (Semtech packet forwarder/Station, concentrador SX1302). ([dragino.com][1])
* **Red TTN / The Things Stack.** Define *frequency plans* (en Europa **EU863-870**; en TTN se recomienda RX2 **SF9** para community plan) y expone integraciones **Webhooks** y **payload formatters**. ([thethingsindustries.com][2])
* **Webhook HTTP.** En TTN se crea desde *Integrations → Webhooks* indicando nuestra URL y formato JSON; TTN exige que el endpoint responda **200 OK**. ([thethingsindustries.com][3])
* **Almacenamiento.**

  * **InfluxDB** para series temporales (formato **line protocol**). ([docs.influxdata.com][4])
  * **IBM Cloudant** (NoSQL JSON, API HTTP) para documentos y metadatos. ([IBM][5])

---

## 2) ¿Cómo llegan los datos desde las balizas (flujo real)?

1. **Uplink LoRaWAN** → 2) **Gateway** → 3) **The Things Stack** (aplicación) → 4) **Webhook** (nuestro endpoint).
   TTN entrega en JSON con los campos estándar, por ejemplo:

* `uplink_message.frm_payload`: **payload binario** en **Base64**, tal y como lo recibe TTN.
* `uplink_message.decoded_payload`: resultado del **payload formatter JavaScript** (si está configurado a nivel de dispositivo o aplicación). ([thethingsindustries.com][6])

Un **mensaje real** del proyecto URJC muestra estos campos (evento `as.up.data.forward`) y cómo **`frm_payload`** viaja en Base64; al aplicar el *formatter* del fabricante se obtiene un JSON con **co2, iaq, tvoc, temperatura, humedad, presión, luz, PIR, voltaje**, etc. (ver dossier del despliegue).  

---

## 3) Formato que **simularemos** (idéntico al de TTN)

Para que el resto de la arquitectura funcione sin cambios, **nuestro simulador generará el mismo esquema** que envía TTN por webhook:

```json
{
  "name": "as.up.data.forward",
  "time": "2025-04-30T10:21:05Z",
  "data": {
    "end_device_ids": {
      "device_id": "dbod202304urjc001",
      "dev_eui": "A8610A34352E7D10",
      "application_ids": {"application_id": "smarte2-smartcampus-urjc-mostoles"}
    },
    "received_at": "2025-04-30T10:21:05.100Z",
    "uplink_message": {
      "f_port": 3,
      "f_cnt": 118,
      "frm_payload": "AQECAwQ=",                   // opcional (Base64 ficticio)
      "decoded_payload": {
        "co2":               {"displayName":"CO2", "value": 463,  "unit":"ppm"},
        "iaq":               {"displayName":"Indoor Air Quality","value": 136, "unit":"adim"},
        "tvoc":              {"displayName":"TVOC","value": 570,  "unit":"ppb"},
        "air_temperature":   {"displayName":"Air temperature","value": 20.2,"unit":"°C"},
        "air_humidity":      {"displayName":"Air humidity","value": 55.1,"unit":"%"},
        "barometric_pressure":{"displayName":"Barometric pressure","value": 947.2,"unit":"hPa"},
        "ambient_light":     {"displayName":"Ambient light","value": 164,"unit":"counts"},
        "pir_count":         {"displayName":"PIR count","value": 0,"unit":"counts"},
        "battery_voltage":   {"displayName":"Battery voltage","value": 3.71,"unit":"V"}
      }
    }
  }
}
```

* Este **shape** coincide con la documentación de TTN (Base64 en `frm_payload` y datos legibles en `decoded_payload`). ([thethingsindustries.com][6])
* Los **nombres/unidades** de variables siguen el *formatter* de las DBLITE usado en el proyecto. 

> **Nota.** Si se desea realismo extremo, el simulador también puede **construir bytes** y **codificarlos a Base64** y (opcionalmente) **omitir `decoded_payload`**, dejando que nuestro backend ejecute el mismo *formatter* JS que en TTN. ([thethingsindustries.com][7])

---

## 4) Ingesta y almacenamiento (simulado pero realista)

* **Webhook** (Flask/FastAPI): recibe exactamente el JSON anterior (`POST`), valida campos clave (`dev_eui`, `received_at`, `decoded_payload`) y persiste.
* **InfluxDB (series temporales)**: cada punto como *line protocol*:
  `env,dev_eui=A8610A34352E7D10 campus=Mostoles,edificio=Lab3 co2=463i,iaq=136i,tvoc=570i,air_temperature=20.2,air_humidity=55.1,barometric_pressure=947.2 1714472465100000000` ([docs.influxdata.com][4])
* **Cloudant (documentos)**: guardar el **mensaje original** y un **resumen** por lectura (útil para auditoría y *replay*). Cloudant es JSON con API HTTP (CouchDB-compatible). ([cloud.ibm.com][8])

---

## 5) Reglas **CEP** mínimas (simples, explicables y ejecutables)

> Buscamos reglas **deterministas** y **parametrizables** sobre ventanas cortas (p. ej. últimos 5-10 min). Se calculan por **sala** / **nodo** y se publican como un **estado de peligrosidad** (OK / Precaución / Peligro), además de un **score** 0-100.

### 5.1 Variables disponibles (según *formatter*)

* `co2 (ppm)`, `tvoc (ppb)`, `iaq (adim)`, `air_temperature (°C)`, `air_humidity (%)`,
  `barometric_pressure (hPa)`, `ambient_light (counts)`, `pir_count (counts)`, `battery_voltage (V)`. 

### 5.2 Umbrales base (simulación con soporte bibliográfico cuando aplica)

* **CO₂**:

  * **Info/confort**: > 1000 ppm (no es límite normativo, indicador de ventilación; ASHRAE aclara que 62.1 **no fija** 1000 ppm como límite de IAQ). Usar como *semáforo* de confort/ventilación. ([ashrae.org][9])
  * **Riesgo laboral (PEL/REL)**: **5000 ppm TWA 8 h** (OSHA/NIOSH); **STEL 30 000 ppm**. Para simulación, tratar > 5000 ppm como **Peligro**. ([Seguridad y Salud Ocupacional][10])
* **TVOC**: no existe estándar universal; usar umbrales heurísticos: > 500 ppb **Precaución**, > 3000 ppb **Peligro** (sensibles a modelo de sensor; se ajustan empíricamente).
* **IAQ (índice adimensional del fabricante)**: > 100 **Precaución**, > 150 **Peligro** (heurístico).
* **Temperatura/Humedad**: fuera de [15–30] °C o **HR** > 70 % → **Precaución**; por encima de 32–35 °C o WBGT alto → **Peligro** (regla simplificada para el TFG).
* **Presión muy baja** + **CO₂ alto** puede elevar riesgo de malestar → sumar puntos al *score*.
* **PIR** > 0 eleva **prioridad** (hay ocupación).

> Estos valores son **operativos para simulación** y pueden ajustarse a normativa específica si se dispone (p. ej., guías de confort/ventilación internas).

### 5.3 Composición de eventos (reglas de ejemplo)

* **Evento simple (ES):** `ES_CO2_ALTO := co2 > 1000` (con histéresis y media móvil 3 muestras).
* **Evento complejo (EC):**

  * `EC_CALOR_Y_HUMEDAD := (air_temperature > 30) AND (air_humidity > 70)`
  * `EC_AIRE_VICIADO := ES_CO2_ALTO AND (tvoc > 500 OR iaq > 100)`
  * `EC_PELIGRO_INMEDIATO := (co2 > 5000) OR (air_temperature > 40)`
* **Score** (0-100): suma ponderada de z-scores/umbrales; **estado** = {OK, Precaución, Peligro}.
* **Tiempo de exposición** (opcional): si `tiempo_estimado_tránsito` > `t_max_variable`, elevar estado (reglas de exposición se mantienen simples para el TFG).

---

## 6) Vínculo con planificación de rutas

El **estado de peligrosidad por sala** se **propaga** a la red de navegación:

* Si una sala está en **Peligro**, **penalizamos** sus aristas (peso → ∞) o **bloqueamos** el nodo; si está en **Precaución**, aumentamos el **coste** (p. ej., +30 %).
* Esto encaja con el motor de rutas ya implementado (matriz de costes/adyacencia y filtros de movilidad), sin cambiar la forma del grafo.

---

## 7) *Playbook* mínimo para ejecutar la simulación

1. **Generación de datos**: proceso que publica cada *X* segundos un JSON con el **shape TTN** del punto 3.
2. **Webhook (Flask/FastAPI)**: endpoint `/entry` que:

   * valida y extrae `dev_eui`, `received_at`, `decoded_payload.*`;
   * **escribe** en **InfluxDB** (line protocol) e **inserta** el documento completo en **Cloudant**;
   * evalúa **CEP** y publica `{id_sala, estado, score, timestamp}` en una *topic* interna (o tabla).
3. **Dashboards** (Grafana/PowerBI) leen de InfluxDB/servicios y pintan **mapa de riesgo por sala**.
4. **Ruta**: el servicio de enrutado consulta el estado para **ajustar pesos**/bloqueos al calcular el camino.

---

## 8) Referencias clave

* **TTN / The Things Stack**
  Mensajes e **integraciones JSON**, **payload formatter** (JS) y **frm_payload (Base64)**; creación de **webhooks**: ([thethingsindustries.com][11])
  *Tipos de mensajes / data messages* (contexto LoRaWAN): ([The Things Network][12])
  Planes de **frecuencia** (EU863-870, **SF9 RX2 recomendado** en TTN): ([thethingsindustries.com][2])
* **Gateway Dragino LPS8-N** (manual/hoja de producto): ([dragino.com][1])
* **Almacenamiento**
  **InfluxDB** (*line protocol*): ([docs.influxdata.com][4])
  **IBM Cloudant** (JSON/HTTP API): ([IBM][5])
* **Límites CO₂ (apoyo bibliográfico)**
  **OSHA/NIOSH** 5000 ppm TWA, 30 000 ppm STEL: ([Seguridad y Salud Ocupacional][10])
  **ASHRAE**: 62.1 **no impone** 1000 ppm como límite de IAQ; ese valor se usa a veces como proxy de ventilación: ([ashrae.org][9])
* **Documentación interna del despliegue** (URJC/SENIALAB): arquitectura, ejemplo de **webhook TTN** real y *formatter* de balizas:   

---

## 9) Qué entregables deja este módulo listos para el TFG

1. **Especificación de formato de mensaje** (idéntico a TTN) y **campos/variables**.
2. **Reglas CEP mínimas** (claras, reproducibles y ajustables).
3. **Esquemas de persistencia** (Influx line protocol + documento Cloudant).
4. **Interfaz** entre CEP y el motor de rutas (estado por sala → penalización de pesos).
5. **Simulador de balizas** que permite probar todo el **pipeline** sin hardware.

Si quieres, te dejo también un esqueleto de **endpoint Flask** y un **script de simulación** listos para pegar y correr con estas reglas.

[1]: https://www.dragino.com/downloads/downloads/LoRa_Gateway/LPS8/LPS8_LoRaWAN_Gateway_User_Manual_v1.3.2.pdf?utm_source=chatgpt.com "LPS8 LoRaWAN Gateway User Manual - Document Version"
[2]: https://www.thethingsindustries.com/docs/concepts/features/lorawan/frequency-plans/?utm_source=chatgpt.com "Frequency Plans | The Things Stack for LoRaWAN"
[3]: https://www.thethingsindustries.com/docs/integrations/webhooks/creating-webhooks/?utm_source=chatgpt.com "Creating Webhooks | The Things Stack for LoRaWAN"
[4]: https://docs.influxdata.com/influxdb/v2/reference/syntax/line-protocol/?utm_source=chatgpt.com "Line protocol | InfluxDB OSS v2 Documentation"
[5]: https://www.ibm.com/products/cloudant?utm_source=chatgpt.com "IBM Cloudant"
[6]: https://www.thethingsindustries.com/docs/integrations/payload-formatters/javascript/uplink/?utm_source=chatgpt.com "Uplink | The Things Stack for LoRaWAN"
[7]: https://www.thethingsindustries.com/docs/integrations/payload-formatters/javascript/?utm_source=chatgpt.com "JavaScript | The Things Stack for LoRaWAN"
[8]: https://cloud.ibm.com/docs/Cloudant?topic=Cloudant-ibm-cloudant-basics&utm_source=chatgpt.com "Using IBM Cloudant"
[9]: https://www.ashrae.org/file%20library/about/government%20affairs/public%20policy%20resources/briefs/indoor-carbon-dioxide-ventilation-and-indoor-air-quality_2023.pdf?utm_source=chatgpt.com "indoor carbon dioxide, ventilation and indoor air quality"
[10]: https://www.osha.gov/chemicaldata/183?utm_source=chatgpt.com "CARBON DIOXIDE | Occupational Safety and Health ..."
[11]: https://www.thethingsindustries.com/docs/integrations/data-formats/?utm_source=chatgpt.com "Data Formats | The Things Stack for LoRaWAN"
[12]: https://www.thethingsnetwork.org/docs/lorawan/message-types/?utm_source=chatgpt.com "Message Types"
