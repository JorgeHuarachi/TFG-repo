# EvacEngine Simulation Physics And Workbench Status

Fecha: 2026-06-23

Este documento resume el estado real de la simulacion EvacEngine tras el flujo de trabajo de reforma. Distingue entre comportamiento implementado, comportamiento aproximado y comportamiento pendiente para no confundir parametros declarados con fisica ya portada.

## Estado Conocido Bueno Actual

Este es el punto funcional que conviene conservar antes de seguir iterando:

- El escenario de una planta se simula y visualiza correctamente en el workbench.
- El escenario multilevel ya mueve agentes entre plantas cuando hay ruta alcanzable.
- El workbench carga rutas escritas o pegadas en `Scenario path` y `Indoor model path`.
- El workbench separa agentes automaticos y agentes manuales en pestanas.
- El workbench permite colocar agentes con clic en el nivel activo desde la pestana `Manual`.
- `Destination mode` evita reducir por error un escenario multisalida a una unica salida.
- `All scenario exits` usa todas las salidas declaradas por el escenario.
- `Selected only` fuerza una salida concreta para pruebas controladas de ascensor, rampa o escalera.
- Las columnas se pintan en negro.
- Las aristas virtuales `VTN_*` no se pintan en el workbench ni en el HTML standalone para no ensuciar la visualizacion.
- Rampas y escaleras se pintan con colores distintos y etiqueta `RAMP` / `STAIR`.
- Las trazas de agentes quedan dibujadas.
- Los agentes ya no desaparecen al cruzar `VTN_*` en los casos verificados.
- La salida de rampa hacia virtual boundary ya no se queda bloqueada por repulsion de pared en la prueba de regresion.
- La salida desde `VTN_*` apunta a una entrada cercana de la celda real, no al centro de la celda, para reducir acelerones visuales.
- Las celdas puente `EP_VC` se tratan como conectores de capacidad limitada, no como salas de acumulacion.
- El spawn aleatorio intenta respetar separacion minima entre cuerpos.
- La repulsion social incluye frenado por espacio personal y empuje lateral simple en cruces cercanos.
- Los agentes en `no_route` por una baliza o evento dinamico ya pueden recuperar ruta cuando el paso vuelve a estar disponible.
- Rampas y escaleras tienen factor de velocidad y capacidad configurable desde `physics`.
- El workbench permite ajustar la velocidad de reproduccion visual con `Playback ms/frame`; esto no cambia la velocidad fisica de la simulacion.

Verificacion ejecutada en este estado:

- `compileall`: OK.
- `tests.test_evac_engine_refactor`: `20/20 OK`.
- `scenario_single_floor.json` con `12` agentes y factores de rampa/escalera: `12/12` evacuados, `noRoute: 0`, `largeJumps: 0`, `bodyOverlapSamples: 118` en QA rapido, `timeS: 80.0`.
- `scenario_multilevel.json` con factores de rampa/escalera: `6/6` evacuados, `noRoute: 0`, `largeJumps: 0`, `timeS: 41.5`.
- Agente manual en `LEVEL_02` con `All scenario exits`: evacua en `CS_L02_EXIT_001`.
- Agente manual en `CS_L01_ROOM_010` forzado a `CS_L00_EXIT_001`: usa cambio de planta por ascensor y evacua.
- Agente manual en `CS_L01_ROOM_013` forzado a `CS_L00_EXIT_001`: usa rampa y evacua.
- Agente manual desde `CS_L01_EP_VC_002_LEVEL_01` forzado a `CS_L00_EXIT_001`: usa escalera y evacua.

## Organizacion De Archivos Nuevos

Paquete principal:

- `src/evac_engine/__init__.py`: version y entrada de paquete.
- `src/evac_engine/__main__.py`: permite `python -m src.evac_engine`.
- `src/evac_engine/application.py`: frontera de servicio para CLI/UI/tests.
- `src/evac_engine/cli.py`: comandos de consola.
- `src/evac_engine/domain.py`: dataclasses y tipos compartidos.
- `src/evac_engine/loaders.py`: carga, validacion y normalizacion de `indoor_model` + `scenario`.
- `src/evac_engine/topology.py`: grafo runtime canonico basado en `CellSpace.id`.
- `src/evac_engine/routing.py`: rutas Dijkstra/A*, costes, perfiles y accesibilidad.
- `src/evac_engine/overlays.py`: beacons, hazards y eventos programados.
- `src/evac_engine/simulation.py`: simulacion, fisicas, agentes, transferencias, salidas y outputs.
- `src/evac_engine/visualization.py`: payload visual, HTML, GIF y metricas QA.
- `src/evac_engine/web_app.py`: workbench web interactivo.
- `src/evac_engine/ui/desktop_app.py`: shell desktop Tk import-safe.

Escenarios nuevos:

- `examples/indoor_data_model/scenario_single_floor.json`: escenario funcional de una planta.
- `examples/indoor_data_model/scenario_multilevel.json`: escenario funcional de tres plantas.
- `examples/indoor_data_model/scenario_beacons_demo.json`: demo de beacons y eventos.

Documentacion nueva o relevante:

- `docs/technical/architecture/evacengine_implementation_notes.md`: mapa tecnico del paquete.
- `docs/technical/architecture/evacengine_indoor_data_model_architecture.md`: arquitectura objetivo EvacEngine + Indoor Data Model.
- `docs/technical/implementation/codex_evacengine_major_refactor_prompt.md`: prompt operativo de la reforma.
- `docs/technical/research/evacuation_routing_research_backlog.md`: backlog tecnico de investigacion/routing.
- `docs/technical/verification/evacengine_refactor_verification.md`: verificacion general de la reforma.
- `docs/technical/verification/evacengine_simulation_physics_and_workbench_status.md`: este estado de fisica/workbench.

Tests:

- `tests/test_evac_engine_refactor.py`: regresion del loader, routing, simulacion, workbench, beacons, multilevel y casos verticales.

## Regla Sobre Indoor Models Exportados

Los `indoor_model.json` exportados por SpatialEngine son la verdad espacial y no deben editarse para corregir comportamiento de simulacion. En esta iteracion no se modificaron:

- `examples/indoor_data_model/una_sola_planta_indoor_model.json`
- `examples/indoor_data_model/tres_plantas_indoor_model.json`

Las correcciones de comportamiento viven en:

- `src/evac_engine/simulation.py`: interpretacion runtime, fisica, capacidad, colas y movimiento.
- `src/evac_engine/web_app.py`: interfaz de ejecucion y configuracion.
- `examples/indoor_data_model/scenario_*.json`: parametros de simulacion, poblacion, perfiles y destino.
- `schemas/indoor/scenario_model.schema.json`: contrato del `scenario_model`, no del `indoor_model`.

Esto importa porque los siguientes modelos generados por SpatialEngine deben poder cargarse sin incorporar manualmente estas correcciones dentro del modelo espacial. Si una futura correccion requiere nueva semantica espacial, primero hay que decidir si pertenece al exportador SpatialEngine o al `scenario_model`; no debe parchearse a mano un `indoor_model` generado.

## Alcance Implementado

- Carga de `indoor_model.json` y `scenario_model.json` mediante `src/evac_engine/loaders.py`.
- Topologia canonica sobre `CellSpace.id` mediante `src/evac_engine/topology.py`.
- Rutas con Dijkstra/A* mediante `src/evac_engine/routing.py`.
- Filtros de movilidad por perfil:
  - `locomotionTypes`
  - `canUseStairs`
  - `canUseRamps`
  - `canUseElevators`
- Parametros por perfil usados por la simulacion:
  - `baseSpeedMps`
  - `bodyRadiusM`
  - `personalRadiusM`
- Estado cinematico por agente:
  - posicion
  - velocidad
  - celda actual
  - nivel actual
  - ruta actual
- Movimiento con:
  - aceleracion maxima aproximada (`maxAccelerationMps2`)
  - inercia de velocidad (`velocityInertia`, si se define)
  - reduccion de velocidad en giros bruscos
  - limite angular de giro (`maxTurnRateRadS`, valor por defecto en codigo)
  - repulsion social basica
  - frenado por entrada en radio personal
  - empuje lateral simple en encuentros cercanos y frontales
  - repulsion de pared contra geometrias no navegables por nivel
  - bloqueo geometrico para no cruzar fuera de union de espacios navegables
- Spawn aleatorio con separacion minima configurable (`spawnMinSpacingM`).
- Separacion de cuerpos post-paso con margen configurable (`bodySeparationSlackM`).
- Tratamiento especial de puertas/transferencias:
  - objetivo local hacia el umbral compartido entre celda actual y puerta
  - atraccion reforzada hacia transferencia para evitar oscilaciones laterales
  - entrada corta y limitada al interior de puertas cuando el agente ya toca el umbral
  - radio de llegada reducido para puertas
  - capacidad limitada en transferencias para formar cola
  - capacidad configurable para escaleras (`stairCapacity`) y rampas (`rampCapacity`)
  - reduccion de velocidad configurable para escaleras (`stairSpeedFactor`), rampas (`rampSpeedFactor`) y ascensores (`elevatorSpeedFactor`)
  - celdas `EP_VC` tratadas como conectores de capacidad 1
  - cola previa al conector con margen configurable (`doorQueueClearanceM`)
  - limite de correccion por tick para evitar saltos (`doorQueueCorrectionMaxM`)
- Recuperacion de rutas:
  - `noRouteRetryIntervalSteps` controla cada cuantos pasos reintenta planificar un agente que quedo sin ruta.
  - Si existe un evento dinamico pendiente de baliza, la simulacion no termina solo porque todos los agentes esten temporalmente en `no_route`.
  - Cuando una baliza desbloquea una celda, se emite `agent_route_recovered`.
- Tratamiento de `VTN_*`:
  - no se fuerza el salto al centro de celda
  - si el agente llega fisicamente a la celda siguiente, se actualiza el estado
  - si parte de un punto virtual fuera de una geometria real, se proyecta al espacio navegable mas cercano
- Trazas visuales:
  - cada agente deja una linea de recorrido en el visor HTML y workbench.
- QA geometrico:
  - `outsideNavigableSamples`
  - `segmentOutsideNavigable`
  - ambos deben ser `0` para confirmar que no se han atravesado zonas no navegables.
- Modo rapido:
  - `--skip-geometry-qa` omite la comprobacion Shapely completa de trayectorias.
  - El workbench deja `Geometry QA` desactivado por defecto para iterar rapido.

## Mapeo Con El EvacEngine Legacy

El archivo legacy `src/MLSM_EvacEngine.py` aun existe como referencia. Lo que se ha recuperado de ahi no es una copia completa, sino un mapeo parcial:

| Legacy | Motor nuevo | Estado |
|---|---|---|
| `RADIO_FISICO` | `bodyRadiusM` | Implementado |
| `RADIO_PERSONAL` | `personalRadiusM` | Implementado |
| `FUERZA_PARED` | `wallRepulsion` | Parcial |
| `RADIO_VISION_MUROS` | `wallRepulsionDistanceM` opcional | Parcial |
| `velocidad_actual` | `AgentState.velocity` | Implementado |
| freno por giro con `dot_giro` | `_turn_speed_scale()` | Aproximado |
| `frames_transicion` | inercia de velocidad + reduccion por giro | Aproximado, no equivalente |
| `es_transitable()` | `_constrain_step()` con geometria navegable | Implementado de otra forma |
| trazas `traza_x/traza_y` | trayectorias y `drawTraces()` | Implementado |
| enfoque fisico hacia puerta | `_local_waypoint()` hacia umbral compartido + entrada corta | Parcial mejorado |
| puerta uno-a-uno | `_apply_transfer_capacity()` | Parcial |
| linea de vision que permite saltar objetivos | lookahead suavizado sin saltar indice fisico | Parcial |

## Diferencias Importantes Frente Al Legacy

- No esta portada al 100% la logica de `frames_transicion`.
- No esta portada al 100% la logica de cambio de objetivo por linea de vision.
- La repulsion de pared usa geometrias no navegables, pero todavia no reproduce exactamente la fuerza exponencial del legacy.
- La cola en puertas existe por capacidad y ahora prioriza alineacion al umbral, pero todavia puede necesitar ajuste fino para escenarios mas densos.
- Los perfiles existen y afectan ruta, velocidad y radios, pero no hay todavia rasgos conductuales ricos por perfil, como decision psicologica, paciencia o variacion individual avanzada.
- El workbench permite colocar agentes con clic, pero todavia no guarda esos cambios de vuelta al JSON de escenario automaticamente.

## Perfiles Disponibles En El Escenario De Una Planta

`examples/indoor_data_model/scenario_single_floor.json` incluye:

- `MP_WALKING`: adulto caminante base.
- `MP_ELDERLY`: caminante mas lento, cuerpo y radio personal mayores.
- `MP_CHILD`: caminante mas pequeno y rapido.
- `MP_ROLLING_ACCESSIBLE`: movilidad rolling, sin escaleras, con rampas/elevadores.

## Beacons

Estado actual:

- El backend soporta `beaconSystem.beacons`.
- `BeaconSimulator` calcula riesgo por celda y por edge a partir de posicion, radio/influencia y `riskPenalty`.
- El estado de beacons se evalua en cada `step` de simulacion, usando el `timeStepS` activo.
- Una baliza no cambia su `riskPenalty` continuamente por si sola: cambia cuando se aplican `scheduledEvents` de tipo `beacon_update`, `beacon_enable`, `beacon_disable` o `beacon_add`.
- `riskPenalty` es el valor de peligro/riesgo emitido por la baliza; la seguridad visual es `1 - risk`.
- `scheduledEvents` soporta `beacon_update`, `beacon_enable`, `beacon_disable` y `beacon_add`.
- El routing puede usar `useBeaconRisk` para penalizar rutas segun el estado procesado de las balizas.
- La ruta se recalcula cuando no existe ruta, cuando una celda restante queda bloqueada, o cada `replanIntervalSteps`; los agentes en `no_route` reintentan cada `noRouteRetryIntervalSteps`.
- El workbench permite crear/editar beacons desde el panel lateral y colocarlos con clic sobre la planta activa.
- El placement visual acepta geometria navegable y no navegable: puedes marcar `ceiling`, `wall`, `floor` o `free` como superficie de montaje y colocar la baliza sobre salas, paredes, columnas u otros espacios dibujados.
- El workbench dibuja cada baliza sobre el plano, incluyendo su radio de influencia.
- El panel de curva permite editar puntos `timeS, riskPenalty`, arrastrarlos sobre el grafico, previsualizarlos y generar automaticamente `scheduledEvents` de tipo `beacon_update`.
- Los eventos generados desde la curva se etiquetan con `source: "workbench_beacon_curve"` para poder regenerarlos sin borrar otros eventos manuales.
- `useBeaconRisk` activa la penalizacion de rutas por riesgo de balizas.
- `beaconBlockThreshold` convierte una celda en bloqueada para routing si el riesgo fusionado de baliza alcanza ese umbral.
- El workbench marca visualmente las celdas afectadas con numero de seguridad `S`; cuando el riesgo supera `beaconBlockThreshold`, la celda se pinta roja y muestra `BLOCKED`.
- La linea de vision usada para lookahead se corta si atraviesa geometria no navegable de muro/columna.
- La ralentizacion por proximidad entre agentes tiene una memoria corta (`proximitySlowdownMemoryS`) para que el agente recupere velocidad despues de separarse.
- Si un agente esta dentro de una celda bloqueada por beacon, intenta escapar por un vecino navegable con menor riesgo antes de quedar esperando sin ruta.

Pendiente:

- La curva actual edita `riskPenalty`; no hay todavia una segunda vista semantica `safety -> riskPenalty` con transformacion explicita.
- El workbench no persiste automaticamente los beacons al JSON de escenario en disco; los manda al simulador desde el estado de la UI y muestra el JSON resultante en `Beacons` y `Dynamic Events`.
- Falta una UX avanzada para arrastrar beacons ya colocados, editar orientacion 3D real de techo/pared o dibujar zonas direccionales de influencia.
- La huida local desde celdas bloqueadas por beacon es heuristica y vecinal; falta calibrarla con un modelo de exposicion/gradiente continuo y con decisiones de grupo.

## Workbench: Colocar Agentes Visualmente

Comando:

```powershell
cd C:\Users\alumno\TFG-repo
.\.venv\Scripts\python.exe -B -m src.evac_engine workbench --scenario examples\indoor_data_model\scenario_single_floor.json
```

URL:

```text
http://127.0.0.1:8765/?scenario=examples/indoor_data_model/scenario_single_floor.json
```

Uso:

1. Escribe o pega el escenario en `Scenario path`.
2. Deja `Indoor model path` vacio para usar el `indoorModelRef.path` del escenario, o pega ahi un `indoor_model.json` concreto si quieres forzarlo.
3. Selecciona `Level`.
4. Para poblacion automatica, usa la pestana `Automatic`: `Agents`, `Spawn cell`, `Spawn X/Y` y `Group distribution`.
5. Para colocar agentes a mano, usa la pestana `Manual`: elige `Click profile`, deja `Click placement` en `On` y haz clic dentro de una celda navegable.
6. El agente aparece en `Manual Agents` con coordenadas exactas.
7. Repite para crear agentes dispersos por distintas salas/zonas.
8. Deja `Geometry QA` desactivado para iterar rapido.
9. Pulsa `Run simulation`.

Si haces clic en pared o fuera de una celda navegable, el workbench ignora el clic.

Si tus `indoor_model.json` estan en otra carpeta, pega la ruta completa del archivo en `Indoor model path` y pulsa `Reload scenario`.

## Formato De Agentes Manuales

Ejemplo:

```json
[
  {
    "agentId": "MANUAL_001",
    "mobilityProfileRef": "MP_WALKING",
    "initialCellSpaceRef": "CS_L00_ROOM_001",
    "initialPosition": {
      "type": "Point",
      "coordinates": [1.2, 1.1]
    }
  }
]
```

Cuando esta activa la pestana `Manual`, el workbench usa los agentes exactos de `Manual Agents`. Cuando esta activa `Automatic`, ignora `Manual Agents` y usa el grupo automatico configurado.

## Workbench Multilevel

Comando:

```powershell
cd C:\Users\alumno\TFG-repo
.\.venv\Scripts\python.exe -B -m src.evac_engine workbench --scenario examples\indoor_data_model\scenario_multilevel.json --host 127.0.0.1 --port 8765
```

Uso recomendado:

1. Deja `Destination mode` en `All scenario exits` para comprobar que cada agente usa cualquier salida alcanzable del escenario.
2. Selecciona `LEVEL_01` o `LEVEL_02` en el selector de nivel.
3. Entra en la pestana `Manual` y activa `Click placement`.
4. Coloca agentes con clic dentro de celdas navegables.
5. Pulsa `Run simulation`.
6. Cambia de nivel para seguir el movimiento entre plantas.

Pruebas manuales utiles:

- `LEVEL_02` + `All scenario exits`: debe moverse y evacuar por `CS_L02_EXIT_001`.
- `LEVEL_01`, zona `CS_L01_ROOM_010`, `Selected only` hacia `CS_L00_EXIT_001`: debe usar ascensor y bajar a `LEVEL_00`.
- `LEVEL_01`, zona `CS_L01_ROOM_013`, `Selected only` hacia `CS_L00_EXIT_001`: debe usar rampa y bajar a `LEVEL_00`.
- `CS_L01_EP_VC_002_LEVEL_01`, `Selected only` hacia `CS_L00_EXIT_001`: debe usar escalera.

Limitacion actual del modelo multilevel:

- El grafo de `tres_plantas_indoor_model.json` contiene componentes separados. Algunas salas de `LEVEL_01` y `LEVEL_02` no tienen ruta hacia todas las salidas.
- Si fuerzas `Selected only` hacia una salida no alcanzable, el agente queda en `no_route` y no se mueve. Eso no es fallo de animacion: es el resultado de routing.
- La escalera `VC_002` esta verificada desde su endpoint, pero las salas cercanas no siempre estan conectadas a ella por el grafo actual. Esto debe revisarse en el Indoor Data Model / graph views si se quiere uso natural desde mas zonas.

## Verificacion Manual Recomendada

Generar HTML para una planta:

```powershell
cd C:\Users\alumno\TFG-repo
.\.venv\Scripts\python.exe -B -m src.evac_engine run --scenario examples\indoor_data_model\scenario_single_floor.json --max-steps 1200 --time-step 0.25 --first-group-count 12 --skip-geometry-qa --output-dir .tmp\view_single --html .tmp\view_single\simulation.html
```

Abrir:

```text
C:\Users\alumno\TFG-repo\.tmp\view_single\simulation.html
```

Generar HTML multilevel:

```powershell
cd C:\Users\alumno\TFG-repo
.\.venv\Scripts\python.exe -B -m src.evac_engine run --scenario examples\indoor_data_model\scenario_multilevel.json --max-steps 500 --time-step 0.25 --skip-geometry-qa --output-dir .tmp\view_multilevel --html .tmp\view_multilevel\simulation.html
```

Abrir:

```text
C:\Users\alumno\TFG-repo\.tmp\view_multilevel\simulation.html
```

Verificacion completa de geometria:

```powershell
cd C:\Users\alumno\TFG-repo
.\.venv\Scripts\python.exe -B -m src.evac_engine run --scenario examples\indoor_data_model\scenario_single_floor.json --max-steps 1200 --time-step 0.25 --first-group-count 12 --output .tmp\qa_run_transfer_focus_fullqa_1200
```

Campos QA clave:

- `outsideNavigableSamples`: debe ser `0`.
- `segmentOutsideNavigable`: debe ser `0`.
- `largeJumps`: debe ser `0`.
- `bodyOverlapSamples`: cuanto menor, mejor; no es cero garantizado todavia.

Resultado verificado el 2026-06-23:

- `evacuated`: `12/12`
- `stepsExecuted`: `320`
- `timeS`: `80.0`
- `largeJumps`: `0`
- `maxStepDistanceM`: `0.967095`
- `bodyOverlapSamples`: `118`
- `outsideNavigableSamples`: `0`
- `segmentOutsideNavigable`: `0`

## Verificacion Automatizada

```powershell
cd C:\Users\alumno\TFG-repo
.\.venv\Scripts\python.exe -B -m compileall -q src\evac_engine
.\.venv\Scripts\python.exe -B -m unittest tests.test_evac_engine_refactor -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

## Estado Honesto De La Fisica

La simulacion nueva ya evita cruces geometricos por zonas no navegables en la prueba de una planta validada, y ya tiene trazas, perfiles basicos, radios fisicos, radios personales, inercia, frenado por giro, limite angular y alineacion de puerta mejorada.

Tambien se ha verificado movimiento multilevel con ascensor, rampa y escalera en casos controlados. Aun asi, la calidad final depende mucho de que el grafo del Indoor Data Model conecte correctamente salas, endpoints verticales y salidas.

Pero no se debe considerar todavia equivalente al EvacEngine legacy. Lo que falta para recuperar "lo mejor" del comportamiento legacy es:

- steering continuo tipo `frames_transicion` 100% equivalente al legacy;
- repulsion de muro con curva de fuerza calibrada contra el legacy;
- alineacion de puerta validada en escenarios mas densos y multisalida;
- fuerza social calibrada contra el legacy; ya existe ralentizacion longitudinal y empuje lateral basicos, pero no estan calibrados al 100%;
- gestion de atascos con ruido controlado, prioridad de paso y desbloqueo local;
- modelo densidad-flujo especifico para escaleras/rampas en grupos numerosos;
- calibracion empirica de `baseSpeedMps`, `stairSpeedFactor`, `rampSpeedFactor`, capacidades y radios por perfil;
- controles persistentes de autoria para guardar escenarios editados desde el workbench.
