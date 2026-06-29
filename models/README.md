# Models

Esta carpeta es el workspace principal para los modelos creados por ti.

`examples/indoor_data_model/` sigue siendo la zona de ejemplos estables del repositorio, como plantillas o casos de referencia. No se actualiza cuando dibujas modelos nuevos.

Cada modelo propio debe vivir aqui, con nombre corto y estructura fija:

```text
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
```

## Inicio rapido

En Windows puedes abrir el launcher con doble clic en:

```text
quick_start.bat
```

O desde terminal:

```powershell
python tools\quick_start.py
```

El launcher te pregunta las opciones y ejecuta:

- SpatialEngine para crear un IndoorModel nuevo con nombre, ancho y alto;
- el visor SpatialEngine para revisar capas/grafos de un IndoorModel existente en `models/`;
- EvacEngine Workbench para cargar scenarios, simular, guardar GIF/HTML y comparar routing.
- `Listar mis modelos de trabajo` muestra solo `models/`; `Listar todo lo detectable` incluye tambien ejemplos y backups historicos.

Regla practica:

- `spatial/indoor_model.json` describe el edificio exportado por SpatialEngine.
- `evacuation/scenarios/*.json` describe una configuracion de EvacEngine sobre ese edificio: agentes, balizas, destino, algoritmo, fisica y duracion.
- `evacuation/experiments/` guarda configuraciones comparativas o notas de routing.
- `outputs/` guarda resultados generados, GIFs, HTML, CSV y metricas de ese modelo.
- `outputs/indoor_models/` en la raiz del repo conserva backups historicos con timestamp.

Crear un modelo desde un IndoorModel existente:

```powershell
python tools\create_model_workspace.py --name Single_Floor_01 --indoor examples\indoor_data_model\una_sola_planta_indoor_model.json --scenario examples\indoor_data_model\scenario_single_floor.json
```

Crear un IndoorModel desde cero con nombre y dimensiones:

```powershell
python src\MLSM_SpatialEngine.py --name Mi_Edificio_01 --width 45 --height 28 --decomposition triangulation --render-detail fast
```

Dentro de SpatialEngine:

- dibuja muros, puertas, salidas, ventanas, columnas, escaleras/rampas/ascensores y espacios;
- pulsa `e` para exportar el modelo activo;
- el modelo queda en `models\Mi_Edificio_01\spatial\indoor_model.json`;
- se intenta crear automaticamente `models\Mi_Edificio_01\evacuation\scenarios\baseline.json`;
- si no hay geometria navegable o salida suficiente, crea/corrige el edificio y vuelve a exportar.

Abrir directamente ese modelo en EvacEngine:

```powershell
python -m src.evac_engine workbench --model Mi_Edificio_01
```

En ese workbench puedes guardar varios scenarios del mismo IndoorModel con `Save scenario name` + `Save scenario`.

Si exportas directamente desde SpatialEngine con `e`, tambien se escribe automaticamente:

```text
models/<nombre_modelo>/spatial/indoor_model.json
```

Si cierras SpatialEngine sin dibujar geometria de edificio, no se genera ningun JSON.

Verificar visualmente el modelo:

```powershell
python -m src.spatial_engine.web_app --model models\Single_Floor_01\spatial\indoor_model.json
```

Abrir EvacEngine sobre un modelo:

```powershell
python -m src.evac_engine workbench --model Single_Floor_01
```

En el workbench de EvacEngine:

- `Open indoor` abre el `indoor_model.json` y crea/reutiliza `evacuation/scenarios/baseline.json`.
- `Scenarios for loaded model` carga solo escenarios que referencian ese mismo IndoorModel.
- `Save scenario name` + `Save scenario` guarda una configuracion nueva en `models/<nombre>/evacuation/scenarios/<nombre>.json`.
- `Run simulation` ejecuta en memoria para mirar la animacion en el canvas.
- `Save GIF/HTML` vuelve a ejecutar la configuracion actual y guarda `simulation.gif` y/o `simulation.html` en `models/<nombre>/outputs/<scenario>/`.
- `Save comparison viewer` compara los presets marcados y guarda `comparison_viewer.html`, CSV y JSON en `models/<nombre>/outputs/<scenario>_routing_compare/`.

Comandos equivalentes por CLI:

```powershell
python -m src.evac_engine run --scenario models\Single_Floor_01\evacuation\scenarios\baseline.json --output-dir models\Single_Floor_01\outputs\baseline
python -m src.evac_engine render --scenario models\Single_Floor_01\evacuation\scenarios\baseline.json --gif models\Single_Floor_01\outputs\baseline\simulation.gif --html models\Single_Floor_01\outputs\baseline\simulation.html
python -m src.evac_engine compare-routing --scenario models\Single_Floor_01\evacuation\scenarios\baseline.json --presets dijkstra_time,astar_time,floyd_warshall_time,robust_agility --output-dir models\Single_Floor_01\outputs\baseline_routing_compare
```
