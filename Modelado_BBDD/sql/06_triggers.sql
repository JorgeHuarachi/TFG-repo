
-- BLOQUE INDOORGML: CORE --

-- CELLSPACE --

-- Trigger para evitar solapamientos 
CREATE CONSTRAINT TRIGGER ct_cell_space_no_overlap
AFTER INSERT OR UPDATE OF geom, level -- Despues de una sentencia (update o insert) en geom o level
ON indoorgml_core.cell_space 
DEFERRABLE INITIALLY DEFERRED -- Para que valide el conjunto (antigui y nuevo) al final 
FOR EACH ROW EXECUTE FUNCTION indoorgml_core.fn_cell_space_no_overlap(); -- Ejecuta la funcion para cada fila afectada


