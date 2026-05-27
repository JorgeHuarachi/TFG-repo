# Schema JSON MLSM v1 - Auditoría de facto

## 1. Propósito del documento

Este documento describe el **formato JSON MLSM v1 actual de facto**, es decir, el schema que realmente se genera en `MLSM_SpatialEngine.py` y se consume en `MLSM_EvacEngine.py`.

**No es:**
- Un idealizado para el futuro MLSM v2
- Un JSON Schema formal (`.schema.json`)
- Una reinterpretación de IndoorGML completo

**Es:**
- Una auditoría de la estructura JSON real que conecta SpatialEngine → EvacEngine
- Una base para futuras mejoras y migraciones a estándares
- Un contrato de datos explícito entre generador y consumidor
- Ejemplos como `baseline/scenario_v0_existing.json` y `baseline/scenario_v1_manual_spatial_FINAL.json` representan el mismo schema MLSM v1, no versiones diferentes del schema.

## 2. Relación entre "schema de facto" y "JSON Schema"

En este contexto:

- **Schema de facto**: La estructura real del JSON MLSM v1 que existe hoy, documentada mediante inspección de código y ejemplos
- **JSON Schema formal**: Un documento `.schema.json` que podría crearse más adelante para validación automática
- **MLSM v2**: Una versión mejorada del schema, potencialmente alineada con IndoorGML/IndoorJSON

Este documento proporciona la **base de facto** necesaria para cualquiera de esos futuros pasos.

## 3. Flujo actual

```
MLSM_SpatialEngine.py
  │ (función: exportar_mlsm_core)
  ├─→ JSON MLSM v1
       │
       ├─ configuracion
       ├─ conexiones_horizontales
       ├─ conexiones_verticales
       ├─ espacios_navegables
       ├─ muros
       └─ agentesspawn
       │
       └─→ MLSM_EvacEngine.py
           │ (ModeloAvanzado.__init__)
           ├─ Lee configuracion → ancho, alto
           ├─ Lee espacios_navegables → hitos, locomotion, polígonos
           ├─ Lee muros → geometría de colisión
           ├─ Lee conexiones_horizontales → grafo de enrutamiento
           └─ Lee agentesspawn → posiciones iniciales de agentes
```

## 4. Campos raíz del JSON MLSM v1

| Campo | Tipo | Generado | Consumido | Obligatorio | Descripción |
|-------|------|----------|-----------|-----------|-------------|
| `configuracion` | object | ✓ | ✓ | ✓ | Metadatos del escenario (ancho, alto) |
| `conexiones_horizontales` | array | ✓ | ✓ | ✓ | Grafo de navegación entre espacios |
| `conexiones_verticales` | array | ✓ | ✗ | ✗ | Inter-layer connections MLSM (reservado) |
| `espacios_navegables` | object | ✓ | ✓ | ✓ | Diccionario de nodos y espacios |
| `muros` | array | ✓ | ✓ | ✓ | Geometría de colisión (Shapely) |
| `agentesspawn` | array | ✓ | ✓ | ~ | Posiciones iniciales de agentes |

---

## 5. `configuracion`

**Estructura:**
```json
{
  "configuracion": {
    "ancho": 10,
    "alto": 5
  }
}
```

| Campo | Tipo | Significado | Rango | Obligatorio |
|-------|------|-----------|-------|-----------|
| `ancho` | float | Dimensión X del mapa en metros | > 0 | ✓ |
| `alto` | float | Dimensión Y del mapa en metros | > 0 | ✓ |

**Consumo en EvacEngine:**
- `ModeloAvanzado.__init__`: Lee `datos['configuracion']['ancho']` y `['alto']`
- Usado para crear `mesa.space.ContinuousSpace(ancho, alto, torus=False)`

**Observaciones:**
- No hay soporte para Z (coordenada vertical de pisos)
- El espacio es 2D continuo, sin soporte para grillas discretas

---

## 6. `espacios_navegables`

**Estructura:**
```json
{
  "espacios_navegables": {
    "Habitacion_1": {
      "centroide": [5.0, 2.5],
      "poligono": [
        [0.0, 0.0],
        [10.0, 0.0],
        [10.0, 5.0],
        [0.0, 5.0]
      ],
      "atributos": {
        "clase_indoor": "NavigableSpace",
        "categoria": "Room",
        "locomotion": ["Walking", "Rolling"]
      }
    },
    "Puerta_simple_1": {
      "centroide": [5.5, 2.75],
      "poligono": [[5.0, 2.5], [6.0, 2.5], [6.0, 3.0], [5.0, 3.0]],
      "atributos": {
        "clase_indoor": "TransferSpace",
        "categoria": "Door",
        "locomotion": ["Walking"]
      }
    }
  }
}
```

| Campo | Tipo | Significado | Obligatorio | Notas |
|-------|------|-----------|-----------|-------|
| (clave) | string | Nombre único del espacio | ✓ | Ej: "Habitacion_1", "Puerta_simple_5", "Salida_16" |
| `centroide` | [float, float] | Coordenadas (x, y) del centro del espacio | ✓ | Usado como "hito" para pathfinding |
| `poligono` | [[float, float], ...] | Vértices del contorno del espacio | ✓ | Cerrado (primer vértice ≈ último) |
| `atributos` | object | Metadatos semánticos | ~ | Puede estar vacío |

**Atributos sub-campos:**

| Campo | Tipo | Significado | Posibles valores | Obligatorio |
|-------|------|-----------|-----------------|-----------|
| `clase_indoor` | string | Clasificación IndoorGML (de facto) | "NavigableSpace", "TransferSpace", "AnchorSpace", "ObjectSpace" | ✗ |
| `categoria` | string | Descripción textual del espacio | "Room", "Door", "Corridor", "Transition", etc. | ✗ |
| `locomotion` | array of strings | Perfiles de movilidad permitidos | ["Walking"], ["Walking", "Rolling"], ["Walking", "Step"] | ✓ (crítico) |

**Consumo en EvacEngine:**
1. `ModeloAvanzado.__init__` → Extrae centroides: `self.hitos[nombre_nodo] = tuple(datos_nodo['centroide'])`
2. `construir_grafo_desde_json()` → Usa centroides para calcular distancias de aristas
3. Línea de visión → Carga poligonos en `Polygon(datos_espacio['poligono'])`
4. Restricciones de movilidad → Filtra por `'Rolling' in datos_espacio['atributos'].get('locomotion', [])`

**Acoplamientos críticos:**

| Acoplamiento | Riesgo | Mitigación |
|-----------|--------|-----------|
| Nombres con `"Puerta"` | String matching para filtros visuales y lógica | Documentación clara de convenciones de naming |
| Nombres con `"Salida"` | Necesario para detectar puntos de evacuación | Obligatorio tener al menos 1 espacio con "Salida" |
| Nombres con `"Frontera"` | Usado para detener búsquedas de visión | Debe ser distinct de puertas físicas |
| `locomotion` ausente → `[]` por defecto | Rolling queda restringido, Walking no se bloquea explícitamente | Documentar que la ausencia no equivale a `"Walking"` |
| `centroide` inexistente → exception | Causa crash en pathfinding | CRÍTICO: Todo espacio debe tener centroide |
| `poligono` estructura inválida | Shapely lanza excepción en intersection | CRÍTICO: Poligonos deben ser valid |

---

## 7. `muros`

**Estructura:**
```json
{
  "muros": [
    {
      "id": "Muro_exterior_1_part0",
      "tipo": "muro_exterior",
      "poligono": [
        [0.0, 0.0],
        [10.0, 0.0],
        [10.0, 0.5],
        [0.0, 0.5]
      ]
    },
    {
      "id": "Puerta_simple_1",
      "tipo": "puerta_simple",
      "poligono": [[5.0, 0.0], [5.9, 0.0], [5.9, 0.15], [5.0, 0.15]]
    }
  ]
}
```

| Campo | Tipo | Significado | Obligatorio | Notas |
|-------|------|-----------|-----------|-------|
| `id` | string | Identificador único del muro/puerta | ✓ | Generado por SpatialEngine con sufijo `_part{N}` |
| `tipo` | string | Clasificación del elemento | ✓ | Ej: "muro_exterior", "muro_interior", "puerta_simple", "puerta_doble", "salida", "frontera_virtual" |
| `poligono` | [[float, float], ...] | Geometría CSG (Constructive Solid Geometry) | ✓ | Ya incluye restas booleanas de puertas |

**Tipos de muros:**

| Tipo | Grosor BIM | Consumo EvacEngine | Observaciones |
|------|----------|-----------------|------------|
| `muro_exterior` | 0.40 m | Cargado como collider opaco | Barrera exterior del mapa |
| `muro_interior` | 0.15 m | Cargado como collider opaco | Tabiques internos |
| `puerta_simple` | 0.15 m | Presente en JSON pero NO cargado como obstáculo físico | Permite inferencia de puertas en CSG |
| `puerta_doble` | 0.15 m | Presente en JSON pero NO cargado como obstáculo físico | Permite inferencia de puertas en CSG |
| `salida` | 0.20 m | Presente en JSON pero NO cargado como obstáculo físico | Marca salidas, no muro sólido |
| `frontera_virtual` | 0.05 m | Presente en JSON pero NO cargado como obstáculo físico | Límite topológico sin barrera física |

**Consumo en EvacEngine:**
1. `construir_paredes_desde_json()`:
   - Filtra solo muros con `tipo in ['muro_exterior', 'muro_interior']`
   - Crea `Polygon(m['poligono'])` y lo añade a `self.poligonos_muros`
   - **Nota:** Las puertas y fronteras NO se cargan como obstáculos físicos (¡están ya substraídos del JSON!)

2. Línea de visión e intersección:
   - Se usa `muro_poly.intersects(linea_visual)` para bloquear visión
   - Se usa `muro_poly.contains(punto_agente)` para detectar colisiones

**Observaciones:**
- Los polígonos de muros ya incluyen **restas booleanas de puertas**, generadas por `procesar_geometria_booleana()`
- Esto significa que las puertas están "cortadas" de los muros sólidos, no superpuestas

---

## 8. `conexiones_horizontales`

**Estructura:**
```json
{
  "conexiones_horizontales": [
    {
      "origen": "Habitacion_1",
      "destino": "Puerta_simple_1",
      "tipo": "navegable_puerta",
      "color": "cyan",
      "estilo": "-"
    },
    {
      "origen": "Puerta_simple_1",
      "destino": "Puerta_doble_2",
      "tipo": "door_to_door",
      "contexto": "Habitacion_1",
      "color": "magenta",
      "estilo": ":"
    },
    {
      "origen": "Habitacion_1",
      "destino": "Habitacion_2",
      "tipo": "adyacencia_fisica",
      "color": "gold",
      "estilo": "--"
    }
  ]
}
```

| Campo | Tipo | Significado | Obligatorio | Notas |
|-------|------|-----------|-----------|-------|
| `origen` | string | Nodo de inicio | ✓ | Referencia a clave en `espacios_navegables` |
| `destino` | string | Nodo de destino | ✓ | Referencia a clave en `espacios_navegables` |
| `tipo` | string | Tipo de conexión | ✓ | Determina comportamiento de pathfinding |
| `contexto` | string | Nodo intermediario (solo door_to_door) | ~ | Especifica habitación donde ocurre la transición |
| `color` | string | Hint para visualización | ✗ | Usado en gráficos del SpatialEngine |
| `estilo` | string | Hint para visualización (linestyle) | ✗ | Usado en gráficos del SpatialEngine |

**Tipos de conexión:**

| Tipo | Capa MLSM | Origen → Destino | Peso en Dijkstra | Consumo |
|------|----------|------------------|------------------|---------|
| `navegable_puerta` | MACRO/MESO | Habitación ↔ Puerta/Salida/Frontera | distancia × 1.5 | ✓ Usado en pathfinding |
| `door_to_door` | MICRO | Puerta ↔ Puerta (dentro de 1 habitación) | distancia × 0.8 | ✓ Preferido en Dijkstra |
| `adyacencia_fisica` | MACRO | Habitación ↔ Habitación | No consumida | ✗ Generado pero NO usado |

**Consumo en EvacEngine:**
1. `construir_grafo_desde_json()`:
   ```python
   if conn['tipo'] in ['navegable_puerta', 'door_to_door']:
       u, v = conn['origen'], conn['destino']
       distancia = ||hitos[u] - hitos[v]||
       peso_ruta = distancia * (0.8 if tipo == 'door_to_door' else 1.5)
       grafo.add_edge(u, v, weight=peso_ruta, tipo=tipo, contexto=conn.get('contexto'))
   ```

2. Pathfinding en `calcular_ruta_dijkstra()`:
   - Solo se usan aristas con tipo `'navegable_puerta'` o `'door_to_door'`
   - `door_to_door` tiene peso menor (0.8×), por lo que Dijkstra las prefiere
   - El contexto se usa para expandir rutas semánticamente: "Puerta → Habitación → Puerta"

**Acoplamientos:**
- Grafo asume que `origen` y `destino` son claves válidas en `espacios_navegables`
- Falta de aristas hace que algunos espacios sean inalcanzables
- El tipo `adyacencia_fisica` se genera pero no se usa (desperdicio de datos)

---

## 9. `conexiones_verticales`

**Estructura:**
```json
{
  "conexiones_verticales": [
    {
      "nodo_id": "Habitacion_1",
      "capa_superior": "adyacencia_fisica",
      "capa_inferior": "navegable_puerta",
      "tipo_conexion": "representa_el_mismo_espacio"
    },
    {
      "nodo_id": "Puerta_simple_1",
      "capa_superior": "navegable_puerta",
      "capa_inferior": "door_to_door",
      "tipo_conexion": "representa_el_mismo_espacio"
    }
  ]
}
```

| Campo | Tipo | Significado | Obligatorio | Notas |
|-------|------|-----------|-----------|-------|
| `nodo_id` | string | Identificador del nodo | ✓ | Clave en `espacios_navegables` |
| `capa_superior` | string | Capa MLSM superior | ✓ | Ej: "adyacencia_fisica", "navegable_puerta" |
| `capa_inferior` | string | Capa MLSM inferior | ✓ | Ej: "navegable_puerta", "door_to_door" |
| `tipo_conexion` | string | Relación entre capas | ✓ | Actualmente siempre "representa_el_mismo_espacio" |

**Estado actual:**
- **Generado:** Sí (en `exportar_mlsm_core`)
- **Consumido:** No (EvacEngine no usa este campo)
- **Propósito:** Reservado para futuras extensiones MLSM o compatibilidad IndoorGML

**Observaciones:**
- Este campo es infraestructura para soportar consultas de capas múltiples en el futuro
- Actualmente es un "placeholder" sin valor operacional en EvacEngine

---

## 10. `agentesspawn`

**Estructura:**
```json
{
  "agentesspawn": [
    [5.0, 2.5],
    [3.0, 1.5],
    [7.5, 3.0],
    [2.0, 4.0]
  ]
}
```

| Campo | Tipo | Significado | Obligatorio | Notas |
|-------|------|-----------|-----------|-------|
| (array) | [[float, float], ...] | Posiciones [x, y] iniciales | ~ | Puede ser vacío (sin agentes) |
| Cada elemento | [float, float] | Coordenada (x, y) del agente | ✓ | Debe estar dentro del mapa y transitible |

**Consumo en EvacEngine:**
```python
agentes_json = datos.get('agentesspawn', [])
lista_final_agentes = [tuple(p) for p in agentes_json]

for i, pos in enumerate(lista_final_agentes):
    if self.es_transitable(pos):
        perfil = random.choice(["Walking", "Rolling", "Elderly"])  # 70/15/15
        agente = AgentePro(i, self, perfil=perfil)
        self.agents.add(agente)
        self.space.place_agent(agente, pos)
```

**Observaciones:**
- Si una posición no es transitable (dentro de un muro), el agente es ignorado con warning
- Los agentes se asignan a perfiles demográficos **estocásticamente** (sin control en JSON)
- No hay soporte para perfiles nominales (ej: "Agent_1: Rolling")

---

## 11. Campos exportados pero no consumidos

| Campo | Dónde | Quién genera | Quién consume | Estado | Impacto |
|-------|-------|-------------|--------------|--------|---------|
| `conexiones_verticales` | JSON raíz | SpatialEngine | Nadie | Infraestructura | No afecta simulación actual |
| `adyacencia_fisica` | conexiones_horizontales | SpatialEngine | Nadie | Documentación | Aumenta tamaño de JSON sin valor |
| `color` | conexiones_horizontales | SpatialEngine | Nadie | Visualización | Solo útil en SpatialEngine UI |
| `estilo` | conexiones_horizontales | SpatialEngine | Nadie | Visualización | Solo útil en SpatialEngine UI |
| `categoria` | espacios_navegables[].atributos | SpatialEngine | Nadie | Documentación | Descriptiva, no funcional |
| `clase_indoor` | espacios_navegables[].atributos | SpatialEngine | Nadie | Semántica | Base para futuro IndoorGML |

**Impacto en tamaño de JSON:**
- Estos campos suponen ~15-20% del tamaño total
- Potencial optimización futura: opcionales o separados a metadata file

---

## 12. Campos consumidos por EvacEngine que Spatial debe garantizar

| Campo | Nivel | Qué ocurre si falta | Riesgo |
|-------|-------|------------------|--------|
| `configuracion.ancho` | Crítico | Crash en ModeloAvanzado.__init__ | ✗ FATAL |
| `configuracion.alto` | Crítico | Crash en ModeloAvanzado.__init__ | ✗ FATAL |
| `espacios_navegables` | Crítico | Crash al iterar hitos | ✗ FATAL |
| `espacios_navegables[*].centroide` | Crítico | KeyError en pathfinding | ✗ FATAL |
| `espacios_navegables[*].poligono` | Crítico | Crash en LineString/Polygon | ✗ FATAL |
| `espacios_navegables[*].atributos` | Crítico | Assume {} vacío, no falla | ✓ Tolerante |
| `espacios_navegables[*].atributos.locomotion` | Importante | Se trata como `[]`; Rolling queda restringido, Walking no se bloquea explícitamente | ⚠ Degradación |
| `muros` | Importante | Sin geometría de colisión física el motor puede ejecutarse, pero la validez espacial y las restricciones de movimiento quedan comprometidas | ⚠ Semántico |
| `muros[*].tipo` | Importante | Filtra solo ext/int, ignora el resto | ⚠ Degradación |
| `muros[*].poligono` | Crítico | Crash en Polygon() o intersection | ✗ FATAL |
| `conexiones_horizontales` | Crítico | Grafo sin aristas, todos aislados | ✗ FATAL |
| `conexiones_horizontales[*].origen/destino` | Crítico | KeyError en nodos del grafo | ✗ FATAL |
| `conexiones_horizontales[*].tipo` | Importante | Filtra solo navegable/door_to_door, ignora adyacencia | ⚠ Degradación |
| `conexiones_horizontales[*].contexto` | Importante | Missing en door_to_door → None, sin expansión semántica | ⚠ Degradación |
| `agentesspawn` | Importante | Assume [], no hay agentes (simulación vacía) | ⚠ Degradación |

---

## 13. Acoplamientos y riesgos actuales

### 13.1. Acoplamientos por nombres de nodos

**String matching en EvacEngine:**

```python
# En verificar_salida()
nodos_salida = [pos for n, pos in self.model.hitos.items() if 'Salida' in n]

# En visualization
if not any(palabra in nombre for palabra in ['Salida', 'Puerta', 'Frontera']):
    # Dibujar como centro de habitación
```

**Riesgo:** Si los nombres de espacios no contienen estas palabras clave, la lógica se rompe.

**Mitigación:** Documentar convención de nombres obligatoria:
- `Habitacion_*` para habitaciones
- `Puerta_*` para puertas
- `Salida_*` para salidas (obligatorio ≥ 1)
- `Frontera_virtual_*` para fronteras

---

### 13.2. Dependencia de `locomotion` array

**En EvacEngine:**
```python
locomotion = datos_espacio['atributos'].get('locomotion', [])
if "Rolling" not in locomotion:
    # Zona prohibida para Rolling
```

**Riesgo:** 
- Valor faltante → se trata como `[]`, por lo que Rolling queda restringido
- Array vacío `[]` → Rolling no está permitido en esa zona
- Typo en "Walking" vs "walking" → ruptura de lógica

**Mitigación:** Normalizar y documentar valores exactos permitidos:
- `"Walking"` (estándar)
- `"Rolling"` (silla de ruedas)
- `"Step"` (escaleras, penaliza velocidad)

---

### 13.3. Estructura de `poligono` crítica

**Esperado:**
```python
poligono = [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
Polygon(poligono)  # Valida geometría Shapely
```

**Riesgo:**
- Orden de vértices incorrecto (horario vs antihorario) → Shapely comportamiento indefinido
- Vértices colineales → Polygon válido pero sin area
- Vértices duplicados al inicio/fin → Shapely lo tolera

**Mitigación:** Documentar que Shapely espera geometría simple, válida, no degenerada y sin autointersecciones

---

### 13.4. Rutas hardcodeadas (2 locaciones)

**En MLSM_EvacEngine.py:**
```python
ruta_escenario = os.path.join(BASE_DIR, "escenarios", "v3_TEST5_FINAL.json")
```

**En MLSM_SpatialEngine.py:**
```python
carpeta_destino = os.path.join(directorio_script, "escenarios")
```

**Riesgo:** 
- Cambios de estructura de carpetas rompen ejecución
- No hay parametrización CLI

**Futuro:** Considerar variable de entorno o archivo `.env`

---

### 13.5. Pesos dinámicos en pathfinding

**Observación:**
- El JSON v1 serializa el tipo de conexión y los nodos, pero no almacena pesos explícitos por arista.
- En `construir_grafo_desde_json()`, EvacEngine calcula los pesos a partir de la distancia entre centroides y del `tipo` de conexión.
- El motor puede actualizar esos pesos dinámicamente con congestión en `actualizar_pesos_congestion()`.

**En construir_grafo_desde_json():**
```python
if conn['tipo'] == 'door_to_door':
    peso = distancia * 0.8   # Favorecido
else:
    peso = distancia * 1.5   # Penalizado
```

**Riesgo:**
- Pesos implícitos en código, no en datos
- Cambios en la heurística requieren editar EvacEngine
- No hay forma de ajustar los coeficientes sin cambiar el motor

**Futuro:** Parametrizar en `configuracion` o `conexiones_horizontales`

---

### 13.6. Falta de validación de entrada

**Estado actual:**
- No hay verificación de que `centroide` esté dentro de su `poligono`
- No hay verificación de intersecciones entre muros
- No hay verificación de que salidas sean alcanzables

**Impacto:** Errores silenciosos → comportamiento inesperado en simulación

---

## 14. Mapeo preliminar con IndoorGML/IndoorJSON

Comparación de conceptos entre JSON MLSM v1 actual y estándares de referencia:

| Elemento JSON MLSM v1 | Uso actual | Equivalencia potencial IndoorGML/IndoorJSON | Estado de soporte | Brecha |
|-------------------|-----------|-----------------------------------|-----------------|-------|
| `espacios_navegables` | Diccionario de espacios | `IndoorFeature` / `CellSpace` | ✓ Parcial | Sin jerarquía de categorías |
| `centroide` | Anclaje de pathfinding / nodo en el espacio dual | `Node` en el espacio dual de rutas | ✗ N/A | Punto de referencia en lugar de entidad espacial completa |
| `poligono` | Límite 2D de espacio | `gml:Polygon` / `gml:Surface` | ✓ Sí | Solo 2D, sin Z |
| `locomotion` | Atributo de accesibilidad | `accessibility` / `spaceType` | ✓ Incipiente | No normalizado a vocab estándar |
| `clase_indoor` | Clasificación semántica | `class` (NavigableSpace, TransferSpace, ObjectSpace) | ✓ Conceptual | Sin enumeración formal |
| `conexiones_horizontales[navegable_puerta]` | Grafo de navegación | `CellBoundary` / `Edge` de adyacencia | ✓ Equivalente | Simplificado |
| `conexiones_horizontales[door_to_door]` | Conexión interna entre puertas | `Edge` de granularidad fina / arista interna | ~ Parcial | Concepto de contexto local no estandarizado |
| `conexiones_verticales` | Inter-layer (reservado) | `InterLayerConnection` | ✗ Reservado | Infraestructura no activa |
| `muros` | Geometría de colisión CSG | `CellBoundary` / `NonNavigableBoundary` / geometría auxiliar | ✓ De facto | No es una feature topológica primaria, sirve de colisión |
| `agentesspawn` | Posiciones iniciales | N/A en IndoorGML | ✗ Fuera scope | Dominio específico de simulación |
| `configuracion` | Metadatos del mapa | `gml:Envelope` / metadatos | ✓ Equivalente | Mínimo (solo ancho/alto) |

**Conclusión:** MLSM v1 es una **simplificación funcional** de conceptos IndoorGML, optimizada para simulación, no para georreferenciación.

---

## 15. Limitaciones del schema MLSM v1 y requisitos a considerar

### 15.1. Soporta

✓ Mapas 2D de un solo nivel
✓ Espacios poligonales con atributos de accesibilidad
✓ Grafo de navegación multicapa (MACRO/MESO/MICRO)
✓ Geometría de colisión Shapely (CSG con restas booleanas)
✓ Centroides como puntos de enrutamiento
✓ Atributos de locomoción (Walking, Rolling, Step)
✓ Pesos en aristas calculados en EvacEngine, no serializados explícitamente en JSON
✓ Múltiples salidas
✓ Agentes con perfiles estocásticos

### 15.2. NO soporta

✗ **Varias plantas (Z):** Sin coordenada vertical, sin escaleras ni ascensores como entidades primarias
✗ **Coordenada Z:** Mapas 100% 2D
✗ **Escaleras como entidades de primer orden:** Solo como atributo `locomotion: ["Step"]`
✗ **Rampas:** No hay soporte especial, solo velocidad reducida
✗ **Ascensores:** Sin modelo de transporte vertical
✗ **Ventanas:** No hay modelo de transparencia o vista externa
✗ **Balizas (beacons):** Sin puntos de referencia dinámicos o señalización
✗ **Agentes con perfiles detallados:** Solo 3 perfiles genéricos (Walking, Rolling, Elderly)
✗ **Lectura de sensores ambientales:** Sin temperatura, humo, luz
✗ **Rutas alternativas pre-calculadas:** Solo Dijkstra en tiempo de ejecución
✗ **Compatibilidad formal con IndoorGML/IndoorJSON:** Conceptual sí, pero no validada todavía contra los schemas oficiales
✗ **Aplicación móvil/portable:** No hay serialización optimizada para dispositivos

### 15.3. Requisitos para MLSM v2 (no diseñar aquí, solo señalar)

- [ ] Soporte de coordenada Z y múltiples plantas
- [ ] Escaleras, rampas, ascensores como entidades explícitas
- [ ] Validación de entrada (schema.json formal)
- [ ] Normalización de nombres de nodos (enum obligatorio)
- [ ] Parametrización de pesos de Dijkstra
- [ ] Perfiles de agentes más detallados (edad, movilidad, visión, velocidad)
- [ ] Lecturas ambientales (calor, humo, luz) → Visión de agentes
- [ ] Exportación a IndoorGML/GeoJSON validado
- [ ] Pre-cálculo de rutas alternativas
- [ ] Compatibilidad con aplicaciones móviles (tamaño optimizado)

---

## 16. Checklist para validar un JSON MLSM v1

Antes de usar un archivo JSON MLSM v1 en EvacEngine:

### Estructura raíz
- [ ] `configuracion` presente con `ancho` y `alto` > 0
- [ ] `espacios_navegables` es un diccionario (no vacío)
- [ ] `conexiones_horizontales` es un array (puede estar vacío, pero riesgoso)
- [ ] `muros` es un array (puede estar vacío, pero riesgoso)
- [ ] `agentesspawn` es un array (puede estar vacío)
- [ ] `conexiones_verticales` presente (puede estar vacío)

### Espacios navegables
- [ ] Cada espacio tiene `centroide: [x, y]` válido
- [ ] Cada espacio tiene `poligono: [[x,y], ...]` con ≥ 3 vértices
- [ ] Cada espacio tiene `atributos` (puede estar vacío)
- [ ] Al menos un espacio contiene `"Salida"` en su nombre
- [ ] `locomotion` array solo contiene valores: "Walking", "Rolling", "Step"
- [ ] Todos los `centroide` están dentro de `configuracion.ancho × configuracion.alto`

### Conexiones horizontales
- [ ] Cada conexión tiene `origen` y `destino` que existen en `espacios_navegables`
- [ ] `tipo` es uno de: "navegable_puerta", "door_to_door", "adyacencia_fisica"
- [ ] Si `tipo == "door_to_door"`, entonces `contexto` existe en `espacios_navegables`

### Muros
- [ ] Cada muro tiene `id`, `tipo`, `poligono`
- [ ] `tipo` es uno de: "muro_exterior", "muro_interior", "puerta_simple", "puerta_doble", "salida", "frontera_virtual"
- [ ] `poligono` tiene ≥ 3 vértices
- [ ] Los polígonos son valid según Shapely (sin self-intersections)

### Agentes spawn
- [ ] Cada posición `[x, y]` está dentro del mapa
- [ ] Cada posición NO está dentro de un `muro` (tipo exterior/interior)
- [ ] Número de agentes es razonable (< 10000)

### Warnings (no fatales, pero revisar)
- [ ] ¿Hay espacios sin `centroide`? → Buscar en logs "KeyError"
- [ ] ¿Hay conexiones a espacios inexistentes? → Buscar "nodes not in graph"
- [ ] ¿Hay polígonos con área muy pequeña? → Potential geometry issues
- [ ] ¿La proporción de puerta:habitación es sensata? (ratio > 0.2 es raro)

---

## 17. Ejemplo completo de validación

**JSON mínimo válido:**
```json
{
  "configuracion": {"ancho": 10, "alto": 10},
  "conexiones_horizontales": [
    {"origen": "Habitacion_1", "destino": "Puerta_simple_1", "tipo": "navegable_puerta"},
    {"origen": "Puerta_simple_1", "destino": "Salida_1", "tipo": "navegable_puerta"}
  ],
  "conexiones_verticales": [],
  "espacios_navegables": {
    "Habitacion_1": {
      "centroide": [5, 5],
      "poligono": [[0, 0], [10, 0], [10, 10], [0, 10]],
      "atributos": {"locomotion": ["Walking", "Rolling"]}
    },
    "Puerta_simple_1": {
      "centroide": [8, 5],
      "poligono": [[7.75, 4.5], [8.25, 4.5], [8.25, 5.5], [7.75, 5.5]],
      "atributos": {"locomotion": ["Walking"]}
    },
    "Salida_1": {
      "centroide": [9, 5],
      "poligono": [[8, 4], [10, 4], [10, 6], [8, 6]],
      "atributos": {"locomotion": ["Walking"]}
    }
  },
  "muros": [
    {"id": "Muro_exterior_1", "tipo": "muro_exterior", "poligono": [[0, 0], [10, 0], [10, 0.2], [0, 0.2]]}
  ],
  "agentesspawn": [[5, 5]]
}
```

**Validación:**
✓ Configuracion: 10 × 10
✓ Espacios: Habitacion_1, Puerta_simple_1 y Salida_1; la salida se detecta por nombre que contiene "Salida"
✓ Conexiones: Habitacion_1 → Puerta_simple_1 → Salida_1
✓ Muro exterior: una franja para cerrar el mapa
✓ Agente: 1 en posición [5, 5]

**Resultado esperado:** Simulación ejecutable, 1 agente evacua rápidamente.

---

## 18. Referencias

### Códigos fuente auditados
- `src/MLSM_SpatialEngine.py` (líneas 703-770: `exportar_mlsm_core`)
- `src/MLSM_EvacEngine.py` (líneas 45-175: ingesta)

### Ejemplos JSON
- `baseline/scenario_v0_existing.json` (escenario de baseline v0)
- `baseline/scenario_v1_manual_spatial_FINAL.json` (escenario de baseline v1)

### Esquemas de referencia (no implementados aún)
- `indoorjson.core.schema.json`
- `indoorjson.navi.schema.json`

### Documentación generada por este proyecto
- `src/docs/01_Arquitectura_EvacEngine.md`
- `src/docs/01_Arquitecture_SpatialEngine.md`

---

## 19. Historial de cambios

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | 2026-05-25 | Auditoría inicial de MLSM v1 |

---

**Documento generado como parte de Fase 1: Auditoría de schema JSON MLSM v1**
