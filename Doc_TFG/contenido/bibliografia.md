# 📚 Bibliografía Organizada: Recursos para Modelado Indoor, Bases de Datos Espaciales, Rutas y Evacuación

He compilado **todos los recursos del texto proporcionado**, eliminando duplicados excesivos pero asegurándome de no omitir ninguno. Cada fuente única se menciona como máximo en **dos grupos temáticos** (incluso si aparecía más veces en el input), para evitar repeticiones innecesarias mientras se mantiene la cobertura completa. Los grupos están ordenados lógicamente: desde estándares base hasta herramientas prácticas. He usado la información extraída de las fuentes (títulos completos, autores, años, etc.) para mayor precisión.

Cada recurso incluye:
- **Descripción breve**: Por qué sirve en el contexto (basado en resúmenes y anotaciones originales).
- **Qué mirar**: Secciones clave o elementos prácticos (adaptado de descripciones proporcionadas).
- **Enlace**: URL directa.

Al final, una **lista única copiable** para bibliografía (formato: Autor(es)/Entidad (Año) - **Título** - Fuente), ordenada alfabéticamente por autor/entidad.

---

## 1) Estándar IndoorGML (Normativa, Conceptos y Compatibilidad)
Estos recursos forman la base normativa para justificar el uso de IndoorGML en modelado, validación y extensiones (e.g., para TFG capítulo teórico).

* **OGC® IndoorGML 1.1**  
  Especificación oficial OGC con schemas XSD, SQL y JSON para modelado celular, validación y navegación indoor; incluye clases como CellSpace, State/Transition y conformance para integridad espacial.  
  **Qué mirar**: Cap. 7-9 (Navigation Module), anexos A-C (schemas y ejemplos), secciones sobre Multi-Layered Space Models y validación de no-solapes.  
  [Enlace](https://docs.ogc.org/is/19-011r4/19-011r4.html)

* **Towards IndoorGML 2.0: Updates and Case Study Illustrations**  
  Propuestas de actualizaciones para IndoorGML 2.0, como renombrado de clases (PrimalSpaceFeatures a PrimalSpaceLayer), simplificación de geometrías, extensión de conexiones multi-capa, ThematicLayer y POIs; incluye ejemplos SQL/JSON y casos de estudio en extracción BIM/IFC.  
  **Qué mirar**: Secc. 3-4 (updates y simplificaciones), ejemplos conceptuales en SQL/JSON, casos de redes topológicas y subdivisión FSS para evacuación.  
  [Enlace](https://isprs-archives.copernicus.org/articles/XLIII-B4-2020/337/2020/)

* **An Extension Model to attach Points of Interest into IndoorGML**  
  Extensión para POIs (e.g., salidas, mobiliario) en IndoorGML, con modelo conceptual para integrar con core y navigation modules; útil para rutas de evacuación con semántica temporal.  
  **Qué mirar**: Secc. 4 (schema de extensión), ejemplos de integración con Multi-Layered Graphs y use cases como hospital management.  
  [Enlace](https://docs.ogc.org/dp/20-054r1.html)

* **Are your IndoorGML files valid?**  
  Nota técnica sobre validación de ficheros IndoorGML con herramientas como val3dity; incluye tests para schema, geometrías, XLinks y consistencia topológica, con datasets públicos.  
  **Qué mirar**: Secc. 2 (herramientas y tests), datasets y reportes de validación para errores comunes (e.g., E102, E703).  
  [Enlace](https://3d.bk.tudelft.nl/hledoux/pdfs/20_3dgeoinfo_indoorgml.pdf)

* **Understanding IndoorGML**  
  Descripción oficial del estándar IndoorGML con conceptos clave como cellular space, semantic/geometric/topological representations, multi-layer y modularización; incluye NRG para relaciones.  
  **Qué mirar**: Secciones sobre motivaciones, conceptos generales, structured space model, multi-layer, referencias externas y modules overview (Core, Navigation).  
  [Enlace](https://www.indoorgml.net/)

---

## 2) Funciones y Documentación PostGIS (Validación y Gestión Espacial)
Recursos para operaciones topológicas, validación y gestión en bases de datos espaciales como PostGIS (e.g., para integridad y consultas en TFG).

* **ST_Relate**  
  Predicados topológicos en PostGIS para detección de intersecciones y relaciones geométricas usando DE-9IM; soporta patrones personalizados y boundary rules.  
  **Qué mirar**: Ejemplos de matrices DE-9IM, uso con intersects/contains/overlaps y optimización con índices espaciales.  
  [Enlace](https://postgis.net/docs/ST_Relate.html)

* **Chapter 4. Data Management**  
  Guía de gestión de bases de datos espaciales en PostGIS, incluyendo tipos geometry/geography, carga/exportación y índices GiST/SP-GiST/BRIN para queries eficientes.  
  **Qué mirar**: Secciones sobre creación de tablas espaciales, metadata views (geometry_columns) y creación de índices GiST para bounding boxes.  
  [Enlace](https://postgis.net/docs/manual-3.3/using_postgis_dbmanagement.html)

* **ST_IsValid**  
  Validación de geometrías en PostGIS para asegurar integridad espacial según OGC rules; detecta invalididades en 2D (incluso para 3D/4D).  
  **Qué mirar**: Ejemplos de uso con flags, integración con GEOS module y manejo de NULL inputs.  
  [Enlace](https://postgis.net/docs/ST_IsValid.html)

---

## 3) Modelado de Espacios Interiores y Bases de Datos (Conceptual a Físico)
Para diseño de esquemas SQL, modelado celular/jerárquico y implementación relacional (e.g., para capítulos de diseño en TFG).

* **A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches**  
  Revisión de implementación del modelo celular en bases de datos, con enfoques relacionales, subspacing y jerarquías; discute cell determination y external references.  
  **Qué mirar**: Fig. 2-3 (UML celular), secc. 4 (implementación relacional y distancias indoor).  
  [Enlace](https://www.mdpi.com/2220-9964/6/4/116)

* **Proposal of a spatial database for indoor navigation**  
  Propuesta de esquema objeto-relacional para floor plans y navegación indoor; incluye entidades, relaciones N:M y adaptabilidad a multi-planta con PgRouting.  
  **Qué mirar**: Secc. 3 (esquema DDL), Fig. 4 (relaciones) y tests en PostgreSQL/PostGIS.  
  [Enlace](https://www.researchgate.net/publication/353782814_Proposal_of_a_spatial_database_for_indoor_navigation)

* **Multiple schema integration through a common intermediate**  
  Integración de esquemas IndoorGML con bases relacionales como CityGML/IFC; usa modelo intermedio para conversión y extracción de floorplans.  
  **Qué mirar**: Secc. 3 (integración schemas), workflow para semantic differences y tests con samples.  
  [Enlace](https://itc.scix.net/pdfs/w78-2024-paper_129.pdf)

* **Indoor Navigation based on IndoorGML: Case Study Rural and Surveying Engineering School, NTUA**  
  Modelado conceptual y topológico de IndoorGML con representaciones geométricas/semánticas/multi-capa; incluye NRG y Poincaré Duality para conectividad.  
  **Qué mirar**: Secciones sobre NRS, multi-layered space y case study en NTUA con JInedit editor.  
  [Enlace](https://dspace.lib.ntua.gr/xmlui/bitstream/handle/123456789/45923/IndoorGML_Tsaggouri.pdf?sequence=1)

* **A Dynamic Indoor Field Model for Emergency Evacuation Simulation**  
  Modelo conceptual/lógico DIFM basado en IndoorGML y CityGML LoD4; entidades como IndoorSpace/GridUnit para modelado dinámico con sensores y congestión.  
  **Qué mirar**: Secciones sobre static/dynamic info, 3D space grid y validación en simulaciones multi-story.  
  [Enlace](https://www.mdpi.com/2220-9964/6/4/104)

* **Developing a database for the LADM-IndoorGML model**  
  Implementación física en PostgreSQL/PostGIS del modelo LADM-IndoorGML; transformación UML a SQL DDL, tablas para espacios interiores y geometrías 2D/3D.  
  **Qué mirar**: Proceso de class diagrams a DDL, visualización de indoor spaces basados en RRRs.  
  [Enlace](https://repository.tudelft.nl/record/uuid:31a20fb8-dabc-4f19-82c8-432f410a3ece)

* **OGC® IndoorGML 1.1**  
  Especificación para modelado y validación en bases de datos; soporta external references a CityGML/IFC y opciones geométricas (internal/no geometry).  
  **Qué mirar**: Conformance requirements, test suites para validación y Multi-Layered Graphs.  
  [Enlace](https://docs.ogc.org/is/19-011r4/19-011r4.html)

* **Are your IndoorGML files valid?**  
  Validación en entornos de bases de datos con tests para geometrías, overlaps y adjacencies; datasets para ficheros IndoorGML.  
  **Qué mirar**: Secc. sobre val3dity tests (e.g., E405, E703) y github datasets.  
  [Enlace](https://3d.bk.tudelft.nl/hledoux/pdfs/20_3dgeoinfo_indoorgml.pdf)

---

## 4) Rutas de Evacuación y Algoritmos de Navegación Indoor
Para grafos duales, routing puerta-a-puerta y algoritmos en evacuaciones dinámicas (e.g., para capítulos de algoritmos en TFG).

* **A "DOOR-TO-DOOR" Path-Finding Approach for Indoor Navigation**  
  Estrategia de routing puerta-a-puerta con grafo dual; two-level (coarse/fine) para rooms y intra-room, adaptable a cambios dinámicos.  
  **Qué mirar**: Secc. 3 (algoritmo), Fig. 5 (grafo ejemplo) y extensión a 3D/obstáculos.  
  [Enlace](https://www.isprs.org/proceedings/2011/gi4dm/pdf/OP05.pdf)

* **Towards IndoorGML 2.0: Updates and Case Study Illustrations**  
  Propuestas para extensiones en grafos de navegación y evacuación; simplificación del módulo de navegación y soporte para rutas semánticas multi-capa.  
  **Qué mirar**: Use cases en routing, integración FSS y triggers para validación en PostGIS.  
  [Enlace](https://isprs-archives.copernicus.org/articles/XLIII-B4-2020/337/2020/)

* **An Extension Model to attach Points of Interest into IndoorGML**  
  Extensión para POIs relevantes en rutas de evacuación (e.g., salidas); integra con navigation module para LBS y route planning.  
  **Qué mirar**: Use cases como home navigation y hospital, atributos para navigable elements.  
  [Enlace](https://docs.ogc.org/dp/20-054r1.html)

* **Proposal of a spatial database for indoor navigation**  
  Enfoque en esquemas para soporte de rutas y navegación; incluye route calculation con shortest distances y floor changes.  
  **Qué mirar**: User evaluations, inclusión de physical characteristics y outdoor references.  
  [Enlace](https://www.researchgate.net/publication/353782814_Proposal_of_a_spatial_database_for_indoor_navigation)

* **Indoor Navigation based on IndoorGML: Case Study Rural and Surveying Engineering School, NTUA**  
  Algoritmos como Dijkstra y A* aplicados a grafos topológicos de IndoorGML para path-finding en evacuaciones dinámicas.  
  **Qué mirar**: Secciones sobre Dijkstra/A*, door-to-door approach y emergency scenarios en NTUA.  
  [Enlace](https://dspace.lib.ntua.gr/xmlui/bitstream/handle/123456789/45923/IndoorGML_Tsaggouri.pdf?sequence=1)

* **A Dynamic Indoor Field Model for Emergency Evacuation Simulation**  
  Algoritmo de recomendación de rutas basado en A* con pesos dinámicos, índice de seguridad y detección de congestión; integra sensores y behavioral data.  
  **Qué mirar**: Simulaciones en railway station, atributos para accessibility/security en Grid Units.  
  [Enlace](https://www.mdpi.com/2220-9964/6/4/104)

---

## 5) Herramientas Prácticas (Edición, Esquematización y Diagramas)
Para flujos de trabajo en edición geométrica y visualización de esquemas (e.g., anexos de TFG).

* **Proposition of a Schematization Plugin for QGIS**  
  Plugin para esquematización de geometrías en QGIS, integrable con PostGIS para modelado de pasillos y límites; automatiza centroids y skeleton lines.  
  **Qué mirar**: Secc. 2 (algoritmo), Fig. 1 (ejemplo visual) y verificación topológica.  
  [Enlace](https://ica-abs.copernicus.org/articles/1/23/2019/ica-abs-1-23-2019.pdf)

* **QGIS (descarga oficial y documentación)**  
  Herramienta libre para edición y exportación de geometrías a PostGIS/PostgreSQL; soporta plugins para IndoorGML y schematization.  
  **Qué mirar**: Sección "Processing Toolbox" para esquematización y loaders como shp2pgsql.  
  [Enlace](https://qgis.org/download/)

* **dbdiagram.io**  
  Herramienta online para diagramas ER de bases relacionales y espaciales; usa DSL para visuales rápidos.  
  **Qué mirar**: Importación de Mermaid para export PNG/SVG y ejemplos de ER bonitos.  
  [Enlace](https://dbdiagram.io/home)

---

## 6) Cómo Conectar Recursos con Tu Trabajo (Resumen Práctico)
- **Estándar/DB**: OGC 1.1 + Kang (2017) para mapeo CellSpace/Node/Edge y SQL.
- **Modelado**: Alattas (2018) + Xiong (2017) para UML a DDL y modelado dinámico.
- **Rutas**: Liu (2011) + Tsangouri (2017) para grafos duales y A*/Dijkstra.
- **Validación**: Ledoux (2020) + ST_IsValid para checks topológicos.
- **Herramientas**: Barioni (2019) + QGIS para preprocesado antes de triggers.
- **Futuro**: Diakité (2020) para extensiones POIs y 2.0.

**Mapa Rápido (Tabla)**:

| Necesidad en TFG                     | Recursos Principales                                                                 |
|--------------------------------------|--------------------------------------------------------------------------------------|
| **Norma/Terminología**               | OGC 1.1, Understanding IndoorGML, Towards 2.0, POI Extension                         |
| **Funciones PostGIS**                | ST_Relate, Chapter 4 Data Management, ST_IsValid                                     |
| **Diseño SQL/Modelo Celular**        | Kang (2017), Sarot (2021), Alattas (2018), Xiong (2017)                              |
| **Rutas y Algoritmos**               | Liu (2011), Tsangouri (2017), Diakité (2020)                                         |
| **Validación/Integración**           | Ledoux (2020), Tauscher (2024)                                                       |
| **Herramientas**                     | Barioni (2019), QGIS, dbdiagram.io                                                   |

---

## 7) Lista Única para Bibliografía (Copiable, Formato Simple)
Formato: Autor(es)/Entidad (Año) - **Título** - Fuente. Orden alfabéticamente por autor/entidad. Total: 18 únicos (incluyendo variaciones de links para mismos papers, pero tratados como uno).

- Alattas, A.F.M.; Oosterom, P.; Zlatanova, S.; Diakite, A.A.; Yan, J. (2018) - **Developing a database for the LADM-IndoorGML model** - TU Delft Repository. [Enlace](https://repository.tudelft.nl/record/uuid:31a20fb8-dabc-4f19-82c8-432f410a3ece)
- Barioni, I.; Delazari, L.S. (2019) - **Proposition of a Schematization Plugin for QGIS** - Abstracts of the International Cartographic Association. [Enlace](https://ica-abs.copernicus.org/articles/1/23/2019/ica-abs-1-23-2019.pdf)
- dbdiagram.io (s.f.) - **Database Relationship Diagrams Design Tool** - dbdiagram.io. [Enlace](https://dbdiagram.io/home)
- Diakité, A.A.; Zlatanova, S.; Alattas, A.F.M.; Li, K.J. (2020) - **Towards IndoorGML 2.0: Updates and Case Study Illustrations** - The International Archives of the Photogrammetry, Remote Sensing and Spatial Information Sciences. [Enlace](https://isprs-archives.copernicus.org/articles/XLIII-B4-2020/337/2020/)
- Kang, H.K.; Li, K.J. (2017) - **A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches** - ISPRS International Journal of Geo-Information. [Enlace](https://www.mdpi.com/2220-9964/6/4/116)
- Kim, K.S.; Lee, J. (2021) - **An Extension Model to attach Points of Interest into IndoorGML** - Open Geospatial Consortium. [Enlace](https://docs.ogc.org/dp/20-054r1.html)
- Ledoux, H. (2020) - **Are your IndoorGML files valid?** - ISPRS Annals of the Photogrammetry, Remote Sensing and Spatial Information Sciences. [Enlace](https://3d.bk.tudelft.nl/hledoux/pdfs/20_3dgeoinfo_indoorgml.pdf)
- Lee, J.; Li, K.J.; Zlatanova, S.; Kolbe, T.H.; Nagel, C.; Becker, T.; Kang, H.Y. (2019) - **OGC® IndoorGML 1.1** - Open Geospatial Consortium. [Enlace](https://docs.ogc.org/is/19-011r4/19-011r4.html)
- Liu, L.; Zlatanova, S. (2011) - **A "DOOR-TO-DOOR" Path-Finding Approach for Indoor Navigation** - ISPRS Proceedings. [Enlace](https://www.isprs.org/proceedings/2011/gi4dm/pdf/OP05.pdf)
- OGC (2020) - **IndoorGML OGC** - indoorgml.net. [Enlace](https://www.indoorgml.net/)
- PostGIS (2012) - **ST_IsValid** - PostGIS Documentation. [Enlace](https://postgis.net/docs/ST_IsValid.html)
- PostGIS (2011) - **ST_Relate** - PostGIS Documentation. [Enlace](https://postgis.net/docs/ST_Relate.html)
- PostGIS (2023) - **Chapter 4. Data Management** - PostGIS Manual 3.3. [Enlace](https://postgis.net/docs/manual-3.3/using_postgis_dbmanagement.html)
- QGIS (s.f.) - **QGIS: Download and Documentation** - qgis.org. [Enlace](https://qgis.org/download/)
- Sarot, R.V.; Delazari, L.S.; Camboim, S.P. (2021) - **Proposal of a spatial database for indoor navigation** - Acta Scientiarum. Technology. [Enlace](https://www.researchgate.net/publication/353782814_Proposal_of_a_spatial_database_for_indoor_navigation)
- Tauscher, H. (2024) - **Multiple schema integration through a common intermediate model: a floorplan extraction case study** - CIB W78 Conference. [Enlace](https://itc.scix.net/pdfs/w78-2024-paper_129.pdf)
- Tsangouri, A. (2017) - **Indoor Navigation based on IndoorGML: Case Study Rural and Surveying Engineering School, NTUA** - National Technical University of Athens. [Enlace](https://dspace.lib.ntua.gr/xmlui/bitstream/handle/123456789/45923/IndoorGML_Tsaggouri.pdf?sequence=1)
- Xiong, Q.; Zhu, Q.; Du, Z.; Zhu, X.; Niu, L.; Li, Y.; Zhou, Y. (2017) - **A Dynamic Indoor Field Model for Emergency Evacuation Simulation** - ISPRS International Journal of Geo-Information. [Enlace](https://www.mdpi.com/2220-9964/6/4/104)