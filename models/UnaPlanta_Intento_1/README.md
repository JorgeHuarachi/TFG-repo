# UnaPlanta_Intento_1

Workspace creado desde SpatialEngine.

- `spatial/indoor_model.json`: modelo espacial/topologico activo del edificio.
- `spatial/indoor_model_all_adjacency.json`: export debug si usas `x`.
- `evacuation/scenarios/`: configuraciones de EvacEngine asociadas a este modelo.
- `evacuation/experiments/`: pruebas comparativas de routing.
- `outputs/`: resultados generados por simulaciones de este modelo.

Comandos utiles:

```powershell
python -m src.spatial_engine.web_app --model models\UnaPlanta_Intento_1\spatial\indoor_model.json
python -m src.evac_engine workbench --model UnaPlanta_Intento_1
python -m src.evac_engine workbench --scenario models\UnaPlanta_Intento_1\evacuation\scenarios\<scenario>.json
```
