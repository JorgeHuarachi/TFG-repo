# Media para la memoria del TFG

Esta carpeta guarda recursos visuales seleccionados para documentacion, tutores y memoria. No sustituye a los outputs reproducibles de cada modelo.

## Regla de uso

* Outputs brutos y reproducibles: `models/<modelo>/outputs/`.
* Recursos curados para explicar el trabajo: `docs/tfg/media/`.

## Carpetas

```text
authoring/
  GIFs o videos de dibujo y autoria en SpatialEngine.

simulation/
  GIFs seleccionados de simulaciones de EvacEngine.
  Ver `simulation/README.md` para la suite walking/rolling/mixed.

routing/cer/
  GIFs, PNG, HTML o capturas que expliquen routing y CER.
```

## Evidencias incluidas ahora

```text
authoring/Dibujado_Space_UnaPlanta_ConConexionesVerticales.gif
authoring/Dibujado_Space_UnaPlanta_ConSoloPuertas.gif
simulation/evac_single_floor_baseline.gif
simulation/mi-planta-solopuertas_walking.gif
simulation/mi-planta-solopuertas_rolling.gif
simulation/mi-planta-solopuertas_mixed.gif
simulation/unaplanta-conconexionesverticales_walking.gif
simulation/unaplanta-conconexionesverticales_rolling.gif
simulation/unaplanta-conconexionesverticales_mixed.gif
simulation/unaplanta-intento-1_walking.gif
simulation/unaplanta-intento-1_rolling.gif
simulation/unaplanta-intento-1_mixed.gif
routing/cer/cer_rerouting_explanation.gif
routing/cer/cer_rerouting_summary.png
routing/cer/cer_rerouting_explanation.html
routing/cer/cer_rerouting_debug.json
```

La evidencia CER curada en GIF cubre los perfiles `(1)` y `(1,1)` completos con `tau = 0.2`. Para exploraciones mas profundas, como `(1,1,1)` o `(1,2)`, es preferible usar el HTML interactivo y grabar el tramo necesario con ScreenToGif.

## Nombres recomendados

```text
authoring/spatial_authoring_single_floor.gif
authoring/spatial_authoring_multilevel.gif
simulation/evac_single_floor_baseline.gif
simulation/evac_beacons_dynamic_safety.gif
routing/cer/cer_rerouting_explanation.gif
```

## Como enlazarlos desde el README principal

```markdown
![Autoria SpatialEngine](docs/tfg/media/authoring/spatial_authoring_single_floor.gif)
![Simulacion EvacEngine](docs/tfg/media/simulation/evac_single_floor_baseline.gif)
![CER rerouting](docs/tfg/media/routing/cer/cer_rerouting_explanation.gif)
```

## Criterio

Guarda aqui solo material que quieras usar para explicar el proyecto. Si un GIF sale de una ejecucion concreta, conserva tambien el output original dentro de `models/<modelo>/outputs/`.
