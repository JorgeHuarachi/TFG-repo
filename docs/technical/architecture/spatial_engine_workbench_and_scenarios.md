# SpatialEngine workbench y organizacion de modelos

## Objetivo

Separar con claridad cuatro piezas:

- **IndoorModel**: salida espacial/topologica de SpatialEngine. No contiene agentes, balizas ni resultados.
- **Scenario**: configuracion de EvacEngine asociada a un IndoorModel. Contiene agentes, balizas, routing, fisica y duracion.
- **Experiment**: comparacion reproducible de estrategias de routing sobre uno o varios escenarios.
- **Output**: resultado generado al simular o comparar estrategias. Es regenerable.

## Estructura recomendada

```text
examples/indoor_data_model/
  ejemplos estables / plantillas del repositorio

models/
  <nombre_modelo>/
    spatial/
      indoor_model.json
      indoor_model_all_adjacency.json
    evacuation/
      scenarios/
        baseline.json
        routing_time.json
        routing_safety.json
        routing_robust.json
      experiments/
        routing_compare.json
    outputs/
      metrics.csv
      metrics.json
      routes.json
      trajectories.ndjson
      simulation.gif
      simulation.html
    README.md

outputs/
  indoor_models/
    copias historicas con timestamp
  visual_checks/
    PNGs de verificacion reproducibles
```

`outputs/` esta ignorado por git. Puede limpiarse cuando haga falta, salvo que haya resultados concretos que quieras conservar para la memoria.

Regla de uso:

- `examples/` no es la carpeta de trabajo para modelos nuevos.
- `models/<nombre>/spatial/indoor_model.json` es el modelo activo y legible.
- `models/<nombre>/evacuation/scenarios/*.json` son configuraciones de simulacion sobre ese mismo edificio.
- `models/<nombre>/evacuation/experiments/*.json` son pruebas comparativas de routing.
- `models/<nombre>/outputs/` guarda resultados de ese modelo.
- `outputs/indoor_models/<nombre>_indoor_model_<timestamp>.json` es backup tecnico exportado automaticamente.

Si cierras SpatialEngine sin dibujar geometria de edificio, no se genera ningun `indoor_model.json`. Esto evita casos vacios creados por accidente.

## Crear un model workspace

```powershell
python tools\create_model_workspace.py --name Single_Floor_01 --indoor examples\indoor_data_model\una_sola_planta_indoor_model.json --scenario examples\indoor_data_model\scenario_single_floor.json
```

El comando copia el IndoorModel a:

```text
models/Single_Floor_01/spatial/indoor_model.json
```

y copia los escenarios a:

```text
models/Single_Floor_01/evacuation/scenarios/
```

Al copiar un escenario, el campo `indoorModelRef.path` se reescribe a `../../spatial/indoor_model.json`, de forma que el escenario queda autocontenido dentro del modelo.

Si exportas desde SpatialEngine pulsando `e`, el exportador ya escribe directamente una copia activa en:

```text
models/<nombre_del_modelo>/spatial/indoor_model.json
```

y mantiene una copia historica con timestamp en:

```text
outputs/indoor_models/
```

## Flujo EvacEngine por modelo

El flujo esperado despues de tener `models/<nombre>/spatial/indoor_model.json` es:

1. Abrir el workbench:

```powershell
python -m src.evac_engine workbench --model <nombre>
```

2. En `Open`, usar `Scenarios for loaded model` para cambiar entre escenarios del mismo IndoorModel.
3. Configurar agentes, destino, balizas, fisica y routing.
4. Usar `Run simulation` para revisar visualmente sin escribir el scenario.
5. Usar `Save scenario name` + `Save scenario` para persistir esa configuracion como:

```text
models/<nombre>/evacuation/scenarios/<scenario>.json
```

6. Usar `Save GIF/HTML` para guardar la animacion reproducible en:

```text
models/<nombre>/outputs/<scenario>/simulation.gif
models/<nombre>/outputs/<scenario>/simulation.html
```

7. Usar `Save comparison viewer` en `Routing Experiments` para comparar presets de recomendacion y guardar:

```text
models/<nombre>/outputs/<scenario>_routing_compare/comparison_viewer.html
models/<nombre>/outputs/<scenario>_routing_compare/comparison_metrics.csv
models/<nombre>/outputs/<scenario>_routing_compare/comparison_routes.csv
models/<nombre>/outputs/<scenario>_routing_compare/comparison_summary.json
```

Esto permite tener varios escenarios sobre el mismo edificio sin duplicar el IndoorModel: por ejemplo `baseline.json`, `crowd_high_density.json`, `beacon_blocked_ramp.json` o `routing_robust_agility.json`.

Comandos CLI equivalentes:

```powershell
python -m src.evac_engine run --scenario models\<nombre>\evacuation\scenarios\<scenario>.json --output-dir models\<nombre>\outputs\<scenario>
python -m src.evac_engine render --scenario models\<nombre>\evacuation\scenarios\<scenario>.json --gif models\<nombre>\outputs\<scenario>\simulation.gif --html models\<nombre>\outputs\<scenario>\simulation.html
python -m src.evac_engine compare-routing --scenario models\<nombre>\evacuation\scenarios\<scenario>.json --presets dijkstra_time,astar_time,floyd_warshall_time,robust_agility --output-dir models\<nombre>\outputs\<scenario>_routing_compare
```

## SpatialEngine clasico

La UI matplotlib de autoria se mantiene como punto de entrada para dibujar. Ahora puede arrancar con dimensiones configurables:

```powershell
python src\MLSM_SpatialEngine.py --name Single_Floor_01 --width 45 --height 28
```

Para crear un modelo nuevo desde cero:

```powershell
python src\MLSM_SpatialEngine.py --name Mi_Edificio_01 --width 45 --height 28 --decomposition triangulation --render-detail fast
```

Al pulsar `e`, SpatialEngine guarda:

```text
models/Mi_Edificio_01/spatial/indoor_model.json
```

y, si el modelo contiene geometria navegable suficiente, crea o reutiliza:

```text
models/Mi_Edificio_01/evacuation/scenarios/baseline.json
```

Despues se abre EvacEngine con:

```powershell
python -m src.evac_engine workbench --model Mi_Edificio_01
```

Tambien acepta variables de entorno:

```powershell
$env:MLSM_CANVAS_WIDTH=45
$env:MLSM_CANVAS_HEIGHT=28
python src\MLSM_SpatialEngine.py --name Single_Floor_01
```

La rueda del raton hace zoom alrededor del cursor. El contrato de exportacion del IndoorModel no cambia por esta mejora.

Para autoria fluida, la UI clasica arranca por defecto en renderizado rapido:

```powershell
python src\MLSM_SpatialEngine.py --name Single_Floor_01 --width 45 --height 28 --render-detail fast
```

`fast` dibuja geometria de autoria simple y evita recalcular la masa detallada de muros en cada redibujado. Para revisar juntas de muros y huecos con mas detalle:

```powershell
python src\MLSM_SpatialEngine.py --name Single_Floor_01 --width 45 --height 28 --render-detail full
```

Dentro de la UI, la tecla `0` alterna entre `fast` y `full`.

La ventana clasica tambien incluye un panel lateral de trabajo:

- muestra herramienta activa, siguiente accion esperada, nivel, dimensiones, locomocion y estrategia de descomposicion;
- muestra contadores de muros, aperturas, espacios detectados, columnas, conectores y agentes;
- permite activar/desactivar capas con checkboxes clicables: espacios automaticos, espacios manuales, muros, aperturas, conectores y agentes;
- permite alternar esas mismas capas con `4`, `5`, `6`, `7`, `8` y `9`;
- permite inspeccionar entidades con clic derecho o con modo `q`;
- resalta en rosa la entidad seleccionada cuando esta visible.

Esto mejora la autoria existente sin reimplementar aun todo el editor como aplicacion web.

## SpatialEngine workbench web

El visor web sirve para revisar por capas el IndoorModel generado:

```powershell
python -m src.spatial_engine.web_app --model models\Single_Floor_01\spatial\indoor_model.json
```

Capas principales:

- `Source`: geometria de autoria exportada como trazabilidad.
- `General`: espacios navegables generales.
- `Transfer`: puertas, salidas, rampas, escaleras, ascensores y otros espacios de transferencia.
- `Blocked`: objetos y espacios no navegables.
- `Boundaries`: limites navegables, no navegables y virtual boundaries.
- `Dual`: nodos y aristas base.
- `Graph`: vistas derivadas como `space_connectivity`, `door_to_door` o `vertical_connectivity`.

Controles:

- desplegable de IndoorModel;
- selector de planta o vista apilada multinivel;
- presets visuales;
- toggles de capas;
- zoom con rueda;
- arrastre con boton derecho o boton central;
- click en entidades para inspeccionar id, tipo y nivel.

## Verificaciones repetibles por CLI

La revision visual interactiva se complementa con PNGs reproducibles:

```powershell
python tools\visualize_latest_indoor_model.py --model models\Single_Floor_01\spatial\indoor_model.json --output-dir outputs\visual_checks_single --split-levels
```

Para fallar si hay solapes entre `CellSpace`:

```powershell
python tools\visualize_indoor_model.py models\Single_Floor_01\spatial\indoor_model.json --preset overlaps --fail-on-overlap --no-show
```

## Divisiones de GeneralSpace

La triangulacion sigue siendo la estrategia por defecto. SpatialEngine expone ahora estrategias seleccionables:

- `triangulation`: actual, robusta para poligonos irregulares;
- `rectilinear`: particion rectangular/ortogonal experimental para plantas tipo T, U o pasillos;
- `none`: conserva el poligono original como una sola celda, util para comparar.

Comando:

```powershell
python src\MLSM_SpatialEngine.py --name Single_Floor_01 --width 45 --height 28 --decomposition rectilinear
```

En la UI clasica, la tecla `g` alterna entre `triangulation`, `rectilinear` y `none`. La estrategia activa aparece en el titulo de la ventana.

La regla de seguridad es que el modo por defecto sigue siendo `triangulation` y genera el mismo contrato `indoor_model.json`. Las alternativas deben compararse por capas antes de usarse en EvacEngine.
