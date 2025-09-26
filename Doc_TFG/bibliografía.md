## https://dspace.lib.ntua.gr/xmlui/bitstream/handle/123456789/45923/IndoorGML_Tsaggouri.pdf?sequence=1&utm_source=chatgpt.com

### rutas
Sección 3.2: Algorithms for Path-Finding
Presenta algoritmos como Dijkstra y A\* como base para calcular rutas óptimas en entornos interiores.

Explica que estos algoritmos se aplican sobre el grafo topológico generado por IndoorGML, donde los nodos representan espacios (salas, pasillos) y las aristas representan conexiones navegables.

Se menciona que la lógica debe considerar:

Distancia mínima

Accesibilidad

Condiciones dinámicas (como fuego, humo, congestión)

🔹 Sección 4.4: Generating Navigation Logical Model from CityGML
Describe cómo transformar datos geométricos de CityGML LoD4 en un modelo lógico de navegación.

Este modelo incluye:

Nodos de navegación

Relaciones espaciales

Jerarquías de conectividad

La lógica de recomendación se basa en este modelo para calcular rutas seguras y eficientes.

🔹 Sección 5.3–5.4: Implementation and Results
En el caso práctico, se simulan evacuaciones usando rutas calculadas dinámicamente.

Se observa cómo las rutas cambian en función de eventos como propagación del fuego o acumulación de personas.

Se aplican criterios de reencaminamiento adaptativo, lo que implica una lógica que recalcula rutas en tiempo real.

🔧 ¿Qué no incluye?
No hay pseudocódigo ni funciones detalladas.

No se especifica cómo se ponderan los factores (seguridad, distancia, accesibilidad).

No se muestra cómo se integra esta lógica en una base de datos o aplicación.
### datos
¿Qué tipo de modelado sí aborda?
Modelado conceptual: define entidades como IndoorSpace, CellSpace, GridUnit, etc., y sus relaciones.

Modelado topológico y semántico: explica cómo se conectan los espacios y qué significado tienen (por ejemplo, pasillo, sala, salida).

Modelado jerárquico y multi-capa: describe cómo se representan distintos niveles de detalle (geométrico, semántico, funcional).

❌ ¿Qué no incluye?
No hay diagramas ER típicos de bases de datos relacionales.

No se definen tipos de datos, claves primarias, ni relaciones N:M.

No se presentan scripts SQL ni estructuras físicas para implementar el modelo.

🧠 ¿Qué puedes hacer tú?
Tú ya has hecho el paso que el documento no cubre: has traducido el modelo conceptual de IndoorGML a una base de datos física en PostgreSQL/PostGIS, con tablas, funciones, triggers y vistas. Eso te coloca en una posición avanzada para:

Comparar tu implementación con el modelo conceptual del documento.

Justificar tus decisiones técnicas en el TFG.

Proponer mejoras o adaptaciones basadas en los estándares.
---

## https://www.mdpi.com/2220-9964/6/4/104?utm_source=chatgpt.com

### drutas

### datos
🧩 Sobre el modelo de datos
Sí, el artículo describe el modelo conceptual y lógico del DIFM, pero no entra en detalle sobre la creación física de la base de datos. Es decir:

Sí incluye UML y diagramas conceptuales (como el de la Figura 2 y Figura 3), donde se definen entidades como IndoorSpace, GridUnit, EmergencyGrid, etc.

Sí explica cómo se calcula el peso de cada celda en función de sensores, fuego, personas, etc.

Pero no muestra el esquema SQL, ni tablas físicas, ni scripts de implementación.

👉 Lo que tú has hecho en PostgreSQL/PostGIS con tablas como cell_space, primal_space_layer, etc., va más allá de lo que el paper muestra a nivel físico. Tú estás aplicando IndoorGML de forma concreta, mientras que ellos se quedan en el plano conceptual y lógico.

### rutas

🧠 Sobre el método de recomendación de rutas
Sí, el artículo describe el algoritmo de recomendación, pero no incluye código fuente ni pseudocódigo detallado. Lo que sí ofrece:

Un diagrama de flujo del método de evacuación basado en cambios (Figura 5).

Fórmulas para calcular el peso de cada celda y el índice de seguridad (SI) de una ruta.

Explicación del uso del algoritmo A\* para buscar rutas óptimas.

Un método para detectar congestión y estancamiento usando una versión del algoritmo k-means.

👉 Pero no hay código Python, ni SQL, ni estructuras de datos concretas. Todo está explicado a nivel de lógica y fórmulas.

🧭 ¿Qué puedes hacer tú?
Traducir el modelo DIFM a tu esquema físico en PostgreSQL.

Implementar el cálculo de pesos como funciones SQL o en tu motor Python.

Usar el índice de seguridad (SI) como parte de tu heurística de recomendación.

Representar el diagrama de flujo en Mermaid para documentarlo en tu TFG.

### https://repository.tudelft.nl/record/uuid%3A31a20fb8-dabc-4f19-82c8-432f410a3ece?utm_source=chatgpt.com
### https://repository.tudelft.nl/file/File_b729a74b-b1e6-4e18-9654-cba82c404f62?preview=1

Ambos tratan sobre el desarrollo de una **base de datos física en PostgreSQL/PostGIS** basada en el modelo conceptual **IndoorGML**, y además integran el estándar **LADM** para gestionar derechos de acceso a espacios interiores.

---

## 🧠 ¿De qué hablan estos documentos?

### 📌 Tema central
Describen cómo se transforma el modelo conceptual **LADM–IndoorGML** en un modelo técnico implementado en **PostgreSQL con extensión PostGIS**, incluyendo:

- Conversión de diagramas UML a SQL DDL
- Creación de tablas físicas con geometrías 2D y 3D
- Gestión de restricciones, claves primarias y foráneas
- Visualización de espacios interiores con herramientas como QGIS, FME, Rhino, ArcGIS

### 🧱 Estructura del trabajo
1. **Transformación del modelo conceptual a técnico**  
   - Uso de Enterprise Architect para generar SQL
   - Correcciones manuales en tipos de datos, claves, índices espaciales

2. **Generación de la base de datos**  
   - Tablas como `Space`, `Node`, `Edge`, `Route`, `Boundary`, etc.
   - Integración de geometrías desde Revit vía ODBC
   - Asociación de datos semánticos y espaciales

3. **Visualización y consultas**  
   - Ejecución de queries para mostrar accesibilidad según roles (estudiantes, personal)
   - Preparación para visualización web con WebGL

---

## ✅ ¿En qué se parece a tu trabajo?

| Elemento | Documentos | Tu TFG |
|---------|------------|--------|
| **IndoorGML** | Modelo conceptual y técnico | Modelo físico en PostgreSQL/PostGIS |
| **PostGIS** | Uso para geometrías 2D/3D | Uso para cellSpace, triggers, validaciones |
| **Tablas físicas** | SQL DDL generado y corregido | Estructura modular con scripts por capas |
| **Visualización** | QGIS, Rhino, WebGL | QGIS y simulación de balizas (en proceso) |
| **Accesibilidad** | Basada en RRRs (LADM) | Basada en seguridad, movilidad, criticidad |
| **Algoritmo de rutas** | No detallado | Heurístico con redundancia y filtros |

---

## 🧭 ¿Qué puedes aprovechar?

- Comparar tu modelo físico con el que ellos generan desde UML
- Justificar tus decisiones técnicas usando sus problemas y soluciones
- Citar este trabajo como referencia directa en tu TFG
- Inspirarte en su estructura de tablas para mejorar la tuya

---

LO DE ARRIBA PERO ORGANIZADO:

Perfecto, Jorge 🙌. He revisado el contenido que compartiste y lo que más necesitas es **ordenar y limpiar la parte de los enlaces** para que luego puedas dárselo a otro modelo (o a mí mismo) y que te ayude a redactar. Te lo organizo en un formato claro, con secciones y listas, para que quede listo para usar.  

---

# 📑 Organización de Contenido del TFG

## ANEXO I: Normas de Presentación
- Formato: DIN-A4, márgenes 2,5 cm, letra legible (Times New Roman 11), interlineado 1,5.  
- Extensión máxima: 75 páginas (sin contar apéndices).  
- Apartados obligatorios:  
  - Resumen (1–2 páginas)  
  - Introducción (máx. 10 páginas)  
  - Objetivos (1–2 páginas)  
  - Solución técnica / Resultados  
  - Conclusiones (1 página)  
  - Bibliografía (ISO 690)  
  - Apéndices (planos, presupuesto, estudios, metodología, etc.)  

---

## Propuesta de TFG
**Título provisional:** Desarrollo de una Arquitectura Distribuida para la Recomendación de Rutas de Evacuación en Espacios Cerrados con Inteligencia Ambiental  
**Lugar de realización:** CETINIA, Universidad Rey Juan Carlos  
**Resumen breve:** Arquitectura para gestión de evacuaciones en interiores con sensores (beacons), base de datos IndoorGML y algoritmos de recomendación de rutas en tiempo real.  

---

## 🔗 Links organizados

### 1. Modelado de espacios interiores
- [A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches](https://www.mdpi.com/2220-9964/6/4/116#:~:text=indoor%20accessibility%20graph%20,edge%20may%20contain%20any%20additional)  
- [A "DOOR-TO-DOOR" Path-Finding Approach for Indoor Navigation](https://www.isprs.org/proceedings/2011/gi4dm/pdf/OP05.pdf#:~:text=introduced%20geometrical%20metric,Erickson%2C%201999%3B%20Choi%20%26%20Lee)  
- [Understanding IndoorGML (web oficial)](https://www.indoorgml.net/#:~:text=,position%20for%20more%20precise%20location)  
- [Towards IndoorGML 2.0 (TU Delft Repository)](https://repository.tudelft.nl/record/uuid:3f2a31d9-043a-4141-a084-3ba87944cd7a)  
- [OGC IndoorGML 2.0 Document Schemas](https://docs.ogc.org/is/19-011r4/19-011r4.html#toc14)  

### 2. Modelado de bases de datos espaciales
- [Proposal of a spatial database for indoor navigation](https://periodicos.uem.br/actascitechnol/index.php/ActaSciTechnol/article/view/51718/751375152299)  
- [Proposition of a Schematization Plugin for QGIS](https://ica-abs.copernicus.org/articles/1/23/2019/ica-abs-1-23-2019.pdf)  
- [QGIS (descarga oficial)](https://qgis.org/download/)  
- [dbdiagram.io (para diagramas de BBDD)](https://dbdiagram.io/home)  

---

## Desarrollo del Proyecto
- **Base de datos:** PostgreSQL + PostGIS + QGIS, siguiendo IndoorGML.  
- **Estructura SQL:**  
  - 00_create_database.sql  
  - 01_schemas.sql  
  - 02_tables_core.sql  
  - 03_tables_relacionales.sql  
  - 04_views.sql  
  - 05_functions.sql  
  - 06_triggers.sql  
  - 07_indexes.sql  
  - 08_sample_data.sql  
- **Diagramas realizados:**  
  - ER de la base de datos  
  - Flujo de validación y reconstrucción de cellBoundary  
  - Reconstrucción de límites (cellBoundary)  
  - Criterio geométrico de validez  

---

## Algoritmo de Recomendación de Rutas
- Basado en **grafo de adyacencia** con pesos (tiempo de recorrido).  
- Matriz de seguridad (valores dinámicos de sensores).  
- Filtro de seguridad (zonas bloqueadas si < umbral).  
- Búsqueda heurística con redundancia:  
  - Se eliminan aristas y se recalculan rutas.  
  - Se mide robustez de caminos alternativos.  

---

## Ideas de mejora
- Filtro de movilidad (accesibilidad: rampas, escaleras).  
- Filtro de criticidad (permitir rutas no convencionales en emergencias extremas).  
- Filtro de seguridad ambiental (sensores de humo, temperatura, visibilidad).  

---

## LO QUE QUIERES CONSEGUIR
- Redacción académica clara.  
- Conexión entre base de datos y motor de recomendación.  
- Simulación de lecturas de balizas.  
- Validación técnica con resultados simulados.  
- Conclusiones sólidas.  
- Bibliografía en ISO 690.  

---

LO DE ARRIBA PERO PARA EL ESTAO DEL ARTE


# 📚 Estado del Arte (Esquema Propuesto)

## 1. Introducción al problema
- Breve explicación de por qué la **evacuación en interiores** es un reto.  
- Limitaciones de los métodos tradicionales (planos estáticos, señalética fija).  
- Necesidad de sistemas dinámicos con **Inteligencia Ambiental (AmI)** e **IoT**.  

---

## 2. Modelado de espacios interiores
- **IndoorGML (OGC)**: estándar internacional para representar espacios interiores como grafos de accesibilidad.  
  - Referencia: [A Standard Indoor Spatial Data Model—OGC IndoorGML and Implementation Approaches](https://chatgpt.com/c/68ce8cb6-0ca0-8328-9aaf-cece79a724f7).  
  - Conceptos clave: *CellSpace*, *CellBoundary*, *grafo de accesibilidad*.  
- **Avances hacia IndoorGML 2.0**: modularización, capas múltiples, integración con JSON/SQL.  
  - Referencia: [Towards IndoorGML 2.0](https://chatgpt.com/c/68ce8cb6-0ca0-8328-9aaf-cece79a724f7).  
- **Implementaciones prácticas**:  
  - Uso de QGIS y PostGIS para generar datos geométricos.  
  - Ejemplo: [Proposition of a Schematization Plugin for QGIS](https://chatgpt.com/c/68ce8cb6-0ca0-8328-9aaf-cece79a724f7).  

---

## 3. Bases de datos espaciales para navegación indoor
- Propuestas de **bases de datos relacionales** adaptadas a IndoorGML.  
  - Referencia: [Proposal of a spatial database for indoor navigation](https://chatgpt.com/c/68ce8cb6-0ca0-8328-9aaf-cece79a724f7).  
- Herramientas de modelado y visualización:  
  - [dbdiagram.io](https://chatgpt.com/c/68ce8cb6-0ca0-8328-9aaf-cece79a724f7) para diagramas ER.  
  - [QGIS](https://chatgpt.com/c/68ce8cb6-0ca0-8328-9aaf-cece79a724f7) para integración con PostGIS.  

---

## 4. Algoritmos de navegación y evacuación
- **Path-finding clásico**: Dijkstra, A*, BFS.  
  - Referencia: [A "DOOR-TO-DOOR" Path-Finding Approach for Indoor Navigation](https://chatgpt.com/c/68ce8cb6-0ca0-8328-9aaf-cece79a724f7).  
- **Extensiones para evacuación**:  
  - Incorporación de sensores y condiciones dinámicas.  
  - Algoritmos que recalculan rutas en tiempo real.  
- **Heurísticas de robustez y redundancia**:  
  - Evaluar no solo la ruta más corta, sino la más segura y con alternativas.  

---

## 5. Inteligencia Ambiental y sistemas distribuidos
- Uso de **beacons, sensores de humo, temperatura, CO₂** para alimentar el sistema.  
- Procesamiento de eventos complejos (CEP) para actualizar la seguridad de cada zona.  
- Arquitecturas distribuidas para tolerancia a fallos y escalabilidad.  

---

## 6. Síntesis y hueco de investigación
- Los estándares (IndoorGML) están bien definidos, pero su **implementación práctica en BBDD relacionales** aún es limitada.  
- Los algoritmos de evacuación suelen centrarse en **distancia mínima**, no en **robustez ni resiliencia**.  
- Tu TFG aporta:  
  - Una **base de datos IndoorGML en PostgreSQL/PostGIS**.  
  - Un **algoritmo heurístico de rutas seguras y redundantes**.  
  - Una **integración con sensores simulados** para validación en tiempo real.  

---

✅ Con esta estructura, tu **Estado del Arte** no será solo una lista de papers, sino un **relato académico** que conecta lo que ya existe con lo que tú aportas.  

---
