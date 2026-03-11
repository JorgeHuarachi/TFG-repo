# IndoorGML Part 1 (Conceptual)
Aqui lo que me interesa sobre el documento de IndoorGML, lo que explican y especifican sobre la información Indoor.

## 1) ¿Tu idea del grafo (nodos = salas; edges = conexiones; weight = tiempo) es lógica?

Sí, 100% IndoorGML-compatible. En el dual de IndoorGML los nodos abstraen CellSpaces (p. ej., salas) y las aristas representan adyacencia/conectividad entre esos nodos; cada Edge puede llevar un weight (Real) para coste/tiempo. Además, el grafo puede ser lógico o geométrico (propiedad isLogical en el DualSpaceLayer).

Traducción directa a tu caso:

Nodo = GeneralSpace (sala/pasillo).

Edge = conexión por puerta/ventana (o por otro mecanismo) entre dos salas; con weight = tiempo. 


## 2) ¿Necesitas geometría 3D? ¿Puedes quedarte en 2D?

IndoorGML permite 2D o 3D; incluso permite omitir geometría y trabajar solo con red lógica. Si marcas el grafo como lógico (isLogical = TRUE), no necesitas geometría para representar conectividad básica; si lo marcas como geométrico (isLogical = FALSE), entonces los Node.geometry deben caer dentro de su CellSpace y las aristas pueden llevar GM_Curve sin auto-intersección.

Para calcular tiempos realistas, ayuda mucho tener al menos 2D (distancias, longitudes de paso). El estándar autoriza 2D: los CellSpace aceptan GM_Surface 2D; y las CellBoundary admiten representación 1D/2D, ideal para planos en 2D.

Conclusión práctica: sí puedes empezar 100% en 2D y es fácil de justificar con IndoorGML. Mantén el grafo lógico al principio; cuando quieras tiempos más finos, añade geometría 2D y conviertes el grafo a geométrico. 


## 3) ¿Puedo identificar posiciones de puertas/ventanas en 2D?

Sí. En 2D, las puertas/ventanas suelen representarse como CellBoundary 1D (línea) navegable o como TransferSpace 2D pequeño (si eliges modelarlas como celdas). IndoorGML explicita ambas opciones:

Puertas/ventanas como TransferSpace (subtipo de NavigableSpace) con category = Door | Window y función Anchor/Connection (ideal para “conecta con exterior”). 


En 2D, las puertas suelen ir como NavigableBoundary (frontera navegable entre celdas). 


Con esa geometría 2D puedes medir distancias entre aberturas de una sala (líneas más cortas dentro del polígono de la sala, o centroides de aberturas) para construir tu grafo de puertas/ventanas. 


## 4) Cómo cubrir tus filtros con el modelo

Querrás diferenciar tipos de conexión y destinos especiales. Te propongo dos patrones (ambos válidos):

Opción A — Un solo grafo y filtras por atributos (más simple)

Una ThematicLayer “Topographic (Physical)” con Navigation activado. En Primal:

GeneralSpace = salas/pasillos.

TransferSpace = aberturas; category=Door|Window; function=Anchor para “conecta con exterior”, o Connection para “interior-interior”. Escaleras: modela la caja como GeneralSpace y la entrada como TransferSpace (vertical). 


Un DualSpaceLayer con Nodes (duales de salas y, si quieres, también de aberturas) y Edges:

edge.type ∈ {door, window, vent, egress...}; edge.weight = tiempo.

Para “puertas y ventanas a la vez”, busca pares de salas con dos edges distintos (door y window) o un edge multi-tipo.

“Con exterior / emergencia / escalera incendios”: marca TransferSpace.function=Anchor (exterior), o usa una sala especial del tipo “stairwell / emergency stair” conectada por su TransferSpace. 


Ventajas: un solo grafo, consultas simples por tipo de edge y locomotionType (Walking, Rolling, Flying) para accesibilidad/movilidad. 


Opción B — Varios grafos (capas) y los relacionas (más limpio semánticamente)

Topographic-Walking (puertas, Walking/Rolling).

Topographic-Openings (grafo interno solo de aberturas).

Ventilation (conductos).

Relaciónalos con InterLayerConnection: contains/within/equals, con la regla de oro: capas distintas, connectedNodes/connectedCells 0 o 2 (nunca 1) y no conmutativo (“A contains B” ≠ “B contains A”). 


Ventajas: separas humano vs ventilación; desventaja: gestionas varias capas. Ambas estrategias son normativas. La elección es de ingeniería.

## 5) Tu grafo de puertas/ventanas como nodos (¿dónde encaja?)

Justificación IndoorGML:

Si modelas cada puerta/ventana como TransferSpace (celda), ya tiene nodo dual en el mismo DualSpaceLayer; puedes construir un subgrafo con solo esos nodos y Edges que unan aberturas dentro de la misma sala (trayectos internos). Está permitido crear Edges sin frontera asociada (no siempre hay CellBoundary común, p. ej. visibility graph), o darles geometría 2D si quieres ver la línea. 


Si quieres tener dos grafos distintos (1: salas↔salas; 2: aberturas↔aberturas), IndoorGML 2.0 define ThematicLayer como agregación de un primal y un dual; como solo hay un dual por capa, la forma canónica de tener “dos duales” es crear otra ThematicLayer (mismo theme=Physical) y unirlas con InterLayerConnection (equals entre nodos/celdas correspondientes). Ambas capas siguen la norma de “mismo tema” por capa.

Recomendación práctica para ti:
Empieza con Opción A (un solo dual y edge.type), y define nodo.tipo ∈ {room, opening} y edge.type ∈ {door,window,vent,egress,intraroom}. Cuando quieras análisis más avanzados de aberturas, puedes escindir a Opción B (otra ThematicLayer “Openings”) sin romper nada.

## 6) Casos especiales que pedías

Salas adyacentes: si comparten CellBoundary o están conectadas por TransferSpace, habrá Edge entre sus Nodes. El Edge puede (o no) enlazar por duality a una CellBoundary; para puertas/ventanas usarás category en TransferSpace y/o edge.type. 


Puertas vs ventanas: usa TransferSpace.category = Door | Window. Para “conectadas por las dos a la vez”, filtra salas con dos edges diferentes (door y window) entre los mismos nodos. 


Conductos de ventilación: mejor como ThematicLayer “Ventilation” con su propio primal/dual; relacionas con Topographic por InterLayerConnection. Así nunca mezclas movilidad humana con red de conductos. 


Exterior / salida de emergencia / escalera de incendios: modela la salida como TransferSpace.function=Anchor (conecta interior↔exterior) y las escaleras como GeneralSpace (caja de escalera) + TransferSpace (entrada), con Edges que reflejen el coste (incluso dirigidos si hay sentido único).

---

¡Perfecto! Vamos a modelar **paredes como anillos poligonales con espesor** que “cubren” (contienen) los huecos de **puertas** y **ventanas**, y ver cómo resolver **escaleras/rampas** y la **conectividad** en PostGIS.

---

### 1) Visión general (2D “+ atributos de altura”)

PostGIS se lleva muy bien con un modelo **2D** por planta (SRID en metros; p.ej. `25830`), y guardas alturas (cotas) como **atributos**.
Esto te da topologías robustas y consultas rápidas; si más adelante quieres 3D, puedes derivarlo (ver §6).

**Capas básicas por planta:**

* `spaces` (salas y zonas de circulación) – **Polygon**
* `walls` (muros con grosor) – **(Multi)Polygon**
* `openings` (huecos) – **Polygon** con tipo = `door` | `window`
* `stairs` / `ramps` (elementos de conexión vertical y circulación) – **Polygon**
* opcional: `exterior` (un gran polígono “fuera”) para tratar puertas a exterior como cualquier otra conexión.

> Idea clave: los **openings** viven *dentro del polígono de muro* y **tocan** (no solapan) los bordes interiores de los `spaces`.

---

### 2) Reglas topológicas (invariantes “de oro”)
v
Estas reglas mantienen tu modelo limpio y hacen triviales las consultas:

1. **Walls vs Spaces**

   * Cada `space.geom` **toca** (`ST_Touches`) a uno o varios `walls.geom` por su frontera interior.
   * `spaces` no se solapan entre sí; a lo sumo comparten frontera.

2. **Openings dentro del muro**

   * `ST_CoveredBy(openings.geom, walls.geom)` = **TRUE** (el hueco está contenido por un único muro).
   * El opening **atraviesa** el muro: su polígono corta el espesor (geométricamente: el opening intersecta la “banda” del muro con una anchura significativa).

3. **Puertas** (tipo = `door`)

   * Tienen **contacto lineal** con **exactamente dos** `spaces` (las 2 caras del muro):
     `ST_Touches(door, space)` y longitud de contacto > umbral (p.ej. 2 cm) para evitar toques en esquina.
   * Definen **conectividad pasable** entre esos dos `spaces`.

4. **Ventanas** (tipo = `window`)

   * También están **cubiertas por el muro** y **tocan** al menos **un** `space`.
   * No generan conectividad “pasable”, pero sí **adyacencia visual/ventilación** hacia otro `space` o `exterior`.

5. **Escaleras/Rampas**

   * En cada planta, son un `space` especial de tipo circulación (así los tratas igual que un pasillo).
   * La **conexión vertical** se modela como **aristas** entre la instancia del elemento en planta `n` y su contraparte en planta `n±1`.



### 4) Ventanas: cómo integrarlas

* **Concepto**: son **openings** dentro de `walls`, con `kind='window'`, y **tocan** la frontera de un `space`.
* **Atributos clave**: `sill_m` y `head_m` te dan la banda vertical que ocupa.
* **Relaciones útiles**:

  * Ventanas a **exterior**: el opening no toca un segundo `space` → el “otro lado” es `exterior`.
  * Ventanas **interiores**: el opening toca dos `spaces` (adyacencia visual/sonora entre ellos).



### Enrutamiento (multiplanta)

* Con **pgRouting** puedes construir un grafo:

  * **Nodos**: `spaces.id`
  * **Aristas horizontales**: de `space_connectivity` (peso = 1 puerta o longitud de puerta/pasillo).
  * **Aristas verticales**: de `vertical_edges` (peso = `cost_s`).
* Luego `pgr_dijkstra` o `pgr_astar` para rutas accesibles, más rápidas, sin escaleras, etc.
  Basta filtrar por `kind != 'stair'` para rutas accesibles o asignarles coste infinito si hay silla de ruedas.

---

# 7) Representación 3D (opcional)

Si quieres “elevar” tu 2D:

* Guarda las cotas `z_base_m` / `z_top_m` en `spaces` y los **rangos** de ventanas/puertas (`sill_m`/`head_m`).
* Puedes extruir para visualización usando la extensión **SFCGAL** (`postgis_sfcgal`) con `ST_Extrude(geom, 0,0, altura)`.
* Para operaciones booleanas 3D simples (intersecciones, volúmenes) SFCGAL también ayuda; pero para GIS de planta, el **2D + atributos** es más simple y suficiente.

---

# 8) Validación y calidad

* `ST_IsValid` + `ST_MakeValid` tras importar CAD/BIM.
* Misma SRID en todas las capas.
* Umbrales (1–5 mm / 5–20 mm) para contactos lineales y tolerancias.
* Índices GiST en todas las columnas `geom`.
* Vistas materializadas para `space_connectivity` y (si lo usas) `adjacencias por muro`.

---

## Resumen

* **Paredes**: polígonos con espesor; **openings** (puertas/ventanas) como polígonos **contenidos** en el muro que **tocan** los `spaces`.
* **Puertas** ⇒ conectividad **pasable** entre dos `spaces`.
* **Ventanas** ⇒ adyacencia **visual/ventilación** (a otra sala o exterior).
* **Escaleras/Rampas** ⇒ trátalas como `spaces` de circulación y crea **aristas verticales** entre plantas; con **pgRouting** resuelves rutas multiplanta.

