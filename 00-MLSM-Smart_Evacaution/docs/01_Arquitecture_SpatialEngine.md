# Arquitectura del Motor Espacial (MLSM_SpatialEngine)

## 1. Visión Macro del Sistema (Top-Down Architecture)
El `MLSM_SpatialEngine` no es una simple herramienta de dibujo; es un motor de Autoría CAD y procesamiento geométrico. Su objetivo es abstraer la complejidad del diseño arquitectónico y generar un Modelo Espacial Multicapa (MLSM) estandarizado. El sistema opera como un *pipeline* (tubería de datos) secuencial dividido en 5 macroprocesos:

1. **Interfaz y Captura de Eventos (UI/UX):** Actúa como el *Front-End*. Escucha clics, movimientos del ratón y atajos de teclado, proyectando coordenadas discretas (Snap a la cuadrícula) en un lienzo interactivo continuo.
2. **Motor Geométrico (CSG - Constructive Solid Geometry):** Procesa las líneas 1D dibujadas por el usuario y las extruye a polígonos 2D basados en constantes paramétricas (grosores BIM). Ejecuta operaciones booleanas matemáticas para garantizar que los muros sólidos y las puertas no se superpongan físicamente.
3. **Inferencia Topológica (El Cerebro Espacial):** Analiza la geometría generada para inferir relaciones lógicas. Aplica algoritmos de intersección con tolerancias dinámicas para descubrir qué habitaciones están adyacentes y generar la red de navegación (NavMesh).
4. **Enriquecimiento Semántico (IndoorGML):** Etiqueta las geometrías y grafos con metadatos de accesibilidad (ej. *Walking*, *Step*) y categoriza los espacios (*Room*, *Transition*), preparando el entorno para agentes con inteligencias asimétricas.
5. **Serialización y Enrutamiento (Exportación):** Actúa como el *Back-End*. Empaqueta las 3 capas (Física, Topológica y Semántica) y las inyecta en un esquema de datos jerárquico (`.json`), guardándolas automáticamente de forma segura en el repositorio del proyecto.

> **💡 Sugerencia Visual para la Memoria del TFG:** > *Incluir aquí un Diagrama de Flujo Horizontal (Pipeline) que muestre cómo el dato en bruto (Clic del usuario) pasa por las cajas de "Shapely (CSG)", "Inferencia Topológica" y acaba en el "JSON Export".*

## 2. Ecosistema de Librerías (Justificación Técnica)
El motor delega las operaciones complejas en librerías científicas probadas en la industria, garantizando eficiencia computacional y precisión matemática:

* `matplotlib`: Funciona como el "Motor Gráfico" interactivo. No se usa para graficar datos estáticos, sino que se explota su API orientada a objetos (`FigureCanvas`) para capturar eventos de hardware (`button_press_event`, `motion_notify_event`) y renderizar *patches* (polígonos) a 60 FPS durante la edición.
* `shapely`: El corazón matemático del motor (Geometría Computacional). Se encarga de tres tareas críticas imposibles de realizar eficientemente a mano:
  * **Cortes Booleanos (`difference`):** Resta el volumen de las puertas al volumen de los muros.
  * **Intersección Tolerante (`buffer` e `intersection`):** Infla las habitaciones milimétricamente para detectar adyacencias reales, calculando áreas de choque para descartar falsos positivos (roces de esquinas).
  * **Cálculo de Masas (`centroid`):** Encuentra el centro de gravedad exacto de polígonos irregulares para ubicar los nodos del grafo.
* `numpy`: Acelerador algebraico. Se utiliza para el cálculo de álgebra lineal, específicamente para hallar hipotenusas (`np.hypot`) y normalizar vectores perpendiculares necesarios para extruir el grosor de los muros a partir de una línea directriz 1D.
* `json` y `os`: Gestores de I/O (Input/Output). Estructuran la complejidad espacial en diccionarios anidados legibles por máquinas y manejan el sistema de archivos del sistema operativo para enrutar los "Bakeos" (horneados) a la carpeta `./escenarios/` de forma autónoma.

> **💡 Sugerencia Visual para la Memoria del TFG:** > *Incluir un Diagrama de Venn o un gráfico de capas técnicas donde el usuario está arriba interactuando con Matplotlib, y Matplotlib se comunica por debajo con Numpy y Shapely.*

## 3. Desglose Arquitectónico por Fases

### Fase 1: Inicialización, Parametrización BIM y Máquina de Estados
El motor no comienza dibujando, sino estableciendo las "leyes de la física" y preparando la memoria de datos estructurados. El método `__init__` actúa como el gestor de la Máquina de Estados del editor.

#### 1.1. Parametrización Física y Prevención de "Magic Numbers"
A diferencia de un editor gráfico tradicional, el `SpatialEngine` es una herramienta paramétrica. No se definen coordenadas de rectángulos absolutos, sino ejes 1D que son extruidos matemáticamente.
Para ello, se declaran los diccionarios `GROSORES` y `ANCHOS_PUERTA` en la inicialización. Esto garantiza:
* **Escalabilidad:** Modificar el grosor de un muro exterior afecta universalmente a todo el procesamiento de Shapely y a las exportaciones JSON sin necesidad de buscar en el código interno.
* **Constantes Globales:** La Mejora `self.RADIO_AGENTE = 0.25` estandariza el volumen físico del agente antes de la simulación, sirviendo de ancla de calibración entre el *SpatialEngine* y el *EvacEngine*.

#### 1.2. Separación de Geometría, Topología y Semántica
La inicialización evidencia cómo el motor almacena el espacio en tres niveles de abstracción:
* **CSG (Muros):** La lista `self.muros` almacena los datos en bruto para la Operación Booleana final.
* **Nodos y Bounds (Topología):** `self.hitos` guarda los centroides matemáticos (puntos 2D), mientras que `self.hitos_bounds` guarda su contorno (polígono real) para las pruebas de intersección.
* **IndoorGML (Semántica):** El diccionario `self.propiedades_zonas` inyecta en paralelo los metadatos de accesibilidad (ej. *Locomotion: [Walking, Rolling]*).

#### 1.3. Algoritmo de Restricción Magnética (Snapping Vectorial)
Uno de los problemas clásicos de la edición espacial 2D es que el usuario dibuje una puerta ligeramente desalineada del muro, lo que provocaría fugas (leaks) en el motor de físicas de la simulación o fallos en la detección de *Raycasting*. 
Para solucionarlo, el motor implementa la función `obtener_muro_cercano(px, py)`:

1. **Proyección por Producto Escalar:** Cuando el usuario intenta colocar una puerta, el motor calcula la distancia perpendicular desde el puntero del ratón a todos los segmentos de muro activos.
2. **Clamp (Límites de Segmento):** Utiliza una función de límite `max(0, min(1, t))` sobre el vector normalizado para evitar que la puerta se "pegue" a una pared en el espacio vacío más allá de los extremos reales del muro.
3. **Bloqueo Direccional (Rail Vector):** Al encontrar un muro válido (<0.5m de distancia), la función devuelve la posición corregida exacta sobre la línea directriz del muro y su `mejor_vector` (vector normalizado).
4. **Consecuencia de Diseño:** El método `on_move` consume este vector para bloquear el ratón a un "riel" unidimensional. Esto asegura matemáticamente que la puerta comparta el 100% de la orientación y posición colineal de su muro anfitrión, permitiendo que la operación booleana posterior de *Shapely* sea infalible al hacer el hueco.

> (💡 Sugerencia Visual para esta sección: Quedaría espectacular si pones un pequeño esquema o  donde se vea un punto P (ratón) proyectándose perpendicularmente hacia un segmento AB (muro), formando el punto P' con una línea punteada).

### Fase 2: Construcción Dinámica (Event Loop y Renderizado UI)
El motor delega la interactividad en un *Event Loop* acoplado al backend de Matplotlib. Las funciones `on_move` y `on_click` conforman el ciclo de vida de la geometría, separando la intención del usuario de la consolidación de los datos.

#### 2.1. Cuantización Espacial (Grid Snapping)
Todo evento de coordenada (`event.xdata`, `event.ydata`) es interceptado y filtrado por una función de redondeo `round(x * 2) / 2`. Esto fuerza la cuantización del espacio a intervalos de 0.5 metros.
* **Justificación Matemática:** En geometría computacional, comparar flotantes (ej. `10.00001 == 10.0`) genera fallos críticos. Al forzar una cuadrícula perfecta, aseguramos que dos habitaciones vecinas compartan vértices idénticos a nivel binario, garantizando que Shapely no interprete fisuras microscópicas entre muros.

#### 2.2. Feedback Visual y Restricción Continua (`on_move`)
La función `on_move` no altera el modelo de datos subyacente (`self.muros` o `self.hitos_bounds`); su objetivo es exclusivamente el cálculo en tiempo real de *Patches* visuales.
Implementa un patrón de **Extrusión al Vuelo**: 
1. Transforma el segmento originado por el primer clic y la posición del ratón en un polígono (la sombra).
2. Si la herramienta es una puerta, ejecuta la proyección vectorial parametrizada (descrita en la Fase 1), anulando el movimiento libre del ratón y deslizándolo por el riel del muro anfitrión.

> **💡 Sugerencia Visual para la Memoria:** > *Mostrar tres *screenshots* secuenciales de la herramienta Habitaciones: 1) Dos clics hechos (solo la línea). 2) Ratón moviéndose al tercer punto (se ve el polígono semi-transparente verde cerrándose dinámicamente). 3) Doble clic final (polígono consolidado con su Centroide y Etiqueta de Locomoción).*

#### 2.3. Cierre Poligonal y Cálculo de Centroides (`on_click`)
Cuando el usuario consolida la geometría (clic en herramientas lineales o doble-clic en herramientas poligonales libres), el motor transfiere la memoria temporal (`self.puntos_temp`) a las estructuras permanentes:
* **Generación de Nodos Topológicos:** A diferencia de una simple *Bounding Box* que fallaría en habitaciones en forma de 'L', el motor coge los vértices dibujados, instancia un `ShapelyPolygon` en la memoria RAM de manera efímera, y usa su propiedad `.centroid`. Esto garantiza que el nodo lógico para el algoritmo de Dijkstra se coloque siempre en el centro de gravedad geométrico del espacio.
* **Inyección Semántica:** En el momento exacto del cierre, el motor captura el estado global de la interfaz (`self.locomotion_actual`, modificable mediante teclas numéricas 1,2,3) y lo sella herméticamente dentro del diccionario del objeto recién creado.

#### 2.4. Gestión de Deshacer (Stack Management)
La función `on_key` actúa como un despachador de comandos (Command Pattern). La pulsación de la tecla `z` implementa un sistema LIFO (*Last In, First Out*). Simplemente hace `pop()` en la lista activa correspondiente (`self.muros` o `self.hitos_bounds`) e invalida el diccionario semántico anidado, obligando al método de renderizado (`dibujar_interfaz`) a repintar el lienzo desde cero sin dejar geometría "fantasma".

### Fase 3: Motor de Geometría Booleana y Topología Multicapa
El núcleo duro del `MLSM_SpatialEngine` reside en su capacidad para transformar dibujos de usuario en entornos aptos para Inteligencia Artificial. Esto se logra separando el análisis en dos motores independientes: el Físico (CSG) y el Topológico (Grafos).

#### 3.1. Operaciones Booleanas Geométricas (CSG)
En simulación física, superponer el polígono de una puerta sobre un muro no elimina el muro subyacente; el agente colisionaría con una barrera invisible. La función `procesar_geometria_booleana` soluciona esto aplicando *Constructive Solid Geometry*.
1. **Agrupación Sustractiva (`unary_union`):** Todas las geometrías clasificadas como puertas se fusionan en un único bloque monolítico. Esta optimización previene problemas de cálculo si el usuario dibuja dos puertas superpuestas entre sí.
2. **Extracción (`difference`):** Se aplica el operador matemático de diferencia (`Muro - Puertas`). 
3. **Manejo de Fragmentación (`MultiPolygon`):** Si una puerta biseca un muro (lo corta de lado a lado), la función detecta la creación de un `MultiPolygon` y lo subdivide en partes discretas (ej. `Muro_1_part0` y `Muro_1_part1`). Así, el simulador final recibe polígonos cóncavos o múltiples perfectos, sin necesidad de calcular colisiones complejas en tiempo de ejecución.

> **💡 Sugerencia Visual:** > *Añadir un esquema de Operación Booleana: Mostrar un Rectángulo Gris (Muro) cruzado por un Rectángulo Naranja (Puerta), seguido del operador matemático "-" y el resultado: un Muro partido en dos con un hueco en medio.*

#### 3.2. Inferencia Topológica MLSM (El Cerebro)
La función `calcular_conexiones` es la responsable de generar el *Multi-Layered Space Model* (MLSM). No requiere que el usuario dibuje las líneas de ruta; el motor las deduce analizando la proximidad física mediante la inflación de polígonos (`buffer(0.15)`).

Genera tres capas de enrutamiento simultáneas:
* **Grafo Macro (Adyacencia Física - Dorado):** Conecta habitaciones colindantes. Aplica un filtro absoluto (`interseccion.area > 0.05`) para descartar que dos habitaciones se conecten por tocarse solo en una esquina matemática.
* **Grafo Meso (Navegabilidad - Cyan):** Conecta el centroide de la habitación con las puertas/salidas/fronteras que pertenecen a ella.
* **Grafo Micro (Door-to-Door - Magenta):** Conecta todas las puertas de una misma habitación entre sí.

#### 3.3. Solución a "Corner Cases" (Filtro de Área Relativa)
Un reto crítico en la topología automática es evitar que fronteras virtuales o puertas exteriores, al rozar sutilmente la esquina inflada de una habitación adyacente, generen enlaces corruptos (atravesando paredes). 
El motor mitiga esto desechando el cálculo de área absoluto y aplicando un **Umbral de Intersección Relativa**:
```python
if interseccion.area > (poly_pta.area * 0.30):
```
Solo se generará la conexión topológica si la burbuja de la habitación envuelve al menos el 30% de la masa total de la puerta. Esto garantiza que las conexiones Door-to-Door (Grafo Micro) sean topológicamente puras y seguras para los agentes, ignorando vectores radiantes y ángulos ciegos.

> 💡 Sugerencia Visual: > Añadir el "Multi-Layered Space Model Graph": Un gráfico isométrico 3D donde la capa base sea el plano 2D, la capa de en medio tenga los nodos de habitaciones, y la capa superior tenga el grafo detallado.ç### Fase 4: Serialización y Enrutamiento (Exportación de Datos)
La fase final del ciclo de vida del `MLSM_SpatialEngine` consiste en empaquetar la abstracción matemática generada en un formato interoperable, estrictamente validado por el esquema `MLSM_Core.schema.json`.

#### 4.1. El Perfil MLSM Core (`exportar_mlsm_core`)
El motor no exporta un simple volcado de memoria, sino que ensambla un "Contrato de Datos" estructurado en motores de ejecución lógicos para el simulador:
* **Físicas:** Separa los muros booleanos (`muros_recortados`) en un array puro de colisionadores estáticos.
* **Topología:** Inyecta directamente las listas de diccionarios de `calcular_conexiones` en la sección de `conexiones_horizontales`.
* **Semántica:** Mapea las áreas de los hitos en el diccionario de `espacios_navegables`, asegurando que cada nodo contenga su centroide y sus etiquetas de `locomotion`.

#### 4.2. Generación Dinámica de InterLayerConnections
En el estándar de modelado multicapa, los diferentes grafos deben vincularse verticalmente. La función `exportar_mlsm_core` genera esta capa automáticamente basándose en la `clase_indoor` de la zona:
* Si la zona es un `NavigableSpace` (Habitación), el motor asume su existencia simultánea en la red Macro (`adyacencia_fisica`) y Meso (`navegable_puerta`), inyectando un vínculo `representa_el_mismo_espacio`.
* Si la zona es un `TransferSpace` o `AnchorSpace` (Puertas/Salidas), se vincula desde la capa Meso a la Micro (`door_to_door`).
Esto exime al usuario de tener que definir relaciones verticales a mano, garantizando un grafo 3D jerárquicamente perfecto para que el algoritmo de Dijkstra del `EvacEngine` pueda saltar de capa.

> **💡 Sugerencia Visual:** > *Añadir un árbol jerárquico tipo JSON (JSON Tree Diagram) mostrando cómo la raíz se divide limpiamente en "muros", "espacios_navegables", "conexiones_horizontales" y "conexiones_verticales".*

#### 4.3. Validación Visual Pre-Exportación
La función `verificar_visual_y_exportar` detiene el hilo de ejecución principal de Python (`plt.show()`) antes de grabar en el disco. Renderiza la malla CSG final, superpone el NavMesh multicapa y proyecta los radios de colisión (`RADIO_AGENTE`) a escala real. Esta auditoría visual garantiza que el usuario pueda detectar anomalías (como un *raycast* o un recoveco inaccesible) antes de alimentar el motor de simulaciones.

#### 4.4. Automatización del Sistema de Archivos
Utilizando la librería `os`, el motor desacopla la ubicación de ejecución del script del destino de los datos (`os.makedirs("escenarios", exist_ok=True)`). Esto asegura que los *assets* generados pueblen automáticamente las carpetas correctas de la arquitectura del repositorio de GitHub, sin importar en qué terminal o sistema operativo se ejecute la herramienta.