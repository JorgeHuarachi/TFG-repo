# Arquitectura del Motor de Simulación (MLSM_EvacEngine)

## 1. Visión Macro del Sistema (Top-Down Architecture)
El motor de simulación está diseñado utilizando un patrón de Modelado Basado en Agentes (ABM). El código se estructura en 5 grandes bloques funcionales que operan en cascada:

1. **Configuración Global (Físicas y Constantes):** Define las reglas inmutables del universo (radios de colisión, fuerza de repulsión de los muros, umbrales de velocidad).
2. **Sistema de Métricas (`GestorDatos`):** Un observador pasivo que registra eventos críticos (reálculos, cruce de puertas, evacuaciones) en memoria para su posterior exportación masiva.
3. **El Entorno (`ModeloAvanzado`):** Es el "tablero de juego". Se encarga de leer la topología (JSON), construir el grafo matemático (`networkx`), instanciar el espacio continuo y gestionar eventos globales como la propagación del fuego o la congestión dinámica.
4. **La Entidad (`AgentePro`):** La unidad de inteligencia. Contiene tres sub-sistemas:
    * *Cerebro (Pathfinding):* Calcula rutas multicapa usando Dijkstra.
    * *Ojos (Visión):* Detecta atajos geométricos y encadena objetivos en tiempo real.
    * *Cuerpo (Steering):* Traduce la intención mental en vectores físicos, gestionando inercias, colisiones y frenado dinámico.
5. **Bucle de Renderizado (Matplotlib):** El ciclo de vida visual que actualiza el modelo en cada *frame* (30 fps) y dibuja el estado actual del espacio.

## 2. Ecosistema de Librerías (Justificación Técnica)
El motor se apoya en librerías científicas y matemáticas de Python, cada una con un rol estrictamente definido:
* `mesa`: Framework central. Proporciona la clase `Agent`, el `Model` y el `ContinuousSpace` que gestiona las posiciones espaciales.
* `networkx`: Motor matemático para la topología. Transforma las conexiones JSON en un grafo y resuelve el enrutamiento mediante el algoritmo de Dijkstra.
* `numpy`: Motor físico. Utilizado intensivamente para cálculo vectorial (distancias euclidianas, normalización de fuerzas y productos escalares para ángulos de giro).
* `shapely`: Motor geométrico. Fundamental para calcular distancias exactas a los bordes de los muros (`Polygon`), líneas de visión (`LineString`) y detección de zonas semánticas.
* `pandas`: Estructuración de datos. Convierte los miles de registros en memoria en un DataFrame optimizado para exportar a `.csv`.
* `matplotlib`: Motor de renderizado 2D y animación en tiempo real.
* `json` & `os`: Lectura del modelo espacial externo y resolución de rutas dinámicas de archivos.

## 3. Desglose Arquitectónico por Fases

### Fase 1: El Universo y sus Leyes (Configuración y `ModeloAvanzado`)
El motor arranca estableciendo un entorno determinista. Se compone de dos bloques principales:

#### 1.1. Constantes Físicas Globales
En lugar de codificar los valores en las funciones ("Hardcoding"), las leyes físicas se declaran en la cabecera del script. Esto garantiza la coherencia escalar de la simulación:
* **Separación Cuerpo-Aura:** `RADIO_FISICO` dicta las colisiones "duras" (evita que dos agentes ocupen el mismo espacio en una puerta), mientras `RADIO_PERSONAL` dicta la repulsión "suave" (la distancia social en pasillos abiertos).
* **Dominancia de Barreras:** `FUERZA_PARED` (4.0) se configura deliberadamente más alta que la fuerza motriz del agente. Esto evita el conocido bug del "Tunneling", donde una multitud empuja a un individuo a través de una pared sólida.

#### 1.2. Construcción del Entorno (Multi-Layer Spatial Model)
La clase `ModeloAvanzado` actúa como el "Dios" de la simulación. En su inicialización (`__init__`), traduce el archivo JSON a un entorno vivo mediante tres capas:
1. **Capa Geométrica (Espacio Continuo):** Extrae los muros físicos y los convierte en polígonos de Shapely (`self.poligonos_muros`) para calcular colisiones precisas.
2. **Capa Topológica (Grafo):** Instancia `self.grafo_logico` usando NetworkX. Los centroides geométricos de las habitaciones se convierten en los nodos (hitos) matemáticos por los que discurrirá el algoritmo de Dijkstra.
3. **Capa Semántica (Restricciones):** El modelo no espera a que un agente en silla de ruedas pregunte si puede usar unas escaleras. Pre-calcula la lista `poligonos_prohibidos_rolling`. Si una línea visual interseca estos polígonos, la topología se rompe virtualmente para ese perfil, optimizando el rendimiento de cálculo en cada fotograma.

*(Nota visual: Se recomienda acompañar esta sección con un Diagrama de Capas que muestre la superposición del plano 2D, el grafo de nodos y los metadatos semánticos).*
### Fase 2: El Agente: Fisiología y Memoria (`__init__` y Perfiles)
Al instanciar la clase `AgentePro`, el sistema no genera clones genéricos. Se implementa una diversidad fisiológica y una arquitectura "Mente-Cuerpo" fundamental para el realismo de la simulación.

#### 2.1. Diversidad Demográfica
Se asigna una etiqueta de perfil (`Walking`, `Rolling`, `Elderly`) que altera inmediatamente la variable `velocidad_base`. Esto permite simular asimetrías de flujo reales, donde agentes rápidos (Walking) deben esquivar o esperar a agentes con movilidad reducida (Elderly), generando turbulencias de fluido realistas en los pasillos.

#### 2.2. Desacoplamiento Mente-Cuerpo
La inicialización evidencia una separación clara de responsabilidades:
* **El Cuerpo (Vectores):** Controla atributos puramente físicos como `velocidad_actual` y `posiciones_recientes` (memoria muscular a corto plazo para detectar atascos).
* **La Mente (Semántica):** Mantiene la ruta no solo como coordenadas, sino como conceptos (`plan_maestro_nombres`). Esto permite al agente saber si el punto geométrico al que se dirige representa una puerta estrecha o el centro de un aula abierta.

#### 2.3. Fundamentos de Inercia
A diferencia de los simuladores basados en rejilla (Grid-based), nuestro motor pre-asigna variables de estado inercial (`frames_transicion` y `destino_previo`). Esto garantiza que, desde el primer frame, el agente tenga memoria posicional y no dependa exclusivamente de su posición actual para calcular su próxima rotación, permitiendo curvas parabólicas fluidas.

*(Sugerencia visual: Añadir un Diagrama de Clases UML que muestre a `AgentePro` heredando de `mesa.Agent`, separando sus atributos en bloques de Fisiología, Mente y Física).*

### Fase 3: El Cerebro y los Ojos (Método `step` y Visión)
El método `step` actúa como el bucle cognitivo de la entidad. Se ejecuta una vez por fotograma y está diseñado para separar estrictamente la "Toma de Decisiones" (Cerebro/Ojos) de la "Ejecución" (Músculos/Física). 

Esta fase resuelve dos problemas clásicos del *Pathfinding* en simulaciones continuas:

#### 3.1. Reevaluación Dinámica (El Cerebro)
El agente no es esclavo de su ruta inicial. Mediante el flag `necesita_recalcular`, el sistema puede inducir "amnesia táctica" si ocurre un evento disruptivo global (como la instanciación de un fuego). Esto fuerza al agente a borrar su `plan_maestro` y volver a consultar la topología de `networkx` en el siguiente frame, logrando un comportamiento de evacuación adaptable en tiempo real.

#### 3.2. Bloqueo de Enfoque (Focus Lock)
En simulaciones estándar, los agentes suelen "cortar esquinas" (Corner-Cutting) al ver su siguiente objetivo a través de la apertura de una puerta, lo que provoca colisiones irreales contra el marco. 
Para mitigarlo, el motor implementa una **Conciencia Semántica del Objetivo**: Si el string del nodo actual contiene la palabra `'Puerta'`, el motor suspende temporalmente el escaneo de Raycast (`tiene_linea_vision`). El agente es obligado a mantener la mirada fija en el umbral hasta que su cuerpo físico cruce el plano geométrico del muro.

#### 3.3. Encadenamiento Visual (Target Chaining)
Cuando el agente camina hacia un nodo virtual (como el centro geométrico de una sala grande) y su Raycast detecta la siguiente puerta, se activa la lógica de encadenamiento:
1. **Atajo Geométrico:** Se elimina el centro virtual del array de objetivos.
2. **Preservación de Inercia (Hands on Wheel):** Si el agente estaba caminando recto, activa la inercia (`frames_transicion = MAX`). Sin embargo, si el agente *ya estaba ejecutando una curva* al momento de ver la puerta, **el cronómetro de inercia no se reinicia**. Simplemente se actualiza el `destino_actual`. Esto permite que el motor de físicas (`mover_pro`) adapte la trayectoria existente al nuevo vector de forma parabólica, eliminando los "volantazos robóticos" y logrando trazadas 100% orgánicas.

*(Sugerencia visual: Añadir un árbol de comportamiento (Behavior Tree) que mapee el flujo condicional desde el chequeo del fuego hasta la resolución de la línea de visión).*

### Fase 4: Cinemática, Volante Dinámico y Frenado (`mover_pro`)
El motor de movimiento prescinde de cuadrículas (grids) y utiliza un sistema de simulación continua basado en *Steering Behaviors*. Calcula la posición del agente sumando vectores de atracción (meta) y repulsión (muros/multitud).

#### 4.1. Semántica del Terreno (Speed Limit)
El espacio no es homogéneo. Antes de aplicar fuerzas vectoriales, el agente comprueba si pisa un polígono etiquetado semánticamente (Ej: `'locomotion': 'Step'`). Si intersecta unas escaleras, su `limite_velocidad` máximo es degradado al 40%. Esta limitación es dinámica y se levanta inmediatamente al volver a terreno llano.

#### 4.2. Volante Dinámico y Freno Inercial Escalonado
Para evitar que los agentes derrapen contra los muros exteriores en las curvas cerradas (Overshooting), el motor calcula en tiempo real el ángulo del desvío mediante el producto escalar (`dot_giro`).
* **Conciencia Espacial:** Si el siguiente objetivo está a menos de 2 metros, la sensibilidad del "volante" se duplica, permitiendo al agente pivotar ágilmente en espacios estrechos.
* **Freno Automático:** Si el ángulo de giro es superior a 30º, la velocidad máxima permitida se reduce progresivamente (hasta caer al 30% en giros agudos). A medida que el agente estabiliza la trazada (`dot_giro` se acerca a 1), el freno inercial se libera de forma orgánica.

#### 4.3. Tolerancia de Llegada (Cruce de Umbrales)
Se elimina el bug del "Waypoint Popping" modificando adaptativamente el radio de precisión. Las puertas exigen una precisión de 0.25m (radio de colisión duro) para forzar el paso central. Sin embargo, en caso de aglomeraciones masivas o puertas dobles, se implementa una solución geométrica: Si un agente es desplazado a un lateral, pero su distancia al *siguiente* nodo ya es menor que la de la propia puerta al nodo, el sistema considera que "ha cruzado el plano arquitectónico" del muro y actualiza su destino, eliminando los atascos residuales.

#### 4.4. Fuerzas de Repulsión e Integración
La posición final se calcula mediante la función de decaimiento exponencial (`np.exp(-dist)`). 
* La repulsión de los muros es dominante (`FUERZA_PARED = 4.0`), asegurando que ningún empujón de la multitud (`FUERZA_MAXIMA = 2.0`) logre un *glitch* que introduzca a un agente en la geometría estática. 
* El sistema inyecta ruido estocástico microscópico a la fuerza social, introduciendo entropía en las masas atascadas para desestabilizar formaciones cristalinas perfectas ("Desempate Simétrico").

*(Sugerencia visual: Incluir un diagrama de suma vectorial mostrando la interacción entre el vector de inercia previa, la atracción de la puerta, y la repulsión tangencial del muro).*