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
sql
Copiar código
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

