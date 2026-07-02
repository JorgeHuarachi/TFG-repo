# CER / CRE — Referencia de decisiones y prompt para Codex

> Documento de referencia para fijar la definición de la **Centralidad de Evacuación por Reencaminamiento** sin perder la intención original del prototipo `obtencion_centralidad_CE.py`.

---

## 1. Idea central

La métrica busca medir, para cada nodo de un grafo de evacuación, **cuántas alternativas de evacuación válidas mantiene ese nodo hacia una o varias salidas cuando se fuerzan rutas alternativas mediante la eliminación de aristas o recursos y posterior replanificación**.

La eliminación de aristas tiene una doble lectura:

1. **Lectura dinámica:** simula fallos, bloqueos o indisponibilidad de transiciones durante una evacuación.
2. **Lectura estructural:** fuerza al algoritmo a encontrar rutas disímiles respecto a una ruta ya conocida.

Por tanto, la medida no es solo robustez de una ruta concreta. Es una medida **nodal**: el valor se asigna al nodo origen y se calcula respecto a cada salida segura.

Nombre recomendado para memoria:

```text
Centralidad de Evacuación por Reencaminamiento
```

Nombre recomendado para código:

```python
rerouting_evacuation_centrality
```

Nombres de métricas preferidos:

```text
distinctRoutes
acceptedCases
totalCases
failureProfile
weightedScore
coverage
```

Evitar nombres demasiado largos como `CER_total_distinct`; se prefiere `distinctRoutes`.

---

## 2. Qué parte viene del prototipo `obtencion_centralidad_CE.py`

El prototipo contiene la intención principal de la métrica:

### `Agrupacion(camino)`

Convierte una ruta en una lista de aristas consecutivas:

```text
[0, 4, 6] -> [(0,4), (4,6)]
```

En EvacEngine esto debe traducirse a una función tipo:

```python
path_to_edges(path)
path_to_resources(path, graph)
```

### `quitar_k_aristas(matriz, indices, k)`

Elimina combinaciones de `k` aristas. En el prototipo trabaja sobre matrices y anula ambos sentidos:

```text
matriz[i,j] = 0
matriz[j,i] = 0
```

En EvacEngine debe traducirse a:

```text
failedResources
failedArcs
failureUnit = "resource" | "arc" | "undirected_connection"
```

La opción preferida para el sistema real es:

```text
failureUnit = "resource"
```

porque si falla una puerta, ventana, rampa, escalera o transferencia, normalmente falla el recurso físico completo, no solo un arco dirigido.

### `Caminos_diferentes(...)`

Contiene la lógica base:

1. Filtra aristas por seguridad mínima.
2. Calcula ruta mínima desde cada origen hacia cada destino seguro.
3. Define un umbral fijo de tolerancia:

   ```text
   costeMax = costeBase * (1 + f_tolerancia)
   ```

4. Elimina aristas de la ruta.
5. Recalcula rutas.
6. Acepta rutas si no superan `costeMax`.
7. Guarda rutas estrictamente diferentes mediante `set(tuple(path))`.
8. Devuelve valores por nodo y por salida.
9. Prepara visualización con `FuncAnimation`.

La nueva implementación debe conservar esta intención, pero trasladada al grafo `multilevel_transfer_to_transfer` o, para pruebas controladas, al grafo pequeño del propio `.py`.

---

## 3. Grafo operativo

Para EvacEngine se usará:

```text
multilevel_transfer_to_transfer
```

O, más exactamente:

```text
snapshot ponderado derivado de multilevel_transfer_to_transfer
```

La métrica debe calcularse sobre el snapshot ya ponderado porque ahí ya están aplicados:

- movilidad;
- tiempo de paso;
- balizas;
- hazards;
- bloqueos;
- congestión, si está activada;
- atributo `weight` final.

Para la primera prueba controlada se puede usar el grafo de `obtencion_centralidad_CE.py`, porque es pequeño y permite observar cuándo explota la combinatoria y cuándo el árbol muere.

---

## 4. Definición formal

Para cada nodo origen `v` y cada salida segura `d`:

1. Calcular ruta base:

   ```text
   P0(v,d)
   ```

2. Calcular coste base:

   ```text
   C0(v,d)
   ```

3. Definir tolerancia fija:

   ```text
   gamma = 1 + tau
   Cmax(v,d) = gamma * C0(v,d)
   ```

4. Simular fallos de aristas o recursos.

5. Recalcular rutas.

6. Una ruta alternativa `P` es aceptada si:

   ```text
   cost(P) <= Cmax(v,d)
   ```

   y cumple las restricciones de seguridad/movilidad.

7. En modo exacto, una ruta cuenta como distinta si:

   ```python
   tuple(path) not in seenRoutes
   ```

8. El valor se asigna al nodo origen `v` y a la salida `d`.

---

## 5. Varias salidas

La función debe trabajar para varias salidas.

Si hay salidas:

```text
D = [d1, d2, d3]
```

entonces para cada nodo `v` se calcula:

```text
(v, d1)
(v, d2)
(v, d3)
```

excepto cuando:

```text
v == d
```

porque una salida no tiene centralidad hacia sí misma.

Ejemplos:

- Si hay 1 salida, cada nodo no salida tiene 1 conjunto de valores.
- Si hay 2 salidas, cada nodo no salida tiene 2 conjuntos de valores y cada salida tiene 1.
- Si hay 5 salidas, cada nodo no salida tiene 5 conjuntos de valores y cada salida tiene 4.

La estructura principal debe preservar los resultados por nodo y por salida.

Ejemplo orientativo:

```json
{
  "origin_0": {
    "targets": {
      "exit_6": {
        "failureProfiles": {
          "(1)": {
            "distinctRoutes": 2,
            "acceptedCases": 5,
            "totalCases": 7,
            "coverage": 0.714,
            "runtimeMs": 12.4,
            "maxDepthReached": 1
          },
          "(1,1)": {
            "distinctRoutes": 3,
            "acceptedCases": 4,
            "totalCases": 9,
            "coverage": 0.444,
            "runtimeMs": 18.7,
            "maxDepthReached": 2
          }
        },
        "summary": {
          "distinctRoutes": 5,
          "acceptedCases": 9,
          "totalCases": 16,
          "weightedScore": 3.5
        }
      },
      "exit_7": {
        "failureProfiles": {
          "(1)": {
            "distinctRoutes": 1,
            "acceptedCases": 2,
            "totalCases": 5,
            "coverage": 0.4
          }
        }
      }
    },
    "summary": {
      "bestTargetByDistinctRoutes": "exit_6",
      "bestTargetByCoverage": "exit_6"
    }
  }
}
```

`summary` es opcional y derivado. Lo principal es:

```text
origin -> target -> failureProfile
```

---

## 6. Métricas que se deben guardar

### `distinctRoutes`

Número de rutas distintas, válidas, seguras y dentro de tolerancia.

Es la métrica principal de centralidad.

Se calcula deduplicando por ruta exacta:

```python
seenRoutes.add(tuple(path))
```

### `acceptedCases`

Número de escenarios de fallo que producen una ruta válida, aunque esa ruta ya hubiese aparecido antes.

Mide resiliencia frente a casos de fallo.

### `totalCases`

Número total de casos de fallo evaluados.

Sirve para conocer la carga computacional y calcular cobertura.

### `coverage`

Proporción de casos resueltos:

```text
coverage = acceptedCases / totalCases
```

### `failureProfile`

Perfil bajo el que se obtiene la medida.

Ejemplos:

```text
(1)
(2)
(1,1)
(2,1)
(1,1,1)
```

### `weightedScore`

Valor secundario que pondera perfiles profundos o severos con menos peso.

Ejemplo:

```text
weightedScore = distinctRoutes(1) + 0.5 * distinctRoutes(1,1) + 0.25 * distinctRoutes(1,1,1)
```

Puede ser útil para ranking o para convertir la centralidad en penalización de aristas.

---

## 7. `distinctRoutes` vs `acceptedCases`

Ejemplo:

```text
fallo e1 -> ruta A válida
fallo e2 -> ruta A válida
fallo e3 -> ruta B válida
fallo e4 -> ruta C válida
```

Entonces:

```text
acceptedCases = 4
distinctRoutes = 3
```

Siempre se espera:

```text
distinctRoutes <= acceptedCases <= totalCases
```

Interpretación:

| Métrica | Qué mide |
|---|---|
| `distinctRoutes` | diversidad real de alternativas |
| `acceptedCases` | cantidad de escenarios de fallo resueltos |
| `totalCases` | esfuerzo total de exploración |
| `coverage` | fracción de fallos con solución válida |

---

## 8. Perfiles de fallo

Un perfil de fallo es una tupla de enteros:

```text
(k1, k2, ..., kn)
```

Cada posición representa una etapa de replanificación.

El valor `ki` indica cuántas aristas o recursos fallan simultáneamente en esa etapa.

Ejemplos:

### `(1)`

Fallo simple.

```text
fallo 1 recurso de la ruta base -> recalcular
```

### `(2)`

Shock simultáneo de dos recursos en la ruta base.

```text
fallan 2 recursos de la ruta base -> recalcular
```

### `(1,1)`

Fallo secuencial.

```text
fallo 1 recurso -> recalcular -> fallo 1 recurso de la nueva ruta -> recalcular
```

### `(2,1)`

Shock inicial doble y después degradación secuencial.

```text
fallan 2 recursos -> recalcular -> falla 1 recurso -> recalcular
```

### `(1,2)`

Fallo simple seguido de shock doble.

```text
falla 1 recurso -> recalcular -> fallan 2 recursos -> recalcular
```

Es válido matemáticamente, pero puede ser menos prioritario para la memoria.

---

## 9. Profundidad, orden total y simultaneidad máxima

### Profundidad

Longitud del perfil.

```text
(1)       profundidad 1
(1,1)     profundidad 2
(1,1,1)   profundidad 3
(2,1)     profundidad 2
```

### Orden total de fallo

Número total de recursos eliminados acumulados.

Es la suma del perfil.

```text
(1)       orden total 1
(2)       orden total 2
(1,1)     orden total 2
(2,1)     orden total 3
(3,2,1)   orden total 6
```

### Simultaneidad máxima

Mayor número de recursos eliminados en una misma etapa.

```text
(1,1,1)   simultaneidad máxima 1
(2,1)     simultaneidad máxima 2
(3)       simultaneidad máxima 3
```

Importante: `(1,1,1)` no tiene simultaneidad 3. Tiene tres fallos acumulados, pero ocurren de uno en uno.

---

## 10. Tolerancia fija

La tolerancia se mantiene fija respecto a la ruta base:

```text
Cmax = (1 + tau) * C0
```

Esto significa:

> Se aceptan solo alternativas razonables respecto a la mejor evacuación inicial desde el nodo.

No se debe actualizar la tolerancia en cada nivel, porque eso permitiría que rutas cada vez peores fueran aceptadas.

Ejemplo:

```text
C0 = 10
tau = 0.3
Cmax = 13
```

Si en nivel 1 se acepta una ruta de coste 13 y después se recalcula tolerancia sobre 13, el nuevo límite sería 16.9. Eso cambia la pregunta original.

Por tanto, la decisión es:

```text
tolerancia fija respecto a C0
```

---

## 11. Poda del árbol

La exploración se realiza sobre un snapshot fijo del grafo con pesos no negativos.

Si una rama ya supera el umbral:

```text
cost(P) > Cmax
```

se puede cortar la rama.

Justificación:

- eliminar más recursos reduce el conjunto de rutas disponibles;
- con pesos fijos y no negativos, el coste mínimo no puede mejorar al eliminar aristas;
- por tanto, si ya está fuera de tolerancia, ninguna extensión de esa rama debería volver a entrar.

Esto solo es estrictamente válido si:

- el snapshot está congelado;
- las eliminaciones solo quitan recursos/aristas;
- no se añaden nuevas aristas;
- no se reducen pesos dinámicamente durante el cálculo.

---

## 12. Estados visitados

Un estado debe definirse como:

```text
(origin, target, failedResources)
```

donde `failedResources` debe ser un conjunto inmutable:

```python
frozenset(failedResources)
```

Esto evita recalcular el mismo estado cuando se llega a él por distinto orden.

Ejemplo:

```text
rama A: falla recurso 1, luego recurso 2
rama B: falla recurso 2, luego recurso 1
```

Ambas llegan al mismo estado final:

```text
failedResources = {1, 2}
```

No tiene sentido recalcularlo dos veces.

### Ruta repetida pero estado distinto

Puede ocurrir:

```text
fallo A -> ruta R
fallo B -> ruta R
```

Entonces:

- no suma `distinctRoutes`, porque la ruta es repetida;
- sí suma `acceptedCases`, porque el caso de fallo fue resuelto;
- puede expandirse si el estado no se había visitado.

---

## 13. Algoritmo del árbol de reencaminamiento

Pseudocódigo:

```text
Input:
    G_snapshot
    origin v
    target d
    tau
    maxDepth
    maxK
    maxTotalFailures
    maxCombinations
    maxRuntimeMs

1. Calcular ruta base P0 = shortest_path(G, v, d)
2. Calcular C0 = cost(P0)
3. Cmax = (1 + tau) * C0
4. Crear estado raíz:
       failedResources = ∅
       path = P0
       profile = ()
       depth = 0

5. Inicializar:
       seenRoutes = set()
       visitedStates = set()
       queue = [root]

6. Mientras queue no esté vacía y no se supere maxRuntimeMs:
       state = queue.pop()

       para k en allowedKs:
           generar combinaciones de k recursos de state.path

           para cada combinación comb:
               F_new = state.failedResources ∪ comb

               si F_new ya está en visitedStates:
                   continuar

               marcar F_new como visitado
               totalCases += 1

               G_failed = G_snapshot sin recursos F_new
               intentar calcular P_new

               si no hay ruta:
                   noPathCases += 1
                   cortar rama

               si cost(P_new) > Cmax:
                   overToleranceCases += 1
                   cortar rama

               acceptedCases += 1

               si tuple(P_new) no está en seenRoutes:
                   seenRoutes.add(tuple(P_new))
                   distinctRoutes += 1

               registrar debug step

               si límites lo permiten:
                   añadir estado hijo a queue
```

---

## 14. Parámetros de control

### `maxDepth`

Longitud máxima del perfil.

```text
maxDepth = 3 permite perfiles como (1,1,1) o (2,1,1)
```

### `maxK`

Máximo número de fallos simultáneos en una etapa.

```text
maxK = 2 permite k=1 y k=2, pero no k=3
```

### `maxTotalFailures`

Número máximo total de recursos fallados acumulados.

```text
maxTotalFailures = 4
```

Permite:

```text
(1,1,1,1)
(2,1,1)
(2,2)
```

No permite:

```text
(2,2,1)
```

porque suma 5.

### `maxCombinations`

Número máximo de combinaciones evaluadas por estado.

Si una ruta tiene 20 recursos y `k=3`:

```text
C(20,3) = 1140
```

Eso puede ser demasiado. `maxCombinations` permite cortar o muestrear.

### `maxRuntimeMs`

Tiempo máximo total de cálculo.

Si se supera, se devuelve resultado parcial con:

```text
truncatedByRuntime = true
```

---

## 15. Perfiles recomendados

### Para memoria principal

Usar familias claras:

```text
(1)
(1,1)
(1,1,1)
```

Representan degradación secuencial simple.

```text
(2)
(2,1)
(2,1,1)
```

Representan un shock doble inicial y reencaminamiento posterior.

Opcional:

```text
(3)
(3,1)
```

### Para experimento controlado

En el grafo pequeño de `obtencion_centralidad_CE.py` se puede activar exploración más agresiva:

```text
maxK = 3 o más
maxDepth = 4 o más
maxTotalFailures = alto
maxCombinations = alto
```

Objetivo: observar cuándo explota la combinatoria y cuándo el propio árbol muere por ausencia de rutas o por tolerancia.

### Para grafo grande

Usar límites conservadores:

```text
maxK = 2
maxDepth = 3
maxTotalFailures = 4
maxCombinations = 100
maxRuntimeMs = definido
```

---

## 16. Media geométrica para agilidad de ruta

Una vez calculado `distinctRoutes` por nodo, se puede usar para valorar rutas.

Para una ruta:

```text
P = [v1, v2, v3, ..., vn]
```

la agilidad geométrica puede ser:

```text
agility(P) = exp(mean(log(1 + distinctRoutes(v)))) - 1
```

En fórmula:

\[
A(P)=
\exp\left(
\frac{1}{n}
\sum_{v\in P}
\ln(1+distinctRoutes(v))
\right)-1
\]

### Por qué no media aritmética

La media aritmética permite compensaciones fuertes.

Ejemplo:

```text
Ruta A: [10, 10, 10]
Ruta B: [30, 0, 0]
```

Media aritmética:

```text
A = 10
B = 10
```

Media geométrica:

```text
A = 10
B ≈ 2.14
```

La media geométrica penaliza rutas que atraviesan nodos sin alternativas, aunque tengan un nodo muy bueno.

Esto encaja mejor con la idea de agilidad: una ruta ágil debe mantener alternativas a lo largo del recorrido, no solo en un punto.

### Nodos cercanos a la salida

Los nodos cercanos a la salida tienden a tener `distinctRoutes = 0`, porque ya casi han evacuado y no necesitan muchas alternativas.

Para evitar penalizar artificialmente todas las rutas:

- excluir el nodo destino;
- opcionalmente excluir el último nodo antes del destino;
- o evaluar solo nodos intermedios relevantes.

Recomendación inicial:

```text
calcular agilidad sobre nodos intermedios, excluyendo la salida
```

---

## 17. Formas de usar la métrica en routing

### Opción A — selección sobre rutas candidatas

Recomendada para la memoria.

1. Generar rutas candidatas con Yen/k-rutas.
2. Filtrar rutas inseguras.
3. Filtrar rutas fuera de tolerancia.
4. Calcular agilidad geométrica con `distinctRoutes`.
5. Elegir la ruta más ágil.
6. Desempatar por menor coste.

Ventaja: clara y defendible.

### Opción B — penalización de aristas

Convertir centralidad en coste:

```text
penalty(v) = 1 / (1 + distinctRoutes(v))
```

Para una arista `(u,v)`:

```text
agilityCost(e) = penalty(v)
```

Peso final:

```text
weight' = weight + lambdaAgility * agilityCost
```

Ventaja: permite usar Dijkstra directamente.

Desventaja: mezcla centralidad global con coste local y requiere calibración.

---

## 18. Visualización/auditoría necesaria

Para el grafo pequeño de `obtencion_centralidad_CE.py`, interesa una visualización paso a paso.

Debe mostrar por pantalla o en HTML:

- origen;
- salida;
- ruta base;
- coste base;
- tolerancia;
- perfil actual;
- profundidad;
- combinación de aristas/recursos eliminados;
- número de combinaciones generadas;
- ruta recalculada;
- coste recalculado;
- si se acepta o se rechaza;
- motivo de rechazo:
  - `no_path`;
  - `over_tolerance`;
  - `duplicate_route`;
  - `visited_state`;
- `distinctRoutes` acumulado;
- `acceptedCases` acumulado;
- tiempo por estado;
- tiempo total.

Salida recomendada:

```text
cer_debug.json
cer_tree.html
cer_tree.gif
cer_summary.csv
```

---

## 19. Experimento controlado con el grafo del `.py`

Objetivo:

> Explorar la combinatoria en un grafo pequeño para decidir límites razonables antes de llevar la métrica al grafo grande de EvacEngine.

Pruebas recomendadas:

1. Elegir un nodo origen y una salida.
2. Elegir un nodo origen y varias salidas.
3. Activar modo exacto.
4. Probar `maxK = 1`, `maxDepth` alto.
5. Probar `maxK = 2`, `maxDepth` medio.
6. Probar `maxK = 3` en grafo pequeño.
7. Medir:
   - ramas evaluadas;
   - ramas muertas por `no_path`;
   - ramas muertas por `over_tolerance`;
   - rutas duplicadas;
   - rutas distintas;
   - tiempos.

Esto permitirá decidir si en el grafo grande se usan límites conservadores o si el propio árbol muere suficientemente rápido.

---

## 20. Qué puede sobrar o quedar para después

### Dejar para después

- modo `overlap`;
- perfiles muy complejos como `(2,1,2)`, `(3,3,1)`, `(1,2,2)`;
- integración completa con routing avanzado si primero se quiere auditar la métrica;
- penalización directa de aristas con CER.

### Mantener ahora

- modo exacto;
- varias salidas;
- tolerancia fija;
- árbol con poda;
- debug visual/auditable;
- métricas `distinctRoutes`, `acceptedCases`, `totalCases`, `coverage`;
- perfiles canónicos y modo experimental agresivo en grafo pequeño.

---

# Prompt para Codex

```text
Quiero que analices e implementes de forma controlada la métrica de Centralidad de Evacuación por Reencaminamiento usando primero el grafo pequeño de `obtencion_centralidad_CE.py`.

No empieces integrándolo directamente en EvacEngine. Primero quiero una herramienta de auditoría para entender la combinatoria, ver cuándo muere el árbol y medir tiempos.

## Contexto

La métrica no es simplemente robustez de ruta. Es una métrica nodal.

Para cada nodo origen `v` y cada salida `d`, se calcula cuántas rutas alternativas válidas y diferentes aparecen cuando se eliminan aristas/recursos y se recalcula ruta.

La eliminación de aristas tiene doble función:

1. simular fallos o bloqueos;
2. forzar rutas alternativas disímiles.

El modo inicial de diferencia de rutas será exacto:

```python
tuple(path)
```

El modo overlap puede quedar preparado, pero no es prioridad.

## Grafo inicial

Usa las matrices y coordenadas de `obtencion_centralidad_CE.py`:

- `matriz_costes`
- `matriz_seguridades`
- `coordenadas`
- `destinos_seguros`
- `f_tol`
- `f_sec`

Quiero que puedas seleccionar:

- un nodo origen;
- una salida;
- o varias salidas.

Si hay varias salidas, calcula resultados para cada par `(origin, target)`, excepto cuando `origin == target`.

## Definición

Para cada `(origin, target)`:

1. Calcula ruta base `P0`.
2. Calcula coste base `C0`.
3. Define:

```text
Cmax = (1 + tau) * C0
```

4. Construye un árbol de reencaminamiento.
5. En cada rama elimina aristas de la ruta activa según un perfil de fallo.
6. Recalcula ruta.
7. Acepta una ruta si:

```text
cost(path) <= Cmax
```

8. Deduplica rutas exactas con `tuple(path)`.

## Métricas

Usa estos nombres:

```text
distinctRoutes
acceptedCases
totalCases
coverage
failureProfile
weightedScore
```

No uses `CER_total_distinct`; prefiero `distinctRoutes`.

`distinctRoutes`: rutas diferentes, válidas y dentro de tolerancia.

`acceptedCases`: escenarios de fallo que producen ruta válida, aunque esté repetida.

`totalCases`: casos evaluados.

`coverage = acceptedCases / totalCases`.

## Árbol de búsqueda

Cada estado debe incluir:

```text
origin
target
failedEdges o failedResources
path actual
cost actual
failureProfile
depth
```

Guardar estados visitados por:

```python
(origin, target, frozenset(failedEdges))
```

Si una ruta es repetida pero el estado es nuevo:

- no sumar `distinctRoutes`;
- sí sumar `acceptedCases`;
- permitir expandir si no supera límites.

Si el estado ya fue visitado:

- no recalcular;
- registrar `visited_state`.

## Poda

Usar tolerancia fija respecto a `C0`.

Si no hay ruta:

```text
no_path -> cortar rama
```

Si `cost(path) > Cmax`:

```text
over_tolerance -> cortar rama
```

Justificación: en snapshot fijo con pesos no negativos, eliminar más aristas solo reduce el conjunto de rutas posibles; si la mejor ruta ya supera el umbral, sus extensiones no deberían volver a ser aceptables.

## Parámetros

Implementa o deja preparado:

```text
maxDepth
maxK
maxTotalFailures
maxCombinations
maxRuntimeMs
maxDistinctRoutes
```

Explica claramente qué hace cada uno.

## Perfiles

Quiero dos modos:

### Modo canónico

Reportar:

```text
(1)
(1,1)
(1,1,1)
(2)
(2,1)
(2,1,1)
```

### Modo experimental/exhaustivo para grafo pequeño

Permitir perfiles más agresivos hasta límites:

```text
maxK
maxDepth
maxTotalFailures
maxCombinations
maxRuntimeMs
```

La idea es observar cuándo explota la combinatoria y cuándo muere el árbol.

## Salida por pantalla

Quiero que imprima de forma auditable:

- origin;
- target;
- ruta base;
- coste base;
- Cmax;
- failureProfile;
- depth;
- combinación eliminada;
- número de combinaciones;
- ruta recalculada;
- coste recalculado;
- decisión: accepted / duplicate / no_path / over_tolerance / visited_state;
- distinctRoutes acumuladas;
- acceptedCases acumulados;
- totalCases;
- tiempo por paso;
- tiempo total.

## Salidas de archivo

Genera si es razonable:

```text
cer_debug.json
cer_summary.csv
cer_tree.html
cer_tree.gif
```

La visualización debe parecerse a la intención original del `.py`, pero más clara:

- grafo base en gris;
- ruta base destacada;
- aristas eliminadas tachadas o discontinuas;
- ruta alternativa aceptada en color destacado;
- ruta rechazada con otro estilo;
- panel con coste, tolerancia, perfil y contadores.

## Uso posterior para agilidad

Calcula o deja preparada la agilidad geométrica de una ruta:

```text
agility(P) = exp(mean(log(1 + distinctRoutes(v)))) - 1
```

Usar nodos intermedios de la ruta y excluir la salida. Opcionalmente permitir excluir también el nodo inmediatamente anterior a la salida si se observa que los valores CER caen naturalmente cerca del destino.

## Resultado esperado

Quiero una implementación/prototipo de auditoría sobre el grafo pequeño, no todavía una integración completa en EvacEngine.

Primero quiero entender:

1. qué perfiles producen rutas;
2. cuándo se corta el árbol;
3. cuántas combinaciones se generan;
4. cuánto tarda;
5. qué límites conviene usar en el grafo grande.
```
