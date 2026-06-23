# Megaprompt para Codex — Reforma mayor de EvacEngine sobre Indoor Data Model

## 0. Instrucción principal

Realiza una **reforma arquitectónica mayor, coherente y funcional de EvacEngine** para abandonar como ruta principal el JSON legacy y trabajar con:

```text
indoor_model.json + scenario_model.json
```

El resultado debe permitir configurar, ejecutar, observar, auditar y comparar simulaciones de evacuación de una o varias plantas. No quiero únicamente un plan, un análisis o interfaces vacías: quiero una implementación real y verificable, desarrollada internamente por fases, con tests y formas de comprobación manual después de cada bloque.

La arquitectura objetivo ya está documentada en:

```text
docs/technical/architecture/evacengine_indoor_data_model_architecture.md
```

**Lee ese documento completo, de principio a fin, antes de modificar nada.** Trátalo como fuente canónica de intención. Este prompt concreta cómo llevarlo a código y qué debe quedar operativo.

También debes leer el resto de archivos de referencia indicados más abajo y contrastar siempre la documentación con el código real del repositorio. Cuando exista una discrepancia, no la ocultes: explíquela, toma la decisión menos destructiva compatible con la arquitectura y documenta la resolución.

---

## 1. Protocolo operativo obligatorio

### 1.1. Git y seguridad del trabajo

Antes de editar:

```bash
git status --short
git branch --show-current
git log -5 --oneline
```

Reglas absolutas:

- **No ejecutes `git add`.**
- **No ejecutes `git commit`.**
- No hagas `git commit --amend`.
- No crees PR.
- No hagas push.
- No uses `git reset`, `git restore`, `git checkout --`, `git clean` ni comandos destructivos sobre trabajo ajeno.
- No borres ni sobrescribas cambios preexistentes que no pertenezcan a esta tarea.
- No stages archivos de ninguna forma.
- Todos los cambios deben quedar sin stage para que el usuario pueda revisarlos.
- No versionarás outputs de simulación, cachés, entornos virtuales ni artefactos temporales.

Al terminar debes ejecutar y mostrar:

```bash
git diff --check
git diff --stat
git status --short
```

### 1.2. Comunicación del progreso

No trabajes como una caja negra. Antes de cada fase importante comunica brevemente:

1. qué vas a conseguir;
2. qué archivos prevés leer o modificar;
3. qué tests o comprobaciones usarás;
4. qué riesgos conocidos tiene la fase.

Al terminar cada fase informa:

1. cambios realizados;
2. decisiones de diseño tomadas;
3. tests exactos ejecutados y su resultado;
4. cómo puede verificarlo manualmente el usuario;
5. cualquier limitación real pendiente.

Continúa con la siguiente fase sin esperar confirmación salvo que aparezca una de las decisiones que requieren permiso explícito.

### 1.3. Uso de subagentes

Puedes y debes usar subagentes cuando ayuden a inspeccionar el repositorio, revisar schemas, diseñar tests, auditar routing, revisar la UI o validar la implementación.

Antes de lanzar cada subagente, anuncia:

- nombre o función;
- objetivo concreto;
- archivos que solo leerá o podrá modificar;
- entregable esperado.

Reglas para subagentes:

- ningún subagente puede ejecutar `git add`, `git commit`, reset, clean o push;
- no permitas escrituras concurrentes sobre los mismos archivos;
- el agente coordinador debe revisar e integrar cada propuesta;
- no aceptes cambios de un subagente sin ejecutar tests;
- no delegues la decisión arquitectónica final: la integración es responsabilidad del agente principal.

El usuario autoriza el uso de subagentes. Solo pide permiso adicional cuando el entorno lo exija o cuando el subagente vaya a proponer una actuación fuera del alcance acordado.

### 1.4. Decisiones que requieren permiso explícito

Detente y consulta antes de:

- añadir una dependencia externa grande de UI como PySide6, PyQt, Electron o similar;
- introducir una base de datos, servicio web o infraestructura distribuida;
- modificar `src/MLSM_SpatialEngine.py`;
- modificar `schemas/indoor/indoor_model.schema.json`;
- cambiar el contrato exportado por SpatialEngine;
- eliminar definitivamente el soporte legacy;
- borrar o renombrar masivamente módulos públicos;
- hacer cambios incompatibles no previstos en este prompt;
- modificar datos reales de ejemplo para ocultar un fallo del motor.

Quedan autorizadas, tras verificar compatibilidad, las dependencias de runtime que EvacEngine ya necesita conceptualmente y que el legacy ya importa o presupone: **Mesa, NetworkX y, solo si sigue siendo necesario, pandas**. También puede declararse `jsonschema` para validación. No añadas otras dependencias sin permiso.

### 1.5. Investigación técnica

Cuando necesites consultar documentación externa:

- usa fuentes oficiales para Mesa, NetworkX, Shapely, Matplotlib, Python/Tkinter y JSON Schema;
- registra en la documentación qué versión/API has adoptado;
- no copies patrones obsoletos sin contrastarlos con la versión instalada;
- no conviertas una decisión provisional en una afirmación científica no justificada.

---

## 2. Archivos que debes leer antes de implementar

Localiza las rutas equivalentes si la estructura ha cambiado.

### 2.1. Arquitectura y traspaso

Lee completos:

```text
docs/technical/architecture/evacengine_indoor_data_model_architecture.md
docs/technical/architecture/indoor_data_model_architecture.md
docs/technical/architecture/spatial_engine_expansion_handoff.md
```

Lee también cualquier documento posterior que mencione:

```text
EvacEngine
scenario_model
routing
beacons
hazards
vertical connectivity
Mesa
```

### 2.2. Schemas y ejemplos

```text
schemas/indoor/indoor_model.schema.json
schemas/indoor/scenario_model.schema.json
examples/indoor_data_model/minimal_scenario_model.json       # si existe
examples/indoor_data_model/una_sola_planta_indoor_model.json # o ruta equivalente
examples/indoor_data_model/tres_plantas_indoor_model.json    # o ruta equivalente
```

Busca todos los `scenario_model*.json` y todos los ejemplos reales del nuevo modelo.

### 2.3. Código espacial y vistas de grafo

```text
src/indoor_data_model/graph_views.py
src/indoor_data_model/builder.py
src/indoor_data_model/geometry.py
src/indoor_data_model/ids.py
src/indoor_data_model/__init__.py
```

Debes confirmar que la corrección de conectividad vertical ya existe:

- `vertical_connectivity.edges[*].connects` usa IDs canónicos de `CellSpace`;
- se conserva trazabilidad a `Node` y referencias completas;
- existe `multilevel_space_connectivity`;
- no hay endpoints fantasma `TL:DS:N_*` al componer;
- el fallback `connectedNodes -> Node.duality -> CellSpace` está cubierto;
- las conexiones equivalentes se deduplican.

No regresiones esa solución.

### 2.4. EvacEngine legacy

Lee completo:

```text
src/MLSM_EvacEngine.py
```

Traza de arriba abajo:

- carga legacy;
- constantes físicas;
- creación de `ContinuousSpace`;
- reconstrucción de muros;
- construcción del grafo;
- selección de rutas;
- focus lock;
- línea de visión;
- cruce de puertas;
- antiatasco;
- repulsión de muros y agentes;
- fuego;
- congestión;
- métricas;
- visualización;
- ejecución al importar.

No copies la clase monolítica a otro archivo. Extrae responsabilidades.

### 2.5. Tests, herramientas y dependencias

```text
tests/test_graph_views.py
tests/test_vertical_connectors.py
tests/**/test_*evac*.py
tests/**/test_*scenario*.py
tools/visualize_indoor_model.py
requirements.txt
pyproject.toml             # si existe
setup.cfg                  # si existe
```

Ejecuta primero la suite existente para obtener baseline. Si falla antes de tus cambios, documenta el fallo exacto y no lo atribuyas a la reforma.

---

## 3. Estado actual que debes respetar

### 3.1. Separación de contratos

El flujo principal es:

```text
SpatialEngine
  -> indoor_model.json

Editor/servicio de escenarios
  -> scenario_model.json

EvacEngine
  -> consume ambos
  -> simula
  -> genera resultados separados
```

`indoor_model.json` no contiene población, lecturas de balizas, hazards runtime, configuración de routing ni resultados.

`scenario_model.json` debe contener toda la configuración del escenario en **un único JSON validado por un único schema**, organizado internamente mediante secciones y `$defs`.

### 3.2. Semántica indoor

- `GeneralSpace`: sala, pasillo o zona navegable normal.
- `TransferSpace`: puerta, ventana, salida o endpoint de conector.
- `NonNavigableSpace`: muros y masa no transitable.
- `ObjectSpace`: columna, mueble u obstáculo.
- `NavigableBoundary`: interfaz cruzable.
- `NonNavigableBoundary`: interfaz no cruzable normalmente.
- `Node`: dual de un `CellSpace`.
- `Edge`: dual de un `CellBoundary`.
- `TransferSpace.function == AnchorSpace`: salida normal de evacuación.

### 3.3. Backbone topológico

Usa como fuente principal:

```text
multilevel_space_connectivity
```

que es:

```text
space_connectivity + vertical_connectivity normalizada
```

No reconstruyas un grafo legacy desde nombres o proximidad geométrica.

### 3.4. Decisiones consolidadas

- Grafo runtime: `networkx.MultiDiGraph`.
- Identidad canónica espacial: `CellSpace.id`.
- Conexión bidireccional: dos arcos dirigidos con un recurso físico compartido.
- Actualización de agentes: síncrona por fases.
- Espacio continuo: uno por planta.
- Transferencia vertical: estado temporal `InConnector`.
- Ruta topológica y trayectoria física: separadas.
- Aleatoriedad: streams deterministas por namespace y entidad.
- Pesos iniciales: distancia y tiempo estimado.
- Componentes dinámicos: contrato presente, inicialmente configurables o a cero.
- UI: cliente del motor mediante Commands/Snapshots/Events.
- Legacy: fallback explícito, nunca ruta principal.

---

## 4. Resultado funcional final

Al terminar, el repositorio debe permitir al usuario:

1. cargar un `indoor_model.json` de una o varias plantas;
2. crear, abrir, editar, validar y guardar un `scenario_model.json` único;
3. ubicar balizas visualmente y configurar su evolución suave `[0,1]`;
4. ubicar spawns y agentes, elegir perfiles y editar parámetros;
5. seleccionar Dijkstra o A*;
6. seleccionar coste por distancia o tiempo estimado;
7. ejecutar la simulación con actualización síncrona;
8. visualizar agentes, rutas, waypoints, puertas y conectores por planta;
9. observar a agentes cambiar de planta mediante un estado temporal de conector;
10. pausar, avanzar un step, reiniciar y cambiar velocidad de reproducción sin alterar `timeStepS`;
11. inspeccionar nodos, arcos, recursos, pesos y motivos de recálculo;
12. observar lecturas individuales y seguridad fusionada de balizas;
13. activar opcionalmente una influencia básica de balizas/hazards sobre routing;
14. producir rutas, eventos, trayectorias y métricas auditables;
15. ejecutar todo en modo headless desde CLI;
16. repetir una ejecución con la misma semilla y obtener el mismo resultado;
17. comparar al menos Dijkstra y A* sobre las mismas entradas;
18. conservar el comportamiento físico útil del legacy como baseline desacoplado;
19. mantener preparado el modelo para futuras tareas cooperativas y rescatistas sin fingir que ya están implementadas;
20. revisar todos los cambios sin que haya ningún archivo staged ni commit nuevo.

---

## 5. Arquitectura de paquetes objetivo

Adapta los nombres a las convenciones reales del repositorio, pero mantén la separación de responsabilidades. Una estructura recomendada es:

```text
src/evac_engine/
├── __init__.py
├── __main__.py
├── cli.py
├── application/
│   ├── service.py
│   ├── commands.py
│   ├── snapshots.py
│   └── event_bus.py
├── io/
│   ├── indoor_loader.py
│   ├── scenario_loader.py
│   ├── reference_resolver.py
│   ├── semantic_validator.py
│   ├── results_writer.py
│   └── legacy_v1_adapter.py
├── domain/
│   ├── indoor.py
│   ├── scenario.py
│   ├── agents.py
│   ├── tasks.py
│   ├── routing.py
│   ├── sensing.py
│   └── events.py
├── topology/
│   ├── canonical_graph.py
│   ├── resources.py
│   ├── overlays.py
│   ├── geometry_index.py
│   └── breach_surfaces.py
├── routing/
│   ├── registry.py
│   ├── planner.py
│   ├── target_resolver.py
│   ├── profile_view.py
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
│   ├── population_factory.py
│   └── intents.py
├── sensing/
│   ├── beacon_simulator.py
│   ├── observations.py
│   ├── fusion.py
│   └── projection.py
├── hazards/
│   ├── model.py
│   └── scheduler.py
├── outputs/
│   ├── metrics.py
│   ├── routes.py
│   ├── trajectories.py
│   └── run_manifest.py
└── ui/
    ├── desktop_app.py
    ├── view_models.py
    ├── map_canvas.py
    └── tabs/
```

No fragmentes artificialmente cada función si el resultado son docenas de módulos vacíos. La prioridad es que cada dependencia apunte en la dirección correcta:

```text
UI/Application -> Domain services -> Simulation/Routing/Physics
```

Nunca:

```text
Domain -> Tkinter/Matplotlib
Routing -> UI
Loader -> ejecución de simulación
Agent -> lectura directa de JSON
```

`src/MLSM_EvacEngine.py` debe dejar de ejecutar al importarse. Conviértelo, si es útil para compatibilidad, en un wrapper fino o entrypoint que delegue al nuevo paquete. No dejes dos motores divergentes.

---

## 6. Modelos runtime y contratos internos

Usa dataclasses, enums y tipos explícitos salvo que la base del repositorio justifique otra opción. Evita introducir Pydantic sin permiso.

### 6.1. `IndoorStaticModel`

Debe contener o referenciar:

- ID y metadata del modelo;
- CRS, unidades y transformación interna reversible;
- niveles por ID;
- CellSpaces por ID;
- CellBoundaries por ID;
- Nodes y Edges por ID;
- índices de dualidad;
- geometrías Shapely por referencia;
- espacios navegables;
- obstáculos;
- salidas;
- conectores verticales;
- vistas de grafo derivadas;
- diagnósticos de carga.

No copies polígonos Shapely dentro de todos los nodos NetworkX. Mantén un índice geométrico central y referencias.

### 6.2. `ScenarioDefinition`

Debe ser inmutable durante una ejecución y contener:

- metadata e ID;
- referencia y checksum esperado del indoor model;
- catálogos;
- perfiles y población;
- balizas y sus generadores;
- hazards;
- overrides iniciales;
- routing;
- física;
- eventos programados;
- configuración temporal;
- outputs;
- experimentos opcionales.

### 6.3. `RuntimeEnvironmentState`

Debe contener:

- reloj y step;
- estados de puertas, ventanas y conectores;
- arcos activos/deshabilitados;
- recursos y colas;
- hazards activos;
- observaciones de balizas;
- seguridad fusionada;
- visibilidad y factores de velocidad por espacio;
- congestión observada;
- versión topológica;
- versión de pesos.

### 6.4. `AgentState`

Separar al menos:

- identidad;
- perfil y rol;
- locomoción;
- capacidades/equipamiento;
- localización `OnLevel` o `InConnector`;
- posición/velocidad/aceleración;
- target vigente;
- Route vigente;
- WaypointPlan y progreso;
- tiempo de reacción;
- visibilidad/percepción;
- exposición básica;
- estado terminal;
- motivo del último recálculo;
- memoria antiatasco.

### 6.5. `TaskState`

Crea el contrato y estados mínimos para extensiones futuras:

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

No implementes comportamientos falsos de rescate. Basta con que el dominio, target resolver y event bus puedan incorporar tareas más adelante sin reescribir el agente base.

### 6.6. Objetos serializables para UI

`SimulationSnapshot`, `GraphSnapshot`, `MetricSnapshot` y eventos deben poder serializarse a JSON. No expongas directamente:

- objetos Mesa;
- grafos NetworkX;
- geometrías Shapely;
- artistas Matplotlib;
- callbacks internos.

Geometría para UI: GeoJSON o estructuras simples.

---

## 7. Loader y validación de `indoor_model.json`

### 7.1. Carga

Implementa:

```text
IndoorModelLoader.load(path) -> IndoorStaticModel
```

Debe:

1. leer UTF-8;
2. validar JSON Schema;
3. comprobar `featureType == IndoorFeatures`;
4. normalizar unidades y CRS local;
5. indexar niveles y capas;
6. indexar CellSpaces, boundaries, Nodes y Edges;
7. resolver referencias completas y locales de forma inequívoca;
8. validar dualidades CellSpace<->Node y Boundary<->Edge;
9. derivar graph views mediante la implementación existente;
10. comprobar endpoints de `multilevel_space_connectivity`;
11. clasificar navegables, obstáculos y salidas;
12. construir el índice geométrico;
13. producir diagnósticos estructurados.

### 7.2. Resolución de referencias

La identidad canónica de un nodo espacial de routing será `CellSpace.id`.

La resolución debe:

- preferir referencias completas;
- aceptar un ID local solo si es único;
- resolver `Node -> duality -> CellSpace`;
- conservar referencias originales;
- rechazar ambigüedades;
- no inventar IDs;
- no crear nodos colgantes.

### 7.3. Geometría y unidades

La primera implementación operativa debe aceptar unidades métricas. Si el modelo no está en metros:

- aplicar una conversión explícita declarada;
- o producir un error claro.

Admite:

- Polygon;
- MultiPolygon cuando aparezca;
- huecos interiores;
- coordenadas negativas;
- origen distinto de `(0,0)`.

No repares silenciosamente geometría inválida. Un `buffer(0)` u otra reparación solo puede aplicarse como política explícita, registrada en diagnósticos.

### 7.4. Validación semántica

Diagnósticos mínimos:

```text
DUPLICATE_ID
AMBIGUOUS_REFERENCE
UNRESOLVED_REFERENCE
INVALID_DUALITY
INVALID_GEOMETRY
UNSUPPORTED_UNIT
DEGENERATE_NAVIGABLE_CELL
UNRESOLVED_VERTICAL_ENDPOINT
DISCONNECTED_NAVIGABLE_COMPONENT
NO_EXIT
```

Las `GeneralSpace` residuales minúsculas se reportan; no se eliminan ni fusionan automáticamente.

---

## 8. Nuevo `scenario_model.schema.json`

Evoluciona el schema existente, manteniendo JSON Schema Draft 2020-12, `$defs`, IDs estables y `additionalProperties: false` donde sea razonable.

El escenario será un único JSON. No lo dividas en varios documentos en esta reforma.

### 8.1. Secciones raíz objetivo

Implementa una estructura equivalente a:

```json
{
  "scenarioId": "SCN_001",
  "scenarioName": "Evacuación base",
  "metadata": {},
  "indoorModelRef": {},
  "catalogs": {},
  "population": {},
  "beaconSystem": {},
  "hazards": [],
  "environmentOverrides": {},
  "routing": {},
  "physics": {},
  "scheduledEvents": [],
  "simulationConfig": {},
  "experiments": [],
  "outputs": {},
  "scenarioDataModel": {}
}
```

Puedes ajustar nombres menores solo si documentas por qué mejoran claridad o compatibilidad. No escondas conceptos principales en `attributes`.

### 8.2. Catálogos

Debe haber IDs reutilizables para:

```text
agentProfiles
roles
capabilities
equipment
targetPolicies
routingAlgorithms
costPolicies
replanPolicies
beaconSignalModels
beaconFusionPolicies
```

El JSON selecciona y parametriza implementaciones registradas. No contiene código Python.

### 8.3. Población

Debe admitir:

- perfiles;
- grupos;
- spawns por CellSpace, posición o región;
- agentes explícitos;
- count;
- distribución de perfiles;
- semilla derivada;
- validación geométrica.

Un perfil debe separar:

```text
roleRef
locomotion
physicalTraits
perception
capabilityRefs
equipmentRefs
behaviorPolicyRef
targetPolicyRef
```

Atributos físicos mínimos:

```text
baseSpeedMps
maxAccelerationMps2
radiusM
personalSpaceRadiusM
reactionTimeS
visibilityM
```

Incluye ejemplos operativos para:

- walking estándar;
- rolling independiente;
- elderly como modificador Walking más lento;
- perfil lento/sobrepeso como modificador, no nueva locomoción.

Deja preparados, sin fingir implementación completa:

- rescatista;
- bombero;
- herido no ambulante;
- capacidades `assist`, `push`, `carry`, `open_blocked_door`, `use_window`, `breach_wall`, `verify_route`.

### 8.4. Routing

Debe separar:

```text
graphRecipe
algorithm
costPolicy
targetPolicy
replanPolicy
constraints
dynamicWeights
alternativesPolicy
```

No uses `dynamic_weighted` como nombre de algoritmo.

Ejemplo conceptual:

```json
{
  "graphRecipe": {
    "backboneView": "multilevel_space_connectivity",
    "augmentations": [],
    "projection": "canonical_multidigraph"
  },
  "algorithm": {
    "algorithmId": "dijkstra"
  },
  "costPolicy": {
    "policyId": "minimum_travel_time"
  },
  "targetPolicy": {
    "policyId": "nearest_reachable_anchor"
  },
  "replanPolicy": {
    "triggers": ["route_invalidated", "target_invalidated"]
  }
}
```

### 8.5. Física

Incluye:

```text
movementModel
bodyParameters
socialForces
collisionPolicy
visibilityModel
terrainFactors
antiStuckPolicy
connectorTransferModels
```

Las constantes legacy dejan de ser globales no configurables.

### 8.6. Balizas

`beaconSystem` debe incluir:

```text
beacons
readingSimulation
fusion
routingProjection
```

Cada baliza necesita:

```text
beaconId
levelRef
position
attachedTo / affectedEntityRefs
coverage
signalModelRef o signalModel inline
measurementMode = processed_safety | raw_variables
sensorChannels opcionales
confidence/status defaults
```

La primera reforma opera con `processed_safety`: cada baliza entrega directamente un valor de seguridad `[0,1]`, como si un CEP local ya hubiera procesado CO₂, humo, temperatura u otras variables. `raw_variables` y `sensorChannels` deben quedar modelados para el futuro, pero no exigen implementar ahora un CEP físico completo.

Modos de observación preparados:

```text
generated
replay
external
```

En esta reforma deben quedar operativos `generated` y, si es viable sin complejidad excesiva, `replay` inline. `external` puede ser una interfaz preparada.

### 8.7. Hazards

Representa hazards estáticos o programados con:

```text
hazardId
hazardType
levelRef
geometry o affectedEntityRefs
activation
severity [0,1]
effects
```

Efectos básicos configurables:

```text
blockRouting
riskFactor
visibilityFactor
speedFactor
```

No implementes propagación avanzada de fuego/humo en esta reforma.

### 8.8. Compatibilidad del schema

- Versiona el nuevo contrato.
- Actualiza o crea ejemplos válidos.
- Añade tests de schema.
- Si el repositorio contiene ejemplos del draft anterior, proporciona una adaptación explícita o mensajes de migración claros.
- No mantengas el draft anterior como ruta principal silenciosa.

---

## 9. Loader de escenario y ensamblado

Implementa:

```text
ScenarioModelLoader.load(path) -> ScenarioDefinition
SimulationAssembler.assemble(indoor, scenario) -> SimulationContext
```

### 9.1. Validaciones cruzadas

Comprueba:

- `indoorModelId` y checksum cuando exista;
- IDs únicos en catálogos;
- referencias de perfiles, roles y capacidades;
- CellSpaces, Nodes, Edges, boundaries y niveles referenciados;
- spawns dentro de dominio navegable;
- spawns fuera de obstáculos;
- compatibilidad de locomoción;
- balizas en niveles existentes;
- cobertura y entidades afectadas válidas;
- hazards y overrides válidos;
- algoritmos/políticas registrados;
- unidades y rangos;
- semilla, `timeStepS` y `maxSteps` válidos.

### 9.2. Materialización de población

Para `count > 1`:

- muestrea posiciones reproducibles dentro del CellSpace o región;
- respeta el radio físico;
- evita obstáculos;
- evita solapamientos iniciales razonables;
- limita intentos;
- genera diagnóstico si no cabe toda la población;
- usa `RandomContext`, nunca random global descontrolado.

---

## 10. Topología canónica y `MultiDiGraph`

### 10.1. Pipeline

```text
IndoorStaticModel
  -> derive_graph_views
  -> multilevel_space_connectivity
  -> CanonicalTopologyBuilder consulta primal/dual original
  -> PotentialTopologyGraph
  -> RuntimeTopologyState
  -> ProfileRoutingView
  -> WeightedRoutingSnapshot
```

### 10.2. Nodos canónicos

Atributos mínimos:

```text
id
nodeKind
cellSpaceRef
dualNodeRef
levelRef
layerRef
navigationType
category
function
locomotionTypes
position
geometryRef
isExit
connectorRef
sourceRefs
```

`NonNavigableSpace` y `ObjectSpace` no entran como nodos de routing normal.

Nodos virtuales deben usar un namespace estable y no colisionar con CellSpace IDs.

### 10.3. Arcos dirigidos

Cada conexión física bidireccional genera dos arcos.

Atributos mínimos:

```text
arcId
edgeKey
fromNodeId
toNodeId
arcKind
resourceRef
baseEdgeRef
boundaryRef
transferSpaceRef
connectorRef
fromLevelRef
toLevelRef
lengthM
verticalDeltaM
locomotionTypes
requiredCapabilities
directionality
availabilityMode
baseTraversalTimeS
sourceRefs
```

Conserva edge key en Route. No basta con una secuencia de nodos porque puede haber puertas paralelas.

### 10.4. `ConnectionResource`

Crea recursos compartidos para puertas, ventanas y conectores:

```text
resourceId
resourceKind
physicalEntityRef
sharedArcKeys
geometryRef
widthM
nominalCapacity
flowRatePersonsPerSecond
serviceModel
defaultState
scenarioControllable
openable
breakable
requiredCapabilities
```

Estado runtime:

```text
state
occupancy
queueLength
currentFlow
blockedReason
changedAt
```

Bloquear una puerta debe afectar a sus arcos correspondientes sin duplicar capacidad.

### 10.5. Topología potencial

Incluye como conexiones potenciales discretas:

- puertas cerradas;
- puertas bloqueadas;
- ventanas habilitables;
- conexiones temporalmente inactivas.

No introduzcas los muros completos como un único nodo routable.

Crea un índice `BreachSurface` preparado para el futuro con:

```text
id
wallCellRef
boundaryRefs
adjacentCellRefs
geometryRef
material
thicknessM
loadBearing
breachable
requiredCapabilities
estimatedActionTimeS
```

No es obligatorio que la ruptura esté operativa ahora. Sí debe evitarse una arquitectura que la haga imposible.

### 10.6. No modificar SpatialEngine

La proyección a `MultiDiGraph` pertenece a EvacEngine. No dupliques Edges en SpatialEngine. No cambies el schema indoor para representar ambos sentidos.

---

## 11. Routing operativo

### 11.1. Registro de algoritmos

Implementa un registro extensible:

```text
AlgorithmRegistry
CostPolicyRegistry
TargetPolicyRegistry
ReplanPolicyRegistry
```

La API debe permitir registrar implementaciones propias por ID sin añadir cadenas de `if/elif` al núcleo.

### 11.2. Algoritmos obligatorios

Operativos:

- Dijkstra;
- A*.

A* debe usar una heurística admisible. Si no puede garantizarse una estimación vertical adecuada, utiliza una heurística conservadora o cero antes que una heurística incorrecta.

Preparados por contrato, no necesariamente implementados:

- Yen k-shortest paths;
- D* Lite;
- rutas disjuntas;
- centralidad/robustez;
- asignación global.

### 11.3. Políticas de coste obligatorias

Operativas:

```text
shortest_distance
minimum_travel_time
```

Base recomendada:

```text
baseTraversalTimeS = distanceM / effectiveSpeedMps + fixedTransferTimeS
```

Las restricciones duras eliminan/deshabilitan el arco:

```text
Rolling + Stair -> no disponible
puerta bloqueada -> no disponible
capacidad requerida ausente -> no disponible
```

No uses pesos enormes para simular imposibilidad.

### 11.4. Componentes de peso

Desde el principio, cada arco ponderado debe exponer:

```text
distance
travelTime
hazardRisk
beaconRisk
currentCongestion
predictedCongestion
accessibility
uncertainty
actionCost
effectiveWeight
```

Componentes no activados: cero.

Nunca hagas:

```python
edge["weight"] += penalty
```

Cada snapshot se recompone desde bases inmutables.

### 11.5. Proyección de atributos nodales

No copies permanentemente la seguridad de un espacio a todas sus aristas. Implementa:

```text
Node state + Arc state + Resource state + Agent profile + CostPolicy
  -> WeightSnapshotCompiler
  -> effectiveWeight por arco
```

Guarda el desglose para auditoría.

### 11.6. `TargetResolver`

Default operativo:

```text
nearest_reachable_anchor
```

Targets normales:

```text
TransferSpace.function == AnchorSpace
```

No uses nombres ni radio fijo.

Diseña la petición de routing:

```text
RoutingRequest
origin
targetPolicy
agentProfile
capabilities
constraints
costPolicy
graphVersion
simulationTime
```

El contrato debe admitir futuros targets:

- agente atrapado;
- grupo;
- hazard;
- zona sin verificar;
- tarea de rescate.

### 11.7. Replan

Triggers básicos:

```text
initial_plan
route_invalidated
target_invalidated
resource_state_changed
beacon_threshold_crossed     # si está activo
hazard_changed               # si está activo
periodic                     # configurable
manual_request
```

Evita recalcular innecesariamente en cada tick.

### 11.8. Route auditable

Debe guardar:

```text
routeId
agentId
simulationTime
step
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
levelSequence
costPerArc
weightBreakdown
totalCost
replanReason
```

---

## 12. `WaypointPlanBuilder` y movimiento físico

### 12.1. Separación obligatoria

```text
Route topológica
  -> WaypointPlanBuilder
  -> plan físico
```

El plan físico debe tener operaciones tipadas:

```text
MoveOnLevel
PortalCrossing
VerticalTransfer
ExitCrossing
```

### 12.2. Portales

Usa geometría de `CellBoundary`/TransferSpace cuando exista para obtener puntos de cruce. Los portales importantes son no omitibles.

El chaining por línea de visión puede conservarse como optimización, pero nunca saltará:

- una puerta que deba cruzarse;
- una boundary requerida;
- una transferencia vertical;
- una operación de salida.

### 12.3. Fallbacks

Si falta geometría:

1. usa waypoint de Edge;
2. usa punto representativo del TransferSpace;
3. usa Node destino;
4. registra diagnóstico.

No ocultes el fallback.

### 12.4. Evacuación

Orden preferido:

1. cruce de `AnchorBoundary`;
2. entrada válida en `AnchorSpace` como fallback.

Al evacuar:

- marcar estado terminal;
- emitir `EVACUATED`;
- registrar tiempo, salida y ruta;
- retirar al agente del espacio físico cuando corresponda.

---

## 13. Física y colisiones

### 13.1. Extraer baseline legacy

Conserva en una implementación desacoplada:

- radio físico/personal;
- repulsión de obstáculos;
- repulsión social;
- fuerza máxima;
- inercia;
- frenado por giro;
- transición de dirección;
- antiatasco;
- línea de visión;
- penalización de terreno.

Nómbrala de forma explícita, por ejemplo:

```text
LegacySteeringPhysics
```

No la presentes como validación científica definitiva.

### 13.2. Tiempo físico

Usa:

```text
timeStepS
speedMps
accelerationMps2
reactionTimeS
```

La UI no determina el tiempo físico.

Documenta cómo se mapean los defaults legacy a unidades físicas para mantener un baseline razonable.

### 13.3. Dominio y obstáculos

Dominio positivo:

```text
GeneralSpace union TransferSpace permitido
```

Obstáculos:

```text
NonNavigableSpace union ObjectSpace
```

La validez de una posición requiere:

- pertenecer al dominio navegable del perfil;
- no intersecar un obstáculo expandido por el radio;
- pertenecer a la planta correcta.

### 13.4. Colisión

Debe considerar:

- radio del agente;
- movimiento barrido entre posición anterior y propuesta;
- puertas estrechas;
- polígonos con huecos;
- MultiPolygon;
- agentes entre sí;
- resolución síncrona.

Evita túneles a través de muros por pasos grandes.

Usa un índice espacial por planta para evitar iterar sobre todos los obstáculos en cada consulta.

### 13.5. Línea de visión

Debe respetar:

- obstáculos;
- dominio navegable;
- portales;
- tolerancia geométrica;
- perfil.

No bloquees por un simple toque numérico al borde si el cruce corresponde al portal correcto.

---

## 14. Simulación síncrona con Mesa

### 14.1. Mesa

Inspecciona la versión instalada y la API vigente. Usa Mesa para:

- Model y agentes;
- colección/registro;
- ejecución por pasos;
- recopilación de datos si aporta valor;
- batch runs;
- semilla/reproducibilidad en coordinación con `RandomContext`.

No uses Matplotlib `FuncAnimation` como scheduler del motor.

### 14.2. Tick síncrono

Implementa:

1. `update_external_systems(t)`;
2. `WorldSnapshot(t)` inmutable;
3. cada agente produce `AgentIntent`;
4. resolución colectiva;
5. commit simultáneo;
6. eventos/métricas/snapshot.

Los agentes no deben mutar posiciones globales durante `decide()`.

### 14.3. Intents

Incluye al menos:

```text
MoveIntent
EnterConnectorIntent
ExitIntent
ReplanIntent
NoOpIntent
```

Reserva contratos para:

```text
RequestAssistanceIntent
AcceptTaskIntent
ModifyResourceIntent
```

### 14.4. Estados terminales

Admite:

```text
evacuated
no_route
trapped
incapacitated
invalid_spawn
max_steps_reached
```

La simulación termina cuando:

- todos los agentes están en estado terminal;
- o se alcanza `maxSteps`;
- o el usuario detiene la ejecución.

No dejes bucles infinitos si no hay salida.

---

## 15. Multinivel y conectores

### 15.1. Un `ContinuousSpace` por nivel

```text
levelSpaces[levelId] = ContinuousSpace(...)
```

Un agente está en uno de estos estados:

```text
OnLevel(levelRef, position2D)
InConnector(connectorRef, fromEndpointRef, toEndpointRef, progress, remainingTimeS)
```

No debe existir físicamente en dos plantas a la vez.

### 15.2. Entrada y salida de conector

1. alcanzar portal del endpoint;
2. solicitar entrada;
3. comprobar movilidad, estado y capacidad;
4. entrar en cola si procede;
5. salir del espacio de origen;
6. avanzar `InConnector`;
7. entrar en el nivel destino;
8. continuar el WaypointPlan.

### 15.3. Bidireccionalidad

`directionality = bidirectional` genera ambos arcos. `entrySide` y `exitSide` sirven para geometría, no prohíben el recorrido inverso.

### 15.4. Tiempo inicial por tipo

Implementa modelos configurables y sencillos:

- Stair: distancia/velocidad vertical o factor de velocidad específico;
- Ramp: longitud/factor de terreno;
- Elevator: transferencia temporizada simple, sin lógica completa de cabina;
- same-level connector: recorrido físico normal o transferencia corta según geometría.

Documenta la fórmula exacta y sus parámetros. No la presentes como calibración científica.

### 15.5. Congestión del conector

Mantén un recurso compartido con:

- capacidad;
- ocupación;
- cola;
- throughput.

La primera versión puede usar una cola FIFO determinista.

---

## 16. `RandomContext` reproducible

### 16.1. Semilla raíz y streams

Deriva semillas mediante una función estable, por ejemplo SHA-256, usando:

```text
rootSeed
namespace
entityId
replicationIndex
```

No uses `hash()` de Python.

Namespaces mínimos:

```text
population/<spawnId>
agent.motion/<agentId>
agent.behavior/<agentId>
agent.anti_stuck/<agentId>
beacon.signal/<beaconId>
beacon.failure/<beaconId>
hazard/<hazardId>
routing.tie_break/<agentId>
```

### 16.2. Independencia

Añadir una baliza no debe cambiar el muestreo de población. Activar ruido de una baliza no debe cambiar la curva base. Cambiar el algoritmo de routing no debe alterar señales exógenas.

### 16.3. Decisiones por tick

Para ruido/decisiones por step, deriva por:

```text
entityId + step + channel
```

para evitar dependencia del orden de iteración.

### 16.4. Tests

Incluye tests que demuestren:

- misma semilla = mismos spawns;
- misma semilla = mismas lecturas;
- añadir un stream no modifica otro;
- Dijkstra y A* reciben las mismas entradas exógenas.

---

## 17. Modelo de agentes operativo y extensible

### 17.1. Composición, no tipos rígidos

No crees clases combinatorias como `ElderlyRollingInjuredWithHelper`.

Separar:

```text
role
locomotion
physicalTraits
healthState
perception
capabilities
targetPolicy
equipment
relationships
dynamicState
```

### 17.2. Comportamientos operativos iniciales

- Evacuado Walking hacia AnchorSpace.
- Evacuado Rolling hacia AnchorSpace, sin escaleras.
- Elderly/slow como Walking con velocidad/aceleración modificadas.
- Visibilidad reducida por humo con reducción de velocidad configurable.
- Reacción inicial configurable.

### 17.3. Asistencia futura

Modela interfaces y estados para:

```text
needs_assistance
requesting_assistance
helper_reserved
helper_approaching
assistance_ready
assisted_movement
transfer_operation
carried
released
```

Pero no implementes toda la cooperación en esta reforma salvo que ya exista infraestructura madura y tests claros.

### 17.4. Rescatistas futuros

Deja preparados:

- targets distintos de salidas;
- tolerancia al riesgo por perfil;
- capacidades de abrir/brechar/verificar;
- `TaskState`;
- observaciones verificadas con timestamp/confianza/caducidad;
- runtime topology overlay.

Define un contrato explícito, aunque inicialmente no se produzca en simulación normal:

```text
SafetyVerificationObservation
entityRefs
verifiedBy
verifiedAt
validUntil
observedSafety
confidence
inspectionType
```

Una verificación de rescatista reduce incertidumbre durante un intervalo; no borra automáticamente el peligro físico ni modifica `indoor_model.json`.

No simules que un bombero atraviesa cualquier hazard sin efecto. El diseño futuro debe diferenciar severidad, equipo, tolerancia y exposición.

---

## 18. Balizas y simulación de lecturas

### 18.1. Semántica

Convención inicial:

```text
safety = 1.0 -> seguro
safety = 0.0 -> peligro extremo
```

Cada baliza produce una observación individual:

```text
beaconId
simulationTime
safety
confidence
status
validUntil / age
levelRef
affectedEntityRefs
```

Nunca pierdas las lecturas individuales al fusionar.

### 18.2. Generador suave

Implementa un generador determinista sin ruido por defecto con:

- keyframes tiempo/valor;
- interpolación suave (`smoothstep` o cúbica monotónica segura);
- sample period;
- clamp `[0,1]`;
- hold before/after;
- previsualización;
- stream independiente para futuras variaciones.

Ejemplo:

```text
t=0   -> 1.00
t=30  -> 0.90
t=60  -> 0.30
```

No hagas random walk por step.

### 18.3. Script/CLI de lecturas

Crea un comando verificable para:

- cargar escenario;
- simular lecturas durante un intervalo;
- imprimir o exportar observaciones;
- seleccionar balizas;
- fijar sample period;
- reproducir exactamente con la misma semilla.

Ejemplo orientativo:

```bash
python -m src.evac_engine beacons \
  --scenario examples/indoor_data_model/scenario_beacons_demo.json \
  --duration 120 \
  --step 0.5 \
  --output outputs/debug/beacon_observations.ndjson
```

Ajusta el entrypoint a la estructura real.

### 18.4. Fusión

Implementa una capa separada:

```text
BeaconObservation[]
  -> SpatialTemporalFusion
  -> SpatialSafetyEstimate
```

`SpatialSafetyEstimate` debe contener:

```text
entityRef
safety
confidence
simulationTime
contributingBeaconIds
fusionPolicyId
```

Políticas operativas mínimas:

- `conservative_min`;
- `weighted_mean` por confianza y, cuando exista, distancia/cobertura.

Usa `conservative_min` como default seguro salvo que el scenario seleccione otra. Documenta pros/contras.

### 18.5. Proyección a routing

La fusión produce seguridad de espacios/entidades. El routing decide cómo usarla.

Implementa una política básica opcional y auditable:

```text
risk = 1 - safety
```

Con configuración para:

- desactivar influencia;
- añadir penalización gradual;
- bloquear por debajo de un umbral crítico;
- registrar `beaconRisk` separado.

No mezcles esta política con la fusión.

### 18.6. Varias balizas

Prueba:

- dos balizas en un espacio;
- valores contradictorios;
- una baliza stale/offline;
- cobertura solapada;
- evolución suave;
- cambio de ruta opcional al cruzar un umbral.

---

## 19. Hazards y humo básicos

### 19.1. Activación programada

Admite hazards con inicio/fin programado y área o referencias afectadas.

### 19.2. Efectos separados

No reduzcas humo a un único peso. Mantén componentes:

- riesgo de ruta;
- visibilidad;
- velocidad;
- exposición acumulada básica.

### 19.3. Primera implementación

Es suficiente con:

- hazard estático/programado;
- severidad `[0,1]`;
- bloqueo opcional de espacios/arcos;
- factor de visibilidad;
- factor de velocidad;
- penalización de riesgo auditable;
- evento de activación/desactivación.

No implementes CFD, propagación física compleja ni CEP raw en esta reforma.

---

## 20. Congestión observada

Implementa una primera versión simple, determinista y desactivable:

- ocupación por CellSpace;
- densidad estimada por área;
- cola por `ConnectionResource`;
- ocupación de conectores;
- componente `currentCongestion` recomputado desde cero.

No implementes obligatoriamente congestión prevista. Deja el contrato:

```text
predictedCongestion = 0
```

por ahora.

Evita el bug legacy de acumulación indefinida.

---

## 21. Application service, commands, snapshots y eventos

### 21.1. Comandos

Implementa DTOs/comandos equivalentes a:

```text
LoadIndoorModel
LoadScenario
CreateScenario
SaveScenario
ValidateProject
PlaceBeacon
MoveBeacon
DeleteBeacon
PlaceAgentSpawn
UpdateAgentProfile
StartSimulation
PauseSimulation
StepSimulation
ResetSimulation
SetPlaybackSpeed
SetDoorState
ActivateHazard
ChangeRoutingPolicy
RequestReplan
ExportResults
```

### 21.2. Snapshots

```text
StaticMapSnapshot
SimulationSnapshot
GraphSnapshot
MetricSnapshot
ValidationSnapshot
```

### 21.3. Eventos

Vocabulario mínimo:

```text
SIMULATION_STARTED
SIMULATION_PAUSED
SIMULATION_FINISHED
ROUTE_PLANNED
ROUTE_CHANGED
NO_ROUTE
EVACUATED
INVALID_SPAWN
BEACON_UPDATED
SAFETY_ESTIMATE_UPDATED
HAZARD_ACTIVATED
HAZARD_DEACTIVATED
RESOURCE_STATE_CHANGED
ENTERED_CONNECTOR
EXITED_CONNECTOR
LEVEL_CHANGED
MAX_STEPS_REACHED
```

Cada evento debe tener ID, tiempo, step, entity refs y payload serializable.

---

## 22. UI desktop por pestañas

### 22.1. Toolkit

Si el repositorio no contiene ya un toolkit desktop adecuado, usa **Tkinter/ttk + Matplotlib embebido**, porque permite pestañas y formularios sin introducir una dependencia grande. Mantén la UI en un adaptador separado.

Si Tkinter no está disponible en el entorno CI:

- el core y los tests headless deben seguir funcionando;
- la importación de EvacEngine no debe fallar por ello;
- documenta cómo instalar soporte Tk en el sistema;
- prueba view-models y commands sin abrir ventana.

No añadas PySide/PyQt sin permiso.

### 22.2. Arquitectura

```text
Desktop UI
  -> Commands
ApplicationService
  -> EvacEngineCore
  -> Snapshots + Events
Desktop UI
```

La UI nunca debe:

- acceder a `model.agents` directamente;
- mutar NetworkX;
- modificar objetos Shapely;
- llamar a métodos privados del motor;
- usar el timer gráfico como tiempo físico.

### 22.3. Pestaña Proyecto y validación

Debe permitir:

- abrir indoor model;
- crear/abrir/guardar scenario model;
- mostrar ruta e IDs;
- mostrar schema errors y semantic diagnostics;
- mostrar checksums;
- indicar cambios sin guardar;
- undo/redo de edición del escenario si es viable;
- validar antes de simular.

### 22.4. Pestaña Espacio indoor

- selector de planta;
- vista de una planta;
- vista de varias plantas en paneles;
- zoom y pan;
- selección por clic;
- capas activables:
  - GeneralSpace;
  - TransferSpace;
  - NonNavigableSpace;
  - ObjectSpace;
  - boundaries;
  - dual;
  - space connectivity;
  - vertical connectivity;
  - active routing graph;
  - waypoints;
- inspector de entidad;
- visualización de conectores y progreso.

### 22.5. Pestaña Balizas

- colocar/mover/eliminar por clic;
- asociar a CellSpace o cobertura;
- tabla de balizas;
- editor de keyframes;
- preview de curva;
- play de lecturas;
- valor individual;
- seguridad fusionada;
- entidades/arcos afectados;
- selector de política de fusión.

### 22.6. Pestaña Agentes y población

- colocar spawn por clic;
- elegir CellSpace;
- editar count;
- seleccionar perfil/grupo;
- crear agentes explícitos;
- editar velocidad, radio, reacción, visibilidad y locomoción;
- avisar si Rolling se ubica en zona incompatible;
- previsualizar posiciones materializadas con semilla.

### 22.7. Pestaña Routing

- seleccionar graph recipe;
- Dijkstra/A*;
- distancia/tiempo;
- toggles de baliza, hazard y congestión;
- inspeccionar Route y WaypointPlan;
- mostrar arc keys;
- mostrar weight breakdown;
- forzar replan;
- elegir agente;
- visualizar rutas alternativas si existen en el futuro.

### 22.8. Pestaña Simulación

- start;
- pause;
- single step;
- reset;
- stop;
- playback speed;
- reloj y step;
- seguimiento de agente;
- rutas y targets;
- estado terminal;
- agente InConnector y progreso;
- estado de recursos;
- activar un hazard programado/manual mediante comando, no mutación directa.

### 22.9. Pestaña Métricas y auditoría

- eventos filtrables;
- evacuados/no route/trapped;
- tiempos por agente;
- distancia;
- número de replans;
- salida usada;
- tiempo en conectores;
- exposición básica;
- exportación;
- comparación Dijkstra/A*.

### 22.10. Pestaña Diagnóstico

- graph version;
- weight snapshot ID;
- componentes desconectados;
- arcos deshabilitados por perfil;
- refs no resueltas;
- geometrías degeneradas;
- recursos/colas;
- streams RandomContext;
- errores de plugin/policy;
- celdas residuales.

### 22.11. Preparación web

Aunque implementes desktop:

- DTOs JSON serializables;
- geometría GeoJSON;
- static snapshot separado de dynamic diffs;
- no dependencias del core respecto a Tk;
- events y commands transportables;
- documenta cómo una futura API HTTP/WebSocket envolvería ApplicationService.

No implementes servidor web ahora.

---

## 23. CLI y ejecución headless

Crea un entrypoint claro sin efectos al importar.

Comandos mínimos orientativos:

```bash
python -m src.evac_engine validate --indoor ... --scenario ...
python -m src.evac_engine inspect-graph --indoor ... --scenario ...
python -m src.evac_engine simulate --indoor ... --scenario ... --output-dir ...
python -m src.evac_engine ui --indoor ... --scenario ...
python -m src.evac_engine beacons --scenario ... --duration ...
python -m src.evac_engine compare --indoor ... --scenario ... --algorithms dijkstra,astar
```

Ajusta el namespace si el paquete se instala de otro modo.

La CLI debe:

- devolver exit codes útiles;
- imprimir errores legibles;
- admitir `--seed`, `--max-steps`, `--headless` cuando proceda;
- no abrir UI en comandos headless;
- no escribir fuera del output dir solicitado;
- no modificar inputs.

---

## 24. Resultados y auditabilidad

Cada ejecución debe crear un directorio propio:

```text
results/<run_id>/
├── run_manifest.json
├── events.ndjson
├── routes.json
├── trajectories.ndjson
├── metrics.json
└── metrics.csv
```

No es obligatorio usar exactamente todos los archivos si justificas una variante equivalente, pero deben separarse definición y resultados.

### 24.1. `run_manifest.json`

Incluye:

- run ID;
- timestamps;
- indoor model ID/checksum;
- scenario ID/checksum;
- engine version;
- schema version;
- Python y dependencias relevantes;
- seed root;
- random policy version;
- `timeStepS`;
- `maxSteps`;
- algorithm/cost policy;
- graph recipe;
- final status;
- output files.

### 24.2. Métricas mínimas

- estado final por agente;
- tiempo de evacuación;
- distancia recorrida;
- replans;
- salida usada;
- tiempo de reacción;
- tiempo en conector;
- tiempo total;
- colisiones/rechazos de movimiento si se registran;
- exposición básica;
- summary global.

### 24.3. Trayectorias

Cada muestra:

```text
simulationTime
step
agentId
locationState
levelRef
x
y
connectorRef
progress
```

### 24.4. Comparación

Implementa un runner sencillo para ejecutar el mismo escenario con Dijkstra y A*, mismas semillas y mismas señales. Produce un resumen comparativo.

---

## 25. Compatibilidad legacy

### 25.1. Adaptador explícito

```text
legacy v1 JSON
  -> LegacyV1Adapter
  -> modelos runtime normalizados
```

El núcleo no debe preguntar por:

```text
configuracion
espacios_navegables
muros
conexiones_horizontales
agentesspawn
```

### 25.2. Invocación

El legacy debe requerir una opción explícita, por ejemplo:

```text
--legacy-v1
```

No autodetectes silenciosamente.

### 25.3. Baseline

Conserva tests o ejemplos que permitan comparar la física deseada, pero no congeles bugs:

- congestión acumulativa;
- detección por substrings;
- salida por radio fijo;
- ejecución infinita sin ruta;
- pesos mágicos.

---

## 26. Dependencias y empaquetado

### 26.1. Declaración real

El `requirements.txt` actual puede no declarar Mesa, NetworkX o pandas aunque el legacy los importe. Corrige la declaración de dependencias tras inspeccionar el entorno.

Preferencias:

- evita pandas si el módulo estándar `csv` cubre las salidas;
- usa NetworkX para routing;
- usa Mesa para el ABM;
- usa Shapely para geometría;
- usa Matplotlib solo como render/plot;
- usa jsonschema para validación si se incorpora.

### 26.2. Versiones

- comprueba versión instalada;
- elige una API compatible;
- fija versiones razonables o rangos compatibles;
- documenta la decisión;
- evita depender de APIs deprecadas.

### 26.3. Importación

Debe funcionar:

```bash
python -c "import src.evac_engine"
```

sin abrir ventanas, ejecutar simulaciones ni escribir archivos.

---

## 27. Estrategia de implementación por fases

Esta es una gran reforma. Implementa por fases y mantén el repositorio ejecutable después de cada una.

### Fase 0 — Preflight y baseline

Objetivos:

- leer docs/código;
- inventariar repo;
- ejecutar tests existentes;
- revisar dependencias;
- confirmar corrección vertical;
- identificar escenarios existentes.

Entregable:

- resumen de baseline;
- lista de riesgos;
- mapa de archivos;
- ninguna modificación todavía hasta completar inspección.

Verificación:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Fase 1 — Fundación del paquete y contratos

Objetivos:

- crear paquete `evac_engine`;
- modelos runtime;
- loaders básicos;
- semantic diagnostics;
- CLI base;
- eliminar efectos de import del legacy;
- declarar dependencias.

Criterios:

- import limpio;
- validate command;
- indoor y escenario se cargan;
- errores estructurados;
- tests unitarios.

Verificación manual:

```bash
python -m src.evac_engine validate --indoor <one_floor> --scenario <minimal>
```

### Fase 2 — Scenario schema y editor de datos base

Objetivos:

- ampliar schema;
- ejemplos válidos;
- profiles/spawns;
- routing/physics declarativos;
- beacons/hazards secciones;
- tests schema y refs.

Criterios:

- ejemplo mínimo válido;
- ejemplo multinivel válido;
- invalid refs fallan claramente;
- un único JSON de escenario.

### Fase 3 — Topología canónica y routing

Objetivos:

- MultiDiGraph;
- resources;
- verticalidad;
- profile views;
- Dijkstra/A*;
- targets AnchorSpace;
- Route auditable.

Criterios:

- una planta y tres plantas;
- Rolling no usa Stair;
- Walking sí puede;
- bidireccionalidad real;
- puertas paralelas conservan keys;
- no nodos fantasma.

### Fase 4 — Waypoints, física y simulación síncrona

Objetivos:

- WaypointPlan;
- baseline legacy extraído;
- CollisionWorld;
- dt;
- synchronous intents/commit;
- espacios por planta;
- `InConnector`.

Criterios:

- agente no atraviesa muros;
- cruza puertas por portal;
- sube/baja conector;
- termina en AnchorSpace;
- `NO_ROUTE` no bloquea.

### Fase 5 — Balizas, hazards y pesos básicos dinámicos

Objetivos:

- generador suave;
- observaciones;
- fusión;
- UI/CLI preview;
- proyección opcional a peso;
- hazard programado;
- visibilidad/velocidad simple;
- congestión observada básica.

Criterios:

- curvas reproducibles;
- lecturas individuales conservadas;
- fusión auditable;
- componente de peso separado;
- no acumulación.

### Fase 6 — UI completa por pestañas

Objetivos:

- ApplicationService;
- Commands/Snapshots/Events;
- editor scenario;
- mapa multinivel;
- balizas;
- agentes;
- routing;
- simulación;
- métricas/diagnóstico.

Criterios:

- core headless sigue funcionando;
- carga/guarda scenario;
- colocar baliza/spawn por clic;
- play/pause/step/reset;
- multi-floor visible;
- inspección de pesos.

### Fase 7 — Outputs, experimentos y auditoría

Objetivos:

- run manifest;
- events/routes/trajectories/metrics;
- compare Dijkstra/A*;
- reproducibilidad;
- documentación de verificación.

Criterios:

- outputs completos;
- mismo seed reproducible;
- comparación usa mismas señales;
- no inputs modificados.

### Fase 8 — Compatibilidad, documentación y limpieza

Objetivos:

- legacy adapter explícito;
- wrapper fino;
- documentación actualizada;
- guía de uso;
- estado de implementación;
- suite completa.

No elimines legacy definitivamente.

---

## 28. Tests obligatorios

Usa el framework ya predominante; actualmente parece `unittest`. No introduzcas tests frágiles dependientes de animaciones o sleeps.

### 28.1. Loader/validación

- indoor model de una planta;
- indoor model de tres plantas;
- refs ambiguas;
- dualidad inválida;
- unidad no soportada;
- celdas residuales diagnosticadas;
- scenario válido/invalid refs;
- checksum mismatch.

### 28.2. Topología

- canonical IDs CellSpace;
- MultiDiGraph;
- dos arcos por conexión bidireccional;
- arcos paralelos;
- shared ConnectionResource;
- vertical endpoints conectados;
- no `TL:DS:N_*` como nodos fantasma;
- windows potential disabled;
- NonNavigable/Object excluidos.

### 28.3. Routing

- Dijkstra y A* mismo coste con heurística válida;
- shortest distance;
- minimum travel time;
- nearest reachable AnchorSpace;
- puerta bloqueada no se usa;
- vuelta por arco inverso;
- Rolling sin stair;
- Walking con stair;
- ruta conserva edge keys;
- no route produce estado/evento.

### 28.4. Pesos

- no acumulación;
- componentes suman según política;
- base inmutable;
- hazard/beacon off = 0;
- umbral bloquea cuando se activa;
- node safety proyectada en compilador, no copiada permanentemente.

### 28.5. Waypoints/física

- portal no se salta;
- agente no atraviesa muro;
- radio físico;
- movimiento barrido;
- colisión con ObjectSpace;
- salida por AnchorSpace/Boundary;
- línea de visión;
- antiatasco determinista.

### 28.6. Sincronización

- todos perciben snapshot t;
- commit simultáneo;
- orden de iteración no cambia resultado;
- resource change visible en tick siguiente según contrato.

### 28.7. Multinivel

- `OnLevel -> InConnector -> OnLevel`;
- subida y bajada;
- progreso y duración;
- Rolling en rampa/ascensor;
- Rolling no en escalera;
- conector con capacidad/cola;
- agentes no existen en dos espacios a la vez.

### 28.8. RandomContext

- reproducibilidad;
- independencia de streams;
- spawn determinista;
- beacon determinista;
- tie break determinista.

### 28.9. Balizas

- smooth curve;
- clamp;
- stale/offline;
- conservative_min;
- weighted_mean;
- contributors;
- proyección a espacio/arco;
- replan por threshold cuando se habilita.

### 28.10. Hazard/humo

- activación programada;
- bloqueo;
- reducción de visibilidad;
- reducción de velocidad;
- exposición acumulada básica;
- desactivación restaura peso base.

### 28.11. Outputs

- manifest;
- eventos NDJSON válidos;
- Route serializable;
- trayectoria con level/connector;
- métricas;
- no modificar input;
- run IDs únicos.

### 28.12. UI/Application

Tests headless de:

- command dispatch;
- scenario mutation;
- dirty state;
- snapshots serializables;
- selección de planta/entidad;
- start/pause/step/reset;
- place beacon/spawn commands;
- validation errors.

La ventana real se verifica manualmente.

---

## 29. Escenarios de aceptación

Crea ejemplos mínimos, claros y versionables. Reutiliza los indoor models reales sin modificarlos.

### A. Una planta, ruta simple

- 1 Walking;
- 1 spawn;
- 1 o más AnchorSpaces;
- Dijkstra por distancia;
- evacúa sin atravesar obstáculos.

### B. Una planta, perfiles distintos

- Walking;
- Rolling;
- Elderly/slow;
- velocidades diferentes;
- rutas compatibles.

### C. Tres plantas

- agente en nivel superior;
- salida en nivel inferior o alcanzable;
- usa conector;
- eventos de cambio de nivel;
- visualización por plantas.

### D. Escalera vs rampa/ascensor

- Walking puede usar escalera;
- Rolling no;
- Rolling elige rampa/ascensor si existe.

### E. Balizas suaves

- dos balizas en el mismo espacio;
- una desciende suavemente;
- otra permanece segura;
- se muestran lecturas y fusión;
- routing influence off y on comparables.

### F. Hazard programado

- hazard se activa;
- cambia visibilidad/peso o bloquea;
- agente recalcula;
- al desaparecer no queda penalización acumulada.

### G. Puerta bloqueada

- ruta inicial usa puerta;
- resource state cambia;
- se invalida ruta;
- agente puede volver y elegir alternativa.

### H. No route

- agente aislado;
- termina `no_route`;
- simulación finaliza correctamente.

### I. Comparación Dijkstra/A*

- mismo modelo, scenario y seed;
- mismo coste/ruta cuando corresponde;
- tiempos de cálculo y métricas registrados.

---

## 30. Comandos de verificación esperados

Adapta paths reales, pero entrega comandos equivalentes.

### Suite base

```bash
python -m unittest tests.test_graph_views tests.test_vertical_connectors -v
python -m unittest discover -s tests -p "test_*.py" -v
```

### Validación

```bash
python -m src.evac_engine validate \
  --indoor examples/indoor_data_model/una_sola_planta_indoor_model.json \
  --scenario examples/indoor_data_model/scenario_single_floor.json
```

### Grafo

```bash
python -m src.evac_engine inspect-graph \
  --indoor examples/indoor_data_model/tres_plantas_indoor_model.json \
  --scenario examples/indoor_data_model/scenario_multilevel.json
```

### Simulación headless

```bash
python -m src.evac_engine simulate \
  --indoor examples/indoor_data_model/una_sola_planta_indoor_model.json \
  --scenario examples/indoor_data_model/scenario_single_floor.json \
  --output-dir outputs/evacengine/single_floor
```

### Multinivel

```bash
python -m src.evac_engine simulate \
  --indoor examples/indoor_data_model/tres_plantas_indoor_model.json \
  --scenario examples/indoor_data_model/scenario_multilevel.json \
  --output-dir outputs/evacengine/multilevel
```

### Balizas

```bash
python -m src.evac_engine beacons \
  --scenario examples/indoor_data_model/scenario_beacons_demo.json \
  --duration 120 \
  --step 0.5
```

### Comparación

```bash
python -m src.evac_engine compare \
  --indoor examples/indoor_data_model/una_sola_planta_indoor_model.json \
  --scenario examples/indoor_data_model/scenario_single_floor.json \
  --algorithms dijkstra,astar \
  --output-dir outputs/evacengine/comparison
```

### UI

```bash
python -m src.evac_engine ui \
  --indoor examples/indoor_data_model/tres_plantas_indoor_model.json \
  --scenario examples/indoor_data_model/scenario_multilevel.json
```

---

## 31. Verificación manual de la UI

Crea una guía reproducible, por ejemplo:

```text
docs/technical/verification/evacengine_refactor_verification.md
```

Debe indicar paso a paso:

1. abrir modelo de tres plantas;
2. cambiar de planta;
3. activar capas;
4. hacer zoom/pan;
5. seleccionar CellSpace/Edge;
6. crear baliza;
7. editar keyframes y ver curva;
8. crear spawn;
9. elegir perfil Rolling;
10. seleccionar Dijkstra/tiempo;
11. validar;
12. iniciar simulación;
13. pausar y step;
14. observar cambio de planta;
15. inspeccionar Route y weights;
16. activar hazard o bloquear puerta;
17. observar replan;
18. exportar resultados;
19. repetir con misma semilla;
20. comparar Dijkstra/A*.

Incluye el resultado visual esperado y qué diagnóstico consultar si falla.

---

## 32. Documentación que debes actualizar o crear

Actualiza cuando corresponda:

```text
docs/technical/architecture/evacengine_indoor_data_model_architecture.md
schemas/indoor/scenario_model.schema.json
```

Crea documentación práctica:

```text
docs/technical/verification/evacengine_refactor_verification.md
docs/technical/architecture/evacengine_implementation_notes.md
docs/technical/research/evacuation_routing_research_backlog.md
```

El backlog de investigación debe conservar la línea futura del TFG: routing dinámico de evacuación sobre grafos, congestión observada y prevista, rutas alternativas, centralidad, robustez/agilidad y fusión CEP multisensor. No inventes referencias. Si tienes acceso a búsqueda, registra solo fuentes verificables y preferentemente primarias; si no, documenta preguntas, términos de búsqueda y criterios de comparación. Esta investigación no debe bloquear la simulación operativa de la presente reforma.

`evacengine_implementation_notes.md` debe contener:

- estructura final;
- decisiones tomadas;
- versiones/dependencias;
- qué está operativo;
- qué está preparado pero no implementado;
- límites conocidos;
- mapa de mantenimiento;
- comandos de ejecución.

No dupliques innecesariamente el documento canónico. Enlaza secciones.

---

## 33. Qué debe quedar operativo ahora

Obligatorio:

- indoor + scenario loaders;
- schema de escenario ampliado;
- una y varias plantas;
- MultiDiGraph;
- recursos compartidos;
- Dijkstra/A*;
- distancia/tiempo;
- AnchorSpace targets;
- Route + WaypointPlan;
- física legacy desacoplada;
- `dt`;
- sincronización;
- ContinuousSpace por planta;
- transferencia vertical;
- perfiles/spawns;
- UI por pestañas;
- balizas `[0,1]` suaves;
- fusión básica;
- CLI de balizas;
- hazard básico programado;
- congestión observada básica o, si bloquea seriamente, contrato completo y modo desactivado documentado;
- outputs/auditoría;
- reproducibilidad;
- tests y guía manual;
- fallback legacy explícito.

---

## 34. Qué debe quedar preparado, pero no necesitas completar ahora

- CEP raw CO2/humo/temperatura;
- propagación física avanzada;
- rescatistas operativos completos;
- asistencia Rolling completa;
- transporte de heridos;
- ruptura de muros;
- ventanas como operación de rescate completa;
- control realista de ascensores;
- congestión prevista;
- robustez y centralidad avanzadas;
- k-shortest/disjoint routes operativos;
- optimización global multiagente;
- backend web;
- PostGIS runtime;
- 3D continuo estricto.

Preparado significa que existen contratos y puntos de extensión razonables, no clases vacías por todas partes ni flags sin semántica.

---

## 35. Criterios de aceptación globales

La tarea no está terminada hasta que:

1. importar EvacEngine no ejecuta simulación ni abre UI;
2. la ruta principal usa indoor + scenario;
3. el legacy solo entra por adaptador explícito;
4. el schema nuevo valida ejemplos reales;
5. una simulación headless de una planta termina y genera resultados;
6. una simulación de tres plantas utiliza un conector y registra el cambio de nivel;
7. el grafo es MultiDiGraph y conserva arcos paralelos/keys;
8. no hay nodos verticales fantasma;
9. Rolling no usa escaleras sin asistencia;
10. Dijkstra y A* funcionan;
11. distancia y tiempo son seleccionables;
12. Route y WaypointPlan están separados;
13. los agentes no atraviesan NonNavigableSpace/ObjectSpace;
14. la actualización es síncrona;
15. la misma semilla reproduce población, balizas y resultado;
16. las balizas tienen curvas suaves y observaciones individuales;
17. la fusión es configurable y auditable;
18. los pesos no se acumulan;
19. la UI permite editar escenario y ejecutar/inspeccionar la simulación;
20. la UI no controla el tiempo físico;
21. se producen manifest, eventos, rutas, trayectorias y métricas;
22. existe guía de verificación manual;
23. la suite completa pasa;
24. `git diff --check` pasa;
25. no se ha hecho `git add` ni `git commit`;
26. el `git status --short` final muestra solo cambios de esta tarea sin stage.

---

## 36. Qué no debes hacer

- No entregar solo un diseño.
- No dejar la UI como un mock sin conexión al motor.
- No dejar loaders que devuelvan dicts crudos usados por todo el código.
- No añadir `if profile == "Firefighter"` por todo el agente.
- No usar nombres humanos para semántica.
- No mutar el indoor model.
- No mutar el scenario model durante un run.
- No mezclar resultados dentro del scenario.
- No usar un único `weight` opaco.
- No copiar estado nodal a todas las aristas sin control.
- No reconstruir grafos por cada agente si puede usarse una vista compartida.
- No crear un `Graph` simple que colapse puertas paralelas.
- No usar una UI que importe el core y acceda a privados.
- No poner la lógica de simulación dentro de callbacks Matplotlib.
- No añadir dependencias grandes sin permiso.
- No tocar SpatialEngine para resolver cuestiones que pertenecen a EvacEngine.
- No reexportar indoor models para ocultar problemas de lectura.
- No hacer commit ni stage.

---

## 37. Respuesta final obligatoria de Codex

Al finalizar, responde con este índice:

```text
# Resultado de la reforma de EvacEngine

## 1. Resumen ejecutivo
## 2. Arquitectura implementada
## 3. Archivos creados
## 4. Archivos modificados
## 5. Scenario schema final
## 6. Topología y routing
## 7. Física y sincronización
## 8. Multinivel
## 9. Balizas y hazards
## 10. UI
## 11. Resultados y auditoría
## 12. Compatibilidad legacy
## 13. Dependencias
## 14. Tests ejecutados
## 15. Verificación manual
## 16. Limitaciones reales
## 17. Próximos pasos
## 18. git diff --stat
## 19. git status --short
```

En tests incluye el comando exacto, número de tests, resultado y cualquier skip.

No afirmes que algo está terminado si solo existe como interfaz. Diferencia claramente:

```text
operativo
parcial
preparado arquitectónicamente
no implementado
```

Repite expresamente:

- no se ejecutó `git add`;
- no se creó commit;
- no se modificó SpatialEngine ni el indoor schema salvo permiso explícito del usuario;
- los cambios están disponibles para revisión sin stage.

