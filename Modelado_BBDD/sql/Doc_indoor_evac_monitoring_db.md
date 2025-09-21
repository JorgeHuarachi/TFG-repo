# Documantación sobre la base de datos ``indoor_evac_monitoring_db``
---
*``COSAS PENDIENTES``*
- Alinear el modeloado al estandar de OGC IndoorGML **(Ended)**.
- pasar todo a ingles **(InPriçocess)**.
- imcluir imagenes de figuras **(TBD)**. 
- Hacer el video antes de todo, porque voy a tardar en hacer lo anterior **(Ended pero necesito nuevo video debido a los cambios)**.
- DIAGRAMA DE FLUJOS NO DEJAR PARA EL FINAL **importante**
---
En este documento se explica la estructura y funcionamiento de la base de datos ``evac_db`` o ``indoor_evac_monotoring_db`` . Esta base de datos esta dividida en 3 bloques conceptuales, estos son:

**Bloque 1: IndoorGML Core Module**
**Bloque 2: Sensors and Readings**
**Bloque 3: Security and Events**


Estos bloques se traducen en **PostgreSQL** como *``Schemas``* dentro de la base de datos.

Primero se va presentar una imagen completa de la base de datos, para posteriormente centrarnos en cada uno de los bloques para comprender como funcionan y se conectan o relacionan entre si.

[PENDIENTE PONER IMAGEN DE LA DB COMPLETA]

>*nota*: Algo que se puede explicar desde ya es las entidades centrales `CellSpace` y `Node` con la cual estan conectadas varios de los bloques, es decir estan referenciados a uno o varias `CellSpace` o `Nodes`.
Esta entidad modela todos los espacios interiores existentes (Habitaciones, pertas, paredes, objetos) en todas las plantas del edificio. Gracias a los indices `id_building` e `id_level` queda definida la jerarquia entre esas entidades.

---

## Explicación de los bloques

### BLOQUE 1: IndoorGML features
FIGURA DEL BLOQUE 1 (MERMAID)
FIGURA UML DEL BLOQUE 1 (DEL DOCUMENTO INDOORGML)

En este primer bloque se modelan tanto los datos geometricos de los espacios interiores siguiendo y tomando como base el modelo conceptual de **IndoorGML OGC**.

> *Nota:* Algunos elementos del `Core` Compuesto por `ThematicLayer`, `PrimalSpaceLayer` y `DualSpaceLayer` no se han representado en los diagramas mermaid por simple preferencia visual, son elementos que tienen su papel dentro del entendimiento de las clases y las agrupaciones entre estas. Se a considerado mas interesante y menos cargaro representar las Entidades a partir de las cuales trabajamos, a pesar de que estas si existen fisicamente dentro de la base de datos.