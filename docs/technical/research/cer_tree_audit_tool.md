# CER tree audit tool

Este documento describe la herramienta nueva y separada para calcular la
Centralidad de Evacuacion por Reencaminamiento como arbol de fallos acotado.
La referencia conceptual sigue estando en
`docs/technical/research/CER_referencia_decisiones_y_prompt_codex.md`.

## Objetivo

La herramienta calcula, para cada origen y salida, cuantas rutas alternativas
validas conserva el grafo operativo cuando se eliminan recursos, arcos o
celdas de la ruta actual y se recalcula la evacuacion.

No sustituye todavia a las politicas de recomendacion en simulacion. Es una
herramienta de auditoria y calibracion para estudiar:

- cuanto tarda el calculo;
- cuantos casos de fallo se evaluan;
- si se corta por tiempo, combinatoria o profundidad;
- cuantas rutas distintas aparecen;
- que perfiles de fallo aportan informacion.

## Archivos implicados

- `src/evac_engine/cer_tree.py`: implementacion del calculo CER-tree.
- `src/evac_engine/cli.py`: comando `cer-tree`.
- `tests/test_cer_tree.py`: tests unitarios de la herramienta.

Esto es distinto de:

- `src/evac_engine/rerouting_centrality.py`: centralidad/rerouting anterior.
- `src/evac_engine/cer_visualization.py`: visualizacion explicativa previa.
- `src/evac_engine/route_recommendation.py`: politicas de recomendacion usadas
  por la simulacion.

## Grafo usado

El comando construye el grafo ponderado desde el escenario mediante
`RoutingEngine.compile_snapshot(...)`, por tanto usa el snapshot operativo de
EvacEngine. Ese snapshot parte del grafo configurado como
`multilevel_transfer_to_transfer` y aplica los pesos activos:

- perfil de movilidad;
- tiempo de cruce;
- escaleras, rampas y ascensores;
- recursos no transitables para un perfil;
- beacons/hazards si se ejecuta en modo dinamico.

Por defecto se usa el modo estructural inicial del escenario, sin avanzar la
simulacion temporal de beacons:

```text
structural = true
step = 0
time_s = 0
```

## Que significa origin -> target -> failureProfile -> metricas

La salida no es un unico numero global. La estructura conserva el detalle:

```text
origin node
  -> target exit
     -> failure profile
        -> metricas
```

Ejemplo conceptual:

```text
CS_L00_DOOR_001
  -> CS_L00_EXIT_001
     -> (1)
     -> (1,1)
     -> (2)
```

Esto permite comparar el mismo origen contra varias salidas y separar fallos
simples, secuenciales y simultaneos. El resumen agregado existe solo como valor
derivado para inspeccion o futuras politicas.

## Perfiles generados

Con los valores por defecto:

```text
maxDepth = 2
maxK = 2
maxTotalFailures = 4
```

aparecen perfiles como:

```text
(1)
(2)
(1,1)
(1,2)
(2,1)
(2,2)
```

Cada numero indica cuantos elementos fallan a la vez en ese nivel del arbol.
Por ejemplo:

```text
(1,2) = falla 1 recurso, se recalcula, despues fallan 2 recursos de la nueva ruta
```

## Metricas principales

- `baseCost`: coste de la ruta minima inicial `P0`.
- `costLimit`: limite aceptable `Cmax = (1 + tau) * baseCost`.
- `distinctRoutes`: rutas aceptadas con secuencia de nodos distinta.
- `acceptedCases`: casos con ruta encontrada dentro de tolerancia.
- `totalCases`: casos evaluados para ese perfil.
- `coverage`: `acceptedCases / totalCases`.
- `noPathCases`: fallos que dejan al origen sin ruta.
- `overToleranceCases`: rutas encontradas pero demasiado caras.
- `duplicateRouteCases`: rutas aceptadas pero repetidas.
- `visitedStateCases`: estados de fallo ya vistos y reutilizados.
- `truncatedByRuntime`: el perfil se corto por `maxRuntimeMs`.
- `truncatedByCombinations`: el perfil se corto por `maxCombinations`.
- `combinationsTruncatedCases`: combinaciones descartadas por limite.

## Comando minimo

```powershell
python -m src.evac_engine cer-tree --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --origin CS_L00_DOOR_001 --target CS_L00_EXIT_001 --profile MP_WALKING
```

## Modo interactivo

Para explorar valores sin editar un comando largo, usa el playground:

```powershell
python tools\cer_tree_playground.py
```

Tambien se puede abrir desde el menu general:

```powershell
python tools\quick_start.py
```

y elegir:

```text
6) CER-tree playground
```

El playground pregunta por:

- modelo en `models/`;
- scenario asociado;
- perfil de movilidad;
- nodo origen o todos los nodos;
- salida objetivo o todas las salidas configuradas;
- preset de perfiles de fallo o perfiles personalizados;
- `tau`, `maxDepth`, `maxK`, `maxTotalFailures`, `maxCombinations` y `maxRuntimeMs`;
- visualizacion `tree`, `calculation` o ambas;
- carpeta de salida.

Es la forma recomendada para jugar con perfiles como:

```text
1;1,1;1,1,1
2;2,1;2,1,1
1;2;1,1;1,2;2,1
```

sin tener que moverse por una linea de comando enorme.

Si eliges todos los nodos, lo normal es desactivar el HTML visual paso a paso.
Asi se genera una tabla manejable con `distinctRoutes` por:

```text
origin -> target -> failureProfile
```

La tabla queda en:

```text
cer_tree_summary_<profile>.csv
cer_tree_<profile>.html
```

## Comando con parametros explicitos

```powershell
python -m src.evac_engine cer-tree --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --origin CS_L00_DOOR_001 --target CS_L00_EXIT_001 --profile MP_WALKING --tau 0.3 --max-depth 2 --max-k 2 --max-total-failures 4 --max-combinations 1000 --max-runtime-ms 5000
```

`--profile` es el perfil de movilidad. Para escoger perfiles de fallo se usa
`--failure-profiles`:

```powershell
python -m src.evac_engine cer-tree --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --origin CS_L00_DOOR_001 --target CS_L00_EXIT_001 --profile MP_WALKING --failure-profiles "1;1,1" --tau 0.3 --max-depth 2 --max-k 1 --max-runtime-ms 5000
```

## Barrido de todos los nodos

Para ver `distinctRoutes` de todos los nodos contra las salidas configuradas,
usa `--all-origins`. Empieza con perfiles pequenos para controlar tiempo y
combinatoria:

```powershell
python -m src.evac_engine cer-tree --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --all-origins --profile MP_WALKING --failure-profiles "1" --tau 0.3 --max-depth 1 --max-k 1 --max-total-failures 1 --max-runtime-ms 30000 --formats json,csv,html
```

Para fallo secuencial simple:

```powershell
python -m src.evac_engine cer-tree --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --all-origins --profile MP_WALKING --failure-profiles "1;1,1" --tau 0.3 --max-depth 2 --max-k 1 --max-total-failures 2 --max-runtime-ms 30000 --formats json,csv,html
```

Si se pide un perfil secuencial como `(1,1)`, el calculo conserva sus prefijos
necesarios, por ejemplo `(1)`, porque el segundo nivel solo existe despues de
una replanificacion valida del primer nivel.

## Comparar movilidad walking y rolling

```powershell
python -m src.evac_engine cer-tree --scenario models\UnaPlanta_ConConexionesVerticales\evacuation\scenarios\baseline.json --origin CS_L00_DOOR_001 --target CS_L00_EXIT_001 --profile MP_WALKING --profile MP_ROLLING_ACCESSIBLE --max-runtime-ms 5000
```

## Salidas generadas

Si no se indica `--output-dir`, los resultados se guardan junto al modelo:

```text
models/<Modelo>/outputs/cer_tree/<scenario_name>/
```

Archivos:

- `cer_tree_<profile>.json`: salida completa con metricas y pasos debug.
- `cer_tree_summary_<profile>.csv`: tabla plana para hoja de calculo.
- `cer_tree_<profile>.html`: inspeccion rapida en navegador.
- `cer_tree_<profile>_visual.html`: visor interactivo sobre el grafo real.
- `cer_tree_manifest.json`: indice de la ejecucion.

El visor `visual.html` reutiliza la gramatica visual de la explicacion CER:

- grafo base en gris;
- ruta inicial `P0` en azul;
- ruta fuente actual en ambar;
- ruta recalculada aceptada en verde;
- ruta recalculada rechazada en rojo;
- recurso fallado en rojo discontinuo;
- panel con `C0`, `Cmax`, `Calt`, perfil, decision y rutas distintas.

Permite avanzar con botones, `Play/Pausa` o flechas izquierda/derecha.
Cuando el payload incluye varios origenes, el grafo muestra sobre cada nodo el
valor `distinctRoutes` correspondiente al `target` y `failureProfile` del paso
activo. Asi se puede ver visualmente como se reparte la CER, por ejemplo para
`(1)` o `(1,1)`, sin bajar necesariamente a la tabla.

Debajo del grafo, haciendo scroll, el mismo HTML incluye un bloque de resultado
final con:

- suma de `distinctRoutes` para las filas incluidas;
- mejor fila `origin -> target -> profile`;
- numero de origenes, salidas y perfiles;
- coverage global;
- tabla completa `origin, target, failureProfile, distinctRoutes, acceptedCases,
  totalCases, coverage...`.

Hay dos ordenes visuales:

- `--visual-order tree`: reordena los pasos por rama del arbol. Muestra un
  fallo `(1)`, desciende a sus hijos `(1,1)`, `(1,1,1)` si existen, y vuelve
  despues a la siguiente rama. Es el mejor modo para explicar la metodologia.
- `--visual-order calculation`: respeta el orden bruto en que se generaron los
  pasos debug. Es mas util para auditar el algoritmo.

Hay dos layouts:

- `--visual-layout wide`: panel de estado a la izquierda, grafo grande y lista
  de pasos abajo.
- `--visual-layout standard`: lista de pasos a la izquierda y detalle arriba,
  como el visor CER anterior.

## Como interpretar los limites

`maxRuntimeMs` no es una constante fisica. Es un limite de seguridad para saber
si el calculo se puede completar dentro del presupuesto elegido. Se puede
aumentar para experimentar:

```text
1000 ms  -> rapido, puede truncar perfiles complejos
5000 ms  -> util para un origen concreto
30000 ms -> util para barridos mas grandes
```

El resultado indica si se ha llegado al limite mediante `truncatedByRuntime`.
Si aparece `false`, ese origen/salida/perfil se ha completado con los limites
combinatorios indicados.

## Estado actual

La herramienta ya calcula CER-tree y exporta JSON, CSV y HTML. La integracion
directa de estos valores en las politicas de recomendacion queda separada para
la siguiente fase, cuando se decida si usar:

- penalizacion inversa sobre el peso de arista;
- seleccion de rutas candidatas tipo Yen;
- una combinacion de ambas.
