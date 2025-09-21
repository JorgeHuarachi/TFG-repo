El objetivo de estos archivos es propircionar una forma facil y modular de crear la base de datos que se utiliza aqui, tal y como esta se puede crear la base de datos de dos formas diferentes:

- Ejecutar archivos uno por uno en orden (00, 01, ..., 07) 
- Copiar en bruto todo el codigo SQL de abajo en una herramienta de consulta y ejecutar.

Todo el Codigo desde ``00_create_database.sql`` hasta ``07_indexes.sql``:

```sql

-- Creación de la base de datos si no esta creada
CREATE DATABASE IF NOT EXISTS indoor_evac_monitoring_db;

-- Extensiones necesarias para trabajar con geometrías
CREATE EXTENSION IF NOT EXISTS postgis;

-- Esquemas necesarios para el modelo IndoorGML
CREATE SCHEMA IF NOT EXISTS indoorgml_core;
CREATE SCHEMA IF NOT EXISTS indoorgml_navigation;

-- Enum necesario de momento solo uno (para el tema de las capas)
CREATE TYPE indoorgml_core.theme_layer_value AS ENUM ('PHYSICAL','VIRTUAL','TAGS','UNKNOWN');

-- BLOQUE INDOORGML: CORE --

-- THEMATIC LAYER
CREATE TABLE indoorgml_core.theme_layer (
    id_theme           smallserial PRIMARY KEY,
    code               VARCHAR(50) NOT NULL UNIQUE, -- Por ejemplo: TH-01
    semantic_extension BOOLEAN NOT NULL DEFAULT FALSE, -- Como usamos Navigation sera TRUE
    theme              indoorgml_core.theme_layer_value NOT NULL -- 'PHISICAL' en nuestro caso
);

-- PRIMAL SPACE LAYER
CREATE TABLE indoorgml_core.primal_space_layer (
    id_primal        smallserial PRIMARY KEY, 
    code             VARCHAR(50) NOT NULL UNIQUE, -- P ej: PR-01
    srid             INTEGER NOT NULL DEFAULT 3857,
    id_theme_layer   SMALLINT NOT NULL, -- FK

    CONSTRAINT primal_theme_layer_fk FOREIGN KEY (id_theme_layer) REFERENCES indoorgml_core.theme_layer(id_theme) ON DELETE CASCADE,
    CONSTRAINT primal_one_per_theme UNIQUE (id_theme_layer) -- Fuerza que sea 1:1
);

-- DUAL SPACE LAYER
CREATE TABLE indoorgml_core.dual_space_layer (
    id_dual          smallserial PRIMARY KEY,
    code             VARCHAR(50) NOT NULL UNIQUE, -- P ej: DU-01
    is_logical       BOOLEAN NOT NULL DEFAULT FALSE,
    is_directed      BOOLEAN NOT NULL DEFAULT FALSE,
    srid             INTEGER NOT NULL DEFAULT 3857,
    id_theme_layer   SMALLINT NOT NULL, -- FK

    CONSTRAINT dual_theme_layer_fk FOREIGN KEY (id_theme_layer) REFERENCES indoorgml_core.theme_layer(id_theme) ON DELETE CASCADE,
    CONSTRAINT dual_one_per_theme UNIQUE (id_theme_layer) -- Relacion 1:1 es una subclase
);

-------------- BLOQUE INDOORGML: NAVIGATION MODULE --------------

-- CELLSPACE --

CREATE TABLE indoorgml_core.cell_space(
    id_cell_space           SERIAL PRIMARY KEY,
    name                    TEXT NOT NULL,             
    code                    VARCHAR(50) NOT NULL UNIQUE,    -- p.ej. CS-001
    geom                    GEOMETRY(PolygonZ, 3857), -- Dato geometrico con coordenada Z
    external_reference      TEXT,  
    level                   TEXT, -- Planta del edificio
    poi                     BOOLEAN NOT NULL DEFAULT FALSE, -- Punto de interes
    id_primal_space_layer   SMALLINT NOT NULL, --FK

    CONSTRAINT cell_primal_space_layer_fk FOREIGN KEY (id_primal_space_layer) REFERENCES indoorgml_core.primal_space_layer(id_primal) ON DELETE CASCADE
    CONSTRAINT cellspace_no_overlap EXCLUDE USING gist (cellspace_geom WITH &&) -- Evita los solapes, se puede ignorar solapes en distinta planta
)


```