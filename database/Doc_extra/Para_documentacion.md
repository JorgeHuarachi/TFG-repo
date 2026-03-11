### Información

- **Contenido clave**: Resumen condensado y estructurado.
- **Fuentes principales**: De qué documentos sale.
- **Ideas para confirmar/añadir/eliminar**: Sugerencias basadas en coherencia (ej. eliminar inconsistencias como SRID variable; añadir ejemplos visuales; confirmar adopción parcial de IndoorGML).

#### 1. **Introducción a IndoorGML y su Adopción en el Proyecto**
   - **Contenido clave**:
     - Explicación del estándar: Vocabulario común para modelado de espacios interiores (navegación, grafos duales, multi-capa). Enfocado en navegación indoor (Room-to-Room, Door-to-Door).
     - Beneficios: Interoperabilidad (export a GML, QGIS, FME), rigor académico para TFG, escalabilidad (sensores, accesibilidad).
     - Implicaciones: Adopción parcial ("IndoorGML-lite": Core + Navigation; roadmap para FSS y 2.0). No entero para evitar overhead.
     - Terminología clave: CellSpace (espacios), Node/Edge (grafo dual), ThematicLayer (capas temáticas), InterLayerConnection (enlaces entre capas).
     - Casos de uso: Evacuación, rutas precisas, integración con pgRouting/NetworkX.
   - **Fuentes principales**: Sobre_indoorGML_para_mi.md, Documentacion_de_IndoorGML.md (secciones 1-6).
   - **Ideas para confirmar/añadir/eliminar**:
     - Confirmar: Adopción parcial (Opción A: mínimo viable con CellSpace + Node/Edge).
     - Añadir: Tabla comparativa de IndoorGML 1.1 vs. 2.0 (renombrados, simplificaciones).
     - Eliminar: Repeticiones sobre "curva de aprendizaje" (consolidar en una tabla de pros/contras).

#### 2. **Modelado Conceptual y Estructura de la Base de Datos**
   - **Contenido clave**:
     - Bloques conceptuales de `evac_db`: 1) Edificios/Espacios (AREA como entidad central, CONEXION/CONEXION_CONDICIONAL para puertas/ventanas); 2) Sensores/Lecturas; 3) Seguridad/Eventos; 4) Usuarios/Rutas.
     - Entidades clave: AREA (espacios con superficie, capacidad, salida_segura), PLANTA/EDIFICIO (jerarquía), BALIZA/SENSOR/VARIABLE (IoT).
     - Relaciones: AREA conecta todo; UNIQUE KEY en lecturas para snapshots.
     - Alineación con IndoorGML: AREA → CellSpace; CONEXION → Edge/TransferSpace; semántica para filtros (accesibilidad, emergencias).
     - Atributos espaciales: Centroides (x/y), bounding box, origen en planta; códigos alfanuméricos (ej. CS-0001 para CellSpace).
     - Namespacing: Esquemas `indoorgml_core` y `indoorgml_nav`.
   - **Fuentes principales**: evac_db_documentacion.md, Ayuda_para_crear_la_BBDD.md (mermaid, centroides), Sobre_indoorGML_para_mi.md (mapeo tablas).
   - **Ideas para confirmar/añadir/eliminar**:
     - Confirmar: AREA como central; IDs numéricos + códigos alfanuméricos para dashboard.
     - Añadir: Diagrama ER actualizado (Mermaid o imagen) con alineación IndoorGML.
     - Eliminar: Descripciones vagas de "bloque 3/4" (pendientes); mover a roadmap.

#### 3. **Diseño Lógico/Físico y Implementación en PostGIS**
   - **Contenido clave**:
     - Fases de diseño: 1) Requisitos (diccionario de datos); 2) Conceptual (ER); 3) Lógico (tablas, FK, normalización); 4) Físico (SQL, índices, triggers).
     - Tablas clave: spaces/walls/openings (geometrías Polygon/MultiPolygon, SRID 3857); vertical_edges (escaleras/rampas); LECTURA/HISTORICO_LECTURAS (snapshots + histórico).
     - Reglas topológicas: ST_Touches/CoveredBy para openings en walls; validación con ST_IsValid.
     - Scripts SQL: DDL para tablas (con GENERATED columnas como distancia); inserciones con ON DUPLICATE; vistas materializadas (space_connectivity).
     - Orden de creación: 00_create_db.sql → 01_extensions.sql → ... → 10_sample_data.sql.
     - Optimizaciones: Particiones por datetime/ubicación; índices GiST; triggers para validación.
   - **Fuentes principales**: Para_documentacion.md (fases), Documentacion_de_IndoorGML.md (secciones 2-8, SQL), Ayuda_para_crear_la_BBDD.md (tablas lecturas, orden SQL).
   - **Ideas para confirmar/añadir/eliminar**:
     - Confirmar: SRID 3857 fijo (web-compatible); 2D + atributos z (no 3D full).
     - Añadir: Script completo de migración (de AREA a CellSpace/Node/Edge).
     - Eliminar: Ejemplos SQL incompletos/fragmentados (consolidar en bloques ejecutables).

#### 4. **Sensores, Lecturas y Análisis de Eventos**
   - **Contenido clave**:
     - Tablas: BALIZA (con coordenadas x/y), BALIZA_SENSOR, SENSOR_VARIABLE; LECTURA (últimas lecturas, UNIQUE por sensor/variable/ubicación); HISTORICO_LECTURAS (trazabilidad).
     - Inserciones: Batch a histórico + UPDATE actual con ON DUPLICATE.
     - Consultas clave: Media de últimas 3 lecturas (ROW_NUMBER + AVG); agrupamiento por ubicación; vistas para estado actual.
     - Análisis: CEP para eventos complejos (incrementos, patrones); filtros por tiempo/ubicación.
     - Integración espacial: Coordenadas para balizas en mapa; relación con AREA.
   - **Fuentes principales**: Ayuda_para_crear_la_BBDD.md (lecturas, consultas, UNIQUE KEY), evac_db_documentacion.md (bloque 2).
   - **Ideas para confirmar/añadir/eliminar**:
     - Confirmar: Dos tablas (actual + histórico) para rendimiento.
     - Añadir: Ejemplo de trigger para volcado automático histórico.
     - Eliminar: Consultas "quizás funcionan" (reemplazar por versión final validada).

#### 5. **Grafos, Rutas y Capas Temáticas (Door-to-Door, Room-to-Room)**
   - **Contenido clave**:
     - Grafos: Room-to-Room (nodos=celda, edges=conexiones); Door-to-Door (nodos=puertas, edges=trayectos intra-sala, con ST_ShortestLine para distancias).
     - Capas: ThematicLayer para DTD/RTR; InterLayerConnection para enlazar (ej. puerta pertenece a celda).
     - Implementación: Vistas SQL para door_node/door_edge; pgRouting para dijkstra/astar; weights (tiempo/distancia).
     - Casos especiales: Espacios L/T/U (dividir en rectángulos conectados); movilidad (capas para walking/rolling).
     - Enrutamiento multiplanta: Aristas verticales para escaleras/rampas.
   - **Fuentes principales**: Documentacion_de_IndoorGML.md (sección 5-6), Sobre_indoorGML_para_mi.md (DTD/RTR, capas), Ayuda_para_crear_la_BBDD.md (door-to-door).
   - **Ideas para confirmar/añadir/eliminar**:
     - Confirmar: Dos capas independientes (no mezclar nodos).
     - Añadir: Diagrama Mermaid para capas + ejemplo de export GML.
     - Eliminar: Notas pendientes como "sobre las demás capas de movilidad" (expandir en roadmap).

#### 6. **Documentación General y Pendientes**
   - **Contenido clave**:
     - Estructura ideal: Requisitos → ER → Relacional → SQL; diccionario de datos; glosario.
     - Pendientes: Alinear a IndoorGML, pasar a inglés, incluir imágenes/figuras, video demo.
     - Roadmap: FSS, 3D opcional, extensiones (accesibilidad, POIs).
   - **Fuentes principales**: Para_documentacion.md, evac_db_documentacion.md (pendientes).
   - **Ideas para confirmar/añadir/eliminar**:
     - Confirmar: Video primero (para TFG).
     - Añadir: Tabla de checklist para migración IndoorGML.
     - Eliminar: Wireframes placeholders (reemplazar por reales).

