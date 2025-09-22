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
--------------------------------------------------------
-- Sala A (izquierda-abajo)
INSERT INTO indoorgml_core.cell_space
(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
VALUES ('CS-001', 'Room-A', 'Room-A', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((0 0 0, 9 0 0, 9 10 0, 0 10 0, 0 0 0))', 3857)
);

-- Sala B (derecha-abajo)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-002', 'Room-B', 'Room-B', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((10 0 0, 20 0 0, 20 10 0, 10 10 0, 10 0 0))', 3857)
);

-- Puerta entre A y B (vertical)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-010', 'Door-A-B', 'Door-A-B', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((9 4 0, 10 4 0, 10 6 0, 9 6 0, 9 4 0))', 3857)
);

-- Sala C (arriba de A)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-003', 'Room-C', 'Room-C', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((0 11 0, 9 11 0, 9 21 0, 0 21 0, 0 11 0))', 3857)
);

-- Puerta entre A y C (horizontal)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-011', 'Door-A-C', 'Door-A-C', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((4 10 0, 6 10 0, 6 11 0, 4 11 0, 4 10 0))', 3857)
);

-- Sala D (arriba de B)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-004', 'Room-D', 'Room-D', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((10 11 0, 20 11 0, 20 21 0, 10 21 0, 10 11 0))', 3857)
);

-- Puerta entre B y D (horizontal)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-012', 'Door-B-D', 'Door-B-D', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((14 10 0, 16 10 0, 16 11 0, 14 11 0, 14 10 0))', 3857)
);

-- Sala E (debajo de A) → bajada 1 m para dejar hueco
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-005', 'Room-E', 'Room-E', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((0 -11 0, 9 -11 0, 9 -1 0, 0 -1 0, 0 -11 0))', 3857)
);

-- Sala F (debajo de B) → bajada 1 m para dejar hueco
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-006', 'Room-F', 'Room-F', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((10 -11 0, 20 -11 0, 20 -1 0, 10 -1 0, 10 -11 0))', 3857)
);

-- Puerta entre E y A (horizontal en hueco y=-1 a y=0)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-013', 'Door-E-A', 'Door-E-A', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((4 -1 0, 6 -1 0, 6 0 0, 4 0 0, 4 -1 0))', 3857)
);

-- Puerta entre F y B (horizontal en hueco y=-1 a y=0)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-014', 'Door-F-B', 'Door-F-B', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((14 -1 0, 16 -1 0, 16 0 0, 14 0 0, 14 -1 0))', 3857)
);

-- Sala G (derecha de B)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-007', 'Room-G', 'Room-G', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((21 0 0, 31 0 0, 31 10 0, 21 10 0, 21 0 0))', 3857)
);

-- Puerta entre B y G (vertical)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-015', 'Door-B-G', 'Door-B-G', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((20 4 0, 21 4 0, 21 6 0, 20 6 0, 20 4 0))', 3857)
);

-- Room-H (arriba de D)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-016', 'Room-H', 'Room-H', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((10 22 0, 20 22 0, 20 32 0, 10 32 0, 10 22 0))', 3857)
);

-- Puerta interna H-D (horizontal)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-017', 'Door-H-D', 'Door-H-D', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((14 21 0, 16 21 0, 16 22 0, 14 22 0, 14 21 0))', 3857)
);

-- Puerta exterior H (derecha, sin conexión)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-018', 'Door-H-Ext', 'Door-H-Ext', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((20 26 0, 21 26 0, 21 28 0, 20 28 0, 20 26 0))', 3857)
);

-- Room-I corregida (a la izquierda de C, con hueco de 1 m para la puerta interna)
INSERT INTO indoorgml_core.cell_space
(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
VALUES ('CS-019', 'Room-I', 'Room-I', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((-11 11 0, -1 11 0, -1 21 0, -11 21 0, -11 11 0))', 3857)
);


-- Puerta interna I-C (vertical)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-020', 'Door-I-C', 'Door-I-C', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((0 14 0, 1 14 0, 1 16 0, 0 16 0, 0 14 0))', 3857)
);

-- Puerta exterior de I (lado izquierdo, sin conexión)
INSERT INTO indoorgml_core.cell_space
(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
VALUES ('CS-021', 'Door-I-Ext', 'Door-I-Ext', 'P01', FALSE, 'PR-01',
  ST_GeomFromText( 'POLYGON Z((-11 14 0, -12 14 0, -12 16 0, -11 16 0, -11 14 0))', 3857)
);

-- Room-J (debajo de E)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-022', 'Room-J', 'Room-J', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((0 -22 0, 9 -22 0, 9 -12 0, 0 -12 0, 0 -22 0))', 3857)
);

-- Puerta interna J-E (vertical)
INSERT INTO indoorgml_core.cell_space
VALUES ('CS-023', 'Door-J-E', 'Door-J-E', 'P01', FALSE, 'PR-01',
  ST_GeomFromText('POLYGON Z((4 -12 0, 6 -12 0, 6 -11 0, 4 -11 0, 4 -12 0))', 3857)
);

-- Puerta entre E y F (vertical en hueco x=9 a x=10)
INSERT INTO indoorgml_core.cell_space
(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
VALUES ('CS-024', 'Door-E-F', 'Door-E-F', 'P01', FALSE, 'PR-01',
  ST_GeomFromText(
    'POLYGON Z((9 -6 0, 10 -6 0, 10 -4 0, 9 -4 0, 9 -6 0))', 3857
  )
);
-- Puerta entre C y D (vertical en hueco x=9 a x=10)
INSERT INTO indoorgml_core.cell_space
(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
VALUES ('CS-025', 'Door-C-D', 'Door-C-D', 'P01', FALSE, 'PR-01',
  ST_GeomFromText(
    'POLYGON Z((9 14 0, 10 14 0, 10 16 0, 9 16 0, 9 14 0))', 3857
  )
);