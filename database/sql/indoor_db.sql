
-------------- Creación de la base de datos si no esta creada --------------

-- CREATE DATABASE IF NOT EXISTS indoor_db;

-------------- Extensiones necesarias para trabajar con geometrías --------------

CREATE EXTENSION IF NOT EXISTS postgis;

--------------------------------------------------------
----------------------01 SCHEMAS------------------------
--------------------------------------------------------

-------------- Esquemas necesarios para el modelo IndoorGML --------------

CREATE SCHEMA IF NOT EXISTS indoorgml_core; --HECHO
CREATE SCHEMA IF NOT EXISTS indoorgml_navigation; --HECHO CON EXITO
--CREATE SCHEMA IF NOT EXISTS monitoring_reading; -- quizas lo dejo indicado
--CREATE SCHEMA IF NOT EXISTS safety_events; -- quizas lo dejo indicado


-- Enum necesario de momento physical
CREATE TYPE indoorgml_core.theme_layer_value AS ENUM ('PHYSICAL','VIRTUAL','TAGS','UNKNOWN');

CREATE TYPE indoorgml_navigation.nav_space_kind AS ENUM ('GENERAL','TRANSFER');--*CAMBIAR NOMBRE SNO ME GUSATN***********nav_space_kind
CREATE TYPE indoorgml_navigation.locomotion_access_type AS ENUM ('WALK','STAIRS','ELEVATOR','ESCALATOR','RAMP','JUMP','OTHER'); --locomotion_access_type locomotion_access_type
--------------------------------------------------------
----------------------02 TABLES------------------------
--------------------------------------------------------


-------------- BLOQUE INDOORGML: CORE [CASI FUNCIONA]--------------

-- THEMATIC LAYER -- [HECHO]

CREATE TABLE indoorgml_core.theme_layer (
    id_theme           VARCHAR(20) PRIMARY KEY,                   -- p.ej. TH-01, TH-02, ... 
    semantic_extension BOOLEAN NOT NULL DEFAULT FALSE,            -- Como usamos Navigation sera TRUE
    theme              indoorgml_core.theme_layer_value NOT NULL  -- 'PHYSICAL' en nuestro caso
);

-- PRIMAL SPACE LAYER -- [HECHO]

CREATE TABLE indoorgml_core.primal_space_layer (
    id_primal        VARCHAR(20) PRIMARY KEY,       -- p.ej. PR-01 , PR-02 , ...
    srid             INTEGER NOT NULL DEFAULT 3857, -- Sistema de referencia espacial
    id_theme_layer   VARCHAR(20) NOT NULL,          -- atributo FK

    FOREIGN KEY (id_theme_layer) REFERENCES indoorgml_core.theme_layer(id_theme), -- FK
    CONSTRAINT primal_one_per_theme UNIQUE (id_theme_layer)                       -- Relacion 1:1 
);

-- DUAL SPACE LAYER -- [HECHO]

CREATE TABLE indoorgml_core.dual_space_layer (
    id_dual          VARCHAR(20) PRIMARY KEY,           -- p.ej. DU-01, DU-01, ...
    is_logical       BOOLEAN NOT NULL DEFAULT FALSE,    -- FALSE porque es real de momento todo
    is_directed      BOOLEAN NOT NULL DEFAULT FALSE,    -- FALSE porque es no dirigido de momento todo
    srid             INTEGER NOT NULL DEFAULT 3857,     -- Sistema de referencia espacial
    id_theme_layer   VARCHAR(20) NOT NULL,              -- atributo FK p.ej. TH-01, TH-02, ...

    FOREIGN KEY (id_theme_layer) REFERENCES indoorgml_core.theme_layer(id_theme), -- FK
    CONSTRAINT dual_one_per_theme UNIQUE (id_theme_layer)                         -- Relacion 1:1 
);

-- CELLSPACE -- [HECHO]

CREATE TABLE indoorgml_core.cell_space(
    id_cell_space           VARCHAR(20) PRIMARY KEY,        -- p.ej. CS-001, CS-002, ...
    name                    TEXT NOT NULL,                  -- p.ej. P01-SPACE-OO1, ...
    external_reference      TEXT,                           -- De momento creacion propia  
    level                   TEXT,                           -- p.ej. P00, P01, ... 
    poi                     BOOLEAN NOT NULL DEFAULT FALSE, -- (Salida de emergencia)
    id_primal_space_layer   VARCHAR(20) NOT NULL,           -- atributo FK p.ej. PR-01 , PR-02
    geom                    GEOMETRY(PolygonZ, 3857),       -- Dato geometrico (2D + Z)

    FOREIGN KEY (id_primal_space_layer) REFERENCES indoorgml_core.primal_space_layer(id_primal),  -- FK
    CONSTRAINT cellspace_geom_valid CHECK (ST_IsValid(geom))                                      -- Para asegurar que la geometria es valida
);

-- CELLBOUNDARY -- [HECHO]

CREATE TABLE indoorgml_core.cell_boundary(
    id_cell_boundary        VARCHAR(20) PRIMARY KEY,          -- p.ej. CB-001, CB-002, ...
    external_reference      TEXT,                             -- De momento creacion propia  
    is_virtual              BOOLEAN NOT NULL DEFAULT FALSE,   -- False porque es real de momnto todo
    id_primal_space_layer   VARCHAR(20) NOT NULL,             -- atributo FK p.ej. PR-01 , PR-02
    geom                    GEOMETRY(MultiLineStringZ, 3857), -- Dato geometrico (conjunto de 1D)
    boundary_key            TEXT,                             -- Para evitar duplicados 

    FOREIGN KEY (id_primal_space_layer) REFERENCES indoorgml_core.primal_space_layer(id_primal), -- FK
    CONSTRAINT chk_cb_id_format CHECK (id_cell_boundary ~ '^CB-\d{3,}$')                         -- Formato ID correcto
);

-- RELACION CELLSPACE-CELLBOUNDARY: BOUNDED BY -- [HECHO] ****PONER EN BLOQUE RELACIONES*** QUIZAS

CREATE TABLE indoorgml_core.cellspace_cellboundary (
    id                INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, -- PK interno 
    id_cell_space     VARCHAR(20) NOT NULL,                         -- atributo FK
    id_cell_boundary  VARCHAR(20) NOT NULL,                         -- atributo FK

    FOREIGN KEY (id_cell_space) REFERENCES indoorgml_core.cell_space(id_cell_space),          -- FK
    FOREIGN KEY (id_cell_boundary) REFERENCES indoorgml_core.cell_boundary(id_cell_boundary), -- FK
    CONSTRAINT uq_cs_cb UNIQUE (id_cell_space, id_cell_boundary)                              -- Evita duplicados
);

-- NODE -- [HECHO]

CREATE TABLE indoorgml_core.node (
    id_node            VARCHAR(20) PRIMARY KEY, -- p.ej. ND-0001
    id_dual            VARCHAR(20) NOT NULL,    -- atributo FK
    id_cell_space      VARCHAR(20) NOT NULL,    -- atributo FK
    geom               geometry(PointZ, 3857),  -- opcional si is_logical=true

    FOREIGN KEY (id_dual) REFERENCES indoorgml_core.dual_space_layer(id_dual),      -- FK
    FOREIGN KEY (id_cell_space) REFERENCES indoorgml_core.cell_space(id_cell_space), -- FK
    CONSTRAINT uq_node_dual_cell UNIQUE (id_dual, id_cell_space) -- 1:1 entre CellSpace y Node
);

-- EDGE -- [HECHO]

CREATE TABLE indoorgml_core.edge (
    id_edge            VARCHAR(20) PRIMARY KEY,     -- p.ej. EG-0001
    weight_m           DOUBLE PRECISION,            -- opcional
    id_dual            VARCHAR(20) NOT NULL,        -- atributo FK
    id_cell_boundary   VARCHAR(20) NULL,            -- atributo FK
    from_node          VARCHAR(20) NOT NULL,        -- atributos FK
    to_node            VARCHAR(20) NOT NULL,        -- atributos FK
    geom               geometry(LineStringZ, 3857), -- opcional si indoorgml_core.dual_space_layer.is_logical=true
    
    FOREIGN KEY (id_dual)          REFERENCES indoorgml_core.dual_space_layer(id_dual),       -- FK
    FOREIGN KEY (id_cell_boundary) REFERENCES indoorgml_core.cell_boundary(id_cell_boundary), -- FK
    FOREIGN KEY (from_node)        REFERENCES indoorgml_core.node(id_node),                   -- FK
    FOREIGN KEY (to_node)          REFERENCES indoorgml_core.node(id_node),                   -- Para evitar nodos inexistentes
    CONSTRAINT ck_edge_from_to_diff CHECK (from_node <> to_node)
);

-------------- BLOQUE INDOORGML: NAVIGATION MODULE --------------

-- Catálogo de funciones/uso de espacios
CREATE TABLE IF NOT EXISTS indoorgml_navigation.nav_space_function (
  code                  VARCHAR(40) PRIMARY KEY,  -- p.ej. ADMIN, STORAGE, OFFICE, CORRIDOR, STAIRS, ELEVATOR...
  label                 TEXT NOT NULL,            -- texto bonito para el selector
  kind                  indoorgml_navigation.nav_space_kind NOT NULL,
  default_locomotion    indoorgml_navigation.locomotion_access_type
);

-- Semillas: GENERAL
INSERT INTO indoorgml_navigation.nav_space_function(code,label,kind,default_locomotion) VALUES
('SPACE','Space','GENERAL','WALK'),
('ADMIN','Administration','GENERAL','WALK'),
('STORAGE','Storage','GENERAL','WALK'),
('OFFICE','Office','GENERAL','WALK'),
('CORRIDOR','Corridor','GENERAL','WALK'),
('HALL','Hall','GENERAL','WALK')
ON CONFLICT (code) DO NOTHING;

-- Semillas: TRANSFER
INSERT INTO indoorgml_navigation.nav_space_function(code,label,kind,default_locomotion) VALUES
('STAIRS','Stair','TRANSFER','STAIRS'),
('ELEVATOR','Elevator','TRANSFER','ELEVATOR'),
('ESCALATOR','Escalator','TRANSFER','ESCALATOR'),
('RAMP','Ramp','TRANSFER','RAMP'),
('LOBBY','Transfer Lobby','TRANSFER','WALK'),
('DOOR','Door','TRANSFER','WALK'),
('WINDOW','Window','TRANSFER','JUMP')

ON CONFLICT (code) DO NOTHING;

-- NAVIGABLE SPACE --
CREATE TABLE IF NOT EXISTS indoorgml_navigation.navigable_space (
  id_cell_space      VARCHAR(20) PRIMARY KEY REFERENCES indoorgml_core.cell_space(id_cell_space) ON DELETE CASCADE,
  kind               indoorgml_navigation.nav_space_kind NOT NULL DEFAULT 'GENERAL',
  function_code      VARCHAR(40) REFERENCES indoorgml_navigation.nav_space_function(code), -- LO PUEDO MODIFICAR EN QGIS
  locomotion         indoorgml_navigation.locomotion_access_type,
  category           TEXT,
  is_emergency_exit  BOOLEAN NOT NULL DEFAULT FALSE,

  -- Si es TRANSFER, debe haber locomotion (la rellenaremos por trigger si está vacía)
  CONSTRAINT ck_transfer_requires_locomotion CHECK (kind <> 'TRANSFER' OR locomotion IS NOT NULL)
);


--------------------------------------------------------
----------------------03 RELACIONES---------------------
--------------------------------------------------------




--------------------------------------------------------
-----------------------04 VIEWS-------------------------
--------------------------------------------------------

-- NAVIGATION MODULE
CREATE OR REPLACE VIEW indoorgml_navigation.v_navigable_space_level AS
SELECT
  ns.id_cell_space,
  cs.id_primal_space_layer,
  cs.level,
  ns.kind,
  ns.function_code,
  nf.label AS function_label,
  ns.locomotion,
  ns.category,
  ns.is_emergency_exit,
  cs.geom
FROM indoorgml_navigation.navigable_space ns
JOIN indoorgml_core.cell_space cs
  ON cs.id_cell_space = ns.id_cell_space
LEFT JOIN indoorgml_navigation.nav_space_function nf
  ON nf.code = ns.function_code;



--------------------------------------------------------
----------------------05 FUNCTIONS----------------------
--------------------------------------------------------

--- BLOQUE INDOORGML: CORE --------------

-- CELLSPACE --

CREATE OR REPLACE FUNCTION indoorgml_core.fn_cell_space_no_overlap() -- Evita solapes entre CellSpace (esto es en 2D no en 3D)
    RETURNS TRIGGER 
    LANGUAGE plpgsql
    AS $$
    
    DECLARE 
        v_conflict_id TEXT; -- guarda el id del cellspace que genera el conflicto (var local de la funcion)
    
    BEGIN
        IF NEW.geom IS NULL OR NEW.level IS NULL THEN
            RETURN NEW;     -- Si la geometría o el nivel es NULL, no hacemos nada
        END IF; 
        
        -- Buscar conflictos en cell_space, (cuando encuentra uno, guarda su id en v_conflict_id)
        SELECT cs.id_cell_space INTO v_conflict_id FROM indoorgml_core.cell_space cs 
        WHERE cs.level = NEW.level                           -- Mismo nivel
            AND cs.id_cell_space <> NEW.id_cell_space        -- Evita compararse a sí mismo
            AND cs.geom && NEW.geom                          -- Filtro (previo) espacial rápido (bounding box) (en teoria acelera el proceso)
            AND (ST_Relate(cs.geom, NEW.geom, '2********') ) -- [ESTE ES EL IMPORTANTE] solape de área (2D)
        LIMIT 1; -- Solo necesitamos saber si hay al menos un conflicto para bloquear la inserción/actualizaciónla
        
        -- Excepcion si hay conflicto (mensaje de error claro)
        IF v_conflict_id IS NOT NULL THEN
            RAISE EXCEPTION 'CellSpace % (level=%) entra en conflicto con % (punto o área compartida no permitidos)',NEW.id_cell_space, NEW.level, v_conflict_id
            USING HINT = 'Solo se permite no contacto o contacto por borde (1D).';
        END IF;
    RETURN NEW; -- Si no hay conflictos, permitir la operación
    END;
    $$;

-- CELLBOUNDARY --

CREATE SEQUENCE IF NOT EXISTS indoorgml_core.seq_cell_boundary START 1; -- Secuencia para IDs de CellBoundary

CREATE OR REPLACE FUNCTION indoorgml_core.next_cb_id() -- Genera IDs únicos para CellBoundary (CB-0001, CB-0002, ...)
  RETURNS varchar LANGUAGE plpgsql AS $$ 
  DECLARE 
      n bigint;
  BEGIN
    n := nextval('indoorgml_core.seq_cell_boundary'); -- Obtener el siguiente valor de la secuencia
    RETURN 'CB-' || lpad(n::text, 4, '0');            -- Devuelvec con fomrato como 'CB-0001', 'CB-0002', ...
  END;
  $$;

CREATE OR REPLACE FUNCTION indoorgml_core.rebuild_cell_boundaries(  -- Reconstruye cell boundaries y sus relaciones a partir de cell spaces  
      p_level TEXT DEFAULT NULL,                -- planta; NULL = todas
      p_psl   VARCHAR(20) DEFAULT NULL,         -- primal; NULL = todas
      p_z     NUMERIC DEFAULT 0                 -- Z de salida
    )
    RETURNS void
    LANGUAGE plpgsql
    AS $$
    DECLARE
      tol DOUBLE PRECISION := 0.001; -- variable para ajustar tolerancia de geometrías (1 mm) (en teoria evita problemas topológicos)
    BEGIN
      --------------------------------------------------------------------
      -- 0) Limpiar SOLO membresías del ámbito afectado
      --------------------------------------------------------------------
      DELETE FROM indoorgml_core.cellspace_cellboundary cscb
      USING indoorgml_core.cell_space cs
      WHERE cscb.id_cell_space = cs.id_cell_space
        AND (p_level IS NULL OR cs.level = p_level)
        AND (p_psl   IS NULL OR cs.id_primal_space_layer = p_psl);

      -- Nota: NO borramos cell_boundary aquí; se borran huérfanos al final (los que no tengan relaciones con cell_space)

      --------------------------------------------------------------------
      -- 1) BORDES INTERNOS (tramos compartidos entre pares de celdas) se consideran navegables
      --------------------------------------------------------------------
      -- Tabla temporal para líneas compartidas (son 2D inicialmente, luego se les añade Z)
      DROP TABLE IF EXISTS tmp_shared_lines;
      CREATE TEMP TABLE tmp_shared_lines(
        ida varchar(20),
        idb varchar(20),
        geom2d geometry(MultiLineString, 3857)
      ) ON COMMIT DROP; -- tabla temporal para líneas compartidas (2D)
      
      -- inserta líneas compartidas (lo hace gracias a ST_Relate lo demas es filtro)
      INSERT INTO tmp_shared_lines(ida, idb, geom2d) 
      SELECT 
        a.id_cell_space,                                                                                         -- solo para referencia interna
        b.id_cell_space,                                                                                         -- solo para referencia interna
        ST_LineMerge(ST_CollectionExtract(ST_Intersection(ST_Force2D(a.geom), ST_Force2D(b.geom)), 2)) AS shared -- se le inserta solo líneas compartida (1D)
      FROM indoorgml_core.cell_space a 
      JOIN indoorgml_core.cell_space b ON a.id_cell_space < b.id_cell_space -- evita duplicados (A-B y B-A)
       AND a.level = b.level                                                -- mismo nivel
       AND a.id_primal_space_layer = b.id_primal_space_layer                -- misma primal
       AND (p_level IS NULL OR a.level = p_level)                           -- filtro por parámetro (level)
       AND (p_psl   IS NULL OR a.id_primal_space_layer = p_psl)             -- filtro por parámetro (primal)
       AND a.geom && b.geom                                                 -- filtro espacial rápido (bounding box)
       AND ST_Relate(a.geom, b.geom, 'F***1****')                           -- contacto por borde (1D)
      WHERE NOT ST_IsEmpty(a.geom) AND NOT ST_IsEmpty(b.geom);              -- evita geometrías vacías

      -- tabla temporal para mapear boundary_key a id_cell_boundary  (sirve para relaciones con cell_space)
      DROP TABLE IF EXISTS tmp_cb_map;
      CREATE TEMP TABLE tmp_cb_map( 
        boundary_key TEXT PRIMARY KEY,
        id_cell_boundary VARCHAR(20)
      ) ON COMMIT DROP; 

      -- tabla temporal para candidatos a límites internos persistentes (sirve para UPDATE + INSERT)
      DROP TABLE IF EXISTS tmp_cand_int;
      CREATE TEMP TABLE tmp_cand_int(
        boundary_key TEXT PRIMARY KEY,
        psl          VARCHAR(20),
        geomz        geometry(MultiLineStringZ,3857),
        ida          VARCHAR(20),
        idb          VARCHAR(20)
      ) ON COMMIT DROP;

      -- inserta candidatos internos persistentes (con boundary_key, psl, geomz, ida, idb)
      INSERT INTO tmp_cand_int(boundary_key, psl, geomz, ida, idb)
      SELECT
        md5(ST_AsBinary(ST_SnapToGrid(ST_LineMerge(ST_Force2D(g2)), tol)))                                         AS boundary_key, -- hash único de la geometría 2D
        (SELECT cs.id_primal_space_layer FROM indoorgml_core.cell_space cs WHERE cs.id_cell_space = u.ida LIMIT 1) AS psl, -- primal común
        ST_Multi(ST_Force3D(u.g2, p_z))::geometry(MultiLineStringZ,3857)                                           AS geomz, -- geometría 3D con Z dada
        u.ida,                                                                                                     -- referencia interna a cellspace
        u.idb                                                                                                      -- referencia interna a cellspace
      FROM (
        WITH dumped AS (
          SELECT ida, idb, (ST_Dump(geom2d)).geom AS g -- descompone en líneas individuales
          FROM tmp_shared_lines  
          WHERE geom2d IS NOT NULL AND NOT ST_IsEmpty(geom2d) -- evita geometrías vacías
        ),
        norm AS (
          SELECT ida, idb, ST_SnapToGrid(ST_Force2D(g), tol) AS g2 -- normaliza geometrías (evita minúsculas diferencias topológicas)
          FROM dumped 
          WHERE GeometryType(g) IN ('LINESTRING','MULTILINESTRING') -- solo líneas (1D) 
            AND ST_NPoints(g) >= 2 -- al menos dos puntos (evita puntos y líneas degeneradas
        ),
        uniq AS (
          SELECT DISTINCT ON (md5(ST_AsBinary(g2))) g2, MIN(ida) AS ida, MIN(idb) AS idb -- elimina duplicados geométricos
          FROM norm   -- de norm (normalizado)
          GROUP BY g2 -- agrupado por geometría
        )
        SELECT * FROM uniq 
      ) u;
      -- Aqui lo siguiente ayuda a entender el flujo:
      -- 1) Se generan líneas compartidas entre pares de cell_space (tmp_shared_lines)
      -- 1.A) Actualiza límites internos existentes (por boundary_key)
      UPDATE indoorgml_core.cell_boundary cb
      SET 
        id_primal_space_layer = c.psl, 
        geom                  = c.geomz 
      FROM tmp_cand_int c 
      WHERE cb.boundary_key = c.boundary_key; -- actualiza si ya existe (esto recicla IDs y relaciones)

      -- 1.B) Inserta SOLO límites internos nuevos (esto para no duplicar)
      INSERT INTO indoorgml_core.cell_boundary
        (id_cell_boundary, external_reference, is_virtual, id_primal_space_layer, geom, boundary_key)
      SELECT indoorgml_core.next_cb_id(), NULL, FALSE, c.psl, c.geomz, c.boundary_key
      FROM tmp_cand_int c
      LEFT JOIN indoorgml_core.cell_boundary cb USING(boundary_key)
      WHERE cb.boundary_key IS NULL; -- solo los que no existen (nuevos)

      -- 1.C) Refresca el relaciones (clave -> ID)
      DELETE FROM tmp_cb_map; -- limpia por si acaso
      INSERT INTO tmp_cb_map(boundary_key, id_cell_boundary)    -- acumula con exteriores (para relaciones)
      SELECT c.boundary_key, cb.id_cell_boundary                -- relaciones boundary_key -> id_cell_boundary
      FROM tmp_cand_int c                                       -- candidatos internos
      JOIN indoorgml_core.cell_boundary cb USING(boundary_key); -- todos los internos

      -- relaciones cellspace-cellboundary (una fila por boundary)
      INSERT INTO indoorgml_core.cellspace_cellboundary(id_cell_boundary, id_cell_space)
      SELECT m.id_cell_boundary, c.ida 
      FROM tmp_cand_int c
      JOIN tmp_cb_map m USING(boundary_key); -- relaciona boundary_key -> id_cell_boundary
       
      INSERT INTO indoorgml_core.cellspace_cellboundary(id_cell_boundary, id_cell_space)
      SELECT m.id_cell_boundary, c.idb 
      FROM tmp_cand_int c
      JOIN tmp_cb_map m USING(boundary_key); 

      --------------------------------------------------------------------
      -- 2) BORDES EXTERIORES (contorno exclusivo de cada celda)
      --------------------------------------------------------------------
      DROP TABLE IF EXISTS tmp_shared_by_cell;
      CREATE TEMP TABLE tmp_shared_by_cell(
        id_cell_space varchar(20),
        geom2d geometry(MultiLineString, 3857)
      ) ON COMMIT DROP;

      INSERT INTO tmp_shared_by_cell(id_cell_space, geom2d)
      SELECT ida, ST_Union(geom2d) FROM tmp_shared_lines GROUP BY ida
      UNION ALL
      SELECT idb, ST_Union(geom2d) FROM tmp_shared_lines GROUP BY idb;

      DROP TABLE IF EXISTS tmp_uniq2;
      CREATE TEMP TABLE tmp_uniq2 ON COMMIT DROP AS
      WITH cell_bnd AS (
        SELECT cs.id_cell_space,
               ST_Force2D(ST_Boundary(cs.geom)) AS b2,
               cs.id_primal_space_layer AS psl
        FROM indoorgml_core.cell_space cs
        WHERE (p_level IS NULL OR cs.level = p_level)
          AND (p_psl   IS NULL OR cs.id_primal_space_layer = p_psl)
      ),
      diff AS (
        SELECT c.id_cell_space, c.psl,
               CASE
                 WHEN s.geom2d IS NULL THEN c.b2
                 ELSE ST_Difference(c.b2, ST_UnaryUnion(s.geom2d))
               END AS g
        FROM cell_bnd c
        LEFT JOIN tmp_shared_by_cell s USING(id_cell_space)
      ),
      merged AS (
        SELECT id_cell_space, psl,
               ST_LineMerge(ST_Union(g)) AS g_merged
        FROM diff
        WHERE g IS NOT NULL AND NOT ST_IsEmpty(g)
        GROUP BY id_cell_space, psl
      ),
      norm2 AS (
        SELECT id_cell_space, psl,
               ST_SnapToGrid(g_merged, tol) AS g2
        FROM merged
        WHERE GeometryType(g_merged) IN ('LINESTRING','MULTILINESTRING')
          AND ST_Length(g_merged) > 0
      )
      SELECT id_cell_space, psl, g2
      FROM norm2;

      -- Candidatos exteriores persistentes
      DROP TABLE IF EXISTS tmp_cand_ext;
      CREATE TEMP TABLE tmp_cand_ext(
        boundary_key  TEXT PRIMARY KEY,
        id_cell_space VARCHAR(20),
        psl           VARCHAR(20),
        geomz         geometry(MultiLineStringZ,3857)
      ) ON COMMIT DROP;

      INSERT INTO tmp_cand_ext(boundary_key, id_cell_space, psl, geomz)
      SELECT
        md5(ST_AsBinary(ST_SnapToGrid(ST_LineMerge(ST_Force2D(u.g2)), tol))) AS boundary_key,
        u.id_cell_space,
        u.psl,
        ST_Multi(ST_Force3D(u.g2, p_z))::geometry(MultiLineStringZ,3857)     AS geomz
      FROM tmp_uniq2 u;

      -- Aqui lo siguiente ayuda a entender el flujo:
      -- 2) Se generan líneas exteriores (contorno exclusivo) para cada cell_space (tmp_cand_ext)
      -- 2.A) Actualiza exteriores existentes
      UPDATE indoorgml_core.cell_boundary cb
      SET id_primal_space_layer = c.psl,
          geom                  = c.geomz
      FROM tmp_cand_ext c
      WHERE cb.boundary_key = c.boundary_key;

      -- 2.B) Inserta SOLO exteriores nuevos
      INSERT INTO indoorgml_core.cell_boundary
        (id_cell_boundary, external_reference, is_virtual, id_primal_space_layer, geom, boundary_key)
      SELECT indoorgml_core.next_cb_id(), NULL, FALSE, c.psl, c.geomz, c.boundary_key
      FROM tmp_cand_ext c
      LEFT JOIN indoorgml_core.cell_boundary cb USING(boundary_key)
      WHERE cb.boundary_key IS NULL;

      -- 2.C) Añade/actualiza en el mapa (acumula con internos)
      INSERT INTO tmp_cb_map(boundary_key, id_cell_boundary)
      SELECT c.boundary_key, cb.id_cell_boundary
      FROM tmp_cand_ext c
      JOIN indoorgml_core.cell_boundary cb USING(boundary_key)
      ON CONFLICT (boundary_key) DO NOTHING;

      -- Membresías exteriores (una fila por boundary)
      INSERT INTO indoorgml_core.cellspace_cellboundary(id_cell_boundary, id_cell_space)
      SELECT m.id_cell_boundary, c2.id_cell_space
      FROM tmp_cand_ext c2
      JOIN tmp_cb_map m USING(boundary_key);

      --------------------------------------------------------------------
      -- 3) LIMPIEZA FINAL: borrar boundaries huérfanos (no referenciados)
      --------------------------------------------------------------------
      DELETE FROM indoorgml_core.cell_boundary cb
      WHERE NOT EXISTS (
        SELECT 1 FROM indoorgml_core.cellspace_cellboundary x
        WHERE x.id_cell_boundary = cb.id_cell_boundary
      ); -- Al no tener relaciones, se borra, te quedas solo con los que tienen relaciones

    END;
    $$;

---- NODE --
-- Convierte un ID de CellSpace (CS-####) -> Node ID (ND-####).
CREATE OR REPLACE FUNCTION indoorgml_core.node_id_from_cellspace(p_cs_id text)
  RETURNS text LANGUAGE plpgsql AS $$
  DECLARE
  num text;
  BEGIN
  SELECT substring(p_cs_id FROM '^CS-(\d+)$') INTO num;
  IF num IS NULL THEN
    RAISE EXCEPTION 'El id_cell_space "%" no sigue el patrón CS-<dígitos>', p_cs_id;
  END IF;
  RETURN 'ND-' || num;
  END $$; -- Para tener coherencia en los IDs

-- Construye/actualiza TODOS los nodos para una Dual y una Primal dadas.
-- Regla: 1 Node por CellSpace (id determinista ND-xxxx)
-- Geom: Centroide si cae dentro; si no, PointOnSurface (fallback).
CREATE OR REPLACE FUNCTION indoorgml_core.rebuild_nodes_for_dual(
  p_dual VARCHAR(20),        -- ej. 'DU-01'
  p_psl  VARCHAR(20),        -- ej. 'PR-01'
  p_z    NUMERIC DEFAULT 0
  ) RETURNS void LANGUAGE plpgsql AS $$
  DECLARE v_is_logical boolean;
  BEGIN
  -- Dual y Primal deben colgar del mismo theme
  IF NOT EXISTS (
    SELECT 1
    FROM indoorgml_core.dual_space_layer d
    JOIN indoorgml_core.primal_space_layer p ON p.id_theme_layer = d.id_theme_layer
    WHERE d.id_dual = p_dual AND p.id_primal = p_psl
  ) THEN
    RAISE EXCEPTION 'Dual % no corresponde a Primal % (theme mismatch)', p_dual, p_psl;
  END IF;

  SELECT is_logical INTO v_is_logical
  FROM indoorgml_core.dual_space_layer
  WHERE id_dual = p_dual;

  WITH base AS (
    SELECT
      cs.id_cell_space,
      -- id_node determinista a partir del id de la celda
      indoorgml_core.node_id_from_cellspace(cs.id_cell_space) AS new_id_node,
      -- centroide 2D (posible fuera en cóncavas)
      ST_Centroid(cs.geom) AS cen2d,
      cs.geom
    FROM indoorgml_core.cell_space cs
    WHERE cs.id_primal_space_layer = p_psl
  ),
  geom_choice AS (
    SELECT
      b.id_cell_space,
      b.new_id_node,
      CASE
        WHEN v_is_logical THEN NULL::geometry
        WHEN ST_Covers(b.geom, b.cen2d)  -- centroide cae dentro
          THEN ST_Force3D(b.cen2d, p_z)::geometry(PointZ,3857)
        ELSE
          ST_Force3D(ST_PointOnSurface(b.geom), p_z)::geometry(PointZ,3857)
      END AS g
    FROM base b
  )
  INSERT INTO indoorgml_core.node (id_node, id_dual, id_cell_space, geom)
  SELECT gc.new_id_node, p_dual, gc.id_cell_space, gc.g
  FROM geom_choice gc
  ON CONFLICT ON CONSTRAINT uq_node_dual_cell
  DO UPDATE SET
    id_node = EXCLUDED.id_node,    -- asegura nombre ND-#### correcto si cambió
    geom    = EXCLUDED.geom;       -- refresca geom si la celda cambia
  END $$; -- Finalmente reconstruye los nodos de forma automática

-- Validación: si la Dual NO es lógica, el Node (si tiene geom) debe estar dentro de su CellSpace.
CREATE OR REPLACE FUNCTION indoorgml_core.trg_node_inside_when_geom()
  RETURNS trigger LANGUAGE plpgsql AS $$
  DECLARE v_is_logical boolean;
  BEGIN
  SELECT is_logical INTO v_is_logical
  FROM indoorgml_core.dual_space_layer
  WHERE id_dual = NEW.id_dual;

  IF NOT v_is_logical AND NEW.geom IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1
      FROM indoorgml_core.cell_space cs
      WHERE cs.id_cell_space = NEW.id_cell_space
        AND cs.geom IS NOT NULL
        AND ST_Covers(cs.geom, NEW.geom)
    ) THEN
      RAISE EXCEPTION 'Node % debe estar dentro de su CellSpace % (dual=%)',
        NEW.id_node, NEW.id_cell_space, NEW.id_dual;
    END IF;
  END IF;

  RETURN NEW;
  END $$;

---- EDGE --

-- Convierte CB-#### -> EG-####
CREATE OR REPLACE FUNCTION indoorgml_core.edge_id_from_cb(p_cb_id text)
  RETURNS text
  LANGUAGE plpgsql
  IMMUTABLE
  AS $$
  DECLARE num text;
  BEGIN
  SELECT substring(p_cb_id FROM '^CB-(\d+)$') INTO num;
  IF num IS NULL THEN
    RAISE EXCEPTION 'El id_cell_boundary "%" no sigue el patrón CB-<dígitos>', p_cb_id;
  END IF;
  RETURN 'EG-' || num;
  END $$;

-- Reconstruye TODOS los edges para una Dual dada.
-- Regla: 1 Edge por CellBoundary que conecta 2 CellSpaces (si conecta más, se ignora)
CREATE OR REPLACE FUNCTION indoorgml_core.rebuild_edges_from_boundaries(
    p_dual VARCHAR(20),       -- ej. 'DU-01'
    p_z    NUMERIC DEFAULT 0  -- (no se usa aquí, la Z la hereda de los PointsZ)
  ) RETURNS void LANGUAGE plpgsql AS $$
  DECLARE
    v_is_directed boolean;
  BEGIN
  -- Si algún día marcas la capa como dirigida, seguimos creando UN edge por boundary
  -- (orden LEAST/GREATEST); si quieres 2 aristas por boundary, te preparo variante aparte.
  SELECT is_directed INTO v_is_directed
  FROM indoorgml_core.dual_space_layer
  WHERE id_dual = p_dual;

  -- Borrado limpio (solo edges de esa dual)
  DELETE FROM indoorgml_core.edge e WHERE e.id_dual = p_dual;

  WITH b2 AS (
    SELECT cb.id_cell_boundary,
           MIN(cscb.id_cell_space) AS a,
           MAX(cscb.id_cell_space) AS b
    FROM indoorgml_core.cell_boundary cb
    JOIN indoorgml_core.cellspace_cellboundary cscb
      ON cscb.id_cell_boundary = cb.id_cell_boundary
    GROUP BY cb.id_cell_boundary
    HAVING COUNT(*) = 2
  ),
  nn AS (
    SELECT n.id_node, n.id_cell_space, n.geom
    FROM indoorgml_core.node n
    WHERE n.id_dual = p_dual
  ),
  pairs AS (
    SELECT
      b2.id_cell_boundary,
      -- Nodes de las dos celdas
      na.id_node AS nA, nb.id_node AS nB,
      na.geom    AS gA, nb.geom    AS gB
    FROM b2
    JOIN nn na ON na.id_cell_space = b2.a
    JOIN nn nb ON nb.id_cell_space = b2.b
  ),
  ordered AS (
    -- Orden determinista (LEAST/GREATEST por id_node)
    SELECT
      id_cell_boundary,
      LEAST(nA, nB) AS from_node,
      GREATEST(nA, nB) AS to_node,
      CASE WHEN LEAST(nA,nB) = nA THEN gA ELSE gB END AS g_from,
      CASE WHEN LEAST(nA,nB) = nA THEN gB ELSE gA END AS g_to
    FROM pairs
  )
  INSERT INTO indoorgml_core.edge (id_edge, id_dual, from_node, to_node, id_cell_boundary, weight_m, geom)
  SELECT
    indoorgml_core.edge_id_from_cb(o.id_cell_boundary)      AS id_edge,
    p_dual                                                   AS id_dual,
    o.from_node, o.to_node,
    o.id_cell_boundary,
    -- Distancia precisa 2D (XY). Si quisieras 3D: ST_3DDistance(o.g_from, o.g_to)
    ST_Distance(o.g_from, o.g_to)                            AS weight_m,
    ST_MakeLine(o.g_from, o.g_to)::geometry(LineStringZ,3857) AS geom
  FROM ordered o
  -- Si ya existe (mismo id_edge), refrescamos datos por si movieron nodes
  ON CONFLICT (id_edge) DO UPDATE
  SET from_node        = EXCLUDED.from_node,
      to_node          = EXCLUDED.to_node,
      id_dual          = EXCLUDED.id_dual,
      id_cell_boundary = EXCLUDED.id_cell_boundary,
      weight_m         = EXCLUDED.weight_m,
      geom             = EXCLUDED.geom;
  END $$; -- Finalmente reconstruye los edges de forma automática

----------------------------------------------------------
----------------------06 TRIGGERS---------------------
--------------------------------------------------------
-- CELLSPACE --
-- Trigger para evitar solapamientos cundo se inserta o actualiza un CellSpace
CREATE CONSTRAINT TRIGGER ct_cell_space_no_overlap
    AFTER INSERT OR UPDATE OF geom, level -- Despues de una sentencia (update o insert) en geom o level
    ON indoorgml_core.cell_space 
    DEFERRABLE INITIALLY DEFERRED -- Para que valide el conjunto (antigui y nuevo) al final 
    FOR EACH ROW EXECUTE FUNCTION indoorgml_core.fn_cell_space_no_overlap(); -- Ejecuta la funcion para cada fila afectada
-- CELLBOUNDARY --
-- función para reconstruir cell boundaries tras cambios en cell_space
CREATE OR REPLACE FUNCTION indoorgml_core.trg_rebuild_boundaries_after_cs()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_level TEXT;
            v_psl   VARCHAR(20);
    BEGIN
      v_level := COALESCE(NEW.level, OLD.level);
      v_psl   := COALESCE(NEW.id_primal_space_layer, OLD.id_primal_space_layer);
      PERFORM indoorgml_core.rebuild_cell_boundaries(v_level, v_psl);
      RETURN NULL; -- AFTER triggers pueden retornar NULL
    END;
    $$;
-- Trigger para reconstruir cell boundaries tras cambios en cell_space
CREATE TRIGGER trg_rebuild_boundaries_after_cs
    AFTER INSERT OR UPDATE OF geom, level, id_primal_space_layer OR DELETE
    ON indoorgml_core.cell_space
    FOR EACH ROW
    EXECUTE FUNCTION indoorgml_core.trg_rebuild_boundaries_after_cs();

---- NODE --
-- 1) Valida posición del node (centroide o fallback) en INSERT/UPDATE
DROP TRIGGER IF EXISTS node_inside_when_geom ON indoorgml_core.node;
CREATE TRIGGER node_inside_when_geom
  BEFORE INSERT OR UPDATE OF geom, id_cell_space, id_dual
  ON indoorgml_core.node
  FOR EACH ROW
  EXECUTE FUNCTION indoorgml_core.trg_node_inside_when_geom();

-- 2) Auto-rellenar/actualizar NODES tras cambios en CELL_SPACE (por Primal/Theme)
--    (No genera EDGES; eso va en el bloque EDGE con la tabla de membresías)
CREATE OR REPLACE FUNCTION indoorgml_core.trg_rebuild_nodes_after_cs()
  RETURNS trigger LANGUAGE plpgsql AS $$
  DECLARE
  v_psl   VARCHAR(20);
  v_theme VARCHAR(20);
  r_dual  record;
  BEGIN
  -- Evita reentradas
  IF pg_trigger_depth() > 1 THEN
    RETURN NULL;
  END IF;

  v_psl := COALESCE(NEW.id_primal_space_layer, OLD.id_primal_space_layer);

  -- Theme de esa PRIMAL
  SELECT p.id_theme_layer INTO v_theme
  FROM indoorgml_core.primal_space_layer p
  WHERE p.id_primal = v_psl;

  -- Para cada DUAL del mismo theme, reconstruye NODES
  FOR r_dual IN
    SELECT d.id_dual
    FROM indoorgml_core.dual_space_layer d
    WHERE d.id_theme_layer = v_theme
  LOOP
    PERFORM indoorgml_core.rebuild_nodes_for_dual(r_dual.id_dual, v_psl, 0);
  END LOOP;

  RETURN NULL;
  END $$;

DROP TRIGGER IF EXISTS ct_rebuild_nodes_after_cs ON indoorgml_core.cell_space;
CREATE CONSTRAINT TRIGGER ct_rebuild_nodes_after_cs
  AFTER INSERT OR UPDATE OF geom, id_primal_space_layer ON indoorgml_core.cell_space
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW
  EXECUTE FUNCTION indoorgml_core.trg_rebuild_nodes_after_cs();

-- EDGE --
-- 1) Si cambian membresías CellSpace<->CellBoundary (después de recalcular boundaries), rehace EDGES
CREATE OR REPLACE FUNCTION indoorgml_core.trg_rebuild_edges_after_cscb()
  RETURNS trigger LANGUAGE plpgsql AS $$
  DECLARE
  v_cs     varchar(20);
  v_psl    varchar(20);
  v_theme  varchar(20);
  r_dual   record;
  BEGIN
  IF pg_trigger_depth() > 1 THEN
    RETURN NULL;
  END IF;

  v_cs := COALESCE(NEW.id_cell_space, OLD.id_cell_space);

  SELECT id_primal_space_layer INTO v_psl
  FROM indoorgml_core.cell_space
  WHERE id_cell_space = v_cs;

  SELECT p.id_theme_layer INTO v_theme
  FROM indoorgml_core.primal_space_layer p
  WHERE p.id_primal = v_psl;

  FOR r_dual IN
    SELECT d.id_dual
    FROM indoorgml_core.dual_space_layer d
    WHERE d.id_theme_layer = v_theme
  LOOP
    PERFORM indoorgml_core.rebuild_edges_from_boundaries(r_dual.id_dual, 0);
  END LOOP;

  RETURN NULL;
  END $$;

DROP TRIGGER IF EXISTS ct_rebuild_edges_after_cscb ON indoorgml_core.cellspace_cellboundary;
CREATE CONSTRAINT TRIGGER ct_rebuild_edges_after_cscb
  AFTER INSERT OR UPDATE OR DELETE ON indoorgml_core.cellspace_cellboundary
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW
  EXECUTE FUNCTION indoorgml_core.trg_rebuild_edges_after_cscb();

-- 2) (Recomendado) Si se mueven NODES (p.ej., cambió geom de CellSpace), refrescar EDGES
CREATE OR REPLACE FUNCTION indoorgml_core.trg_rebuild_edges_after_node()
  RETURNS trigger LANGUAGE plpgsql AS $$
  BEGIN
  IF pg_trigger_depth() > 1 THEN
    RETURN NULL;
  END IF;
  -- Recalcula todas las edges de la dual del nodo afectado
  PERFORM indoorgml_core.rebuild_edges_from_boundaries(NEW.id_dual, 0);
  RETURN NULL;
  END $$;

DROP TRIGGER IF EXISTS ct_rebuild_edges_after_node ON indoorgml_core.node;
CREATE CONSTRAINT TRIGGER ct_rebuild_edges_after_node
  AFTER INSERT OR UPDATE OF geom, id_cell_space, id_dual ON indoorgml_core.node
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW
  EXECUTE FUNCTION indoorgml_core.trg_rebuild_edges_after_node();

-- NAVIGABLE MODULE --

CREATE OR REPLACE FUNCTION indoorgml_navigation.trg_ns_coherence()
  RETURNS trigger LANGUAGE plpgsql AS $$
  DECLARE 
    v_kind indoorgml_navigation.nav_space_kind;
    v_defl indoorgml_navigation.locomotion_access_type;
  BEGIN
    IF NEW.function_code IS NOT NULL THEN
      SELECT kind, default_locomotion
        INTO v_kind, v_defl
      FROM indoorgml_navigation.nav_space_function
      WHERE code = NEW.function_code;

      IF v_kind IS NULL THEN
        RAISE EXCEPTION 'function_code % no existe en catálogo', NEW.function_code;
      END IF;

      -- Derivar automáticamente
      NEW.kind := v_kind;

      IF v_kind = 'TRANSFER' THEN
        NEW.locomotion := v_defl;           -- auto
      ELSE
        NEW.locomotion := NULL;             -- en GENERAL no aplica
      END IF;
    ELSE
      -- Si no hay function_code y el usuario ha puesto kind a mano:
      IF NEW.kind = 'GENERAL' THEN
        NEW.locomotion := NULL;
      END IF;
    END IF;

    RETURN NEW;
  END $$;

DROP TRIGGER IF EXISTS ns_coherence_biu ON indoorgml_navigation.navigable_space;
CREATE TRIGGER ns_coherence_biu
  BEFORE INSERT OR UPDATE ON indoorgml_navigation.navigable_space
  FOR EACH ROW EXECUTE FUNCTION indoorgml_navigation.trg_ns_coherence();



--------------------------------------------------------
----------------------07 INDICES---------------------
--------------------------------------------------------

-- CELLSPACE --
CREATE INDEX IF NOT EXISTS cell_space_geom_gix ON indoorgml_core.cell_space USING GIST(geom);
CREATE INDEX IF NOT EXISTS cell_space_level_idx ON indoorgml_core.cell_space(level);
-- CELLBOUNDARY --
CREATE INDEX IF NOT EXISTS cell_boundary_geom_gix ON indoorgml_core.cell_boundary USING GIST(geom);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cell_boundary_key   ON indoorgml_core.cell_boundary (boundary_key);

---- NODE --
CREATE UNIQUE INDEX IF NOT EXISTS uq_node_dual_cell ON indoorgml_core.node (id_dual, id_cell_space);
CREATE INDEX IF NOT EXISTS node_geom_gix ON indoorgml_core.node USING GIST (geom);
---- EDGE --
CREATE UNIQUE INDEX IF NOT EXISTS ux_edge_dual_cb ON indoorgml_core.edge (id_dual, id_cell_boundary);
CREATE UNIQUE INDEX IF NOT EXISTS ux_edge_undirected ON indoorgml_core.edge ( id_dual, LEAST(from_node, to_node),  GREATEST(from_node, to_node));
CREATE INDEX IF NOT EXISTS edge_geom_gix ON indoorgml_core.edge USING GIST (geom);
CREATE INDEX IF NOT EXISTS edge_from_idx ON indoorgml_core.edge(from_node);
CREATE INDEX IF NOT EXISTS edge_to_idx   ON indoorgml_core.edge(to_node);
ALTER TABLE indoorgml_core.edge
DROP CONSTRAINT IF EXISTS ck_edge_id_matches_cb;

ALTER TABLE indoorgml_core.edge ADD CONSTRAINT ck_edge_id_matches_cb CHECK (id_edge = indoorgml_core.edge_id_from_cb(id_cell_boundary));

-- NAVIGATION MODULE --
CREATE INDEX IF NOT EXISTS nav_space_kind_idx ON indoorgml_navigation.navigable_space (kind);
CREATE INDEX IF NOT EXISTS cell_space_psl_level_idx ON indoorgml_core.cell_space (id_primal_space_layer, level);