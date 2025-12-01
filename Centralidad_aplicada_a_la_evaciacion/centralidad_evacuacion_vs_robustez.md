# Robustez de Ruta vs Centralidad de Evacuación  
**Discusión, análisis comparativo y conclusiones**

---

## 1. Introducción
En el marco de la optimización de rutas de evacuación en espacios cerrados, hemos discutido en detalle dos conceptos clave:

- **Robustez de una ruta**: métrica implementada en el sistema actual, que mide la tolerancia de una ruta frente a fallos de sus aristas.  
- **Centralidad de evacuación** (*Evacuation Centrality*): métrica propuesta en la literatura académica (Lujak & Giordani, 2018), que mide la importancia de un nodo en función de la disponibilidad de rutas alternativas eficientes y disímiles hacia salidas seguras.

Ambas métricas buscan capturar la **resiliencia y adaptabilidad** de las rutas de evacuación, pero lo hacen desde perspectivas distintas.

---

## 2. Definición de Robustez de Ruta

### 2.1. Proceso iterativo
1. Se toma una **ruta base** π₀ con coste \(C₀\).  
2. Para cada **arista e ∈ π₀**:  
   - Se elimina temporalmente \(e\) del grafo.  
   - Se recalcula la mejor ruta alternativa con NetworkX (Dijkstra, A*, Yen, etc.).  
   - Se obtiene el nuevo coste \(C_e\).  
3. **Criterio de robustez**:  
   - Si \(C_e \le (1+τ)\cdot C₀\) → la arista se considera **robusta**.  
   - Si no existe alternativa aceptable → la arista se considera **frágil**.  
4. **Resultado**:  
   

\[
   R(\pi₀) = \frac{\#\{\text{aristas robustas}\}}{\#\{\text{aristas totales}\}}
   \]



### 2.2. Intuición
- Una ruta con \(R(\pi) \approx 1\) → muy estable, tolera fallos.  
- Una ruta con \(R(\pi) \approx 0\) → frágil, cualquier fallo obliga a replanificar.  

---

## 3. Definición de Centralidad de Evacuación

### 3.1. Según Lujak & Giordani (2018)
- **Unidad de análisis**: el **nodo**.  
- **Definición**: número de rutas **eficientes y suficientemente disímiles** que parten de un nodo hacia salidas seguras.  
- **Objetivo**: medir la **capacidad de re‑encaminarse** desde un nodo intermedio en caso de contingencia.  
- **Formalización**: se formula como un problema de **máximo flujo de rutas disímiles** (idealmente arc‑disjoint).  

### 3.2. Relación con la agilidad
La **agilidad de una ruta** se define como la media o producto de las centralidades de evacuación de sus nodos intermedios.  


\[
\Delta(\pi) = \Bigg(\prod_{v \in \pi \setminus \{s,t\}} C_\epsilon(v)\Bigg)^{1/|\pi|-2}
\]



---

## 4. Similitudes en el proceso iterativo

### 4.1. Robustez de ruta
- Itera sobre **aristas** de la ruta base.  
- Elimina una arista y recalcula.  
- Marca la arista como robusta si existe alternativa aceptable.  

### 4.2. Centralidad de evacuación (visión práctica)
- Itera sobre **nodos**.  
- Desde un nodo, busca rutas alternativas eficientes hacia salidas.  
- Cuenta cuántas rutas disímiles existen dentro de la tolerancia.  

**Similitud**: ambos procesos son **iterativos** y consisten en “simular fallos y buscar alternativas”.  
**Diferencia**: cambia la **unidad de análisis** (aristas de una ruta vs nodos del grafo).

---

## 5. Diferencias clave

| Aspecto | Robustez de ruta | Centralidad de evacuación |
|---------|------------------|---------------------------|
| Unidad de análisis | Ruta completa | Nodo |
| Iteración | Eliminar aristas de la ruta base | Buscar rutas alternativas desde un nodo |
| Resultado | Proporción de aristas robustas | Nº de rutas eficientes y disímiles |
| Naturaleza | Índice de tolerancia a fallos | Métrica estructural de adaptabilidad |
| Nivel | Global (ruta) | Local (nodo) |

---

## 6. Matiz importante
- En **robustez**, solo se eliminan **una a una** las aristas de la ruta base.  
- En **centralidad de evacuación**, se pueden considerar **múltiples eliminaciones** y rutas alternativas más disímiles, incluso en varios niveles.  
- Por tanto, la centralidad de evacuación es **más general y compleja**, mientras que la robustez es una **aproximación práctica y simplificada**.

---

## 7. Conclusión

- La **robustez de ruta** y la **centralidad de evacuación** comparten un **proceso iterativo análogo**: eliminar elementos y comprobar si existen alternativas aceptables.  
- La diferencia fundamental está en la **unidad de análisis**:  
  - Robustez → aristas de una ruta concreta.  
  - Centralidad de evacuación → nodos y sus rutas alternativas.  
- La robustez puede verse como una **aproximación práctica** a la agilidad, mientras que la centralidad de evacuación es la **formulación teórica formal** que fundamenta esa agilidad.  
- En términos de TFG:  
  - **Robustez** = índice operativo, fácil de implementar con NetworkX.  
  - **Centralidad de evacuación** = métrica académica más rica, que justifica conceptualmente la noción de **agilidad** en rutas de evacuación.  

---

## 8. Referencia principal
- Marin Lujak, Stefano Giordani. *Centrality measures for evacuation: Finding agile evacuation routes*. Future Generation Computer Systems, Vol. 83, 2018, pp. 401–412.

---
