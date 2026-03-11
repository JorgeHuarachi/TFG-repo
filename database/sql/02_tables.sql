-------------- BLOQUE INDOORGML: CORE MODULE --------------

-- THEMATIC LAYER --
CREATE TABLE indoorgml_core.theme_layer (
    id_theme           smallserial PRIMARY KEY,
    code               VARCHAR(50) NOT NULL UNIQUE, -- Por ejemplo: TH-01
    semantic_extension BOOLEAN NOT NULL DEFAULT FALSE, -- Como usamos Navigation sera TRUE
    theme              indoorgml_core.theme_layer_value NOT NULL -- 'PHISICAL' en nuestro caso
);

-- PRIMAL SPACE LAYER --
CREATE TABLE indoorgml_core.primal_space_layer (
    id_primal       smallserial PRIMARY KEY, 
    code            VARCHAR(50) NOT NULL UNIQUE, -- P ej: PR-01
    srid            INTEGER NOT NULL DEFAULT 3857,
    id_theme_layer   SMALLINT NOT NULL, -- FK

    CONSTRAINT primal_theme_layer_fk FOREIGN KEY (id_theme_layer) REFERENCES indoorgml_core.theme_layer(id_theme) ON DELETE CASCADE,
    CONSTRAINT primal_one_per_theme UNIQUE (id_theme_layer) -- Fuerza que sea 1:1
);

-- DUAL SPACE LAYER --
CREATE TABLE indoorgml_core.dual_space_layer (
    id_dual         smallserial PRIMARY KEY,
    code            VARCHAR(50) NOT NULL UNIQUE, -- P ej: DU-01
    is_logical      BOOLEAN NOT NULL DEFAULT FALSE,
    is_directed     BOOLEAN NOT NULL DEFAULT FALSE,
    srid            INTEGER NOT NULL DEFAULT 3857,
    id_theme_layer   SMALLINT NOT NULL, -- FK

    CONSTRAINT dual_theme_layer_fk FOREIGN KEY (id_theme_layer) REFERENCES indoorgml_core.theme_layer(id_theme) ON DELETE CASCADE,
    CONSTRAINT dual_one_per_theme UNIQUE (id_theme_layer) -- Relacion 1:1 es una subclase
);

-------------- BLOQUE INDOORGML: NAVIGATION MODULE --------------