# Suite documental de simulaciones

Estos GIFs se generaron para documentar visualmente que EvacEngine puede ejecutar el mismo modelo con distintas composiciones de movilidad.

## Escenarios usados

Cada modelo tiene tres escenarios nuevos:

```text
models/<modelo>/evacuation/scenarios/doc_walking_suite.json
models/<modelo>/evacuation/scenarios/doc_rolling_suite.json
models/<modelo>/evacuation/scenarios/doc_mixed_suite.json
```

Los agentes se colocaron manualmente en habitaciones (`GeneralSpace`, `Room`, `NavigableSpace`), evitando puertas, ventanas, virtual boundaries y conectores. Esto permite verificar agentes en diferentes salas y con diferentes perfiles sin tocar el `baseline.json`.

## GIFs generados

| Modelo | Walking | Rolling | Mixed |
|---|---|---|---|
| `Mi_Planta_SoloPuertas` | `mi-planta-solopuertas_walking.gif` | `mi-planta-solopuertas_rolling.gif` | `mi-planta-solopuertas_mixed.gif` |
| `UnaPlanta_ConConexionesVerticales` | `unaplanta-conconexionesverticales_walking.gif` | `unaplanta-conconexionesverticales_rolling.gif` | `unaplanta-conconexionesverticales_mixed.gif` |
| `UnaPlanta_Intento_1` | `unaplanta-intento-1_walking.gif` | `unaplanta-intento-1_rolling.gif` | `unaplanta-intento-1_mixed.gif` |

## Resultado de QA

| Modelo | Caso | Evacuados | Max time | No route | Trapped | Large jumps | Body overlap samples |
|---|---:|---:|---:|---:|---:|---:|---:|
| `Mi_Planta_SoloPuertas` | walking | 10/10 | 18.5 s | 0 | 0 | 0 | 0 |
| `Mi_Planta_SoloPuertas` | rolling | 10/10 | 25.5 s | 0 | 0 | 0 | 0 |
| `Mi_Planta_SoloPuertas` | mixed | 12/12 | 26.0 s | 0 | 0 | 0 | 0 |
| `UnaPlanta_ConConexionesVerticales` | walking | 10/10 | 19.5 s | 0 | 0 | 0 | 0 |
| `UnaPlanta_ConConexionesVerticales` | rolling | 10/10 | 28.5 s | 0 | 0 | 0 | 0 |
| `UnaPlanta_ConConexionesVerticales` | mixed | 12/12 | 30.5 s | 0 | 0 | 0 | 1 |
| `UnaPlanta_Intento_1` | walking | 10/10 | 18.5 s | 0 | 0 | 0 | 0 |
| `UnaPlanta_Intento_1` | rolling | 10/10 | 25.0 s | 0 | 0 | 0 | 0 |
| `UnaPlanta_Intento_1` | mixed | 12/12 | 30.0 s | 0 | 0 | 0 | 0 |

Todos los casos usaron `multilevel_transfer_to_transfer`.

## Comando base

```powershell
python -m src.evac_engine render --scenario models\<modelo>\evacuation\scenarios\doc_<caso>_suite.json --gif docs\tfg\media\simulation\<salida>.gif --level LEVEL_00 --fps 8 --max-frames 120 --skip-geometry-qa
```
