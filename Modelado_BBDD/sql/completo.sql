
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
    FOREIGN KEY (id_cell_boundary) REFERENCES indoorgml_core.cell_boundary(id_cell_boundary) -- FK
);
-------------- BLOQUE INDOORGML: NAVIGATION MODULE --------------

-- NODE --

CREATE TABLE indoorgml_core.node (
    id_node            VARCHAR(20) PRIMARY KEY, -- p.ej. ND-0001
    id_dual             VARCHAR(20) NOT NULL,   -- atributo FK
    id_cell_space      VARCHAR(20) NOT NULL,    -- atributo FK
    geom               geometry(PointZ, 3857),  -- opcional si is_logical=true
  
    FOREIGN KEY (id_dual) REFERENCES indoorgml_core.dual_space_layer(id_dual),      -- FK
    FOREIGN KEY (id_cell_space) REFERENCES indoorgml_core.cell_space(id_cell_space) -- FK
    
    CONSTRAINT uq_node_dual_cell UNIQUE (id_dual_layer, id_cell_space) -- Garantizamos mapeo 1:1 (por capa dual) entre CellSpace y Node
);

-- EDGE --

CREATE TABLE indoorgml_core.edge (
    id_edge            VARCHAR(20) PRIMARY KEY, -- p.ej. EG-0001
    weight_m           DOUBLE PRECISION,        -- opcional
    from_node          VARCHAR(20) NOT NULL,    -- atributos FK
    to_node            VARCHAR(20) NOT NULL,    -- atributos FK
    id_dual            VARCHAR(20) NOT NULL,    -- atributo FK
    id_cell_boundary   VARCHAR(20) NULL,        -- atributo FK
    geom               geometry(LineStringZ, 3857), -- opcional si is_logical=true
    
    FOREIGN KEY (id_dual) REFERENCES indoorgml_core.dual_space_layer(id_dual), -- FK
    FOREIGN KEY (from_node) REFERENCES indoorgml_core.node(id_node),           -- FK
    FOREIGN KEY (to_node) REFERENCES indoorgml_core.node(id_node),             -- FK
    FOREIGN KEY (id_cell_boundary) REFERENCES indoorgml_core.cell_boundary(id_cell_boundary), -- FK
    
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
          p_level TEXT DEFAULT NULL,                -- limita a una planta; NULL = todas
          p_psl   VARCHAR(20) DEFAULT NULL,         -- limita a una primal layer; NULL = todas
          p_z     NUMERIC DEFAULT 0                 -- Z de salida (LineStringZ)
        )
        RETURNS void
        LANGUAGE plpgsql
    AS $$
    DECLARE
      tol DOUBLE PRECISION := 0.001; -- tolerancia para SnapToGrid (m) para deduplicar
    BEGIN
        PERFORM setval('indoorgml_core.seq_cell_boundary', 1, false);
        -- 1) Borrar boundaries/membresías SOLO de lo que vamos a recalcular
        DELETE FROM indoorgml_core.cellspace_cellboundary cscb --cambiar nombre tabla
        USING indoorgml_core.cell_space cs
        WHERE cscb.id_cell_space = cs.id_cell_space
          AND (p_level IS NULL OR cs.level = p_level)
          AND (p_psl   IS NULL OR cs.id_primal_space_layer = p_psl);
        DELETE FROM indoorgml_core.cell_boundary cb
        WHERE NOT EXISTS (
          SELECT 1 FROM indoorgml_core.cellspace_cellboundary m
          WHERE m.id_cell_boundary = cb.id_cell_boundary
        );
        -- 2) Calcular líneas compartidas (boundaries internos) entre pares de celdas
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
         AND ST_Relate(a.geom, b.geom, 'F***1****')  -- contacto 1D (borde)
        WHERE NOT ST_IsEmpty(a.geom) AND NOT ST_IsEmpty(b.geom);

        -- 3) Insertar boundaries internos (segmentos únicos) + membresías (2 celdas)
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
        INSERT INTO indoorgml_core.cell_boundary(id_cell_boundary, external_reference, is_virtual, id_primal_space_layer, geom)
        SELECT indoorgml_core.next_cb_id(),
               NULL, FALSE,
               (SELECT cs.id_primal_space_layer FROM indoorgml_core.cell_space cs WHERE cs.id_cell_space = u.ida LIMIT 1),
               ST_Force3D(u.g2, p_z)::geometry(LineStringZ, 3857)
        FROM uniq u;

        -- membresías (dos filas por boundary interno)
        INSERT INTO indoorgml_core.cellspace_cellboundary(id_cell_boundary, id_cell_space)
        SELECT cb.id_cell_boundary, u.ida
        FROM (
          SELECT DISTINCT ON (md5(ST_AsBinary(g2))) g2, ida, idb
          FROM (
            SELECT ida, idb, ST_SnapToGrid(ST_Force2D((ST_Dump(geom2d)).geom), tol) AS g2
            FROM tmp_shared_lines
            WHERE geom2d IS NOT NULL
          ) q
        ) u
        JOIN indoorgml_core.cell_boundary cb
          ON ST_Equals(cb.geom, ST_Force3D(u.g2, p_z));

        INSERT INTO indoorgml_core.cellspace_cellboundary(id_cell_boundary, id_cell_space)
        SELECT cb.id_cell_boundary, u.idb
        FROM (
          SELECT DISTINCT ON (md5(ST_AsBinary(g2))) g2, ida, idb
          FROM (
            SELECT ida, idb, ST_SnapToGrid(ST_Force2D((ST_Dump(geom2d)).geom), tol) AS g2
            FROM tmp_shared_lines
            WHERE geom2d IS NOT NULL
          ) q
        ) u
        JOIN indoorgml_core.cell_boundary cb
          ON ST_Equals(cb.geom, ST_Force3D(u.g2, p_z));

        -- 4) Contorno exterior (boundaries con 1 sola celda)
        DROP TABLE IF EXISTS tmp_shared_by_cell;
        CREATE TEMP TABLE tmp_shared_by_cell(
          id_cell_space varchar(20),
          geom2d geometry(MultiLineString, 3857)
        ) ON COMMIT DROP;

        INSERT INTO tmp_shared_by_cell(id_cell_space, geom2d)
        SELECT ida, ST_Union(geom2d) FROM tmp_shared_lines GROUP BY ida
        UNION ALL
        SELECT idb, ST_Union(geom2d) FROM tmp_shared_lines GROUP BY idb;

        -- 1. Crear la tabla temporal tmp_uniq2 con un único contorno exterior por celda
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
          -- Unir todos los segmentos exteriores de cada celda
          SELECT id_cell_space, psl,
                 ST_LineMerge(ST_Union(g)) AS g_merged
          FROM diff
          WHERE g IS NOT NULL AND NOT ST_IsEmpty(g)
          GROUP BY id_cell_space, psl
        ),
        norm AS (
          SELECT id_cell_space, psl,
                 ST_SnapToGrid(g_merged, tol) AS g2
          FROM merged
          WHERE GeometryType(g_merged) IN ('LINESTRING','MULTILINESTRING')
            AND ST_Length(g_merged) > 0
        )
        SELECT id_cell_space, psl, g2
        FROM norm;

        -- 2. Insertar boundaries exteriores (una sola celda)
        INSERT INTO indoorgml_core.cell_boundary(
            id_cell_boundary, external_reference, is_virtual, id_primal_space_layer, geom
        )
        SELECT indoorgml_core.next_cb_id(), NULL, FALSE, psl,
               ST_Force3D(g2, p_z)::geometry(MultiLineStringZ, 3857)
        FROM tmp_uniq2;

        -- 3. Insertar membresías para boundaries exteriores (una fila por boundary)
        INSERT INTO indoorgml_core.cellspace_cellboundary(id_cell_boundary, id_cell_space)
        SELECT cb.id_cell_boundary, u.id_cell_space
        FROM tmp_uniq2 u
        JOIN indoorgml_core.cell_boundary cb
          ON ST_Equals(cb.geom, ST_Force3D(u.g2, p_z));

        END;
        $$;




--------------------------------------------------------
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


--------------------------------------------------------
----------------------07 INDICES---------------------
--------------------------------------------------------

-- CELLSPACE --
CREATE INDEX IF NOT EXISTS cell_space_geom_gix ON indoorgml_core.cell_space USING GIST(geom);
CREATE INDEX IF NOT EXISTS cell_space_level_idx ON indoorgml_core.cell_space(level);
-- CELLBOUNDARY --
CREATE INDEX IF NOT EXISTS cell_boundary_geom_gix ON indoorgml_core.cell_boundary USING GIST(geom);
