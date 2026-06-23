# EvacEngine e Indoor Data Model — Arquitectura objetivo de la reforma

**Estado:** documento de arquitectura previo al megaprompt de implementación.  
**Ámbito:** adaptación mayor de EvacEngine al nuevo `indoor_model.json`, evolución de `scenario_model.json`, routing multinivel, agentes, balizas, simulación, auditoría y UI.  
**Carácter:** documento canónico y mantenible. No es todavía el prompt de Codex ni una especificación cerrada de cada fórmula científica.  
**Revisión de cobertura:** contrastado con todas las decisiones debatidas sobre EvacEngine, grafos multinivel, escenario único, balizas/CEP, agentes, routing, Mesa, reproducibilidad, auditoría y UI. Los requisitos de ejecución de Codex se reservan para el futuro megaprompt y no se confunden con la arquitectura del producto.

---

## 1. Propósito, alcance y decisiones ya tomadas

El objetivo no es añadir compatibilidad puntual al `MLSM_EvacEngine.py` legacy. Se pretende realizar una **reforma arquitectónica completa** para que EvacEngine consuma el Indoor Data Model, pueda simular edificios multinivel, sea auditable y deje preparados puntos de extensión para balizas, hazards, comportamientos cooperativos, rescatistas y algoritmos de routing avanzados.

El flujo objetivo es:

```text
SpatialEngine
  → indoor_model.json

Editor de escenarios / UI
  → scenario_model.json

EvacEngine
  → carga ambos documentos
  → deriva topología y estado runtime
  → simula
  → produce rutas, eventos, trayectorias y métricas
```

### Decisiones consolidadas

1. `indoor_model.json` y `scenario_model.json` permanecen separados.
2. Se utilizará **un único `scenario_model.json` y un único `scenario_model.schema.json`**. El schema será internamente modular mediante `$defs` y secciones bien delimitadas.
3. El Indoor Data Model es inmutable durante una ejecución. Los cambios de puertas, hazards o aperturas creadas por rescatistas viven en un overlay runtime.
4. La ruta principal deja de ser el JSON legacy. El legacy solo puede mantenerse mediante un adaptador explícito y temporal.
5. El backbone topológico será `space_connectivity`, enriquecido con `vertical_connectivity` normalizada.
6. El grafo canónico de routing en NetworkX será un `MultiDiGraph`.
7. Una conexión física bidireccional se representa en runtime mediante dos arcos dirigidos que comparten un mismo recurso físico.
8. La ruta topológica y la trayectoria física se modelan por separado.
9. La simulación utilizará actualización síncrona por fases.
10. Habrá un `ContinuousSpace` por planta; el cambio de planta será una operación temporal de conector.
11. La aleatoriedad se gestionará mediante un contexto reproducible con streams independientes.
12. Los pesos avanzados no bloquean la reforma: al principio se usarán distancia y tiempo estimado, pero el contrato admitirá componentes dinámicos desde el primer día.
13. La UI será una aplicación cliente del motor, con pestañas, edición visual del escenario, inspección y auditoría; no controlará directamente los objetos internos de Mesa o NetworkX.

### Invariantes no negociables

- No se detectarán puertas, salidas o fronteras mediante substrings como `"Puerta"`, `"Salida"` o `"Frontera"`.
- No se acumularán penalizaciones sobre el peso anterior. Todo peso runtime se recompone desde una base inmutable.
- No se modificarán `indoor_model.json` ni `scenario_model.json` durante la simulación.
- No se utilizará el framerate de la UI como reloj físico.
- No se crearán nodos fantasma por mezclar referencias de `Node` y `CellSpace`.
- Ningún agente podrá recorrer un arco incompatible con su movilidad o capacidades.
- Todo resultado deberá poder relacionarse con IDs estables del modelo espacial y del escenario.
- La misma semilla, configuración y entradas deberán producir la misma ejecución dentro de una misma versión del motor.

---

## 2. Fronteras del sistema y contratos de datos

### 2.1. `indoor_model.json`

Es la fuente de verdad espacial y topológica. Contiene:

- `IndoorFeatures`;
- `levels[]`;
- `ThematicLayer` por planta;
- `primalSpace.cellSpaceMember[]`;
- `primalSpace.cellBoundaryMember[]`;
- `dualSpace.nodeMember[]`;
- `dualSpace.edgeMember[]`;
- `verticalConnectors[]`;
- `layerConnections[]`;
- `sourceFeatures[]` para trazabilidad.

Semántica principal:

| Tipo | Uso en EvacEngine |
|---|---|
| `GeneralSpace` | Dominio navegable normal: salas, pasillos y zonas de estancia. |
| `TransferSpace` | Puertas, ventanas, salidas y endpoints de conectores. |
| `NonNavigableSpace` | Muros y masas no transitables. |
| `ObjectSpace` | Columnas, mobiliario y obstáculos. |
| `NavigableBoundary` | Interfaz que puede cruzarse. |
| `NonNavigableBoundary` | Interfaz que no puede cruzarse normalmente. |
| `Node` | Dual de un `CellSpace`. |
| `Edge` | Dual de un `CellBoundary`. |
| `AnchorSpace` | Salida exterior u objetivo terminal de evacuación. |

SpatialEngine ya exporta este contrato; EvacEngine no debe volver a inferirlo desde listas legacy. `sourceFeatures[]` se utilizará para trazabilidad y diagnóstico, no como fuente primaria de colisiones o routing cuando existan `CellSpace` y `CellBoundary` derivados. El loader normalizará CRS, unidades y referencias, pero no reparará silenciosamente geometrías o celdas defectuosas.

### 2.2. `scenario_model.json`

Es la definición completa del experimento o situación simulada. Contendrá, en un único documento:

```text
scenario_model.json
├── metadata
├── indoorModelRef
├── catalogs
├── population
├── beaconSystem
├── hazards
├── environmentOverrides
├── routing
├── physics
├── scheduledEvents
├── simulationConfig
├── experiments              # opcional: matriz de comparaciones reproducibles
└── outputs
```

El escenario define **qué debe ocurrir**, no los resultados que ya ocurrieron. Las observaciones generadas durante la ejecución, rutas, trayectorias y métricas se guardan fuera del escenario. Puede contener una matriz declarativa de experimentos para comparar algoritmos y políticas sobre la misma definición, pero cada ejecución producirá un `run_manifest` separado e inmutable.

### 2.3. Resultados

Los resultados serán artefactos separados y reproducibles, por ejemplo:

```text
results/<run_id>/
├── run_manifest.json
├── events.ndjson
├── routes.json
├── trajectories.ndjson
├── metrics.json
├── metrics.csv
└── optional_snapshots/
```

### 2.4. Capas de estado

La arquitectura distinguirá explícitamente:

| Capa | Mutabilidad | Responsabilidad |
|---|---:|---|
| `IndoorStaticModel` | Inmutable | Geometría, primal, dual, niveles, conectores y salidas. |
| `ScenarioDefinition` | Inmutable | Población, balizas, hazards, física y routing declarados. |
| `RuntimeEnvironmentState` | Mutable | Puertas, ventanas, hazards activos, seguridad, congestión y cambios de topología. |
| `AgentState` | Mutable | Posición, nivel, cinemática, objetivo, ruta, percepción y estado físico. |
| `TaskState` | Mutable | Ayuda, rescate, transporte, apertura, ruptura o verificación. |
| `RoutingState` | Mutable/versionado | Grafo activo, snapshot de pesos, rutas y motivos de recálculo. |

Esta separación permite que un bombero abra una puerta o cree un paso temporal sin alterar el edificio original.

---

## 3. Diagnóstico del EvacEngine legacy y estrategia de migración

El archivo actual `src/MLSM_EvacEngine.py` mezcla en el mismo módulo:

- carga de JSON legacy;
- construcción geométrica;
- creación del grafo NetworkX;
- población y perfiles;
- física y comportamiento;
- fuego y congestión;
- métricas;
- visualización Matplotlib;
- interacción con el ratón;
- ejecución al importar;
- exportación final.

También depende de claves legacy como:

```text
configuracion
espacios_navegables
muros
conexiones_horizontales
agentesspawn
```

### 3.1. Elementos que conviene conservar

La física actual se conservará como **baseline extraído y configurable**, no como arquitectura final indivisible:

- movimiento continuo;
- radio físico y radio personal;
- repulsión frente a obstáculos;
- repulsión interpersonal;
- limitación de fuerza y velocidad;
- inercia;
- frenado por giro;
- cambio progresivo de objetivo;
- focus lock en portales como heurística provisional;
- línea de visión;
- antiatasco;
- recálculo ante cambios del entorno;
- registro de eventos.

Se recomienda encapsular este comportamiento bajo un nombre explícito, por ejemplo `LegacySteeringPhysics`, para poder compararlo con futuras alternativas sin confundirlo con una validación científica definitiva.

### 3.2. Elementos que deben desaparecer como contrato

- Heurísticas por nombres humanos.
- Distribución demográfica fija 70/15/15.
- Pesos mágicos `0.8` y `1.5`.
- Fuego modelado únicamente por distancia al midpoint y penalización `5000`.
- Congestión acumulativa sobre el peso ya penalizado.
- Un único `ContinuousSpace` para todas las plantas.
- Un único `nx.Graph` reconstruido desde el JSON legacy.
- Ejecución y apertura de Matplotlib al importar el módulo.
- Rutas de archivos hardcodeadas.
- La UI como reloj de simulación.
- El radio fijo de salida basado en un nombre que contiene `Salida`.

### 3.3. Compatibilidad legacy

La compatibilidad temporal debe adoptar esta forma:

```text
legacy JSON
  → LegacyV1Adapter
  → IndoorStaticModel + ScenarioDefinition normalizados
```

El núcleo no conocerá las claves legacy. El fallback se activará explícitamente, nunca mediante autodetección silenciosa.

---

## 4. Arquitectura interna objetivo

La reforma debe dividir responsabilidades, aunque inicialmente algunas clases vivan en menos archivos.

```text
src/evac_engine/
├── application/
│   ├── service.py
│   ├── commands.py
│   └── snapshots.py
├── io/
│   ├── indoor_loader.py
│   ├── scenario_loader.py
│   ├── reference_resolver.py
│   ├── semantic_validator.py
│   └── legacy_v1_adapter.py
├── domain/
│   ├── indoor.py
│   ├── scenario.py
│   ├── agents.py
│   ├── tasks.py
│   ├── routing.py
│   └── events.py
├── topology/
│   ├── canonical_graph.py
│   ├── resources.py
│   ├── overlays.py
│   └── breach_surfaces.py
├── routing/
│   ├── planner.py
│   ├── target_resolver.py
│   ├── cost_policies.py
│   ├── weight_compiler.py
│   └── waypoint_builder.py
├── physics/
│   ├── collision_world.py
│   ├── legacy_steering.py
│   ├── movement.py
│   └── visibility.py
├── simulation/
│   ├── model.py
│   ├── agent.py
│   ├── clock.py
│   ├── random_context.py
│   └── population_factory.py
├── sensing/
│   ├── beacon_simulator.py
│   ├── observations.py
│   └── fusion.py
├── outputs/
│   ├── metrics.py
│   ├── routes.py
│   ├── trajectories.py
│   └── run_manifest.py
└── ui_adapters/
    └── desktop/
```

### Interfaces fundamentales

```text
IndoorModelLoader.load(path) -> IndoorStaticModel
ScenarioModelLoader.load(path) -> ScenarioDefinition
SimulationAssembler.assemble(indoor, scenario) -> SimulationContext
CanonicalTopologyBuilder.build(indoor) -> CanonicalTopologyGraph
GraphOverlayManager.apply(topology, runtime_state) -> ActiveTopologySnapshot
WeightSnapshotCompiler.compile(graph, policy, snapshot, profile) -> WeightedRoutingSnapshot
TargetResolver.resolve(agent, snapshot) -> TargetSet
RoutePlanner.plan(request, weighted_graph) -> Route
WaypointPlanBuilder.build(route, indoor, profile) -> WaypointPlan
PhysicsStepper.propose(agent, snapshot, waypoint, dt) -> AgentIntent
EvacSimulation.step() -> SimulationSnapshot
AlgorithmRegistry.resolve(id) -> RoutingAlgorithm
BeaconObservationSource.read(t) -> BeaconObservation[]
ExperimentRunner.run(matrix) -> RunResult[]
```

La UI, los tests y una futura API web deben usar estas fronteras, no acceder directamente a objetos privados de Mesa o Shapely.

---

## 5. Topología canónica, grafos y routing multinivel

### 5.1. Vistas derivadas existentes

`graph_views.py` ya deriva, entre otras:

- `base_dual`;
- `space_adjacency`;
- `space_connectivity`;
- `room_adjacency`;
- `room_to_room_accessibility`;
- `transfer_to_transfer`;
- `door_to_door`;
- `vertical_connectivity`;
- `multilevel_space_connectivity`.

Estas vistas no son intercambiables: representan distintos niveles de abstracción. `space_connectivity` será el backbone principal porque mantiene `GeneralSpace`, `TransferSpace` y nodos virtuales de conexión.

### 5.2. Corrección de identidad vertical ya realizada

La conectividad vertical se normaliza actualmente a IDs canónicos de `CellSpace`, evitando mezclar:

```text
CS_L00_EP_...
```

con referencias duales:

```text
TL_NAV_L00:DS_NAV_L00:N_L00_EP_...
```

`vertical_connectivity.edges[*].connects` utiliza ahora `CellSpace.id`, conserva las referencias originales para auditoría y se compone con `space_connectivity` en `multilevel_space_connectivity`. La resolución debe preferir referencias completas, aceptar IDs locales solo cuando sean inequívocos, usar `connectedCells` cuando exista y recurrir a `connectedNodes → Node.duality → CellSpace` como fallback. Las conexiones equivalentes se deduplican y los endpoints no resolubles generan diagnósticos, nunca arcos colgantes.

No es necesario reexportar `indoor_model.json` por esta corrección: la normalización pertenece a la vista derivada. Adoptar `MultiDiGraph` tampoco obliga a cambiar SpatialEngine: una conexión física bidireccional exportada una sola vez se proyecta en EvacEngine como dos arcos runtime.

### 5.3. Pipeline topológico

```text
indoor_model.json + índices primal/dual
  → derive_graph_views(...)
  → multilevel_space_connectivity como backbone
  → CanonicalTopologyBuilder consulta también el modelo original
  → CanonicalTopologyGraph
  → RuntimeTopologyState
  → ProfileRoutingView
  → WeightedRoutingSnapshot
  → RoutePlanner
```

El builder no debe depender exclusivamente de la vista ya filtrada: debe consultar también el primal/dual original para conservar puertas, ventanas u otras conexiones potenciales que estén cerradas o no transitables en el estado inicial.

La selección del grafo se expresará mediante una receta, no mediante un único `sourceGraphView`:

```text
graphRecipe
├── backboneView = multilevel_space_connectivity
├── augmentations
├── projection
├── topologyOverrides
├── profileFilters
└── weightPolicyRef
```

### 5.4. `CanonicalTopologyGraph`

Se utilizará un `NetworkX.MultiDiGraph` interno.

**Razones:**

- una puerta bidireccional se representa mediante dos arcos;
- es posible volver por donde se ha venido;
- puede haber varias puertas entre el mismo par de espacios;
- subir y bajar pueden tener costes diferentes;
- una conexión futura puede ser unidireccional;
- cada conexión conserva su propia key y trazabilidad.

#### Nodos

Atributos mínimos:

| Atributo | Significado |
|---|---|
| `id` | Identidad canónica: normalmente `CellSpace.id`. |
| `nodeKind` | `Space`, `VirtualTransfer`, `OutsideTerminal`. |
| `cellSpaceRef` | Celda primal de origen. |
| `dualNodeRef` | Node dual original. |
| `levelRef` | Planta. |
| `navigationType` | `GeneralSpace` o `TransferSpace`. |
| `category` / `function` | Semántica de sala, puerta, salida o conector. |
| `locomotionTypes` | Compatibilidades espaciales. |
| `position` | Punto representativo para heurísticas y visualización. |
| `geometryRef` | Referencia al índice geométrico. |
| `isExit` | Verdadero para `TransferSpace.function=AnchorSpace`. |
| `connectorRef` | Conector vertical asociado, cuando exista. |
| `sourceRefs` | Trazabilidad a entidades originales. |

Los valores dinámicos —ocupación, seguridad, visibilidad o hazard— no pertenecen al nodo estático; viven en el overlay runtime.

#### Arcos

Atributos mínimos:

| Atributo | Significado |
|---|---|
| `arcId` / `edgeKey` | Identidad única del arco dirigido. |
| `fromNodeId`, `toNodeId` | Extremos canónicos. |
| `arcKind` | Movimiento horizontal, portal, conexión vertical, salida o acción requerida. |
| `resourceRef` | Puerta, ventana o conector físico compartido. |
| `baseEdgeRef`, `boundaryRef` | Trazabilidad primal/dual. |
| `transferSpaceRef`, `connectorRef` | Elemento de transferencia. |
| `fromLevelRef`, `toLevelRef` | Plantas de origen y destino. |
| `lengthM`, `verticalDeltaM` | Geometría de coste. |
| `locomotionTypes` | Modos permitidos. |
| `requiredCapabilities` | Capacidades necesarias. |
| `directionality` | Semántica de dirección. |
| `availabilityMode` | Siempre, controlado por escenario, acción requerida o creado en runtime. |
| `baseTraversalTimeS` | Tiempo base antes de overlays. |
| `sourceRefs` | Entidades que justifican la conexión. |

#### `ConnectionResource`

Los arcos de ambos sentidos comparten un recurso físico:

```text
ConnectionResource
├── resourceId
├── resourceKind
├── physicalEntityRef
├── sharedArcKeys
├── geometryRef
├── widthM
├── nominalCapacity
├── flowRatePersonsPerSecond
├── serviceModel
├── defaultState
├── scenarioControllable
├── openable
├── breakable
└── requiredCapabilities
```

Su estado runtime incluye apertura, bloqueo, ocupación, cola, flujo y motivo del bloqueo. Esto evita duplicar capacidad o mantener estados contradictorios entre direcciones.

### 5.5. Topología potencial y activa

Se distinguirán:

```text
PotentialTopologyGraph
    conexiones normales
    puertas cerradas o bloqueadas
    ventanas controlables
    conexiones habilitables

ActiveTopologySnapshot(t)
    solo arcos utilizables por un perfil en el instante t
```

Un muro rompible no debe representarse mediante un único nodo abstracto. Aunque una vista `room-wall-room` sea útil para análisis de adyacencia, no será el backbone de evacuación: un muro completo no determina el punto real de apertura. Se modelará como `BreachSurface`: una superficie geométrica potencial con geometría, material, espesor, celdas adyacentes y requisitos. Cuando una tarea de ruptura finaliza, se crea un `RuntimePortal` y los arcos correspondientes. Las columnas y elementos no rompibles nunca se convierten en candidatos.

### 5.6. Ruta topológica y plan físico

```text
Route
├── nodeSequence
├── arcSequence
├── edgeKeys
├── levelSequence
├── costBreakdown
├── graphVersion
└── creationTime
```

```text
WaypointPlan
├── MoveOnLevel
├── PortalCrossing
├── VerticalTransfer
├── ExitCrossing
└── arrivalConditions
```

El `RoutePlanner` no decide cómo girar físicamente en una puerta. El `WaypointPlanBuilder` traduce la ruta a portales, puntos y operaciones ejecutables y marca como no omitibles los portales o transferencias que deban cruzarse expresamente.

### 5.7. Salidas, ventanas y criterio de evacuación

Los targets normales son `TransferSpace` con `function=AnchorSpace`. No se exige un nodo exterior artificial. Un agente se considera evacuado preferentemente al cruzar una `AnchorBoundary`; como fallback geométrico controlado, al entrar en el `AnchorSpace`. No se usará un radio fijo ni el nombre del elemento. Las ventanas permanecen fuera del routing normal salvo que el escenario, el perfil y una capacidad explícita las habiliten.

---

## 6. Simulación, física, tiempo, aleatoriedad y multinivel

### 6.1. Tiempo físico

El escenario define:

```text
timeStepS
maxSteps
updateMode = synchronous
```

Velocidades, aceleraciones, reacciones, giros y transferencias se expresan en unidades físicas:

```text
speedMps
accelerationMps2
reactionTimeS
transferDurationS
```

La velocidad de reproducción de la UI no modifica el tiempo simulado.

### 6.2. Ciclo síncrono

Cada tick se divide en fases:

1. **Actualizar sistemas exógenos:** balizas, hazards, eventos y cambios completados.
2. **Crear `WorldSnapshot(t)`:** estado inmutable observado por todos.
3. **Percepción y decisión:** cada agente produce un `AgentIntent` sin mutar el mundo.
4. **Resolución colectiva:** colisiones, capacidades, colas, conflictos y tareas.
5. **Commit simultáneo:** aplicación de todos los estados a `t + dt`.
6. **Eventos, métricas y snapshot de UI.**

Esto evita que el resultado dependa del orden secuencial en que Mesa recorre los agentes.

### 6.3. Uso de Mesa

Mesa se aprovechará para:

- ciclo de simulación;
- registro y colección de agentes;
- reloj y pasos;
- ejecución por lotes;
- semillas y reproducibilidad;
- recopilación de datos.

EvacEngine seguirá delegando:

- geometría en Shapely;
- routing en NetworkX;
- presentación en un adaptador de UI.

No es necesario sustituir Mesa, pero sí dejar de usar Matplotlib como scheduler de la simulación.

### 6.4. Un espacio continuo por planta

```text
levelSpaces = {
    LEVEL_00: ContinuousSpace,
    LEVEL_01: ContinuousSpace,
    LEVEL_02: ContinuousSpace
}
```

La localización del agente será una unión de estados:

```text
OnLevel(levelRef, position2D)
InConnector(connectorRef, fromEndpoint, toEndpoint, progress, remainingTimeS)
```

Secuencia vertical:

1. Alcanzar el portal del endpoint.
2. Solicitar entrada al recurso.
3. Comprobar perfil, capacidad y estado.
4. Salir del `ContinuousSpace` de origen.
5. Permanecer `InConnector` durante el tiempo de transferencia.
6. Entrar en el `ContinuousSpace` de destino.
7. Continuar el siguiente segmento del `WaypointPlan`.

`directionality` determina si el conector puede recorrerse en ambos sentidos. `entrySide` y `exitSide` describen geometría de autoría, no una prohibición automática del sentido contrario.

### 6.5. Colisiones y dominio navegable

El dominio navegable será positivo:

```text
GeneralSpace ∪ TransferSpace permitido
```

Los obstáculos serán:

```text
NonNavigableSpace ∪ ObjectSpace
```

La comprobación tendrá en cuenta el radio del agente y no solo su centro. Debe admitir polígonos, multipolígonos, huecos y movimiento barrido. La línea de visión considerará obstáculos, dominio permitido, portales y tolerancias geométricas. Para escalar se mantendrán índices espaciales —por ejemplo `STRtree` o una abstracción equivalente— y cachés por planta/perfil, sin duplicar geometría dentro de NetworkX. Las coordenadas del modelo se conservarán mediante una transformación reversible cuando el origen no sea `(0,0)` o existan valores negativos; la primera versión operativa exigirá unidades métricas o una conversión explícita.

### 6.6. `RandomContext`

Una semilla global no basta. Se derivarán streams deterministas por namespace y entidad:

```text
population/spawn_01
agent.motion/agent_003
agent.behavior/agent_003
agent.anti_stuck/agent_003
beacon.signal/beacon_007
beacon.failure/beacon_007
hazard/hazard_001
routing.tie_break/agent_003
```

La derivación utilizará una función estable, no `hash()` de Python. Para decisiones por tick se incluirán `entityId`, `step` y `channel`, evitando dependencia del orden de iteración.

Esto garantiza comparaciones justas entre algoritmos con las mismas posiciones, balizas y hazards. Los desempates de routing, el muestreo de spawns y las decisiones probabilísticas usarán canales separados para que añadir una nueva baliza o agente no altere streams ajenos.

---

## 7. Modelo de agentes, comportamientos y tareas futuras

Un agente no se definirá mediante un único tipo rígido. Se compondrá por dimensiones:

| Dimensión | Ejemplos |
|---|---|
| Rol | Evacuado, guía, rescatista, bombero. |
| Locomoción | Walking, Rolling. |
| Rasgos físicos | Velocidad, aceleración, radio, resistencia. |
| Estado físico | Sano, herido, incapacitado, fatigado. |
| Percepción | Visibilidad, conocimiento, alcance sensorial. |
| Capacidades | Ayudar, empujar, cargar, abrir, romper, verificar. |
| Objetivo | Salida, grupo, víctima, hazard, zona por inspeccionar. |
| Equipamiento | Silla, máscara, herramienta, camilla. |
| Relaciones | Grupo, ayudante, equipo de rescate. |
| Estado dinámico | Esperando ayuda, acompañado, transportado, desorientado. |

`Elderly`, sobrepeso, lesión o baja visibilidad serán modificadores del perfil; no nuevos modos de locomoción.

### 7.1. Rolling y asistencia

El modelo debe quedar preparado para:

- silla de ruedas lenta sin ayuda;
- petición de ayuda a agentes próximos;
- aceptación o rechazo;
- ayudante que se aproxima y queda ocupado;
- empuje desde atrás con aumento de velocidad;
- una o dos personas ayudando;
- cruce asistido de escaleras o ventanas;
- operación lenta de transferencia;
- abandono temporal o definitivo de la silla;
- transporte de la persona;
- velocidad superior con rescatistas entrenados.

No debe implementarse como un simple multiplicador booleano. Se reservarán entidades:

```text
Task
Assignment
VictimRef
RescuerTeamRef
requiredCapabilities
status
progress
rendezvous
handoff
```

La misma infraestructura servirá para personas heridas que no pueden caminar.

### 7.2. Rescatistas y bomberos

El diseño debe admitir objetivos diferentes a una salida:

```text
TargetSelectionPolicy
├── nearest_reachable_exit
├── trapped_agent
├── agent_group
├── hazard_source
├── unverified_area
└── rescue_assignment
```

Un bombero tendrá mayor tolerancia al riesgo, pero no inmunidad. La transitabilidad dependerá de:

```text
severidad ambiental
+ perfil
+ equipamiento
+ exposición acumulada
+ capacidades
```

Las acciones sobre puertas, ventanas o muros modificarán el overlay runtime. Nunca reescribirán `indoor_model.json`.

Una ruta verificada por un rescatista producirá una observación con `verifiedAt`, `validUntil`, `confidence` y `verifiedBy`; reduce incertidumbre, no borra automáticamente el peligro físico.

### 7.3. Restricciones, misión y preferencias

Se distinguirán tres conceptos que no deben mezclarse:

- **restricción dura:** un arco no es utilizable, por ejemplo `Rolling` en una escalera sin asistencia;
- **objetivo de misión:** salida, víctima, grupo, zona o hazard;
- **preferencia blanda:** familiaridad, aversión a escaleras, seguimiento de grupo o tolerancia al riesgo.

Las preferencias blandas quedan inicialmente desactivadas o con coste cero, pero tendrán un punto de extensión propio en `CostPolicy`; nunca sustituirán restricciones de accesibilidad.

### 7.4. Inicialización de población y spawns

La resolución seguirá esta prioridad: `nodeRef`, `cellSpaceRef`, posición/región explícita y, solo como fallback diagnosticado, nodo navegable más cercano. Los spawns múltiples muestrearán posiciones reproducibles dentro del dominio permitido, respetando radio corporal, obstáculos y solapamientos iniciales. Un spawn incompatible o no resoluble producirá `invalid_spawn`, no una corrección silenciosa.

### 7.5. Humo y percepción

El humo tendrá efectos separados:

- riesgo ambiental;
- visibilidad;
- velocidad;
- desorientación;
- exposición acumulada.

Aunque la primera versión de balizas entregue directamente seguridad `[0,1]`, el modelo no debe reducir toda la dinámica del humo a un único peso de routing.

---

## 8. Balizas, seguridad, hazards y futura integración CEP

### 8.1. Dos niveles de procesamiento

Las balizas se procesan **individualmente y después en conjunto**.

```text
BeaconObservation individual
  → SpatialTemporalFusion
  → SafetyEstimate de CellSpace/Edge
  → política de routing
```

Una lectura individual conserva:

```text
beaconId
timeS
safety ∈ [0,1]
confidence
status
validUntil
```

La estimación fusionada conserva:

```text
entityRef
safety
confidence
timeS
contributingBeaconIds
fusionPolicyId
```

No se pierde la lectura original al fusionar.

### 8.2. Simplificación inicial

Inicialmente, cada baliza simulará directamente un valor continuo de seguridad:

```text
0 = inseguro
1 = seguro
```

Este valor representa conceptualmente la salida de un CEP local que ya hubiera procesado CO₂, humo, temperatura y otras variables. En el futuro se podrá sustituir el generador directo por:

```text
variables físicas simuladas
  → reglas CEP locales
  → safety individual
  → fusión global/contextual
```

sin modificar el motor de rutas.

### 8.3. Fuentes de observaciones y control de la simulación

El subsistema admitirá tres modos intercambiables bajo el mismo contrato: `generated` para curvas declarativas, `replay` para reproducir lecturas registradas y `external` para una futura fuente/servicio CEP. Además de la UI, existirá un script o CLI headless para generar, inspeccionar, exportar y reproducir observaciones sin arrancar la simulación completa. Esto permite controlar exactamente qué detecta cada baliza y repetir una ejecución.

### 8.4. Evolución suave y reproducible

La señal inicial será determinista y suave, definida por:

- valor inicial;
- puntos de control temporales;
- tiempos de inicio y fin;
- interpolación `linear`, `smoothstep` o curva equivalente;
- periodo, si es cíclica;
- estado y fallos opcionales;
- semilla solo cuando se solicite variación.

No se muestreará un valor aleatorio independiente en cada tick. La señal base, el ruido futuro y los fallos utilizarán streams separados del `RandomContext`.

### 8.5. Fusión

Una media simple no será la única opción, porque puede ocultar una lectura peligrosa. El escenario podrá elegir una política:

```text
minimum
weighted_mean
soft_min
latest_valid
custom
```

La ponderación podrá usar distancia, cobertura, confianza y antigüedad. La primera política predeterminada debe ser conservadora y documentada. Lecturas contradictorias, ausentes, fallidas o caducadas no se promediarán silenciosamente: afectarán a `confidence`, podrán activar una política de peor caso y quedarán registradas con los IDs contribuyentes.

### 8.6. Proyección espacial

Una baliza podrá asociarse a:

- un `CellSpace`;
- un `CellBoundary`;
- un `Node`;
- un `Edge`;
- una región geométrica;
- un radio de influencia.

La fusión produce seguridad de entidades espaciales; el `WeightSnapshotCompiler` decide después cómo proyectarla a arcos. La baliza no modifica directamente `edge.weight`.

### 8.7. Hazards

El contrato debe permitir hazards estáticos, programados y externos. En una primera etapa pueden activar:

- celdas bloqueadas;
- arcos bloqueados;
- penalización de riesgo;
- reducción de visibilidad;
- reducción de velocidad.

Más adelante podrán modelar propagación, exposición y predicción temporal. Los componentes de hazard y beacon deben mantenerse separados para poder auditar su influencia.

---

## 9. Estructura objetivo del único `scenario_model.json`

El documento seguirá siendo único, pero organizado por responsabilidad. Los nombres exactos deberán cerrarse al actualizar el schema.

```json
{
  "scenarioId": "...",
  "metadata": {},
  "indoorModelRef": {},
  "catalogs": {
    "agentProfiles": [],
    "roles": [],
    "capabilities": [],
    "targetPolicies": [],
    "routingAlgorithms": [],
    "routingCostPolicies": [],
    "beaconSignalModels": [],
    "beaconFusionPolicies": []
  },
  "population": {
    "agentGroups": [],
    "agentSpawns": [],
    "agents": []
  },
  "beaconSystem": {
    "beacons": [],
    "readingSimulation": {},
    "fusion": {},
    "routingMapping": {}
  },
  "hazards": [],
  "environmentOverrides": {},
  "routing": {},
  "physics": {},
  "scheduledEvents": [],
  "simulationConfig": {},
  "experiments": {
    "variants": [],
    "replications": 1
  },
  "outputs": {}
}
```

### 9.1. Reglas del schema

- Un único archivo físico, organizado con `$defs` internos.
- IDs únicos por catálogo y entidad.
- Referencias cruzadas validadas semánticamente además de JSON Schema.
- Unidades explícitas.
- Sin funciones Python arbitrarias dentro del JSON.
- Curvas y políticas declarativas mediante IDs y parámetros.
- `attributes` reservado para extensiones, no para ocultar conceptos centrales.
- Perfiles, roles y capacidades separados.
- Routing separado en algoritmo, coste, target y recálculo.
- Algoritmos y políticas personalizadas registradas por ID mediante una API de plugins/registro; el JSON solo selecciona y parametriza implementaciones permitidas, nunca contiene código ejecutable.
- Una matriz opcional de experimentos puede variar algoritmo, política, parámetros y réplica conservando las mismas entradas exógenas.

### 9.2. Población dentro del escenario

`population` debe admitir perfiles reutilizables, grupos, spawns y agentes explícitos. Cada perfil separa rol, locomoción, rasgos físicos, percepción, capacidades y equipamiento. El loader valida todas las referencias contra el Indoor Data Model y los catálogos antes de materializar agentes.

### 9.3. Routing dentro del escenario

```text
routing
├── graphRecipe
├── algorithm
├── costPolicy
├── targetPolicy
├── replanPolicy
├── constraints
├── dynamicWeights
└── alternativesPolicy
```

`dynamic_weighted` no se tratará como algoritmo. Dijkstra o A* son algoritmos; riesgo, tiempo o congestión son políticas de coste.

### 9.4. Física dentro del escenario

```text
physics
├── movementModel
├── bodyParameters
├── socialForces
├── collisionPolicy
├── visibilityModel
├── terrainFactors
└── antiStuckPolicy
```

Las constantes globales actuales se trasladarán aquí o a defaults versionados del motor.

---

## 10. Pesos, algoritmos y auditabilidad del routing

La composición avanzada no bloquea la reforma. La primera ejecución operativa utilizará:

```text
shortest_distance
minimum_travel_time
```

Preferencia inicial:

```text
baseTraversalTimeS = distanceM / effectiveSpeedMps + fixedTransferTimeS
```

Las restricciones duras no se convierten en números enormes:

```text
Rolling + Stair → arco no disponible
puerta bloqueada → arco no disponible
```

### 10.1. Componentes del coste

Desde el principio, cada snapshot admitirá:

```text
weightComponents
├── distance
├── travelTime
├── hazardRisk
├── beaconRisk
├── currentCongestion
├── predictedCongestion
├── accessibility
├── uncertainty
├── actionCost
└── effectiveWeight
```

Los componentes no implementados valdrán cero. El sistema conservará:

```text
CostPolicy
WeightSnapshotCompiler
GraphVersion
WeightPolicyVersion
WeightSnapshotId
```

### 10.2. Atributos nodales y coste de arista

No se copiarán permanentemente todos los atributos del nodo a cada arco. El peso se deriva de:

```text
estado del nodo destino
+ estado del arco
+ estado del recurso
+ perfil del agente
+ política de coste
```

El compilador produce un snapshot de pesos consumible por NetworkX y auditable por la UI.

### 10.3. Catálogo de algoritmos

La arquitectura debe admitir, sin mezclarlos:

- algoritmos de búsqueda: Dijkstra, A*, Yen, D* Lite u otros;
- políticas de coste: distancia, tiempo, riesgo, congestión o multicriterio;
- políticas de asignación: individual, grupo o coordinación global;
- políticas de recálculo: periódica o disparada por eventos;
- análisis de robustez: alternativas, disjoint paths, centralidad y agilidad.

La primera versión puede activar solo Dijkstra/A* y distancia/tiempo. La comparación científica posterior no debe exigir rehacer el grafo, los resultados ni la UI. `AlgorithmRegistry` y `CostPolicyRegistry` ofrecerán una interfaz estable para incorporar algoritmos propios, medidas de centralidad o robustez sin añadir condicionales al motor principal. Las vistas por perfil deben filtrar o evaluar el grafo compartido sin copiarlo íntegramente en cada recálculo.

El riesgo de hazard y las preferencias personales no necesitan una fórmula definitiva para arrancar: podrán permanecer desactivados, aplicar bloqueos explícitos o utilizar una política versionada sencilla. Lo obligatorio es que nunca queden ocultos dentro de un peso opaco y que puedan auditarse por componente.

### 10.4. Registro de rutas

Cada cálculo guardará:

```text
simulationTime
step
agentId
origin
targetsConsidered
targetSelected
algorithmId
costPolicyId
graphVersion
weightSnapshotId
nodeSequence
arcSequence
edgeKeys
costPerArc
weightBreakdown
totalCost
replanReason
```

---

## 11. UI de escenario, simulación y auditoría

La UI completa forma parte importante de la reforma. Debe ser fácil de usar, pero no acoplar el motor a una tecnología concreta.

### 11.1. Frontera de aplicación

```text
UI desktop actual/futura
        ↓ Commands
ApplicationService
        ↓
EvacEngineCore
        ↑ Snapshots + Events
UI desktop o Web API futura
```

Comandos típicos:

```text
LoadIndoorModel
LoadScenario
SaveScenario
PlaceBeacon
PlaceAgentSpawn
StartSimulation
PauseSimulation
StepSimulation
ResetSimulation
SetDoorState
ActivateHazard
ChangeRoutingPolicy
RequestReplan
```

Salidas:

```text
StaticMapSnapshot
SimulationSnapshot
GraphSnapshot
MetricSnapshot
DomainEvent
```

Todo será serializable. La UI no recibirá directamente objetos Shapely, NetworkX, Mesa o artistas Matplotlib. El `EventBus` publicará, al menos, eventos tipados como `ROUTE_CHANGED`, `EVACUATED`, `NO_ROUTE`, `HAZARD_ACTIVATED`, `BEACON_UPDATED`, `ENTERED_CONNECTOR`, `LEVEL_CHANGED` y `RESOURCE_STATE_CHANGED`.

### 11.2. Pestañas requeridas

#### Proyecto y validación

- abrir `indoor_model.json`;
- abrir, crear y guardar `scenario_model.json`;
- validar schema y semántica;
- mostrar warnings, IDs no resueltos y componentes desconectados;
- mostrar metadatos y checksums;
- historial undo/redo del escenario, indicador de cambios sin guardar y vista de diferencias antes de persistir.

#### Espacio indoor

- pestaña o selector por planta;
- vista conjunta de varias plantas;
- zoom, pan y selección;
- capas activables;
- primal, dual, `space_connectivity`, verticalidad y grafo activo;
- inspector de CellSpaces, boundaries, Nodes y Edges;
- estado y progreso de conectores.

#### Balizas

- colocar, mover y eliminar balizas;
- asociarlas a espacios o regiones;
- definir cobertura;
- configurar curvas suaves;
- reproducir y previsualizar lecturas;
- visualizar seguridad individual y fusionada;
- ver qué entidades y arcos reciben su influencia.

#### Agentes y población

- ubicar spawns mediante clic;
- crear agentes explícitos y grupos;
- elegir perfiles, roles y capacidades;
- configurar velocidad, radio, reacción y visibilidad;
- validar compatibilidad de movilidad.

#### Routing

- elegir receta de grafo;
- seleccionar algoritmo y política de coste;
- inspeccionar rutas, arcos y waypoints;
- mostrar pesos desglosados;
- forzar recálculos;
- comparar alternativas y futuras medidas de robustez.

#### Simulación

- play, pause, step y reset;
- velocidad de reproducción independiente de `timeStepS`;
- seguimiento de agentes;
- rutas actuales y targets;
- visualización simultánea de plantas;
- agentes `InConnector` y progreso vertical;
- estado de puertas, hazards y recursos.

#### Métricas y auditoría

- eventos;
- tiempos de evacuación;
- distancias y exposición;
- cambios de ruta;
- estado final por agente;
- exportación;
- comparación entre ejecuciones y variantes de una matriz experimental.

#### Diagnóstico

- versión del grafo y pesos;
- conexiones activas y potenciales;
- arcos filtrados por perfil;
- componentes desconectados;
- estado del `RandomContext`;
- errores de referencias y geometría;
- celdas degeneradas o residuales.

### 11.3. Preparación para web

La primera UI puede ser desktop, pero el contrato `Commands / Snapshots / Events` permitirá una futura API:

- HTTP para carga y configuración;
- WebSocket o stream para eventos y snapshots;
- GeoJSON para geometría;
- diffs dinámicos por tick en vez de retransmitir el edificio completo.

La UI Matplotlib actual puede conservarse como visualizador de depuración, no como arquitectura principal.

---

## 12. Resultados, validación, pruebas, fases y mantenimiento

### 12.1. Reproducibilidad y manifest de ejecución

Cada run debe registrar:

- ID y checksum del indoor model;
- ID y checksum del escenario;
- versión del motor;
- versión del schema;
- semilla raíz y política de aleatoriedad;
- `timeStepS` y `maxSteps`;
- algoritmo y parámetros;
- política de coste;
- versiones del grafo y snapshots de peso;
- estado final de todos los agentes.

Estados terminales admitidos:

```text
evacuated
no_route
trapped
incapacitated
invalid_spawn
max_steps_reached
```

No se asumirá que todos los escenarios terminan con todos los agentes evacuados.

### 12.2. Validación

Se aplicarán tres niveles:

1. **JSON Schema:** forma de los documentos.
2. **Validación semántica:** referencias, dualidades, IDs, unidades y compatibilidades.
3. **Validación operacional:** cada spawn y espacio relevante debe alcanzar un target admisible o producir un diagnóstico explícito.

Las `GeneralSpace` residuales minúsculas no se repararán silenciosamente. Se detectarán y reportarán para corregir la autoría o aplicar una política explícita.

### 12.3. Estrategia de pruebas

| Nivel | Ejemplos |
|---|---|
| Unitarias | Loaders, referencias, target resolver, pesos y filtros. |
| Topológicas | Composición horizontal/vertical, MultiDiGraph, arcos paralelos y dirección. |
| Geométricas | Colisión, dominio navegable, radio físico y cruce de portal. |
| Propiedades | Rolling no usa escalera sin ayuda; pesos no se acumulan; misma semilla, mismo resultado. |
| Integración | Una planta, tres plantas, hazard, balizas, cambio de ruta. |
| Regresión | Física legacy extraída con tolerancias y defectos conocidos excluidos. |
| UI | Comandos, edición de escenario, selección, snapshots y persistencia. |

Los goldens legacy solo conservarán comportamiento deseado; no congelarán errores como congestión acumulativa o detección por nombres.

### 12.4. Fases internas de la gran reforma

La reforma es de gran alcance, pero debe ejecutarse con puertas de aceptación:

1. **Fundación:** paquete, dependencias, ejecución headless, loaders y modelos runtime.
2. **Topología:** `MultiDiGraph`, recursos, verticalidad, targets y rutas topológicas.
3. **Física:** `LegacySteeringPhysics`, `dt`, colisiones, sincronización y espacios por planta.
4. **Escenario:** schema ampliado, perfiles, spawns, física y routing declarativos.
5. **Balizas:** despliegue, curvas suaves, observaciones y fusión básica.
6. **UI:** editor por pestañas, visualización multinivel, comandos y snapshots.
7. **Auditoría:** resultados, manifest, eventos, métricas y comparación.
8. **Extensiones:** hazards avanzados, congestión prevista, robustez, tareas cooperativas y rescatistas.

Estas fases son una estrategia de control de calidad, no una reducción del alcance arquitectónico.

### 12.5. Qué debe quedar operativo y qué solo preparado

| Capacidad | Operativa en la primera reforma | Preparada arquitectónicamente |
|---|---:|---:|
| Carga `indoor_model + scenario_model` | Sí | Sí |
| Una y varias plantas | Sí | Sí |
| Dijkstra/A* por distancia o tiempo | Sí | Sí |
| Rutas + waypoints | Sí | Sí |
| Física legacy desacoplada | Sí | Sí |
| Actualización síncrona | Sí | Sí |
| UI por pestañas | Sí | Sí |
| Balizas `[0,1]` con curvas suaves | Sí | Sí |
| Fusión básica de balizas | Sí | Sí |
| Hazard estático/programado básico | Deseable | Sí |
| Congestión observada | Puede ser básica | Sí |
| Congestión prevista | No obligatoria | Sí |
| CEP con CO₂, humo, temperatura | No | Sí |
| Rescatistas y tareas completas | No | Sí |
| Derribo de muros y transporte | No | Sí |
| Robustez y centralidad avanzadas | No | Sí |
| Optimización global multiagente | No | Sí |

### 12.6. Mapa de mantenimiento

Esta tabla indica dónde actualizar la documentación y el código cuando cambie un concepto.

| Cambio | Sección de este documento | Código principal esperado | Schema / datos | Tests |
|---|---|---|---|---|
| Nuevo tipo de espacio o boundary | 2 y 5 | `io/`, `topology/` | `indoor_model.schema.json` | Loader y topología |
| Nueva vista de grafo | 5 | `graph_views.py`, `topology/` | No necesariamente | Graph views |
| Nuevo conector vertical | 5 y 6 | `topology/`, `waypoint_builder.py` | Indoor + scenario overrides | Multinivel |
| Nuevo perfil o rasgo | 7 y 9 | `domain/agents.py`, `population_factory.py` | `catalogs.agentProfiles` | Agentes |
| Nueva capacidad o tarea | 7 | `domain/tasks.py`, resolutor colectivo | `capabilities`, políticas | Tareas |
| Nueva señal de baliza | 8 y 9 | `sensing/` | `beaconSystem` | Señales/fusión |
| Nueva política de fusión | 8 | `sensing/fusion.py` | catálogo de fusión | Fusión |
| Nuevo algoritmo de routing | 10 | `routing/planner.py` | catálogo de algoritmos | Comparativa |
| Nuevo componente de peso | 10 | `cost_policies.py`, `weight_compiler.py` | `dynamicWeights` | Pesos |
| Nueva métrica | 12 | `outputs/metrics.py` | `outputs` | Métricas |
| Nueva pestaña o interacción UI | 11 | `application/`, `ui_adapters/` | Según el editor | UI |
| Cambio de ciclo temporal | 6 | `simulation/model.py` | `simulationConfig` | Reproducibilidad |
| Cambio legacy | 3 | `legacy_v1_adapter.py` | Ninguno nuevo | Compatibilidad |

### 12.7. Investigación y calibración posterior

La arquitectura no sustituye la revisión científica. Antes de fijar políticas avanzadas deberán documentarse y compararse trabajos sobre: fusión CEP multisensor, caducidad/confianza de observaciones, routing dinámico sobre grafos, congestión observada y prevista, asignación de flujos, rutas alternativas, centralidad y robustez. Cada política adoptada tendrá referencia, supuestos, unidades, parámetros y pruebas de sensibilidad. La primera reforma debe dejar el banco experimental preparado para esa investigación.

También debe revisarse el entorno reproducible: el `requirements.txt` actual no declara todas las dependencias usadas por EvacEngine legacy, como Mesa, NetworkX o pandas. La reforma fijará versiones, separará dependencias de motor/UI y permitirá ejecución headless y CI.

### 12.8. Decisiones pendientes antes del megaprompt final

Deben cerrarse o dejarse explícitamente como decisión de implementación:

- toolkit de UI desktop;
- nombres exactos de las nuevas secciones y `$defs` del schema;
- política de fusión predeterminada;
- fórmula inicial de tiempo vertical por tipo de conector;
- política de congestión observada de primera versión;
- formato exacto de resultados y snapshots;
- versión de Mesa y dependencias declaradas;
- umbrales semánticos para celdas residuales y geometrías degeneradas;
- contrato exacto del registro de plugins y matriz de experimentos;
- modos y formato de replay de observaciones de balizas.

Ninguna de estas decisiones debe romper los principios y contratos definidos arriba.

### 12.9. Próximo artefacto: megaprompt de implementación

El megaprompt será un documento separado de esta arquitectura. Deberá ordenar el trabajo por fases y criterios de aceptación, exigir lectura completa de este `.md`, revisión del repositorio real, comunicación del progreso y permiso antes de commits, cambios destructivos o ampliaciones no solicitadas. El prompt corto posterior se limitará a señalar el archivo largo y exigir que se siga íntegramente; estas reglas operativas no deben contaminar los modelos de dominio.

---

## Referencias internas del repositorio

Este documento debe mantenerse coordinado con:

- `docs/technical/architecture/indoor_data_model_architecture.md`
- `schemas/indoor/indoor_model.schema.json`
- `schemas/indoor/scenario_model.schema.json`
- `src/indoor_data_model/graph_views.py`
- `src/indoor_data_model/builder.py`
- `src/MLSM_EvacEngine.py`
- `tools/visualize_indoor_model.py`
- `tests/test_graph_views.py`
- `tests/test_vertical_connectors.py`
- ejemplos de una y tres plantas
- OGC IndoorGML 2.0 Part 1 — Conceptual Model

Cuando una decisión arquitectónica cambie, deben actualizarse como mínimo: esta documentación, el schema afectado, los tests de contrato y la UI que exponga esa función.
