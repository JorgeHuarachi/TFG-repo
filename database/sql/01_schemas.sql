
-- Extensiones necesarias para trabajar con geometrías
CREATE EXTENSION IF NOT EXISTS postgis;

-- Esquemas necesarios para el modelo IndoorGML
CREATE SCHEMA IF NOT EXISTS indoorgml_core;
CREATE SCHEMA IF NOT EXISTS indoorgml_navigation;

-- Enum necesario de momento solo uno (para el tema de las capas)
CREATE TYPE indoorgml_core.theme_layer_value AS ENUM ('PHYSICAL','VIRTUAL','TAGS','UNKNOWN');


