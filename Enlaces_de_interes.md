# Links de interés

## Sobre la evacuación
### PathFinder de ThunderHead Engineering
Modelo de evacuación, este modelo es bastante popular en el diseño de edificios para evaluar el tiempo de evauación, es de pago pero tiene prueba gratis 30 dias -> [PathFinder](https://www.thunderheadeng.com/pathfinder/)

- Se pueden importar modelos Autocad(.DWG) o modelos de Revit/BIM (.IFC)
- Simular movimienos realistas, tiene dos motores de movimiento: **SFPE** *(los agentes se pueden superponer)* y **Steering** *(los agentes colisionan y depende de la distancia y obstaculos, es más relista)*
- Se visuaiza en 3D, diagramas de calor, cuellos de botella etc.
- Integra FDS (Fire Dynamics Simulator) se pueden importar resultados de un incendio (humo, calor, gases) de PyroSim/FDS y ver como afecta a las personas (visibilidad, calor, etc)

Si consigo la versión más reciente de PathFinder podría trasladar la lógica de la recomendación de rutas al software con el uso de  Python, en principio lo que deberia hacer es:
- Modelar/Dibujar/Importar el edificio.
- Definir los peligros y zonas peligrosas en ciertos momentos.
- Script de Control, Programar un bucle para cada segundo de simulación. 1. Analiza el estado (Peligro) 2. Ejecuta algoritmo de recomendación de ruta (basado en datos de pthfinder) 3. Actualiza el destino de los agentes según la **recomendación de ruta**.
- simular, para obervar como siguen las instrucciones.

#### Como