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

-- CELLBOUNDARY --
