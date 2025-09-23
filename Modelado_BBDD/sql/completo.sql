
-------------- Creación de la base de datos si no esta creada --------------

--CREATE DATABASE IF NOT EXISTS evac_db;

-------------- Extensiones necesarias para trabajar con geometrías --------------

CREATE EXTENSION IF NOT EXISTS postgis;

--------------------------------------------------------
----------------------01 SCHEMAS------------------------
--------------------------------------------------------

-------------- Esquemas necesarios para el modelo IndoorGML --------------

CREATE SCHEMA IF NOT EXISTS indoorgml_core; --HECHO
CREATE SCHEMA IF NOT EXISTS indoorgml_navigation;
--CREATE SCHEMA IF NOT EXISTS monitoring_reading;
--CREATE SCHEMA IF NOT EXISTS safety_events;


-- Enum necesario de momento physical
CREATE TYPE indoorgml_core.theme_layer_value AS ENUM ('PHYSICAL','VIRTUAL','TAGS','UNKNOWN');

--------------------------------------------------------
----------------------02 TABLES------------------------
--------------------------------------------------------


-------------- BLOQUE INDOORGML: CORE [CASI FUNCIONA]--------------

-- THEMATIC LAYER -- [HECHO]

CREATE TABLE indoorgml_core.theme_layer (
    id_theme           VARCHAR(20) PRIMARY KEY, -- p.ej. TH-01, TH-02, ... 
    semantic_extension BOOLEAN NOT NULL DEFAULT FALSE, -- Como usamos Navigation sera TRUE
    theme              indoorgml_core.theme_layer_value NOT NULL -- 'PHYSICAL' en nuestro caso
);

-- PRIMAL SPACE LAYER -- [HECHO]

CREATE TABLE indoorgml_core.primal_space_layer (
    id_primal        VARCHAR(20) PRIMARY KEY,       -- p.ej. PR-01 , PR-02 , ...
    srid             INTEGER NOT NULL DEFAULT 3857,
    id_theme_layer   VARCHAR(20) NOT NULL,          -- atributo FK

    FOREIGN KEY (id_theme_layer) REFERENCES indoorgml_core.theme_layer(id_theme),-- FK
    CONSTRAINT primal_one_per_theme UNIQUE (id_theme_layer) -- Fuerza que sea 1:1
);

-- DUAL SPACE LAYER -- [HECHO]

CREATE TABLE indoorgml_core.dual_space_layer (
    id_dual          VARCHAR(20) PRIMARY KEY,           -- p.ej. DU-01, DU-01, ...
    is_logical       BOOLEAN NOT NULL DEFAULT FALSE,
    is_directed      BOOLEAN NOT NULL DEFAULT FALSE,
    srid             INTEGER NOT NULL DEFAULT 3857,
    id_theme_layer   VARCHAR(20) NOT NULL,              -- atributo FK p.ej. TH-01, TH-02, ...

    FOREIGN KEY (id_theme_layer) REFERENCES indoorgml_core.theme_layer(id_theme), -- FK
    CONSTRAINT dual_one_per_theme UNIQUE (id_theme_layer) -- Relacion 1:1 es una subclase
);

-- CELLSPACE -- [HECHO]

CREATE TABLE indoorgml_core.cell_space(
    id_cell_space           VARCHAR(20) PRIMARY KEY,        -- p.ej. CS-001, CS-001, ...
    name                    TEXT NOT NULL,                  -- p.ej. Room-001, Door-001, ...
    external_reference      TEXT,                           -- De momento creacion propia  
    level                   TEXT,                           -- p.ej. P00, P01, ... 
    poi                     BOOLEAN NOT NULL DEFAULT FALSE, -- (Salida de emergencia)
    id_primal_space_layer   VARCHAR(20) NOT NULL,           -- atributo FK p.ej. PR-01 , PR-02
    geom                    GEOMETRY(PolygonZ, 3857),       -- Dato geometrico (2D + Z)

    FOREIGN KEY (id_primal_space_layer) REFERENCES indoorgml_core.primal_space_layer(id_primal), -- FK
    CONSTRAINT cellspace_geom_valid CHECK (ST_IsValid(geom))
);

-- CELLBOUNDARY --

CREATE TABLE indoorgml_core.cell_boundary(
    id_cell_boundary        VARCHAR(20) PRIMARY KEY,        -- p.ej. CB-001, CB-002, ...
    external_reference      TEXT,                           -- De momento creacion propia  
    is_virtual              BOOLEAN NOT NULL DEFAULT FALSE, -- False porque es real de momnto todo
    id_primal_space_layer   VARCHAR(20) NOT NULL,           -- atributo FK p.ej. PR-01 , PR-02
    geom                    GEOMETRY(MultiLineStringZ, 3857),    -- Dato geometrico (conjunto de 1D)
    boundary_key        TEXT, --   

    FOREIGN KEY (id_primal_space_layer) REFERENCES indoorgml_core.primal_space_layer(id_primal), -- FK
    CONSTRAINT chk_cb_id_format CHECK (id_cell_boundary ~ '^CB-\d{3,}$')
);
-- RELACION CELLSPACE-CELLBOUNDARY: BOUNDED BY --

CREATE TABLE indoorgml_core.cellspace_cellboundary (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    --PRIMARY KEY (id_cell_boundary, id_cell_space), -- PK compuesta
    id_cell_space VARCHAR(20) NOT NULL, -- atributo FK
    id_cell_boundary VARCHAR(20) NOT NULL, -- atributo FK

    FOREIGN KEY (id_cell_space) REFERENCES indoorgml_core.cell_space(id_cell_space),          -- FK
    FOREIGN KEY (id_cell_boundary) REFERENCES indoorgml_core.cell_boundary(id_cell_boundary), -- FK
    CONSTRAINT uq_cs_cb UNIQUE (id_cell_space, id_cell_boundary) -- Evita duplicados
);
-------------- BLOQUE INDOORGML: NAVIGATION MODULE --------------

-- NODE --

CREATE TABLE indoorgml_core.node (
    id_node            VARCHAR(20) PRIMARY KEY, -- p.ej. ND-0001
    id_dual            VARCHAR(20) NOT NULL,   -- atributo FK
    id_cell_space      VARCHAR(20) NOT NULL,    -- atributo FK
    geom               geometry(PointZ, 3857),  -- opcional si is_logical=true

    FOREIGN KEY (id_dual) REFERENCES indoorgml_core.dual_space_layer(id_dual),      -- FK
    FOREIGN KEY (id_cell_space) REFERENCES indoorgml_core.cell_space(id_cell_space), -- FK
    CONSTRAINT uq_node_dual_cell UNIQUE (id_dual, id_cell_space) -- 1:1 entre CellSpace y Node
);

-- EDGE --

CREATE TABLE indoorgml_core.edge (
    id_edge            VARCHAR(20) PRIMARY KEY, -- p.ej. EG-0001
    weight_m           DOUBLE PRECISION,        -- opcional
    id_dual            VARCHAR(20) NOT NULL,    -- atributo FK
    id_cell_boundary   VARCHAR(20) NULL,        -- atributo FK
    from_node          VARCHAR(20) NOT NULL,    -- atributos FK
    to_node            VARCHAR(20) NOT NULL,    -- atributos FK
    geom               geometry(LineStringZ, 3857), -- opcional si is_logical=true
    
    FOREIGN KEY (id_dual)          REFERENCES indoorgml_core.dual_space_layer(id_dual), -- FK
    FOREIGN KEY (id_cell_boundary) REFERENCES indoorgml_core.cell_boundary(id_cell_boundary), -- FK
    FOREIGN KEY (from_node)        REFERENCES indoorgml_core.node(id_node),           -- FK
    FOREIGN KEY (to_node)          REFERENCES indoorgml_core.node(id_node),             -- FK
    CONSTRAINT ck_edge_from_to_diff CHECK (from_node <> to_node)
);


--------------------------------------------------------
----------------------03 RELACIONES---------------------
--------------------------------------------------------





--------------------------------------------------------
-----------------------04 VIEWS-------------------------
--------------------------------------------------------


--------------------------------------------------------
----------------------05 FUNCTIONS----------------------
--------------------------------------------------------

--- BLOQUE INDOORGML: CORE --------------

-- CELLSPACE --

CREATE OR REPLACE FUNCTION indoorgml_core.fn_cell_space_no_overlap()
    RETURNS TRIGGER 
    LANGUAGE plpgsql
    AS $$
    
    DECLARE 
        v_conflict_id TEXT; --guarda el id del cellspace que genera el conflicto
    
    BEGIN
        IF NEW.geom IS NULL OR NEW.level IS NULL THEN
            RETURN NEW; -- Si la geometría o el nivel es NULL, no hacemos nada
        END IF; 
        
        -- Buscar conflictos en cell_space 
        SELECT cs.id_cell_space INTO v_conflict_id FROM indoorgml_core.cell_space cs
    
        WHERE cs.level = NEW.level -- Mismo nivel
            AND cs.id_cell_space <> NEW.id_cell_space -- No comparar con sí mismo
            AND cs.geom && NEW.geom  -- filtro espacial rápido (bounding box)
            -- logica principal
            AND (
                ST_Relate(cs.geom, NEW.geom, '2********')            -- solape de área (2D)
            )
        LIMIT 1; -- Solo necesitamos saber si hay al menos un conflicto para bloquear la inserción/actualizaciónla operación
        
        -- Excepcion si hay conflicto
        IF v_conflict_id IS NOT NULL THEN
            RAISE EXCEPTION 'CellSpace % (level=%) entra en conflicto con % (punto o área compartida no permitidos)',NEW.id_cell_space, NEW.level, v_conflict_id
            USING HINT = 'Solo se permite no contacto o contacto por borde (1D).';
        END IF;
    RETURN NEW; -- Si no hay conflictos, permitir la operación
    END;
    $$;

-- CELLBOUNDARY --

CREATE SEQUENCE IF NOT EXISTS indoorgml_core.seq_cell_boundary START 1;

    CREATE OR REPLACE FUNCTION indoorgml_core.next_cb_id()
    RETURNS varchar LANGUAGE plpgsql AS $$
    DECLARE 
        n bigint;
    BEGIN
      n := nextval('indoorgml_core.seq_cell_boundary');
      RETURN 'CB-' || lpad(n::text, 4, '0');
    END;
    $$;

CREATE OR REPLACE FUNCTION indoorgml_core.rebuild_cell_boundaries(  
      p_level TEXT DEFAULT NULL,                -- planta; NULL = todas
      p_psl   VARCHAR(20) DEFAULT NULL,         -- primal; NULL = todas
      p_z     NUMERIC DEFAULT 0                 -- Z de salida
    )
    RETURNS void
    LANGUAGE plpgsql
    AS $$
    DECLARE
      tol DOUBLE PRECISION := 0.001; -- tolerancia Snap/SnapToGrid (unidades del CRS)
    BEGIN
      --------------------------------------------------------------------
      -- 0) Limpiar SOLO membresías del ámbito afectado
      --------------------------------------------------------------------
      DELETE FROM indoorgml_core.cellspace_cellboundary cscb
      USING indoorgml_core.cell_space cs
      WHERE cscb.id_cell_space = cs.id_cell_space
        AND (p_level IS NULL OR cs.level = p_level)
        AND (p_psl   IS NULL OR cs.id_primal_space_layer = p_psl);
    
      -- Nota: NO borramos cell_boundary aquí; se borran huérfanos al final
    
      --------------------------------------------------------------------
      -- 1) BORDES INTERNOS (tramos compartidos entre pares de celdas)
      --------------------------------------------------------------------
      DROP TABLE IF EXISTS tmp_shared_lines;
      CREATE TEMP TABLE tmp_shared_lines(
        ida varchar(20),
        idb varchar(20),
        geom2d geometry(MultiLineString, 3857)
      ) ON COMMIT DROP;
    
      INSERT INTO tmp_shared_lines(ida, idb, geom2d)
      SELECT a.id_cell_space, b.id_cell_space,
             ST_LineMerge(
               ST_CollectionExtract(
                 ST_Intersection(ST_Force2D(a.geom), ST_Force2D(b.geom)), 2
               )
             ) AS shared
      FROM indoorgml_core.cell_space a
      JOIN indoorgml_core.cell_space b
        ON a.id_cell_space < b.id_cell_space
       AND a.level = b.level
       AND a.id_primal_space_layer = b.id_primal_space_layer
       AND (p_level IS NULL OR a.level = p_level)
       AND (p_psl   IS NULL OR a.id_primal_space_layer = p_psl)
       AND a.geom && b.geom
       AND ST_Relate(a.geom, b.geom, 'F***1****')
      WHERE NOT ST_IsEmpty(a.geom) AND NOT ST_IsEmpty(b.geom);
    
      -- Mapa boundary_key -> id_cell_boundary (para membresías)
      DROP TABLE IF EXISTS tmp_cb_map;
      CREATE TEMP TABLE tmp_cb_map(
        boundary_key TEXT PRIMARY KEY,
        id_cell_boundary VARCHAR(20)
      ) ON COMMIT DROP;
    
      -- Candidatos internos persistentes
      DROP TABLE IF EXISTS tmp_cand_int;
      CREATE TEMP TABLE tmp_cand_int(
        boundary_key TEXT PRIMARY KEY,
        psl          VARCHAR(20),
        geomz        geometry(MultiLineStringZ,3857),
        ida          VARCHAR(20),
        idb          VARCHAR(20)
      ) ON COMMIT DROP;
    
      INSERT INTO tmp_cand_int(boundary_key, psl, geomz, ida, idb)
      SELECT
        md5(ST_AsBinary(ST_SnapToGrid(ST_LineMerge(ST_Force2D(g2)), tol))) AS boundary_key,
        (SELECT cs.id_primal_space_layer
           FROM indoorgml_core.cell_space cs
          WHERE cs.id_cell_space = u.ida
          LIMIT 1)                                                       AS psl,
        ST_Multi(ST_Force3D(u.g2, p_z))::geometry(MultiLineStringZ,3857) AS geomz,
        u.ida, u.idb
      FROM (
        WITH dumped AS (
          SELECT ida, idb, (ST_Dump(geom2d)).geom AS g
          FROM tmp_shared_lines
          WHERE geom2d IS NOT NULL AND NOT ST_IsEmpty(geom2d)
        ),
        norm AS (
          SELECT ida, idb, ST_SnapToGrid(ST_Force2D(g), tol) AS g2
          FROM dumped
          WHERE GeometryType(g) IN ('LINESTRING','MULTILINESTRING')
            AND ST_NPoints(g) >= 2
        ),
        uniq AS (
          SELECT DISTINCT ON (md5(ST_AsBinary(g2))) g2, MIN(ida) AS ida, MIN(idb) AS idb
          FROM norm
          GROUP BY g2
        )
        SELECT * FROM uniq
      ) u;
    
      -- *** SOLUCIÓN MÍNIMA: UPDATE + INSERT-solo-nuevos (no gasta secuencia en existentes) ***
    
      -- 1.A) Actualiza límites internos existentes (por boundary_key)
      UPDATE indoorgml_core.cell_boundary cb
      SET id_primal_space_layer = c.psl,
          geom                  = c.geomz
      FROM tmp_cand_int c
      WHERE cb.boundary_key = c.boundary_key;
    
      -- 1.B) Inserta SOLO límites internos nuevos
      INSERT INTO indoorgml_core.cell_boundary
        (id_cell_boundary, external_reference, is_virtual, id_primal_space_layer, geom, boundary_key)
      SELECT indoorgml_core.next_cb_id(), NULL, FALSE, c.psl, c.geomz, c.boundary_key
      FROM tmp_cand_int c
      LEFT JOIN indoorgml_core.cell_boundary cb USING(boundary_key)
      WHERE cb.boundary_key IS NULL;
    
      -- 1.C) Refresca el mapa (clave -> ID)
      DELETE FROM tmp_cb_map;
      INSERT INTO tmp_cb_map(boundary_key, id_cell_boundary)
      SELECT c.boundary_key, cb.id_cell_boundary
      FROM tmp_cand_int c
      JOIN indoorgml_core.cell_boundary cb USING(boundary_key);
    
      -- Membresías internos (dos filas por boundary)
      INSERT INTO indoorgml_core.cellspace_cellboundary(id_cell_boundary, id_cell_space)
      SELECT m.id_cell_boundary, c.ida
      FROM tmp_cand_int c
      JOIN tmp_cb_map m USING(boundary_key);
    
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
      );
    
    END;
    $$;




---- NODE --
--
--CREATE SEQUENCE IF NOT EXISTS indoorgml_core.seq_node START 1;
--
--CREATE OR REPLACE FUNCTION indoorgml_core.next_nd_id()
--    RETURNS varchar LANGUAGE plpgsql AS $$
--    DECLARE n bigint;
--    BEGIN
--      n := nextval('indoorgml_core.seq_node');
--      RETURN 'ND-' || lpad(n::text, 4, '0');
--    END $$;
--
--CREATE OR REPLACE FUNCTION indoorgml_core.rebuild_nodes_for_dual(
--      p_dual_layer VARCHAR(20),   -- ej. 'DU-01'
--      p_psl        VARCHAR(20),   -- ej. 'PR-01'
--      p_z          NUMERIC DEFAULT 0
--    ) RETURNS void LANGUAGE plpgsql AS $$
--    DECLARE v_is_logical boolean;
--    BEGIN
--      -- Comprueba que DUAL y PRIMAL cuelgan del mismo THEME
--      IF NOT EXISTS (
--        SELECT 1
--        FROM indoorgml_core.dual_space_layer d
--        JOIN indoorgml_core.primal_space_layer p ON p.id_theme_layer = d.id_theme_layer
--        WHERE d.id_dual = p_dual_layer AND p.id_primal = p_psl
--      ) THEN
--        RAISE EXCEPTION 'La Dual % no corresponde a la Primal % (theme mismatch)', p_dual_layer, p_psl;
--      END IF;
--
--      SELECT is_logical INTO v_is_logical
--      FROM indoorgml_core.dual_space_layer
--      WHERE id_dual = p_dual_layer;
--
--      -- Inserta los nodes faltantes (1:1 por cell_space dentro de esa PRIMAL)
--      INSERT INTO indoorgml_core.node (id_node, id_dual_layer, id_cell_space, geom)
--      SELECT indoorgml_core.next_nd_id(),
--             p_dual_layer,
--             cs.id_cell_space,
--             CASE WHEN v_is_logical
--                  THEN NULL
--                  ELSE ST_Force3D(ST_PointOnSurface(cs.geom), p_z)::geometry(PointZ,3857)
--              END
--      FROM indoorgml_core.cell_space cs
--      LEFT JOIN indoorgml_core.node n
--             ON n.id_dual_layer = p_dual_layer
--            AND n.id_cell_space = cs.id_cell_space
--      WHERE cs.id_primal_space_layer = p_psl
--        AND n.id_node IS NULL;
--    END $$;
--
--CREATE OR REPLACE FUNCTION indoorgml_core.trg_node_inside_when_geom()
--    RETURNS trigger LANGUAGE plpgsql AS $$
--    DECLARE v_is_logical boolean;
--    BEGIN
--      SELECT is_logical INTO v_is_logical
--      FROM indoorgml_core.dual_space_layer
--      WHERE id_dual = NEW.id_dual_layer;
--
--      IF NOT v_is_logical THEN
--        IF NEW.geom IS NOT NULL THEN
--          IF NOT EXISTS (
--            SELECT 1
--            FROM indoorgml_core.cell_space cs
--            WHERE cs.id_cell_space = NEW.id_cell_space
--              AND cs.geom IS NOT NULL
--              AND ST_Covers(cs.geom, NEW.geom)
--          ) THEN
--            RAISE EXCEPTION 'Node % debe estar dentro de su CellSpace % en dual %',
--              NEW.id_node, NEW.id_cell_space, NEW.id_dual_layer;
--          END IF;
--        END IF;
--      END IF;
--
--      RETURN NEW;
--    END $$;
--
---- EDGE --
--
--CREATE SEQUENCE IF NOT EXISTS indoorgml_core.seq_edge START 1;
--
--CREATE OR REPLACE FUNCTION indoorgml_core.next_eg_id()
--    RETURNS varchar LANGUAGE plpgsql AS $$
--    DECLARE n bigint;
--    BEGIN
--      n := nextval('indoorgml_core.seq_edge');
--      RETURN 'EG-' || lpad(n::text, 4, '0');
--    END $$;
--
--CREATE OR REPLACE FUNCTION indoorgml_core.rebuild_edges_from_boundaries(
--      p_dual_layer VARCHAR(20),
--      p_z          NUMERIC DEFAULT 0
--    ) RETURNS void LANGUAGE plpgsql AS $$
--    DECLARE v_is_directed boolean;
--    DECLARE v_is_logical  boolean;
--    BEGIN
--      SELECT is_directed, is_logical INTO v_is_directed, v_is_logical
--      FROM indoorgml_core.dual_space_layer
--      WHERE id_dual = p_dual_layer;
--
--      -- Borrado limpio (solo la dual afectada)
--      DELETE FROM indoorgml_core.edge e WHERE e.id_dual_layer = p_dual_layer;
--
--      WITH b2 AS (
--        SELECT id_cell_boundary,
--               MIN(id_cell_space) AS a,
--               MAX(id_cell_space) AS b
--        FROM indoorgml_core.cellspace_cellboundary
--        GROUP BY id_cell_boundary
--        HAVING COUNT(*) = 2
--      ),
--      nn AS (
--        SELECT n.id_node, n.id_cell_space
--        FROM indoorgml_core.node n
--        WHERE n.id_dual_layer = p_dual_layer
--      ),
--      pairs AS (
--        SELECT b2.id_cell_boundary, na.id_node AS nA, nb.id_node AS nB
--        FROM b2
--        JOIN nn na ON na.id_cell_space = b2.a
--        JOIN nn nb ON nb.id_cell_space = b2.b
--      )
--      INSERT INTO indoorgml_core.edge (id_edge, id_dual_layer, from_node, to_node, id_cell_boundary, weight_m, geom)
--      SELECT indoorgml_core.next_eg_id(),
--             p_dual_layer,
--             p.nA, p.nB,
--             p.id_cell_boundary,
--             NULL,
--             CASE WHEN v_is_logical THEN NULL
--                  ELSE (
--                    SELECT ST_Force3D(ST_ShortestLine(n1.geom, n2.geom), p_z)::geometry(LineStringZ,3857)
--                    FROM indoorgml_core.node n1, indoorgml_core.node n2
--                    WHERE n1.id_node = p.nA AND n2.id_node = p.nB
--                  )
--              END
--      FROM pairs p;
--
--      IF v_is_directed THEN
--        INSERT INTO indoorgml_core.edge (id_edge, id_dual_layer, from_node, to_node, id_cell_boundary, weight_m, geom)
--        SELECT indoorgml_core.next_eg_id(),
--               p_dual_layer,
--               p.nB, p.nA,
--               p.id_cell_boundary,
--               NULL,
--               CASE WHEN v_is_logical THEN NULL
--                    ELSE (
--                      SELECT ST_Force3D(ST_ShortestLine(n2.geom, n1.geom), p_z)::geometry(LineStringZ,3857)
--                      FROM indoorgml_core.node n1, indoorgml_core.node n2
--                      WHERE n1.id_node = p.nA AND n2.id_node = p.nB
--                    )
--                END
--        FROM pairs p;
--      END IF;
--    END $$;
--
--CREATE OR REPLACE FUNCTION indoorgml_core.trg_rebuild_all_after_cs()
--    RETURNS trigger LANGUAGE plpgsql AS $$
--    DECLARE
--      v_level  TEXT;
--      v_psl    VARCHAR(20);
--      v_theme  VARCHAR(20);
--      r_dual   record;
--    BEGIN
--      IF pg_trigger_depth() > 1 THEN
--        RETURN NULL;
--      END IF;
--
--      v_level := COALESCE(NEW.level, OLD.level);
--      v_psl   := COALESCE(NEW.id_primal_space_layer, OLD.id_primal_space_layer);
--
--      -- 1) Rebuild boundaries (tuyo)
--      PERFORM indoorgml_core.rebuild_cell_boundaries(v_level, v_psl, 0);
--
--      -- 2) Theme de esa PRIMAL
--      SELECT p.id_theme_layer INTO v_theme
--      FROM indoorgml_core.primal_space_layer p
--      WHERE p.id_primal = v_psl;
--
--      -- 3) Por cada DUAL del theme: NODES -> EDGES
--      FOR r_dual IN
--        SELECT d.id_dual
--        FROM indoorgml_core.dual_space_layer d
--        WHERE d.id_theme_layer = v_theme
--      LOOP
--        PERFORM indoorgml_core.rebuild_nodes_for_dual(r_dual.id_dual, v_psl, 0);
--        PERFORM indoorgml_core.rebuild_edges_from_boundaries(r_dual.id_dual, 0);
--      END LOOP;
--
--      RETURN NULL;
--    END $$;
--
----------------------------------------------------------
----------------------06 TRIGGERS---------------------
--------------------------------------------------------
-- CELLSPACE --
-- Trigger para evitar solapamientos 
CREATE CONSTRAINT TRIGGER ct_cell_space_no_overlap
    AFTER INSERT OR UPDATE OF geom, level -- Despues de una sentencia (update o insert) en geom o level
    ON indoorgml_core.cell_space 
    DEFERRABLE INITIALLY DEFERRED -- Para que valide el conjunto (antigui y nuevo) al final 
    FOR EACH ROW EXECUTE FUNCTION indoorgml_core.fn_cell_space_no_overlap(); -- Ejecuta la funcion para cada fila afectada
-- CELLBOUNDARY --
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

CREATE TRIGGER trg_rebuild_boundaries_after_cs
    AFTER INSERT OR UPDATE OF geom, level, id_primal_space_layer OR DELETE
    ON indoorgml_core.cell_space
    FOR EACH ROW
    EXECUTE FUNCTION indoorgml_core.trg_rebuild_boundaries_after_cs();

---- NODE --
--
--DROP TRIGGER IF EXISTS node_inside_when_geom ON indoorgml_core.node;
--CREATE TRIGGER node_inside_when_geom
--    BEFORE INSERT OR UPDATE OF geom, id_cell_space, id_dual_layer
--    ON indoorgml_core.node
--    FOR EACH ROW
--    EXECUTE FUNCTION indoorgml_core.trg_node_inside_when_geom();
--
---- EGDE --
--
--DROP TRIGGER IF EXISTS ct_rebuild_all_after_cs ON indoorgml_core.cell_space;
--CREATE CONSTRAINT TRIGGER ct_rebuild_all_after_cs
--    AFTER INSERT OR UPDATE OR DELETE ON indoorgml_core.cell_space
--    DEFERRABLE INITIALLY DEFERRED
--    FOR EACH ROW
--    EXECUTE FUNCTION indoorgml_core.trg_rebuild_all_after_cs();

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
--CREATE UNIQUE INDEX IF NOT EXISTS uq_node_dual_cell ON indoorgml_core.node (id_dual_layer, id_cell_space);
--CREATE INDEX IF NOT EXISTS node_geom_gix ON indoorgml_core.node USING GIST (geom);
--
---- EDGE --
--CREATE INDEX IF NOT EXISTS edge_geom_gix ON indoorgml_core.edge USING GIST (geom);
--CREATE INDEX IF NOT EXISTS edge_from_idx ON indoorgml_core.edge(from_node);
--CREATE INDEX IF NOT EXISTS edge_to_idx   ON indoorgml_core.edge(to_node);
--CREATE UNIQUE INDEX IF NOT EXISTS ux_edge_undirected ON indoorgml_core.edge ( id_dual, LEAST(from_node, to_node),  GREATEST(from_node, to_node)) -- Evita duplicados en edges no dirigidos

