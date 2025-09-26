## ANEXO I: Normas de Presentación de la Memoria

### a) Formato general

La memoria deberá estar escrita en formato **DIN-A4**, con márgenes de **2,5 cm**, tipo y tamaño de letra legible (por ejemplo, *Times New Roman tamaño 11*), con **espaciado de 1,5 líneas**. La extensión máxima será de **75 páginas a una sola cara**, excluyendo los apéndices.


### b) Apartados obligatorios

La memoria incluirá, con carácter general, los siguientes apartados:

#### • Resumen (1–2 páginas)
Debe resumirse el contenido completo de la memoria, incluyendo:
- Justificación de la relevancia del trabajo realizado
- Objetivos planteados
- Principales logros alcanzados y/o hallazgos obtenidos
- Principales conclusiones

#### • Introducción (máximo 10 páginas)
Debe contextualizar el ámbito científico-tecnológico del TFG, mostrar el estado del arte y destacar la relevancia del trabajo desarrollado.

#### • Objetivos (1–2 páginas)
Debe incluir:
- Mención expresa de los objetivos del TFG
- Estructura del plan de trabajo
- Programación de actividades para alcanzar los objetivos

#### • Solución Técnica / Resultados
Este apartado constituye el **cuerpo principal** de la memoria. Debe incluir:
- Detalle de la solución técnica aportada
- Principales logros y hallazgos
- Interpretación y discusión de los resultados

#### • Conclusiones (1 página)
Síntesis final del trabajo y sus implicaciones.

#### • Bibliografía
Las referencias deben seguir el estilo descrito por la **norma ISO 690**.

#### • Apéndices
Se incluirá toda información útil para la evaluación del TFG que no sea esencial en el cuerpo principal. Ejemplos:
- Planos
- Presupuesto
- Estudio de seguridad
- Estudio de impacto ambiental (si procede)
- Metodología
- Estudios de viabilidad técnica y económica
- Estudios básicos de diseño, simulación y optimización

---

## Propuesta de Trabajo de Fin de Grado

**Nº:** 1  
**Especialidad:** Sistemas y Tecnologías de la Información  
**Título provisional:** Desarrollo de una Arquitectura Distribuida para la Recomendación de Rutas de Evacuación en Espacios Cerrados con Inteligencia Ambiental  
**Breve resumen (máx. 100 palabras):**  
Este proyecto se centra en el diseño de una arquitectura para la gestión de evacuaciones en entornos cerrados, junto con el desarrollo de una aplicación móvil que interactúe con sensores de proximidad (beacons) mediante comunicación inalámbrica. El objetivo es implementar un sistema de localización de evacuados en tiempo real, utilizando algoritmos de detección y seguimiento, que permita recomendar rutas de evacuación en entornos dinámicos e interconectados con Inteligencia Ambiental (AmI). Se abordarán desafíos como la coordinación de grandes flujos de personas, aplicando técnicas de procesamiento de eventos complejos para mejorar la eficacia del sistema en situaciones críticas.  
**Lugar de realización:** CETINIA, Universidad Rey Juan Carlos

---

## Links utilizados o consultados

En cuanto a la recomendación de rutas
Sobre el modelado o para el modelado de espacios interiores.

[A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches](https://www.mdpi.com/2220-9964/6/4/116#:~:text=indoor%20accessibility%20graph%20,edge%20may%20contain%20any%20additional)

[A "DOOR-TO-DOOR" PATH-FINDING APPROACH FOR INDOOR NAVIGATION](https://www.isprs.org/proceedings/2011/gi4dm/pdf/OP05.pdf#:~:text=introduced%20geometrical%20metric,Erickson%2C%201999%3B%20Choi%20%26%20Lee)

[Web para hacer diagrama BBDD bonitos](https://dbdiagram.io/home)

[Para hacer los datos geométricos y conectarlo a PostgresSQL usando PostGis](https://qgis.org/download/)

Sobre Modelado de Bases de datos de espacios interiores.

[Understanding IndoorGML](https://www.indoorgml.net/#:~:text=,position%20for%20more%20precise%20location)

1. Motivations
2. General Concepts of IndoorGML
3. Structured Space Model
4. Multi-Layered Space Model
5. External References
6. Anchor Node
7. Subspacing
8. Modularization

[Proposal of a spatial database for indoor navigation](https://periodicos.uem.br/actascitechnol/index.php/ActaSciTechnol/article/view/51718/751375152299)

- Database design and implementation

[Proposition of a Schematization Plugin for QGIS](https://ica-abs.copernicus.org/articles/1/23/2019/ica-abs-1-23-2019.pdf)

Aqui dibuja una linea central en los pasillos,


Estandares proximos? de modelado de espacios indoor como modelos relacionales

[Towards indoorgml 2.0](https://repository.tudelft.nl/record/uuid:3f2a31d9-043a-4141-a084-3ba87944cd7a)

En esete caso estudiar de que trata este paper, que propuestas tienen y compara con nuestra base de datos, ver posibles mejores o posibles adaptaciones.

Revisa el artículo “Towards IndoorGML 2.0: Updates and Case Study Illustrations” (TU Delft Repository), que detalla los cambios propuestos y muestra ejemplos de implementación en SQL y JSON

[Understanding IndoorGML](https://www.indoorgml.net/)

Este se repite, bastante interesante en teoria.
Consulta la sección Document Schemas en la web oficial de IndoorGML (OGC), donde encontrarás los XSD y los nuevos scripts de SQL/JSON para 2.0

[Mas cosas](https://docs.ogc.org/is/19-011r4/19-011r4.html#toc14)


---

## Desarrollo del Proyecto

Hasta el momento he realizado tanto el modelado como la creación de una base de datos siguiendo parcialmente el estándar **IndoorGML**. La estructura de archivos SQL que he utilizado es la siguiente:

```
/sql/
├── 00_create_database.sql         ← (opcional) crea la base si no existe
├── 01_schemas.sql                 ← esquemas si se usan (ej.: public, gis, etc.)
├── 02_tables_core.sql            ← tablas principales (usuarios, áreas, etc.)
├── 03_tables_relacionales.sql    ← tablas intermedias, relaciones N:M
├── 04_views.sql                  ← vistas
├── 05_functions.sql              ← funciones PL/pgSQL (ej.: triggers)
├── 06_triggers.sql               ← triggers conectados a funciones
├── 07_indexes.sql                ← índices
├── 08_sample_data.sql            ← datos de prueba (si se desea)
```

Además, he elaborado varios diagramas de flujo para representar distintos procesos:

```
%% Diagramas realizados
- Diagrama ER de la base de datos
- Diagrama de flujo de la lógica de validación y reconstrucción de cellBoundary
- Reconstrucción de límites (cellBoundary) a partir de cellSpace
- Criterio geométrico para decidir si las nuevas geometrías son válidas dentro de una misma planta
- Otros diagramas en proceso dentro del propio PostgreSQL
```

La base de datos (PostgreSQL + PostGIS + QGIS) no solo gestiona los datos IndoorGML en 2D, sino que también está preparada para almacenar las lecturas de las balizas instaladas en cada sala (aunque aún no he terminado de crear esta parte físicamente).

Una vez tenga un conjunto de datos de ejemplo (IndoorGML + Navigation + balizas modeladas), crearé un script que inserte lecturas simuladas de balizas. Esto permitirá observar cómo varían las variables ambientales en las distintas salas. Esta parte está pendiente de implementación.

---

## Algoritmo de Recomendación de Rutas

En paralelo, he estado desarrollando una propuesta para la recomendación de rutas de evacuación. He implementado un código en Python que incluye varias funciones, entre ellas una función principal que realiza una búsqueda heurística exhaustiva sobre un grafo de ejemplo. El funcionamiento general es el siguiente:

1. Parto de una **matriz de adyacencia** que representa las conexiones entre salas del edificio. El peso de cada arista representa el tiempo estimado de desplazamiento.
2. Utilizo una segunda matriz del mismo tamaño que representa la **seguridad** de cada sala, con valores numéricos.
3. Aplico un **filtro de seguridad**: elimino las salas o conexiones cuya seguridad esté por debajo de un umbral definido.
4. Esta matriz de seguridad debería ser el resultado de un sistema de **procesamiento de eventos complejos (CEP)** que actualiza los valores en tiempo real según el flujo de datos de cada sala.

---

### Búsqueda heurística (recomendación basada en redundancia)

La búsqueda heurística que me propuso mi tutor funciona así:

- Se define uno o varios nodos como **salidas de emergencia** (targets).
- Para cada nodo del grafo (source), se calcula el **camino mínimo** hacia el target.
- Se guarda el coste de ese camino.
- Se elimina una arista del grafo y se recalcula el camino mínimo desde el mismo nodo.
- Se compara el nuevo coste con el original usando un **factor de tolerancia**.
  - Si el nuevo coste está dentro del margen, se suma +1.
  - Si no, no se contabiliza.
- Al repetir este proceso para todas las aristas, se obtiene una **medida de redundancia**: cuántos caminos alternativos siguen siendo viables desde ese nodo.
- Este valor puede usarse para **ponderar la calidad del nodo** como punto de evacuación.

En resumen: se mide la **robustez de las rutas** ante fallos o bloqueos, y se utiliza esa información para recomendar caminos más seguros y resilientes.

---

## Ideas para mejorar la recomendación

Aunque aún no he avanzado mucho en la parte de aplicación práctica, tengo algunas ideas para enriquecer el sistema de recomendación:

- **Filtro de movilidad**: tener en cuenta rampas, escaleras, accesibilidad.
- **Filtro de criticidad**: si la situación es extremadamente crítica, permitir rutas alternativas como ventanas o accesos no convencionales.
- **Filtro de seguridad ambiental**: basado en las lecturas de sensores (temperatura, humo, etc.).

Una vez conecte la base de datos con el motor de recomendación, podré realizar un **simulacro o ejemplo de uso** que combine todos estos factores.

---

## LO QUE QUIERO

Quiero que me ayudes a decidir qué apartados incluir, qué contenido va en cada uno, y cómo priorizar mi tiempo según lo que ya he hecho. No quiero que me lo redactes todo de golpe, sino que me guíes paso a paso.

Búscame TFGs similares al mío (IndoorGML, evacuación inteligente, arquitectura distribuida) y ayúdame a comparar sus estructuras y enfoques.

---
---
---

¡Jorge, esto está muy bien planteado! Has reunido toda la información clave de tu TFG en un solo bloque, lo que te permite construir sobre una base sólida. Ahora vamos a crear una **secuencia de prompts iterativos**, cada uno con el **modo más adecuado** para lograr tus objetivos paso a paso.

---

## 🧭 Objetivo: Estructurar y desarrollar tu TFG con ayuda inteligente

### 🔁 Enfoque: Iterativo, guiado, con razonamiento profundo y búsqueda avanzada

---

## 🧩 Prompt 1: Estructura óptima del TFG  
**Modo recomendado:** 🧠 *Think Deeper*

```text
Estoy desarrollando un TFG titulado “Desarrollo de una Arquitectura Distribuida para la Recomendación de Rutas de Evacuación en Espacios Cerrados con Inteligencia Ambiental”. Ya he modelado una base de datos en PostgreSQL/PostGIS siguiendo el estándar IndoorGML, he creado diagramas de flujo, y estoy trabajando en un algoritmo heurístico para recomendar rutas seguras en tiempo real.

Quiero que me ayudes a definir la estructura óptima del documento del TFG, alineada con las normas académicas que exige mi universidad. No quiero que lo redactes aún, solo que me digas qué apartados incluir, qué contenido debería ir en cada uno, y cómo organizarlo para que sea coherente y profesional. También dime en qué apartados debo invertir más tiempo y cuáles puedo simplificar.
```

---

## 🧩 Prompt 2: Comparar con TFGs similares  
**Modo recomendado:** 🔍 *Deep Research*

```text
Busca ejemplos de TFGs similares al mío que trabajen con IndoorGML, evacuación inteligente, arquitectura distribuida o algoritmos de recomendación en entornos cerrados. Quiero que me ayudes a comparar sus estructuras, enfoques y resultados con los míos. Dame ideas sobre cómo puedo mejorar mi planteamiento y qué elementos suelen destacar en trabajos bien valorados.
```

---

## 🧩 Prompt 3: Redacción del apartado de objetivos  
**Modo recomendado:** 🧠 *Think Deeper*

```text
Ahora que tengo clara la estructura del TFG, quiero que me ayudes a redactar el apartado de “Objetivos”. Ya tengo definidos los objetivos generales y específicos, pero quiero que estén bien redactados, con lenguaje académico claro y preciso. Usa lo que ya he desarrollado para que refleje fielmente mi trabajo.
```

---

## 🧩 Prompt 4: Organización del repositorio y apéndices  
**Modo recomendado:** 🧠 *Smart Mode*

```text
En mi repositorio JorgeHuarachi/TFG-repo tengo todo lo que he avanzado, pero está algo desordenado. Quiero que me ayudes a organizarlo de forma que refleje la estructura del TFG: separar scripts SQL, diagramas, código Python, documentación, etc. También dime qué materiales deberían ir en los apéndices y cómo presentarlos.
```

---

## 🧩 Prompt 5: Simulación de lecturas de balizas  
**Modo recomendado:** 🧠 *Smart Mode*

```text
Quiero simular lecturas de balizas en mi base de datos PostgreSQL/PostGIS. Ayúdame a diseñar un script en Python que inserte datos ficticios en tiempo real, representando sensores de temperatura, humo, etc. Quiero que el script sea modular, configurable y que active los triggers que actualizan la seguridad de las salas.
```

---

## 🧩 Prompt 6: Validación técnica del sistema  
**Modo recomendado:** 🧠 *Think Deeper*

```text
Ayúdame a diseñar una validación técnica del sistema de evacuación. Quiero simular un escenario de emergencia y comprobar que el algoritmo de recomendación responde correctamente: recalcula rutas, evita zonas peligrosas y ofrece alternativas seguras. Dime qué métricas puedo usar para evaluar la eficacia del sistema y cómo presentar los resultados en el TFG.
```

---

## 🧩 Prompt 7: Redacción de conclusiones  
**Modo recomendado:** 🧠 *Think Deeper*

```text
Quiero redactar el apartado de “Conclusiones” de mi TFG. Ayúdame a sintetizar los logros alcanzados, las limitaciones encontradas y las posibles mejoras futuras. Usa un tono académico, claro y reflexivo. Quiero que este apartado cierre el trabajo con fuerza y deje claro el valor del sistema propuesto.
```

---

## 🧩 Prompt 8: Generar bibliografía en formato ISO 690  
**Modo recomendado:** 🧠 *Smart Mode*

```text
Genera la bibliografía de mi TFG en formato ISO 690 usando los enlaces y fuentes que he consultado. Incluye artículos científicos, estándares técnicos, webs oficiales y papers relevantes. Asegúrate de que el formato sea correcto y homogéneo.
```

---

¿Quieres que te prepare una plantilla editable con estos prompts para que los uses en cada fase del TFG? También puedo ayudarte a convertir esto en un plan semanal de trabajo para que avances sin agobios.


---
# LA DESESPERADA PARA API

Muy buena idea, Jorge 🙌. Te cuento cómo podrías plantear una **cliente app** para tu TFG y cómo encaja lo de **Base44** con tu caso:

---

## 🔹 ¿Qué es una “cliente app” en tu arquitectura?
En tu flujo (TTN → Webhook → CEP → BBDD → Motor de rutas → Cliente), la **cliente app** es la interfaz que usan los usuarios finales (ej. personas en un edificio) para:
- Consultar rutas de evacuación seguras.  
- Ver el estado de las celdas (seguridad, accesibilidad).  
- Recibir notificaciones en tiempo real.  

Básicamente, es el **front-end** que consume lo que tu backend ya procesa y guarda en la BBDD.

---

## 🔹 Opciones para construirla
1. **Desarrollo clásico**  
   - **Web app** con React, Angular o Vue.  
   - **Mobile app** con Flutter o React Native.  
   - Se conecta a tu API Flask (que expone rutas REST/JSON).  

2. **Low-code / No-code**  
   - Herramientas como **Base44**, Bubble, AppSheet, Glide.  
   - Te permiten crear una app funcional describiendo lo que quieres en lenguaje natural.  
   - Ideal si no quieres invertir tiempo en programar la interfaz desde cero.  

---

## 🔹 ¿Qué es Base44 y cómo encaja?
- **Base44** es una plataforma de IA que genera aplicaciones web completas a partir de descripciones en lenguaje natural.  
- Incluye:  
  - Interfaz de usuario lista para usar.  
  - Base de datos integrada (aunque puedes conectarla a la tuya).  
  - Autenticación y gestión de usuarios.  
  - Hosting automático.  
- Tú le dices: *“Quiero una app donde un usuario pueda introducir su ubicación y recibir una ruta de evacuación desde la BBDD”* → y Base44 genera la app inicial.  

👉 En tu caso, como **ya tienes la BBDD y el motor de rutas**, lo que harías es:  
- Crear la app en Base44.  
- Conectarla a tu **API Flask** (que expone los datos de la BBDD).  
- Usar la app como **cliente ligero** para mostrar rutas y estados.  

---

## 🔹 Ventajas para tu TFG
- Te permite **mostrar un prototipo funcional** sin invertir semanas en programar front-end.  
- Refuerza la idea de que tu sistema es **usable por un cliente real**.  
- Puedes centrarte en la parte académica (IndoorGML, CEP, BBDD) y usar Base44 como “capa de presentación”.  

---

✅ Resumen:  
- Sí, puedes usar **Base44** para crear tu cliente app.  
- Solo necesitas que tu API exponga los datos de tu BBDD (ej. `/getRoute`, `/getCellStatus`).  
- Base44 se conecta a esa API y te da una interfaz lista para mostrar rutas y estados.  

---

👉 ¿Quieres que te prepare un **ejemplo de endpoints REST** (tipo `/route?origin=Aula101&target=Exit`) que tu cliente app podría consumir, para que veas cómo encajaría con Base44 o cualquier otra app?