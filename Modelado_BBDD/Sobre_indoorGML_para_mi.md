# IndoorGML

Es eso del estandar para modelo de datos de interiores como un vocubulario comun y tal.

## Esta indicado para este tipo de proyectos.

| Dominio                             | Cómo se usa IndoorGML                                                                                      |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Navegación indoor**               | Cálculo de rutas multi-planta, señalización accesible (PMR, sillas de ruedas), “blue-dot” en apps móviles. |
| **Gestión de instalaciones (FM)**   | Inventario espacial normalizado; vinculación con sensores IoT para mantenimiento predictivo.               |
| **Robótica y drones**               | Grafo de navegación semántico que se inyecta en ROS; facilita planificación y SLAM semántico.              |
| **Emergencias / seguridad pública** | Pre-planos para primeros respondedores (véase el Pilot de NIST-OGC).                                       |
| **AR/VR y *digital twins***         | Sincroniza la maqueta 3D, la topología y la base de activos en un único formato intercambiable.            |

A mi me interesa el primero de todos Navegación Indoor.

## Lo que implica para mi el estandar OGC IndoorMGL

| Aspecto                   | Sin adoptar el estándar                                            | Adoptando (total o parcialmente) IndoorGML 2.0                                                            |
| ------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| **Interoperabilidad**     | Tu esquema es único; necesitarás ETL ad-hoc para cada app externa. | Exportar/ importar con cualquier software que hable IndoorGML (FME, 3D-Tiles, QGIS plugins…).             |
| **Cobertura semántica**   | Sólo lo que hayas previsto en tu diseño.                           | Ganas clases y atributos consolidados para topología, accesibilidad, PoIs, multilayer…                    |
| **Curva de aprendizaje**  | Baja (ya la dominas).                                              | Debes leer la especificación y mapear tablas → clases.                                                    |
| **Valor académico (TFG)** | Correcto si el jurado valora la solución “casera”.                 | Plus por alinearte con un estándar OGC emergente; muestra rigor, comparabilidad y proyección profesional. |

Adoptar paricalmente este estandar es la mejor idea, no en su totalidad, la idea será alinear mi trabajo con el suyo.

## ¿Conviene?

| Situación                                                                                   | Recomendación                                                                                                 |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Proyecto corto, sin intercambio externo y con fecha límite inminente.                       | Adopta **“IndoorGML-lite”**: `CellSpace` + `Node/Edge` y deja reflejado un roadmap para el resto.             |
| Proyecto que aspira a ser usado/extendido por terceros (universidad, empresa, open source). | Implementa IndoorGML 2.0 completo (al menos Core + Navigation) y documenta tu **ETL**.                        |
| TFG enfocado a innovación/ investigación.                                                   | Incluir FSS y multilayer te da **originalidad** y abre líneas futuras (robótica, evacuación, análisis AR/VR). |

El primer de todos es la opción, adoptar Solo una parte y lo demas dejarlo en un roadmap, como futuras inclusiones.

## Preguntas

| Pregunta                         | Respuesta breve                                                                                                   |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **¿Añade valor académico?**      | Sí. Mostrar que tu BD se **alinea con un estándar OGC** puntúa en rigor y proyección profesional.                 |
| **¿Cuánto esfuerzo extra?**      | Si ya guardas edificios, salas y puertas, mapeas el 80 % con un *view* SQL + exportador GML.                      |
| **¿Tengo que adoptarlo entero?** | No. Puedes implementar sólo el *Core* (celdas + grafo) y declarar “compatible con FSS” para futuras mejoras.      |
| **¿Qué gano a largo plazo?**     | Intercambio inmediato con FME, flujos BIM (IFC) y con cualquier cliente que pida IndoorGML —sin reescribir tu BD. |

Con esto añado valor académico al proyecto.

## Aporte al TFG

| Beneficio concreto               | Qué aportaría al TFG                                                                         |
| -------------------------------- | -------------------------------------------------------------------------------------------- |
| **Interoperabilidad** automática | Tu BD podría exportarse/importarse con QGIS, FME, NavVis, etc., sin transformaciones ad-hoc. |
| **Topología “ya hecha”**         | El grafo que usas para rutas encaja 1-a-1 con las clases `Node` y `Edge` del estándar.       |
| **Rigor académico**              | Referenciar un estándar OGC demuestra que el trabajo sigue buenas prácticas consolidadas.    |
| **Escalabilidad**                | Si mañana añades sensores, mobiliario o accesibilidad, IndoorGML ya tiene dónde guardarlo.   |

## Inconvenientes

| Desafío                  | Impacto                                                                                               |
| ------------------------ | ----------------------------------------------------------------------------------------------------- |
| **Curva de aprendizaje** | Entender la especificación (≈ 80 páginas) y su esquema XML.                                           |
| **Overhead de ETL**      | Mapear tus tablas a `CellSpace`, `Node`, `Edge` y generar el .gml (unas semanas si partes de cero).   |
| **Evolución 2.0**        | La nomenclatura cambia (`State→Node`, etc.); si implementas ahora la 1.1 tendrás que renombrar luego. |

## Opciones

| Opción                           | ¿Qué harías ahora?                                                                              | Ventajas                                                                                     | Riesgos                                                                 |
| -------------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **A. “Mínimo viable IndoorGML”** | 1. Exportar sólo `CellSpace` + `Node/Edge`.<br>2. Documentar cómo se añadiría FSS en el futuro. | Ganas interoperabilidad y puntos académicos sin retrasar la entrega.                         | Ajustar tu BD y escribir un script de exportación.                      |
| **B. “Lo menciono y listo”**     | 1. Describir IndoorGML en el estado-del-arte.<br>2. Dejar la adopción como línea futura.        | Cero tiempo de desarrollo ahora; evitas apostar por una versión que está a punto de cambiar. | Pierdes la oportunidad de enseñar resultados exportables y comparables. |

Va a ser la opción A

## Ayuda para los cambios

| Concepto IndoorGML | Función                                                                                                                  | Por qué no basta con una sola tabla `AREAS`                                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **CellSpace**      | La *región física* (polígono 2 D / sólido 3 D).                                                                          | Aquí guardas geometría, uso (“aula”, “pasillo”), planta, etc.                                                                                                |
| **Node**           | El *nodo lógico* del grafo dual que “resume” una `CellSpace`. Normalmente es el **centroide** o un punto representativo. | Permite calcular rutas sin cargar polígonos complejos y soporta que una misma celda tenga varios nodos (p. ej. dos puertas).                                 |
| **Edge**           | La *arista* que une dos `Node`; modela la posibilidad de pasar de una celda a otra.                                      | Si hoy tu tabla `EDGE` apunta directamente a dos `AREAS`, te saltas la dualidad y pierdes flexibilidad (por ejemplo, varias puertas entre las mismas salas). |

```sql
-- 1. Tabla original (renombrada o vista) -----------------------------
CREATE TABLE cellspace (
  cell_id       SERIAL PRIMARY KEY,
  name          TEXT,
  usage         TEXT,          -- aula, lab, pasillo…
  floor         INTEGER,
  geom          geometry(Polygon, 3857)
);

-- 2. Nuevo nodo dual --------------------------------------------------
CREATE TABLE node (
  node_id       SERIAL PRIMARY KEY,
  cell_id       INTEGER NOT NULL REFERENCES cellspace(cell_id),
  point_geom    geometry(Point, 3857)  -- centroide o puerta principal
);

-- 3. Aristas entre nodos ---------------------------------------------
CREATE TABLE edge (
  edge_id       SERIAL PRIMARY KEY,
  node_from     INTEGER NOT NULL REFERENCES node(node_id),
  node_to       INTEGER NOT NULL REFERENCES node(node_id),
  cost          FLOAT,         -- longitud, tiempo, penalización…
  geometry      geometry(LineString, 3857)
);

-- 4. Dualidad explícita (1-a-muchos) ----------------------------------
ALTER TABLE node
  ADD CONSTRAINT uk_node_cell UNIQUE (cell_id, node_id);
```

## Ventajas

| Ventaja                             | Con este esquema nuevo                                                                                                                    |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Compatibilidad IndoorGML 1.1**    | Basta exportar las tres vistas.                                                                                                           |
| **Preparado para 2.0**              | Cuando cambien los nombres (`node`/`edge` ya son definitivos) solo ajustas las etiquetas XML, no la BD.                                   |
| **pgRouting out-of-the-box**        | `edge(node_from, node_to, cost)` es la firma estándar de pgRouting.                                                                       |
| **Apoyo a puertas múltiples / FSS** | Podrás asignar varios nodos a un `CellSpace` (puertas) y, más adelante, descomponer la geometría en `O-/F-/R-Space` sin cambiar el grafo. |

### 7 | Checklist para tu TFG Renombrar/crear tablas cellspace, node, edge.
- Script de migración desde AREAS y old_edge.
- Vistas de exportación a GML.
- Documentar: “La BD sigue el núcleo IndoorGML; FSS y capas temáticas quedan como trabajo futuro”.
- (Opc.) Demo de pgRouting que aproveche el nuevo grafo.

## Sobre el DOOR-TO-DOOR

### 1. ¿Puedo sacar un grafo “normal” con **Node + Edge**?

Sí.
IndoorGML (≥ 1.1) ya incluye el **grafo dual**:

* `Node` (`State` en 1.1) = punto representativo de una celda.
* `Edge` (`Transition` en 1.1) = conexión que atraviesa la frontera física entre dos celdas.

En la práctica basta extraer las tablas / vistas `node` y `edge` (o sus equivalentes en tu BD) y usarlas directamente en pgRouting o NetworkX. La propia especificación indica que esas aristas pueden llevar geometría y pesos (distancia, tiempo, accesibilidad) ([mdpi.com][1]).

---

### 2. ¿Y un grafo donde **los nodos sean las puertas** (Door-to-Door)?

IndoorGML **no lo trae “de fábrica”**, pero **lo contempla** como *otra capa de interpretación*:

* El documento estándar describe un **door-to-door layer** que se genera sobre el topographic layer para calcular distancias “puerta-a-puerta” ([mdpi.com][1]).
* La idea es **invertir** el grafo dual:

  | Convención habitual | Capa Door-to-Door                                                     |
  | ------------------- | --------------------------------------------------------------------- |
  | `Node` → celda      | **nodo = puerta** (`Transition`/`CellBoundary` con semántica “door”)  |
  | `Edge` → puerta     | **arista = trayecto dentro de la misma celda** que enlaza dos puertas |

#### Cómo derivarlo en PostGIS

```sql
-- 1. Puertas → nodo del nuevo grafo
CREATE TABLE door_node AS
SELECT t.transition_id AS door_id,
       ST_StartPoint(t.geometry) AS geom   -- o el punto medio
FROM   transition t
WHERE  t.type = 'door';

-- 2. Aristas = pares de puertas que caen en la misma celda
CREATE TABLE door_edge AS
SELECT row_number() OVER ()        AS edge_id,
       d1.door_id                  AS door_from,
       d2.door_id                  AS door_to,
       ST_Length(
          ST_ShortestLine(d1.geom, d2.geom)
       )                           AS cost,
       ST_MakeLine(d1.geom, d2.geom) AS geom
FROM   door_node d1
JOIN   cellspace_boundary cb
       ON cb.transition_id = d1.door_id
JOIN   cellspace cs
       ON cs.cell_id = cb.left_cell          -- puerta “pertenece” a esta celda
JOIN   door_node d2
       ON d2.door_id <> d1.door_id
       AND EXISTS (                          -- misma celda
           SELECT 1
           FROM cellspace_boundary cb2
           WHERE cb2.transition_id = d2.door_id
             AND cb2.left_cell = cs.cell_id
       );
```

En ese `door_edge` ya tienes la topología **puerta-a-puerta** con un coste geométrico (`cost`) listo para `pgr_dijkstra()`.

> *Tip*: si tu celda es grande (p. ej. un pasillo), puedes densificar la línea central y medir la distancia real sobre la polilínea en lugar de la línea recta.

---

### 3. Empaquetarlo de nuevo como IndoorGML

IndoorGML permite múltiples *space layers*. Así que:

1. Conserva tu capa original (topographic + dual).
2. Crea una **`DoorToDoorLayer`**:

   * `PrimalSpaceLayer`: si quieres, NO tiene geometría porque las puertas ya son suficientes.
   * `DualSpaceLayer`: nodos = `door_node`, aristas = `door_edge`.
3. Añade una `layer.theme` = `"DOOR_TO_DOOR"` para que clientes sepan qué están leyendo.

---

### 4. Ventajas y cuándo usarlo

| Door-to-Door                                                        | Cuando interesa                              | Por qué                                                         |
| ------------------------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------- |
| **Rutas muy precisas** (distinguir varias puertas de la misma sala) | Aeropuertos, hospitales, centros comerciales | Evita ambigüedades (“usa la puerta norte de la tienda”).        |
| **Cálculo de distancias métricas exactas**                          | Logística interna (robots, AGV)              | La arista mide realmente la longitud del pasillo entre puertas. |
| **Integrar puertas inteligentes / sensores**                        | Edificios con control de acceso              | Cada nodo-puerta se puede “desactivar” si está cerrada.         |

Si tu aplicación sólo necesita saber “qué sala viene después”, el grafo `Node`/`Edge` clásico es suficiente. Pero si la puerta concreta importa (accesos, evacuación, control de flujos), el **door-to-door layer** marca la diferencia.

---

### 5. Pasos mínimos para tu TFG

1. **Añade columna `is_door`** o `type='door'` en tu `transition`.
2. Genera `door_node` y `door_edge` con el SQL anterior (o en Python con GeoPandas/NetworkX).
3. Exporta esa capa extra usando vistas `v_door_node_gml`, `v_door_edge_gml` y el driver **GMLAS**.
4. Documenta que el modelo ya soporta dos grafos:

   * **Cell-to-Cell** (core IndoorGML).
   * **Door-to-Door** (capa temática adicional recomendada en la literatura).

Así demuestras que tu base de datos **exprime** IndoorGML para casos de uso avanzados sin dejar de ser estándar.

[1]: https://www.mdpi.com/2220-9964/6/4/116 "A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches"

## terminologia que me interesa de DTD y RTR.

DTD: Door-to-Door
RTR: Room-to-Room

### 1. La terminología que verás en los papers

| Término habitual                                | Cómo encaja en IndoorGML 1.1 (y 2.0)                                                                                                                                                                                              | Idea clave                                                                |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **Room-to-Room graph** (también *cell-to-cell*) | **Topographic Layer**<br>• Primal = `CellSpace` (polígonos de salas, pasillos…) <br>• Dual  = `Node` / `Edge` (un nodo por celda, una arista por puerta)                                                                          | Sirve para navegación básica “¿a qué sala voy después?”                   |
| **Door-to-Door graph**                          | **Otro Space Layer** dentro del mismo edificio, normalmente con *theme* = `ACCESS_POINT` o nombre similar. <br>• Primal = las propias puertas (opcional)<br>• Dual  = `Node` = puertas, `Edge` = trayecto dentro de la misma sala | Da rutas de alta precisión: “entra por la puerta norte y sal por la sur”. |
| **Thematic Layer** (IndoorGML 2.0)              | Contenedor que **agrupa un par** «primal+dual» y le pone una etiqueta `theme` (`TOPOGRAPHIC`, `FUNCTIONAL`, `DOOR_TO_DOOR`…)                                                                                                      | Cada interpretación (resolución o propósito) queda auto-contenida.        |

➜ **Conclusión rápida**: *Room-to-Room* y *Door-to-Door* son **dos capas distintas**. No importa que sus nodos y aristas **no coincidan**; la norma prevé enlazarlas con `InterLayerConnection`. ([indoorgml.net][1], [mdpi.com][2])

---

### 2. ¿Por qué NO comparten nodos ni aristas?

1. **Diferente unidad semántica**
   *Topographic* trata las salas como “átomos” de movimiento; *Door-to-Door* trata la puerta como átomo.
2. **Diferente granularidad**
   Cada capa optimiza un problema: la primera simplifica el grafo, la segunda maximiza la exactitud métrica y permite puertas múltiples por sala.
3. **Independencia de mantenimiento**
   Si cierras una puerta por obras, sólo actualizas el *Door-Layer*; la capa de salas (topographic) sigue válida.

> *¿Y si necesito relacionarlas?*
> Usas `InterLayerConnection` para decir, por ejemplo, «la puerta D17 pertenece a la celda C42». El algoritmo de la Univ. de Keimyung muestra precisamente ese salto entre capas para calcular la distancia punto-a-punto: topographic → puerta inicial → grafo D2D → puerta final → topographic ([mdpi.com][2]).

---

### 3. Cómo lo describen los artículos

| Cita típica                                                                                                              | Traducción práctica                                                                         |
| ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| “**Door-to-Door layer graph** is generated by connecting doors within the same cell” ([mdpi.com][2])                     | Nuestra `door_edge` que une cada par de puertas de una sala.                                |
| “Multi-Layered Space Model integrates the topographic and the D2D layers via inter-layer relations” ([indoorgml.net][1]) | En IndoorGML: `<interLayerConnection xlink:href="#door_D17" xlink:href="#cell_C42"/>`.      |
| “A space may have several decompositions depending on application requirements” ([docs.ogc.org][3])                      | Exactamente el motivo por el que tu proyecto puede llevar **dos** grafos sin mezclar nodos. |

---

### 4. Cómo quedaría en tu base de datos

```
cellspace  (C42, geom)            -- rooms/pasillos
door_node  (D17, cell_id=C42, geom)
door_edge  (E99, door_from=D17, door_to=D18, cost)

-- inter-layer link (opcional)
CREATE TABLE ilc_cell_door (
  cell_id  INT REFERENCES cellspace,
  door_id  INT REFERENCES door_node,
  PRIMARY KEY(cell_id, door_id)
);
```

* `cellspace` + su grafo `node/edge` = **Layer 1** (`TOPOGRAPHIC`)
* `door_node` + `door_edge`           = **Layer 2** (`ACCESS_POINT`)
* `ilc_cell_door`                      = `InterLayerConnection`

Sin mezclar ids; cada capa mantiene su lógica.

---

### 5. Cómo lo contarías en tu memoria/TFG

> *«El modelo implementa dos **ThematicLayers** IndoorGML:
> (i) un layer `TOPOGRAPHIC` con grafo **Room-to-Room** para navegación general,
> (ii) un layer `DOOR_TO_DOOR` donde los nodos son puertas y las aristas describen trayectos intra-sala.
> Ambos layers se enlazan mediante `InterLayerConnection` para resolver rutas que combinen ambos niveles de detalle.»*

Con esto das evidencia de que entiendes la arquitectura de IndoorGML y puedes justificar por qué **no** necesitas duplicar nodos/aristas ni forzar que coincidan.

---

#### Puntos clave para no perderse

1. **Layer ≠ theme** en 1.1 — pero en 2.0 cada layer *sí* lleva un `theme`.
2. **Capas independientes**, conectadas sólo cuando hace falta.
3. **Room-graph rápido** para la mayoría de rutas; **Door-graph preciso** cuando importan las puertas.
4. **Nada impide añadir más capas** (sensor, accesibilidad, mobiliario…), todas convivirán gracias al Multi-Layered Space Model.

Así de sencillo (y flexible) lo describe la literatura, y así lo puedes trasladar a tu base de datos sin complicarte.

[1]: https://www.indoorgml.net/?utm_source=chatgpt.com "IndoorGML OGC"
[2]: https://www.mdpi.com/2220-9964/6/4/116 "A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches"
[3]: https://docs.ogc.org/is/19-011r4/19-011r4.html?utm_source=chatgpt.com "OGC® IndoorGML 1.1"

## sobre las demas capas de mobilidad

Aqui se supone que habria mas cosas? se quedo asi


