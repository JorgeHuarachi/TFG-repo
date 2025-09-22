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

> *Nota*: No se entrara en detalle sobre el modelado de la base de datos, los detalles del modelado *Modelo Conceptual*, *Modelo Lógico* y *Modelo Fisico* se reflejaran en **Documentacion Modelado de evac_db.md** aqui nos limitamos a entender como se estructura internamente la base de datos, que contiene y como funciona, se mencionaran elementos técnicos como si son necesarios, pero no es el objetivo de esta documentación

**Bloque 1: IndoorGML Core Module**
**Bloque 2: Sensors and Readings**
**Bloque 3: Security and Events**


Estos bloques se traducen en **PostgreSQL** como *``Schemas``* dentro de la base de datos.

Primero se va presentar una imagen completa de la base de datos, para posteriormente centrarnos en cada uno de los bloques para comprender como funcionan y se conectan o relacionan entre si.

[PENDIENTE PONER IMAGEN DE LA DB COMPLETA]

>*nota*: Algo que se puede explicar desde ya es las entidades centrales `CellSpace` y `Node` con la cual estan conectadas varios de los bloques, es decir estan referenciados a uno o varias `CellSpace` o `Nodes`.
Esta entidad modela todos los espacios interiores existentes (Habitaciones, pertas, paredes, objetos) en todas las plantas del edificio. Gracias a los indices `id_building` e `id_level` queda definida la jerarqWuia entre esas entidades.

---

## Explicación de los bloques

### BLOQUE 1: IndoorGML Core
FIGURA DEL BLOQUE 1 (MERMAID)****
FIGURA UML DEL BLOQUE 1 (DEL DOCUMENTO INDOORGML)****

En este primer bloque se modelan tanto los datos geometricos de los espacios interiores siguiendo y tomando como base el modelo conceptual de **IndoorGML OGC**.

> *Nota:* Algunos elementos del `Core Module` Compuesto por `ThematicLayer`, `PrimalSpaceLayer` y `DualSpaceLayer` no se han representado en los diagramas mermaid por simple preferencia visual, son elementos que tienen su papel dentro del entendimiento de las clases y las agrupaciones entre estas. Se a considerado mas interesante y menos cargaro representar las Entidades a partir de las cuales trabajamos, a pesar de que estas si existen fisicamente dentro de la base de datos. No se explicarán esas entidades y se pasará directamente a las entidades que implican directamente al modulo de **Navegación**

En este bloque 4 entidades son importantes para dar pie a el modulo de navegación y son:
- `CellSpace`
- `CellBoundary`
- `Node`
- `Edge`

**CellSpace:** Esta entidad guardará toda la información geométrica de los espacios tanto navegables como no navegables y de esta de heredan dos ramas del modulo de navegacion en:
- `NavigableSpace`
- `NonNavigableSpace`

`CellSpace` almacena en su interior los poligonos que corresponden a los diferentes espacios dentro de un edifico en diferentes plantas (salas, puertas, paredes, ventanas, escaleras, rampas etc. aunque paredes no insertaran en nuestro caso).

**CellBoundary:** Esta entidad guarda toda la informacino geometrica de los bbox (boundary box) ya sea que estan entre celdas o estan libres al exterior, es la frontera de cada uno de las celdas, aqui es intersante quedarse solo con las que conectan dos `CellBoundary` ya que esto me da directamente las relaciones entre celdas, util para la dualidad, de esta se heredan la ramas del modulo de navegación:
- `NavigableBoundary`
- `NonNavigableBoundary` 
Para nosotros no es tan interesante modelar esto, con una tabla relacion entre las dos tabla `CellSpace` y `CellBoundary` ya se tiene la información de que `CellBondary` es navegable *(Da a una puerta)* o no *(da a una pared o no da a ningun sitio)*.



