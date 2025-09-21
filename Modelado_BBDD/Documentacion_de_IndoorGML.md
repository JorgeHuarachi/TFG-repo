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

---

### 3) Esquema de datos (DDL mínimo)

```sql
-- Salas / espacios
CREATE TABLE spaces (
  id        serial PRIMARY KEY,
  floor_id  int NOT NULL,
  name      text,
  kind      text DEFAULT 'room',          -- 'room','corridor','stair','ramp','lobby', etc.
  z_base_m  numeric,                      -- cota suelo
  z_top_m   numeric,                      -- altura libre
  geom      geometry(Polygon, 25830) NOT NULL
);
CREATE INDEX spaces_gix ON spaces USING GIST (geom);

-- Muros con espesor (un muro puede ser MultiPolygon si te viene mejor)
CREATE TABLE walls (
  id        serial PRIMARY KEY,
  floor_id  int NOT NULL,
  geom      geometry(MultiPolygon, 25830) NOT NULL
);
CREATE INDEX walls_gix ON walls USING GIST (geom);

-- Huecos: puertas y ventanas (mismo tipo geométrico, distinto uso)
CREATE TABLE openings (
  id        serial PRIMARY KEY,
  floor_id  int NOT NULL,
  kind      text NOT NULL CHECK (kind IN ('door','window')),
  sill_m    numeric,     -- altura alféizar (ventana) o umbral (puerta)
  head_m    numeric,     -- dintel
  width_m   numeric,     -- opcional
  geom      geometry(Polygon, 25830) NOT NULL
);
CREATE INDEX openings_gix ON openings USING GIST (geom);
```

> Puedes mantener `stairs/ramps` en `spaces.kind` o en tablas separadas. Mantenerlos como `spaces` simplifica mucho.

---

### 4) Ventanas: cómo integrarlas

* **Concepto**: son **openings** dentro de `walls`, con `kind='window'`, y **tocan** la frontera de un `space`.
* **Atributos clave**: `sill_m` y `head_m` te dan la banda vertical que ocupa.
* **Relaciones útiles**:

  * Ventanas a **exterior**: el opening no toca un segundo `space` → el “otro lado” es `exterior`.
  * Ventanas **interiores**: el opening toca dos `spaces` (adyacencia visual/sonora entre ellos).

Consultas típicas:

```sql
-- Ventanas de una sala
SELECT o.*
FROM openings o
JOIN spaces s ON s.floor_id=o.floor_id
WHERE o.kind='window' AND ST_Touches(o.geom, s.geom) AND s.id=:room_id;

-- ¿Esa ventana da a exterior o a otra sala?
WITH hits AS (
  SELECT o.id AS win_id, s.id AS room_id
  FROM openings o JOIN spaces s
    ON o.kind='window' AND s.floor_id=o.floor_id AND ST_Touches(o.geom, s.geom)
)
SELECT win_id,
       CASE WHEN COUNT(*)=1 THEN 'exterior'
            WHEN COUNT(*)=2 THEN 'interior'
       END AS target
FROM hits
GROUP BY win_id;
```

---

### 5) Puertas y conectividad horizontal (misma planta)

Derivamos pares de salas conectadas por **puertas** (sin solapes, solo contacto de bordes):

```sql
-- 1) Comprobar: cada opening está cubierto por exactamente un muro
WITH cover AS (
  SELECT o.id
  FROM openings o JOIN walls w
    ON o.floor_id=w.floor_id AND ST_CoveredBy(o.geom, w.geom)
  GROUP BY o.id
  HAVING COUNT(*)=1
)
-- 2) Contacto opening–space (longitud de borde compartido)
, touch AS (
  SELECT o.id AS opening_id, o.kind, s.id AS space_id,
         ST_Length(ST_Intersection(ST_Boundary(o.geom), ST_Boundary(s.geom))) AS contact_len
  FROM openings o
  JOIN spaces  s ON s.floor_id=o.floor_id
  WHERE ST_Touches(o.geom, s.geom)
)
-- 3) Conectividad por puertas: exactamente dos espacios con contacto suficiente
CREATE MATERIALIZED VIEW space_connectivity AS
SELECT t1.opening_id AS door_id,
       LEAST(t1.space_id, t2.space_id)  AS space_a,
       GREATEST(t1.space_id, t2.space_id) AS space_b
FROM touch t1
JOIN touch t2 ON t1.opening_id=t2.opening_id AND t1.space_id<t2.space_id
JOIN openings o ON o.id=t1.opening_id AND o.kind='door'
JOIN cover    c ON c.id=o.id
WHERE t1.contact_len>0.02 AND t2.contact_len>0.02;  -- >2 cm (ajusta tolerancia)
```

---

### 6) Escaleras y rampas (conexión vertical)

#### En el plano (2D)

* Modela **escaleras** y **rampas** como `spaces.kind IN ('stair','ramp')` en **cada planta**.
* Las conexiones **entre plantas** se representan en una tabla de **aristas verticales**:

```sql
CREATE TABLE vertical_edges (
  id serial PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN ('stair','ramp','elevator')),
  from_space_id int NOT NULL,  -- space de planta N (p.ej. ojo de escalera / rellano)
  to_space_id   int NOT NULL,  -- space de planta N±1
  rise_m        numeric,       -- subida (Δz)
  run_m         numeric,       -- desarrollo horizontal (rampa)
  cost_s        numeric        -- coste de paso (tiempo) para enrutar
);
```

**Cómo poblarla automáticamente:**

* Para cada `stair/ramp` en planta N y su homóloga en N±1, enlázalas si sus **proyecciones se solapan** (misma “caja” en planta) y las cotas casan (`z_top_m` con `z_base_m` del nivel superior).
* El `cost_s` puedes calcularlo con una función:

  * escalera: `cost = t_espera + (n_peldaños * tiempo_por_peldaño)`.
  * rampa: `cost = run_m / velocidad_media` y además calcula **pendiente** `slope = rise_m / run_m`.

Ejemplo de extracción (muy simplificada):

```sql
-- Encontrar solapes verticales entre espacios 'stair' de plantas consecutivas
WITH stairs AS (
  SELECT id, floor_id, geom, z_base_m, z_top_m
  FROM spaces WHERE kind='stair'
)
INSERT INTO vertical_edges (kind, from_space_id, to_space_id, rise_m, cost_s)
SELECT 'stair', a.id, b.id, (b.z_base_m - a.z_base_m) AS rise_m,
       GREATEST(0.0, (b.z_base_m - a.z_base_m)) * 1.2  -- 1.2 s por peldaño ~ 0.17 m
FROM stairs a
JOIN stairs b
  ON b.floor_id = a.floor_id + 1
 AND ST_Intersects(a.geom, b.geom)
WHERE b.z_base_m > a.z_base_m;
```

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

Si quieres, te dejo un **script completo** con las vistas materializadas, triggers de validación (para que no se inserte una puerta fuera de un muro) y un ejemplo mínimo con 2 plantas, una escalera y una rampa.

---
