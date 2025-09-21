
# Consultas para crear la Base de datos (ANTIGUO PRE indoorGML)

Aqui quise empezar a pegar las consultas de creación de la base de datos en postgreSQL, esto como sabes son consultas que se ejecutan una sola vez.

Existe una forma de hacerlo bien, como meter todos los archivos en una carpeta dedicada a la creación de la base de datos (Pero quizas no es necesario)

## Creacion del primer bloque

```sql
-- ============================
-- TABLA: EDIFICIO
-- ============================
CREATE TABLE EDIFICIO (
    id_edificio SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    latitud FLOAT,
    longitud FLOAT,
    capacidad_personas INT,
    superficie_m2 FLOAT
);

-- ============================
-- TABLA: PLANTA
-- ============================
CREATE TABLE PLANTA (
    id_planta SERIAL PRIMARY KEY,
    id_edificio INT REFERENCES EDIFICIO(id_edificio) ON DELETE CASCADE,
    nombre VARCHAR(50),
    nivel INT, -- Nivel de elevación de planta
    superficie_m2 FLOAT,
    coord_origen_x FLOAT, -- Origen de coordenadas de la planta (sistema local)
    coord_origen_y FLOAT
);

-- ============================
-- TABLA: TIPO_AREA
-- ============================
CREATE TABLE TIPO_AREA (
    id_tipo_area SERIAL PRIMARY KEY,
    nombre VARCHAR(100),
    descripcion TEXT
);

-- ============================
-- TABLA: AREA
-- ============================
CREATE TABLE AREA (
    id_area SERIAL PRIMARY KEY,
    id_planta INT REFERENCES PLANTA(id_planta) ON DELETE CASCADE,
    id_tipo_area INT REFERENCES TIPO_AREA(id_tipo_area),
    nombre VARCHAR(100),
    descripcion TEXT,
    superficie_m2 FLOAT,
    capacidad_personas INT,
    salida_segura BOOLEAN,

    -- Posiciones relativas para visualización en planta
    x FLOAT,
    y FLOAT,
    ancho FLOAT,
    alto FLOAT
);

-- ============================
-- TABLA: TIPO_CONEXION
-- ============================
CREATE TABLE TIPO_CONEXION (
    id_tipo_conexion SERIAL PRIMARY KEY,
    nombre VARCHAR(100),
    descripcion TEXT,
    clase_acceso VARCHAR(50),
    requiere_rescate BOOLEAN,
    uso_extremo BOOLEAN,
    restriccion_movilidad BOOLEAN,
    accesible_bomberos BOOLEAN,
    bidireccional BOOLEAN,
    requiere_apertura BOOLEAN,
    observaciones TEXT
);

-- ============================
-- TABLA: CONEXION (Ej: puertas normales)
-- ============================
CREATE TABLE CONEXION (
    id_conexion SERIAL PRIMARY KEY,
    id_area_origen INT REFERENCES AREA(id_area),
    id_area_destino INT REFERENCES AREA(id_area),
    nombre VARCHAR(100),
    descripcion TEXT,
    ancho FLOAT,
    alto FLOAT,
    flujo_personas_min INT,
    bidireccional BOOLEAN,
    id_tipo_conexion INT REFERENCES TIPO_CONEXION(id_tipo_conexion),

    -- Coordenadas relativas para representación en planta
    x FLOAT,
    y FLOAT
);

-- ============================
-- TABLA: CONEXION_CONDICIONAL (Ej: ventanas, huecos, solo en emergencias)
-- ============================
CREATE TABLE CONEXION_CONDICIONAL (
    id_conexion_condicional SERIAL PRIMARY KEY,
    id_area_origen INT REFERENCES AREA(id_area),
    id_area_destino INT REFERENCES AREA(id_area),
    id_tipo_conexion INT REFERENCES TIPO_CONEXION(id_tipo_conexion),
    alto FLOAT,
    ancho FLOAT,
    requiere_rescate BOOLEAN,
    uso_extremo BOOLEAN,
    restriccion_movilidad BOOLEAN,
    accesible_bomberos BOOLEAN,
    descripcion TEXT,

    -- Posición en planta (puede ser el centro de la ventana por ejemplo)
    x FLOAT,
    y FLOAT
);

CREATE TABLE ESTADO_CONEXION (
    id_estado SERIAL PRIMARY KEY,
    id_conexion INT REFERENCES CONEXION(id_conexion) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT NOW(),
    estado VARCHAR(50),  -- Ej: 'abierta', 'cerrada', 'bloqueada'
    seguridad FLOAT,     -- Valor de 0.0 a 1.0 que representa cuán segura es en ese momento
    observaciones TEXT
);

CREATE TABLE ESTADO_CONEXION_CONDICIONAL (
    id_estado SERIAL PRIMARY KEY,
    id_conexion_condicional INT REFERENCES CONEXION_CONDICIONAL(id_conexion_condicional) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT NOW(),
    estado VARCHAR(50),  -- Ej: 'accesible', 'inaccesible', 'ventilada', etc.
    seguridad FLOAT,     -- Valor de 0.0 a 1.0
    observaciones TEXT
);


```