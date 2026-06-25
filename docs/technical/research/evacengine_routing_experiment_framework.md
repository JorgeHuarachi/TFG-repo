# EvacEngine Routing Experiment Framework

Este documento define el alcance metodologico y operativo del comparador de recomendacion de rutas de EvacEngine. El objetivo no es "probar algoritmos genericos", sino comparar politicas de evacuacion sobre el mismo escenario, con las mismas condiciones dinamicas y metricas reproducibles.

## Objetivo

Evaluar como cambia una evacuacion indoor cuando la recomendacion de ruta prioriza:

- tiempo minimo como base fisica de las aristas;
- riesgo dinamico procedente de hazards y balizas;
- robustez ante fallo de conexiones;
- agilidad o capacidad de reencaminamiento desde nodos intermedios;
- congestion observada durante la simulacion.

La unidad experimental es:

```text
indoor_model + scenario_model + preset_de_routing -> resultados comparables
```

El comando `compare-routing` ejecuta varios presets sobre el mismo escenario y escribe:

- `comparison_summary.json`: resumen estructurado;
- `comparison_metrics.csv`: una fila por preset;
- `comparison_routes.csv`: rutas planificadas y metricas asociadas;
- `comparison_plot.png`: grafica compacta si `matplotlib` esta disponible.

## Separacion Conceptual

El framework separa cinco capas:

| Capa | Pregunta | Implementacion |
|---|---|---|
| Grafo base | Que espacios y conexiones existen? | `EvacTopology` |
| Estado dinamico | Que riesgo, bloqueo o congestion hay ahora? | `HazardScheduler`, `BeaconSimulator` |
| Funcion de coste | Cuanto cuesta atravesar una arista? | `WeightSnapshotCompiler` |
| Algoritmo | Como se buscan rutas candidatas? | Dijkstra, A*, Yen k-rutas |
| Politica | Que candidata se recomienda? | menor coste, robustez, agilidad, combinacion |

Esta separacion evita mezclar un algoritmo de busqueda con una politica de recomendacion. Por ejemplo, Yen genera candidatas; la politica puede elegir la mas barata, la mas robusta o la mas agil.

## Funcion De Coste

Sea una arista dirigida \(e=(u,v)\). El coste base de EvacEngine es siempre tiempo de recorrido estimado, medido en segundos. Esto es importante porque una escalera, una rampa o un ascensor pueden tener una proyeccion 2D similar a un tramo llano, pero no tienen el mismo tiempo de cruce.

```text
t(e) = lengthM(e) / (v_p * phi_c)
```

Donde `v_p` es la velocidad base del perfil de movilidad y `phi_c` es el factor de velocidad del conector: por defecto `1.0` en espacios horizontales, `0.55` en escaleras, `0.7` en rampas y `0.5` en ascensores. Si el escenario define `stairSpeedFactor`, `rampSpeedFactor` o `elevatorSpeedFactor`, esos valores se usan en la simulacion.

El riesgo se mantiene normalizado:

```text
r_h(e), r_b(e) in [0, 1]
```

donde:

- `r_h(e)` es riesgo de hazard;
- `r_b(e)` es riesgo de beacon;
- `0` significa sin riesgo;
- `1` significa riesgo maximo en la escala del experimento.

La forma canonica que conviene explicar en el TFG es:

```text
C(e) = alpha * t(e) + beta * r(e)
```

Cuando hay varias fuentes de riesgo, EvacEngine expande ese termino como una suma ponderada: `beta * r(e)` puede materializarse como `beta_h * r_h(e) + beta_b * r_b(e)`. Asi queda claro que el algoritmo sigue usando pesos escalares no negativos, pero el origen de esos pesos sigue siendo auditable. Los modelos `multiplicative_beta` y `linear_time_risk` tambien parten de `t(e)`; no usan distancia como base fisica.

### Origen Del Riesgo

El riesgo de una arista puede venir de:

- `edge_risk[resourceRef]`: riesgo propio de la conexion, por ejemplo puerta/boundary afectada;
- `cell_risk[source]`: riesgo del espacio de origen;
- `cell_risk[target]`: riesgo del espacio destino;
- una combinacion de ambos extremos.

El parametro `riskEndpointPolicy` define la regla cuando no se usa, o no existe, riesgo propio de arista:

| Valor | Formula |
|---|---|
| `target` | \(r(e)=r(v)\) |
| `source` | \(r(e)=r(u)\) |
| `mean` | \(r(e)=0.5(r(u)+r(v))\) |
| `min` | \(r(e)=min(r(u),r(v))\) |
| `max` | \(r(e)=max(r(u),r(v))\) |

Por defecto `riskEdgePrecedence=true`, asi que un riesgo propio de conexion tiene prioridad sobre la regla por extremos.

### Modelos De Coste

EvacEngine mantiene el modelo historico y anade dos modelos experimentales.

#### `legacy_additive`

Modelo anterior del motor:

```text
C(e) = b(e) + b(e) * 20 * r_h(e) + b(e) * 5 * r_b(e) + congestion(e)
```

Es operativo y agresivo: los hazards pesan mucho mas que las balizas. Se conserva por compatibilidad.

#### `multiplicative_beta`

Modelo proximo a `animate_dynamic_route.py`:

```text
C(e) = b(e) * (alpha + beta_h * r_h(e) + beta_b * r_b(e)) + congestion(e)
```

Con `alpha=1`, `beta_h=1`, `beta_b=1`, si una arista tiene riesgo `0.4`, su coste aumenta de forma proporcional. Conserva las unidades de `b(e)`.

#### `linear_time_risk`

Modelo explicito tipo:

```text
C(e) = alpha * b(e) + U_r * (beta_h * r_h(e) + beta_b * r_b(e)) + congestion(e)
```

`U_r = riskUnitCost` convierte riesgo adimensional a la misma unidad que `t(e)`. Como `t(e)` esta en segundos, `riskUnitCost` tambien se interpreta como segundos de penalizacion maxima por unidad de riesgo.

## Simbolos Y Parametros

| Simbolo / campo | Significado | Unidad / rango |
|---|---|---|
| \(|V|\) | numero de nodos del grafo | nodos |
| \(|E|\) | numero de arcos dirigidos | arcos |
| \(e=(u,v)\) | arista dirigida de origen a destino | - |
| \(b(e)\) | coste base de arista | metros o segundos |
| \(t(e)\) | tiempo base de arista | segundos |
| \(r(e)\) | riesgo normalizado de arista | `[0,1]` |
| \(\alpha\) / `riskAlpha` | peso del coste base | adimensional |
| \(\beta_h\) / `hazardBeta` | peso de hazard | adimensional en multiplicativo; unidad de `b(e)` en lineal |
| \(\beta_b\) / `beaconBeta` | peso de beacon | adimensional en multiplicativo; unidad de `b(e)` en lineal |
| \(\tau\) / `beaconBlockThreshold` | umbral de bloqueo por riesgo de beacon | `[0,1]` |
| \(k\) / `kShortestPaths` | numero de rutas candidatas | entero |
| \(R(\pi)\) | robustez de ruta | `[0,1]` |
| \(CE(v)\) | centralidad de evacuacion de nodo | conteo normalizable |
| \(\Delta(\pi)\) | agilidad de ruta | media o producto de centralidades |
| `planningMs` | latencia de recomendacion | ms |
| `snapshotCompileMs` | latencia de compilacion del grafo ponderado | ms |
| `runtimeMs` | tiempo total de simulacion por preset | ms |

## Campos De Configuracion

Estos campos viven en `scenario.routing` o dentro de cada `experiments.routingPresets[*].routing`.

| Campo | Uso |
|---|---|
| `algorithm` | algoritmo de busqueda/recomendacion: `dijkstra`, `astar`, `floyd_warshall`, `yen_ksp` o `robust_agility` |
| `costPolicy` | define explicitamente la base temporal `minimum_travel_time` |
| `riskCostModel` | formula de coste: `legacy_additive`, `multiplicative_beta` o `linear_time_risk` |
| `riskEndpointPolicy` | como convertir riesgo de espacios en riesgo de arista: `target`, `source`, `mean`, `min`, `max` |
| `riskEdgePrecedence` | si `true`, un riesgo propio de conexion tiene prioridad sobre el riesgo de origen/destino |
| `riskAggregation` | modo informativo de fusion de riesgo cuando se necesita un unico `combinedRisk`: `sum`, `max`, `mean` |
| `riskAlpha` | peso del coste base en los modelos experimentales |
| `hazardBeta` | peso del riesgo procedente de hazards |
| `beaconBeta` | peso del riesgo procedente de balizas |
| `riskUnitCost` | unidad de conversion del riesgo en `linear_time_risk` |
| `useHazardRisk` | activa o desactiva la influencia de hazards |
| `useBeaconRisk` | activa o desactiva la influencia de balizas |
| `useCongestion` | activa o desactiva la penalizacion por ocupacion observada |
| `beaconBlockThreshold` | umbral a partir del cual una celda afectada por baliza se bloquea para routing |
| `routeRecommendation.routeSelection` | politica de seleccion: `lowest_cost`, `highest_robustness`, `highest_agility` o `robust_agility` |
| `routeRecommendation.kShortestPaths` | numero maximo de candidatas que genera Yen |
| `routeRecommendation.candidateCostTolerance` | margen permitido frente al coste de la mejor candidata |
| `routeRecommendation.robustnessTolerance` | margen usado al evaluar alternativas ante fallo de arista |
| `routeRecommendation.centralityTolerance` | margen usado al contar rutas eficientes para centralidad de evacuacion |
| `routeRecommendation.centralityMaxPaths` | limite de rutas consideradas para centralidad |
| `routeRecommendation.centralityMaxOverlap` | solape maximo aceptado entre rutas de centralidad |
| `routeRecommendation.costWeight` | peso del coste en la politica combinada |
| `routeRecommendation.robustnessWeight` | peso de robustez en la politica combinada |
| `routeRecommendation.agilityWeight` | peso de agilidad en la politica combinada |
| `routeRecommendation.agilityAggregation` | agregacion de agilidad de nodos intermedios: `mean` o `geometric` |

## Cuando Se Recalcula La Ruta

La simulacion mantiene para cada agente una ruta topologica formada por ids de `CellSpace`. En cada tick se evalua si hace falta calcularla de nuevo:

```text
recalcular = route is None
          or remaining_route intersects blocked_cells
          or step % replanIntervalSteps == 0
```

Con la configuracion por defecto:

- `replanPolicy = on_blocked_or_interval`;
- `replanIntervalSteps = 10`;
- `noRouteRetryIntervalSteps = 10` si no se define otro valor.

Por tanto, cada agente activo planifica al inicio y vuelve a planificar cada 10 pasos, ademas de hacerlo inmediatamente si una celda restante de su ruta queda bloqueada por hazards o balizas. Los agentes en `no_route` reintentan segun `noRouteRetryIntervalSteps`.

Las metricas de salida incluyen:

| Campo | Lectura |
|---|---|
| `routePlans` | numero de eventos `route_planned`; mide recalculos de agentes activos |
| `routeRecoveries` | numero de eventos `agent_route_recovered`; mide agentes que salieron de `no_route` |
| `noRouteEvents` | numero de veces que un agente no encontro ruta |

En comparaciones de presets, la tabla del workbench muestra `plans` para comparar cuantas planificaciones ha provocado cada politica.

### Origen Real De La Ruta

Actualmente el recomendador recibe como origen `agent.current_cell`. Es decir, la busqueda en el grafo empieza en la celda topologica donde esta el agente, no en su coordenada continua exacta.

La coordenada exacta si se usa en la capa de movimiento: waypoints locales, entrada al transfer, centrado en puertas/rampas/escaleras, repulsion, vision y restricciones geometricas. Esto significa que:

- el algoritmo decide la secuencia de celdas desde la celda actual;
- la fisica decide como moverse desde la posicion XY actual hasta la siguiente celda;
- la primera arista todavia no se pondera por "distancia real desde el punto del agente hasta el transfer concreto".

La mejora pendiente para un routing mas fino es hacer el primer salto position-aware:

```text
coste_total(vecino) =
    coste_local(agent.xy -> entrada/centro del transfer vecino)
  + coste_grafo(vecino -> salida)
```

Floyd-Warshall puede ayudar en esa arquitectura como tabla rapida de sufijos `vecino/transfer -> salida`, pero hace falta anadir una capa local que evalue los vecinos desde la posicion continua del agente.

## Algoritmos Y Politicas

### Dijkstra

Baseline para pesos no negativos. Sirve para medir la ruta optima bajo la funcion de coste definida.

### A*

Debe devolver la misma ruta optima que Dijkstra si la heuristica es admisible. En EvacEngine la heuristica es tiempo euclideo optimista: distancia entre puntos representativos dividida por la velocidad base del perfil. Se compara contra Dijkstra para medir si reduce latencia sin cambiar el resultado.

### Floyd-Warshall

Calcula distancias minimas entre todos los pares del snapshot ponderado actual. Para una unica consulta suele ser mas caro que Dijkstra/A*, pero es metodologicamente util porque:

- permite comparar un algoritmo all-pairs contra algoritmos single-source/single-target;
- da una referencia estable cuando se quieren consultar muchos origenes y destinos sobre el mismo snapshot;
- encaja con un futuro routing por etapas, donde se precalculan sufijos desde transfers hacia salidas y la primera decision depende de la posicion continua del agente.

En la implementacion actual se ejecuta sobre el snapshot de cada recalculo de ruta. Por tanto no es el algoritmo recomendado por defecto para escenarios dinamicos grandes; es una opcion de estudio y verificacion.

### Yen k-rutas

Genera varias rutas simples candidatas. Es necesario cuando la pregunta no es solo "cual es la mas barata", sino "cual es aceptablemente barata y ademas robusta/agil".

### Robustez

Para una ruta \(\pi\), se elimina cada arista de la ruta y se comprueba si queda una alternativa con coste:

```text
C_alt <= (1 + robustnessTolerance) * C_0
```

El indice actual es la proporcion de aristas que toleran fallo.

### Centralidad De Evacuacion Y Agilidad

La centralidad de evacuacion aproxima cuantas rutas eficientes y suficientemente disimiles conectan un nodo con alguna salida. La agilidad de una ruta resume las centralidades de sus nodos intermedios.

```text
agility_mean(pi) = mean(CE(v) para v intermedio en pi)
```

La agregacion geometrica tambien esta disponible para castigar rutas que atraviesan un nodo intermedio sin alternativas.

## Presets Integrados

| Preset | Coste | Algoritmo | Politica |
|---|---|---|---|
| `dijkstra_time` | tiempo puro | Dijkstra | menor coste |
| `astar_time` | tiempo puro | A* | menor coste |
| `floyd_warshall_time` | tiempo puro | Floyd-Warshall | menor coste all-pairs |
| `astar_risk_multiplicative` | tiempo x riesgo | A* | menor coste |
| `yen_risk_lowest` | tiempo x riesgo | Yen | menor coste |
| `yen_highest_robustness` | tiempo x riesgo | Yen | mayor robustez |
| `yen_highest_agility` | tiempo x riesgo | Yen | mayor agilidad |
| `robust_agility` | tiempo x riesgo | Yen/robust_agility | score combinado |
| `astar_risk_congestion` | tiempo x riesgo + ocupacion | A* | menor coste dinamico |

Los escenarios pueden declarar presets propios en:

```json
{
  "experiments": {
    "routingPresets": [
      {
        "presetId": "mi_preset",
        "label": "Mi preset",
        "routing": {
          "algorithm": "yen_ksp",
          "riskCostModel": "multiplicative_beta",
          "riskEndpointPolicy": "max",
          "hazardBeta": 1.0,
          "beaconBeta": 1.0,
          "routeRecommendation": {
            "routeSelection": "highest_robustness",
            "kShortestPaths": 8
          }
        }
      }
    ]
  }
}
```

## Comandos

Listar presets integrados:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine compare-routing --list-presets
```

Si se anade `--scenario`, el listado tambien incluye presets propios definidos dentro de `experiments.routingPresets`.

Comparar tres politicas:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine compare-routing --scenario examples\indoor_data_model\scenario_single_floor.json --presets dijkstra_time,astar_risk_multiplicative,yen_highest_robustness --output-dir outputs\routing_compare_single
```

Comparar Dijkstra, A* y Floyd-Warshall con el mismo coste temporal:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine compare-routing --scenario examples\indoor_data_model\scenario_single_floor.json --presets dijkstra_time,astar_time,floyd_warshall_time --output-dir outputs\routing_compare_shortest_path
```

Comparacion rapida sin salidas completas por preset:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine compare-routing --scenario examples\indoor_data_model\scenario_single_floor.json --presets dijkstra_time,astar_time --max-steps 40 --first-group-count 2 --output-dir outputs\routing_compare_smoke --no-run-outputs --skip-plot
```

## Verificacion Visual En Workbench

El workbench expone una seccion `Routing Experiments` para probar estos mismos parametros sin salir de la UI. La seccion esta colocada despues de `Beacons` de forma deliberada: primero se define el escenario que se va a comparar (agentes, destino, balizas y curva temporal de seguridad) y despues se decide que politica de routing se quiere evaluar.

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine workbench --scenario examples\indoor_data_model\scenario_single_floor.json --host 127.0.0.1 --port 8765
```

Flujo recomendado:

1. Abrir el workbench y revisar agentes/balizas como en una simulacion normal.
2. Elegir un `Preset`.
3. Pulsar `Apply preset` para copiar sus parametros a los controles editables.
4. Ajustar, si hace falta, `Safety-cost model`, `alpha`, `hazard beta`, `beacon beta`, `routeSelection`, `k` o tolerancias. En el JSON esos campos siguen llamandose `riskCostModel`, `hazardBeta`, `beaconBeta`, etc.
5. Pulsar `Run preset visually` para ver ese caso en el canvas.
6. Marcar varios presets en la lista y pulsar `Compare selected` para obtener una tabla con evacuados, activos, no-route, planes/recalculos, coste medio, latencia de planificacion, robustez y agilidad.

La comparacion visual usa el estado actual del workbench: agentes manuales, grupo automatico, destino, balizas, curva temporal y eventos programados. Asi se puede comprobar el efecto de cambiar la politica de routing manteniendo constante el escenario.

En la UI se usa la palabra `safety` porque es mas intuitiva: `safety = 1` significa espacio usable y `safety = 0` significa inseguro. Internamente, para mantener compatibilidad con el schema y los resultados existentes, EvacEngine guarda la perdida de seguridad como `riskPenalty = 1 - safety`.

Lectura recomendada de los experimentos, de menor a mayor complejidad:

1. `dijkstra_time`: baseline de evacuacion por menor tiempo.
2. `astar_time`: mismo objetivo de tiempo, pero con heuristica para comparar latencia frente a Dijkstra.
3. `floyd_warshall_time`: mismo coste de tiempo, calculo all-pairs para contrastar rutas y coste computacional.
4. `astar_risk_multiplicative`: tiempo mas perdida de seguridad por balizas/hazards.
5. `yen_risk_lowest`: varias rutas candidatas, seleccionando la de menor coste safety-tiempo.
6. `yen_highest_robustness`: varias rutas candidatas, premiando alternativas si falla una arista.
7. `yen_highest_agility`: varias rutas candidatas, premiando espacios con mayor agilidad/CE.
8. `robust_agility`: seleccion combinada de coste, robustez y agilidad.
9. `astar_risk_congestion`: incorpora congestion como penalizacion dinamica adicional.

Este orden permite reproducir el estilo de `animate_dynamic_route.py`: partir de una mascara de movilidad y coste temporal simple, despues activar seguridad, despues rutas candidatas y finalmente criterios de robustez/agilidad/congestion. La diferencia es que ahora se conserva la arquitectura nueva de scenario + indoor model + simulador fisico.

### Estructura De La Seccion

La seccion visible esta pensada para uso normal:

| Control | Uso |
|---|---|
| `Preset strategy` | selecciona una politica completa ya definida |
| `Apply preset` | copia el preset a los controles editables del workbench |
| `Run visually` | aplica el preset seleccionado y ejecuta una simulacion visible en el canvas |
| `Compare checked` | ejecuta todos los presets marcados con los mismos agentes, balizas, destino y eventos |
| `Presets to compare` | lista de estrategias que entran en la comparacion |
| panel de resultados | muestra una tabla compacta: preset, algoritmo, evacuados, activos, no-route, planes/recalculos, coste medio, latencia, robustez y agilidad |

La parte avanzada esta plegada en `Advanced safety/cost parameters` para no saturar la UI. Ahi se ajustan los parametros de calibracion:

| Grupo | Controles | Significado |
|---|---|---|
| Modelo safety/cost | `Safety-cost model`, `Safety source`, `Safety-loss aggregation` | como se transforma seguridad de espacios/conexiones en coste de arista |
| Activadores | `Beacon safety affects routes`, `Hazard safety affects routes`, `Congestion affects routes` | que senales dinamicas entran en el peso |
| Pesos | `alpha`, `hazard beta`, `beacon beta`, `safety unit cost` | intensidad del tiempo base y de la perdida de seguridad |
| Candidatas | `Route selection`, `k routes`, `cost tolerance` | como se generan y filtran rutas alternativas |
| Robustez | `robust tolerance`, `robust weight` | cuanto se premian rutas con alternativas ante fallo |
| Agilidad | `CE tolerance`, `CE paths`, `CE overlap`, `Agility aggregation`, `agility weight` | como se valora pasar por espacios con mas alternativas de evacuacion |
| Balance final | `cost weight`, `robust weight`, `agility weight` | ponderacion de la politica combinada `robust_agility` |

El workbench muestra un bloque compacto de parametros activos/ignorados. Esto es deliberado: no todos los campos participan siempre. Por ejemplo, en `dijkstra_time`, `k routes`, tolerancias, robustez y CE/agility no se usan porque se calcula una unica ruta de menor tiempo. En `yen_ksp` o `robust_agility`, esos campos si participan porque se generan candidatas y despues se aplica una politica de seleccion.

`CE/agility` se interpreta aqui como una medida operacional de centralidad de evacuacion: no es solo una centralidad grafica clasica, sino un indicador de cuantas alternativas eficientes y suficientemente distintas quedan al pasar por una zona. `agility` resume esa informacion a nivel de ruta; `robustness` mide que ocurre si fallan conexiones. La comparacion final interesante no es escoger una y descartar la otra, sino estudiar coste/latencia/agilidad/robustez por separado y luego justificar una combinacion.

### Relacion Safety / Risk Interno

La interfaz evita mostrar `risk` como concepto principal porque para configurar el experimento es mas claro pensar en seguridad:

```text
safety_loss = 1 - safety
riskPenalty = safety_loss
```

Por eso:

- `Safety loss = 0` significa que la baliza no penaliza la zona;
- `Safety loss = 1` significa que la zona se considera completamente insegura;
- `Block at loss = 0.85` bloquea una zona cuando su seguridad cae por debajo de `0.15`;
- los nombres JSON siguen siendo `riskPenalty`, `riskCostModel`, `riskEndpointPolicy`, etc., para no romper compatibilidad con schema, outputs y tests.

### Lectura De Resultados

`Compare checked` no cambia el escenario base en disco. Ejecuta replicas internas con los presets seleccionados y devuelve:

| Columna | Interpretacion |
|---|---|
| `preset` | estrategia evaluada |
| `alg` | algoritmo activo en esa estrategia |
| `evacuated` | agentes que alcanzaron salida dentro de `maxSteps` |
| `active` | agentes que siguen evacuando al terminar |
| `noRoute` | agentes sin ruta disponible |
| `routeCost` | coste medio de rutas planificadas |
| `planMs` | latencia media de recomendacion de ruta |
| `robust` | indice medio de robustez cuando aplica |
| `agility` | indice medio de agilidad/centralidad cuando aplica |

Para una verificacion manual justa, se recomienda mantener constante todo lo demas (seed, agentes, balizas, curvas y destino) y cambiar solo el preset o los parametros avanzados que se quieran estudiar.

## Hipotesis Experimentales

- Dijkstra y A* deben producir costes equivalentes bajo la misma funcion de coste; A* deberia reducir latencia cuando la heuristica geometrica ayuda.
- El coste bicriterio debe reducir exposicion a riesgo, aceptando rutas mas largas.
- Yen no es una politica por si mismo: aporta candidatas. La diferencia aparece al seleccionar por coste, robustez o agilidad.
- La politica de robustez deberia elegir rutas menos fragiles, aunque su coste base sea mayor.
- La politica de agilidad deberia favorecer nodos intermedios con mas alternativas aceptables hacia salidas.
- La congestion dinamica deberia reducir apelotonamientos cuando hay rutas alternativas, pero puede aumentar tiempo si fuerza desvios.

## Referencias Minimas Para El TFG

- IndoorGML 1.1, OGC: https://docs.ogc.org/is/19-011r4/19-011r4.html
- Dijkstra, E. W. "A note on two problems in connexion with graphs", 1959: https://doi.org/10.1007/BF01386390
- Hart, Nilsson, Raphael. "A Formal Basis for the Heuristic Determination of Minimum Cost Paths", 1968: https://doi.org/10.1109/TSSC.1968.300136
- Yen, J. Y. "Finding the k Shortest Loopless Paths in a Network", 1971: https://doi.org/10.1287/mnsc.17.11.712
- Suurballe, J. W. "Disjoint paths in a network", 1974: https://doi.org/10.1002/net.3230040204
- Suurballe, Tarjan. "A quick method for finding shortest pairs of disjoint paths", 1984: https://doi.org/10.1002/net.3230140209
- Lujak, Giordani. "Centrality measures for evacuation: Finding agile evacuation routes", 2018.
- Helbing, Molnar. "Social force model for pedestrian dynamics", 1995: https://doi.org/10.1103/PhysRevE.51.4282
- Apache Flink CEP documentation: https://nightlies.apache.org/flink/flink-docs-stable/docs/libs/cep/
- Kafka Streams documentation: https://kafka.apache.org/documentation/streams/
- Esper documentation: https://www.espertech.com/esper/
- Apache Beam programming guide: https://beam.apache.org/documentation/programming-guide/

## Estado Actual

Implementado:

- modelos de coste `legacy_additive`, `multiplicative_beta` y `linear_time_risk`;
- seleccion del origen del riesgo con `riskEndpointPolicy`;
- medicion de `snapshotCompileMs` y `planningMs`;
- presets integrados de comparacion;
- comando `compare-routing`;
- CSV/JSON/PNG de comparacion;
- validacion JSON Schema para presets declarados en escenario.

Pendiente para investigacion posterior:

- calibracion empirica de \(\alpha\), \(\beta_h\), \(\beta_b\) y \(\tau\);
- rutas disjuntas Suurballe-Tarjan como politica propia;
- time-dependent shortest paths sin discretizar solo por snapshots;
- medicion de overhead de triggers de SpatialEngine/PostGIS por inserciones en lote;
- integracion de CEP real o replay de streams simulados.
