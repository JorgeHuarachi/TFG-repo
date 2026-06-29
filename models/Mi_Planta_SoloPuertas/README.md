# Mi_Planta_SoloPuertas

Workspace creado desde SpatialEngine.

- `spatial/indoor_model.json`: modelo espacial/topologico activo del edificio.
- `spatial/indoor_model_all_adjacency.json`: export debug si usas `x`.
- `evacuation/scenarios/`: configuraciones de EvacEngine asociadas a este modelo.
- `evacuation/experiments/`: pruebas comparativas de routing.
- `outputs/`: resultados generados por simulaciones de este modelo.

Comandos utiles:

```powershell
python -m src.spatial_engine.web_app --model models\Mi_Planta_SoloPuertas\spatial\indoor_model.json
python -m src.evac_engine workbench --model Mi_Planta_SoloPuertas
python -m src.evac_engine validate --scenario models\Mi_Planta_SoloPuertas\evacuation\scenarios\baseline.json
python -m src.evac_engine render --scenario models\Mi_Planta_SoloPuertas\evacuation\scenarios\baseline.json --gif models\Mi_Planta_SoloPuertas\outputs\baseline\simulation.gif --html models\Mi_Planta_SoloPuertas\outputs\baseline\simulation.html
python -m src.evac_engine compare-routing --scenario models\Mi_Planta_SoloPuertas\evacuation\scenarios\baseline.json --presets dijkstra_time,astar_time,floyd_warshall_time,robust_agility --output-dir models\Mi_Planta_SoloPuertas\outputs\baseline_routing_compare
```
