# Diseño técnico MLSM JSON v2 — Especificación enriquecida

Documento de diseño del modelo de datos **MLSM JSON v2** para representar escenarios indoor de evacuación, integrando geometría espacial, semántica indoor, grafos de conectividad, balizas, peligros programados y configuración inicial de simulación.

La documentación está redactada en español. Las claves JSON, enums, IDs técnicos y nombres de entidades del contrato se mantienen en inglés para facilitar su uso posterior en código, JSON Schema, validadores, `SpatialEngine`, `EvacEngine` y una futura base de datos PostgreSQL/PostGIS.

---

## Índice

- [Diseño técnico MLSM JSON v2 — Especificación enriquecida](#diseño-técnico-mlsm-json-v2--especificación-enriquecida)
  - [Índice](#índice)
  - [Objetivo del documento](#objetivo-del-documento)
  - [Idea general del modelo](#idea-general-del-modelo)
  - [Relación con IndoorGML e IndoorJSON](#relación-con-indoorgml-e-indoorjson)
  - [Relación futura con PostgreSQL/PostGIS](#relación-futura-con-postgresqlpostgis)
  - [JSON canónico y posibles vistas derivadas](#json-canónico-y-posibles-vistas-derivadas)
  - [Arquitectura general](#arquitectura-general)
  - [Entidades raíz](#entidades-raíz)
  - [Sistema de coordenadas y plantas](#sistema-de-coordenadas-y-plantas)
  - [Catálogos](#catálogos)
  - [Elementos físicos: `physical_elements`](#elementos-físicos-physical_elements)
  - [Geometría de autoría y geometría derivada](#geometría-de-autoría-y-geometría-derivada)
  - [Espacios: `spaces`](#espacios-spaces)
  - [Fronteras: `boundaries`](#fronteras-boundaries)
  - [Jerarquía de grafos](#jerarquía-de-grafos)
  - [Grafo de adyacencia: `adjacency_graph`](#grafo-de-adyacencia-adjacency_graph)
  - [Grafo de conectividad: `connectivity_graph`](#grafo-de-conectividad-connectivity_graph)
  - [Grafo puerta a puerta: `door_to_door_graph`](#grafo-puerta-a-puerta-door_to_door_graph)
  - [Grafo de conectividad vertical: `vertical_connectivity_graph`](#grafo-de-conectividad-vertical-vertical_connectivity_graph)
  - [Grafo de rutas en runtime: `routing_graph`](#grafo-de-rutas-en-runtime-routing_graph)
  - [Agentes y puntos de aparición](#agentes-y-puntos-de-aparición)
  - [Balizas: `beacons`](#balizas-beacons)
  - [Peligros: `hazards`](#peligros-hazards)
  - [Configuración inicial de simulación: `simulation`](#configuración-inicial-de-simulación-simulation)
  - [Mapeo conceptual con IndoorJSON](#mapeo-conceptual-con-indoorjson)
  - [Correspondencia orientativa entre MLSM JSON v1 y MLSM JSON v2](#correspondencia-orientativa-entre-mlsm-json-v1-y-mlsm-json-v2)
  - [Validación](#validación)
  - [Límites del documento actual](#límites-del-documento-actual)
  - [Criterios para pasar a implementación](#criterios-para-pasar-a-implementación)
  - [Resumen de decisiones adoptadas](#resumen-de-decisiones-adoptadas)

---

## Objetivo del documento

Este documento define cómo debe organizarse un escenario **MLSM JSON v2**.

El objetivo es establecer una estructura suficientemente clara para que:

* `SpatialEngine` pueda exportar escenarios indoor enriquecidos;
* `EvacEngine` pueda consumir esos escenarios para construir rutas y simulaciones;
* el modelo pueda persistirse más adelante en PostgreSQL/PostGIS;
* el diseño mantenga una relación conceptual con IndoorGML e IndoorJSON;
* las extensiones propias del proyecto, como balizas, peligros programados, agentes y grafos multicapa, queden integradas sin romper la lógica indoor;
* el sistema pueda evolucionar hacia edificios con varias plantas, conexiones verticales, app portable y simulación en tiempo real.

Este documento no implementa código. Define el modelo de datos que guiará las siguientes mejoras.

---

## Idea general del modelo

MLSM JSON v2 se plantea como un **perfil enriquecido inspirado en IndoorGML/IndoorJSON**, pero no como una copia exacta de IndoorJSON.

IndoorJSON aporta una base profesional para representar espacios interiores mediante conceptos como `CellSpace`, `CellBoundary`, `Node`, `Edge`, `PrimalSpaceLayer` y `DualSpaceLayer`.

MLSM JSON v2 mantiene esa filosofía, pero añade elementos que son necesarios para este proyecto:

* elementos físicos editables;
* catálogos de muros, puertas, ventanas, escaleras, rampas, ascensores, balizas y peligros;
* grafos diferenciados para adyacencia, conectividad y evacuación;
* balizas ambientales o de evacuación;
* peligros iniciales o programados;
* puntos de aparición de agentes;
* configuración inicial de simulación;
* compatibilidad futura con PostgreSQL/PostGIS;
* preparación para varias plantas y conexiones verticales.

La idea central es separar tres niveles:

```text
1. Capa de autoría física
   physical_elements

2. Capa espacial semántica o primal
   spaces + boundaries

3. Capa de grafos o dual
   adjacency_graph
   connectivity_graph
   door_to_door_graph
   vertical_connectivity_graph
```

`EvacEngine` no tiene por qué usar todas estas capas directamente. Para calcular rutas puede derivar en tiempo de simulación un `routing_graph`, usando principalmente `door_to_door_graph`, junto con filtros de movilidad, peligros, balizas, congestión y pesos dinámicos.

---

## Relación con IndoorGML e IndoorJSON

MLSM JSON v2 se inspira en IndoorGML e IndoorJSON porque ambos separan el espacio físico interior de su representación topológica o de navegación.

La relación conceptual principal es:

| IndoorJSON / IndoorGML | MLSM JSON v2                             | Comentario                                            |
| ---------------------- | ---------------------------------------- | ----------------------------------------------------- |
| `IndoorFeatures`       | objeto raíz del JSON                     | contenedor del escenario                              |
| `CellSpace`            | `spaces[]`                               | habitaciones, pasillos, puertas, ventanas, obstáculos |
| `CellBoundary`         | `boundaries[]`                           | interfaces entre espacios                             |
| `PrimalSpaceLayer`     | `spaces` + `boundaries`                  | capa espacial primal                                  |
| `DualSpaceLayer`       | `graphs`                                 | capa dual basada en nodos y aristas                   |
| `Node`                 | `graphs.*.nodes[]`                       | nodos de los grafos                                   |
| `Edge`                 | `graphs.*.edges[]`                       | aristas de los grafos                                 |
| `InterLayerConnection` | futuras relaciones entre capas o niveles | útil para conexiones verticales o vistas derivadas    |

El módulo de navegación de IndoorJSON también es relevante:

| IndoorJSON Navigation  | MLSM JSON v2                      | Uso                                              |
| ---------------------- | --------------------------------- | ------------------------------------------------ |
| `NavigableSpace`       | `navigable_space`                 | habitaciones, pasillos y zonas transitables      |
| `TransferSpace`        | `transfer_space`                  | puertas, ventanas, escaleras, rampas, ascensores |
| `ObjectSpace`          | `object_space`                    | columnas, obstáculos o huellas no navegables     |
| `NonNavigableSpace`    | `non_navigable_space`             | zonas interiores no transitables                 |
| `NavigableBoundary`    | `navigable_boundary`              | frontera atravesable                             |
| `NonNavigableBoundary` | `non_navigable_boundary`          | frontera no atravesable                          |
| `Route`                | rutas calculadas por `EvacEngine` | no se almacena como parte fija del escenario     |

MLSM JSON v2 no debe afirmar compatibilidad formal completa con IndoorJSON. Es más correcto decir que es un **perfil propio e inspirado en IndoorJSON**, enriquecido para simulación de evacuación.

---

## Relación futura con PostgreSQL/PostGIS

MLSM JSON v2 se diseña como formato de intercambio y persistencia intermedia. Aunque en esta etapa no se implementa una base de datos, el modelo debe facilitar una futura traducción a PostgreSQL/PostGIS.

Para ello, el diseño prioriza:

* IDs estables para espacios, elementos físicos, fronteras, nodos y aristas;
* geometrías explícitas en `centerline_2d`, `derived_footprint_2d`, `footprint_2d`, `geometry_2d` y `position`;
* sistema de coordenadas definido mediante `crs`;
* separación entre plantas mediante `levels`;
* separación entre `physical_elements`, `spaces`, `boundaries` y `graphs`;
* referencias explícitas entre entidades;
* posibilidad futura de almacenar geometrías como `Point`, `LineString`, `Polygon`, `PolygonZ` o geometrías derivadas.

El objetivo no es implementar PostGIS todavía, sino evitar que el diseño del JSON bloquee esa evolución.

Una futura base de datos podría tener tablas conceptuales como:

```text
buildings
levels
physical_elements
spaces
boundaries
graph_nodes
graph_edges
beacons
hazards
agent_spawns
simulation_configs
```

El JSON debe ser suficientemente ordenado para alimentar esa estructura sin rediseñar todo desde cero.

---

## JSON canónico y posibles vistas derivadas

MLSM JSON v2 se define inicialmente como un **JSON canónico completo**.

En este contexto, “canónico” significa que ese archivo es la **fuente principal de verdad** del escenario. Contiene toda la información necesaria para reconstruir el modelo indoor:

* elementos físicos;
* espacios;
* fronteras;
* grafos;
* balizas;
* peligros;
* agentes o puntos de aparición;
* configuración inicial de simulación;
* mapeo conceptual con IndoorJSON.

El enfoque principal será, por tanto:

```text
Un escenario MLSM JSON v2 = un archivo completo y autocontenido.
```

Más adelante, a partir de ese JSON canónico, podrían generarse vistas derivadas:

* un JSON solo espacial con `physical_elements`, `spaces` y `boundaries`;
* un JSON solo de grafos;
* un JSON de balizas y coberturas;
* un JSON de configuración de simulación;
* un JSON más próximo a IndoorJSON puro junto con otro JSON de extensiones MLSM;
* una importación a PostgreSQL/PostGIS.

Estas vistas no son necesarias para el producto mínimo actual. Se dejan como posibilidad futura.

---

## Arquitectura general

La estructura conceptual adoptada es:

```text
physical_elements
  ↓
spaces / boundaries
  ↓
adjacency_graph
  ↓
connectivity_graph
  ↓
door_to_door_graph
  ↓
EvacEngine runtime routing_graph
```

También existe un grafo adicional para conexiones entre plantas:

```text
vertical_connectivity_graph
```

La lectura conceptual es:

1. `physical_elements` guarda lo que se dibuja o edita en `SpatialEngine`.
2. `spaces` y `boundaries` representan el modelo espacial semántico.
3. `adjacency_graph` captura contactos físicos, geométricos o topológicos.
4. `connectivity_graph` captura conexiones reales mediante canales.
5. `door_to_door_graph` representa la base principal para rutas de evacuación.
6. `vertical_connectivity_graph` representa conexiones entre plantas.
7. `EvacEngine` deriva en runtime un `routing_graph` con pesos y restricciones dinámicas.

---

## Entidades raíz

La estructura raíz recomendada es:

```json
{
  "schema_version": "2.0.0",
  "metadata": {},
  "crs": {},
  "levels": [],
  "catalogs": {},
  "physical_elements": [],
  "spaces": [],
  "boundaries": [],
  "graphs": {},
  "agent_spawns": [],
  "agents": [],
  "beacons": [],
  "hazards": [],
  "simulation": {},
  "indoorjson_mapping": {}
}
```

Descripción general:

| Campo                | Función                                |
| -------------------- | -------------------------------------- |
| `schema_version`     | versión técnica del modelo JSON        |
| `metadata`           | información general del escenario      |
| `crs`                | sistema de coordenadas                 |
| `levels`             | plantas o niveles del edificio         |
| `catalogs`           | tipos reutilizables                    |
| `physical_elements`  | elementos dibujados o editables        |
| `spaces`             | espacios semánticos                    |
| `boundaries`         | fronteras entre espacios               |
| `graphs`             | grafos derivados o semánticos          |
| `agent_spawns`       | puntos de aparición de agentes         |
| `agents`             | agentes concretos opcionales           |
| `beacons`            | balizas o sensores                     |
| `hazards`            | peligros iniciales o programados       |
| `simulation`         | configuración inicial de simulación    |
| `indoorjson_mapping` | trazabilidad conceptual con IndoorJSON |

---

## Sistema de coordenadas y plantas

Todas las plantas deben compartir el mismo sistema XY local del edificio.

Esto es importante porque permite que una escalera, rampa o ascensor mantenga coherencia entre plantas. Si una escalera se encuentra en una posición `(x, y)` en planta baja, debe conservar esa posición horizontal en las plantas que conecta.

Ejemplo de `crs`:

```json
{
  "crs": {
    "type": "local",
    "srid": 0,
    "unit": "meters",
    "origin": {
      "x": 0,
      "y": 0,
      "z": 0
    },
    "description": "Sistema de coordenadas local del edificio"
  }
}
```

Ejemplo de `levels`:

```json
{
  "levels": [
    {
      "level_id": "LEVEL_00",
      "name": "Planta baja",
      "floor_index": 0,
      "floor_z": 0.0,
      "ceiling_z": 3.0,
      "height_m": 3.0
    },
    {
      "level_id": "LEVEL_01",
      "name": "Primera planta",
      "floor_index": 1,
      "floor_z": 3.0,
      "ceiling_z": 6.0,
      "height_m": 3.0
    }
  ]
}
```

Para el desarrollo actual, la geometría principal será 2D. La coordenada Z aparece mediante `levels` y puede usarse posteriormente para extender el modelo a 2.5D o 3D.

---

## Catálogos

`catalogs` define tipos reutilizables.

Sirve para que `SpatialEngine` no tenga que repetir toda la información cada vez que dibuja un muro, una puerta o una ventana. Un elemento concreto referencia un tipo de catálogo mediante `catalog_ref` y solo añade `overrides` si necesita sobrescribir algo.

Ejemplo:

```json
{
  "catalogs": {
    "wall_types": [
      {
        "catalog_id": "WALL_INTERIOR_15CM",
        "element_type": "wall",
        "default_thickness_m": 0.15,
        "default_height_m": 3.0,
        "material": "generic",
        "description": "Muro interior estándar"
      }
    ],
    "door_types": [
      {
        "catalog_id": "DOOR_SINGLE_90CM",
        "element_type": "door",
        "default_width_m": 0.90,
        "default_height_m": 2.10,
        "description": "Puerta simple estándar"
      }
    ],
    "window_types": [],
    "stair_types": [],
    "ramp_types": [],
    "elevator_types": [],
    "beacon_types": [],
    "hazard_types": []
  }
}
```

Regla general:

```text
catalogs = tipos reutilizables
physical_elements = instancias concretas
overrides = excepciones locales
geometry = siempre propia del elemento concreto
```

---

## Elementos físicos: `physical_elements`

`physical_elements` representa lo que se dibuja o edita en `SpatialEngine`.

Aquí entran:

* muros;
* puertas;
* ventanas;
* columnas;
* escaleras;
* rampas;
* ascensores;
* otros elementos constructivos;
* eventualmente balizas físicas si se decide integrarlas como elementos colocables.

Un muro puede dibujarse como una línea, pero almacenarse con grosor, altura y huella derivada:

```json
{
  "element_id": "PE_WALL_001",
  "element_type": "wall",
  "level_id": "LEVEL_00",
  "catalog_ref": "WALL_INTERIOR_15CM",
  "centerline_2d": {
    "type": "LineString",
    "coordinates": [[0, 0], [5, 0]]
  },
  "derived_footprint_2d": {
    "type": "Polygon",
    "coordinates": [[[0, -0.075], [5, -0.075], [5, 0.075], [0, 0.075], [0, -0.075]]]
  },
  "overrides": {}
}
```

Esta separación permite que `SpatialEngine` conserve información editable, mientras que `EvacEngine` puede usar las huellas derivadas como obstáculos, límites o referencias espaciales.

---
## Geometría de autoría y geometría derivada

MLSM JSON v2 diferencia entre la geometría que se dibuja o introduce en `SpatialEngine` y la geometría que puede derivarse, detectarse o verificarse automáticamente después.

La geometría de autoría es la forma simple que el usuario dibuja o define:

* muros como líneas o polilíneas con grosor;
* puertas, ventanas y salidas como puntos ancla o marcas lineales asociadas a un muro hospedador;
* columnas como puntos con tamaño, círculos, rectángulos o polígonos;
* habitaciones y pasillos como polígonos;
* escaleras, rampas y ascensores como footprints con entradas/salidas;
* balizas como puntos o dispositivos asociados a un espacio o elemento físico;
* hazards como puntos, áreas iniciales o eventos definidos externamente.

La geometría derivada es la que se calcula o completa a partir de esa información:

* `derived_footprint_2d` de muros, puertas, ventanas, columnas y obstáculos;
* `spaces` derivados, corregidos o enriquecidos;
* `boundaries` entre espacios, transfer spaces, object spaces y elementos físicos;
* nodos y aristas de los grafos;
* áreas de influencia de balizas;
* zonas afectadas por hazards.

Esta separación permite que `SpatialEngine` sea cómodo de usar, pero que el JSON final conserve información suficiente para simulación, validación, visualización y futura persistencia en PostgreSQL/PostGIS.

Puertas, ventanas y salidas pueden definirse en la fase de autoría como puntos ancla o marcas lineales asociadas a un muro hospedador, junto con atributos como ancho, tipo y catálogo. A partir de esa definición ligera, el sistema puede derivar posteriormente su footprint 2D, el `transfer_space` asociado, las `boundaries` navegables o no navegables y las conexiones de grafo.

Las `boundaries` no son normalmente geometría de autoría primaria. Se generan, detectan o verifican después de derivar las geometrías físicas y espaciales, analizando contactos entre `spaces`, `transfer_spaces`, `object_spaces` y elementos físicos con footprint.

Para simulación, los agentes no deben depender únicamente de las `boundaries` como líneas. La colisión y evitación deben basarse principalmente en footprints físicos, `object_spaces`, muros, columnas, obstáculos y otras geometrías derivadas. Las `boundaries` sirven para representar interfaces, contactos, pasos y restricciones topológicas.

---

## Espacios: `spaces`

`spaces` representa espacios semánticos del modelo indoor.

No solo incluye habitaciones y pasillos. También puede incluir puertas, ventanas, escaleras, rampas, ascensores y obstáculos cuando se modelan como espacios con significado.

Tipos principales:

| `space_type`          | Uso                                              |
| --------------------- | ------------------------------------------------ |
| `navigable_space`     | habitaciones, pasillos, zonas transitables       |
| `transfer_space`      | puertas, ventanas, escaleras, rampas, ascensores |
| `exit_space`          | salidas de evacuación                            |
| `object_space`        | columnas, obstáculos o huellas no navegables     |
| `non_navigable_space` | zonas interiores no transitables                 |

Ejemplo de habitación:

```json
{
  "space_id": "SPACE_ROOM_001",
  "space_type": "navigable_space",
  "category": "room",
  "level_id": "LEVEL_00",
  "name": "Habitación 001",
  "centroid_2d": {
    "type": "Point",
    "coordinates": [2.0, 2.0]
  },
  "footprint_2d": {
    "type": "Polygon",
    "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]]
  },
  "attributes": {
    "locomotion": ["walking", "rolling"],
    "accessible": true
  }
}
```

Ejemplo de puerta como espacio de transferencia:

```json
{
  "space_id": "SPACE_DOOR_001",
  "space_type": "transfer_space",
  "category": "door_space",
  "level_id": "LEVEL_00",
  "name": "Puerta 001",
  "physical_element_ref": "PE_DOOR_001",
  "attributes": {
    "locomotion": ["walking", "rolling"],
    "accessible": true
  }
}
```

La decisión importante es que una puerta puede existir simultáneamente como:

```text
physical_element → objeto físico dibujado
transfer_space   → espacio de paso
boundary         → interfaz atravesable con otro espacio
graph node/edge  → elemento de navegación
```

Esto no se considera redundancia negativa. Es una representación multicapa de la misma realidad.

---

## Fronteras: `boundaries`

`boundaries` representa interfaces geométricas reales entre entidades espaciales o físicas.

En 2D se almacenan normalmente como `LineString`. En una evolución 3D podrían almacenarse como superficies o caras. Su función no es sustituir a los muros, puertas, columnas u obstáculos, sino describir el contacto o interfaz entre entidades.

Ejemplos:

```text
Room 1 ↔ Door 1          = navigable_boundary
Door 1 ↔ Corridor        = navigable_boundary
Room 1 ↔ Wall/Object     = non_navigable_boundary
Room 1 ↔ Window          = opening_boundary / non_evacuation_boundary
Room 1 ↔ Room 2          = contact_boundary, si existe contacto sin paso
Level 0 ↔ Level 1        = vertical_contact_boundary, si existe contacto suelo/techo
```

Una `boundary` puede derivarse automáticamente, detectarse por contacto geométrico o ser corregida manualmente si el modelo lo requiere.

Ejemplo:

```json
{
  "boundary_id": "BOUNDARY_ROOM_DOOR_001",
  "boundary_type": "navigable_boundary",
  "level_id": "LEVEL_00",
  "source_ref": {
    "entity_type": "space",
    "entity_id": "SPACE_ROOM_001"
  },
  "target_ref": {
    "entity_type": "space",
    "entity_id": "SPACE_DOOR_001"
  },
  "geometry_2d": {
    "type": "LineString",
    "coordinates": [[4, 1.5], [4, 2.5]]
  },
  "attributes": {
    "traversable": true,
    "bidirectional": true,
    "derived": true,
    "derivation_source": "geometry_contact"
  }
}
```

Este bloque es clave para mantener coherencia con IndoorGML/IndoorJSON, donde `CellBoundary` permite representar interfaces entre `CellSpace`. En MLSM JSON v2 se permite extender esta idea para cubrir también contactos con `object_spaces`, `transfer_spaces` y elementos físicos derivados.

---

## Jerarquía de grafos

MLSM JSON v2 adopta una jerarquía de grafos:

```text
adjacency_graph
  ↓
connectivity_graph
  ↓
door_to_door_graph
  ↓
routing_graph runtime en EvacEngine
```

Y añade:

```text
vertical_connectivity_graph
```

para conexiones entre plantas.

Esta jerarquía evita mezclar conceptos:

| Grafo                         | Pregunta que responde                                     |
| ----------------------------- | --------------------------------------------------------- |
| `adjacency_graph`             | ¿Qué toca qué?                                            |
| `connectivity_graph`          | ¿Qué está conectado mediante un canal real?               |
| `door_to_door_graph`          | ¿Cómo se mueve una persona entre puntos de paso?          |
| `vertical_connectivity_graph` | ¿Cómo se conectan distintas plantas?                      |
| `routing_graph`               | ¿Qué ruta calcula EvacEngine en esta simulación concreta? |

---
## Grafo de adyacencia: `adjacency_graph`

`adjacency_graph` representa contactos físicos, geométricos o topológicos entre entidades del modelo.

Puede construirse a partir de `boundaries`, relaciones de contacto, intersección, contención o proximidad controlada entre entidades espaciales y físicas. No tiene que depender exclusivamente de un cálculo automático: puede generarse, verificarse o corregirse como parte del proceso de exportación del JSON.

Incluye contactos atravesables y no atravesables:

* habitación con puerta;
* habitación con muro;
* habitación con ventana;
* habitación con otra habitación;
* habitación con object space u obstáculo interior;
* espacio inferior/superior por suelo o techo;
* posibles contactos entre espacios sin paso.

El grafo de adyacencia no significa que exista paso. Solo indica relación espacial o física.

Si se quiere una adyacencia física extendida, `adjacency_graph` puede incluir nodos que representen no solo `spaces`, sino también elementos físicos relevantes, como muros, puertas, ventanas, columnas u object spaces. Esto puede ser útil para visualización, validación geométrica, análisis espacial y futura persistencia en PostgreSQL/PostGIS.

Ejemplo de relación de adyacencia entre habitación y puerta:

```json
{
  "edge_id": "EDGE_ADJ_ROOM_DOOR_001",
  "source_node_id": "NODE_ROOM_001",
  "target_node_id": "NODE_DOOR_001",
  "relationship_type": "contact_via_boundary",
  "boundary_ref": "BOUNDARY_ROOM_DOOR_001"
}
```

Ejemplo de relación de adyacencia física extendida entre habitación y muro:

```json
{
  "edge_id": "EDGE_ADJ_ROOM_WALL_001",
  "source_node_id": "NODE_ROOM_001",
  "target_node_id": "NODE_WALL_001",
  "relationship_type": "contact_with_physical_element",
  "physical_element_ref": "PE_WALL_001",
  "traversable": false
}
```

Por tanto:

```text
adjacency_graph = qué toca qué
connectivity_graph = por dónde se puede pasar o intercambiar flujo
door_to_door_graph = cómo se mueve una persona entre puntos de paso
routing_graph = grafo operativo que EvacEngine deriva en runtime
```

---

## Grafo de conectividad: `connectivity_graph`

`connectivity_graph` representa conexiones reales mediante canales de paso o intercambio.

Parte de las relaciones detectadas en `adjacency_graph`, pero filtra y transforma esas relaciones según puertas, ventanas, huecos, salidas, escaleras, rampas, ascensores o conductos.

En su forma detallada, debe poder representar conexiones mediante `transfer_space` explícitos:

```text
Room 1 → Door 1 → Corridor
Room 2 → Door 2 → Corridor
Corridor → Exit
```

Esto permite conservar información importante:

* qué puerta, hueco o ventana produce la conexión;
* qué perfiles de movilidad pueden atravesarla;
* qué anchura, capacidad o peso base tiene;
* qué balizas, peligros o restricciones pueden afectarla;
* si existen varios canales alternativos entre los mismos espacios.

A partir de este grafo puede derivarse una vista más simple de conectividad entre espacios:

```text
Room 1 ↔ Corridor
Room 2 ↔ Corridor
Corridor ↔ Exit
```

Esa vista simplificada puede ser útil para visualización, análisis rápido o consultas en base de datos, pero no debe sustituir al grafo detallado cuando se necesite simular evacuación o calcular rutas con restricciones.

---

## Grafo puerta a puerta: `door_to_door_graph`

`door_to_door_graph` representa el movimiento entre puntos de paso.

Sus nodos principales son:

* puertas;
* salidas;
* entradas a escaleras;
* salidas de escaleras;
* rampas;
* ascensores;
* puntos de transferencia relevantes.

Ejemplo conceptual:

```text
Door 1 → Door 2
Door 2 → Exit
Door 2 → Stair Entry
```

Este grafo es la base principal para el cálculo de rutas de evacuación.

A diferencia de `connectivity_graph`, no se centra en conectar habitaciones con puertas, sino en representar cómo una persona se desplaza entre puntos de paso una vez dentro de la red navegable.

`EvacEngine` debe usar principalmente este grafo como base para construir rutas, aplicar pesos y recalcular trayectorias.

---

## Grafo de conectividad vertical: `vertical_connectivity_graph`

`vertical_connectivity_graph` representa conexiones entre plantas.

Incluye:

* escaleras;
* rampas;
* ascensores;
* posibles conexiones verticales especiales.

Debe respetar el sistema XY común del edificio.

Ejemplo conceptual:

```text
Stair Entry L0 → Stair Exit L1
Ramp Entry L0 → Ramp Exit L1
Elevator L0 → Elevator L1
```

Una escalera puede representarse como:

```text
physical_element
transfer_space
vertical connection
graph edge
```

En una primera versión de una sola planta, este grafo puede estar vacío, pero debe existir para que el modelo no bloquee la evolución a edificios con varios niveles.

---

## Grafo de rutas en runtime: `routing_graph`

`routing_graph` no se almacena como grafo principal del escenario.

Es una estructura derivada en tiempo de simulación por `EvacEngine`.

Se construye a partir de:

* `door_to_door_graph`;
* `connectivity_graph`;
* `vertical_connectivity_graph`;
* perfil de movilidad del agente;
* estado de peligros;
* lecturas o influencia de balizas;
* congestión;
* pesos dinámicos.

Esto permite que el mismo escenario genere rutas distintas según:

* tipo de agente;
* estado del peligro;
* lectura de balizas;
* tiempo de simulación;
* congestión;
* algoritmo de evacuación usado.

Por tanto:

```text
JSON MLSM v2 = escenario base
routing_graph = grafo operativo de simulación
```

---

## Agentes y puntos de aparición

`agent_spawns` define ubicaciones desde las cuales pueden generarse agentes.

No representa necesariamente agentes concretos.

Ejemplo:

```json
{
  "spawn_id": "SPAWN_ROOM_001",
  "level_id": "LEVEL_00",
  "space_ref": "SPACE_ROOM_001",
  "position": {
    "type": "Point",
    "coordinates": [2.0, 2.0]
  },
  "capacity": 20,
  "allowed_profiles": ["walking", "rolling"]
}
```

`agents` puede usarse si se quieren definir agentes concretos:

```json
{
  "agent_id": "AGENT_001",
  "spawn_ref": "SPAWN_ROOM_001",
  "profile": "walking",
  "initial_position": {
    "type": "Point",
    "coordinates": [2.0, 2.0]
  }
}
```

La idea es que `SpatialEngine` pueda definir puntos de aparición, mientras que `EvacEngine` decida cuántos agentes crear, qué perfiles usar y cómo simularlos.

---

## Balizas: `beacons`

`beacons` representa balizas, sensores o dispositivos colocados en el entorno.

Una baliza debe almacenar:

* identificador;
* planta;
* posición;
* elemento o espacio al que está asociada;
* tipo de sensores;
* modelo de influencia;
* espacios, nodos o aristas afectadas.

Ejemplo:

```json
{
  "beacon_id": "BEACON_001",
  "level_id": "LEVEL_00",
  "beacon_type": "environmental_beacon",
  "position": {
    "type": "Point",
    "coordinates": [5.0, 2.0]
  },
  "attached_to": {
    "type": "physical_element",
    "ref": "PE_WALL_001"
  },
  "sensor_types": ["temperature", "smoke", "co"],
  "influence": {
    "model": "radius",
    "radius_m": 4.0,
    "coverage_type": "circular"
  },
  "affects": {
    "mode": "manual_or_computed",
    "space_refs": ["SPACE_ROOM_001"],
    "node_refs": [],
    "edge_refs": [],
    "graph_refs": ["door_to_door_graph"]
  }
}
```

Las balizas no calculan rutas por sí solas. Su información puede alimentar un servicio posterior que genere lecturas simuladas o reales. Después, `EvacEngine` podrá traducir esas lecturas en pesos dinámicos, penalizaciones, bloqueos o recomendaciones de ruta.

---

## Peligros: `hazards`

`hazards` representa peligros iniciales o programados dentro del escenario.

Este bloque es opcional y puede estar vacío. Si el escenario no define ningún peligro, `EvacEngine` o un servicio externo de simulación de balizas/peligros podrá introducirlos durante la ejecución.

No representa el historial de lo ocurrido durante una simulación. La evolución real del peligro, las lecturas de balizas, los cambios de pesos y los eventos ocurridos deben almacenarse como salidas de simulación o como flujos externos.

Ejemplo de peligro programado:

```json
{
  "hazard_id": "HAZARD_FIRE_001",
  "hazard_type": "fire",
  "level_id": "LEVEL_00",
  "initial_position": {
    "type": "Point",
    "coordinates": [6.0, 2.0]
  },
  "activation": {
    "mode": "scheduled",
    "start_step": 120
  },
  "growth_model": {
    "type": "linear_radius",
    "initial_radius_m": 0.5,
    "radius_per_step": 0.02,
    "max_radius_m": 4.0
  },
  "severity": 0.8
}
```

Esto permite simular escenarios donde el peligro no existe desde el inicio, sino que aparece tras cierto tiempo. También permite dejar el escenario limpio y delegar la aparición/evolución del peligro a un servicio externo que genere lecturas de balizas o eventos ambientales.


---

## Configuración inicial de simulación: `simulation`

`simulation` contiene parámetros iniciales de simulación.

No debe contener resultados.

Ejemplo:

```json
{
  "simulation": {
    "random_seed": 42,
    "time_step_s": 1.0,
    "max_steps": 1000,
    "routing": {
      "source_graph": "door_to_door_graph",
      "use_dynamic_weights": true,
      "use_beacon_risk": true,
      "use_hazard_risk": true,
      "use_congestion": true
    },
    "population": {
      "mode": "from_agent_spawns",
      "default_profile": "walking",
      "default_count": 30
    }
  }
}
```

Los resultados de simulación deberán almacenarse aparte, por ejemplo:

```text
metrics.csv
agent_trajectories.csv
route_changes.csv
beacon_readings.csv
hazard_events.json
graph_weights_over_time.csv
```

La estructura exacta de resultados se definirá cuando `EvacEngine` esté más estabilizado.

---

## Mapeo conceptual con IndoorJSON

`indoorjson_mapping` sirve para documentar la relación conceptual con IndoorJSON.

No significa que el archivo sea IndoorJSON formal.

Ejemplo:

```json
{
  "indoorjson_mapping": {
    "core_mapping": {
      "spaces": "CellSpace",
      "boundaries": "CellBoundary",
      "graphs.nodes": "Node",
      "graphs.edges": "Edge"
    },
    "navigation_mapping": {
      "navigable_space": "NavigableSpace",
      "transfer_space": "TransferSpace",
      "object_space": "ObjectSpace",
      "navigable_boundary": "NavigableBoundary",
      "non_navigable_boundary": "NonNavigableBoundary"
    },
    "mlsm_extensions": [
      "physical_elements",
      "catalogs",
      "beacons",
      "hazards",
      "agent_spawns",
      "simulation",
      "door_to_door_graph"
    ]
  }
}
```

Este bloque ayuda a justificar académicamente el modelo, dejando claro qué partes se inspiran en IndoorJSON y qué partes son extensiones propias.

---

## Correspondencia orientativa entre MLSM JSON v1 y MLSM JSON v2

Esta tabla no implica que sea obligatorio crear un migrador completo. Sirve como referencia para no perder conceptos del JSON actual y para orientar futuras conversiones manuales o automáticas.

| MLSM JSON v1                                | MLSM JSON v2                  | Comentario                                 |
| ------------------------------------------- | ----------------------------- | ------------------------------------------ |
| `configuracion.ancho`, `configuracion.alto` | `levels[0].spatial_extent_2d` | extensión del escenario                    |
| `espacios_navegables`                       | `spaces[]`                    | requiere normalizar tipos y geometría      |
| `muros`                                     | `physical_elements[]`         | con `catalog_ref` y `derived_footprint_2d` |
| `conexiones_horizontales.adyacencia_fisica` | `adjacency_graph`             | contacto físico/topológico                 |
| `conexiones_horizontales.navegable_puerta`  | `connectivity_graph`          | conectividad mediante puertas/huecos       |
| `conexiones_horizontales.door_to_door`      | `door_to_door_graph`          | base principal de rutas                    |
| `conexiones_verticales`                     | `vertical_connectivity_graph` | futuras plantas                            |
| `agentesspawn`                              | `agent_spawns[]`              | pasar de coordenadas a objetos             |
| implícito                                   | `boundaries[]`                | derivado de relaciones espaciales          |
| inexistente                                 | `beacons[]`                   | extensión MLSM                             |
| inexistente                                 | `hazards[]`                   | extensión MLSM                             |
| inexistente                                 | `simulation`                  | configuración inicial                      |

MLSM JSON v1 quedará obsoleto progresivamente, pero esta correspondencia ayuda a mantener continuidad con el baseline actual.

---

## Validación

JSON Schema puede validar:

* existencia de campos obligatorios;
* tipos de datos;
* enums;
* estructura general;
* formatos básicos de geometría;
* presencia de grafos esperados;
* estructura de balizas, hazards y agentes.

Sin embargo, JSON Schema no es suficiente para validar toda la lógica espacial.

Validaciones futuras deberán comprobar:

* que los IDs referenciados existen;
* que los polígonos son válidos;
* que no hay espacios mal solapados;
* que las fronteras coinciden con los espacios que conectan;
* que las puertas están ubicadas sobre muros o fronteras coherentes;
* que las aristas apuntan a nodos existentes;
* que los grafos son conexos cuando corresponde;
* que las escaleras, rampas o ascensores conectan plantas correctas;
* que la cobertura de balizas afecta realmente a espacios/aristas existentes.

Estas validaciones pueden implementarse después mediante scripts auxiliares.

---

## Límites del documento actual

Este documento no implementa todavía:

* exportación desde `SpatialEngine`;
* lectura directa desde `EvacEngine`;
* base de datos PostgreSQL/PostGIS;
* `PolyhedralSurfaceZ`;
* aplicación móvil;
* interfaz Qt;
* simulación real de balizas;
* propagación física avanzada de fuego o humo;
* validadores topológicos completos;
* optimización de rendimiento.

Estas partes son relevantes para el proyecto, pero se abordarán después de estabilizar el modelo de datos.

---

## Criterios para pasar a implementación

El diseño puede considerarse suficientemente estable para empezar la implementación cuando:

* el documento de diseño esté revisado;
* los ejemplos JSON representen correctamente el modelo;
* el JSON Schema valide los ejemplos;
* el ejemplo mínimo represente correctamente la lógica `Space → TransferSpace → Space`;
* el ejemplo rico incluya espacios, elementos físicos, grafos, balizas, hazards y configuración inicial;
* `door_to_door_graph` quede claramente definido como base principal para evacuación;
* `routing_graph` quede claramente definido como estructura derivada en runtime;
* no haya cambios pendientes en `src/` ni en `baseline/`.

Una vez cumplido esto, el siguiente paso lógico será implementar la exportación MLSM JSON v2 desde `SpatialEngine`.

---

## Resumen de decisiones adoptadas

* MLSM JSON v2 será un perfil propio inspirado en IndoorJSON, no IndoorJSON puro.
* Se usará un JSON canónico completo como fuente principal de verdad.
* Las posibles vistas separadas o JSON derivados se dejan para más adelante.
* `physical_elements` conserva lo dibujado/editable.
* `spaces` y `boundaries` representan el modelo espacial primal.
* `graphs` representa el modelo dual y las capas de conectividad.
* `adjacency_graph` representa contactos, no paso.
* `connectivity_graph` representa canales reales de conexión.
* `door_to_door_graph` será la base principal de rutas de evacuación.
* `vertical_connectivity_graph` prepara el modelo para varias plantas.
* `routing_graph` se deriva en runtime dentro de `EvacEngine`.
* `beacons` y `hazards` son extensiones MLSM.
* Los resultados de simulación no pertenecen al JSON de escenario.
* El diseño debe facilitar una futura persistencia PostgreSQL/PostGIS.
