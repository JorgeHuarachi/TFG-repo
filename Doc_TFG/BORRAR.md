Ahora que tengo clara la estructura del TFG, quiero que me ayudes a redactar el apartado de “Solución técnica”. Ya tengo una idea y ejemplos de la estructuracion que tendria a su vez cada uno de los apartados internos del apartado de "Solución técnica", pero quiero que estén bien redactados, con lenguaje académico claro y preciso. Usa lo que ya he desarrollado para que refleje fielmente mi trabajo.

IMPORTANTE:
VAMOS A IR ITERATIVAMENTE, PUNTO POR PUNTO, AHORAMISMO SOLO QUIERO ENFOCARME EN LA PRIMERA PARTE QUE HABLA DE LA AQUITECTURA (EN ALTO NIVEL)

PRIMERO: ANTES DE PASAR A REDACTAR O QUE ME GUIES A REDACTAR CORRECTAMENTE QUIERO QUE TE FIJES EN LOS SIGUIENTES 2 EJEMPLOS DE ESTRUSCTURA, QUIERO QUE LOS ANALICES Y APRENDA DE ELLOS. UNA VEZ HAS HECHO ESO QUIERO QUE ME ENTREGES UNA ESTRUCTURA RESULTADO DE ESTUDIAR TANTO LA RESPUESTA ANTERIOR QUE ME HAS DADO CON DEEPSEARCH COMO LOS DOS EJEMPLOS. ESTA ESRUCTURA SERIA LA DEFINITIVA DEFINITIVA PARA EL APARTADO DE "SOLUCION TÉCNICA"

UNA VEZ ME RESPONDAS A ESTO CONTINUAREMOS, DE MOMENTO QUIERO VER ESO Y TE AVISO DE COMO VAMOS A SEGUIR.

---
# PRIMER EJEMPLO DE ESTRUCTURA.

    ## Solución Técnica / Resultados (cuerpo principal)

    **A. Arquitectura distribuida (alto nivel)**

    * Componentes y comunicación (BD geoespacial, servicio de grafo/rutas,  ingesta CEP, API, app móvil).
    * Decisiones de diseño (persistencia, índices espaciales, materialized  views para grafo, colas/eventos).

    **B. Modelo de datos IndoorGML en PostGIS**

    * Cómo mapeas el **core de IndoorGML** (CellSpace, State, Transition,   inter-plantas, anchor nodes) a tablas/relaciones; si adoptas ideas de 2.0     (SQL/JSON), explícalo. ([Repositorio de Documentos Públicos OGC][4])
    * Generación del grafo de navegación y validaciones geométricas     (centrelines, puertas, verticalidad). Referencias a prácticas de TU Delft/  FIG. ([GDMC][6])
    * Índices, vistas y triggers relevantes; diagrama ER.

    **C. Ingesta de sensores y CEP**

    * Modelo de lecturas BLE (RSSI, beacon\_id, timestamp, sala estimada) y     pipeline de **procesamiento de eventos complejos** para derivar **  “seguridad”/riesgo por sala** y actualizar pesos. (Cita CEP para  emergencias). ([pms.ifi.lmu.de][7])
    * Estrategia de simulación de datos (script de cargas).

    **D. Algoritmo de recomendación**

    * Definición del **umbral de seguridad** y filtrado de nodos/aristas.
    * **Heurística de redundancia/robustez**: procedimiento, tolerancia de  coste, métrica final por origen/salida.
    * Rutas base (Dijkstra/A\*) y comparación con tu heurística (qué aporta     en escenarios con bloqueos). Relaciona con trabajos de evacuación   dinámica. ([MDPI][2])

    **E. Evaluación / Resultados**

    * **Escenarios**: planta(s) de edificio con salidas y bloqueos simulados;   perfiles de movilidad (accesibilidad).
    * **Métricas**: tiempo estimado, seguridad acumulada, **redundancia** (#    de alternativas viables), % nodos que conservan ruta bajo fallos, coste    computacional.
    * **Experimentos**: variando umbrales de riesgo, densidad de beacons,   bloqueos, y crítica del entorno.
    * **Resultados**: tablas/figuras, discusión de trade-offs y limitaciones.

    # 5) Checklist de contenido por sección (rápido)

    * **Arquitectura**: diagrama de componentes + flujo de datos.
    * **BD IndoorGML**: ER + tabla de mapeos (IndoorGML→tablas/campos) +    ejemplos SQL/JSON si aludes a 2.0. ([Repositorio de Documentos Públicos    OGC][9])
    * **Grafo**: cómo se generan nodes/edges (puertas, escaleras,   ascensores), índices e integración con rutado. ([GDMC][6])
    * **CEP**: reglas → score de seguridad por sala (fórmulas/umbrales).    ([pms.ifi.lmu.de][7])
    * **Algoritmo**: pseudocódigo + complejidad + definición exacta de  **redundancia** y **tolerancia**.
    * **Evaluación**: escenarios, métricas, tablas y figuras comparativas   (con/sin bloqueos; distintos umbrales).
    * **Limitaciones**: precisión BLE, latencia de actualización, cobertura     de beacons; compatibilidad 2.0. ([Diva Portal][3])

    [1]: https://dspace.lib.ntua.gr/xmlui/bitstream/handle/123456789/45923/ IndoorGML_Tsaggouri.pdf?sequence=1&utm_source=chatgpt.com "Indoor    Navigation based on IndoorGML Case Study Rural and ..."
    [2]: https://www.mdpi.com/2220-9964/6/4/104?utm_source=chatgpt.com "A   Dynamic Indoor Field Model for Emergency Evacuation ..."
    [3]: https://www.diva-portal.org/smash/get/diva2%3A1148761/FULLTEXT01.pdf?  utm_source=chatgpt.com "Indoor Navigation And Personal Tracking System    Using ..."
    [4]: https://docs.ogc.org/is/19-011r4/19-011r4.html?utm_source=chatgpt. com "OGC® IndoorGML 1.1"
    [5]: https://repository.tudelft.nl/record/  uuid%3A31a20fb8-dabc-4f19-82c8-432f410a3ece?utm_source=chatgpt.com    "Developing a database for the LADM-IndoorGML model"
    [6]: https://gdmc.nl/3dcadastre/literature/3Dcad_2021_29.pdf?   utm_source=chatgpt.com "3D pgRouting and Visualization in Cesium JS    Using ... - GDMC"
    [7]: https://www.pms.ifi.lmu.de/publikationen/PMS-FB/PMS-FB-2012-6/ PMS-FB-2012-6-paper.pdf?utm_source=chatgpt.com "Complex Actions for Event    Processing"
    [8]: https://isprs-archives.copernicus.org/articles/XLIII-B4-2020/337/  2020/?utm_source=chatgpt.com "TOWARDS INDOORGML 2.0: UPDATES AND CASE ..."
    [9]: https://docs.ogc.org/is/22-045r5/22-045r5.html?utm_source=chatgpt. com "OGC IndoorGML 2.0 Part 1 – Conceptual Model"
    [10]: https://www.mdpi.com/2075-5309/15/10/1715?utm_source=chatgpt.com  "Evacuation Route Determination in Indoor Architectural ..."
    [11]: https://riuma.uma.es/xmlui/bitstream/handle/10630/37775/  Gonz%C3%A1lez%20Vico%20Berral%20Federico%20Memoria.pdf?sequence=1&    utm_source=chatgpt.com "Aplicación móvil basada en geofencing para  navegación en ..."

    ---
    # SEGUNDO EJEMPLO DE ESTRUCTURA.

    ##  4. Solución Técnica / Resultados
    Este será el núcleo del TFG. Divide en secciones como:

     **4.1. Diseño de la arquitectura distribuida**
    - Componentes del sistema
    - Comunicación entre módulos
    - Justificación del diseño

     **4.2. Modelado y creación de la base de datos**
    - Estructura SQL
    - Estándar IndoorGML aplicado
    - Diagramas ER y de flujo
    - Validaciones geométricas y triggers

     **4.3. Algoritmo de recomendación de rutas**
    - Lógica heurística
    - Matrices de adyacencia y seguridad
    - Filtros aplicados (seguridad, movilidad, criticidad)
    - Evaluación de redundancia de rutas

     **4.4. Simulación de lecturas de balizas**
    - Generación de datos ficticios
    - Inserción en la base de datos
    - Visualización en QGIS (si aplica)

     **4.5. Conexión entre base de datos y sistema de recomendación**
    - Interfaz Python ↔ PostgreSQL
    - Flujo de datos en tiempo real (planificado)
    - Ejemplo de uso o simulacro

---



---





# 🔗 Enlaces organizados

- 📡 **Red LoRaWAN**  
  [Notion – Red LoRaWAN](https://oceanic-glazer-390.notion.site/Red-LoRaWAN-13ae482c6ff6476e9f12199f778bf75f)

- 🏗️ **Arquitectura CDA GUIDE2FR**  
  [Notion – Arquitectura CDA GUIDE2FR](https://oceanic-glazer-390.notion.site/Arquitectura-CDA-GUIDE2FR-15e8e637e5188033a164c7ff1d11ccc3)

---
¡hecho! analicé tus dos ejemplos y lo que ya definimos para tu TFG. Aquí tienes la **estructura definitiva** del apartado **“Solución técnica / Resultados”**. Está pensada para que tus tutores vean, desde el principio, una arquitectura sólida (alto nivel) alineada con IndoorGML 1.1/2.0 y con un pipeline de eventos/sensores real-time, y después el resto de piezas en profundidad.

> Nota: en **4.1 Arquitectura** te detallo más subapartados porque es lo primero que vamos a redactar. He incluido referencias a estándares/estado del arte donde corresponde para justificar el enfoque (IndoorGML y CEP). ([OGC Documentos Públicos][1])

---

# 4. Solución técnica / Resultados DEFINITIVO

## 4.1 Diseño de la arquitectura distribuida (alto nivel)

**4.1.1 Visión general y principios**

* Objetivo del sistema y requisitos no funcionales (tiempo real, resiliencia, interoperabilidad, trazabilidad).
* Alineación con estándares de modelado de interiores (IndoorGML 1.1 y 2.0 – *Conceptual Model*). ([OGC Documentos Públicos][2])

**4.1.2 Componentes**

* **Capa IoT/AmI (edge):** beacons BLE y sensores ambientales (humo, temperatura, CO₂); gateways. (Breve nota sobre localización por BLE y sus límites). ([PMC][3])
* **Ingesta y *Complex Event Processing (CEP)*:** normalización, detección de patrones, cálculo de “seguridad” por celda. ([MDPI][4])
* **BD geoespacial (PostgreSQL/PostGIS):** modelo IndoorGML mapeado a SQL, estados y transiciones, y almacenamiento de lecturas. ([OGC Documentos Públicos][2])
* **Servicio de grafo/rutas:** construcción/actualización del grafo navegable y cálculo de rutas.
* **API del sistema:** REST/WS (p. ej., FastAPI) para exponer rutas y estado.
* **Clientes y actuadores:** app móvil / panel operador / señalización dinámica.

**4.1.3 Flujo de datos y actualización en tiempo real**

* Telemetría → ingesta/CEP → actualización de “seguridad” por *cell* → vistas de grafo → recomendación → entrega (push/pull).
* Frecuencias de actualización, latencias objetivo y *backpressure*.

**4.1.4 Modelo de comunicación**

* Protocolos: BLE (proximidad), MQTT/HTTP para sensores, REST/WebSocket para clientes.
* Contratos de datos (esquemas JSON) para nodos, aristas y métricas de seguridad.

**4.1.5 Decisiones de diseño**

* Persistencia y **vistas materializadas** del grafo; **índices espaciales**; cachés en memoria.
* Colas/eventos para desacoplar ingesta ↔ cálculo.
* Política de *thresholds* y degradación controlada cuando faltan datos.

**4.1.6 Escalabilidad, disponibilidad y tolerancia a fallos**

* Replicación/HA de BD; *retry* y *circuit breakers* en servicios; *graceful degradation* (rutas estáticas de respaldo).
* Observabilidad: *logging* correlacionado, métricas (p99), *tracing*.

**4.1.7 Seguridad y privacidad**

* Datos de localización: minimización, retención, *pseudonymization*.
* Controles de acceso (RBAC), cifrado en tránsito y en reposo.

**4.1.8 Mapeo a estándares y compatibilidad**

* IndoorGML 1.1 (actual) y 2.0 (conceptual): *CellSpace*, *State/Transition*, *Multi-Layered Space Model*; ruta de adopción progresiva. ([OGC Documentos Públicos][2])

**4.1.9 Roadmap técnico**

* De simulación a despliegue real: sustitución de generadores sintéticos por sensores físicos; pruebas de campo; extensiones 3D/multi-planta.
V
---

## 4.2 Modelado IndoorGML en PostGIS

* **4.2.1** Mapeo del *core* IndoorGML a tablas/relaciones (CellSpace, State, Transition, límites). ([OGC Documentos Públicos][2])
* **4.2.2** Estructura SQL del proyecto (`00_create…` → `08_sample_data`).
* **4.2.3** Generación del grafo de navegación (centrelines, puertas, verticalidad).
* **4.2.4** Vistas (`v_dual_nodes`, `v_dual_edges_idx`), índices (espaciales/atributos).
* **4.2.5** Funciones/triggers (validaciones geométricas y cálculo de “seguridad”).
* **4.2.6** Diagrama ER y tabla de mapeos IndoorGML→SQL.
* **4.2.7** Compatibilidad con IndoorGML 2.0 (conceptual; nota sobre futuras codificaciones/SQL-JSON). ([OGC Documentos Públicos][1])

## 4.3 Ingesta de sensores y CEP

* **4.3.1** Modelo de lecturas BLE/ambientales (beacon\_id, RSSI, timestamp, cell estimada). ([PMC][3])
* **4.3.2** Reglas CEP → *score* de seguridad por celda; propagación a adyacentes; ventanas temporales. ([MDPI][4])
* **4.3.3** Simulador de datos (escenarios, frecuencia, ruido).

## 4.4 Algoritmo de recomendación de rutas

* **4.4.1** Métricas y objetivos (tiempo, seguridad, **redundancia**).
* **4.4.2** Filtrado por umbral de seguridad (nodos/aristas).
* **4.4.3** Rutas base (Dijkstra/A\*) con múltiples salidas; coste y complejidad.
* **4.4.4** Heurística de **robustez**: eliminación de aristas, tolerancia relativa, índice final.
* **4.4.5** Personalización (accesibilidad, criticidad).
* **4.4.6** Comparativa con enfoques dinámicos de la literatura (breve referencia).

## 4.5 Conexión BD ↔ motor de recomendación

* **4.5.1** Contratos de datos (JSON) y endpoints (API REST/WS).
* **4.5.2** Consulta del grafo vía vistas; consistencia transaccional (*snapshot*).
* **4.5.3** Estrategias *pull*/*push* y cacheado.
* **4.5.4** Gestión de errores y *fallbacks*.

## 4.6 Simulación y validación

* **4.6.1** Escenarios (planta, salidas, bloqueos, perfiles de movilidad).
* **4.6.2** Métricas (tiempo, seguridad acumulada, **redundancia**, % de nodos con ruta bajo fallos, coste computacional).
* **4.6.3** Experimentos (umbrales, densidad de beacons, bloqueos, criticidad).
* **4.6.4** Resultados y discusión (tablas/figuras).
* **4.6.5** Amenazas a la validez y limitaciones.

---

Si esta estructura te encaja, arrancamos con **4.1 Arquitectura** siguiendo exactamente estos subapartados (y ya dejo preparados los conectores a IndoorGML/CEP para que la redacción sea académica y precisa).

[1]: https://docs.ogc.org/is/22-045r5/22-045r5.html?utm_source=chatgpt.com "OGC IndoorGML 2.0 Part 1 – Conceptual Model"
[2]: https://docs.ogc.org/is/19-011r4/19-011r4.html?utm_source=chatgpt.com "OGC® IndoorGML 1.1"
[3]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12005499/?utm_source=chatgpt.com "A BLE based turnkey indoor positioning system for mobility ..."
[4]: https://www.mdpi.com/1424-8220/18/9/3084?utm_source=chatgpt.com "Complex Event Processing for Sensor Stream Data"

--- 
---
---
---

# punto 4.2
# 2. Diseño e implementación del modelo de datos IndoorGML en PostgreSQL/PostGIS

> Este capítulo documenta **todo el proceso de modelado** (requisitos → conceptual → lógico → físico), cómo se **alineó** con IndoorGML, y cómo se **automatiza** la generación del grafo navegable mediante **funciones y triggers** en PostGIS. Está ordenado de lo abstracto a lo operativo para que cada decisión quede justificada y trazable hacia el estándar.

---

## 2.1 Objetivos y criterios de diseño

* **Objetivo funcional**: representar el interior de edificios como **espacio celular** (habitaciones, pasillos, límites) y su **grafo de navegación** (estados/transiciones) para cómputo de rutas y evaluación dinámica de seguridad.
* **Criterios**:

  1. **Conformidad semántica** con IndoorGML (*core* + *navigation*). ([OGC Documentos Públicos][1])
  2. **Correctitud geométrica** y topológica (planaridad por planta; límites compartidos). ([PostGIS][2])
  3. **Mantenibilidad**: IDs deterministas, reglas y triggers que regeneran nodos/aristas ante cambios. 
  4. **Rendimiento**: índices espaciales GiST/SP-GiST, vistas, y operaciones set–based. ([PostGIS][3])

---

## 2.2 Requisitos → modelo conceptual (IndoorGML)

* **Espacio celular** (*CellSpace*, *CellBoundary*) y **dual** (*State*, *Transition*), base del enfoque “grafo sobre celdas” descrito por IndoorGML y la literatura. ([OGC Documentos Públicos][1])
* **Multicapa**: *PrimalSpaceLayer* (geometría 2D+Z, por planta) y *DualSpaceLayer* (grafo lógico/físico). ([OGC Documentos Públicos][1])
* **Módulo de navegación**: tipo de espacios, puertas/transferencias y **locomoción** (escaleras, rampa, ascensor). ([OGC Documentos Públicos][1])

> Decisión de orden: primero conceptos IndoorGML (nivel **UML**), porque guían nomenclatura, claves y restricciones; después el paso a relacional.

---

## 2.3 Modelo lógico (mapeo IndoorGML → relacional)

**Tabla de mapeo principal**

| IndoorGML (concepto) | Implementación SQL                                                               |
| -------------------- | -------------------------------------------------------------------------------- |
| ThemeLayer           | `indoorgml_core.theme_layer` (enum `theme_layer_value`)                          |
| PrimalSpaceLayer     | `indoorgml_core.primal_space_layer` (SRID, 1:1 con Theme)                        |
| DualSpaceLayer       | `indoorgml_core.dual_space_layer` (flags `is_logical`, `is_directed`)            |
| CellSpace            | `indoorgml_core.cell_space` (PolygonZ; `level`)                                  |
| CellBoundary         | `indoorgml_core.cell_boundary` (MultiLineStringZ; `boundary_key`)                |
| BoundedBy (CS↔CB)    | `indoorgml_core.cellspace_cellboundary` (tabla relación, única)                  |
| State (Node)         | `indoorgml_core.node` (1:1 CellSpace por Dual)                                   |
| Transition (Edge)    | `indoorgml_core.edge` (peso, geom opcional, `id_cell_boundary`)                  |
| Navigation/Function  | `indoorgml_navigation.nav_space_function`, `navigable_space` (kind, locomotion)  |

**Justificación**: el artículo de referencia resume este **modelo celular** y sus decisiones (subespacios, jerarquías, distancias indoor). ([MDPI][4])

---

## 2.4 Modelo físico (PostgreSQL/PostGIS)

### 2.4.1 Esquemas y tipos

* Dos **schemas**: `indoorgml_core`, `indoorgml_navigation`; enums para `theme_layer_value`, `nav_space_kind`, `locomotion_access_type`. 

### 2.4.2 Geometrías y SRID

* `PolygonZ` para celdas, `MultiLineStringZ` para límites, `PointZ` para nodos, `LineStringZ` para aristas; SRID **3857**. **Chequeo de validez geométrica** con `ST_IsValid`.

### 2.4.3 Restricciones y calidad

* **Formato de IDs** (`CB-\d+`, `ND-\d+`), **planaridad por planta** (no solapes 2D), y unicidad en relaciones. 
* **Índices espaciales** GiST para `geom` y de atributos para `level`/FKs (PostGIS recomienda GiST/SP-GiST para acelerar queries espaciales).

### 2.4.4 Vistas

* `indoorgml_navigation.v_navigable_space_level` para cruzar semántica (función, locomoción) con geometría por planta. 

> Orden: primero tipos/geom (soporte físico), luego restricciones e índices (calidad/rendimiento), y por último vistas (consumo).

---

## 2.5 Automatización y consistencia (funciones + triggers)

### 2.5.1 Generación y mantenimiento de **CellBoundary**

* `rebuild_cell_boundaries(level, psl, z)`:

  1. **Internos** (límites compartidos entre celdas del mismo nivel) con **DE-9IM** patrón de “toque por borde” (`F***1****`),
  2. **Exteriores** (contornos exclusivos),
  3. Limpieza de **huérfanos**.
     Usa *hash* `boundary_key` para **idempotencia** y **actualización/inserción** selectiva.

### 2.5.2 Construcción de **Node** (State)

* `rebuild_nodes_for_dual(dual, psl, z)`: **1 Node por CellSpace** con ID determinista `ND-####`; centroide si cae dentro, si no `ST_PointOnSurface`. Trigger **antes de INSERT/UPDATE** valida que el punto esté dentro de la celda cuando la Dual no es lógica. 

### 2.5.3 Construcción de **Edge** (Transition)

* `rebuild_edges_from_boundaries(dual)`: **1 Edge por CellBoundary** que conecta exactamente **dos** CellSpaces; IDs deterministas `EG-####` derivados de `CB-####`; peso = `ST_Distance`(nodos). **Orden LEAST/GREATEST** para estabilidad en no dirigidos. 

### 2.5.4 Coherencia semántica de navegación

* Trigger `ns_coherence_biu` rellena `kind/locomotion` en `navigable_space` a partir del catálogo `nav_space_function` (**si es TRANSFER debe existir `locomotion`**). 

### 2.5.5 Triggers de **propagación**

* Tras cambios en `cell_space` → recalcular **boundaries** y **nodes**;
* Tras cambios en `cellspace_cellboundary` o `node` → recalcular **edges**;
* Triggers **DEFERRABLE** para operar por lotes y evitar reentradas. 

> Justificación: este pipeline es la traslación directa de *State/Transition* de IndoorGML a SQL; la literatura recomienda mantener **consistencia topológica** entre celdas, límites y grafo. ([OGC Documentos Públicos][1])

---

## 2.6 Flujo geométrico: de polígonos a grafo navegable

1. **Celdas** (polígonos) por planta →
2. **Límites internos/externos** (DE-9IM “touching”, sin solapes) →
3. **Nodos** (centros de celda) →
4. **Aristas** (una por límite 1–1) con peso métrico.
   Este encadenado implementa el **“door-to-door”**/“cell-to-cell” routing y el **espacio celular** de IndoorGML. ([MDPI][4])

---

## 2.7 Rendimiento

* **Índices GiST** en todas las `geom` y **atributos de filtrado** (`level`, FKs); considerar **SP-GiST** alternativo en tablas con miles de geometrías.
* **Operaciones por lotes** (triggers DEFERRABLE) y **hash geométrico** para no recalcular todo. 
* **Vistas/materializadas** para exponer el grafo o “seguridad por celda” a servicios de rutas.

---

## 2.8 Integración con herramientas (QGIS/PostGIS)

* Digitalización/edición en **QGIS** y carga a PostGIS; la **validez** (`ST_IsValid`) y la detección de “toques por borde” (DE-9IM) garantizan que la reconstrucción del grafo sea robusta. ([PostGIS][5])

---

## 2.9 Compatibilidad y camino a IndoorGML 2.0

* La estructura ya usa **terminología y relaciones** del estándar 1.1.
* Para 2.0 (en evolución) se prevén ajustes en **mapeos y modularidad**; tu diseño deja abierta la exportación a GML/JSON y la incorporación de **capas/semántica extendidas**. ([TU Delft Research Portal][6])

---

## 2.10 Lecciones aprendidas

* **Alinear temprano** con el estándar reduce deuda técnica (nombres, cardinalidades).
* **IDs deterministas** y **hash de geometría** evitan duplicados y estabilizan referencias. 
* Mantener la **planaridad** (no solapes) y el uso explícito de DE-9IM simplifica la generación de límites/grafo. ([PostGIS][2])

---

### Anexo A (referencia rápida a objetos y reglas implementadas)

* **No solapes** de `cell_space` en la misma planta: trigger `fn_cell_space_no_overlap()` con `ST_Relate` y patrón de solape ‘2********’ para detectar intersección de área. 
* **Reconstrucción** de límites y membresías `cellspace_cellboundary` (internos/externos) y limpieza de **huérfanos**. 
* **Nodos**: `node_id_from_cellspace()`, validación `trg_node_inside_when_geom`. 
* **Aristas**: `edge_id_from_cb()`, constraint `ck_edge_id_matches_cb`, y regeneración completa por Dual. 
* **Navegación**: catálogo `nav_space_function`, trigger `ns_coherence_biu`. 

---

## Referencias clave

* **OGC IndoorGML 1.1** (documento oficial y página del estándar). ([OGC Documentos Públicos][1])
* **Revisión y guías de implementación** del modelo celular IndoorGML. ([MDPI][4])
* **DE-9IM / ST_Relate** (predicados topológicos y patrones). ([PostGIS][2])
* **PostGIS**: validez geométrica y **índices** espaciales GiST/SP-GiST. ([PostGIS][5])
* **IndoorGML 2.0 (propuestas y casos)**. ([TU Delft Research Portal][6])

---

### Por qué este orden

1. **Concepto → estándar**: asegura semántica correcta (IndoorGML) antes de pensar en tablas.
2. **Lógico → físico**: el mapeo aclara claves, FKs y tipos geométricos.
3. **Automatización/consistencia**: funciones + triggers mantienen el modelo **vivo** frente a ediciones.
4. **Rendimiento e integración**: índices y vistas para uso operativo (routing/visualización).

Todo el SQL descrito en este capítulo está implementado en tu script maestro (esquemas, tablas, vistas, funciones, triggers e índices), sobre el que se apoyan los servicios de rutas y los filtros por accesibilidad/seguridad. 

[1]: https://docs.ogc.org/is/19-011r4/19-011r4.html?utm_source=chatgpt.com "OGC® IndoorGML 1.1"
[2]: https://postgis.net/docs/ST_Relate.html?utm_source=chatgpt.com "ST_Relate"
[3]: https://postgis.net/docs//manual-3.3/using_postgis_dbmanagement.html?utm_source=chatgpt.com "Chapter 4. Data Management"
[4]: https://www.mdpi.com/2220-9964/6/4/116?utm_source=chatgpt.com "A Standard Indoor Spatial Data Model—OGC IndoorGML ..."
[5]: https://postgis.net/docs/ST_IsValid.html?utm_source=chatgpt.com "ST_IsValid"
[6]: https://research.tudelft.nl/files/83789368/isprs_archives_XLIII_B4_2020_337_2020.pdf?utm_source=chatgpt.com "Towards indoorgml 2.0 Updates and case study illustrations"
--- 
---
---
## 🔗 Links organizados y depurados PARA ELABORACION DE REDACCIÓN CON MISMO NIVEL OPERATIVO

### 1. 📐 Modelado de espacios interiores
- [A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches (MDPI, 2017)](https://www.mdpi.com/2220-9964/6/4/116#:~:text=indoor%20accessibility%20graph%20,edge%20may%20contain%20any%20additional)  
- [A "DOOR-TO-DOOR" Path-Finding Approach for Indoor Navigation (ISPRS, 2011)](https://www.isprs.org/proceedings/2011/gi4dm/pdf/OP05.pdf#:~:text=introduced%20geometrical%20metric,Erickson%2C%201999%3B%20Choi%20%26%20Lee)  
- [Understanding IndoorGML (web oficial OGC)](https://www.indoorgml.net/#:~:text=,position%20for%20more%20precise%20location)  
- [Towards IndoorGML 2.0: Updates and Case Study Illustrations (TU Delft Repository, 2020)](https://repository.tudelft.nl/record/uuid:3f2a31d9-043a-4141-a084-3ba87944cd7a)  
- [OGC IndoorGML 1.1 Document Schemas (XSD, SQL, JSON)](https://docs.ogc.org/is/19-011r4/19-011r4.html#toc14)  

---

### 2. 🗄️ Modelado de bases de datos espaciales
- [Proposal of a spatial database for indoor navigation (Acta Sci. Technol.)](https://periodicos.uem.br/actascitechnol/index.php/ActaSciTechnol/article/view/51718/751375152299)  
- [Proposition of a Schematization Plugin for QGIS (ICA, 2019)](https://ica-abs.copernicus.org/articles/1/23/2019/ica-abs-1-23-2019.pdf)  
- [QGIS (descarga oficial)](https://qgis.org/download/)  
- [dbdiagram.io (herramienta para diagramas de BBDD)](https://dbdiagram.io/home)  

---

### 3. 📊 Conceptos clave de IndoorGML (para tu marco teórico)
- **Understanding IndoorGML (web oficial)**:  
  - Motivations  
  - General Concepts of IndoorGML  
  - Structured Space Model  
  - Multi-Layered Space Model  
  - External References  
  - Anchor Node  
  - Subspacing  
  - Modularization  

- **Proposal of a spatial database for indoor navigation**:  
  - Diseño e implementación de BBDD espaciales para navegación indoor.  

- **Proposition of a Schematization Plugin for QGIS**:  
  - Ejemplo de esquematización (línea central en pasillos).  

---

### 4. 🚀 Estándares emergentes y próximos pasos
- [Towards IndoorGML 2.0 (TU Delft Repository)](https://repository.tudelft.nl/record/uuid:3f2a31d9-043a-4141-a084-3ba87944cd7a)  
  - Cambios propuestos en IndoorGML 2.0.  
  - Ejemplos de implementación en **SQL** y **JSON**.  
  - Comparación con bases de datos relacionales.  

- [OGC IndoorGML 1.1 Document Schemas](https://docs.ogc.org/is/19-011r4/19-011r4.html#toc14)  
  - XSD y scripts de referencia para validación.  
  - Punto de partida para migrar a IndoorGML 2.0.  

---

## ✅ Resumen de organización
- **Sección 1**: papers y estándares sobre **modelado indoor**.  
- **Sección 2**: papers y herramientas sobre **bases de datos espaciales**.  
- **Sección 3**: conceptos teóricos de IndoorGML (útiles para tu marco conceptual).  
- **Sección 4**: estándares emergentes (IndoorGML 2.0) y su relación con BBDD relacionales.  
---
# Guía rápida y anotada de lecturas/recursos (indoor modelling, rutas y BBDD)

A continuación tienes los enlaces **ordenados por tema**, con una frase de **por qué** te sirven y **qué** mirar de cada uno. Todos están contrastados y enlazados a fuentes primarias o publicaciones académicas.

---

## 1) Estándar IndoorGML (qué es y cómo usarlo)

* **IndoorGML 1.1 – especificación oficial OGC (HTML/PDF)**
  La referencia **normativa** del modelo (Core + Navigation): conceptos, clases, conformance y anexos con ejemplos e integración con CityGML/IFC. Imprescindible para nombres/semántica correctos y para justificar decisiones de modelado. ([docs.ogc.org][1])

* **Página oficial del estándar en OGC**
  Resumen, alcance y relación con otros estándares (CityGML, IFC, KML). Útil para introducir IndoorGML en el TFG. ([Open Geospatial Consortium][2])

* **Site oficial de IndoorGML + recursos**
  Descripción del estándar y enlaces a esquemas/XSD y módulos 1.0/1.1 (Core, Navigation, extensiones). Útil cuando necesitas los **schemas** o ejemplos. ([IndoorGML][3])

* **Towards IndoorGML 2.0 (actualizaciones y casos)**
  Qué cambia/proponen para la versión 2.0 y ejemplos de uso; buen material para “trabajos futuros” y comparar tu BBDD con propuestas recientes. ([ISPRS Archives][4])

* **Validación de ficheros IndoorGML**
  Nota técnica (Ledoux) con herramientas/datasets de validación; útil si en algún momento exportas a GML y quieres verificar calidad. ([3D Geoinformation TU Delft][5])

* **POIs en IndoorGML (discussion paper OGC)**
  Extensión para asociar Puntos de Interés (salidas, mobiliario, etc.) al modelo. Interesante si más adelante enriqueces tu grafo. ([docs.ogc.org][6])

---

## 2) Buenas revisiones/papers para “cómo modelar indoors”

* **A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches**
  Revisión clara del modelo celular de IndoorGML (determinación de celdas, *subspacing*, jerarquías) y notas de implementación. Perfecto para el marco teórico. ([MDPI][7])

* **Door-to-door path-finding (indoor)**
  Artículo clásico sobre la estrategia “puerta-a-puerta” (routing a dos niveles: entre estancias y dentro de la estancia). Útil para motivar tu enfoque de grafo/edges. ([gdmc.nl][8])

* **Propuesta de BBDD espacial para navegación indoor (Acta Scientiarum Technology)**
  Aborda requisitos y esquema objeto-relacional para *floor plan* y mapa esquemático. Te da ideas de tablas/relaciones y cómo almacenar niveles. ([ResearchGate][9])

---

## 3) Modelado y esquematización (línea central de pasillos, etc.)

* **Proposition of a Schematization Plugin for QGIS (ICA Abstracts)**
  Plugin/proceso para **esquematizar** (p. ej., trazar **línea central** de un corredor a partir del polígono). Encaja con tu pipeline QGIS→PostGIS. ([ica-abs.copernicus.org][10])

---

## 4) Herramientas prácticas que usas en el TFG

* **QGIS (descarga y documentación)**
  Editor GIS libre para crear/editar geometrías y exportarlas a PostGIS/PostgreSQL. Página de descarga oficial y portal del proyecto. ([QGIS][11])

* **dbdiagram.io**
  Herramienta online sencilla para dibujar diagramas ER con una DSL mínima; rápida para dejar diagramas bonitos en la memoria del TFG. ([dbdiagram.io][12])

---

## 5) Extras útiles para la discusión técnica

* **IndoorGML en publicaciones recientes / integraciones**
  Referencias que citan IndoorGML 1.1 (19-011r4) y su integración con CityGML/IFC; te sirven como apoyo bibliográfico cuando menciones interoperabilidad y estándares. ([itc.scix.net][13])

---

## 6) Cómo conectar estos recursos con tu trabajo

1. **Modelo/DB:** sustenta tu esquema PostGIS con IndoorGML 1.1 (Core + Navigation). Copia la terminología (CellSpace, CellBoundary, Node/Edge en la **Dual Layer**) y cita la especificación. ([docs.ogc.org][14])
2. **Rutas:** apóyate en *door-to-door* para justificar la creación de edges a partir de **puertas/boundaries** y el routing a dos niveles. ([gdmc.nl][8])
3. **QGIS→PostGIS:** usa QGIS para digitalizar espacios y **líneas centrales** de corredores (esquematización) antes de construir el grafo (triggers ya los tienes). ([ica-abs.copernicus.org][10])
4. **Mejoras futuras:** resume brevemente qué aporta IndoorGML 2.0 y qué extensiones/validaciones añadirías si exportaras a GML. ([ISPRS Archives][4])

---

## 7) Lista rápida (para copiar a la bibliografía)

* Kang & Li (2017) **IndoorGML & Implementation Approaches** (IJGI). ([MDPI][7])
* Liu & Zlatanova (2011) **Door-to-door path-finding** (PDF). ([gdmc.nl][8])
* **OGC IndoorGML 1.1** (19-011r4, HTML/PDF). ([docs.ogc.org][1])
* Diakité et al. (2020) **Towards IndoorGML 2.0** (ISPRS). ([TU Delft Research Portal][15])
* Ledoux (2020) **Are your IndoorGML files valid?** (nota técnica + datasets). ([3D Geoinformation TU Delft][5])
* Sarot, Delazari & Camboim (2021) **Proposal of a spatial DB for indoor navigation**. ([ResearchGate][9])
* Barioni & Delazari (2019) **Schematization Plugin for QGIS** (ICA). ([ica-abs.copernicus.org][10])
* **QGIS – descarga/documentación**. ([QGIS][11])
* **dbdiagram.io** (diagramas ER online). ([dbdiagram.io][12])

---

[1]: https://docs.ogc.org/is/19-011r4/19-011r4.html?utm_source=chatgpt.com "OGC® IndoorGML 1.1"
[2]: https://www.ogc.org/standards/indoorgml/?utm_source=chatgpt.com "IndoorGML Standard | OGC Publications"
[3]: https://www.indoorgml.net/?utm_source=chatgpt.com "IndoorGML OGC"
[4]: https://isprs-archives.copernicus.org/articles/XLIII-B4-2020/337/2020/?utm_source=chatgpt.com "TOWARDS INDOORGML 2.0: UPDATES AND CASE ..."
[5]: https://3d.bk.tudelft.nl/hledoux/pdfs/20_3dgeoinfo_indoorgml.pdf?utm_source=chatgpt.com "Are your IndoorGML files valid?"
[6]: https://docs.ogc.org/dp/20-054r1.html?utm_source=chatgpt.com "An Extension Model to attach Points of Interest into IndoorGML"
[7]: https://www.mdpi.com/2220-9964/6/4/116?utm_source=chatgpt.com "A Standard Indoor Spatial Data Model—OGC IndoorGML ..."
[8]: https://www.gdmc.nl/publications/2011/Door-to-door_path-finding_approach.pdf?utm_source=chatgpt.com "A \"DOOR-TO-DOOR\" PATH-FINDING APPROACH ... - GDMC"
[9]: https://www.researchgate.net/publication/353782814_Proposal_of_a_spatial_database_for_indoor_navigation?utm_source=chatgpt.com "Proposal of a spatial database for indoor navigation"
[10]: https://ica-abs.copernicus.org/articles/1/23/2019/?utm_source=chatgpt.com "Proposition of a Schematization Plugin for QGIS"
[11]: https://qgis.org/download/?utm_source=chatgpt.com "Download · QGIS Web Site"
[12]: https://dbdiagram.io/?utm_source=chatgpt.com "dbdiagram.io - Database Relationship Diagrams Design Tool"
[13]: https://itc.scix.net/pdfs/w78-2024-paper_129.pdf?utm_source=chatgpt.com "Multiple schema integration trough a common intermediate ..."
[14]: https://docs.ogc.org/is/19-011r4/19-011r4.pdf?utm_source=chatgpt.com "OGC® IndoorGML 1.1"
[15]: https://research.tudelft.nl/files/83789368/isprs_archives_XLIII_B4_2020_337_2020.pdf?utm_source=chatgpt.com "Towards indoorgml 2.0 Updates and case study illustrations"
---
---

