-------------- BLOQUE INDOORGML: CORE [FUNCIONA]--------------

INSERT INTO indoorgml_core.theme_layer (id_theme, semantic_extension, theme)
VALUES ('TH-01', TRUE, 'PHYSICAL');
--SELECT * FROM indoorgml_core.theme_layer; --para comprobar

INSERT INTO indoorgml_core.primal_space_layer (id_primal, srid, id_theme_layer)
VALUES ('PR-01', 3857, 'TH-01');
--SELECT * FROM indoorgml_core.primal_space_layer; --para comprobar

INSERT INTO indoorgml_core.dual_space_layer (id_dual, is_logical, is_directed, srid, id_theme_layer)
VALUES ('DU-01', FALSE, FALSE, 3857, 'TH-01');
--SELECT * FROM indoorgml_core.dual_space_layer; --para comprobar

