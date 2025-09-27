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
¡Perfecto! Aquí tienes una **lista única, sin duplicados**, ordenada por **para qué te sirve** en tu TFG. Cada enlace lleva una nota rápida para que sepas **cuándo usarlo** (modelado de BBDD, rutas de evacuación, CEP/sensórica, estándar IndoorGML, herramientas). Así puedes **pasarla a otro ChatGPT** para que se apoye en estas fuentes antes de buscar fuera.

---

# 📚 Enlaces clasificados por propósito

## A) Estándar IndoorGML (normativa, conceptos y compatibilidad)

* **OGC IndoorGML 1.1 – especificación oficial (HTML/XSD/SQL/JSON)**
  Referencia *normativa* del modelo (Core + Navigation), definiciones de *CellSpace/State/Transition*, esquemas y materiales para validación/implementación. Úsalo para justificar tu mapeo SQL y terminología. ([OGC Documentos Públicos][1])
* **Site oficial de IndoorGML (descripción y recursos)**
  Resumen del estándar y su encaje con GML; útil para la introducción y para enlazar recursos oficiales. ([indoorgml.net][2])
* **Towards IndoorGML 2.0 (ISPRS Archives, 2020)**
  Cambios propuestos hacia 2.0 y casos de estudio; perfecto para el apartado de compatibilidad/“trabajo futuro” y posibles extensiones SQL/JSON. ([ISPRS Archives][3])

**Cuándo usarlos**: marco teórico (2.1–2.3), compatibilidad (2.9), términos y clases exactas para tu modelo.

---

## B) Modelado de espacios interiores y bases de datos (de conceptual a físico)

* **A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches (MDPI, 2017)**
  Revisión clara del **modelo celular** (determinación de celdas, subespacios, jerarquías) y notas de implementación; excelente para motivar decisiones de diseño en tu SQL. ([mdpi.com][4])
* **Proposal of a spatial database for indoor navigation**
  Requisitos y **esquema objeto-relacional** para *floor plan* y *schematic map*; ideas prácticas para tablas/relaciones y manejo multi-planta. (Alternativa de acceso: Academia si ResearchGate no carga). ([ResearchGate][5])
* **Proposition of a Schematization Plugin for QGIS (ICA Abstracts, 2019)**
  Esquematización (p. ej., **línea central** de corredores) que encaja con tu pipeline QGIS→PostGIS antes de generar el grafo. ([ICA-Abs][6])

**Cuándo usarlos**: justificar mapeo IndoorGML→SQL (2.3–2.4), decisiones geométricas (2.6) y preprocesado (líneas centrales).

---

## C) Rutas de evacuación / algoritmos de navegación indoor

* **“Door-to-door” path-finding (ISPRS, 2011, PDF)**
  Enfoque de **routing a dos niveles** (entre estancias y dentro de la estancia) apoyado en **puertas/boundaries**; base conceptual para tu generación de edges a partir de límites y estrategia de rutas. (Copias en GDMC/Scispace). ([gdmc.nl][7])

**Cuándo usarlo**: 4.4 (métricas, Dijkstra/A*), 2.6 (de polígonos a grafo), y para justificar “door-to-door”.

---

## D) Herramientas prácticas que usas (edición/datos)

* **QGIS – descarga y documentación**
  Digitalización y edición de geometrías con exportación a PostGIS; respalda tu flujo de trabajo. ([qgis.org][8])

**Cuándo usarlo**: 2.8 (QGIS/PostGIS) y anexo de herramientas.

---

## E) CEP (Complex Event Processing) para datos reales/simulados (IoT/edificios)

> Estos no estaban en tu lista inicial, pero te sirven **directamente** para definir reglas simples, ventanas temporales y formato de eventos simulados (lo que pedías).

* **CEP en seguridad física/ciber e IoT (Journal of Cloud Computing, 2022)**
  Revisión con integración CEP+IoT/ML; buen material para justificar reglas de alerta en edificios y sensores ambientales. ([SpringerOpen][9])
* **Real-time bushfire alerting con CEP en Apache Flink (AWS blog, 2018)**
  Ejemplo operativo de **patrones CEP** sobre **eventos de temperatura** y telemetría IoT (ventanas/event-time, retrasos); útil para **formato** de eventos y **simulación** compatible con ingestas reales. ([Amazon Web Services, Inc.][10])
* **Probabilistic Complex Event Recognition: A Survey (ACM Computing Surveys)**
  Base teórica si quieres mencionar **incertidumbre** (eventos ruidosos/atrasados) en tu simulador. ([ACM Digital Library][11])
* **Smart Buildings con CEP (arXiv, 2023)**
  Arquitectura con Kafka/Flink/Siddhi para **operaciones de edificio en tiempo real**; ideas de reglas y *topics* para simular streams. ([arXiv][12])

**Cuándo usarlos**: capítulo de **Ingesta/CEP** (4.3) y el apéndice de **datos simulados** (definir *JSON events*, ventanas, y umbrales de peligro).

---

# 🧭 Mapa “qué usar para qué” (resumen rápido)

| Necesidad                                  | Mejor(es) enlaces                                                                                                                  |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Norma/terminología IndoorGML**           | OGC IndoorGML 1.1; Site IndoorGML; Towards 2.0. ([OGC Documentos Públicos][1])                                                     |
| **Justificar diseño SQL + modelo celular** | MDPI (Kang & Li 2017); Proposal of a spatial DB. ([mdpi.com][4])                                                                   |
| **Preprocesar geometrías (línea central)** | QGIS + Schematization Plugin (ICA). ([qgis.org][8])                                                                                |
| **Rutas “door-to-door”/evacuación**        | Paper ISPRS “Door-to-door”. ([gdmc.nl][7])                                                                                         |
| **Simular eventos y reglas CEP**           | AWS Flink CEP (práctico), Survey ACM (teórico), Smart Buildings (arXiv), Cloud Computing review. ([Amazon Web Services, Inc.][10]) |
| **Compatibilidad futura**                  | Towards IndoorGML 2.0 (ISPRS). ([ISPRS Archives][3])                                                                               |

---

## 🧩 Consejos para integrarlo en tu redacción

* En el **cap. 2 (modelo de datos)** cita **OGC IndoorGML** (norma) + **MDPI 2017** (visión e implementación) para anclar decisiones de tablas, claves y geometrías. ([OGC Documentos Públicos][1])
* En **2.6 (pipeline geométrico)** apóyate en **door-to-door** para defender la generación de aristas a partir de **boundaries**. ([gdmc.nl][7])
* En **4.3 (CEP)** usa **AWS Flink CEP** para proponer un **formato de evento JSON** y **ventanas temporales** en la simulación, y si quieres plus teórico menciona **ACM survey**. ([Amazon Web Services, Inc.][10])
* En **Roadmap** y compatibilidad, referencia **IndoorGML 2.0**. ([ISPRS Archives][3])

---

### Enlaces (lista limpia, copiable)

1. **Estándar IndoorGML**

* OGC IndoorGML 1.1 (HTML/XSD/SQL/JSON): ([OGC Documentos Públicos][1])
* IndoorGML (página oficial): ([indoorgml.net][2])
* Towards IndoorGML 2.0 (ISPRS): ([ISPRS Archives][3])

2. **Modelado & BBDD**

* MDPI 2017 – IndoorGML & Implementation Approaches: ([mdpi.com][4])
* Proposal of a Spatial DB for Indoor Navigation: ([ResearchGate][5])
* Schematization Plugin for QGIS (ICA): ([ICA-Abs][6])

3. **Rutas/Evacuación**

* Door-to-door path-finding (ISPRS/GDMC, PDF): ([gdmc.nl][7])

4. **Herramientas**

* QGIS (descarga/documentación): ([qgis.org][8])

5. **CEP (para simulación/ingesta IoT)**

* CEP para seguridad física/ciber e IoT (Journal of Cloud Computing, 2022): ([SpringerOpen][9])
* Flink CEP para detección en tiempo real (AWS blog): ([Amazon Web Services, Inc.][10])
* Probabilistic Complex Event Recognition (ACM Computing Surveys): ([ACM Digital Library][11])
* Smart Building operations con CEP (arXiv 2023): ([arXiv][12])

---

[1]: https://docs.ogc.org/is/19-011r4/19-011r4.html?utm_source=chatgpt.com "OGC® IndoorGML 1.1"
[2]: https://www.indoorgml.net/?utm_source=chatgpt.com "IndoorGML OGC"
[3]: https://isprs-archives.copernicus.org/articles/XLIII-B4-2020/337/2020/?utm_source=chatgpt.com "TOWARDS INDOORGML 2.0: UPDATES AND CASE ..."
[4]: https://www.mdpi.com/2220-9964/6/4/116?utm_source=chatgpt.com "A Standard Indoor Spatial Data Model—OGC IndoorGML ..."
[5]: https://www.researchgate.net/publication/353782814_Proposal_of_a_spatial_database_for_indoor_navigation?utm_source=chatgpt.com "Proposal of a spatial database for indoor navigation"
[6]: https://ica-abs.copernicus.org/articles/1/23/2019/?utm_source=chatgpt.com "Proposition of a Schematization Plugin for QGIS"
[7]: https://www.gdmc.nl/publications/2011/Door-to-door_path-finding_approach.pdf?utm_source=chatgpt.com "A \"DOOR-TO-DOOR\" PATH-FINDING APPROACH ... - GDMC"
[8]: https://qgis.org/download/?utm_source=chatgpt.com "Download · QGIS Web Site"
[9]: https://journalofcloudcomputing.springeropen.com/articles/10.1186/s13677-022-00338-x?utm_source=chatgpt.com "Complex event processing for physical and cyber security in ..."
[10]: https://aws.amazon.com/blogs/big-data/real-time-bushfire-alerting-with-complex-event-processing-in-apache-flink-on-amazon-emr-and-iot-sensor-network/?utm_source=chatgpt.com "Real-time bushfire alerting with Complex Event Processing ..."
[11]: https://dl.acm.org/doi/10.1145/3117809?utm_source=chatgpt.com "Probabilistic Complex Event Recognition: A Survey"
[12]: https://arxiv.org/pdf/2309.10822?utm_source=chatgpt.com "A Real-Time Approach for Smart Building Operations ..."
