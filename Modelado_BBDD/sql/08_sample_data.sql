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
-- PLANTA P01
INSERT INTO indoorgml_core.cell_space
(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
VALUES
  -- CS-001
  ('CS-001', 'Room-A', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((0 0 0, 9 0 0, 9 10 0, 0 10 0, 0 0 0))', 3857)),
  -- CS-002
  ('CS-002', 'Room-B', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((10 0 0, 20 0 0, 20 10 0, 10 10 0, 10 0 0))', 3857)),
  -- CS-003
  ('CS-003', 'Room-C', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((0 11 0, 9 11 0, 9 21 0, 0 21 0, 0 11 0))', 3857)),
  -- CS-004
  ('CS-004', 'Room-D', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((10 11 0, 20 11 0, 20 21 0, 10 21 0, 10 11 0))', 3857)),
  -- CS-005
  ('CS-005', 'Room-E', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((0 -11 0, 9 -11 0, 9 -1 0, 0 -1 0, 0 -11 0))', 3857)),
  -- CS-006
  ('CS-006', 'Room-F', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((10 -11 0, 20 -11 0, 20 -1 0, 10 -1 0, 10 -11 0))', 3857)),
  -- CS-007
  ('CS-007', 'Room-G', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((21 0 0, 31 0 0, 31 10 0, 21 10 0, 21 0 0))', 3857)),
  -- CS-010
  ('CS-010', 'Door-A-B', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((9 4 0, 10 4 0, 10 6 0, 9 6 0, 9 4 0))', 3857)),
  -- CS-011
  ('CS-011', 'Door-A-C', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((4 10 0, 6 10 0, 6 11 0, 4 11 0, 4 10 0))', 3857)),
  -- CS-012
  ('CS-012', 'Door-B-D', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((14 10 0, 16 10 0, 16 11 0, 14 11 0, 14 10 0))', 3857)),
  -- CS-013
  ('CS-013', 'Door-E-A', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((4 -1 0, 6 -1 0, 6 0 0, 4 0 0, 4 -1 0))', 3857)),
  -- CS-014
  ('CS-014', 'Door-F-B', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((14 -1 0, 16 -1 0, 16 0 0, 14 0 0, 14 -1 0))', 3857)),
  -- CS-015
  ('CS-015', 'Door-B-G', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((20 4 0, 21 4 0, 21 6 0, 20 6 0, 20 4 0))', 3857)),
  -- CS-016
  ('CS-016', 'Room-H', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((10 22 0, 20 22 0, 20 32 0, 10 32 0, 10 22 0))', 3857)),
  -- CS-017
  ('CS-017', 'Door-H-D', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((14 21 0, 16 21 0, 16 22 0, 14 22 0, 14 21 0))', 3857)),
  -- CS-018
  ('CS-018', 'Door-H-Ext', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((20 26 0, 21 26 0, 21 28 0, 20 28 0, 20 26 0))', 3857)),
  -- CS-019
  ('CS-019', 'Room-I', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((-11 11 0, -1 11 0, -1 21 0, -11 21 0, -11 11 0))', 3857)),
  -- CS-020 (corregida: x = -1..0 para evitar solape con Room-C)
  ('CS-020', 'Door-I-C', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((-1 14 0, 0 14 0, 0 16 0, -1 16 0, -1 14 0))', 3857)),
  -- CS-021
  ('CS-021', 'Door-I-Ext', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((-11 14 0, -12 14 0, -12 16 0, -11 16 0, -11 14 0))', 3857)),
  -- CS-022
  ('CS-022', 'Room-J', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((0 -22 0, 9 -22 0, 9 -12 0, 0 -12 0, 0 -22 0))', 3857)),
  -- CS-023
  ('CS-023', 'Door-J-E', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((4 -12 0, 6 -12 0, 6 -11 0, 4 -11 0, 4 -12 0))', 3857)),
  -- CS-024
  ('CS-024', 'Door-E-F', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((9 -6 0, 10 -6 0, 10 -4 0, 9 -4 0, 9 -6 0))', 3857)),
  -- CS-025
  ('CS-025', 'Door-C-D', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((9 14 0, 10 14 0, 10 16 0, 9 16 0, 9 14 0))', 3857)
  );

-- PLANTA P02
-- =========================
-- Planta P02 (rooms + doors)
-- =========================

-- Salas principales
INSERT INTO indoorgml_core.cell_space
(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
VALUES
    -- A (0..8 x 0..8)
    ('CS-101','P2-Room-A','P2-Room-A','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 0 0, 8 0 0, 8 8 0, 0 8 0, 0 0 0))',3857)),
    -- B (9..18 x 0..8)  → hueco vertical x=8..9
    ('CS-102','P2-Room-B','P2-Room-B','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 0 0, 18 0 0, 18 8 0, 9 8 0, 9 0 0))',3857)),
    -- C (0..8 x 9..18)  → hueco horizontal y=8..9
    ('CS-105','P2-Room-C','P2-Room-C','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 9 0, 8 9 0, 8 18 0, 0 18 0, 0 9 0))',3857)),
    -- D (9..18 x 9..18) → hueco horizontal y=8..9
    ('CS-107','P2-Room-D','P2-Room-D','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 9 0, 18 9 0, 18 18 0, 9 18 0, 9 9 0))',3857)),
    -- E a la derecha de B (19..28 x 0..8) → hueco vertical x=18..19
    ('CS-109','P2-Room-E','P2-Room-E','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((19 0 0, 28 0 0, 28 8 0, 19 8 0, 19 0 0))',3857)),
    -- F sobre E (19..28 x 9..18) → hueco vertical x=18..19
    ('CS-111','P2-Room-F','P2-Room-F','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((19 9 0, 28 9 0, 28 18 0, 19 18 0, 19 9 0))',3857)),
    -- G debajo de A (0..8 x -9..-1) → hueco horizontal y=-1..0
    ('CS-114','P2-Room-G','P2-Room-G','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 -9 0, 8 -9 0, 8 -1 0, 0 -1 0, 0 -9 0))',3857)),
    -- H debajo de B (9..18 x -9..-1) → hueco horizontal y=-1..0
    ('CS-116','P2-Room-H','P2-Room-H','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 -9 0, 18 -9 0, 18 -1 0, 9 -1 0, 9 -9 0))',3857)),
    -- I a la izquierda de A (-9..-1 x 0..8) → hueco vertical x=-1..0
    ('CS-118','P2-Room-I','P2-Room-I','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-9 0 0, -1 0 0, -1 8 0, -9 8 0, -9 0 0))',3857));

-- Puertas (todas dentro de los huecos de 1 m; contacto 1D con salas)
INSERT INTO indoorgml_core.cell_space
(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
VALUES
    -- A ↔ B (dos puertas verticales en el hueco x=8..9)
    ('CS-103','P2-Door-A-B-1','P2-Door-A-B-1','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((8 2 0, 9 2 0, 9 3 0, 8 3 0, 8 2 0))',3857)),
    ('CS-104','P2-Door-A-B-2','P2-Door-A-B-2','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((8 5 0, 9 5 0, 9 6 0, 8 6 0, 8 5 0))',3857)),

    -- A ↔ C (puerta horizontal en y=8..9)
    ('CS-106','P2-Door-A-C','P2-Door-A-C','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((3 8 0, 5 8 0, 5 9 0, 3 9 0, 3 8 0))',3857)),

    -- B ↔ D (puerta horizontal en y=8..9)
    ('CS-108','P2-Door-B-D','P2-Door-B-D','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((13 8 0, 15 8 0, 15 9 0, 13 9 0, 13 8 0))',3857)),

    -- B ↔ E (puerta vertical en x=18..19)
    ('CS-110','P2-Door-B-E','P2-Door-B-E','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((18 3 0, 19 3 0, 19 5 0, 18 5 0, 18 3 0))',3857)),

    -- D ↔ F (puerta vertical en x=18..19)
    ('CS-112','P2-Door-D-F','P2-Door-D-F','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((18 12 0, 19 12 0, 19 14 0, 18 14 0, 18 12 0))',3857)),

    -- Puerta exterior de D (arriba, y=18..19), toca solo D
    ('CS-113','P2-Door-D-Ext','P2-Door-D-Ext','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((16 18 0, 17 18 0, 17 19 0, 16 19 0, 16 18 0))',3857)),

    -- G ↔ A (puerta horizontal en y=-1..0)
    ('CS-115','P2-Door-G-A','P2-Door-G-A','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((2 -1 0, 4 -1 0, 4 0 0, 2 0 0, 2 -1 0))',3857)),

    -- H ↔ B (puerta horizontal en y=-1..0)
    ('CS-117','P2-Door-H-B','P2-Door-H-B','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((12 -1 0, 14 -1 0, 14 0 0, 12 0 0, 12 -1 0))',3857)),

    -- I ↔ A (puerta vertical en x=-1..0)
    ('CS-119','P2-Door-I-A','P2-Door-I-A','P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-1 4 0, 0 4 0, 0 5 0, -1 5 0, -1 4 0))',3857));

