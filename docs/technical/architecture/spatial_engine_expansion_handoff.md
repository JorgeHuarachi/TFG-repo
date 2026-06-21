# SpatialEngine expansion handoff

**Fecha:** 2026-06-20  
**Estado:** resumen final de implementacion para traspaso a la siguiente fase del proyecto.  
**Objetivo:** permitir que otro ChatGPT entienda los cambios finales de SpatialEngine sin analizar un `git diff` grande.  
**Ambito:** solo documenta la expansion nueva de SpatialEngine, Indoor Data Model, autorias multinivel, conectores verticales, deteccion de espacios, grafos y visualizacion.

## Resumen ejecutivo

SpatialEngine quedo reorganizado alrededor de un contrato nuevo: exportar un `indoor_model.json` espacial/topologico, separado de escenarios de simulacion. El modelo nuevo se alinea conceptualmente con IndoorGML/IndoorJSON y usa:

- `CellSpace` para espacios fisicos: `GeneralSpace`, `TransferSpace`, `NonNavigableSpace`, `ObjectSpace`.
- `CellBoundary` para interfaces entre celdas: navegables, no navegables y virtuales.
- `DualSpace` con `Node` y `Edge` derivados por dualidad de celdas y boundaries.
- `ThematicLayer` por planta/nivel.
- `InterLayerConnection` para conectividad vertical entre plantas.
- `sourceFeatures` para trazar desde elementos dibujados hasta celdas/boundaries derivadas.

El cambio central es que la UI sigue siendo comoda para dibujar, pero la fuente de verdad ya no son solo listas legacy como `self.muros` o `self.hitos`. La fuente de verdad durante la edicion es `BuildingAuthoringState`, y desde ahi se crea un snapshot de autoria que alimenta `build_indoor_model(...)`.

No se tocaron como parte del cierre final:

- `src/MLSM_EvacEngine.py`
- `tools/visualize_mlsm_v2.py`
- `requirements.txt`

## Mapa de archivos relevantes

### Nuevos modulos de autoria

- `src/indoor_authoring/model.py`
  - Define el estado de autoria tipado.
  - Clases clave: `BuildingAuthoringState`, `LevelAuthoringState`, `AuthoringLineElement`, `AuthoringAreaElement`, `DetectedSpace`, `VirtualBoundary`, `VerticalConnector`, `ConnectorEndpoint`.
  - Permite niveles, muros, puertas, salidas, ventanas, columnas, espacios manuales, espacios detectados, boundaries virtuales y conectores verticales.
  - Expone `to_snapshot(...)`, que es el contrato de entrada al builder.

- `src/indoor_authoring/history.py`
  - Historial undo/redo por snapshots profundos del estado de autoria.
  - Usado por la UI con teclas `z` y `y`.

- `src/indoor_authoring/space_detection.py`
  - Deteccion automatica de espacios con `detect_spaces(...)`.
  - Usa muros exteriores para derivar shell.
  - Usa linework de muros y boundaries virtuales manuales.
  - No usa puertas/salidas/ventanas como linework de division.
  - No reutiliza `automatic_virtual_boundaries` antiguas como entrada.
  - Recorta contra masa solida de muros, columnas y conectores para obtener espacios libres.

- `src/indoor_authoring/space_decomposition.py`
  - Descompone poligonos concavos o con agujeros en piezas mas simples.
  - Genera `VirtualBoundary` automaticas cuando hay una division real entre partes.
  - Mantiene control de error por area para evitar decomposiciones incorrectas.

- `src/indoor_authoring/connectors.py`
  - Helpers para crear escaleras, rampas y ascensores.
  - `create_tile_chain_connector(...)`: escaleras/rampas con tiles contiguos.
  - `create_elevator_connector(...)`: ascensor rectangular con endpoints por nivel servido.

### Indoor Data Model

- `src/indoor_data_model/builder.py`
  - Construye `indoor_model.json`.
  - Clases clave: `IndoorModelBuilder`, `MultiLevelIndoorModelBuilder`.
  - Funciones publicas: `build_indoor_model(...)`, `derive_wall_mass_from_snapshot(...)`.
  - Deriva muros como `NonNavigableSpace`, puertas/salidas/ventanas como `TransferSpace`, columnas como `ObjectSpace`, habitaciones como `GeneralSpace`, conectores como `TransferSpace`.
  - Genera boundaries, nodos, edges, `sourceFeatures`, `layerConnections` y validaciones de overlap.

- `src/indoor_data_model/graph_views.py`
  - Deriva vistas de grafo limpias desde el modelo exportado.
  - Funcion publica: `derive_graph_views(model)`.
  - Vistas: `base_dual`, `space_adjacency`, `space_connectivity`, `room_adjacency`, `room_to_room_accessibility`, `transfer_to_transfer`, `door_to_door`, `vertical_connectivity`.
  - Alias compatibles: `general_space_adjacency`, `space_transfer_connectivity`, `room_transfer_connectivity`, `room_to_room`.

- `src/indoor_data_model/geometry.py`
  - Helpers geometricos compartidos: conversion GeoJSON, footprints, union, limpieza booleana, lineas de contacto, nodos representativos.

- `src/indoor_data_model/ids.py`
  - Normalizacion de tokens, IDs y referencias internas.

- `src/indoor_data_model/__init__.py`
  - Exporta `build_indoor_model`, `derive_wall_mass_from_snapshot`, `derive_graph_views`.

### UI y visualizacion

- `src/MLSM_SpatialEngine.py`
  - Integra `BuildingAuthoringState`.
  - Mantiene listas legacy sincronizadas para que la UI previa no se rompa.
  - Agrega niveles, ventanas, columnas, deteccion automatica, conectores verticales, previsualizaciones y exportacion nueva.
  - Exporta con `exportar_indoor_model(...)`.
  - Ya no genera automaticamente una bateria grande de PNGs salvo que se active `MLSM_AUTO_VISUAL_CHECKS`.

- `tools/visualize_indoor_model.py`
  - Visualizador nuevo del `indoor_model.json`.
  - Permite capas separadas, presets limpios, grafos derivados y deteccion/visualizacion de overlaps.

### Schemas y documentacion

- `schemas/indoor/indoor_model.schema.json`
  - Ampliado para soportar niveles, layers, source features, vertical connectors, layer connections, navigation types, cell boundaries y metadatos nuevos.

- `schemas/indoor/scenario_model.schema.json`
  - Ajustes pequenos para mantener separacion conceptual entre modelo indoor y escenario.

- `docs/technical/architecture/indoor_data_model_architecture.md`
  - Documento canonico de arquitectura conceptual del Indoor Data Model.

### Tests nuevos o ampliados

- `tests/test_authoring_history.py`
- `tests/test_graph_views.py`
- `tests/test_multilevel_authoring.py`
- `tests/test_space_decomposition.py`
- `tests/test_space_detection.py`
- `tests/test_vertical_connectors.py`
- `tests/test_windows_and_objects.py`
- `tests/test_indoor_wall_junctions.py` se mantiene como suite sensible para junctions.

## Flujo final end-to-end

1. El usuario dibuja en `MLSM_SpatialEngine`.
2. Cada accion relevante se guarda en `BuildingAuthoringState`.
3. Las estructuras legacy (`self.muros`, `self.hitos`, `self.hitos_bounds`, `self.propiedades_zonas`) se reconstruyen desde el estado nuevo para seguir pintando la UI.
4. Con `f`, se ejecuta `detect_spaces(...)` sobre el nivel activo.
5. Con `e`, se exporta `indoor_model.json` en modo `navigation`.
6. Con `x`, se exporta un JSON debug en modo `all_adjacency`.
7. `build_authoring_snapshot(...)` genera el snapshot normalizado.
8. `build_indoor_model(...)` decide si usa `IndoorModelBuilder` o `MultiLevelIndoorModelBuilder`.
9. Se escribe `outputs/indoor_models/<nombre>_indoor_model_<timestamp>.json`.
10. Se valida contra `schemas/indoor/indoor_model.schema.json` si el validador esta disponible.

## Controles principales de la UI

- `m`: muro exterior.
- `n`: muro interior.
- `p`: puerta simple.
- `d`: puerta doble.
- `s`: salida.
- `w`: ventana.
- `v`: frontera virtual manual.
- `h`: espacio/manual footprint legacy.
- `c`: columna.
- `f`: detectar espacios automaticamente en el nivel activo.
- `t`: escalera.
- `r`: rampa.
- `l`: ascensor.
- `b`: alternar conector `same_level` / `inter_level`.
- `tab`: alternar edicion de lado `entry` / `exit`.
- flechas: seleccionar lado `north/south/east/west`.
- `enter`: cerrar escalera/rampa.
- `backspace/delete`: quitar ultimo tile de escalera/rampa.
- `+` o `=`: crear nuevo nivel.
- `[` y `]`: cambiar nivel activo.
- `z`: undo.
- `y`: redo.
- `e`: exportar Indoor Data Model en modo `navigation`.
- `x`: exportar Indoor Data Model en modo `all_adjacency`.
- `esc`: cancelar operacion actual.

## Estado de autoria

`BuildingAuthoringState` es la fuente de verdad. Contiene:

- `levels`: lista de `LevelAuthoringState`.
- `active_level_id`.
- `vertical_connectors`.
- `counters`: contadores para nombres estables.

Cada `LevelAuthoringState` contiene:

- `wall_centerlines`
- `doors`
- `exits`
- `windows`
- `manual_virtual_boundaries`
- `automatic_virtual_boundaries`
- `columns`
- `manual_spaces`
- `detected_spaces`
- `geometry_dirty`
- `detection_report`

Decision importante: las listas legacy se consideran vistas de compatibilidad. No deberian usarse para introducir nuevas semanticas.

## Deteccion automatica de espacios

`detect_spaces(state, level_id)` hace:

1. Obtiene el shell desde muros exteriores.
2. Construye linework con:
   - muros del nivel;
   - boundaries virtuales manuales.
3. No usa como linework:
   - puertas;
   - salidas;
   - ventanas;
   - automatic virtual boundaries antiguas.
4. Polygoniza el linework.
5. Calcula obstaculos:
   - masa solida de muros (`solidWallUnion`);
   - columnas;
   - conectores verticales tipo `Stair`, `Ramp`, `Elevator`;
   - footprints de puertas/salidas/ventanas solo cuando estan ancladas a muro, como recorte de area libre, no como lineas de division.
6. Resta obstaculos de cada face.
7. Descompone poligonos complejos con `decompose_space(...)`.
8. Genera `DetectedSpace` y `VirtualBoundary` automaticas nuevas.
9. Reemplaza `level.automatic_virtual_boundaries` con las nuevas del pase actual.

Problema corregido: antes se realimentaban `automatic_virtual_boundaries` antiguas en el siguiente `f`, lo que podia partir espacios con geometria derivada obsoleta. Ahora son salida del pase, no entrada.

Problema corregido: puertas/salidas no deben participar en la subdivision de habitaciones. Ahora no son linework. Si estan ancladas a muro, recortan el espacio libre donde corresponde, pero no crean una linea que divida una sala.

## Muros, junctions y masa de muro

El builder deriva dos masas de muro:

- `solidWallUnion`: masa cerrada de muros y junctions antes de abrir huecos de puertas/salidas/ventanas. Se usa para deteccion automatica de habitaciones, evitando que huecos de puertas deformen o partan salas.
- `wallUnion`: masa final de muros con huecos ya recortados. Se usa para exportar `WallSegment`, `WallJunction`, boundaries y visualizacion final.

Los muros se derivan como `NonNavigableSpace`:

- `WallSegment`: tramo normal de muro.
- `WallJunction`: pieza derivada para cubrir uniones L/T/X/V, angulos y encuentros de muros.

La logica de junctions:

- agrupa candidatos de union por proximidad;
- crea poligonos de junction angle-aware;
- evita picos visuales y huecos topologicos;
- recorta junctions contra openings;
- evita overlaps entre WallSegment y WallJunction;
- evita edges navegables hacia WallJunction en modo normal.

Decision importante: los bordes/coberturas de conectores tambien se recortan contra masa de muros y junctions para evitar solapes con paredes que nacen o terminan en escaleras/rampas.

## GeneralSpace

`GeneralSpace` representa areas navegables principales: habitaciones, pasillos, piezas libres detectadas.

Hay dos fuentes:

- `detectedSpaces`: resultado de `detect_spaces(...)`.
- `spaceFootprints`: espacios manuales legacy.

Para `detectedSpaces`, el builder recorta contra:

- `wallUnion` final;
- `objectUnion`;
- transferencias que deben ocupar area fisica, como puertas/salidas/ventanas ancladas a muro y conectores.

Esto evita que una puerta o salida aparezca como `TransferSpace` superpuesto sobre un `GeneralSpace`.

## TransferSpace

`TransferSpace` representa elementos que conectan o median navegacion:

- puertas (`Door`);
- salidas (`Exit`);
- ventanas (`Window`);
- endpoints de escaleras/rampas/ascensores (`Stair`, `Ramp`, `Elevator`).

Puertas:

- se dibujan sobre un muro;
- guardan metadatos de host wall (`hostWallName`, `hostWallType`, `hostWallThicknessM`, `hostWallRef`);
- se exportan como `TransferSpace`, `category: Door`, `function: ConnectionSpace`;
- por defecto son atravesables.

Salidas:

- se exportan como `TransferSpace`, `category: Exit`, `function: AnchorSpace`;
- generan boundary exterior navegable de tipo anchor cuando queda borde expuesto.

Ventanas:

- se exportan como `TransferSpace`, `category: Window`;
- por defecto tienen `defaultTraversable: false`;
- se consideran controlables por escenario (`scenarioControllable`) para permitir cambios futuros.

Decision importante: que una puerta/salida se vea como rectangulo en `CellSpaces` es correcto, porque es un `TransferSpace` real. Lo incorrecto era que esa geometria dividiera salas o solapara con `GeneralSpace`; eso quedo corregido.

## ObjectSpace y NonNavigableSpace

Columnas:

- se crean como `ObjectSpace`;
- tienen `navigationClass: NonNavigableSpace`;
- recortan `GeneralSpace`;
- no deben solapar con espacios navegables.

Muros y coberturas:

- muros finales son `NonNavigableSpace`;
- coberturas laterales de conectores son `NonNavigableSpace`, `category: ConnectorSideCoverage`;
- las coberturas de conectores representan lados cerrados/no abiertos alrededor de escaleras/rampas/ascensores.

## CellBoundary

El builder crea boundaries por contacto geometrico:

- `general_transfer_contact`: entre `GeneralSpace` y `TransferSpace`; navegable si el transfer es atravesable.
- `general_transfer_contact_blocked`: por ejemplo ventana no atravesable.
- `general_non_navigable_contact`: contacto entre espacio navegable y muro/objeto.
- `transfer_non_navigable_contact`: contacto entre transfer y no navegable.
- `same_level_connector_internal_contact`: contacto interno entre endpoints de una escalera/rampa en la misma planta.
- `virtual_general_general_contact`: boundary virtual entre GeneralSpaces.
- `outer_shell`: boundary exterior no navegable de muros exteriores.
- `exterior_anchor`: boundary navegable exterior de una salida.

Las boundaries virtuales:

- son `CellBoundary` con `isVirtual: true`;
- no son `CellSpace`;
- pueden generar un nodo logico `VirtualTransferNode` en vistas de grafo;
- se exportan solo si encuentran dos `GeneralSpace` adyacentes.

## DualSpace y edges

Cada `CellSpace` tiene un `Node` dual.

Cada `CellBoundary` que debe tener dualidad puede generar un `Edge`:

- edges navegables entre `GeneralSpace` y `TransferSpace`;
- edges de general-general virtual;
- edges verticales same-level para conectores;
- edges no navegables de adyacencia muro-general cuando el modo lo permite;
- edges debug adicionales en `all_adjacency`.

Modo `navigation`:

- modo por defecto;
- mantiene el grafo util para navegacion;
- evita edges navegables hacia `WallJunction`;
- mantiene adyacencias no navegables relevantes contra `WallSegment`.

Modo `all_adjacency`:

- modo debug;
- exporta mas relaciones de adyacencia;
- se usa con tecla `x`.

## Conectores verticales

Tipos soportados:

- `Stair`
- `Ramp`
- `Elevator`

Scopes:

- `same_level`: conector dentro de la misma planta.
- `inter_level`: conector entre niveles.

Escaleras y rampas:

- se dibujan como cadena de tiles de 1 m por defecto;
- cada tile debe compartir lado con el anterior;
- no se aceptan tiles duplicados;
- se seleccionan lados `entry` y `exit`;
- se cierran con `enter`;
- si la cadena no es valida, se mantiene editable y se muestra error.

Same-level:

- si hay mas de un tile, se crean endpoints entry y exit dentro del mismo nivel;
- se genera boundary interna navegable entre endpoints cuando comparten contacto;
- se genera edge con `relationshipType: vertical_connectivity`;
- esto representa conectividad dentro de la propia escalera/rampa aunque sea en la misma planta.

Inter-level:

- crea endpoint en nivel origen y endpoint en nivel destino;
- el endpoint del nivel origen deja abierta solo la boca `entry`;
- el endpoint del nivel destino deja abierta solo la boca `exit`;
- el extremo no local se cubre como `ConnectorSideCoverage` no navegable, para evitar que el grafo continue por la misma planta como si fuera un conector `same_level`;
- `MultiLevelIndoorModelBuilder` genera `InterLayerConnection`;
- `derive_graph_views(...)[\"vertical_connectivity\"]` recoge esas conexiones.
- las coberturas laterales se generan como anillo exterior continuo y se recortan contra muros, otros endpoints de conector y coberturas previas para evitar puntas abiertas y overlaps.

Reexport:

- `tools/reexport_indoor_model.py` recalcula las `sideCoverages` de conectores `inter_level` desde `footprint` + `openSides`.
- Esto permite corregir modelos ya exportados sin redibujarlos cuando cambia la logica de cobertura de conectores.

Ascensores:

- se crean por footprint rectangular;
- pueden servir uno o varios niveles;
- default accesible: `Walking`, `Rolling`;
- atributos por defecto: capacidad, espera estimada y velocidad.

Coberturas laterales:

- se generan a partir de lados cerrados;
- no solapan con el footprint del conector;
- se recortan contra otros conectores y muros;
- se exportan como `ConnectorSideCoverage`.

## Multinivel

El estado de autoria permite multiples niveles:

- `LEVEL_00`, `LEVEL_01`, etc.
- cada nivel tiene `order`, `elevationM`, `floorZ`, `ceilingZ`, `heightM`;
- la UI cambia de nivel con `[` y `]`;
- `+` crea nuevo nivel.

`MultiLevelIndoorModelBuilder`:

- crea una `ThematicLayer` por nivel con celdas exportables;
- conserva todos los niveles en `levels[]`;
- agrupa `sourceFeatures`;
- crea `layerConnections` para conectores interplanta.

## Vistas de grafo derivadas

`derive_graph_views(model)` produce:

- `base_dual`: nodos y edges crudos del `DualSpaceLayer` exportado. Es la vista mas fiel al modelo, pero no siempre es la mas limpia para inspeccion.
- `space_adjacency`: grafo entre `GeneralSpace` ya divididos. Incluye contacto directo `GeneralSpace`-`GeneralSpace` y tambien conexiones indirectas por `TransferSpace`. No inserta nodo intermedio; la arista resume la relacion.
- `space_connectivity`: grafo de conectividad entre `GeneralSpace` divididos, `TransferSpace` y `VirtualTransferNode`. Es la version explicita de `space_adjacency`: puertas, salidas, rampas, escaleras, ventanas y boundaries virtuales aparecen como nodos intermedios. Alias: `space_transfer_connectivity` y `room_transfer_connectivity` por compatibilidad historica.
- `room_adjacency`: grafo entre habitaciones logicas. Una habitacion logica se obtiene agrupando `GeneralSpace` separados solo por `VirtualBoundary`. La arista agrupa un unico contacto entre habitaciones e indica si viene por muro, transfer o conector.
- `room_to_room_accessibility`: subgrafo de `room_adjacency` que conserva solo aristas con al menos un transfer navegable o conector navegable. Alias: `room_to_room`.
- `transfer_to_transfer`: grafo entre transfers dentro de un mismo `GeneralSpace` dividido. Incluye puertas, salidas, ventanas, rampas/escaleras/ascensores y `VirtualTransferNode`. No cruza toda la habitacion logica; cada arista tiene un unico `viaSpaceRef`.
- `door_to_door`: grafo entre puertas/salidas navegables dentro de un mismo `GeneralSpace` dividido. No incluye ventanas ni boundaries virtuales.
- `vertical_connectivity`: endpoints y conexiones verticales. Incluye edges internos de conectores `same_level` y conexiones interplanta serializadas como `InterLayerConnection` en `layerConnections`.

Estas vistas son derivadas. La fuente principal sigue siendo `layers[].primalSpace` y `layers[].dualSpace`.

La diferencia clave entre `Space` y `Room` es:

- `Space` = `GeneralSpace` fisico tal como queda tras la subdivision por boundaries virtuales.
- `Room` = componente logico que agrupa varios `GeneralSpace` conectados por `VirtualBoundary`.

### Conectividad vertical

- Conectores `same_level` como una rampa/escalera dentro de la misma planta generan endpoints `TransferSpace` y una boundary/edge interna con `relationshipType: vertical_connectivity`.
- Conectores `inter_level` generan endpoints `TransferSpace` en cada planta y una entrada en `layerConnections[]` de tipo `InterLayerConnection`.
- `derive_graph_views(model)["vertical_connectivity"]` recoge ambas formas: edges del dual para `same_level` y `layerConnections[]` para interplanta.
- En un modelo de una sola planta con conectores `same_level`, `layerConnections[]` puede estar vacio aunque `vertical_connectivity` tenga edges.

## Visualizador nuevo

`tools/visualize_indoor_model.py` permite inspeccionar JSONs sin abrir la UI.

Capas:

- `source`
- `cells`
- `general`
- `transfer`
- `non_navigable`
- `object`
- `boundaries`
- `navigable_boundaries`
- `non_navigable_boundaries`
- `nodes`
- `edges`
- `dual`

Presets:

- `basic`
- `spaces`
- `navigable-boundaries`
- `non-navigable`
- `overlaps`
- `graph-base-dual`
- `graph-space-adjacency`
- `graph-space-connectivity`
- `graph-room-adjacency`
- `graph-room-to-room`
- `graph-room-transfer`
- `graph-transfer-to-transfer`
- `graph-door-to-door`
- `graph-vertical`
- `graph-multilevel-vertical`

Opciones importantes:

- `--level LEVEL_00`
- `--all-levels`
- `--split-levels`
- `--fail-on-overlap`
- `--show-overlaps`
- `--focus-overlaps`
- `--multilevel-stack`
- `--save`
- `--no-show`

Comandos recomendados:

```powershell
$MODEL="outputs\\indoor_models\\TU_MODELO.json"
$LEVEL="LEVEL_00"

python tools\\visualize_indoor_model.py $MODEL --layers all --labels none --level $LEVEL --save outputs\\visual_checks\\all.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset spaces --level $LEVEL --save outputs\\visual_checks\\spaces.png --no-show
python tools\\visualize_indoor_model.py $MODEL --layers general,transfer --labels none --level $LEVEL --save outputs\\visual_checks\\navigable_spaces.png --no-show
python tools\\visualize_indoor_model.py $MODEL --layers non_navigable,object --labels none --level $LEVEL --save outputs\\visual_checks\\non_navigable_spaces.png --no-show
python tools\\visualize_indoor_model.py $MODEL --layers boundaries --labels none --level $LEVEL --save outputs\\visual_checks\\boundaries.png --no-show
python tools\\visualize_indoor_model.py $MODEL --layers navigable_boundaries --labels none --level $LEVEL --save outputs\\visual_checks\\nav_boundaries.png --no-show
python tools\\visualize_indoor_model.py $MODEL --layers non_navigable_boundaries --labels none --level $LEVEL --save outputs\\visual_checks\\non_nav_boundaries.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-base-dual --level $LEVEL --save outputs\\visual_checks\\graph_base_dual.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-space-adjacency --level $LEVEL --save outputs\\visual_checks\\graph_space_adjacency.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-space-connectivity --level $LEVEL --save outputs\\visual_checks\\graph_space_connectivity.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-room-adjacency --level $LEVEL --save outputs\\visual_checks\\graph_room_adjacency.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-room-to-room --level $LEVEL --save outputs\\visual_checks\\graph_room_to_room.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-room-transfer --level $LEVEL --save outputs\\visual_checks\\graph_room_transfer.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-transfer-to-transfer --level $LEVEL --save outputs\\visual_checks\\graph_transfer_to_transfer.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-door-to-door --level $LEVEL --save outputs\\visual_checks\\graph_door_to_door.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-vertical --level $LEVEL --save outputs\\visual_checks\\graph_vertical.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset graph-multilevel-vertical --save outputs\\visual_checks\\multilevel_vertical.png --no-show
python tools\\visualize_indoor_model.py $MODEL --preset overlaps --level $LEVEL --fail-on-overlap --save outputs\\visual_checks\\overlaps.png --no-show
```

Exportar desde la UI ya no genera automaticamente todos esos PNGs. Para recuperar el comportamiento automatico:

```powershell
$env:MLSM_AUTO_VISUAL_CHECKS="1"
```

Para generar imagenes por planta sin escribir a mano el ultimo nombre del modelo:

```powershell
python tools\\visualize_latest_indoor_model.py --split-levels --only spaces graph_space_connectivity graph_vertical
```

Para validar contra el schema y ver exactamente que campo falla:

```powershell
python tools\\validate_indoor_model_schema.py --show-value
python tools\\validate_indoor_model_schema.py outputs\\indoor_models\\TU_MODELO.json --show-value
```

Los endpoints de conectores verticales omiten `entrySide` o `exitSide` cuando no aplica. No deben serializarse como `null`, porque el schema solo permite esos campos cuando contienen uno de `north`, `south`, `east` o `west`.

## Ejemplos versionables

`outputs/` es una carpeta de resultados generados y esta ignorada por Git. Los modelos canonicos que interesa conservar para pruebas, documentacion y consumo por fases posteriores viven en:

- `examples/indoor_data_model/una_sola_planta_indoor_model.json`
- `examples/indoor_data_model/tres_plantas_indoor_model.json`

Ambos son exports `indoor_model.json` completos y validan contra `schemas/indoor/indoor_model.schema.json`.

La carpeta local `escenarios/` no se usa como fuente canonica de autoria. El archivo encontrado `TresPlantas_IndoorGML_184429.json` solo contenia `featureType: IndoorFeatures` y `layers: []`, sin geometria ni estado de autoria reproducible, por lo que se trato como resultado temporal y se aparto bajo `outputs/ignored_scenarios/`.

## Estructura del JSON exportado

Raiz:

- `id`
- `featureType: IndoorFeatures`
- `metadata`
- `crs`
- `levels`
- `layers`
- `layerConnections`
- `verticalConnectors`
- `sourceFeatures`
- `indoorDataModel`

Por cada layer:

- `id: TL_NAV_<level_code>`
- `featureType: ThematicLayer`
- `level`
- `primalSpace`
  - `cellSpaceMember`
  - `cellBoundaryMember`
- `dualSpace`
  - `nodeMember`
  - `edgeMember`

Campos clave de `CellSpace`:

- `id`
- `featureType: CellSpace`
- `cellSpaceGeom.geometry2D`
- `level`
- `navigationType`
- `navigationClass`
- `category`
- `function`
- `locomotionTypes`
- `boundedBy`
- `duality`
- `sourceFeatureRefs`
- `attributes`

Campos clave de `CellBoundary`:

- `id`
- `featureType: CellBoundary`
- `isVirtual`
- `cellBoundaryGeom.geometry2D`
- `navigationBoundaryType`
- `navigableBoundaryFunction` cuando aplica
- `traversable`
- `cellRefs`
- `duality` cuando tiene edge
- `sourceFeatureRefs`
- `attributes.boundaryRole`
- `attributes.relationshipType`

Campos clave de `Edge`:

- `id`
- `featureType: Edge`
- `weight`
- `geometry`
- `connects`
- `relationshipType`
- `traversable`
- `boundaryRef`
- `transferSpaceRef` cuando aplica
- `locomotionTypes`
- `widthM` y `capacityPersons` cuando aplica
- `attributes`

## Decisiones importantes ya tomadas

1. SpatialEngine exporta modelo espacial/topologico, no escenario de evacuacion.
2. Puertas/salidas/ventanas son `TransferSpace`, no muros ni linework de subdivision.
3. Las ventanas son transferencias no atravesables por defecto.
4. Las salidas son `TransferSpace` con funcion `AnchorSpace`.
5. Las boundaries virtuales son `CellBoundary`, no `CellSpace`.
6. Los muros son `NonNavigableSpace`.
7. Las columnas son `ObjectSpace`.
8. Los conectores verticales se modelan como endpoints `TransferSpace`.
9. La conectividad vertical interplanta vive en `layerConnections`.
10. La conectividad same-level de escalera/rampa puede vivir como boundary/edge interno de `vertical_connectivity`.
11. `WallJunction` evita huecos/picos y no debe contaminar grafos navegables normales.
12. `solidWallUnion` se usa para detectar habitaciones; `wallUnion` final se usa para exportar muros con huecos.
13. Las imagenes de validacion se generan bajo demanda, no automaticamente en cada `e`.

## Problemas corregidos durante el cierre

### Escaleras/rampas que no cerraban

Se valido la cadena de tiles antes de crear el conector. Si hay error de contiguidad o duplicado, se informa y se deja la edicion abierta para borrar/corregir.

### Solapes entre coberturas de conectores y muros

Las `ConnectorSideCoverage` se recortan contra masa final de muros y junctions. Esto evita overlaps cuando se dibujan muros interiores desde/hacia bordes de escalera/rampa.

### UI con muros visualmente distintos a la geometria final

La UI usa masa de muro derivada del builder para pintar muros fusionados y sin picos. Asi lo que se ve al dibujar se parece al resultado exportado.

### Deteccion con geometria de muros incorrecta

La deteccion usa `derive_wall_mass_from_snapshot(...)` y toma `solidWallUnion` para detectar espacios sin que huecos de puertas/salidas deformen salas.

### Puertas/salidas generando particiones o grafos ruidosos

Las puertas/salidas/ventanas ya no entran como linework de deteccion. Si estan ancladas a muro, recortan GeneralSpaces para evitar overlap, pero no dividen habitaciones como virtual boundaries.

### Automatic virtual boundaries obsoletas

`detect_spaces(...)` ya no alimenta el siguiente pase con `automatic_virtual_boundaries` antiguas. Solo usa manual virtual boundaries como entrada.

### Export lento por imagenes automaticas

Se desactivo la generacion automatica de visual checks en `e`. El visualizador queda disponible por comandos.

## Invariantes que deben mantenerse

- No debe haber overlaps significativos entre `CellSpace` del mismo nivel.
- `GeneralSpace` no debe solapar con muros, columnas, conectores ni openings anclados.
- `TransferSpace` de puerta/salida puede verse como rectangulo, pero no debe partir habitaciones por si mismo.
- `Window` debe ser `TransferSpace` no atravesable salvo que se cambie explicitamente.
- `WallJunction` no debe generar edges navegables normales.
- Los tiles de escalera/rampa deben ser contiguos por lado.
- `automatic_virtual_boundaries` son salida de deteccion, no entrada.
- La UI debe poder redibujarse desde `BuildingAuthoringState`.
- El modelo exportado debe validar contra schema cuando el validador este disponible.

## Tests de referencia

Comando final usado:

```powershell
$env:Path = "$PWD\\.venv\\Scripts;$env:Path"
python -m unittest discover -s tests -v
```

Resultado final verificado:

```text
Ran 43 tests in 4.880s
OK
```

Suites relevantes:

- `test_indoor_wall_junctions.py`
  - L/T/X/V junctions, angulos agudos, puertas cerca de junction.

- `test_space_detection.py`
  - deteccion rectangular y con divisor;
  - preservacion con shell abierto;
  - estabilidad de IDs;
  - conectores como obstaculos;
  - masa final/solida de muro;
  - automatic virtual boundaries obsoletas no dividen;
  - openings no dividen;
  - openings anclados recortan sin overlap.

- `test_vertical_connectors.py`
  - rampas same-level;
  - escaleras inter-level;
  - ascensores multi-level;
  - side coverages validas;
  - no overlaps con GeneralSpaces ni muros.

- `test_graph_views.py`
  - virtual boundary como nodo logico;
  - room-door-room;
  - door-to-door;
  - vertical connectivity.

- `test_windows_and_objects.py`
  - ventana no atravesable;
  - columna recorta GeneralSpace.

- `test_multilevel_authoring.py`
  - niveles separados;
  - layers por nivel.

- `test_authoring_history.py`
  - undo/redo en muros, openings, columnas, deteccion, niveles y conectores.

## Guia para la siguiente fase del proyecto

Si la siguiente fase consiste en consumir el JSON:

1. Usar `indoor_model.json` como fuente espacial base.
2. Leer `levels[]` para contexto vertical.
3. Leer `layers[]` por planta.
4. Para geometria navegable principal, filtrar `cellSpaceMember` con `navigationType == "GeneralSpace"`.
5. Para puertas/salidas/escaleras/rampas/ascensores, filtrar `navigationType == "TransferSpace"`.
6. Para muros/obstaculos, filtrar `navigationType == "NonNavigableSpace"` u `ObjectSpace`.
7. Para conectividad base, usar `dualSpace.nodeMember` y `dualSpace.edgeMember`.
8. Para grafos limpios, usar `derive_graph_views(model)` en vez de reconstruirlo todo manualmente.
9. Para **conectividad** vertical interplanta, leer `layerConnections[]`.
10. Para trazabilidad, usar `sourceFeatures[]` y `sourceFeatureRefs`.

Grafo recomendado para movimiento general:

- `space_connectivity` si interesa caminar desde cada `GeneralSpace` dividido hacia puerta/salida/conector/virtual boundary. `room_transfer_connectivity` queda como alias legacy.
- `vertical_connectivity` para enlazar plantas.
- `transfer_to_transfer` si interesa reducir cada `GeneralSpace` dividido a conexiones entre transfers.
- `room_to_room_accessibility` si interesa una vista agregada habitacion-a-habitacion solo con conexiones realmente atravesables.
- `base_dual` solo si se quiere el dual completo con todo el detalle.

## Recomendacion de organizacion futura de `src/`

Estado actual:

- `src/MLSM_SpatialEngine.py` sigue siendo la UI/aplicacion principal de autoria espacial.
- `src/MLSM_EvacEngine.py` sigue siendo el motor legacy de evacuacion.
- `src/indoor_authoring/` contiene el modelo editable, historial, deteccion de espacios y conectores.
- `src/indoor_data_model/` contiene builder, geometria, schemas internos y vistas de grafos derivadas.
- `tests/` y `tools/` deben permanecer fuera de `src/`; son suites y CLIs de apoyo, no libreria importable.

No conviene mover `MLSM_EvacEngine.py` o `MLSM_SpatialEngine.py` justo antes de un commit/tag de cierre: hay imports mixtos (`indoor_data_model` desde scripts que insertan `src/` en `sys.path`, y `src.indoor_data_model` desde tests mediante namespace package implicito). Mover ahora obligaria a revisar imports, entrypoints, documentacion y posibles rutas de usuario.

Ruta recomendada para la fase EvacEngine:

1. Crear un paquete nuevo, por ejemplo `src/evacuation/` o `src/evac_engine/`.
2. Extraer ahi responsabilidades nuevas: carga de `indoor_model`, sensores/balizas, escenarios temporales, agentes, routing, simulacion y visualizacion.
3. Mantener `MLSM_EvacEngine.py` inicialmente como adaptador/launcher legacy que llama al paquete nuevo.
4. Cuando tests y CLI esten estabilizados, decidir si se renombra/mueve el launcher legacy.

Esta estrategia reduce riesgo porque permite modernizar EvacEngine por piezas sin romper los scripts existentes.

## Pendientes o puntos que conviene revisar manualmente antes de continuar

- Decidir si el consumidor de simulacion usara `dualSpace.edgeMember` directamente o `derive_graph_views(...)`.
- Definir como mapear `locomotionTypes`, `widthM`, `capacityPersons`, `defaultTraversable` y `scenarioControllable` a reglas de simulacion.
- Decidir si ventanas pueden abrirse/cerrarse desde `scenario_model.json`.
- Decidir si `ConnectorSideCoverage` debe ser relevante para simulacion o solo para geometria no navegable/validacion.
- Si se va a persistir en PostGIS, definir tablas para `CellSpace`, `CellBoundary`, `Node`, `Edge`, `Level`, `LayerConnection`, `SourceFeature`.
- Revisar si se quiere guardar `graphViews` dentro del JSON o derivarlas siempre bajo demanda. Actualmente se derivan con `derive_graph_views(...)`.

## Estado Git esperado

Este documento describe el estado no commiteado final de la expansion. La rama puede mostrar muchos archivos modificados y nuevos. No se hizo commit.
