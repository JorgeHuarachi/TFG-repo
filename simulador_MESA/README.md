# GENERADOR DE PLANO + SIMULADOR DE EVACUACIÓN BASADA EN AGENTES
Aqui dejare ordenado lo que tiene implentado este sistemaa de generación de plano con la información necesaria en dos tipos de _schemas_ uno propio "json_data" y otro basado en un estandar "indoorjson2".

## Simulador basado en agentes
Este es un simulador que usa la información geometrica extraida de un json, en dicho json esta la distribución de una planta de un edificio (Muros, paredes, habitaciones, puertas, salidas) e incluso las relaciónes ya calculadas de estos elementos (conexion de habitación A con Habitación B mediante la puerta C) en forma de grafo. Este grafo viene con los pesos de la distancia entre cada uno de los elementos, este peso se dinamizará en función de la seguridad o condiciones de las habitaciones, puertas o cualquier elemento cercano, de tal forma que los peligros supongan un cambió en la prioridad de la evacuación (no ir por una ruta corta, sino una ruta segura y robusta).

El simulador esta implementado 100% en python con las siguientes librerias:

- **MESA**: Es un `Agent-Based Modeling` y un motor temporal, me deja manipular la lógica de los agenes y llevar un reloj "step" y gestionar una recolección de datos.
- **NetworkX**: Para trabajar con el Grafo extraido del json y dinamizar los pesos de las aristas y la lógica de las rutas de evacuación.
- **Numpy**: Para los vectors de repusión y atracción de los agentes hacia las salidas y para evitar las paredes o a otros agentes (cuellos de botella).
- **Pantas/matplotlib**: Para visualizar las metricas obtenidas en la simulación.