
-- BLOQUE INDOORGML: CORE --

-- CELLSPACE --
CREATE INDEX IF NOT EXISTS cell_space_geom_gix ON indoorgml_core.cell_space USING GIST(geom);
CREATE INDEX IF NOT EXISTS cell_space_level_idx ON indoorgml_core.cell_space(level);

-- CELLBOUNDARY --