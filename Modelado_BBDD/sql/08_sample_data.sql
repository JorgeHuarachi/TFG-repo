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


INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-001','P00-SPACE-001',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((0 0 0, 16.5 0 0, 16.5 6 0, 0 6 0, 0 0 0))  ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-002','P00-SPACE-002',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((17 0 0, 25 0 0, 25 6 0, 17 6 0, 17 0 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-003','P00-SPACE-003',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((25.5 0 0, 33.5 0 0, 33.5 6 0, 25.5 6 0, 25.5 0 0))       ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-004','P00-SPACE-004',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((34 0 0, 42 0 0, 42 6 0, 34 6 0, 34 0 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-005','P00-SPACE-005',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((0 6.5 0, 8 6.5 0, 8 12.5 0, 0 12.5 0, 0 6.5 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-006','P00-SPACE-006',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((8.5 6.5 0, 16.5 6.5 0, 16.5 12.5 0, 8.5 12.5 0, 8.5 6.5 0))              ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-007','P00-SPACE-007',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((17 6.5 0, 25 6.5 0, 25 12.5 0, 17 12.5 0, 17 6.5 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-008','P00-SPACE-008',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((25.5 6.5 0, 33.5 6.5 0, 33.5 12.5 0, 25.5 12.5 0, 25.5 6.5 0))   ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-009','P00-SPACE-009',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((37.5 32 0, 38.5 32 0, 38.5 32.5 0, 37.5 32.5 0, 37.5 32 0))      ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-010','P00-SPACE-010',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((34 6.5 0, 42 6.5 0, 42 12.5 0, 34 12.5 0, 34 6.5 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-011','P00-SPACE-011',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((0 13 0, 8 13 0, 8 19 0, 0 19 0, 0 13 0))     ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-012','P00-SPACE-012',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((8.5 13 0, 16.5 13 0, 16.5 19 0, 8.5 19 0, 8.5 13 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-013','P00-SPACE-013',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((17 13 0, 33.5 13 0, 33.5 19 0, 17 19 0, 17 13 0))      ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-014','P00-SPACE-014',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((34 13 0, 42 13 0, 42 19 0, 34 19 0, 34 13 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-015','P00-SPACE-015',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((0 19.5 0, 8 19.5 0, 8 25.5 0, 0 25.5 0, 0 19.5 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-016','P00-SPACE-016',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((8.5 19.5 0, 16.5 19.5 0, 16.5 25.5 0, 8.5 25.5 0, 8.5 19.5 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-017','P00-SPACE-017',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((17 19.5 0, 25 19.5 0, 25 25.5 0, 17 25.5 0, 17 19.5 0))              ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-018','P00-SPACE-018',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((25.5 19.5 0, 33.5 19.5 0, 33.5 25.5 0, 25.5 25.5 0, 25.5 19.5 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-019','P00-SPACE-019',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((34 19.5 0, 42 19.5 0, 42 25.5 0, 34 25.5 0, 34 19.5 0))                ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-020','P00-SPACE-020',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((0 26 0, 8 26 0, 8 32 0, 0 32 0, 0 26 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-021','P00-SPACE-021',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((8.5 26 0, 16.5 26 0, 16.5 32 0, 8.5 32 0, 8.5 26 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-022','P00-SPACE-022',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((17 26 0, 25 26 0, 25 32 0, 17 32 0, 17 26 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-023','P00-SPACE-023',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((25.5 26 0, 33.5 26 0, 33.5 32 0, 25.5 32 0, 25.5 26 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-024','P00-SPACE-001',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((34 26 0, 42 26 0, 42 32 0, 34 32 0, 34 26 0))  ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-025','P00-SPACE-002',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((16.5 2.5 0, 17 2.5 0, 17 3.5 0, 16.5 3.5 0, 16.5 2.5 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-026','P00-SPACE-003',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((25 2.5 0, 25.5 2.5 0, 25.5 3.5 0, 25 3.5 0, 25 2.5 0))       ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-027','P00-SPACE-004',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((33.5 2.5 0, 34 2.5 0, 34 3.5 0, 33.5 3.5 0, 33.5 2.5 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-028','P00-SPACE-005',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((8 9.0 0, 8.5 9.0 0, 8.5 10.0 0, 8 10.0 0, 8 9.0 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-029','P00-SPACE-006',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((16.5 9.0 0, 17 9.0 0, 17 10.0 0, 16.5 10.0 0, 16.5 9.0 0))               ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-030','P00-SPACE-007',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((25 9.0 0, 25.5 9.0 0, 25.5 10.0 0, 25 10.0 0, 25 9.0 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-031','P00-SPACE-008',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((33.5 9.0 0, 34 9.0 0, 34 10.0 0, 33.5 10.0 0, 33.5 9.0 0))   ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-032','P00-SPACE-009',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((8 15.5 0, 8.5 15.5 0, 8.5 16.5 0, 8 16.5 0, 8 15.5 0))       ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-033','P00-SPACE-010',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((16.5 15.5 0, 17 15.5 0, 17 16.5 0, 16.5 16.5 0, 16.5 15.5 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-034','P00-SPACE-011',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((33.5 15.5 0, 34 15.5 0, 34 16.5 0, 33.5 16.5 0, 33.5 15.5 0))    ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-035','P00-SPACE-012',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((8 22.0 0, 8.5 22.0 0, 8.5 23.0 0, 8 23.0 0, 8 22.0 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-036','P00-SPACE-013',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((16.5 22.0 0, 17 22.0 0, 17 23.0 0, 16.5 23.0 0, 16.5 22.0 0))      ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-037','P00-SPACE-014',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((25 22.0 0, 25.5 22.0 0, 25.5 23.0 0, 25 23.0 0, 25 22.0 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-038','P00-SPACE-015',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((33.5 22.0 0, 34 22.0 0, 34 23.0 0, 33.5 23.0 0, 33.5 22.0 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-039','P00-SPACE-016',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((8 28.5 0, 8.5 28.5 0, 8.5 29.5 0, 8 29.5 0, 8 28.5 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-040','P00-SPACE-017',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((16.5 28.5 0, 17 28.5 0, 17 29.5 0, 16.5 29.5 0, 16.5 28.5 0))              ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-041','P00-SPACE-018',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((25 28.5 0, 25.5 28.5 0, 25.5 29.5 0, 25 29.5 0, 25 28.5 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-042','P00-SPACE-019',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((33.5 28.5 0, 34 28.5 0, 34 29.5 0, 33.5 29.5 0, 33.5 28.5 0))                ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-043','P00-SPACE-020',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((3.5 6 0, 4.5 6 0, 4.5 6.5 0, 3.5 6.5 0, 3.5 6 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-044','P00-SPACE-021',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((12.0 6 0, 13.0 6 0, 13.0 6.5 0, 12.0 6.5 0, 12.0 6 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-045','P00-SPACE-022',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((20.5 6 0, 21.5 6 0, 21.5 6.5 0, 20.5 6.5 0, 20.5 6 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-046','P00-SPACE-023',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((29.0 6 0, 30.0 6 0, 30.0 6.5 0, 29.0 6.5 0, 29.0 6 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-047','P00-SPACE-001',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((37.5 6 0, 38.5 6 0, 38.5 6.5 0, 37.5 6.5 0, 37.5 6 0))   ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-048','P00-SPACE-002',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((3.5 12.5 0, 4.5 12.5 0, 4.5 13 0, 3.5 13 0, 3.5 12.5 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-049','P00-SPACE-003',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((12.0 12.5 0, 13.0 12.5 0, 13.0 13 0, 12.0 13 0, 12.0 12.5 0))      ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-050','P00-SPACE-004',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((20.5 12.5 0, 21.5 12.5 0, 21.5 13 0, 20.5 13 0, 20.5 12.5 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-051','P00-SPACE-005',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((29.0 12.5 0, 30.0 12.5 0, 30.0 13 0, 29.0 13 0, 29.0 12.5 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-052','P00-SPACE-006',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((37.5 12.5 0, 38.5 12.5 0, 38.5 13 0, 37.5 13 0, 37.5 12.5 0))              ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-053','P00-SPACE-007',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((3.5 19 0, 4.5 19 0, 4.5 19.5 0, 3.5 19.5 0, 3.5 19 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-054','P00-SPACE-008',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((12.0 19 0, 13.0 19 0, 13.0 19.5 0, 12.0 19.5 0, 12.0 19 0))  ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-055','P00-SPACE-009',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((20.5 19 0, 21.5 19 0, 21.5 19.5 0, 20.5 19.5 0, 20.5 19 0))      ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-056','P00-SPACE-010',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((29.0 19 0, 30.0 19 0, 30.0 19.5 0, 29.0 19.5 0, 29.0 19 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-057','P00-SPACE-011',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((37.5 19 0, 38.5 19 0, 38.5 19.5 0, 37.5 19.5 0, 37.5 19 0))    ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-058','P00-SPACE-012',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((3.5 25.5 0, 4.5 25.5 0, 4.5 26 0, 3.5 26 0, 3.5 25.5 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-059','P00-SPACE-013',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((12.0 25.5 0, 13.0 25.5 0, 13.0 26 0, 12.0 26 0, 12.0 25.5 0))      ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-060','P00-SPACE-014',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((20.5 25.5 0, 21.5 25.5 0, 21.5 26 0, 20.5 26 0, 20.5 25.5 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-061','P00-SPACE-015',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((29.0 25.5 0, 30.0 25.5 0, 30.0 26 0, 29.0 26 0, 29.0 25.5 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-062','P00-SPACE-016',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((37.5 25.5 0, 38.5 25.5 0, 38.5 26 0, 37.5 26 0, 37.5 25.5 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-063','P00-SPACE-017',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((-0.5 2.5 0, 0 2.5 0, 0 3.5 0, -0.5 3.5 0, -0.5 2.5 0))               ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-064','P00-SPACE-018',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((-0.5 9.0 0, 0 9.0 0, 0 10.0 0, -0.5 10.0 0, -0.5 9.0 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-065','P00-SPACE-019',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((-0.5 15.5 0, 0 15.5 0, 0 16.5 0, -0.5 16.5 0, -0.5 15.5 0))                ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-066','P00-SPACE-020',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((-0.5 22.0 0, 0 22.0 0, 0 23.0 0, -0.5 23.0 0, -0.5 22.0 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-067','P00-SPACE-021',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((-0.5 28.5 0, 0 28.5 0, 0 29.5 0, -0.5 29.5 0, -0.5 28.5 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-068','P00-SPACE-022',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((42 2.5 0, 42.5 2.5 0, 42.5 3.5 0, 42 3.5 0, 42 2.5 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-069','P00-SPACE-023',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((42 9.0 0, 42.5 9.0 0, 42.5 10.0 0, 42 10.0 0, 42 9.0 0))         ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-071','P00-SPACE-001',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((42 15.5 0, 42.5 15.5 0, 42.5 16.5 0, 42 16.5 0, 42 15.5 0))  ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-072','P00-SPACE-002',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((42 22.0 0, 42.5 22.0 0, 42.5 23.0 0, 42 23.0 0, 42 22.0 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-073','P00-SPACE-003',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((42 28.5 0, 42.5 28.5 0, 42.5 29.5 0, 42 29.5 0, 42 28.5 0))      ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-074','P00-SPACE-004',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((3.5 -0.5 0, 4.5 -0.5 0, 4.5 0 0, 3.5 0 0, 3.5 -0.5 0))           ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-075','P00-SPACE-005',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((12.0 -0.5 0, 13.0 -0.5 0, 13.0 0 0, 12.0 0 0, 12.0 -0.5 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-076','P00-SPACE-006',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((20.5 -0.5 0, 21.5 -0.5 0, 21.5 0 0, 20.5 0 0, 20.5 -0.5 0))              ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-077','P00-SPACE-007',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((29.0 -0.5 0, 30.0 -0.5 0, 30.0 0 0, 29.0 0 0, 29.0 -0.5 0))        ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-078','P00-SPACE-008',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((37.5 -0.5 0, 38.5 -0.5 0, 38.5 0 0, 37.5 0 0, 37.5 -0.5 0))  ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-079','P00-SPACE-009',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((3.5 32 0, 4.5 32 0, 4.5 32.5 0, 3.5 32.5 0, 3.5 32 0))       ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-080','P00-SPACE-010',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((12.0 32 0, 13.0 32 0, 13.0 32.5 0, 12.0 32.5 0, 12.0 32 0))          ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-081','P00-SPACE-011',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((20.5 32 0, 21.5 32 0, 21.5 32.5 0, 20.5 32.5 0, 20.5 32 0))    ',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-082','P00-SPACE-012',NULL,'P00',FALSE,'PR-01', ST_GeomFromText('POLYGONZ((29.0 32 0, 30.0 32 0, 30.0 32.5 0, 29.0 32.5 0, 29.0 32 0))        ',3857));



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
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-101','P01-SPACE-101',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 0 0, 9 0 0, 9 10 0, 0 10 0, 0 0 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-102','P01-SPACE-102',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((10 0 0, 20 0 0, 20 10 0, 10 10 0, 10 0 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-103','P01-SPACE-103',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 11 0, 9 11 0, 9 21 0, 0 21 0, 0 11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-104','P01-SPACE-104',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((10 11 0, 20 11 0, 20 21 0, 10 21 0, 10 11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-105','P01-SPACE-105',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 -11 0, 9 -11 0, 9 -1 0, 0 -1 0, 0 -11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-106','P01-SPACE-106',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((10 -11 0, 20 -11 0, 20 -1 0, 10 -1 0, 10 -11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-107','P01-SPACE-107',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((21 0 0, 31 0 0, 31 10 0, 21 10 0, 21 0 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-108','P01-SPACE-108',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 4 0, 10 4 0, 10 6 0, 9 6 0, 9 4 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-109','P01-SPACE-109',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((4 10 0, 6 10 0, 6 11 0, 4 11 0, 4 10 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-110','P01-SPACE-110',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((14 10 0, 16 10 0, 16 11 0, 14 11 0, 14 10 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-111','P01-SPACE-111',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((4 -1 0, 6 -1 0, 6 0 0, 4 0 0, 4 -1 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-112','P01-SPACE-112',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((14 -1 0, 16 -1 0, 16 0 0, 14 0 0, 14 -1 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-113','P01-SPACE-113',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((20 4 0, 21 4 0, 21 6 0, 20 6 0, 20 4 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-114','P01-SPACE-114',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((10 22 0, 20 22 0, 20 32 0, 10 32 0, 10 22 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-115','P01-SPACE-115',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((14 21 0, 16 21 0, 16 22 0, 14 22 0, 14 21 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-116','P01-SPACE-116',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((20 26 0, 21 26 0, 21 28 0, 20 28 0, 20 26 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-117','P01-SPACE-117',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-11 11 0, -1 11 0, -1 21 0, -11 21 0, -11 11 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-118','P01-SPACE-118',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-1 14 0, 0 14 0, 0 16 0, -1 16 0, -1 14 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-119','P01-SPACE-119',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-11 14 0, -12 14 0, -12 16 0, -11 16 0, -11 14 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-120','P01-SPACE-120',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 -22 0, 9 -22 0, 9 -12 0, 0 -12 0, 0 -22 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-121','P01-SPACE-121',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((4 -12 0, 6 -12 0, 6 -11 0, 4 -11 0, 4 -12 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-122','P01-SPACE-122',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 -6 0, 10 -6 0, 10 -4 0, 9 -4 0, 9 -6 0))',3857));
INSERT INTO indoorgml_core.cell_space (id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-123','P01-SPACE-123',NULL,'P01',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 14 0, 10 14 0, 10 16 0, 9 16 0, 9 14 0))',3857));

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
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-201','P02-SPACE-201',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 0 0, 8 0 0, 8 8 0, 0 8 0, 0 0 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-202','P02-SPACE-202',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 0 0, 18 0 0, 18 8 0, 9 8 0, 9 0 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-203','P02-SPACE-203',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 9 0, 8 9 0, 8 18 0, 0 18 0, 0 9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-204','P02-SPACE-204',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 9 0, 18 9 0, 18 18 0, 9 18 0, 9 9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-205','P02-SPACE-205',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((19 0 0, 28 0 0, 28 8 0, 19 8 0, 19 0 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-206','P02-SPACE-206',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((19 9 0, 28 9 0, 28 18 0, 19 18 0, 19 9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-207','P02-SPACE-207',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((0 -9 0, 8 -9 0, 8 -1 0, 0 -1 0, 0 -9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-208','P02-SPACE-208',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((9 -9 0, 18 -9 0, 18 -1 0, 9 -1 0, 9 -9 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-209','P02-SPACE-209',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-9 0 0, -1 0 0, -1 8 0, -9 8 0, -9 0 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-210','P02-SPACE-210',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((8 2 0, 9 2 0, 9 3 0, 8 3 0, 8 2 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-211','P02-SPACE-211',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((8 5 0, 9 5 0, 9 6 0, 8 6 0, 8 5 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-212','P02-SPACE-212',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((3 8 0, 5 8 0, 5 9 0, 3 9 0, 3 8 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-213','P02-SPACE-213',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((13 8 0, 15 8 0, 15 9 0, 13 9 0, 13 8 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-214','P02-SPACE-214',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((18 3 0, 19 3 0, 19 5 0, 18 5 0, 18 3 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-215','P02-SPACE-215',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((18 12 0, 19 12 0, 19 14 0, 18 14 0, 18 12 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-216','P02-SPACE-216',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((16 18 0, 17 18 0, 17 19 0, 16 19 0, 16 18 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-217','P02-SPACE-217',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((2 -1 0, 4 -1 0, 4 0 0, 2 0 0, 2 -1 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-218','P02-SPACE-218',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((12 -1 0, 14 -1 0, 14 0 0, 12 0 0, 12 -1 0))',3857));
INSERT INTO indoorgml_core.cell_space(id_cell_space, name, external_reference, level, poi, id_primal_space_layer, geom) VALUES ('CS-219','P02-SPACE-219',NULL,'P02',FALSE,'PR-01', ST_GeomFromText('POLYGON Z((-1 4 0, 0 4 0, 0 5 0, -1 5 0, -1 4 0))',3857))


--INICIALIZAR: marcar TODAS las celdas como GENERAL (SE EJECUTA DESPUES DE INSERTAR TODAS TUS CELDAS)

INSERT INTO indoorgml_navigation.navigable_space (id_cell_space, kind)
SELECT cs.id_cell_space, 'GENERAL'
FROM indoorgml_core.cell_space cs
LEFT JOIN indoorgml_navigation.navigable_space ns USING (id_cell_space)
WHERE ns.id_cell_space IS NULL
ON CONFLICT (id_cell_space) DO NOTHING;

-- Pon WALK a todos los GENERAL que no tengan locomotion
UPDATE indoorgml_navigation.navigable_space
SET locomotion = 'WALK'
WHERE kind = 'GENERAL' AND locomotion IS NULL;

