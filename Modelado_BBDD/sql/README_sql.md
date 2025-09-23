El objetivo de estos archivos es propircionar una forma facil y modular de crear la base de datos que se utiliza aqui, tal y como esta se puede crear la base de datos de dos formas diferentes:

- Ejecutar archivos uno por uno en orden (00, 01, ..., 07) 
- Copiar en bruto todo el codigo SQL de abajo en una herramienta de consulta y ejecutar.

Todo el Codigo desde ``00_create_database.sql`` hasta ``07_indexes.sql``:

```sql

-------------- Creación de la base de datos si no esta creada --------------

CREATE DATABASE IF NOT EXISTS evac_db;

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
    geom                    GEOMETRY(LineStringZ, 3857),    -- Dato geometrico (1D)

    FOREIGN KEY (id_primal_space_layer) REFERENCES indoorgml_core.primal_space_layer(id_primal), -- FK
)
-- RELACION CELLSPACE-CELLBOUNDARY: BOUNDED BY --

CREATE TABLE indoorgml_core.cellspace_boundedby (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_cell_space VARCHAR(20) NOT NULL, -- atributo FK
    id_cell_boundary VARCHAR(20) NOT NULL, -- atributo FK

    FOREIGN KEY (id_cell_space) REFERENCES indoorgml_core.cell_space(id_cell_space),          -- FK
    FOREIGN KEY (id_cell_boundary) REFERENCES indoorgml_core.cell_boundary(id_cell_boundary), -- FK
)
-------------- BLOQUE INDOORGML: NAVIGATION MODULE --------------


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



--------------------------------------------------------
----------------------07 INDICES---------------------
--------------------------------------------------------

-- CELLSPACE --
CREATE INDEX IF NOT EXISTS cell_space_geom_gix ON indoorgml_core.cell_space USING GIST(geom);
CREATE INDEX IF NOT EXISTS cell_space_level_idx ON indoorgml_core.cell_space(level);

```

Insert de datos de ejemplo:

```sql
-- 
INSERT INTO indoorgml_core.theme_layer (id_theme, semantic_extension, theme)
VALUES ('TH-01', TRUE, 'PHYSICAL');
--SELECT * FROM indoorgml_core.theme_layer; --para comprobar

INSERT INTO indoorgml_core.primal_space_layer (id_primal, srid, id_theme_layer)
VALUES ('PR-01', 3857, 'TH-01');
--SELECT * FROM indoorgml_core.primal_space_layer; --para comprobar

INSERT INTO indoorgml_core.dual_space_layer (id_dual, is_logical, is_directed, srid, id_theme_layer)
VALUES ('DU-01', FALSE, TRUE, 3857, 'TH-01');
--SELECT * FROM indoorgml_core.dual_space_layer; --para comprobar


``` 
