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

-- ========================================================================================
-- ========================================================================================
-- ========================================================================================

-- PLANTA P01
  --INSERT INTO indoorgml_core.cell_space
  --(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
  --VALUES
  --  ('CS-001', 'P01-SPACE-001', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((0 0 0, 9 0 0, 9 10 0, 0 10 0, 0 0 0))', 3857)),
  --  ('CS-002', 'P01-SPACE-002', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((10 0 0, 20 0 0, 20 10 0, 10 10 0, 10 0 0))', 3857)),
  --  ('CS-003', 'P01-SPACE-003', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((0 11 0, 9 11 0, 9 21 0, 0 21 0, 0 11 0))', 3857)),
  --  ('CS-004', 'P01-SPACE-004', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((10 11 0, 20 11 0, 20 21 0, 10 21 0, 10 11 0))', 3857)),
  --  ('CS-005', 'P01-SPACE-005', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((0 -11 0, 9 -11 0, 9 -1 0, 0 -1 0, 0 -11 0))', 3857)),
  --  ('CS-006', 'P01-SPACE-006', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((10 -11 0, 20 -11 0, 20 -1 0, 10 -1 0, 10 -11 0))', 3857)),
  --  ('CS-007', 'P01-SPACE-007', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((21 0 0, 31 0 0, 31 10 0, 21 10 0, 21 0 0))', 3857)),
  --  ('CS-008', 'P01-SPACE-008', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((9 4 0, 10 4 0, 10 6 0, 9 6 0, 9 4 0))', 3857)),
  --  ('CS-009', 'P01-SPACE-009', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((4 10 0, 6 10 0, 6 11 0, 4 11 0, 4 10 0))', 3857)),
  --  ('CS-010', 'P01-SPACE-010', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((14 10 0, 16 10 0, 16 11 0, 14 11 0, 14 10 0))', 3857)),
  --  ('CS-011', 'P01-SPACE-011', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((4 -1 0, 6 -1 0, 6 0 0, 4 0 0, 4 -1 0))', 3857)),
  --  ('CS-012', 'P01-SPACE-012', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((14 -1 0, 16 -1 0, 16 0 0, 14 0 0, 14 -1 0))', 3857)),
  --  ('CS-013', 'P01-SPACE-013', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((20 4 0, 21 4 0, 21 6 0, 20 6 0, 20 4 0))', 3857)),
  --  ('CS-014', 'P01-SPACE-014', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((10 22 0, 20 22 0, 20 32 0, 10 32 0, 10 22 0))', 3857)),
  --  ('CS-015', 'P01-SPACE-015', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((14 21 0, 16 21 0, 16 22 0, 14 22 0, 14 21 0))', 3857)),
  --  ('CS-016', 'P01-SPACE-016', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((20 26 0, 21 26 0, 21 28 0, 20 28 0, 20 26 0))', 3857)),
  --  ('CS-017', 'P01-SPACE-017', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((-11 11 0, -1 11 0, -1 21 0, -11 21 0, -11 11 0))', 3857)),
  --  ('CS-018', 'P01-SPACE-018', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((-1 14 0, 0 14 0, 0 16 0, -1 16 0, -1 14 0))', 3857)),
  --  ('CS-019', 'P01-SPACE-019', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((-11 14 0, -12 14 0, -12 16 0, -11 16 0, -11 14 0))', 3857)),
  --  ('CS-020', 'P01-SPACE-020', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((0 -22 0, 9 -22 0, 9 -12 0, 0 -12 0, 0 -22 0))', 3857)),
  --  ('CS-021', 'P01-SPACE-021', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((4 -12 0, 6 -12 0, 6 -11 0, 4 -11 0, 4 -12 0))', 3857)),
  --  ('CS-022', 'P01-SPACE-022', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((9 -6 0, 10 -6 0, 10 -4 0, 9 -4 0, 9 -6 0))', 3857)),
  --  ('CS-023', 'P01-SPACE-023', NULL, 'P01', FALSE, 'PR-01', ST_GeomFromText('POLYGON Z((9 14 0, 10 14 0, 10 16 0, 9 16 0, 9 14 0))', 3857)
  --  );
-- EN VARIAS SENTENCIAS EJECUTA MAS RAPIDO
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-001','P01-SPACE-001',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 0 0, 9 0 0, 9 10 0, 0 10 0, 0 0 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-002','P01-SPACE-002',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((10 0 0, 20 0 0, 20 10 0, 10 10 0, 10 0 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-003','P01-SPACE-003',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 11 0, 9 11 0, 9 21 0, 0 21 0, 0 11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-004','P01-SPACE-004',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((10 11 0, 20 11 0, 20 21 0, 10 21 0, 10 11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-005','P01-SPACE-005',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 -11 0, 9 -11 0, 9 -1 0, 0 -1 0, 0 -11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-006','P01-SPACE-006',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((10 -11 0, 20 -11 0, 20 -1 0, 10 -1 0, 10 -11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-007','P01-SPACE-007',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((21 0 0, 31 0 0, 31 10 0, 21 10 0, 21 0 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-008','P01-SPACE-008',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 4 0, 10 4 0, 10 6 0, 9 6 0, 9 4 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-009','P01-SPACE-009',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((4 10 0, 6 10 0, 6 11 0, 4 11 0, 4 10 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-010','P01-SPACE-010',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((14 10 0, 16 10 0, 16 11 0, 14 11 0, 14 10 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-011','P01-SPACE-011',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((4 -1 0, 6 -1 0, 6 0 0, 4 0 0, 4 -1 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-012','P01-SPACE-012',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((14 -1 0, 16 -1 0, 16 0 0, 14 0 0, 14 -1 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-013','P01-SPACE-013',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((20 4 0, 21 4 0, 21 6 0, 20 6 0, 20 4 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-014','P01-SPACE-014',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((10 22 0, 20 22 0, 20 32 0, 10 32 0, 10 22 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-015','P01-SPACE-015',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((14 21 0, 16 21 0, 16 22 0, 14 22 0, 14 21 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-016','P01-SPACE-016',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((20 26 0, 21 26 0, 21 28 0, 20 28 0, 20 26 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-017','P01-SPACE-017',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-11 11 0, -1 11 0, -1 21 0, -11 21 0, -11 11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-018','P01-SPACE-018',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-1 14 0, 0 14 0, 0 16 0, -1 16 0, -1 14 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-019','P01-SPACE-019',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-11 14 0, -12 14 0, -12 16 0, -11 16 0, -11 14 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-020','P01-SPACE-020',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 -22 0, 9 -22 0, 9 -12 0, 0 -12 0, 0 -22 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-021','P01-SPACE-021',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((4 -12 0, 6 -12 0, 6 -11 0, 4 -11 0, 4 -12 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-022','P01-SPACE-022',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 -6 0, 10 -6 0, 10 -4 0, 9 -4 0, 9 -6 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-023','P01-SPACE-023',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 14 0, 10 14 0, 10 16 0, 9 16 0, 9 14 0))',3857));

-- PLANTA P02  --
  --INSERT INTO indoorgml_core.cell_space
  --(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom)
  --VALUES
  --    ('CS-101','SPACE-P2-101',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 0 0, 8 0 0, 8 8 0, 0 8 0, 0 0 0))',3857)),
  --    ('CS-102','SPACE-P2-102',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 0 0, 18 0 0, 18 8 0, 9 8 0, 9 0 0))',3857)),
  --    ('CS-103','SPACE-P2-103',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 9 0, 8 9 0, 8 18 0, 0 18 0, 0 9 0))',3857)),
  --    ('CS-104','SPACE-P2-104',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 9 0, 18 9 0, 18 18 0, 9 18 0, 9 9 0))',3857)),
  --    ('CS-105','SPACE-P2-105',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((19 0 0, 28 0 0, 28 8 0, 19 8 0, 19 0 0))',3857)),
  --    ('CS-106','SPACE-P2-106',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((19 9 0, 28 9 0, 28 18 0, 19 18 0, 19 9 0))',3857)),
  --    ('CS-107','SPACE-P2-107',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 -9 0, 8 -9 0, 8 -1 0, 0 -1 0, 0 -9 0))',3857)),
  --    ('CS-108','SPACE-P2-108',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 -9 0, 18 -9 0, 18 -1 0, 9 -1 0, 9 -9 0))',3857)),
  --    ('CS-109','SPACE-P2-109',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-9 0 0, -1 0 0, -1 8 0, -9 8 0, -9 0 0))',3857)),
  --    ('CS-110','SPACE-P2-110',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((8 2 0, 9 2 0, 9 3 0, 8 3 0, 8 2 0))',3857)),
  --    ('CS-111','SPACE-P2-111',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((8 5 0, 9 5 0, 9 6 0, 8 6 0, 8 5 0))',3857)),
  --    ('CS-112','SPACE-P2-112',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((3 8 0, 5 8 0, 5 9 0, 3 9 0, 3 8 0))',3857)),
  --    ('CS-113','SPACE-P2-113',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((13 8 0, 15 8 0, 15 9 0, 13 9 0, 13 8 0))',3857)),
  --    ('CS-114','SPACE-P2-114',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((18 3 0, 19 3 0, 19 5 0, 18 5 0, 18 3 0))',3857)),
  --    ('CS-115','SPACE-P2-115',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((18 12 0, 19 12 0, 19 14 0, 18 14 0, 18 12 0))',3857)),
  --    ('CS-116','SPACE-P2-116',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((16 18 0, 17 18 0, 17 19 0, 16 19 0, 16 18 0))',3857)),
  --    ('CS-117','SPACE-P2-117',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((2 -1 0, 4 -1 0, 4 0 0, 2 0 0, 2 -1 0))',3857)),
  --    ('CS-118','SPACE-P2-118',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((12 -1 0, 14 -1 0, 14 0 0, 12 0 0, 12 -1 0))',3857)),
  --    ('CS-119','SPACE-P2-119',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-1 4 0, 0 4 0, 0 5 0, -1 5 0, -1 4 0))',3857));
  --
  -- MISMA PLANTA EN VARIAS SENTENCIAS: ACTUALMENTE ES MUCHO MAS RAPIDO ASI, EJECUTA MAS RAPIDO
-- EN VARIAS SENTENCIAS EJECUTA MAS RAPIDO
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-101','SPACE-P2-101',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 0 0, 8 0 0, 8 8 0, 0 8 0, 0 0 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-102','SPACE-P2-102',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 0 0, 18 0 0, 18 8 0, 9 8 0, 9 0 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-103','SPACE-P2-103',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 9 0, 8 9 0, 8 18 0, 0 18 0, 0 9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-104','SPACE-P2-104',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 9 0, 18 9 0, 18 18 0, 9 18 0, 9 9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-105','SPACE-P2-105',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((19 0 0, 28 0 0, 28 8 0, 19 8 0, 19 0 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-106','SPACE-P2-106',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((19 9 0, 28 9 0, 28 18 0, 19 18 0, 19 9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-107','SPACE-P2-107',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 -9 0, 8 -9 0, 8 -1 0, 0 -1 0, 0 -9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-108','SPACE-P2-108',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 -9 0, 18 -9 0, 18 -1 0, 9 -1 0, 9 -9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-109','SPACE-P2-109',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-9 0 0, -1 0 0, -1 8 0, -9 8 0, -9 0 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-110','SPACE-P2-110',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((8 2 0, 9 2 0, 9 3 0, 8 3 0, 8 2 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-111','SPACE-P2-111',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((8 5 0, 9 5 0, 9 6 0, 8 6 0, 8 5 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-112','SPACE-P2-112',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((3 8 0, 5 8 0, 5 9 0, 3 9 0, 3 8 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-113','SPACE-P2-113',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((13 8 0, 15 8 0, 15 9 0, 13 9 0, 13 8 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-114','SPACE-P2-114',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((18 3 0, 19 3 0, 19 5 0, 18 5 0, 18 3 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-115','SPACE-P2-115',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((18 12 0, 19 12 0, 19 14 0, 18 14 0, 18 12 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-116','SPACE-P2-116',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((16 18 0, 17 18 0, 17 19 0, 16 19 0, 16 18 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-117','SPACE-P2-117',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((2 -1 0, 4 -1 0, 4 0 0, 2 0 0, 2 -1 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-118','SPACE-P2-118',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((12 -1 0, 14 -1 0, 14 0 0, 12 0 0, 12 -1 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-119','SPACE-P2-119',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-1 4 0, 0 4 0, 0 5 0, -1 5 0, -1 4 0))',3857))


--INICIALIZAR: marcar TODAS las celdas como GENERAL (SE EJECUTA DESPUES DE INSERTAR TODAS TUS CELDAS)

INSERT INTO indoorgml_navigation.navigable_space (id_cell_space, kind)
SELECT cs.id_cell_space, 'GENERAL'
FROM indoorgml_core.cell_space cs
LEFT JOIN indoorgml_navigation.navigable_space ns USING (id_cell_space)
WHERE ns.id_cell_space IS NULL
ON CONFLICT (id_cell_space) DO NOTHING;
