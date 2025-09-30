## 5. Solución Técnica / Resultados

### 5.1 Diseño de la arquitectura distribuida (alto nivel)
- 5.1.1 Visión general y principios
- 5.1.2 Componentes
  - 5.1.2.1 Capa IoT/AmI (edge)
  - 5.1.2.2 Ingesta y Complex Event Processing (CEP)
  - 5.1.2.3 Servicio de grafo/rutas
  - 5.1.2.4 API del sistema
  - 5.1.2.5 Clientes y actuadores
- 5.1.3 Flujo de datos y actualización en tiempo real
- 5.1.4 Modelo de comunicación
- 5.1.5 Decisiones de diseño
- 5.1.6 Escalabilidad, disponibilidad y tolerancia a fallos
- 5.1.7 Seguridad y privacidad
- 5.1.8 Mapeo a estándares y compatibilidad
- 5.1.9 Roadmap técnico

### 5.2 Diseño e implementación del modelo de datos IndoorGML en PostgreSQL/PostGIS (BRUTO)
- 5.2.1 Objetivos y criterios de diseño
- 5.2.2 Requisitos a modelo conceptual
- 5.2.3 Modelo lógico: Mapeo IndoorGML 2.0 a relacional (PostgreSQL)
- 5.2.4 Modelo físico
- 5.2.5 Automatización y consistencia (funciones y triggers)
- 5.2.6 Rendimiento y escalabilidad
- 5.2.7 Integración con herramientas (QGIS/PostGIS)
- 5.2.8 Conformidad con IndoorGML 2.0 (y compatibilidad 1.1)
- 5.2.9 Lecciones y decisiones de diseño
- 5.2.10 Resumen operativo del SQL implementado
- 5.2.11 Trabajo futuro inmediato (en línea con IndoorGML 2.0 Part 1 y literatura)

### 5.3 Ingesta de sensores y Complex Event Processing (CEP) (BRUTO)
- 5.3.1 Propósito y alcance
- 5.3.2 Fuentes de datos y modelo de lectura
  - 5.3.2.1 Sensorica y transporte
  - 5.3.2.2 Contrato de evento (payload normalizado)
- 5.3.3 Persistencia y unión con IndoorGML
- 5.3.4 Motor CEP: Lecturas a cell_score
  - 5.3.4.1 Ventanas y noción de tiempo
  - 5.3.4.2 Reglas base (transparentes y auditables)
  - 5.3.4.3 Propagación espacial y reglas compuestas (opcional)
- 5.3.5 Conexión con el grafo IndoorGML (actualización en tiempo real)
- 5.3.6 Simulador de datos (estado actual del TFG)
- 5.3.7 Operación: latencias, backpressure y calidad de datos *(no incluido)*
- 5.3.8 Seguridad y privacidad
- 5.3.9 Observabilidad y replay
- 5.3.10 Ruta de producción
- 5.3.11 Relación con arquitectura CDA/URJC
- 5.3.12 Limitaciones y trabajo futuro

### 5.4 Algoritmo de recomendación de rutas (BRUTO)
- 5.4.1 Modelo de grafo y relación con IndoorGML
- 5.4.2 Métrica de coste y objetivos (tiempo, seguridad, redundancia)
- 5.4.3 Filtro previo por seguridad y por movilidad
- 5.4.4 Rutas base: Dijkstra/A* y salidas múltiples
- 5.4.5 Heurística de robustez (redundancia bajo fallos)
- 5.4.6 Personalización por perfil de usuario y contexto
- 5.4.7 Actualización dinámica y re-planificación
- 5.4.8 Salida del recomendador
- 5.4.9 Validación empírica (enlazado con 5.6)
  - 5.4.9.1 Implementación (resumen técnico reproducible)

### 5.5 Conexión BD ↔ motor de recomendación (NO QUZAS SE SUSTITUYA POR EL 6 QUE AQUI NO ESTA)
- 5.5.1 Contratos de datos (JSON) y endpoints (API REST/WS)
- 5.5.2 Consulta del grafo vía vistas; consistencia transaccional (*snapshot*)
- 5.5.3 Estrategias *pull*/*push* y cacheado
- 5.5.4 Gestión de errores y *fallbacks*

### 5.6 SIMULACIÓN Y VALIDACIÓN 
- 5.6.1 ...
- ... muchisimos apartados
- 5.6.10 ...