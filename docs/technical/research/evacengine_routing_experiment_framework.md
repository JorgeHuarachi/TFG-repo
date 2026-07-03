# EvacEngine Route Recommendation Policies

Este documento sustituye el enfoque anterior de "comparar algoritmos" por el
enfoque actual del TFG: estudiar politicas de recomendacion de rutas de
evacuacion. Dijkstra, Yen u otros algoritmos quedan como solvers internos. La
contribucion metodologica se centra en como se construyen los pesos, como se
usa la seguridad dinamica y como se incorpora la Centralidad de Evacuacion por
Reencaminamiento (CER).

## Decision Principal

El eje experimental anterior basado en comparar solvers genericos queda
retirado. El eje experimental pasa a ser:

```text
politica de evacuacion = coste temporal + seguridad + CER + reglas de seleccion
```

Los algoritmos siguen existiendo en el codigo, pero no son el objeto principal
de comparacion en el workbench. Su papel es instrumental:

- una politica de minimo coste puede resolverse con Dijkstra sobre pesos no
  negativos;
- una politica de candidatas puede usar Yen para generar varias rutas simples y
  despues aplicar un criterio de seleccion;
- Floyd-Warshall queda como herramienta diagnostica/all-pairs, no como flujo
  visual principal.

## Grafo Operativo

La recomendacion se calcula sobre el backbone:

```text
multilevel_transfer_to_transfer
```

No se usa `space_connectivity` como grafo principal de evacuacion. Las salas o
GeneralSpaces se incorporan solo como endpoints temporales cuando un agente
esta dentro de una sala y la ruta debe empezar desde su coordenada continua
`x,y`.

Flujo operativo:

```text
Indoor model
  -> EvacTopology
  -> multilevel_transfer_to_transfer
  -> WeightSnapshotCompiler
  -> snapshot.graph ponderado por perfil
  -> recomendador de rutas
```

El snapshot ponderado respeta:

- perfil de movilidad;
- tiempo base de cruce;
- penalizacion de escaleras, rampas y ascensores;
- seguridad de hazards y beacons;
- bloqueos;
- congestion si esta activa.

## Coste Base

La base de todas las aristas es tiempo de recorrido, no distancia 2D pura:

```text
t(e) = lengthM(e) / (v_p * phi_c) + delta_m(e)
```

Donde:

- `v_p` es la velocidad base del perfil de movilidad;
- `phi_c` es el factor del tipo de conector;
- `delta_m(e)` representa overheads de maniobra y cruce.

Esto evita tratar una rampa o escalera como si fuera un tramo llano con la misma
proyeccion horizontal.

## Seguridad

En la UI se habla de seguridad porque es mas intuitivo:

```text
safety = 1        zona segura
safety = 0        zona insegura
safety_loss = 1 - safety
```

Internamente se conserva el nombre historico:

```text
riskPenalty = safety_loss
```

La forma canonica para la memoria es:

```text
C(e) = alpha * t(e) + beta * r(e)
```

Con varias fuentes:

```text
C(e) = alpha * t(e) + beta_h * r_h(e) + beta_b * r_b(e)
```

En la implementacion tambien existe el modelo multiplicativo:

```text
C(e) = t(e) * (alpha + beta_h * r_h(e) + beta_b * r_b(e))
```

## CER

CER significa:

```text
Centralidad de Evacuacion por Reencaminamiento
```

Para cada origen `v`, salida `d` y perfil de fallo `p`:

1. Se calcula la ruta base `P0(v,d)`.
2. Se mide su coste `C0`.
3. Se define la tolerancia:

```text
Cmax = (1 + tau) * C0
```

4. Se eliminan recursos segun el perfil de fallo.
5. Se recalcula la ruta.
6. Una alternativa cuenta si:

```text
C_alt <= Cmax
```

7. Las rutas distintas se cuentan por secuencia exacta de nodos, salvo que en
   el futuro se active una politica de solape.

La salida primaria conserva el detalle:

```text
origin -> target -> profile -> metrics
```

El resumen por nodo es derivado y sirve para aplicar CER en politicas de
recomendacion.

## Perfiles Recomendados

Para el uso normal del workbench y los barridos de todos los nodos:

```text
(1)
(1,1)
```

Para estudiar simultaneidad moderada:

```text
(2)
(2,1)
(2,2)
```

Perfiles mas profundos como `(1,1,1)` o `(2,1,1)` se reservan para visualizacion
puntual o sensibilidad. El arbol puede crecer mucho y conviene ejecutarlo sin
debug completo cuando se quieren limites altos.

Configuracion razonable:

```text
maxDepth = 2
maxK = 2
maxTotalFailures = 4
maxCombinations = 1000
maxRuntimeMs = 1000..30000 segun el experimento
failureUnit = resource
distinctnessPolicy = exact
```

`failureUnit = resource` es la opcion principal porque una puerta, rampa,
escalera, boundary o conector se bloquea como recurso fisico completo, no como
un arco dirigido aislado.

## Politicas Actuales

### Minimum Time

Minimiza el tiempo de viaje con movilidad filtrada.

Uso:

```text
routeSelection = lowest_cost
useBeaconRisk = false
useHazardRisk = false
algorithm = dijkstra
```

Sirve como baseline fisico.

### Safety + Time

Minimiza tiempo ponderado por seguridad:

```text
routeSelection = lowest_cost
useBeaconRisk = true
useHazardRisk = true
riskCostModel = multiplicative_beta
algorithm = dijkstra
```

Sirve para comprobar que balizas/hazards deforman la ruta antes de introducir
CER.

### CER-Cost

Convierte la CER en una penalizacion positiva por baja capacidad de
reencaminamiento:

```text
cerNorm(v) = CER(v) / maxCER
agilityPenalty(v) = 1 - cerNorm(v)
edgeWeight = timeSafetyCost(e) + lambda * agilityPenalty(targetNode)
```

El solver minimiza el nuevo peso escalar. Es una politica directa y barata:

```text
routeSelection = cer_weighted
algorithm = dijkstra
centralityType = rerouting
```

### CER-Agility

Genera rutas candidatas y despues elige la mejor por CER dentro de una
tolerancia de coste:

```text
1. generar k rutas candidatas;
2. filtrar por coste razonable;
3. calcular agilidad CER de cada ruta;
4. elegir la de mayor agilidad.
```

Es conceptualmente mas expresiva que CER-Cost porque separa generacion de
candidatas y decision:

```text
routeSelection = cer_agility_yen
algorithm = yen_ksp
centralityType = rerouting
```

## Agregacion CER

El score de nodo puede ponderar perfiles:

```text
CER_score(v) =
    1.0 * CER_(1)(v)
  + 0.6 * CER_(1,1)(v)
```

Si se activan perfiles de simultaneidad:

```text
CER_score(v) =
    1.0 * CER_(1)(v)
  + 0.6 * CER_(1,1)(v)
  + 0.7 * CER_(2)(v)
  + 0.5 * CER_(2,1)(v)
```

La decision importante es no confundir la suma derivada con la salida primaria:
la metrica completa sigue existiendo por origen, salida y perfil.

## CER Estructural Y CER Dinamica

Uso principal actual:

```text
CER estructural precomputada
```

Ventajas:

- es estable;
- representa la capacidad estructural del edificio;
- es reutilizable durante la simulacion;
- puede combinarse con seguridad dinamica sin recalcular todo el arbol.

Uso futuro o puntual:

```text
CER dinamica sobre snapshot actual
```

Puede recalcularse si una baliza bloquea una zona, pero solo con perfiles y
limites bajos si se quiere mantener una latencia subsegundo.

## Workbench

La seccion visual se llama:

```text
CER & Route Recommendation
```

Muestra solo politicas de trabajo:

- `minimum_time`;
- `safety_time`;
- `cer_weighted`;
- `cer_agility_yen`.

El selector visible es la politica. El solver interno se deriva de ella:

- Minimum Time -> Dijkstra;
- Safety + Time -> Dijkstra;
- CER-Cost -> Dijkstra con penalizacion inversa de CER;
- CER-Agility -> Yen como generador de candidatas.

El boton `Run simulation` usa la politica y parametros actuales. `Apply policy
+ run` copia primero la politica seleccionada y despues simula.

## Comandos Utiles

Abrir el workbench:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine workbench --model UnaPlanta_ConConexionesVerticales --host 127.0.0.1 --port 8765
```

Exportar visualizacion CER de un nodo:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine cer-tree --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --origin CS_L00_DOOR_001 --profile MP_WALKING --failure-profiles "1;1,1" --tau 0.2 --max-depth 2 --max-k 2 --max-total-failures 4 --max-combinations 1000 --max-runtime-ms 30000 --formats json,html --visual-order tree
```

Calcular CER compacta para todos los nodos sin debug pesado:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine cer-tree --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --all-origins --profile MP_WALKING --failure-profiles "1;1,1" --tau 0.2 --max-depth 2 --max-k 2 --max-total-failures 4 --max-combinations 1000 --max-runtime-ms 30000 --debug-steps none --formats summary-json
```

Generar HTML explicativo de aplicacion CER al recomendador:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine explain-routing-policies --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --origin CS_L00_DOOR_001 --target CS_L00_EXIT_001 --profile MP_WALKING --failure-profiles "1;1,1" --cost-tolerance 0.2 --level LEVEL_00
```

El comando `compare-routing` se conserva como utilidad tecnica de comparacion
de presets, pero no es el flujo principal del workbench ni el eje metodologico
del TFG.

## Salidas Esperadas

CER-tree puede generar:

- `cer_tree_summary.json`: resumen compacto;
- `cer_tree_debug.json`: pasos detallados si se activa debug;
- `cer_tree_explanation.html`: visor paso a paso;
- `cer_tree_distinct_routes.html`: rutas distintas globales cuando aplica.

El policy explainer genera:

- `cer_cost_explainer.html`;
- `cer_agility_explainer.html`;
- `cer_all_nodes.json`;
- `policy_comparison.html`;
- `policy_comparison.json`.

## Que Queda Fuera Del Foco Principal

- Comparar solvers genericos como resultado cientifico principal.
- Usar `space_connectivity` como grafo principal del recomendador.
- Recalcular CER completa de todos los nodos en cada tick con perfiles largos.
- Confundir robustez de una ruta con CER de un nodo.

## Texto Para La Memoria

El recomendador de EvacEngine se plantea como un sistema de politicas de
evacuacion sobre un grafo indoor tipo IndoorGML. La geometria se transforma en
un backbone `multilevel_transfer_to_transfer`, ponderado por tiempo de cruce,
movilidad, seguridad y bloqueos dinamicos. Sobre ese snapshot se calculan rutas
mediante solvers de grafos, pero la contribucion principal no reside en escoger
un algoritmo generico, sino en definir politicas de seleccion de rutas. La
metrica CER mide la capacidad de un nodo para conservar rutas alternativas
aceptables ante fallos de recursos fisicos, y se incorpora al recomendador de
dos formas: como penalizacion inversa en el coste (`CER-Cost`) o como criterio
de agilidad sobre rutas candidatas (`CER-Agility`).
