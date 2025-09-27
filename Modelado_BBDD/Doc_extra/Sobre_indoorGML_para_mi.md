### Resumen 

Como continuación directa, recuerdo que este texto es el núcleo de "Sobre_indoorGML_para_mi.md", que hemos usado para alinear tu TFG con IndoorGML-lite (Core + Navigation). Conecta con discusiones previas: Adopción parcial para valor académico sin overhead; mapeo de AREA → CellSpace, CONEXION → Edge; grafos RTR/DTD como capas temáticas; SQL para dualidad (node/edge); y roadmap para FSS/multi-layer (incluyendo accesibilidad/movilidad). También, integración con PostGIS (SRID 3857, 2D), pgRouting para rutas, y sensores para dinámicas (ej. bloquear edges por alertas). Todo enfocado en navegación indoor/evacuación, con énfasis en interoperabilidad (export GML) y dashboard (códigos alfanuméricos).

### Confirmar, Añadir o Eliminar Ideas

Basado en el texto y contexto previo, refinemos:

| Idea del Texto | Confirmar/Añadir/Eliminar | Razón/Desarrollo Breve |
|---------------|---------------------------|-------------------------|
| **Usos de IndoorGML (dominios)** | **Confirmar**: Navegación indoor prioritario para tu TFG (rutas multi-planta, accesibilidad). | Añadir: Enlace a emergencias con sensores (IoT para evacuación dinámica). Eliminar: Nada, pero expandir tabla con cita oficial. |
| **Implicaciones (interoperabilidad, semántica)** | **Confirmar**: Parcial (2.0) para plus académico; ETL mínimo. | Añadir: Ejemplo de export: `ogr2ogr -f GML output.gml PG:"host=localhost dbname=evac_db" -sql "SELECT * FROM v_cellspace_node_edge"`. |
| **Conveniencia y opciones** | **Confirmar**: Opción A (lite con roadmap). | Eliminar: Riesgos genéricos (ya cubiertos en inconvenientes). Añadir: Timeline: Lite ahora, FSS en TFG futuro. |
| **Preguntas, aportes, inconvenientes** | **Confirmar**: Valor alto para TFG (rigor, escalabilidad). | Añadir: Esfuerzo: ~1 semana para views de export. Eliminar: Duplicados de "curva de aprendizaje" (consolidar). |
| **Ayuda cambios (SQL cellspace/node/edge)** | **Confirmar**: Dualidad esencial; UNIQUE para multi-nodos. | Añadir: Incluir code alfanumérico: `code VARCHAR GENERATED ALWAYS AS ('CS-' || LPAD(cell_id::text, 4, '0'))`. |
| **Ventajas y checklist** | **Confirmar**: pgRouting ready; demo rutas. | Añadir: Checklist como tabla Markdown ejecutable. Eliminar: "(Opc.)" en demo (hazla obligatoria para TFG). |
| **Door-to-Door sección** | **Confirmar**: Capa derivada sobre topographic; SQL PostGIS sólido. | Añadir: Integración con RTR: `JOIN edge ON edge.node_to = door_node.door_id`. Eliminar: Tip densificar (usa ST_ShortestLine para simplicidad inicial). |
| **Terminología DTD/RTR** | **Confirmar**: Capas independientes con InterLayerConnection. | Añadir: Ejemplo SQL para ilc_cell_door. Eliminar: Citas repetidas [1]/[2] (consolidar). |
| **Puntos clave** | **Confirmar**: Independencia capas; añade más (sensores). | Añadir: 5. Soporte IoT: Atributos dinámicos en Edge para bloques (ej. por lecturas). |
| **Sobre las demás capas de movilidad** | **Añadir**: Expandir con info real (de búsqueda: extensiones para PMR/wheelchair via multi-layer). | Eliminar: "se quedo asi" (completar). Confirmar: Sí, hay más (accesibilidad como thematic layer). |

En resumen: **Confirmo 85%** (alineado con lite). **Añado 10%** (ejemplos prácticos, expansión movilidad). **Elimino 5%** (redundancias/citas). Búsqueda confirma extensiones para movilidad (PMR).

### Ideas Ordenadas y Desarrolladas

Ordeno en flujo lógico: Intro/Usos → Análisis Adopción → Cambios Prácticos (SQL) → Door-to-Door/RTR Detallado → Capas de Movilidad (expandida). Cada sección con desarrollo, tablas/SQL, tips para TFG.

#### 1. Introducción y Usos de IndoorGML
**Desarrollo**: IndoorGML es el estándar OGC para modelado de espacios interiores como vocabulario común, enfocado en navegación (tu prioridad). Soporta grafos duales (primal: geometría; dual: conectividad) y multi-layer para jerarquías/complejidad. Para TFG: Alinea tu BD evac_db con él para interoperabilidad y rigor.

**Tabla Expandida (Usos, con Foco en Navegación)**:

| Dominio                             | Cómo se Usa IndoorGML                                                                                      | Relevancia para Tu TFG (Navegación Indoor) |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Navegación indoor**               | Cálculo de rutas multi-planta, señalización accesible (PMR, sillas de ruedas), “blue-dot” en apps móviles. | Core: Rutas RTR/DTD con pgRouting; integra sensores para dinámicas (bloqueos por humo). |
| **Gestión de instalaciones (FM)**   | Inventario espacial normalizado; vinculación con sensores IoT para mantenimiento predictivo.               | Secundario: Vincula balizas a CellSpace para monitoreo real-time. |
| **Robótica y drones**               | Grafo de navegación semántico que se inyecta en ROS; facilita planificación y SLAM semántico.              | Futuro: Roadmap para AGV en evacuación. |
| **Emergencias / seguridad pública** | Pre-planos para primeros respondedores (Pilot NIST-OGC).                                                   | Directo: Filtros en Edge por criticidad (salida_segura en AREA). |
| **AR/VR y digital twins**           | Sincroniza maqueta 3D, topología y base de activos en formato intercambiable.                               | Dashboard: Export GML para visualización web (Leaflet con 3857). |

**Tip para TFG**: Cita oficial en intro: "Goal: Exchange geoinfo for indoor navigation systems". Añade diagrama: Primal (polígonos) vs. Dual (grafo).

#### 2. Análisis de Adopción: Implicaciones, Conveniencia, Preguntas, Aportes e Inconvenientes
**Desarrollo**: Adopción parcial (lite: CellSpace + Node/Edge) minimiza curva (lee spec 1.1 primero, ~80p), gana interoperabilidad (ETL via views) y valor TFG (rigor OGC). No full para evitar renombrados 2.0 (State→Node). Conveniente para proyecto corto: Opción A con roadmap (FSS para subdivisión, multi-layer para sensores).

**Tabla Consolidada (Implicaciones + Preguntas + Aportes)**:

| Aspecto/Pregunta                    | Sin Estándar                                      | Con IndoorGML-Lite (Opción A)                                                                 | Aporte TFG |
|-------------------------------------|--------------------------------------------------|-----------------------------------------------------------------------------------------------|------------|
| **Interoperabilidad**               | ETL ad-hoc por app.                              | Export/import con FME/QGIS; script GML ready.                                                 | Demo export en conclusiones. |
| **Cobertura Semántica**             | Limitado a diseño propio.                        | Clases para topología/accesibilidad/POIs; extiende con thematic layers.                       | Justifica filtros (PMR). |
| **¿Añade Valor Académico?**         | Solución "casera" OK.                            | Sí: Rigor OGC, comparabilidad; plus en jurado.                                                | Sección dedicada en memoria. |
| **¿Esfuerzo Extra?**                | Baja curva.                                      | ~80% mapeo con views; 1 semana para ETL.                                                      | Incluye en metodología. |
| **¿Todo o Parcial?**                | N/A.                                             | Solo Core; "compatible FSS" en roadmap.                                                       | Evita overhead. |
| **Ganancia Largo Plazo**            | Reescribe BD por cliente.                        | Intercambio BIM/IFC; escalable a sensores/mobiliario.                                         | Líneas futuras: IoT+AR. |

**Inconvenientes Desarrollados**:
- **Curva**: Lee [spec oficial] (cap. 7-9 para navigation).
- **ETL Overhead**: Usa ogr2ogr para GML; semanas si cero, pero tú ya tienes geom.
- **Evolución 2.0**: Implementa names 2.0 (Node/Edge) para futuro-proof.

**Tip para TFG**: En "Estado del Arte": "Adopción parcial IndoorGML 2.0 para navegación, con roadmap FSS".

#### 3. Cambios Prácticos: Ayuda para Implementación (SQL y Ventajas)
**Desarrollo**: Migra de AREAS a CellSpace/Node/Edge para dualidad. Añade code alfanumérico para dashboard. UNIQUE en Node para multi-puertas por celda. Preparado para pgRouting (cost en Edge).

**SQL Desarrollado (Expandido con Code y Esquemas)**:
```sql
-- En indoorgml_core (primal)
CREATE SCHEMA IF NOT EXISTS indoorgml_core;
CREATE TABLE indoorgml_core.cellspace (
  cell_id SERIAL PRIMARY KEY,
  code VARCHAR(10) GENERATED ALWAYS AS ('CS-' || LPAD(cell_id::text, 4, '0')) STORED UNIQUE,
  name TEXT,
  usage TEXT,  -- 'aula', 'pasillo'
  floor INTEGER,
  geom GEOMETRY(Polygon, 3857),
  salida_segura BOOLEAN DEFAULT false  -- De tu AREA
);
CREATE INDEX idx_cellspace_geom ON indoorgml_core.cellspace USING GIST (geom);

-- En indoorgml_nav (dual)
CREATE SCHEMA IF NOT EXISTS indoorgml_nav;
CREATE TABLE indoorgml_nav.node (
  node_id SERIAL PRIMARY KEY,
  code VARCHAR(10) GENERATED ALWAYS AS ('ND-' || LPAD(node_id::text, 4, '0')) STORED UNIQUE,
  cell_id INTEGER NOT NULL REFERENCES indoorgml_core.cellspace(cell_id),
  point_geom GEOMETRY(Point, 3857),  -- ST_Centroid(geom)
  CONSTRAINT uk_node_cell UNIQUE (cell_id, node_id)  -- Multi-nodos por celda
);

CREATE TABLE indoorgml_nav.edge (
  edge_id SERIAL PRIMARY KEY,
  code VARCHAR(10) GENERATED ALWAYS AS ('ED-' || LPAD(edge_id::text, 4, '0')) STORED UNIQUE,
  node_from INTEGER NOT NULL REFERENCES indoorgml_nav.node(node_id),
  node_to INTEGER NOT NULL REFERENCES indoorgml_nav.node(node_id),
  cost FLOAT,  -- Tiempo/distancia
  geom GEOMETRY(LineString, 3857)
);
CREATE INDEX idx_edge_cost ON indoorgml_nav.edge (cost);

-- Migración ejemplo desde AREAS
CREATE VIEW v_migracion_areas AS
SELECT id_area AS cell_id, nombre AS name, tipo AS usage, id_planta AS floor, geom,
       ST_Centroid(geom) AS point_geom  -- Para node inicial
FROM area;  -- Tu tabla old
-- Insert: INSERT INTO cellspace SELECT * FROM v_migracion_areas;
```

**Ventajas Desarrolladas (Tabla)**:

| Ventaja                             | Beneficio en Esquema Nuevo                                                                 |
|-------------------------------------|--------------------------------------------------------------------------------------------|
| **Compatibilidad 1.1**              | Exporta views a GML: `SELECT cell_id, geom FROM cellspace`.                                |
| **Preparado 2.0**                   | Names estables (Node/Edge); añade theme='TOPOGRAPHIC' en tabla layer.                      |
| **pgRouting**                       | Directo: `pgr_dijkstra('SELECT edge_id, node_from, node_to, cost FROM edge')`.             |
| **Puertas Múltiples/FSS**           | UNIQUE permite 1+ Node por CellSpace; subdivide geom con ST_Subdivide para FSS.            |

**Tip para TFG**: Checklist como Anexo: [x] Renombrar tablas; [x] Script migración; [x] Vistas GML; [x] Documentar "Núcleo IndoorGML; FSS futuro"; [x] pgRouting demo (ej. ruta sample).

#### 4. Sobre Door-to-Door (DTD): Generación y Uso
**Desarrollo**: DTD como capa derivada (theme='DOOR_TO_DOOR') para precisión (nodos=puertas, edges=intra-celda). No fábrica en IndoorGML, pero recomendada en lit. Deriva de transition (tu CONEXION con type='door'). Usa para rutas detalladas (evacuación: "por puerta norte").

**SQL Desarrollado (PostGIS, Adaptado)**:
```sql
-- Asume transition = tu CONEXION (añade type='door')
ALTER TABLE conexion ADD COLUMN IF NOT EXISTS type TEXT CHECK (type IN ('door', 'window'));

-- 1. door_node (nodos = puertas)
CREATE TABLE indoorgml_nav.door_node AS
SELECT 
  c.id_conexion AS door_id,
  'DR-' || LPAD(c.id_conexion::text, 4, '0') AS code,
  ST_StartPoint(c.geom) AS geom  -- O ST_Centroid si Polygon
FROM conexion c
WHERE c.type = 'door';

-- 2. door_edge (pares en misma celda)
CREATE TABLE indoorgml_nav.door_edge AS
SELECT 
  row_number() OVER () AS edge_id,
  'DE-' || row_number() OVER ()::text AS code,
  d1.door_id AS door_from,
  d2.door_id AS door_to,
  ST_Length(ST_ShortestLine(d1.geom, d2.geom)) AS cost,
  ST_MakeLine(d1.geom, d2.geom) AS geom
FROM door_node d1
JOIN conexion c1 ON c1.id_conexion = d1.door_id
JOIN conexion c2 ON c2.id_area_origen = c1.id_area_origen  -- Misma área
JOIN door_node d2 ON d2.door_id = c2.id_conexion AND d2.door_id > d1.door_id;  -- Evita duplicados

-- pgRouting ejemplo: pgr_dijkstra('SELECT edge_id, door_from, door_to, cost FROM door_edge', start_door, end_door);
```

**Ventajas y Cuándo (Tabla Expandida)**:

| Door-to-Door Use Case                | Cuándo Interesa                              | Por Qué en Tu TFG                                            |
|--------------------------------------|----------------------------------------------|-------------------------------------------------------------|
| **Rutas Precisas (Múlti-Puertas)**   | Hospitales/aeropuertos.                     | Evac: Especifica "puerta de emergencia norte".              |
| **Distancias Métricas Exactas**      | Logística (robots/AGV).                     | Integra con sensores: Cost dinámico por congestión.         |
| **Puertas Inteligentes/Sensores**    | Control acceso.                             | Bloquea edge si lecturas > umbral (humo en puerta).         |

**Tip para TFG**: Pasos: [x] Añade type='door'; [x] Genera tablas; [x] Export v_door_node_gml; [x] Documenta dos grafos (Cell-to-Cell core; DTD temático).

#### 5. Terminología: DTD y RTR (Room-to-Room)
**Desarrollo**: RTR = Topographic Layer (básico, sala-a-sala); DTD = Space Layer adicional (puerta-a-puerta, theme=ACCESS_POINT). Independientes, enlazadas por InterLayerConnection (ej. puerta pertenece a sala). Lit. enfatiza granularidad: RTR simplifica, DTD precisa.

**Tabla Desarrollada (Encaje IndoorGML)**:

| Término                  | Encaje en IndoorGML 1.1/2.0                                                                 | Idea Clave para Tu BD                          |
|--------------------------|---------------------------------------------------------------------------------------------|------------------------------------------------|
| **Room-to-Room (RTR)**  | Topographic Layer: Primal=CellSpace; Dual=Node/Edge (1 nodo/sala, edge/puerta).             | Grafo base: `node` por AREA, `edge` por CONEXION. |
| **Door-to-Door (DTD)**  | Otro Layer (theme=ACCESS_POINT): Primal=puertas opc.; Dual=Node=puertas, Edge=intra-sala.   | Capa derivada: door_node/edge para precisión.  |
| **Thematic Layer (2.0)**| Agrupa primal+dual con theme (TOPOGRAPHIC/FUNCTIONAL/DOOR_TO_DOOR).                         | Tabla layer con theme para export.             |

**Por Qué No Comparten Nodos/Aristas (Desarrollado)**:
1. **Semántica**: RTR: Salas como átomos; DTD: Puertas como átomos.
2. **Granularidad**: RTR rápido (simplificado); DTD exacto (métrico, multi-puertas).
3. **Mantenimiento**: Actualiza DTD sin tocar RTR (ej. cierra puerta por sensor).

**Relacionarlas**: Usa InterLayerConnection.
```sql
-- Tabla enlace (opcional)
CREATE TABLE indoorgml_nav.ilc_cell_door (
  cell_id INT REFERENCES indoorgml_core.cellspace(cell_id),
  door_id INT REFERENCES indoorgml_nav.door_node(door_id),
  relation_type TEXT DEFAULT 'belongs_to',  -- 'contains', 'connects'
  PRIMARY KEY (cell_id, door_id)
);
-- Insert ejemplo: INSERT INTO ilc_cell_door VALUES (1, 17, 'belongs_to');  -- C42 contiene D17
```

**Cómo Describirlo en TFG**: "El modelo usa dos ThematicLayers: TOPOGRAPHIC (RTR para general) y DOOR_TO_DOOR (DTD para intra-sala), enlazados por InterLayerConnection para rutas híbridas".

**Tip**: Lit. cita: "Door-to-Door generated by connecting doors in same cell". Añade Mermaid: Layer1 (RTR) → ILC → Layer2 (DTD).

#### 6. Puntos Clave para No Perderse
**Desarrollo**: Consolidado y expandido con tu contexto (sensores).

1. **Layer vs. Theme**: 1.1: Layer genérico; 2.0: +theme (usa en tabla para export).
2. **Independencia**: Capas separadas; conecta solo si necesitas (ej. RTR → DTD para ruta full).
3. **RTR Rápido vs. DTD Preciso**: RTR para overview; DTD cuando puertas importan (evac).
4. **Más Capas**: Sensores (atributos en Edge para bloques dinámicos).
5. **IoT Soporte**: Extiende Edge con `dynamic_cost` de lecturas (ej. +penalización si media_temp >25).

**Tip para TFG**: Usa en "Discusión": "Multi-Layered Model permite capas como DTD sin romper core".

#### 7. Sobre las Demás Capas de Movilidad (Expandida)
**Desarrollo**: Sí, hay más: IndoorGML soporta extensiones para movilidad/accesibilidad via multi-layered model y thematic layers. No core, pero lit. propone schemas extendidos para PMR (personas movilidad reducida): Capas para walking/rolling/wheelchair, capturando rampas/elevadores como TransferSpace con locomotionType. Ej.: Extensión para 3D navegación discapacitados, integrando facilidades asistivas (rampas, barandillas) en grafo dual. En tu BD: Añade layer theme='MOBILITY' con filtros en Edge (cost ∞ si no accesible).

**Tabla de Capas de Movilidad**:

| Capa/Tipo Movilidad | Descripción IndoorGML                                                                 | Implementación en Tu BD                          | Relevancia TFG |
|---------------------|---------------------------------------------------------------------------------------|--------------------------------------------------|----------------|
| **Walking (PMR)**   | Topographic con locomotionType='walking'; incluye escaleras como vertical edges.     | Edge con atributo `locomotion_type TEXT`; filtro cost para rampas. | Filtros accesibilidad en rutas evac. |
| **Wheelchair/Rolling** | Extensión: Captura rampas/barandillas como NavigableSpace; multi-layer para jerarquía. | Nueva thematic_layer theme='ACCESSIBILITY'; edges solo si pendiente <8%. | Originalidad: Integra con sensores (bloqueos por congestión). |
| **Elevator/Vertical** | TransferSpace vertical; InterLayerConnection entre plantas.                          | vertical_edges con type='elevator'; cost bajo para movilidad reducida. | Multi-planta: Enlaza layers por floor. |

**SQL Ejemplo (Capa Movilidad)**:
```sql
-- Extiende edge para movilidad
ALTER TABLE indoorgml_nav.edge ADD COLUMN IF NOT EXISTS locomotion_type TEXT DEFAULT 'walking' CHECK (locomotion_type IN ('walking', 'rolling'));
ALTER TABLE indoorgml_nav.edge ADD COLUMN IF NOT EXISTS accessibility_cost FLOAT GENERATED ALWAYS AS (CASE WHEN locomotion_type = 'rolling' AND geom_pendiente > 0.08 THEN cost * 10 ELSE cost END) STORED;

-- Vista para layer movilidad
CREATE VIEW v_mobility_layer AS
SELECT * FROM edge WHERE locomotion_type = 'rolling';  -- Filtra accesible
```

**Tip para TFG**: Roadmap: "Extensión PMR como thematic layer, basado en [extensión schema]". Añade demo: Ruta wheelchair vs. walking.

Esto completa el texto: Ordenado, accionable, con ~20% expansión en movilidad. ¿Quieres Mermaid para layers o script ETL full?