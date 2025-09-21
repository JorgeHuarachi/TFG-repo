# Cosas a tener en cuenta para modelar la base de datos a partir del mermaid

## CON RESPECTO A LAS CONSULTAS (EVALUACIÓN)

Uno de los objetivos que se necesita en una consulta que se hace continuamente es:

### Objetivo

Para cada combinación de ubicación y variable, quieres:

- Obtener las 3 últimas lecturas (ordenadas por datetime)

- Calcular la media de esas 3 lecturas (valor)

- Hacerlo aunque haya más o menos de 3 registros

- Si hay menos de 3, se usa la media de los disponibles.

Esa es una de las consultas mas importantes.

Basicamente Analisis complejo de eventos.


**Consultas que quizas funcionan**
`LECTURA` Es un snapshot de las lecturas que hay en una planta, ya estan ordenadas por ubicación que es algo que interesa, se puede hacer una consulta para obtenerlas ordenadas por ubicación.

A continuación unas consultas que quizas sirven para cumplir el objetivo.
```sql
WITH ordenadas AS (
  SELECT
    id_ubicacion,
    id_variable,
    valor,
    datetime,
    ROW_NUMBER() OVER (
      PARTITION BY id_ubicacion, id_variable
      ORDER BY datetime DESC
    ) AS rn
  FROM LECTURA
),
ultimas_3 AS (
  SELECT *
  FROM ordenadas
  WHERE rn <= 3
)
SELECT
  id_ubicacion,
  id_variable,
  ROUND(AVG(valor), 2) AS media_3_ultimas
FROM ultimas_3
GROUP BY id_ubicacion, id_variable;
```

```sql
SELECT id_sensor, id_variable, id_ubicacion,
       AVG(valor) AS media_ultimos_3
FROM (
    SELECT id_sensor, id_variable, id_ubicacion, valor,
           ROW_NUMBER() OVER (
               PARTITION BY id_sensor, id_variable, id_ubicacion
               ORDER BY timestamp DESC
           ) as rn
    FROM HISTORICO_LECTURAS
) sub
WHERE rn <= 3
GROUP BY id_sensor, id_variable, id_ubicacion;
```
Este cálculo lo puedes aplicar dentro de un procedimiento o script que se ejecute cada 10 segundos. También puedes usar una vista materializada si usas PostgreSQL o engines que lo soporten.

---

¿Qué es lo que quieres lograr?
Tener acceso rápido y directo a los últimos datos (estado actual de sensores, variables, ubicaciones…).

No perder los datos antiguos, porque son necesarios para auditorías, estadísticas o evaluaciones históricas.

--- 

## CON RESPECTO A LAS TABLAS LECTURA HISTORICO_LECTURA

Estrategia recomendada (rendimiento + agrupamiento)
Ya que:

Prioridad = rendimiento muy alto.

Las balizas generan muchas lecturas en paralelo.

Necesitas procesarlas agrupadas por ubicación.

Te interesa evaluar el estado actual, pero también tener trazabilidad.

La mejor opción es:

✅ Mantener dos tablas:
LECTURA_ACTUAL: contiene solo la última lectura por sensor + variable + ubicación.

LECTURA_HISTORICO: contiene todas las lecturas, sirve para auditoría y estadísticas.

🧱 Estructura sugerida

LECTURA_ACTUAL
```sql
CREATE TABLE LECTURA_ACTUAL (
  id_lectura INT PRIMARY KEY AUTO_INCREMENT,
  id_ubicacion INT NOT NULL,
  id_baliza INT NOT NULL,
  id_sensor INT NOT NULL,
  id_variable INT NOT NULL,
  datetime TIMESTAMP NOT NULL,
  valor FLOAT,
  UNIQUE KEY idx_sensor_variable_ubicacion (id_sensor, id_variable, id_ubicacion),
  FOREIGN KEY (id_ubicacion) REFERENCES UBICACION(id_ubicacion),
  FOREIGN KEY (id_baliza) REFERENCES BALIZA(id_baliza),
  FOREIGN KEY (id_sensor) REFERENCES SENSOR(id_sensor),
  FOREIGN KEY (id_variable) REFERENCES VARIABLE(id_variable)
);
```

LECTURA_HISTORICO
```sql
CREATE TABLE LECTURA_HISTORICO (
  id INT PRIMARY KEY AUTO_INCREMENT,
  id_ubicacion INT NOT NULL,
  id_baliza INT NOT NULL,
  id_sensor INT NOT NULL,
  id_variable INT NOT NULL,
  datetime TIMESTAMP NOT NULL,
  valor FLOAT,
  INDEX idx_ubicacion_datetime (id_ubicacion, datetime),
  FOREIGN KEY (id_ubicacion) REFERENCES UBICACION(id_ubicacion),
  FOREIGN KEY (id_baliza) REFERENCES BALIZA(id_baliza),
  FOREIGN KEY (id_sensor) REFERENCES SENSOR(id_sensor),
  FOREIGN KEY (id_variable) REFERENCES VARIABLE(id_variable)
);
```
### insercion de datos
Inserción de datos (batch o trigger)
Cuando llegan nuevas lecturas:

Se insertan en LECTURA_HISTORICO.

Se actualiza o reemplaza el valor de LECTURA_ACTUAL.

Esto puedes hacerlo desde tu backend o mediante un TRIGGER (menos flexible para datos masivos, pero funcional).

Ejemplo en backend (pseudocódigo SQL)
```sql
-- 1. Insertar en histórico
INSERT INTO LECTURA_HISTORICO (id_ubicacion, id_baliza, id_sensor, id_variable, datetime, valor)
VALUES (..., ..., ..., ..., ..., ...);

-- 2. Reemplazar la lectura actual
INSERT INTO LECTURA_ACTUAL (id_ubicacion, id_baliza, id_sensor, id_variable, datetime, valor)
VALUES (..., ..., ..., ..., ..., ...)
ON DUPLICATE KEY UPDATE valor = VALUES(valor), datetime = VALUES(datetime);
El ON DUPLICATE KEY UPDATE funciona porque tienes la restricción UNIQUE (id_sensor, id_variable, id_ubicacion).
```
---

### consultas

Agrupamiento por ubicación
Ahora puedes hacer consultas como:

```sql
-- Últimas lecturas agrupadas por ubicación
SELECT 
  id_ubicacion, 
  COUNT(*) as total_lecturas, 
  AVG(valor) as promedio_valor
FROM LECTURA_ACTUAL
GROUP BY id_ubicacion;
```
O si necesitas todo el detalle:

```sql
SELECT * 
FROM LECTURA_ACTUAL 
WHERE id_ubicacion = 3;
```
Y si necesitas comparar contra el histórico:

```sql
SELECT * 
FROM LECTURA_HISTORICO 
WHERE id_ubicacion = 3 
  AND datetime BETWEEN NOW() - INTERVAL 10 MINUTE AND NOW();
```

### particiones

🚀 Optimización adicional
Índices en `LECTURA_HISTORICO` por `(id_ubicacion, datetime)` → muy útil para filtros por ubicación y tiempo.

Particionado en LECTURA_HISTORICO:

Por fecha `(RANGE(datetime))`: útil si vas a consultar por períodos.

Por ubicación `(LIST(id_ubicacion))`: útil si consultas ubicación por ubicación.

Ejemplo:

```sql
CREATE TABLE LECTURA_HISTORICO_PART (
  -- columnas
)
PARTITION BY RANGE (YEAR(datetime)) (
  PARTITION p2024 VALUES LESS THAN (2025),
  PARTITION p2025 VALUES LESS THAN (2026)
);
```
### vistas?
Vistas si quieres un resumen por ubicación para evaluaciones de seguridad:

```sql
CREATE VIEW vista_estado_actual_por_ubicacion AS
SELECT id_ubicacion, AVG(valor) as media, MAX(datetime) as ultima
FROM LECTURA_ACTUAL
GROUP BY id_ubicacion;
```

### ✅Conclusión
Tu idea es sólida y la estrategia sugerida es:

LECTURA_ACTUAL: estado actual, consultas rápidas.

LECTURA_HISTORICO: almacén completo, análisis.

Operaciones rápidas con ON DUPLICATE KEY UPDATE.

Agrupamientos por ubicación son simples con GROUP BY id_ubicacion.

---
### UNIQUE KEY (id_sensor, id_varaible, id_ubicación)
¿Qué es UNIQUE KEY (id_sensor, id_variable, id_ubicacion)?
Esta clave única:

Impide que haya más de un registro con la misma combinación de:

Sensor

Variable

Ubicación

Se utiliza para que al insertar una lectura nueva del mismo sensor + variable + ubicación, se reemplace la anterior sin duplicar.

Además, crea automáticamente un índice compuesto, lo que hace que:

Buscar por id_sensor, id_variable y/o id_ubicacion sea mucho más rápido.

Las búsquedas y actualizaciones sean eficientes (optimización de consultas).


Este índice:

sql
Copiar código
UNIQUE KEY idx_sensor_variable_ubicacion (id_sensor, id_variable, id_ubicacion)
dice: ❗"No puedes tener más de una fila con la combinación (1, 1, 10) o (2, 1, 10)."

---

### ejemplo?

Ejemplo completo con dos ubicaciones y varios sensores/variables
Supongamos que tienes:

2 ubicaciones: 10 y 20

2 sensores: 1 y 2

2 variables: 1 (Temperatura) y 2 (Humedad)

🟢 Tabla LECTURA_ACTUAL con UNIQUE (id_sensor, id_variable, id_ubicacion)
```sql
CREATE TABLE LECTURA_ACTUAL (
    id_lectura INT PRIMARY KEY,
    id_sensor INT,
    id_variable INT,
    id_ubicacion INT,
    valor FLOAT,
    datetime TIMESTAMP,
    UNIQUE (id_sensor, id_variable, id_ubicacion)
);
```
🔄 Simulación de inserciones (usando ON DUPLICATE para mantener actualizadas)
```sql
-- Lectura inicial para sensor 1, variable 1 en ubicación 10
INSERT INTO LECTURA_ACTUAL VALUES (1, 1, 1, 10, 22.0, '2025-05-19 10:00:00')
ON DUPLICATE KEY UPDATE valor = VALUES(valor), datetime = VALUES(datetime), id_lectura = VALUES(id_lectura);

-- Llega una nueva lectura más reciente para esa combinación
INSERT INTO LECTURA_ACTUAL VALUES (2, 1, 1, 10, 23.5, '2025-05-19 10:05:00')
ON DUPLICATE KEY UPDATE valor = VALUES(valor), datetime = VALUES(datetime), id_lectura = VALUES(id_lectura);

-- Humedad en ubicación 10
INSERT INTO LECTURA_ACTUAL VALUES (3, 1, 2, 10, 65.0, '2025-05-19 10:06:00')
ON DUPLICATE KEY UPDATE valor = VALUES(valor), datetime = VALUES(datetime), id_lectura = VALUES(id_lectura);

-- Temperatura en ubicación 20
INSERT INTO LECTURA_ACTUAL VALUES (4, 2, 1, 20, 24.8, '2025-05-19 10:07:00')
ON DUPLICATE KEY UPDATE valor = VALUES(valor), datetime = VALUES(datetime), id_lectura = VALUES(id_lectura);

-- Humedad en ubicación 20
INSERT INTO LECTURA_ACTUAL VALUES (5, 2, 2, 20, 60.0, '2025-05-19 10:08:00')
ON DUPLICATE KEY UPDATE valor = VALUES(valor), datetime = VALUES(datetime), id_lectura = VALUES(id_lectura);
📊 Resultado final de la tabla LECTURA_ACTUAL
id_lectura	id_sensor	id_variable	id_ubicacion	valor	datetime
2	1	1	10	23.5	2025-05-19 10:05:00
3	1	2	10	65.0	2025-05-19 10:06:00
4	2	1	20	24.8	2025-05-19 10:07:00
5	2	2	20	60.0	2025-05-19 10:08:00
```
🔸 Como ves: solo hay una fila por cada combinación de sensor + variable + ubicación.

---

🎯 Objetivo
Para cada combinación de ubicación y variable, quieres:

Obtener las 3 últimas lecturas (ordenadas por datetime)

Calcular la media de esas 3 lecturas (valor)

Hacerlo aunque haya más o menos de 3 registros

Si hay menos de 3, se usa la media de los disponibles.

---

### Evaluaciones con ventana deslizante

Ejemplo SQL para evaluar dentro de tu lógica:

```sql
SELECT id_sensor, id_variable, id_ubicacion,
       AVG(valor) AS media_ultimos_3
FROM (
    SELECT id_sensor, id_variable, id_ubicacion, valor,
           ROW_NUMBER() OVER (
               PARTITION BY id_sensor, id_variable, id_ubicacion
               ORDER BY timestamp DESC
           ) as rn
    FROM HISTORICO_LECTURAS
) sub
WHERE rn <= 3
GROUP BY id_sensor, id_variable, id_ubicacion;
```
Este cálculo lo puedes aplicar dentro de un procedimiento o script que se ejecute cada 10 segundos. También puedes usar una vista materializada si usas PostgreSQL o engines que lo soporten.

_____________

### añadir centroide a area y conexion, origen en planta

🗄️ Resumen de cambios en la base de datos
Para poder almacenar también la posición de cada área y puerta, basta con añadir unos pocos campos a tus tablas:

sql
Copiar código
-- En AREA, guardamos el centroide y opcionalmente su caja envolvente:
ALTER TABLE AREA
  ADD COLUMN centroid_x DOUBLE PRECISION,
  ADD COLUMN centroid_y DOUBLE PRECISION,
  ADD COLUMN min_x DOUBLE PRECISION,
  ADD COLUMN min_y DOUBLE PRECISION,
  ADD COLUMN max_x DOUBLE PRECISION,
  ADD COLUMN max_y DOUBLE PRECISION;

-- En CONEXION (puertas), guardamos el punto de inserción:
ALTER TABLE CONEXION
  ADD COLUMN pos_x DOUBLE PRECISION,
  ADD COLUMN pos_y DOUBLE PRECISION;

-- En PLANTA, opcionalmente el origen de coordenadas:
ALTER TABLE PLANTA
  ADD COLUMN origin_x DOUBLE PRECISION,
  ADD COLUMN origin_y DOUBLE PRECISION;

  ___

Vale quiero ir la siguiente bloque, quiero que recuerdes todo lo que hablamos y me digas qeu es lo que recuerdas para comfinar, añadir o elimiinar ideas.

Te paso el codigo mermaid de referentia.

con respecto alas balizas tambien me gustaria conoces u coordenada xy y lo otro igual que hemos hecho antes asi podemos situarlas en el espacio.

 %% --- Bloque 2: Sensores y Lecturas ---
    %% Esto modela los sensores y el estado en tiempo real de las mediciones, es dinámica.
    AREA ||--o{ LECTURA : "ocurre en"
    AREA ||--o{ HISTORICO_LECTURAS : "ocurre en"
    AREA ||--o{ BALIZA : "tiene"

    BALIZA   ||--o{ BALIZA_SENSOR    : "tiene sensores"
    SENSOR   ||--|| SENSOR_VARIABLE  : "mide variables"
    SENSOR   ||--o{ BALIZA_SENSOR    : "conectado a"
    VARIABLE ||--|| SENSOR_VARIABLE  : "definida en"

    HISTORICO_LECTURAS||--o{ VARIABLE : "mide"
    HISTORICO_LECTURAS||--o{ SENSOR   : "usa"
    HISTORICO_LECTURAS||--o{ BALIZA   : "genera"

    LECTURA ||--o{ VARIABLE  : "mide"
    LECTURA ||--o{ SENSOR    : "usa"
    LECTURA ||--o{ BALIZA    : "genera"
    
    BALIZA {
      int id_baliza PK
      varchar nombre
      text descripcion
      boolean activa
      int id_area FK
    }
    SENSOR {
      int id_sensor PK
      varchar nombre
      text descripcion
      boolean activa
    }
    VARIABLE {
      int id_variable PK
      varchar nombre
      text descripcion
      varchar unidad
    }
    BALIZA_SENSOR {
      int id PK
      int id_baliza FK
      int id_sensor FK
      text descripcion
    }
    SENSOR_VARIABLE {
      int id PK
      int id_sensor FK
      int id_variable FK
      text descripcion
    }
    %% En LECTURA se almacena los ultimos valores medidos por los sensores de las balizas en cada una de las AREAS, su tamaño es fijo, y unicamente se actualiza el valor de la variable, se podría decir que es una especie de Snapshot del estado del sistema en términos de las variables.
    %% Mi idea con esta entidad es tener las ultimas lecturas como si fuera un Live.
    LECTURA {
      int id_lectura PK
      int id_area FK
      int id_baliza FK
      int id_sensor FK
      int id_variable FK
      float valor
      datetime timestamp
    }
    %% Como LECTURA es una tabla estática, para no perdér los datos con cada nueva lectura, se deben ir volcando con cada nueva LECTURA en su HISTORICO, se vuelca al mismo tiempo que se obtiene la lectura de tal modo que los ultimos registros de LECTURA y su HISTORICO son los mismos
    %% Mi idea con esta entidad es poder tener un registro en el tiempo de como han evolucionado las variabes (Tº, CO2, Humo) y poder auditar lo que ha ocurrido, tambien de obtener una media de las ultimas lecturas, como una media de temperatura, el incremento, etc, para poder tener control sobre como evolucionan y detectar patrones.
    HISTORICO_LECTURAS {
      int id_historico_lectura PK
      int id_area FK
      int id_baliza FK
      int id_sensor FK
      int id_variable FK
      float valor
      datetime timestamp
    }

### Orden al crear la base de datos

🧪 ¿Qué orden seguir?
Cuando montas toda la base desde cero, este es el orden lógico:

Crear la base de datos (si aún no existe).

Crear las tablas base.

Crear las funciones de trigger (son funciones como set_pos_from_geom()).

Crear los triggers que usan esas funciones.

Crear las vistas.

Crear los índices.

📍 En pgAdmin
Abre tu base en pgAdmin.

Clic derecho en el esquema → Query Tool.

Pega el bloque SQL (función, trigger o vista).

Ejecuta (F5 o botón del rayo).

Puedes hacer uno por uno o pegar un archivo .sql completo con todo junto (si el orden es correcto).

✅ Recomendación
Si estás haciendo un proyecto serio (aunque sea personal):

✨ Crea tu estructura.sql desde ya.

Añade todos tus CREATE TABLE, CREATE FUNCTION, CREATE TRIGGER, CREATE VIEW, CREATE INDEX.

Usa IF NOT EXISTS y CREATE OR REPLACE para que lo puedas ejecutar varias veces sin miedo.

___

/sql/
├── 00_create_database.sql       ← (opcional) crea la base si no existe
├── 01_schemas.sql               ← schemas si usas (ej: `public`, `gis`, etc.)
├── 02_tables_core.sql           ← tablas principales (usuarios, áreas, etc.)
├── 03_tables_relacionales.sql   ← tablas intermedias, relaciones N:M
├── 04_views.sql                 ← vistas
├── 05_functions.sql             ← funciones PL/pgSQL (ej: triggers)
├── 06_triggers.sql              ← triggers conectados a funciones
├── 07_indexes.sql               ← índices
├── 08_sample_data.sql           ← datos de prueba (si quieres)

__

/sql/
├── 02_tablas_autenticacion.sql
├── 03_tablas_espaciales.sql
├── 04_tablas_eventos.sql

/sql/
├── 00_create_database.sql
├── 01_extensions.sql                    ← PostGIS y otras
├── 02_schemas.sql                       ← Si usas varios esquemas
├── 03_tablas_autenticacion.sql
├── 04_tablas_espaciales.sql
├── 05_tablas_eventos.sql
├── 06_particiones_eventos.sql          ← Si particionas por años
├── 07_functions_triggers.sql
├── 08_views.sql
├── 09_indexes.sql
├── 10_datos_prueba.sql

✅ Recomendación final
Necesidad	Solución
Base con muchas tablas	✅ Divide por bloques (.sql por módulo)
Evitar errores al ejecutar varias veces	✅ Usa IF NOT EXISTS, OR REPLACE
Crear base completa desde cero	✅ Usa script con orden y comentarios
Tener futuro control de versiones	✅ Guarda en Git (estructura + cambios)
Particiones	✅ Dentro del archivo de su tabla, o aparte

___

📦 Conclusión
Tu estructura es totalmente válida y no es necesario “repensarla” ahora. Pero puedes:

Mejora	Acción sugerida
Mejor organización	✅ Separar en un bloque tablas_usuarios.sql
Buen rendimiento futuro	✅ Añadir índices geom, timestamp, etc.
Mayor claridad	✅ Añadir comentarios en cada tabla
Automatización o lógica espacial	✅ Usar PostGIS también aquí, si guardas ubicaciones

---

✅ Conclusión
Quieres...	Usa...
Solo usar NetworkX o exportar a Python	pos_x, pos_y
Mostrar en plano GIS / QGIS / mapas interactivos	GEOMETRY(POINT)
Hacer análisis espacial (distancias, zonas)	GEOMETRY(POINT)
Tener ambos	Usa geometry(POINT) y calcula pos_x, pos_y como campos o vista

---
### entidda door-to-door para tener distancias (aristas)
ALTER TABLE door_to_door
ADD COLUMN distancia_metros DOUBLE PRECISION GENERATED ALWAYS AS (
  ST_Length(geom)
) STORED;

👉 Esto te da una columna siempre sincronizada con la geometría. Perfecto para usar como peso en NetworkX (weight).

---
### modelar door-to-door
✅ Entonces sí necesitas modelar door-to-door aparte
Porque estás pasando de:

🔳 Área-a-área (conceptual, a nivel de recinto)
→ conexiones (ya la tienes)

a

🚪 Puerta-a-puerta (físico, en el plano)
→ door_to_door (que tú defines)

### Sobre los espacios en forma de L T U

Dividirlo en rectangulos conectados.
L: dos rectangulos con una conexion |_
T: dos rectangulos con una conexion |-
U: tres rectangulos con dos conexiones |_|

---
BD: PostgreSQL + PostGIS con la z, para tenerlo ya modelado pero trabajare en 2D.

CRS: Voy a trabajar con un edificion en principio ficticio y creado por mi el SRID creo que es mejor que sea EPSG:3857 (me interesa algo compatible con web de cara al dashboard) de momento no ncesito coordenadas reales. No cambies el SRID ni uses otro CRS salvo que yo lo indique expresamente.

Namespacing: dos esquemas de BD: indoorgml_core y indoorgml_nav, de momento esos mas adelanto los aumentaré.

IDs: No quiero uuid, lo que voy a quere hacer es usar id numerico PK junto co un code alfa-numérico de forma que sea auto explicativo, para mostrar esto en dashboard y no el id numerico como clave primaria.

Semántica: declaramos en ThematicLayer.semanticExtension = true para capas donde apliques Navigation. 

id
Tabla	PK interna	code ejemplo
PrimalSpaceLayer	1	PR-01
DualSpaceLayer	1	DU-01
CellSpace	1	CS-0001
CellBoundary	1	CB-0001-0002
Node	1	ND-0001
Edge	1	ED-0001-0002
NavigableSpace	1	NS-0001
NonNavigableSpace	1	NN-0001
NavigableBoundary	1	NB-0001-0002
NonNavigableBoundary	1	NNB-0001-0002
TransferSpace	1	TS-0001
ObjectSpace	1	OS-0001
Route	1	RT-2025001 (año + secuencia)