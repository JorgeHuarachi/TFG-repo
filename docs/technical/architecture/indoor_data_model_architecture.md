# Indoor Data Model — Arquitectura y especificación conceptual

**Estado:** documento canónico de arquitectura para la nueva línea de trabajo del TFG.  
**Ámbito:** modelo de datos indoor, separación entre modelo espacial y escenarios de simulación, compatibilidad conceptual con IndoorGML/IndoorJSON y transición desde los prototipos MLSM v1/v2.  
**Idioma:** español para documentación; claves JSON, IDs técnicos, nombres de clases y enums principales en inglés técnico por compatibilidad con código, schemas e IndoorJSON.  

---

## 1. Objetivo del documento

Este documento define la arquitectura objetivo del nuevo **Indoor Data Model** del proyecto.

Su finalidad es sustituir la idea anterior de un `mlsm_json_v2` monolítico por un sistema más claro, más fiel a IndoorGML/IndoorJSON y más fácil de mantener:

```text
indoor_data_model
├── indoor_model.json      → modelo espacial/topológico indoor
├── scenario_model.json    → condiciones de simulación y overlays
└── project_manifest.json  → opcional, coordinación de archivos
```

La decisión principal es que **SpatialEngine debe exportar solo el modelo espacial/topológico**. Agentes, balizas, peligros, configuración de simulación y resultados no forman parte del modelo espacial base; deben vivir en un archivo de escenario o en salidas de simulación.

Este documento no es simplemente una lista de cambios sobre el prototipo actual. Es el documento de referencia al que acudir para responder preguntas como:

- qué es un `CellSpace` en este proyecto;
- cómo se representan habitaciones, puertas, ventanas, muros, columnas y salidas;
- qué pertenece al modelo primal y qué pertenece al dual;
- qué debe exportar SpatialEngine y qué no;
- cómo se relaciona el modelo con IndoorGML/IndoorJSON;
- qué queda como legado de MLSM v1/v2;
- cómo deben coordinarse los datos espaciales con los escenarios de evacuación;
- qué implicaciones tiene todo esto para schemas, visualizador, EvacEngine y PostGIS.

---

## 2. Por qué se abandona `mlsm_json_v2` como contrato principal

El prototipo `mlsm_json_v2` fue útil para explorar rápidamente muchas necesidades:

- geometría indoor;
- muros, puertas, espacios y boundaries;
- grafos de adyacencia, conectividad y evacuación;
- agentes;
- balizas;
- hazards;
- configuración de simulación;
- mapeo conceptual con IndoorJSON.

Sin embargo, al crecer, ese formato empezó a mezclar responsabilidades distintas dentro de un único JSON. Esto genera varios problemas:

1. **El edificio deja de ser reutilizable.**  
   Si el mismo archivo contiene también población, balizas, hazards y configuración de simulación, cada experimento obliga a duplicar o modificar el modelo espacial.

2. **SpatialEngine asume demasiadas responsabilidades.**  
   SpatialEngine debería encargarse de modelar el espacio interior, no de decidir cuántos agentes existen, qué hazard aparece en qué instante o cómo se ponderan rutas dinámicas.

3. **La compatibilidad con IndoorGML/IndoorJSON se diluye.**  
   IndoorGML se basa en espacios celulares, primal/dual y capas temáticas. Un JSON plano con `physical_elements`, `spaces`, `boundaries`, `graphs`, `agents`, `beacons` y `simulation` se aleja de esa estructura.

4. **La validación se complica.**  
   Un único schema grande mezcla reglas geométricas, topológicas, dinámicas y de simulación. Es más difícil saber qué parte falla y qué herramienta es responsable.

5. **La evolución hacia PostGIS y Qt se vuelve más difícil.**  
   La base de datos y la UI se benefician de una separación clara entre autoría, modelo espacial, escenarios y resultados.

Por tanto, `mlsm_json_v2` queda definido como **formato transicional / prototipo enriquecido**, no como contrato principal futuro.

La nueva línea se denomina:

```text
indoor_data_model
```

Y su archivo espacial principal se denomina:

```text
indoor_model.json
```

---

## 3. Principios de diseño

El nuevo modelo sigue estos principios.

### 3.1. Separación de responsabilidades

```text
SpatialEngine → indoor_model.json
Scenario/Simulation tools → scenario_model.json
EvacEngine → resultados, rutas y métricas
```

SpatialEngine no debe exportar agentes, beacons, hazards ni configuraciones de simulación. Puede visualizar o usar información auxiliar durante la autoría, pero el modelo espacial final debe estar limpio.

### 3.2. Cercanía estructural a IndoorJSON

El archivo `indoor_model.json` debe parecerse lo máximo razonable a IndoorJSON:

```text
IndoorFeatures
└── layers[]
    └── ThematicLayer
        ├── primalSpace
        │   ├── cellSpaceMember[]
        │   └── cellBoundaryMember[]
        └── dualSpace
            ├── nodeMember[]
            └── edgeMember[]
```

No se exige compatibilidad formal absoluta desde el primer momento, pero la estructura debe permitir una conversión razonable a IndoorJSON estricta.

### 3.3. Modelo espacial como fuente de verdad

El `indoor_model.json` es la fuente de verdad para:

- geometría espacial;
- semántica de espacios;
- boundaries;
- relaciones primal/dual;
- IDs estables;
- referencias que usarán otros archivos.

### 3.4. Escenarios como overlays dependientes

`scenario_model.json` no redefine el edificio. Solo referencia el `indoor_model.json` y añade información variable:

- población;
- agentes;
- balizas;
- hazards;
- configuración de simulación.

### 3.5. Trazabilidad de autoría sin contaminar el primal

La geometría que el usuario dibuja en SpatialEngine es importante para editar, depurar y regenerar el modelo. Pero no debe confundirse con el modelo primal final.

Por eso se permite una sección opcional:

```text
authoringGeometry / sourceFeatures
```

pero el núcleo del modelo indoor son `CellSpace`, `CellBoundary`, `Node` y `Edge`.

### 3.6. IDs estables desde el inicio

Los overlays, EvacEngine, el visualizador y PostGIS dependerán de IDs estables. No basta con nombres visibles de UI como `Habitacion_1` o `Puerta_simple_3`.

---

## 4. Fuentes normativas y documentos de referencia

La arquitectura se basa en los siguientes recursos:

### 4.1. OGC IndoorGML 2.0 Part 1 — Conceptual Model

Documento oficial OGC 22-045r5. Define el modelo conceptual de IndoorGML 2.0.

Ideas clave usadas en este proyecto:

- IndoorGML es un estándar centrado en espacios interiores y relaciones topológicas.
- El core model se basa en `PrimalSpace`, `DualSpace` e `InterLayerConnection`.
- La navegación es una extensión semántica sobre el core.
- Las celdas de un mismo primal space layer no deben solaparse.
- El dual space representa nodos y aristas derivados por dualidad de CellSpaces y CellBoundaries.
- Un modelo válido puede contener geometría, red geométrica, red lógica o combinaciones.
- Las thematic layers permiten representar distintos modelos celulares para el mismo espacio físico.

### 4.2. IndoorJSON Core schema

Define la estructura JSON de conceptos core:

- `IndoorFeatures`;
- `ThematicLayer`;
- `PrimalSpaceLayer`;
- `CellSpace`;
- `CellBoundary`;
- `DualSpaceLayer`;
- `Node`;
- `Edge`;
- `InterLayerConnection`.

### 4.3. IndoorJSON Navigation schema

Define especializaciones para navegación:

- `NavigableSpace`;
- `NonNavigableSpace`;
- `GeneralSpace`;
- `TransferSpace`;
- `ObjectSpace`;
- `NavigableBoundary`;
- `NonNavigableBoundary`;
- `Route`.

### 4.4. IndoorJSON dummy oficial

El dummy oficial muestra una estructura mínima con:

```text
IndoorFeatures
└── layers[0]
    └── ThematicLayer
        ├── primalSpace
        │   ├── cellSpaceMember: C1, C2
        │   └── cellBoundaryMember: B1
        └── dualSpace
            ├── nodeMember: N1, N2
            └── edgeMember: E1
```

Ese ejemplo es especialmente importante porque muestra la relación de dualidad:

```text
CellSpace C1 ↔ Node N1
CellSpace C2 ↔ Node N2
CellBoundary B1 ↔ Edge E1
```

El nuevo `indoor_model.json` debe seguir esa filosofía.

### 4.5. Prototipos del proyecto

Se consideran como material transicional:

- `mlsm_json_v2_design.md`;
- `mlsm_json_v2.schema.json`;
- `MLSM_SpatialEngine.py`;
- `visualize_mlsm_v2.py`;
- JSONs generados por SpatialEngine.

Estos archivos no son la arquitectura final, pero contienen decisiones útiles que se reutilizan.

---

## 5. Glosario mínimo

### Indoor Data Model

Nombre paraguas del nuevo sistema de datos. Incluye `indoor_model.json`, `scenario_model.json`, schemas, documentación y flujos de validación.

### indoor_model.json

Archivo espacial/topológico exportado por SpatialEngine. Contiene el modelo indoor, cercano a IndoorJSON.

### scenario_model.json

Archivo dependiente del `indoor_model.json`. Contiene población, beacons, hazards y configuración de simulación.

### CellSpace

Unidad básica de espacio indoor en el modelo primal. En 2D se representa normalmente mediante una superficie/polígono.

### CellBoundary

Interfaz o límite de uno o varios CellSpaces. En 2D se representa normalmente mediante una línea.

### PrimalSpaceLayer

Contenedor de CellSpaces y CellBoundaries de una capa temática.

### DualSpaceLayer

Red dual formada por Nodes y Edges que abstraen CellSpaces y CellBoundaries.

### NavigableSpace

CellSpace por el que se puede transitar.

### GeneralSpace

Subtipo de NavigableSpace. Representa estancias, aulas, laboratorios, pasillos, vestíbulos o zonas en las que una persona puede permanecer o moverse.

### TransferSpace

Subtipo de NavigableSpace. Representa espacios de transición entre otros espacios: puertas, ventanas practicables, salidas, conectores verticales, entradas a escalera, rampas, ascensores.

### NonNavigableSpace

CellSpace no transitable por una persona en el escenario de navegación considerado. Puede representar muros, slabs, zonas bloqueadas, mobiliario o restricciones.

### ObjectSpace

Subtipo de NonNavigableSpace que aporta detalle cuando el espacio no navegable está ocupado por objetos: columnas, mobiliario, obstáculos.

### NavigableBoundary

CellBoundary atravesable o que permite conexión.

### NonNavigableBoundary

CellBoundary no atravesable.

### Route

Resultado de una consulta o cálculo de ruta. No es el grafo base exportado por SpatialEngine.

---

## 6. Separación entre modelo espacial y escenario de simulación

La separación central del nuevo sistema es:

```text
indoor_model.json
  modelo relativamente estable del edificio

scenario_model.json
  estado experimental o de simulación sobre ese edificio
```

### 6.1. indoor_model.json

Contiene:

- estructura IndoorFeatures-like;
- niveles del edificio;
- thematic layers;
- primal space;
- dual space;
- CellSpaces;
- CellBoundaries;
- Nodes;
- Edges;
- authoring/source features opcionales;
- mapping con IndoorJSON;
- metadatos;
- CRS.

No contiene:

- agentes concretos;
- spawns;
- beacons activos;
- peligros;
- pesos dinámicos;
- configuración de simulación;
- resultados.

### 6.2. scenario_model.json

Contiene:

- referencia al `indoor_model.json`;
- población;
- spawns;
- perfiles de agentes;
- beacons;
- hazards;
- configuración de simulación;
- parámetros de routing;
- opciones de salida.

No debe redefinir geometría del edificio salvo que se trate explícitamente de un overlay temporal.

### 6.3. Ventajas

- Un edificio puede usarse en muchos escenarios.
- Se evita duplicar geometría.
- Es más sencillo validar cada archivo.
- EvacEngine puede ejecutar varias simulaciones sobre el mismo modelo espacial.
- PostGIS puede separar entidades espaciales estables de eventos dinámicos.
- La documentación y los schemas son más comprensibles.

### 6.4. Riesgo de separación excesiva

Separar demasiado pronto en muchos archivos puede complicar el TFG. Por eso no se empieza con seis archivos independientes. La decisión inicial es:

```text
indoor_model.json
scenario_model.json
project_manifest.json opcional
```

---

## 7. Archivos del sistema

### 7.1. `indoor_model.json`

Archivo principal exportado por SpatialEngine.

Debe ser reutilizable y relativamente estable. Cambia cuando se modifica el edificio, no cuando cambia la simulación.

### 7.2. `scenario_model.json`

Archivo de escenario experimental. Puede haber muchos escenarios para un mismo `indoor_model.json`.

Ejemplos:

```text
scenario_daytime_100_agents.json
scenario_fire_room_01.json
scenario_beacon_failure.json
scenario_accessibility_rolling.json
```

### 7.3. `project_manifest.json`

Opcional. Solo se vuelve necesario cuando hay:

- varios escenarios para un mismo edificio;
- rutas relativas complejas;
- múltiples carpetas de resultados;
- necesidad de checksums;
- comparación sistemática de experimentos.

No debe ser obligatorio en la primera iteración.

---

## 8. `indoor_model.json`

### 8.1. Propósito

`indoor_model.json` representa el edificio como modelo espacial/topológico.

Es el equivalente operativo del modelo IndoorGML/IndoorJSON adaptado al TFG.

### 8.2. Qué contiene

- `id`;
- `featureType: "IndoorFeatures"`;
- `metadata`;
- `crs`;
- `levels`;
- `layers`;
- `layerConnections` opcional;
- `sourceFeatures` o `authoringGeometry` opcional;
- `indoorDataModel` metadata opcional.

### 8.3. Qué no contiene

- `agent_spawns`;
- `agents`;
- `beacons`;
- `hazards`;
- `simulation`;
- resultados;
- rutas calculadas.

### 8.4. Estructura raíz propuesta

```json
{
  "id": "IF_BUILDING_001",
  "featureType": "IndoorFeatures",
  "metadata": {
    "name": "building_001",
    "description": "Indoor model exported from SpatialEngine",
    "createdAt": "2026-01-01T00:00:00Z",
    "generator": "SpatialEngine"
  },
  "crs": {
    "type": "local",
    "unit": "meters",
    "origin": {"x": 0, "y": 0, "z": 0}
  },
  "levels": [],
  "layers": [],
  "layerConnections": [],
  "sourceFeatures": [],
  "indoorDataModel": {
    "modelName": "indoor_data_model",
    "modelVersion": "0.1-draft",
    "compatibility": "IndoorJSON-like profile"
  }
}
```

### 8.5. Compatibilidad con IndoorJSON

El bloque `IndoorFeatures`, `layers`, `ThematicLayer`, `primalSpace` y `dualSpace` debe seguir de cerca el dummy oficial.

Las extensiones propias deben añadirse de forma controlada, sin romper la lectura conceptual:

```text
core IndoorJSON-like structure first
project extensions second
```

---

## 9. ThematicLayer

IndoorGML permite organizar un mismo entorno en distintas capas temáticas.

Para el TFG, la capa principal será:

```text
TopographicNavigationLayer
```

Representa la subdivisión física/navegable del edificio.

Ejemplo conceptual:

```json
{
  "id": "TL_NAV_L00",
  "featureType": "ThematicLayer",
  "semanticExtension": true,
  "theme": "Physical",
  "name": "Navigation layer level 00",
  "level": "LEVEL_00",
  "primalSpace": {},
  "dualSpace": {}
}
```

### 9.1. Una capa por planta o una capa por edificio

Hay dos posibilidades:

#### Opción A: una capa por planta

```text
TL_NAV_LEVEL_00
TL_NAV_LEVEL_01
```

Ventajas:

- más fácil de visualizar;
- más fácil de depurar;
- cada planta tiene su primal/dual propio;
- encaja con flujos 2D.

Inconvenientes:

- se necesitan `InterLayerConnection` para escaleras, rampas y ascensores.

#### Opción B: una capa para todo el edificio

Ventajas:

- más simple conceptualmente para edificios pequeños;
- menos capas.

Inconvenientes:

- peor para visualización 2D por planta;
- conexiones verticales más difíciles de aislar.

### Decisión inicial

Para este TFG se recomienda:

```text
una ThematicLayer principal por planta
```

Y usar `InterLayerConnection` para conectar nodos/celdas entre plantas más adelante.

---

## 10. PrimalSpaceLayer

### 10.1. Propósito

`PrimalSpaceLayer` contiene:

```text
cellSpaceMember[]
cellBoundaryMember[]
```

Es la representación espacial del nivel.

### 10.2. Regla de no solape

Los CellSpaces de un mismo PrimalSpaceLayer no deben solaparse.

Esto tiene consecuencias importantes:

- si una habitación contiene una columna modelada como `ObjectSpace` en la misma capa, la geometría navegable de la habitación debe recortarse;
- si no se quiere hacer ese recorte aún, la columna puede representarse en otra ThematicLayer y conectarse mediante `InterLayerConnection`;
- los muros representados como `NonNavigableSpace` no deberían solaparse con GeneralSpaces;
- las puertas como TransferSpace tampoco deberían solaparse mal con habitaciones; deben compartir boundaries.

### 10.3. Implicación para SpatialEngine

Los polígonos dibujados actualmente como habitaciones en `self.hitos_bounds` son geometría de autoría o footprints iniciales, no necesariamente CellSpaces finales.

El CellSpace final navegable debería ser:

```text
authoring_room_polygon
  - wall_footprints
  - object_footprints
  - other non-navigable footprints
```

Mientras ese cálculo no exista, el exportador debe marcar esos spaces como provisionales o mantenerlos en `sourceFeatures`.

---

## 11. CellSpace

### 11.1. Definición operativa

Un `CellSpace` es una unidad espacial identificable dentro de una ThematicLayer.

En el modelo 2D del TFG se representará normalmente como:

```json
"cellSpaceGeom": {
  "geometry2D": {
    "type": "Polygon",
    "coordinates": []
  }
}
```

### 11.2. Campos mínimos recomendados

```json
{
  "id": "CS_L00_ROOM_001",
  "featureType": "CellSpace",
  "cellSpaceName": "Room 001",
  "level": "LEVEL_00",
  "poi": false,
  "duality": "TL_NAV_L00:DS_NAV_L00:N_L00_ROOM_001",
  "cellSpaceGeom": {
    "geometry2D": {
      "type": "Polygon",
      "coordinates": []
    }
  },
  "boundedBy": []
}
```

### 11.3. Extensión semántica

Para Navigation, el CellSpace se especializa conceptualmente como:

- `GeneralSpace`;
- `TransferSpace`;
- `NonNavigableSpace`;
- `ObjectSpace`.

Como JSON práctico, hay dos opciones:

#### Opción A: usar `featureType: "CellSpace"` y un campo de extensión

```json
{
  "featureType": "CellSpace",
  "navigationType": "GeneralSpace"
}
```

#### Opción B: usar `featureType` especializado

```json
{
  "featureType": "GeneralSpace"
}
```

### Decisión inicial

Para mantener cercanía con IndoorJSON Core y permitir extensión clara:

```text
featureType = "CellSpace"
navigationType = "GeneralSpace" | "TransferSpace" | "NonNavigableSpace" | "ObjectSpace"
```

Si más adelante el schema propio adopta directamente los `oneOf` de Navigation, podrá permitir `featureType` especializado o validar por `navigationType`.

---

## 12. Jerarquía espacial Navigation

La jerarquía conceptual es:

```text
CellSpace
├── NavigableSpace
│   ├── GeneralSpace
│   └── TransferSpace
└── NonNavigableSpace
    └── ObjectSpace
```

### 12.1. NavigableSpace

Espacio por el que puede transitar una persona o agente.

Debe incluir información de locomoción:

```text
Walking
Rolling
Flying
Unspecified
```

En el TFG, los modos principales serán:

```text
Walking
Rolling
Step / stair-related como extensión local si hace falta
```

Si `Step` no existe en IndoorJSON Navigation, se debe mapear con cuidado:

```text
Step → extensión local o constraint adicional
```

### 12.2. GeneralSpace

Subtipo de NavigableSpace que representa:

- habitaciones;
- aulas;
- laboratorios;
- pasillos;
- vestíbulos;
- zonas principales de permanencia o tránsito.

No representa puertas ni ventanas.

### 12.3. TransferSpace

Subtipo de NavigableSpace que representa conexión o transición:

- puerta;
- ventana practicable;
- salida exterior;
- entrada/salida de escalera;
- rampa;
- ascensor;
- conexión vertical.

Campos recomendados:

```text
category: Door | Window | Ramp | Stair | Elevator | LocalExtension
function: ConnectionSpace | AnchorSpace
```

IndoorJSON Navigation define oficialmente `Door` y `Window` como categorías de TransferSpace. Para escaleras, rampas y ascensores se puede usar una extensión local documentada o una capa específica futura.

### 12.4. NonNavigableSpace

Espacio no transitable.

Incluye:

- muros;
- slabs;
- zonas bloqueadas;
- masas constructivas;
- objetos si no se necesita detalle adicional.

### 12.5. ObjectSpace

Subtipo de NonNavigableSpace para objetos concretos:

- columnas;
- mobiliario;
- obstáculos;
- equipamiento;
- elementos internos que bloquean o restringen el paso.

La regla importante es que ObjectSpace también está sujeto a no solaparse con CellSpaces de la misma capa. Si se quiere evitar recortar la habitación, puede modelarse en otra capa temática y relacionarse mediante InterLayerConnection.

---

## 13. CellBoundary

### 13.1. Definición

Un `CellBoundary` representa una interfaz de una o varias celdas.

En 2D se representa como:

```text
LineString
```

En 3D se representaría como superficie.

### 13.2. Campos básicos

```json
{
  "id": "CB_L00_ROOM001_DOOR001",
  "featureType": "CellBoundary",
  "isVirtual": false,
  "duality": "TL_NAV_L00:DS_NAV_L00:E_L00_ROOM001_DOOR001",
  "cellBoundaryGeom": {
    "geometry2D": {
      "type": "LineString",
      "coordinates": []
    }
  }
}
```

### 13.3. Navigation boundary types

```text
CellBoundary
├── NavigableBoundary
└── NonNavigableBoundary
```

Como con CellSpace, se recomienda:

```text
featureType = "CellBoundary"
navigationBoundaryType = "NavigableBoundary" | "NonNavigableBoundary"
```

### 13.4. NavigableBoundary

Boundary atravesable.

Ejemplos:

- umbral entre habitación y puerta;
- umbral entre puerta y pasillo;
- anchor boundary entre salida y exterior;
- boundary virtual entre dos zonas navegables si la subdivisión es funcional.

Puede tener:

```text
navigableBoundaryFunction = ConnectionBoundary | AnchorBoundary
```

### 13.5. NonNavigableBoundary

Boundary no atravesable.

Ejemplos:

- contacto habitación-muro;
- lateral de puerta contra muro;
- contacto sala-columna;
- envolvente sólida.

---

## 14. Puertas, ventanas y salidas

### 14.1. Problema conceptual

En 2D, una puerta puede representarse de dos formas:

1. Como `TransferSpace` con footprint 2D.
2. Como `NavigableBoundary` entre dos spaces.

IndoorGML reconoce que en 2D las puertas suelen representarse como boundaries de habitaciones, pero también admite que las puertas pueden modelarse como espacios navegables, especialmente cuando se quiere más detalle.

### 14.2. Decisión para el TFG

Para el modelo operativo del TFG:

```text
puerta = TransferSpace con footprint 2D
```

Motivos:

- permite guardar ancho;
- permite guardar grosor;
- permite representar capacidad;
- permite conectar `GeneralSpace → TransferSpace → GeneralSpace`;
- permite derivar grafos más ricos;
- permite visualizar umbrales;
- permite simular restricciones de paso.

### 14.3. Vista IndoorJSON estricta

Para una exportación estricta 2D se podrá generar una vista derivada:

```text
TransferSpace Door → NavigableBoundary
```

Esta vista perderá información operativa, pero puede mejorar compatibilidad con consumidores IndoorJSON estrictos.

### 14.4. Salidas

Una salida al exterior se modela como:

```text
TransferSpace
category = Door
function = AnchorSpace
```

No se recomienda crear un tipo raíz `ExitSpace` en el nuevo modelo indoor si el objetivo es fidelidad IndoorGML. Puede mantenerse como alias interno o legacy.

### 14.5. Ventanas

Una ventana practicable se modela como:

```text
TransferSpace
category = Window
function = ConnectionSpace o AnchorSpace según caso
```

EvacEngine decidirá después si una ventana es usable para evacuación normal.

---

## 15. Muros, columnas y obstáculos

### 15.1. Muros

En el prototipo MLSM, un muro aparece como `physical_element` dibujado con centerline y grosor.

En el nuevo modelo:

```text
muro de autoría → sourceFeature / authoringGeometry
muro derivado → NonNavigableSpace
contacto muro-sala → NonNavigableBoundary
```

### 15.2. Columnas

```text
columna de autoría → sourceFeature
columna derivada → ObjectSpace
contacto columna-sala → NonNavigableBoundary
```

### 15.3. Obstáculos y mobiliario

Si el obstáculo debe bloquear el paso dentro de una habitación, hay dos opciones:

#### Opción A: tallarlo en el mismo PrimalSpaceLayer

La habitación navegable se recorta y el obstáculo se vuelve ObjectSpace.

Ventaja:

- topológicamente claro;
- CellSpaces no se solapan.

Desventaja:

- requiere operaciones booleanas más complejas.

#### Opción B: capa temática separada

El mobiliario se coloca en otra ThematicLayer y se conecta con la sala mediante InterLayerConnection.

Ventaja:

- evita recortes complejos;
- conserva la geometría de habitación simple.

Desventaja:

- el simulador debe considerar esa capa para colisión.

### Decisión inicial

Para el TFG:

```text
muros principales → NonNavigableSpace en la capa topográfica si se dispone de footprint
columnas/obstáculos → ObjectSpace si se tallan; capa separada si se quiere evitar recorte
```

---

## 16. Authoring geometry / sourceFeatures

### 16.1. Propósito

`sourceFeatures` conserva la geometría que el usuario dibuja en SpatialEngine.

Ejemplos:

- muro como línea;
- puerta como línea;
- habitación dibujada como polígono inicial;
- columna como punto;
- frontera virtual como línea.

### 16.2. Por qué no debe reemplazar el primal

La autoría no necesariamente cumple:

- no solape;
- boundaries correctas;
- espacios navegables recortados;
- dualidad con nodos y edges;
- semántica IndoorGML completa.

Por eso se conserva como trazabilidad, no como modelo espacial final.

### 16.3. Ejemplo conceptual

```json
{
  "id": "SF_L00_WALL_001",
  "sourceType": "wall_centerline",
  "level": "LEVEL_00",
  "geometry": {
    "type": "LineString",
    "coordinates": [[0, 0], [5, 0]]
  },
  "parameters": {
    "thickness_m": 0.15,
    "height_m": 3.0
  },
  "derivedCellSpaces": ["CS_L00_WALL_001"]
}
```

---

## 17. DualSpaceLayer y grafos derivados

### 17.1. DualSpaceLayer base

El modelo no debe exportar inicialmente cuatro grafos independientes como raíz principal.

Debe exportar un `DualSpaceLayer`:

```text
nodeMember[]
edgeMember[]
```

Cada `Node` representa un `CellSpace`.

Cada `Edge` representa una relación entre dos Nodes y puede estar asociado por dualidad a un `CellBoundary`.

### 17.2. Node

```json
{
  "id": "N_L00_ROOM_001",
  "featureType": "Node",
  "duality": "TL_NAV_L00:PS_NAV_L00:CS_L00_ROOM_001",
  "geometry": {
    "type": "Point",
    "coordinates": [2.0, 2.0]
  },
  "connects": []
}
```

Si `DualSpaceLayer.isLogical = false`, la geometría del node debe estar dentro de su CellSpace correspondiente.

### 17.3. Edge

```json
{
  "id": "E_L00_ROOM001_DOOR001",
  "featureType": "Edge",
  "duality": "TL_NAV_L00:PS_NAV_L00:CB_L00_ROOM001_DOOR001",
  "weight": 1.0,
  "geometry": {
    "type": "LineString",
    "coordinates": [[2.0, 2.0], [4.0, 2.0]]
  },
  "connects": [
    "TL_NAV_L00:DS_NAV_L00:N_L00_ROOM_001",
    "TL_NAV_L00:DS_NAV_L00:N_L00_DOOR_001"
  ],
  "attributes": {
    "relationshipType": "connectivity",
    "traversable": true,
    "sourceBoundaryType": "NavigableBoundary"
  }
}
```

### 17.4. Atributos de edge

Como IndoorJSON Core no define todos los atributos que el TFG necesita, se permite una extensión local:

```text
relationshipType: adjacency | connectivity | containment | vertical_connection
traversable: true | false
boundaryRef
transferSpaceRef
locomotion
width_m
capacity
baseWeight
```

### 17.5. Grafos derivados

A partir del `DualSpaceLayer` se derivan vistas:

```text
adjacency_total       = todos los edges de contacto
connectivity_graph    = edges traversable = true
general_to_general    = colapso de TransferSpaces
transfer_to_transfer  = vista tipo door-to-door
routing_graph         = runtime de EvacEngine
```

Estas vistas no tienen que almacenarse todas en `indoor_model.json`. Pueden ser generadas por servicios externos, visualizador o EvacEngine.

### 17.6. Door-to-door

El antiguo `door_to_door_graph` es útil, pero no debe ser la estructura base.

Puede derivarse de:

```text
GeneralSpace ↔ TransferSpace ↔ GeneralSpace
```

Para cada GeneralSpace, se conectan los TransferSpaces incidentes dentro del mismo espacio navegable.

Esto puede hacerse en un servicio posterior si SpatialEngine no debe asumir ese cálculo.

### 17.7. Route

`Route` representa una ruta calculada, no el grafo base del edificio.

Por tanto:

```text
SpatialEngine no exporta Route.
EvacEngine puede exportar Route como resultado.
```

---

## 18. InterLayerConnection y capas futuras

### 18.1. Uso principal

`InterLayerConnection` conecta capas temáticas distintas.

Casos futuros:

- capa topográfica ↔ capa de mobiliario;
- capa topográfica ↔ capa de sensores;
- planta 0 ↔ planta 1;
- geometría de autoría ↔ primal derivado;
- modelo indoor ↔ coverage de beacons.

### 18.2. No abusar al inicio

No conviene usar InterLayerConnection para todo desde el principio.

Primero se recomienda:

```text
una capa topográfica/navigation por planta
```

Después, cuando haya sensores u objetos complejos, se añaden capas.

---

## 19. `scenario_model.json`

### 19.1. Propósito

`scenario_model.json` describe condiciones de simulación sobre un `indoor_model.json`.

### 19.2. Estructura propuesta

```json
{
  "scenario_id": "SCENARIO_001",
  "schema_version": "0.1-draft",
  "indoor_model_ref": {
    "path": "indoor_model.json",
    "indoor_model_id": "IF_BUILDING_001"
  },
  "population": {},
  "beacons": [],
  "hazards": [],
  "simulation_config": {},
  "outputs": {}
}
```

### 19.3. Population

Puede incluir:

- groups;
- profiles;
- spawn areas;
- initial positions;
- distributions.

Referencias permitidas:

- `cellSpaceId`;
- `nodeId`;
- coordenadas;
- nivel.

### 19.4. Beacons

Beacons pueden referenciar:

- CellSpaces;
- Nodes;
- Edges;
- Boundaries;
- geometrías.

No pertenecen al indoor model base salvo que se decida tratarlos como mobiliario o sensores fijos dentro de una capa temática especial.

### 19.5. Hazards

Hazards pueden referenciar:

- CellSpaces afectados;
- Edges bloqueados;
- Boundaries atravesables afectadas;
- regiones geométricas.

### 19.6. Simulation config

Incluye:

- `timeStep`;
- `maxSteps`;
- estrategia de routing;
- pesos dinámicos;
- overlays activos;
- output metrics.

---

## 20. `project_manifest.json`

### 20.1. Decisión

No es obligatorio al inicio.

### 20.2. Cuándo usarlo

Usarlo cuando existan:

- varios escenarios para un edificio;
- múltiples variantes de indoor_model;
- carpetas de resultados;
- necesidad de checksums;
- pipeline automatizado.

### 20.3. Estructura mínima

```json
{
  "project_id": "PROJECT_TFG_001",
  "indoor_model": "indoor_model.json",
  "scenarios": [
    "scenario_model.json"
  ],
  "outputs_dir": "outputs/simulations"
}
```

---

## 21. IDs estables y referencias

### 21.1. Reglas generales

- Los IDs no deben depender solo del nombre visible.
- Los IDs deben mantenerse estables si se edita una etiqueta.
- Los IDs deben incluir nivel cuando corresponda.
- Los overlays nunca deben referenciar nombres de UI si existe un ID técnico.

### 21.2. Prefijos recomendados

```text
IF_     IndoorFeatures
TL_     ThematicLayer
PS_     PrimalSpaceLayer
DS_     DualSpaceLayer
CS_     CellSpace
CB_     CellBoundary
N_      Node
E_      Edge
ILC_    InterLayerConnection
SF_     SourceFeature
SCN_    Scenario
AG_     Agent
SP_     Spawn
BCN_    Beacon
HZ_     Hazard
RT_     Route
```

### 21.3. Ejemplos

```text
CS_L00_ROOM_001
CS_L00_DOOR_001
CS_L00_WALL_001
CB_L00_ROOM001_DOOR001
N_L00_ROOM_001
E_L00_ROOM001_DOOR001
SF_L00_WALL_LINE_001
```

### 21.4. Referencias URI-like

Para acercarse a IndoorJSON:

```text
TL_NAV_L00:PS_NAV_L00:CS_L00_ROOM_001
TL_NAV_L00:DS_NAV_L00:N_L00_ROOM_001
```

---

## 22. Relación futura con PostgreSQL/PostGIS

El modelo se puede mapear a tablas:

```text
indoor_features
levels
thematic_layers
primal_space_layers
dual_space_layers
cell_spaces
cell_boundaries
nodes
edges
inter_layer_connections
source_features
scenarios
agent_spawns
agents
beacons
hazards
simulation_configs
routes
```

Geometrías:

```text
cell_spaces.geom Polygon
cell_boundaries.geom LineString
nodes.geom Point
edges.geom LineString
source_features.geom Point/LineString/Polygon
```

Relaciones:

```text
cell_spaces.duality_node_id
cell_boundaries.duality_edge_id
edges.source_node_id
edges.target_node_id
edges.boundary_id
scenario.indoor_model_id
beacons.affected_cell_space_id
hazards.affected_edge_id
```

El punto clave es que `indoor_model.json` debe usar IDs estables desde el principio para que la migración a PostGIS no requiera rediseñar referencias.

---

## 23. Relación futura con SpatialEngine

### 23.1. Situación actual

SpatialEngine mantiene:

```text
self.muros          → elementos lineales de autoría
self.hitos          → centroides
self.hitos_bounds   → footprints de espacios de autoría
self.agentes        → spawns, que deben salir de SpatialEngine en el nuevo modelo
```

### 23.2. Objetivo

SpatialEngine debe evolucionar hacia:

```text
Authoring geometry
  ↓
Derived physical model
  ↓
Primal indoor model
  ↓
DualSpaceLayer
```

### 23.3. Nueva exportación

Se añadirá en el futuro:

```python
exportar_indoor_model()
```

Esta exportación no debe incluir:

```text
agent_spawns
agents
beacons
hazards
simulation
```

### 23.4. v1/v2 legacy

`exportar_mlsm_core()` y `exportar_mlsm_core_v2()` pueden mantenerse temporalmente, pero no son el destino conceptual.

---

## 24. Relación futura con EvacEngine

EvacEngine deberá cargar:

```text
indoor_model.json
scenario_model.json
```

Luego derivará:

```text
runtime routing graph
routes
metrics
agent trajectories
```

EvacEngine no debe modificar el indoor model base. Sus resultados deben guardarse aparte.

---

## 25. Relación futura con el visualizador

El visualizador debe poder abrir:

```text
indoor_model.json
scenario_model.json opcional
project_manifest.json opcional
```

Capas visuales esperadas:

```text
source features
general spaces
transfer spaces
non-navigable spaces
object spaces
cell boundaries
nodes
edges
scenario overlays
routes
```

No debe intentar mostrar una capa que el modelo no exporta. Si `NonNavigableSpace` no está todavía generado, debe indicarlo claramente en vez de mostrar una capa vacía sin explicación.

---

## 26. Estrategia de migración desde MLSM v1/v2

### 26.1. MLSM v1

Estado:

```text
legacy
```

Uso:

```text
referencia histórica / compatibilidad temporal
```

No se diseñan nuevas funciones para v1.

### 26.2. MLSM JSON v2 monolítico

Estado:

```text
transitional prototype
```

Uso:

```text
puente hacia indoor_data_model
```

No debe seguir creciendo como formato principal.

### 26.3. Indoor Data Model

Estado objetivo:

```text
nuevo contrato conceptual del TFG
```

---

## 27. Decisiones adoptadas

1. El nuevo nombre conceptual es `indoor_data_model`.
2. El archivo espacial principal será `indoor_model.json`.
3. El archivo de escenario será `scenario_model.json`.
4. `project_manifest.json` queda opcional.
5. SpatialEngine exportará solo `indoor_model.json`.
6. Agentes, beacons, hazards y simulación quedan fuera del indoor model.
7. El indoor model debe parecerse a IndoorJSON: `IndoorFeatures → ThematicLayer → PrimalSpaceLayer/DualSpaceLayer`.
8. `physical_elements` deja de ser raíz principal del nuevo contrato.
9. La geometría de autoría se conserva como `sourceFeatures` o `authoringGeometry`.
10. Muros derivados se modelan como `NonNavigableSpace` si se incluyen en la capa topográfica.
11. Columnas/obstáculos se modelan como `ObjectSpace`.
12. Puertas se modelan operativamente como `TransferSpace` con footprint 2D.
13. Una vista estricta 2D podrá colapsar puertas a `NavigableBoundary`.
14. Salidas se modelan como `TransferSpace` con función `AnchorSpace`.
15. `Route` es resultado de EvacEngine, no grafo base de SpatialEngine.
16. El `DualSpaceLayer` base sustituye a múltiples grafos raíz independientes.
17. Grafos como connectivity, room-to-room y door-to-door serán vistas derivadas.
18. IDs estables son obligatorios para overlays y PostGIS.

---

## 28. Decisiones pendientes

1. Definir el primer `indoor_model.schema.json`.
2. Definir el primer `scenario_model.schema.json`.
3. Decidir si `sourceFeatures` vive en raíz o dentro de una extensión.
4. Decidir si las capas de objetos/furniture se tallan o se separan en ThematicLayer distinta.
5. Definir el tratamiento inicial de escaleras, rampas y ascensores.
6. Definir si cada planta será una ThematicLayer o si se agruparán varias plantas.
7. Definir cómo se generarán IDs persistentes desde SpatialEngine.
8. Definir cómo se hará la exportación estricta IndoorJSON si se necesita.
9. Definir cómo se visualizarán las capas cuando falten NonNavigableSpaces o ObjectSpaces.
10. Definir cuándo se eliminará o congelará definitivamente `mlsm_json_v2.schema.json`.

---

## 29. Plan incremental recomendado

### Etapa 1 — Documentación canónica

Crear:

```text
docs/technical/architecture/indoor_data_model_architecture.md
```

Marcar como legacy/transitional:

```text
mlsm_json_v2_design.md
mlsm_json_v2.schema.json
```

### Etapa 2 — Schema del indoor model

Crear:

```text
schemas/indoor_data_model/indoor_model.schema.json
```

Debe validar una estructura IndoorFeatures-like.

### Etapa 3 — Ejemplo mínimo generado

Crear un ejemplo mínimo equivalente al dummy oficial:

```text
C1 ↔ B1 ↔ C2
N1 ↔ E1 ↔ N2
```

pero usando nombres y extensiones del TFG.

### Etapa 4 — Exportador de SpatialEngine

Añadir:

```python
exportar_indoor_model()
```

No incluir scenario data.

### Etapa 5 — Visualizador nuevo

Adaptar visualizador para `indoor_model.json`, no para el viejo `mlsm_json_v2`.

### Etapa 6 — Scenario model

Crear:

```text
scenario_model.schema.json
```

con population, beacons, hazards y simulation config.

### Etapa 7 — EvacEngine

Crear loader:

```text
indoor_model + scenario_model → runtime graph
```

### Etapa 8 — PostGIS / Qt / mejoras avanzadas

Solo después de estabilizar el modelo.

---

## 30. Criterios para considerar estable esta arquitectura

La arquitectura puede considerarse estable cuando:

- el documento canónico está aprobado;
- el schema `indoor_model` valida un ejemplo mínimo;
- el ejemplo mínimo representa primal y dual como el dummy oficial;
- `scenario_model` queda separado;
- SpatialEngine puede exportar un indoor model sin agentes/beacons/hazards;
- el visualizador puede mostrar CellSpaces, CellBoundaries, Nodes y Edges;
- EvacEngine puede derivar una ruta desde el dual layer y scenario model;
- las decisiones sobre puertas, muros, boundaries y ObjectSpaces están implementadas o claramente marcadas como pendientes.
