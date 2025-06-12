# Recomendación de rutas de evacuación
## Primera aproximacion
### De todos a uno
En una primera aporximación hice una función que calculase los caminos minimos de todos a un nodo y los dibuje y todo en un grafico.
### Analisis resiliencia

Has planteado un algoritmo que:

Calcula el camino más corto (usando Dijkstra) entre un origen y una salida segura.

Luego genera alternativas quitando una o más aristas del camino principal.

Vuelve a calcular caminos para estudiar qué pasa si ese enlace se rompe (simulando bloqueos).

Filtra los nuevos caminos por tolerancia (coste) y seguridad.

Cuenta cuántos caminos “válidos” siguen existiendo, lo que usas para ponderar nodos.

Esto simula resiliencia: te dice qué tan robusta es una ruta si algo falla. En evacuaciones, esto es clave, y aunque lo hagas de forma manual y con bucles pesados, el razonamiento es sólido.

---

📌 Qué he entendido de tu propuesta (confirmación rápida)
Paso	Lo que haces	Lo que produce
1. Pre-filtrado por seguridad	Eliminas del grafo todas las aristas cuya «seguridad» < f_seguridad.	Un grafo “limpio” en el que solo quedan conexiones aceptables.
2. Bucle por destinos y orígenes	Para cada salida segura (destinos) y para cada nodo del grafo (nodos): si el nodo ≠ destino…	…calculas el camino mínimo principal con Dijkstra.
3. Cálculo de coste máximo	coste_max = coste_principal × (1 + f_tolerancia)	Sirve como umbral para aceptar rutas un poco más largas si son necesarias.
4. Búsqueda exhaustiva de alternativas (k-aristas)	- Tomas el camino mínimo.
- Generas todas las combinaciones posibles quitando k = 1 arista.
- Para cada combinación: vuelves a correr Dijkstra sobre el grafo resultante.	- Cuenta cuántas rutas «aceptables» (< coste_max) existen.
- Guarda cada ruta distinta en un set para no duplicar.
5. Búsqueda recursiva (nivel 2)	Para cada camino nuevo también quitas de nuevo 1 arista (nivel 2).	Añades alternativas de segundo nivel y sus contadores.
6. Salida	Muestras:
- el camino principal
- rutas alternativas
- nº de caminos aceptables (totales y estrictamente diferentes) por nodo/destino.	Tu idea es usar esos contadores como peso de resiliencia de cada nodo. Cuantos más caminos válidos salen de él, “mejor” nodo es para evacuar.

En palabras llanas:
Estás midiendo redundancia de rutas bajo fallos (bloquear aristas inseguras), y usas esa “redundancia” para puntuar nodos o decidir por dónde conviene pasar.

---

#### Cosas al respecto de esto

➡️ A corto plazo: sigue usándolo, pero con control.
➡️ A largo plazo: piensa en modelos más estructurados (ver abajo).


### Metricas intersantes

Para estudio y analisis
- Tu enfoque actual ya roza una idea muy importante: cuán crítica o sólida es una ruta o un nodo frente a fallos.

🔸 Centralidad de paso (Betweenness Centrality)
Calcula cuántos caminos mínimos entre pares de nodos pasan por ese nodo.

En evacuación, un nodo con alta centralidad puede ser un cuello de botella.

Puedes interpretarlo así:

🔺 Alta centralidad = crítico pero peligroso.

🔻 Baja centralidad = menos tráfico, útil como ruta alternativa.

🔸 Número de caminos mínimos alternativos (k-paths)
Para cada nodo:

¿Cuántos caminos distintos (no necesariamente disjuntos) te llevan desde ese nodo a una salida?

¿Y cuántos siguen funcionando si se rompe una conexión?

Esto ya lo haces con tu análisis exhaustivo. Puedes empaquetarlo y guardar el resultado como:

    G.nodes[n]['resiliencia'] = n_rutas_validas

🔸 Disjoint paths / rutas disjuntas
Estudia cuántos caminos independientes existen desde un nodo a la salida:

Completely disjoint: no comparten nodos.

Edge-disjoint: no comparten aristas.

Esto es muy útil en evacuación, porque simula redundancia total.
    nx.edge_disjoint_paths(G, source, target)
### F_tolerancia

🧮 2. Factor de tolerancia dinámico: ideas realistas
Tu idea de que el factor de tolerancia sea dinámico tiene mucho sentido. Algunas formas de definirlo en función del contexto:

🔹 Según la severidad del evento:
Si la situación es crítica, puede subir el nivel de tolerancia (aceptas caminos más largos).

Se puede definir como:

python
Copiar código
f_tolerancia = base_tolerancia + α * severidad_evento
Donde α es una constante (por ejemplo 0.2) y la severidad puede venir del evento registrado en la base de datos.

🔹 Según el perfil de movilidad del usuario:
Para personas con movilidad reducida, se puede bajar la tolerancia: no deben caminar más de lo necesario.

O al revés: si es un bombero o rescatista, puede tolerar más.

🔹 Según el número de rutas disponibles:
Si un nodo tiene pocas rutas disponibles, aumentar la tolerancia permite que tenga al menos opciones válidas.

Podrías usar:

python
Copiar código
f_tolerancia = max(0.3, 1 - (n_rutas_validas / rutas_esperadas))