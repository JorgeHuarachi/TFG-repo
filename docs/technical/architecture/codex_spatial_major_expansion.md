# Gran ampliación de SpatialEngine e Indoor Data Model

## Naturaleza de la tarea

Implementa una ampliación mayor y coherente de SpatialEngine y del Indoor Data Model.

No quiero un plan separado ni una respuesta únicamente conceptual. Analiza el código real y aplica los cambios, trabajando internamente por fases y ejecutando los criterios de aceptación después de cada fase.

Este es un cambio grande. No debes intentar resolverlo mediante parches aislados dentro de la clase actual. Se permite crear módulos nuevos para separar:

- estado de autoría;
- detección automática de espacios;
- descomposición geométrica;
- conectores verticales;
- vistas derivadas de grafos;
- validación;
- visualización multinivel.

## Archivos de referencia obligatorios

Lee primero:

- `docs/technical/architecture/indoor_data_model_architecture.md`
- `schemas/indoor/indoor_model.schema.json`
- `schemas/indoor/scenario_model.schema.json`
- `src/MLSM_SpatialEngine.py`
- `src/indoor_data_model/builder.py`
- `src/indoor_data_model/geometry.py`
- `src/indoor_data_model/ids.py`
- `tools/visualize_indoor_model.py`
- `tests/test_indoor_wall_junctions.py`
- `indoorjson.core.schema.json`
- `indoorjson.navi.schema.json`

Si falta cualquiera de los archivos principales del proyecto, detente y señala exactamente cuál falta.

## Restricciones absolutas

No modifiques:

- `src/MLSM_EvacEngine.py`
- `tools/visualize_mlsm_v2.py`
- schemas MLSM legacy
- examples MLSM legacy
- `requirements.txt`

No elimines exportadores legacy todavía.

No hagas commit.

No crees PR.

No añadas dependencias nuevas.

Utiliza únicamente dependencias ya presentes, principalmente:

- Python estándar;
- Shapely;
- Matplotlib;
- NumPy.

No generes outputs para versionar.

No rompas los tests actuales de junctions.

No reescribas el algoritmo de junctions que actualmente funciona salvo que un cambio sea estrictamente necesario para integrarlo con niveles.

## Objetivo funcional final

SpatialEngine debe permitir:

1. Dibujar uno o varios niveles.
2. Detectar automáticamente espacios cerrados.
3. Dividir automáticamente espacios cóncavos o con huecos mediante virtual boundaries.
4. Mantener virtual boundaries manuales.
5. Dibujar ventanas.
6. Dibujar columnas como ObjectSpace.
7. Dibujar escaleras, rampas y ascensores.
8. Representar conectores dentro de un nivel y entre niveles.
9. Generar primal y dual para todos los niveles.
10. Derivar y visualizar:
    - room adjacency;
    - room-transfer connectivity;
    - door-to-door.
11. Deshacer y rehacer operaciones completas.
12. Visualizar niveles individualmente sin superposición.
13. Exportar un `indoor_model.json` válido.

---

## Aclaraciones tras comprobacion manual

Estas notas corrigen ambigüedades detectadas durante una primera ronda de implementación y uso manual. La siguiente ronda debe considerarlas requisitos, no sugerencias:

* Escaleras, rampas y ascensores: la dirección buena es la autoría pensada como conectores, no como rectángulos libres sin semántica. Escaleras y rampas deben poder dibujarse como una sucesión de cuadrados/tiles estándar, con entrada y salida seleccionables mediante flechas. Los ascensores deben poder replicar su footprint en la misma XY al cambiar de planta.
* La detección automática con `f` debe poder ejecutarse en cualquier momento y nunca debe borrar ni ocultar definitivamente lo ya dibujado: muros, puertas, ventanas, columnas, escaleras, rampas, ascensores, conectores y virtual boundaries manuales deben seguir visibles y presentes tras detectar espacios.
* Las `VirtualBoundary` son navegables, pero deben seguir siendo líneas 1D. No deben convertirse en `CellSpace`, `TransferSpace` ni geometría 2D con grosor. Si hace falta un punto de transferencia en el dual, usar un nodo lógico en el punto medio de la línea, no un polígono fino.
* La cobertura no navegable alrededor de escaleras/rampas/ascensores debe generarse como contorno coherente: esquinas cerradas en una única esquina limpia, sin huecos, sin picos colgantes/dobles y sin solapes con muros ni con el propio conector.
* Las vistas de grafo son parte de la depuración visual. Deben poder verse `base_dual`, `room_adjacency`, `room_transfer_connectivity`, `door_to_door` y `vertical_connectivity`, porque en la vista "all" puede no apreciarse si el grafo está bien.
* La UI actual puede mantenerse simple, pero debe ser más explícita: ayuda/tutorial con teclas, estado de modo, nivel activo, scope del conector, lado entry/exit seleccionado y previsualización fluida mientras se dibuja.

---

# Fase 0 — Protección del estado estable

Antes de modificar:

```powershell
python -m unittest discover -s tests -v
````

Registra el resultado inicial.

Los siguientes comportamientos deben conservarse:

* junctions L, V, T y X;
* ausencia de solapes relevantes;
* puertas y salidas host-aware;
* WallSegment y WallJunction;
* edge mode `navigation`;
* edge mode `all_adjacency`;
* export automático;
* autovisualización;
* export con timestamp.

No cambies el resultado de los junctions arbitrarios sin tests que demuestren que sigue siendo correcto.

---

# Fase 1 — Modelo de autoría multinivel

## 1.1. Separar estado de autoría

Crea un paquete, si no existe:

```text
src/indoor_authoring/
├── __init__.py
├── model.py
├── history.py
├── space_detection.py
├── space_decomposition.py
└── connectors.py
```

Usa dataclasses o estructuras tipadas para representar como mínimo:

```text
BuildingAuthoringState
LevelAuthoringState
AuthoringLineElement
AuthoringAreaElement
DetectedSpace
VirtualBoundary
VerticalConnector
ConnectorEndpoint
```

`BuildingAuthoringState` debe contener:

* building/project ID;
* colección ordenada de niveles;
* nivel activo;
* conectores verticales;
* configuración;
* historial.

`LevelAuthoringState` debe contener:

* wall centerlines;
* doors;
* exits;
* windows;
* manual virtual boundaries;
* automatic virtual boundaries;
* columns/ObjectSpaces;
* manual spaces opcionales;
* detected spaces;
* atributos semánticos.

## 1.2. Compatibilidad temporal

El código actual usa:

```text
self.muros
self.hitos
self.hitos_bounds
self.propiedades_zonas
self.agentes
```

No mantengas esas estructuras como fuente principal.

Puedes conservar aliases o propiedades temporales para no romper exportadores legacy, pero la nueva fuente de verdad debe ser el modelo de autoría tipado y multinivel.

## 1.3. Niveles

Inicializa siempre:

```text
LEVEL_00
```

No preguntes al inicio cuántas plantas tendrá el edificio.

Permite añadir niveles dinámicamente.

Cada nivel debe tener:

```text
id
name
order
elevationM
heightM
spatialExtent2D
```

Atajos propuestos:

```text
+ o =     añadir nivel
[         nivel anterior
]         nivel siguiente
```

Cuando se cambia de nivel:

* limpiar temporales;
* redibujar solo el nivel activo;
* mostrar el nivel actual en título y ayuda;
* mantener el resto de niveles en memoria;
* no superponerlos.

Permite opcionalmente mostrar como ghost únicamente footprints de conectores verticales relacionados.

## 1.4. ThematicLayer por nivel

Para este perfil de proyecto, crea una `ThematicLayer` física por nivel:

```text
TL_NAV_L00
TL_NAV_L01
...
```

Cada una contiene:

```text
PrimalSpaceLayer
DualSpaceLayer
```

Las conexiones entre niveles deben ir en:

```text
layerConnections
```

o en la extensión equivalente admitida por el schema actualizado.

Genera IDs dinámicamente. Elimina los hardcodes globales:

```text
LEVEL_ID
LEVEL_CODE
LAYER_ID
PRIMAL_ID
DUAL_ID
```

---

# Fase 2 — Undo/redo transaccional

El undo actual depende del modo activo y no elimina siempre todas las estructuras asociadas.

Sustitúyelo por historial de operaciones o snapshots.

## Requisitos

* `z`: undo de la última operación completa.
* `y`: redo.
* Cada operación de autoría debe ser una transacción:

  * muro;
  * opening;
  * columna;
  * virtual boundary;
  * nivel;
  * detección automática de espacios;
  * conector vertical.
* Restaurar:

  * geometrías;
  * metadatos;
  * contadores;
  * detected spaces;
  * virtual boundaries automáticas;
  * conectores;
  * nivel activo.

La operación de autodetección completa debe poder deshacerse con una sola pulsación.

Usa `copy.deepcopy` para snapshots si resulta suficientemente claro y estable. La prioridad es corrección antes que microoptimización.

---

# Fase 3 — Detección automática de espacios

## 3.1. Nuevo flujo

Añade:

```text
detect_spaces(level_id)
detect_all_levels()
```

Atajo:

```text
f = detectar/regenerar espacios del nivel activo
```

Requisito confirmado por uso manual:

* `f` debe poder pulsarse antes o después de dibujar puertas, ventanas, columnas, escaleras, rampas, ascensores y virtual boundaries.
* `f` solo puede sustituir/regenerar los `detected_spaces`, las virtual boundaries automáticas derivadas de esa detección y el reporte de detección.
* `f` no debe borrar, ocultar ni recrear destructivamente elementos de autoría manual ya dibujados.
* Después de detectar espacios, la ventana debe seguir mostrando los elementos de autoría junto con el overlay de espacios detectados. El mensaje "X espacios detectados" no debe implicar que lo demás haya desaparecido.
* La detección debe restar obstáculos y conectores al calcular `GeneralSpace`, pero no debe eliminar los objetos de autoría originales.
* La operación completa de detección debe ser una transacción de undo/redo.

Al exportar:

* si un nivel no tiene espacios detectados;
* o si su geometría está marcada como dirty;

ejecutar detección automáticamente antes del builder.

Mantén `h` como modo manual opcional, pero la ruta principal será automática.

## 3.2. Linework de detección

Usa las centerlines de autoría, no los footprints derivados.

El linework debe incluir:

* muros exteriores;
* muros interiores;
* virtual boundaries manuales;
* virtual boundaries automáticas aceptadas.

Las puertas, ventanas y salidas no deben abrir el linework usado para detectar recintos. El muro hospedador sigue actuando como línea separadora durante `polygonize`.

Utiliza:

```python
shapely.ops.unary_union
shapely.ops.polygonize_full
```

Analiza y reporta:

* polygons;
* dangles;
* cuts;
* invalid rings.

## 3.3. Exterior del edificio

Deriva el shell interior a partir de muros exteriores cerrados.

No conviertas el exterior infinito en espacio.

Filtra los polígonos detectados mediante representative points y el shell del edificio.

Si el contorno exterior no está cerrado:

* no inventar espacios;
* mostrar error claro;
* conservar el estado anterior.

## 3.4. Geometría final

Para cada face detectada:

```text
GeneralSpace =
    face
    - wall mass
    - ObjectSpace
    - TransferSpace
```

Los footprints de escaleras, rampas, ascensores y su cobertura lateral no navegable deben participar como obstáculos/zonas recortadas al construir `GeneralSpace`. Esto permite que el grafo conecte con la entrada real del conector, en vez de atravesar el cuerpo de una escalera o rampa.

No permitir solapes entre CellSpaces.

No permitir geometrías inválidas.

No exportar slivers por debajo de una tolerancia razonable.

---

# Fase 4 — Virtual boundaries automáticas y descomposición

## 4.1. Objetivo

Dividir automáticamente espacios irregulares:

* L;
* T;
* U;
* H;
* O;
* formas con huecos;
* polígonos cóncavos;
* formas diagonales cóncavas.

Las piezas resultantes deben ser más simples para:

* primal;
* dual;
* routing;
* validación;
* persistencia.

## 4.2. Prioridades

1. Las virtual boundaries manuales son obligatorias y tienen prioridad.
2. Después se generan boundaries automáticas.
3. Las boundaries automáticas no son muros.
4. Por defecto son atravesables.
5. Deben generar:

   * `CellBoundary`;
   * `isVirtual: true`;
   * `NavigableBoundary`;
   * Edge de connectivity entre las celdas resultantes.

## 4.2.1. Semántica obligatoria de VirtualBoundary

Una `VirtualBoundary` es una frontera topológica navegable, no un espacio físico:

* debe almacenarse y visualizarse como línea 1D;
* no debe exportarse como `CellSpace`;
* no debe exportarse como `TransferSpace`;
* no debe tener footprint 2D, grosor artificial ni buffer fino;
* no debe generar solapes ni micro-contactos por tener área;
* debe poder dividir/delimitar `GeneralSpace`;
* por defecto debe ser atravesable.

Si el `DualSpace` o una vista derivada necesita representar el cruce de una virtual boundary, crear como mucho un nodo lógico puntual en el punto medio de la línea y dos edges hacia las celdas vecinas. Ese nodo lógico puede aparecer en vistas de grafo como `VirtualTransfer`, pero no debe tener geometría 2D en el primal.

## 4.3. Polígonos ortogonales

Para polígonos ortogonales:

1. Simplificar vértices colineales.
2. Detectar reflex vertices.
3. Generar candidatos de corte desde cada reflex vertex.
4. Proyectar hacia la boundary visible más cercana.
5. Rechazar cortes que:

   * salgan del polígono;
   * crucen huecos;
   * crucen openings;
   * crucen otros cortes aceptados.
6. Elegir cortes cortos, estables y que reduzcan concavidad.
7. Dividir recursivamente hasta obtener piezas:

   * rectangulares;
   * o convexas simples.

## 4.4. Polígonos con huecos, como O

Generar bridge boundaries entre cada anillo interior y el anillo exterior:

* usar el segmento válido más corto;
* no cruzar obstáculos ni otros bridges;
* marcar:

  * `generatedAutomatically: true`;
  * `generationReason: "hole_bridge"`.

Después continuar la descomposición.

## 4.5. Polígonos no ortogonales

Usar un fallback robusto:

* triangulación;
* intersección de triángulos con el polígono original;
* filtrado;
* fusión greedy de piezas adyacentes cuando la unión siga siendo convexa/simple.

No producir fragmentación extrema.

## 4.6. Invariantes

Debe comprobarse:

```text
union(parts) ≈ original polygon
intersection.area(parts_i, parts_j) <= 1e-6
```

No debe haber:

* huecos nuevos;
* solapes;
* piezas minúsculas;
* cortes atravesando paredes;
* cortes atravesando puertas.

## 4.7. IDs persistentes

Cuando se regeneran espacios:

* intentar conservar IDs por máximo solape/IoU con las celdas previas;
* reutilizar ID cuando existe correspondencia clara;
* crear nuevo ID solo para celdas nuevas;
* no basar IDs únicamente en el orden de iteración.

---

# Fase 5 — Ventanas

Añade modo:

```text
w = ventana
```

La ventana debe:

* hacer snap a un muro;
* conservar host wall;
* usar el grosor del muro hospedador;
* cortar la masa física del muro;
* generar `TransferSpace`;
* `category: "Window"`;
* `function: "ConnectionSpace"`.

Atributos mínimos:

```text
windowType: fixed | openable | breakable
defaultTraversable: false
scenarioControllable: true
widthM
hostWallRef
sillHeightM
```

Por defecto:

* no crear edge navegable;
* sí aparecer en all adjacency;
* poder habilitarse en un escenario futuro.

No convertir una ventana fija en puerta.

---

# Fase 6 — Columnas y ObjectSpace

Añade modo:

```text
c = columna
```

Primera implementación:

* columna rectangular mediante dos esquinas;
* opcionalmente permitir dimensión por defecto.

Debe generar:

```text
ObjectSpace
category: "Column"
navigationType: "ObjectSpace"
traversable: false
```

Debe:

* restarse de GeneralSpace;
* generar Node;
* generar NonNavigableBoundary;
* no entrar en grafo de navegación normal;
* aparecer en all adjacency.

Prepara el modelo para futuros obstáculos/mobiliario sin implementarlos todos.

---

# Fase 7 — Locomotion y accesibilidad

Elimina `Step` como locomotion type principal.

Valores compatibles:

```text
Walking
Rolling
Flying
Unspecified
```

Representa escaleras y desniveles mediante atributos:

```text
requiresSteps
stepCount
wheelchairAccessible
slope
riseM
runM
maxGradient
```

Reglas:

```text
GeneralSpace normal:
    Walking, Rolling

Stair:
    Walking
    requiresSteps = true
    wheelchairAccessible = false

Ramp:
    Walking, Rolling
    slope definido

Elevator:
    Walking, Rolling
```

Actualiza schema, builder y documentación de forma coherente.

---

# Fase 8 — Conectores verticales

## 8.1. Modelo común

Escaleras, rampas y ascensores deben usar un modelo común:

```text
VerticalConnector
├── connectorType
├── scope
├── endpoints[]
├── sourceLevel
├── targetLevel
├── fromElevationM
├── toElevationM
├── directionality
├── locomotionTypes
└── attributes
```

Tipos:

```text
Stair
Ramp
Elevator
```

Scope:

```text
same_level
inter_level
```

## 8.2. Autoría

Atajos:

```text
t = escalera
r = rampa
l = ascensor
```

Decisión de UX confirmada por pruebas manuales:

* Escaleras y rampas no deben dibujarse como un rectángulo libre cualquiera.
* Deben dibujarse como una cadena de cuadrados/tiles estándar, por ejemplo de 1 m x 1 m, suficiente para representar el paso de una persona.
* Cada click añade un tile contiguo a la cadena. La cadena debe poder tener 1, 2, 3 o más tiles.
* Las flechas seleccionan el lado de entrada/salida:
  * si se pulsa una flecha antes o durante el primer tile, define `entrySide`;
  * si se pulsa una flecha antes de terminar el último tile, define `exitSide`;
  * si falta un lado obligatorio, mostrar aviso claro antes de cerrar el conector.
* `b` debe alternar claramente `same_level` / `inter_level` antes de finalizar el conector.
* La previsualización debe mostrar tiles ya fijados, tile candidato, scope actual y lado seleccionado.
* Ascensor puede seguir usando un footprint rectangular/cuadrado, pero también debe tener lado abierto entry/exit seleccionable. Para un ascensor el entry y exit pueden ser el mismo lado.

Flujo de dibujo:

### Same-level

1. Elegir `t` o `r`.
2. Elegir scope `same_level`.
3. Seleccionar `entrySide` con flecha.
4. Colocar el primer tile estándar.
5. Añadir tiles contiguos hasta representar el recorrido.
6. Seleccionar `exitSide` con flecha antes de cerrar.
7. Finalizar el conector.
8. Indicar elevación inicial/final o `riseM` si la UI lo permite.

Cada endpoint:

* es un `TransferSpace`;
* tiene Node;
* se conecta al otro endpoint mediante Edge vertical;
* se recorta del GeneralSpace.

Para una cadena same-level, los endpoints lógicos son el primer y último tile, pero el footprint completo del conector debe comportarse como obstáculo/TransferSpace compuesto. El grafo debe conectar con los lados abiertos, no atravesar el cuerpo lateral de la escalera/rampa.

### Inter-level

1. Elegir `t`, `r` o `l`.
2. Elegir scope `inter_level`.
3. Dibujar el footprint/cadena en nivel origen.
4. Elegir nivel destino.
5. Replicar footprint/cadena en la misma posición XY en el nivel destino.
6. Seleccionar lado de entrada en origen.
7. Seleccionar lado de salida en destino.

Debe conservar el mismo `connectorId`.

Para escaleras/rampas inter-planta, la autoría debe sentirse igual que en same-level: cadena de tiles estándar y lados abiertos explícitos. Para ascensor, la replicación exacta en XY entre plantas es el comportamiento esperado.

## 8.3. Representación primal

Cada endpoint es una celda rectangular.

Los lados seleccionados como entrada/salida son:

```text
NavigableBoundary
```

Los restantes:

```text
NonNavigableBoundary
```

La representación de peldaños o líneas de rampa es puramente estética/sourceFeature.

No debe alterar la topología.

## 8.3.1. Cobertura lateral no navegable

Para escaleras, rampas y ascensores:

* Los lados no marcados como `entrySide`, `exitSide` u `openSides` deben quedar cubiertos por una barrera/cobertura `NonNavigableSpace`.
* Esa cobertura debe generarse como contorno exterior unido del footprint/cadena, no como tiras independientes que se solapen entre sí.
* Las esquinas deben cerrar en una única esquina limpia, con union/buffer robusto y join tipo miter cuando proceda.
* No deben quedar huecos en las esquinas, picos colgantes, dobles picos ni pequeñas islas por redondeos numéricos.
* La cobertura debe recortarse contra muros, columnas, objetos y el propio footprint del conector para evitar solapes.
* Los lados abiertos deben quedar como boundary navegable/virtual hacia el `GeneralSpace`; el resto debe actuar como obstáculo durante detección y export.
* La cobertura debe ser verificable visualmente y en tests: no basta con que el JSON valide.

## 8.4. Representación dual

### Same-level

Crear Edge:

```text
relationshipType: "vertical_connectivity"
connectorType: Stair | Ramp | Elevator
```

entre los Nodes de los dos endpoints.

### Inter-level

Crear:

```text
InterLayerConnection
```

entre los Nodes de las ThematicLayers de origen y destino.

Además, la vista de grafo vertical debe poder materializar un edge equivalente para routing.

## 8.5. Ascensor

Permitir varios niveles servidos.

Crear un endpoint por nivel servido.

Conectar niveles adyacentes o todos los pares según configuración, preferentemente niveles adyacentes para no crear un grafo completo innecesario.

Atributos:

```text
capacityPersons
estimatedWaitSeconds
travelSpeedMps
```

---

# Fase 9 — Vistas derivadas de grafos

Crea:

```text
src/indoor_data_model/graph_views.py
```

El `DualSpaceLayer` sigue siendo la fuente de verdad.

No introduzcas cuatro grafos raíz duplicados dentro de `indoor_model.json`.

Genera estas vistas:

## 9.1. room_adjacency

Nodes:

```text
GeneralSpace
```

Edges entre GeneralSpaces físicamente relacionadas.

Distinguir:

```text
traversable = true  mediante TransferSpace o virtual boundary
traversable = false mediante WallSegment
```

Incluir:

```text
viaBoundaryRefs
viaTransferSpaceRefs
viaTransferNodeRefs
viaWallRefs
```

Evitar falsas conexiones entre todas las salas que toquen un mismo muro largo. Utilizar geometría/localización de boundaries para emparejar relaciones reales.

Si la adyacencia proviene de una `VirtualBoundary`, debe quedar claro en la vista: `traversable = true`, `viaBoundaryRefs` apuntando a la línea 1D y, si existe, `viaTransferNodeRefs` apuntando al nodo lógico del punto medio.

## 9.2. room_transfer_connectivity

Grafo bipartito:

```text
GeneralSpace ↔ TransferSpace
```

Solo relaciones navegables por defecto.

Debe representar:

```text
Room → Door → Room
Room → Exit
Room → ConnectorEndpoint
Room → VirtualTransferNode → Room
```

`VirtualTransferNode` solo representa una virtual boundary navegable en el dual o en la vista derivada. No implica que exista un `TransferSpace` 2D en el primal.

## 9.3. door_to_door

Nodes:

```text
TransferSpace atravesables
```

Dos TransferSpaces se conectan cuando comparten un GeneralSpace navegable.

Incluir:

```text
viaSpaceRef
distanceM
locomotionTypes
```

Para `distanceM`:

1. usar segmento directo si queda cubierto por el GeneralSpace;
2. si no, calcular ruta interior mediante visibility graph simple sobre vértices del polígono;
3. fallback Euclidean con warning si falla.

## 9.4. vertical_connectivity

Incluir:

* stair endpoints;
* ramp endpoints;
* elevator endpoints;
* conexiones same-level;
* InterLayerConnections.

## 9.5. Serialización opcional

No contaminar el core.

Permitir generar un archivo acompañante:

```text
outputs/graph_views/<stem>_graph_views.json
```

Solo cuando se solicite.

La ruta normal de EvacEngine podrá derivar las vistas directamente desde indoor_model.

---

# Fase 10 — Visualización multinivel y vistas de grafo

Actualiza exclusivamente:

```text
tools/visualize_indoor_model.py
```

No modifiques el visualizador MLSM legacy.

El script debe poder ejecutarse tanto desde la raíz del repo como invocado directamente por ruta (`tools/visualize_indoor_model.py`). Si necesita importar módulos de `src`, debe preparar `sys.path` de forma robusta. No debe fallar con `ModuleNotFoundError` al ser llamado desde SpatialEngine para autovisualización.

Añade:

```text
--level LEVEL_00
--all-levels
--split-levels
--graph-view room_adjacency
--graph-view room_transfer_connectivity
--graph-view door_to_door
--graph-view vertical_connectivity
--graph-view base_dual
```

Reglas:

* por defecto mostrar un nivel;
* no superponer niveles;
* `--split-levels` genera un PNG por nivel;
* `--all-levels` puede usar una composición claramente separada;
* mostrar connectors relacionados;
* usar colores distintos por graph view;
* permitir labels none/cells/nodes/edges/all.
* permitir verificar visualmente virtual boundaries 1D y nodos lógicos asociados;
* permitir verificar visualmente la cobertura no navegable de conectores y sus lados abiertos.

La autovisualización de SpatialEngine debe generar:

```text
un PNG all por nivel
un PNG room_adjacency por nivel
un PNG room_transfer_connectivity por nivel
un PNG door_to_door por nivel si hay varios TransferSpace
un PNG vertical_connectivity para el edificio si hay conectores
```

No generar decenas de PNG innecesarios. Generar pocas vistas, pero las suficientes para diagnosticar si:

* las salas se detectaron;
* las puertas/ventanas/columnas/conectores siguen visibles;
* las virtual boundaries son líneas y no polígonos;
* el grafo room adjacency tiene aristas esperadas;
* room-transfer connectivity muestra accesos a puertas, salidas y conectores;
* vertical connectivity conecta las plantas correctas.

---

# Fase 11 — Interfaz y keymap

Centraliza el keymap en una sola estructura visible.

Atajos mínimos:

```text
m exterior
n interior
p puerta simple
d puerta doble
s salida
v virtual boundary manual
h espacio manual
f detectar espacios
w ventana
c columna
t escalera
r rampa
l ascensor
b alternar same/inter-level para escalera/rampa/ascensor
flechas seleccionar lado entry/exit/openSide
[ nivel anterior
] nivel siguiente
+ añadir nivel
z undo
y redo
e export normal
x all adjacency debug
? ayuda
esc cancelar
```

Desactiva keymaps internos de Matplotlib que entren en conflicto.

Muestra:

* herramienta activa;
* nivel activo;
* locomotion;
* estado dirty/detected;
* ayuda resumida.

La ayuda completa debe poder imprimirse con `?`.

La UI debe incluir una ayuda/tutorial operativo, no solo una lista de teclas:

* En modo escalera/rampa/ascensor debe mostrar scope actual (`same_level` o `inter_level`), tile size, lado seleccionado y si falta entry/exit.
* Mientras se dibuja una cadena de tiles debe previsualizar la cadena completa y el siguiente tile candidato.
* Al cambiar de nivel debe quedar claro qué nivel está activo y qué conectores tienen footprint relacionado en otros niveles.
* Tras pulsar `f`, debe verse simultáneamente el resultado de espacios detectados y los elementos dibujados originales.
* Los avisos de terminal deben ser accionables: decir qué falta o qué se solapa, con IDs/nombres de elementos cuando sea posible.
* Si una operación no puede terminarse por falta de entry/exit, shell abierto o geometría inválida, no debe dejar un conector parcial silencioso.
* Mejorar fluidez visual y refresco durante dibujo está permitido siempre que no introduzca dependencias nuevas ni reescriba el visualizador legacy.

---

# Fase 12 — Schema y documentación

Actualiza:

```text
schemas/indoor/indoor_model.schema.json
docs/technical/architecture/indoor_data_model_architecture.md
```

No modifiques documentación MLSM legacy salvo una referencia clara de que es legacy.

El schema debe admitir:

* varios niveles;
* ThematicLayer por nivel;
* layerConnections;
* virtual boundaries manuales/automáticas;
* windows;
* ObjectSpace Column;
* connector endpoints;
* vertical connector metadata;
* Point 2D o 3D si se usa Z;
* locomotion oficial;
* propiedades de escalera/rampa/elevador;
* stable references.

Valida el propio schema con Draft 2020-12.

---

# Fase 13 — Tests obligatorios

Mantén:

```text
tests/test_indoor_wall_junctions.py
```

Crea:

```text
tests/test_space_detection.py
tests/test_space_decomposition.py
tests/test_multilevel_authoring.py
tests/test_vertical_connectors.py
tests/test_windows_and_objects.py
tests/test_graph_views.py
tests/test_authoring_history.py
```

Usa `unittest`.

## Space detection

Casos:

* rectángulo;
* dos habitaciones;
* L;
* T;
* U;
* H;
* O con hueco;
* polígono diagonal cóncavo;
* virtual boundary manual;
* door sobre wall;
* shell exterior abierto.
* pulsar `f` después de dibujar puertas/ventanas/columnas/conectores no borra esos elementos.
* conectores tratados como obstáculos al recortar `GeneralSpace`.

Comprobar:

```text
sin solapes
sin huecos no intencionados
union(parts) ≈ original free space
IDs reutilizados cuando sea posible
```

## Connectors

Casos:

* escalera same-level;
* rampa same-level;
* escalera LEVEL_00 → LEVEL_01;
* ascensor de tres niveles;
* entry/exit boundaries;
* cadena de tiles para escalera/rampa;
* cobertura lateral continua con esquinas cerradas y sin solapes;
* vertical edges;
* InterLayerConnection;
* no solape.

## Windows/ObjectSpace

* ventana corta muro;
* defaultTraversable false;
* columna recorta GeneralSpace;
* ObjectSpace válido.

## Graph views

* room adjacency;
* room-door-room;
* door-to-door;
* vertical;
* virtual boundary navegable como línea 1D, no como CellSpace;
* nodo lógico opcional en punto medio de virtual boundary;
* ningún edge hacia WallJunction en navegación normal.

## History

* undo/redo de wall;
* opening;
* column;
* auto detection;
* level;
* connector.

---

# Gates de calidad

Después de cada fase ejecuta los tests relevantes.

No continúes a la fase siguiente si:

* los junction tests fallan;
* aparecen CellSpaces solapados;
* el schema no valida;
* se rompe export de una planta;
* se pierde una puerta/opening;
* z/undo deja referencias huérfanas;
* `f` borra u oculta elementos de autoría existentes;
* una `VirtualBoundary` aparece como `CellSpace`, `TransferSpace` o geometría 2D;
* la cobertura lateral de escaleras/rampas/ascensores solapa muros, objetos, conectores o deja esquinas abiertas;
* no se puede visualizar al menos una vista de grafo útil para depurar conectividad;
* el visualizador de indoor model falla al ser invocado desde SpatialEngine.

En caso de bloqueo:

* conserva las fases anteriores funcionando;
* no ocultes el error;
* devuelve exactamente dónde se detuvo;
* no dejes stubs que aparenten estar completos.

---

# Verificación final obligatoria

Ejecuta:

```powershell
python -m py_compile src/MLSM_SpatialEngine.py
python -m py_compile src/indoor_authoring/model.py
python -m py_compile src/indoor_authoring/history.py
python -m py_compile src/indoor_authoring/space_detection.py
python -m py_compile src/indoor_authoring/space_decomposition.py
python -m py_compile src/indoor_authoring/connectors.py
python -m py_compile src/indoor_data_model/builder.py
python -m py_compile src/indoor_data_model/geometry.py
python -m py_compile src/indoor_data_model/graph_views.py
python -m py_compile tools/visualize_indoor_model.py

python -m unittest discover -s tests -v
```

Comprueba también:

```powershell
git diff -- src/MLSM_EvacEngine.py
git diff -- tools/visualize_mlsm_v2.py
git diff -- requirements.txt
```

Deben estar vacíos.

## Respuesta final de Codex

Devuelve:

1. archivos creados;
2. archivos modificados;
3. arquitectura final;
4. keymap final;
5. algoritmo de detección;
6. algoritmo de descomposición;
7. representación de ventanas y columnas;
8. representación de niveles;
9. representación de stairs/ramps/elevators;
10. graph views;
11. schema actualizado;
12. tests y resultados;
13. limitaciones pendientes;
14. confirmación de que EvacEngine y MLSM visualizer no fueron tocados.

No hagas commit.

---
