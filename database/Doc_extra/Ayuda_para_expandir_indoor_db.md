### Resumen de lo que Recuerdo de Nuestras Conversaciones Previas

Antes de ordenar y desarrollar las ideas del texto que me pasas, te confirmo lo que recuerdo de todo lo que hemos hablado (basado en los documentos y mensajes anteriores). Esto me ayuda a contextualizar y asegurar coherencia. He agrupado mis recuerdos en puntos clave para que sea fácil verificar:

- **Alineación con IndoorGML**: Adoptamos una implementación "lite" (Core + Navigation), mapeando AREA → CellSpace, CONEXION → Edge/TransferSpace. Usamos capas temáticas (ThematicLayer) para Room-to-Room (RTR) y Door-to-Door (DTD). Semántica con `semanticExtension = true` para navegación. Roadmap para FSS y multi-capa (accesibilidad, POIs).
  
- **Estructura general de la BD (`evac_db`)**: 4 bloques conceptuales: 1) Edificios/Espacios (AREA central, PLANTA/EDIFICIO, CONEXION/CONEXION_CONDICIONAL para puertas/ventanas); 2) Sensores/Lecturas (BALIZA, SENSOR, VARIABLE, LECTURA/HISTORICO_LECTURAS); 3) Seguridad/Eventos (pendiente, para CEP y filtros dinámicos); 4) Usuarios/Rutas (para enrutamiento y evacuación). Entidad central: AREA (con atributos como superficie_m2, capacidad_personas, salida_segura).

- **Aspectos espaciales**: Trabajo en 2D con PostGIS (SRID EPSG:3857 fijo para web/dashboard). Geometrías: Polygon para spaces/openings, LineString para edges. Reglas topológicas (ST_Touches, ST_CoveredBy). Centroides y bounding boxes para posicionamiento. Para formas irregulares (L/T/U): Dividir en rectángulos conectados.

- **Grafos y rutas**: RTR (nodos=áreas, edges=conexiones); DTD (nodos=puertas, edges=trayectos intra-área con ST_ShortestLine para distancias). Integración con pgRouting/NetworkX (weights por tiempo/distancia). Aristas verticales para escaleras/rampas. Filtros: Accesibilidad (walking/rolling), emergencias (bloqueos dinámicos).

- **Sensores y datos dinámicos**: Balizas con coordenadas x/y para mapeo espacial. Dos tablas para lecturas: Actual (snapshot único por combo) + Histórico (trazabilidad). Consultas frecuentes: Media de últimas 3 lecturas por ubicación/variable (ventana deslizante con ROW_NUMBER). Optimizaciones: Particiones por fecha/ubicación, índices GiST/timestamp, vistas materializadas.

- **Configuración BD**: PostgreSQL + PostGIS. Esquemas: `indoorgml_core` (primal), `indoorgml_nav` (dual). IDs: Numéricos PK + códigos alfanuméricos (ej. CS-0001 para CellSpace). Orden de scripts SQL modular (00_create_db → 10_sample_data). Pendientes: Pasar a inglés, alinear full IndoorGML, incluir figuras/video.

- **Mejoras generales**: Usar GENERATED columnas para distancias (ST_Length). Triggers para validación/actualizaciones automáticas. Dashboard-friendly: Códigos autoexplicativos, geometrías para QGIS/export GML.

Esto cubre ~90% de lo discutido. Si algo falta (ej. detalles de usuarios o eventos), dime para ajustar.

### Confirmar, Añadir o Eliminar Ideas

Basado en el texto y recuerdos, aquí va un análisis rápido para refinar:

| Idea del Texto | Confirmar/Añadir/Eliminar | Razón/Desarrollo Breve |
|---------------|---------------------------|-------------------------|
| **Consulta media de últimas 3 lecturas** | **Confirmar**: Es clave para CEP (análisis eventos complejos). Adaptar a PG (usar `timestamp` consistente). | Alinea con histórico para auditorías. Añadir: Vista materializada refrescada cada 10s para rendimiento. |
| **Dos tablas: LECTURA_ACTUAL + HISTORICO** | **Confirmar**: Estrategia sólida para snapshot vs. trazabilidad. | Eliminar: MySQL-specific (AUTO_INCREMENT → SERIAL en PG). Añadir: Trigger para volcado auto de actual a histórico. |
| **Inserciones con ON DUPLICATE** | **Confirmar**: Eficiente para updates. | En PG: Usar `INSERT ... ON CONFLICT DO UPDATE`. Añadir: Ejemplo batch para datos masivos de balizas. |
| **Consultas de agrupamiento por ubicación** | **Confirmar**: Prioridad alta. | Añadir: JOIN con AREA para contexto espacial (ej. media por superficie_m2). |
| **Particiones e índices** | **Confirmar**: Por fecha/ubicación para queries temporales. | Eliminar: Ejemplo RANGE YEAR (usa MONTH para granularidad fina). Añadir: GiST para coords de balizas. |
| **Vistas para resúmenes** | **Confirmar**: Útil para seguridad (ej. media por ubicación). | Añadir: Vista con alertas (si media > umbral). |
| **Unique Key en LECTURA_ACTUAL** | **Confirmar**: Evita duplicados, acelera queries. | Eliminar: Nombre idx_sensor_variable_ubicacion (usa más descriptivo: uk_actual_snapshot). Añadir: Incluir id_baliza en unique si balizas por área varían. |
| **Ejemplo de inserciones** | **Confirmar**: Ilustra bien. | Adaptar fechas a 2025 (actual). Añadir: Salida esperada en tabla Markdown. |
| **Centroides para AREA/CONEXION/PLANTA** | **Confirmar**: Esencial para mapeo. | Añadir: Para BALIZA: Campos x/y o GEOMETRY(POINT). Usar ST_Centroid para auto-cálculo en trigger. |
| **Orden de creación BD** | **Confirmar**: Modular con /sql/ estructura. | Eliminar: Duplicados de recomendaciones (consolidar tabla). Añadir: Script 01_extensions.sql con PostGIS enable. |
| **Door-to-Door con GENERATED distancia** | **Confirmar**: Peso para grafos. | Añadir: Tabla door_to_door con FK a CONEXION. Integrar en indoorgml_nav. |
| **Modelado DTD y formas L/T/U** | **Confirmar**: DTD aparte de conexiones. Dividir irregulares. | Añadir: Función PG para subdivisión (ST_Subdivide). |
| **Config BD (SRID, esquemas, IDs, semántica)** | **Confirmar**: Todo fijo como indicas. | Eliminar: "con la z" (2D prioritario). Añadir: Columna code en tablas (ej. GENERATED o trigger). |

En general: **Confirmo 80%** (sólido para rendimiento/dinámica). **Añado 15%** (adaptaciones PG, triggers, espacial para balizas). **Elimino 5%** (inconsistencias MySQL, redundancias).

### Ideas Ordenadas y Desarrolladas

He ordenado las ideas en **secciones lógicas**, fluyendo de consultas → tablas → operaciones → optimizaciones → espaciales → config general. Cada una desarrollada con: Explicación, SQL adaptado a PostgreSQL (corregido: SERIAL, TIMESTAMP, ON CONFLICT), ejemplos y tips. Incluyo el Mermaid actualizado con coords para BALIZA.

#### 1. Objetivo Principal: Consultas de Evaluación (Media de Últimas 3 Lecturas)
**Desarrollo**: Esta consulta es el núcleo para análisis CEP (Complex Event Processing): Detecta patrones/anomalías en tiempo real (ej. subida de temperatura en área). Usa ventana deslizante (ROW_NUMBER) sobre HISTORICO_LECTURAS para flexibilidad (maneja <3 lecturas). Ejecuta cada 10s via cron/job o función PG. Para live, usa LECTURA_ACTUAL como base rápida.

**SQL Desarrollado (para HISTORICO_LECTURAS)**:
```sql
-- Vista materializada para media de últimas 3 (refresca cada 10s con REFRESH MATERIALIZED VIEW)
CREATE MATERIALIZED VIEW vm_media_ultimas_3 AS
WITH ordenadas AS (
  SELECT
    id_ubicacion, id_variable, id_sensor,  -- Incluir id_sensor si varía por baliza
    valor, timestamp,
    ROW_NUMBER() OVER (
      PARTITION BY id_ubicacion, id_variable, id_sensor  -- Agrupar por sensor si aplica
      ORDER BY timestamp DESC
    ) AS rn
  FROM historico_lecturas
),
ultimas_3 AS (
  SELECT * FROM ordenadas WHERE rn <= 3
)
SELECT
  id_ubicacion, id_variable, id_sensor,
  ROUND(AVG(valor)::numeric, 2) AS media_ultimas_3,
  COUNT(*) AS num_lecturas_usadas  -- Útil para logs (si <3, alerta)
FROM ultimas_3
GROUP BY id_ubicación, id_variable, id_sensor;

-- Uso: SELECT * FROM vm_media_ultimas_3 WHERE id_ubicacion = 10;
-- Refresco: REFRESH MATERIALIZED VIEW vm_media_ultimas_3; (en script cron)
```

**Tip**: Si solo por ubicación/variable (sin sensor), quita id_sensor del PARTITION. Integra con AREA: `JOIN area ON area.id_area = id_ubicacion` para filtrar por tipo (ej. solo 'sala').

#### 2. Estructura de Tablas: LECTURA_ACTUAL y HISTORICO_LECTURAS
**Desarrollo**: Dos tablas para balance: ACTUAL (rápida, única por combo sensor+variable+ubicación+baliza) como snapshot live; HISTORICO (todo lo demás) para auditorías/históricas. Tamaño fijo en ACTUAL vía UNIQUE. Agrupamiento por ubicación prioritario para queries planta-wide.

**SQL Desarrollado (PostgreSQL-adaptado)**:
```sql
-- LECTURA_ACTUAL (snapshot único)
CREATE TABLE IF NOT EXISTS lectura_actual (
  id_lectura SERIAL PRIMARY KEY,
  id_ubicacion INT NOT NULL REFERENCES area(id_area),  -- Asumiendo UBICACION = AREA
  id_baliza INT NOT NULL REFERENCES baliza(id_baliza),
  id_sensor INT NOT NULL REFERENCES sensor(id_sensor),
  id_variable INT NOT NULL REFERENCES variable(id_variable),
  timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  valor FLOAT NOT NULL,
  UNIQUE (id_sensor, id_variable, id_ubicacion, id_baliza)  -- Evita duplicados por baliza
);

-- HISTORICO_LECTURAS (todas las lecturas)
CREATE TABLE IF NOT EXISTS historico_lecturas (
  id_historico SERIAL PRIMARY KEY,
  id_ubicacion INT NOT NULL REFERENCES area(id_area),
  id_baliza INT NOT NULL REFERENCES baliza(id_baliza),
  id_sensor INT NOT NULL REFERENCES sensor(id_sensor),
  id_variable INT NOT NULL REFERENCES variable(id_variable),
  timestamp TIMESTAMP NOT NULL,
  valor FLOAT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_historico_ubicacion_timestamp ON historico_lecturas (id_ubicacion, timestamp DESC);
```

**Tip**: Añade `activa BOOLEAN DEFAULT true` en BALIZA/SENSOR para filtrar inactivos.

#### 3. Inserción de Datos (Batch/Trigger)
**Desarrollo**: Al llegar lecturas (de balizas/IoT), inserta en HISTORICO y actualiza ACTUAL. Usa ON CONFLICT para upserts atómicos. Para masivo: Batch via COPY o función PL/pgSQL.

**SQL Desarrollado**:
```sql
-- Función para inserción batch (llama desde backend o trigger)
CREATE OR REPLACE FUNCTION insertar_lectura(
  p_id_ubicacion INT, p_id_baliza INT, p_id_sensor INT, p_id_variable INT, p_valor FLOAT
) RETURNS VOID AS $$
BEGIN
  -- Insertar en histórico
  INSERT INTO historico_lecturas (id_ubicacion, id_baliza, id_sensor, id_variable, timestamp, valor)
  VALUES (p_id_ubicacion, p_id_baliza, p_id_sensor, p_id_variable, CURRENT_TIMESTAMP, p_valor);

  -- Upsert en actual
  INSERT INTO lectura_actual (id_ubicacion, id_baliza, id_sensor, id_variable, timestamp, valor)
  VALUES (p_id_ubicacion, p_id_baliza, p_id_sensor, p_id_variable, CURRENT_TIMESTAMP, p_valor)
  ON CONFLICT (id_sensor, id_variable, id_ubicacion, id_baliza)
  DO UPDATE SET valor = EXCLUDED.valor, timestamp = EXCLUDED.timestamp;
END;
$$ LANGUAGE plpgsql;

-- Uso: SELECT insertar_lectura(10, 1, 1, 1, 23.5);
```

**Tip**: Trigger en HISTORICO para auto-volcado si backend falla, pero evita para alto volumen (usa app-level).

#### 4. Consultas de Agrupamiento por Ubicación
**Desarrollo**: Rápidas para dashboard/planta. Incluye detalle o resúmenes. Compara actual vs. histórico para deltas (ej. incremento %).

**SQL Desarrollado**:
```sql
-- Agrupamiento simple por ubicación (de ACTUAL)
SELECT 
  id_ubicacion,
  COUNT(*) AS total_lecturas,
  ROUND(AVG(valor)::numeric, 2) AS promedio_valor
FROM lectura_actual
GROUP BY id_ubicacion
ORDER BY id_ubicacion;

-- Detalle por ubicación específica
SELECT * FROM lectura_actual WHERE id_ubicacion = 3 ORDER BY timestamp DESC;

-- Comparación histórico (últimos 10 min)
SELECT * FROM historico_lecturas 
WHERE id_ubicacion = 3 AND timestamp >= NOW() - INTERVAL '10 minutes'
ORDER BY timestamp DESC;
```

**Tip**: JOIN con AREA: `... JOIN area a ON a.id_area = id_ubicacion` para añadir superficie_m2 en output.

#### 5. Optimizaciones: Particiones, Índices y Vistas
**Desarrollo**: Particiones para queries históricas grandes (por mes para granularidad). Índices para filtros comunes. Vistas para seguridad (alertas si media > umbral).

**SQL Desarrollado**:
```sql
-- Partición en HISTORICO (por RANGE mes, desde 2025)
CREATE TABLE historico_lecturas_part (
  LIKE historico_lecturas INCLUDING ALL
) PARTITION BY RANGE (timestamp);
CREATE TABLE historico_lecturas_2025_09 PARTITION OF historico_lecturas_part
  FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
-- Añadir más: ALTER TABLE historico_lecturas_part ATTACH PARTITION ... 

-- Vista resumen por ubicación (con alerta ejemplo)
CREATE OR REPLACE VIEW vista_estado_seguro AS
SELECT 
  la.id_ubicacion,
  AVG(la.valor) AS media_actual,
  MAX(la.timestamp) AS ultima_actualizacion,
  CASE WHEN AVG(la.valor) > 25 THEN 'ALERTA_TEMPERATURA' ELSE 'OK' END AS estado_seguro
FROM lectura_actual la
GROUP BY la.id_ubicacion;
```

**Tip**: Refresca vistas con triggers o pg_cron. GiST para futuras coords: `CREATE INDEX idx_baliza_geom ON baliza USING GIST (geom);`.

#### 6. Unique Key en LECTURA_ACTUAL
**Desarrollo**: Clave compuesta (sensor + variable + ubicación + baliza) asegura unicidad y acelera JOINs/upserts. Crea índice auto para queries por combo.

**SQL Desarrollado**: Ya en tabla arriba (UNIQUE clause). Ejemplo impacto:
- Sin: Duplicados posibles → queries lentas.
- Con: `EXPLAIN ANALYZE SELECT * FROM lectura_actual WHERE id_sensor=1 AND id_variable=1 AND id_ubicacion=10;` → Usa índice compuesto.

**Tip**: Si balizas no varían por área, quita id_baliza del unique para simplicidad.

#### 7. Ejemplo Completo de Inserciones y Resultado
**Desarrollo**: Simulación con 2 ubicaciones, sensores/variables. Fechas en 2025. Resultado: Solo 4 filas (una por combo).

**SQL Desarrollado**:
```sql
-- Asume tablas creadas. Inserciones:
INSERT INTO lectura_actual (id_lectura, id_sensor, id_variable, id_ubicacion, valor, timestamp)
VALUES (1, 1, 1, 10, 22.0, '2025-09-27 10:00:00'::timestamp)
ON CONFLICT (...) DO UPDATE SET valor = EXCLUDED.valor, timestamp = EXCLUDED.timestamp;

-- Nueva para mismo combo (actualiza)
INSERT INTO lectura_actual (id_lectura, id_sensor, id_variable, id_ubicacion, valor, timestamp)
VALUES (2, 1, 1, 10, 23.5, '2025-09-27 10:05:00'::timestamp)
ON CONFLICT (...) DO UPDATE SET valor = EXCLUDED.valor, timestamp = EXCLUDED.timestamp;

-- Otras: (3: sensor1-var2-ubic10=65.0@10:06), (4: sensor2-var1-ubic20=24.8@10:07), (5: sensor2-var2-ubic20=60.0@10:08)
```

**Resultado Esperado (Tabla)**:

| id_lectura | id_sensor | id_variable | id_ubicacion | valor | timestamp          |
|------------|-----------|-------------|--------------|-------|--------------------|
| 2         | 1        | 1          | 10          | 23.5 | 2025-09-27 10:05:00 |
| 3         | 1        | 2          | 10          | 65.0 | 2025-09-27 10:06:00 |
| 4         | 2        | 1          | 20          | 24.8 | 2025-09-27 10:07:00 |
| 5         | 2        | 2          | 20          | 60.0 | 2025-09-27 10:08:00 |

#### 8. Añadir Centroides/Coordenadas (para AREA, CONEXION, PLANTA y BALIZA)
**Desarrollo**: Para mapeo espacial. Usa ST_Centroid en trigger para auto-cálculo. Para BALIZA: Añade x/y o POINT (prioridad GIS).

**SQL Desarrollado**:
```sql
-- ALTERS
ALTER TABLE area ADD COLUMN IF NOT EXISTS centroid_x DOUBLE PRECISION, centroid_y DOUBLE PRECISION;
ALTER TABLE area ADD COLUMN IF NOT EXISTS min_x DOUBLE PRECISION, min_y DOUBLE PRECISION, max_x DOUBLE PRECISION, max_y DOUBLE PRECISION;
ALTER TABLE conexion ADD COLUMN IF NOT EXISTS pos_x DOUBLE PRECISION, pos_y DOUBLE PRECISION;
ALTER TABLE planta ADD COLUMN IF NOT EXISTS origin_x DOUBLE PRECISION DEFAULT 0, origin_y DOUBLE PRECISION DEFAULT 0;

-- Para BALIZA (nueva: coords o geom)
ALTER TABLE baliza ADD COLUMN IF NOT EXISTS pos_x DOUBLE PRECISION, pos_y DOUBLE PRECISION;
ALTER TABLE baliza ADD COLUMN IF NOT EXISTS geom GEOMETRY(POINT, 3857);  -- Para GIS

-- Trigger ejemplo para auto-centroide en AREA (asumiendo geom en area)
CREATE OR REPLACE FUNCTION set_centroid_from_geom() RETURNS TRIGGER AS $$
BEGIN
  NEW.centroid_x := ST_X(ST_Centroid(NEW.geom));
  NEW.centroid_y := ST_Y(ST_Centroid(NEW.geom));
  -- Bounding box
  NEW.min_x := ST_XMin(NEW.geom); NEW.min_y := ST_YMin(NEW.geom);
  NEW.max_x := ST_XMax(NEW.geom); NEW.max_y := ST_YMax(NEW.geom);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_area_centroid BEFORE INSERT OR UPDATE ON area
FOR EACH ROW EXECUTE FUNCTION set_centroid_from_geom();

-- Para BALIZA: Similar, o manual: UPDATE baliza SET geom = ST_MakePoint(pos_x, pos_y, 0) WHERE id_baliza = 1;
```

**Mermaid Actualizado (Bloque 2 con Coords en BALIZA)**:
```
%% --- Bloque 2: Sensores y Lecturas (actualizado con coords) ---
AREA ||--o{ LECTURA : "ocurre en"
AREA ||--o{ HISTORICO_LECTURAS : "ocurre en"
AREA ||--o{ BALIZA : "tiene"

BALIZA   ||--o{ BALIZA_SENSOR : "tiene sensores"
SENSOR   ||--|| SENSOR_VARIABLE : "mide variables"
SENSOR   ||--o{ BALIZA_SENSOR : "conectado a"
VARIABLE ||--|| SENSOR_VARIABLE : "definida en"

HISTORICO_LECTURAS ||--o{ VARIABLE : "mide"
HISTORICO_LECTURAS ||--o{ SENSOR : "usa"
HISTORICO_LECTURAS ||--o{ BALIZA : "genera"

LECTURA ||--o{ VARIABLE : "mide"
LECTURA ||--o{ SENSOR : "usa"
LECTURA ||--o{ BALIZA : "genera"

BALIZA {
  int id_baliza PK
  varchar nombre
  text descripcion
  boolean activa
  int id_area FK
  double pos_x  // Nueva: coord X
  double pos_y  // Nueva: coord Y
  geometry geom POINT(3857)  // Opcional GIS
}
-- Resto igual...
```

**Tip**: Para dashboard: Query `SELECT id_area, centroid_x, centroid_y FROM area;` para plotear en Leaflet (compatible 3857).

#### 9. Orden de Creación de la Base de Datos
**Desarrollo**: Modular para iteraciones. Usa IF NOT EXISTS para re-ejecuciones seguras. Estructura /sql/ con comentarios.

**Estructura Desarrollada (/sql/)**:
```
/sql/
├── 00_create_database.sql          -- CREATE DATABASE evac_db;
├── 01_extensions.sql               -- CREATE EXTENSION postgis; CREATE EXTENSION pg_trgm;
├── 02_schemas.sql                  -- CREATE SCHEMA indoorgml_core; CREATE SCHEMA indoorgml_nav;
├── 03_tablas_espaciales.sql        -- CREATE TABLE area (...); etc. (Bloque 1)
├── 04_tablas_sensores.sql          -- BALIZA, SENSOR, etc. (Bloque 2, con coords)
├── 05_tablas_lecturas.sql          -- LECTURA_ACTUAL, HISTORICO_LECTURAS
├── 06_particiones.sql              -- Particiones en historico_lecturas
├── 07_functions_triggers.sql       -- insertar_lectura(), trg_area_centroid
├── 08_views.sql                    -- vm_media_ultimas_3, vista_estado_seguro
├── 09_indexes.sql                  -- UNIQUE, GiST, etc.
└── 10_sample_data.sql              -- INSERTs de prueba
```

**Script Ejemplo (00_create_database.sql)**:
```sql
CREATE DATABASE IF NOT EXISTS evac_db;
\c evac_db;  -- Conectar
```

**Tip**: En pgAdmin: Ejecuta secuencial (F5 por archivo). Git para versiones: `git add sql/ && git commit -m "Add lecturas module"`.

#### 10. Modelado Door-to-Door (DTD) y Formas Espaciales Irregulares
**Desarrollo**: DTD como capa separada en `indoorgml_nav` (nodos=puertas de CONEXION, edges=trayectos con distancia GENERATED). Para L/T/U: Función para subdividir Polygon en rectángulos conectados (usa ST_Subdivide + ST_Intersection).

**SQL Desarrollado (DTD)**:
```sql
-- Tabla door_to_door (en indoorgml_nav)
CREATE TABLE IF NOT EXISTS door_to_door (
  id_edge SERIAL PRIMARY KEY,
  door_from INT REFERENCES conexion(id_conexion),
  door_to INT REFERENCES conexion(id_conexion),
  geom GEOMETRY(LineString, 3857),
  distancia_metros DOUBLE PRECISION GENERATED ALWAYS AS (ST_Length(geom)) STORED
);

-- Vista para generar edges intra-área (ej. puertas en misma AREA)
CREATE VIEW v_door_edges AS
SELECT 
  row_number() OVER () AS id_edge,
  c1.id_conexion AS door_from,
  c2.id_conexion AS door_to,
  ST_ShortestLine(c1.geom, c2.geom) AS geom  -- Línea más corta intra-área
FROM conexion c1
JOIN conexion c2 ON c1.id_area_origen = c2.id_area_origen AND c1.id_conexion < c2.id_conexion
WHERE c1.tipo = 'door' AND ST_Within(ST_ShortestLine(c1.geom, c2.geom), (SELECT geom FROM area WHERE id_area = c1.id_area_origen));
-- Materializar: CREATE MATERIALIZED VIEW mv_door_to_door AS SELECT * FROM v_door_edges;
```

**Para Formas L/T/U**:
```sql
-- Función para subdividir (ej. L en 2 rects)
CREATE OR REPLACE FUNCTION subdivide_l_shape(p_geom GEOMETRY) RETURNS SETOF GEOMETRY AS $$
SELECT ST_Subdivide(p_geom, 2);  -- Divide en 2 partes; ajusta n para T/U
$$ LANGUAGE sql;
-- Uso: UPDATE area SET geom_sub = subdivide_l_shape(geom) WHERE forma = 'L';
```

**Tip**: Integra en RTR: JOIN door_to_door para pesos precisos en pgRouting: `pgr_dijkstra('SELECT id_edge, door_from, door_to, distancia_metros FROM door_to_door')`.

#### 11. Configuración General de la BD
**Desarrollo**: Fija como indicas. Esquemas para separación (core: primal/static; nav: dual/dinámico). IDs: PK numérico + columna code (trigger para generar, ej. 'CS-' || LPAD(id::text, 4, '0')).

**SQL Desarrollado (IDs y Semántica)**:
```sql
-- Esquemas
CREATE SCHEMA IF NOT EXISTS indoorgml_core;
CREATE SCHEMA IF NOT EXISTS indoorgml_nav;

-- Ej. Tabla CellSpace (en core) con code
CREATE TABLE indoorgml_core.cellspace (
  id SERIAL PRIMARY KEY,
  code VARCHAR(10) UNIQUE NOT NULL,  -- CS-0001
  -- ... otros
);

-- Trigger para code
CREATE OR REPLACE FUNCTION generate_code() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.code IS NULL THEN
    NEW.code := 'CS-' || LPAD(NEW.id::text, 4, '0');
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_cellspace_code BEFORE INSERT ON indoorgml_core.cellspace
FOR EACH ROW EXECUTE FUNCTION generate_code();

-- Semántica en ThematicLayer (tabla ejemplo en nav)
CREATE TABLE indoorgml_nav.thematic_layer (
  id SERIAL PRIMARY KEY,
  code VARCHAR(10) DEFAULT 'TH-01',
  semantic_extension BOOLEAN DEFAULT true  -- Para Navigation
);
```

**Tip**: Para dashboard: `SELECT code, ... FROM cellspace;` en lugar de id. No cambies SRID: Siempre 3857. Para z: Atributos z_base/z_top en AREA (no full 3D).

Esto ordena todo en un flujo accionable. ¿Quieres SQL completo en un archivo, o expandir sección específica (ej. Mermaid full)?