# 🎬 HERO SECTION

![MLSM Smart Evacuation Demo](./src/resultados/evacuacion_demo.gif)

# MLSM Smart Evacuation
### Multi-Layer Spatial Model for Realistic Crowd Evacuation Simulation

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Mesa Framework](https://img.shields.io/badge/Mesa-Agent%20Based%20Modeling-green?logo=python&logoColor=white)](https://mesa.readthedocs.io/)
[![Shapely](https://img.shields.io/badge/Shapely-Geometric%20Operations-orange?logo=python&logoColor=white)](https://shapely.readthedocs.io/)
[![NetworkX](https://img.shields.io/badge/NetworkX-Graph%20Theory-red?logo=python&logoColor=white)](https://networkx.org/)

**Trabajo Fin de Grado en Ingeniería** | Simulación y Análisis de Evacuaciones en Edificios

---

# 🎯 DESCRIPCIÓN GENERAL

## ¿Qué es MLSM Smart Evacuation?

MLSM Smart Evacuation es un **sistema integrado de simulación de evacuaciones de multitudes** desarrollado como Trabajo Fin de Grado. Combina un **motor CAD paramétrico** con un **simulador multi-agente basado en física realista** para analizar cómo grupos de personas evacúan edificios de manera segura y eficiente.

El proyecto aborda un desafío crítico en ingeniería civil y seguridad: **¿Cómo validar y optimizar rutas de evacuación antes de construir un edificio?** Nuestra solución proporciona herramientas para diseñar planos con restricciones de evacuación y simular miles de escenarios de riesgo en segundos.

---

## Arquitectura Multi-Capa: El Modelo MLSM

Este proyecto implementa el **Multi-Layer Spatial Model (MLSM)**, una arquitectura de tres capas de abstracción que separa de forma elegante la *geometría*, la *topología* y la *semántica* del espacio:

```
┌─────────────────────────────────────────────────────────────────┐
│                     MLSM (3 Capas)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  🔷 CAPA GEOMÉTRICA                                             │
│     └─ Física de colisión: muros, puertas, salidas             │
│        Representación: Polígonos 2D (Shapely)                  │
│        Propósito: Detección de obstáculos, raycast             │
│                                                                   │
│  🔹 CAPA TOPOLÓGICA                                             │
│     └─ Navegación y conectividad: grafo de nodos y aristas    │
│        Representación: Grafo dirigido (NetworkX)               │
│        Propósito: Cálculo de rutas dinámicas (Dijkstra)       │
│                                                                   │
│  🔸 CAPA SEMÁNTICA                                              │
│     └─ Atributos de locomoción: perfiles de movilidad         │
│        Representación: Metadatos IndoorGML                      │
│        Propósito: Adaptar comportamiento según tipo de agente  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

Esta separación permite:
- **Reutilizar** geometría en múltiples simulaciones
- **Ajustar** rutas sin rediseñar la planta
- **Representar** distintos perfiles demográficos (Walking, Rolling, Elderly)

---

## Características Principales

### 🎨 Motor SpatialEngine: Diseño Paramétrico
Un editor CAD interactivo que interpreta clics del usuario y genera automáticamente:
- **Operaciones booleanas automáticas**: resta geométrica de puertas en muros sin fisuras
- **Generación topológica inteligente**: infiere adyacencias y conectividades entre espacios
- **Stack de deshacer**: Command Pattern para reversibilidad completa
- **Exportación JSON**: serialización en formato MLSM compatible con simulador

### ⚡ Motor EvacEngine: Simulación Realista
Un simulador multi-agente con física continua y comportamientos cognitivos:
- **Steering behaviors avanzados**: atracción a destino + repulsión de muros y multitud
- **Pathfinding dinámico**: Dijkstra adaptativo con pesos que varían por congestión y fuego
- **Visión artificial**: raycast para detectar atajos visuales en tiempo real
- **3 perfiles demográficos**: Walking (70%), Rolling (15%), Elderly (15%)
- **Métricas en tiempo real**: registro de evacuaciones, cruces de puertas, eventos de congestión

### 📊 Resultados Exportables
- **Animación GIF**: visualización fluida de la simulación (multitud, trayectorias, bottlenecks)
- **Datos CSV**: métricas por agente (posición, velocidad, tiempo de evacuación, distancia recorrida)
- **Compatible IndoorGML 2.0**: estándar OGC para modelos de edificios semánticos

---

## ¿Por Qué Tres Capas?

La separación MLSM no es arbitraria; responde a principios de ingeniería de software:

| Capa | Ventaja | Ejemplo |
|------|---------|---------|
| **Geométrica** | Reutilizable en otros proyectos CAD | El mismo fichero `planta_v4.json` sirve para diseño estructural y evacuación |
| **Topológica** | Cálculo separado de física | Cambiar algoritmo de rutas sin tocar geometría |
| **Semántica** | Extensible a nuevos perfiles | Agregar "Visually Impaired" sin recodificar motores |

---

## Casos de Uso

1. **Validación de códigos de construcción**: Verificar que el tiempo de evacuación cumple normativas de seguridad
2. **Optimización de salidas**: Identificar bottlenecks y redimensionar puertas antes de construir
3. **Investigación académica**: Estudiar cómo diferentes factores (ancho, señalética, fuego) afectan evacuación
4. **Entrenamiento**: Generar GIFs realistas para cursos de seguridad y emergencias

---

## Stack Tecnológico

| Componente | Tecnología | Rol |
|------------|-----------|-----|
| **Simulación** | Mesa Framework | Motor multi-agente (ABM) |
| **Geometría** | Shapely | Operaciones booleanas, raycast, colisiones |
| **Grafos** | NetworkX | Dijkstra, análisis topológico |
| **Visualización CAD** | Matplotlib | Editor interactivo con eventos de ratón |
| **Álgebra** | NumPy | Cálculos vectoriales, normalizaciones |
| **Datos** | Pandas | Exportación a CSV, auditoría |
| **Serialización** | JSON | Formato MLSM estándar |
| **Lenguaje** | Python 3.8+ | Prototipado rápido, readibilidad |

---

# 🛠️ REQUISITOS TÉCNICOS

## Sistema Operativo
- **Windows 10/11** (recomendado para desarrollo)
- **Linux** (Ubuntu 18.04+, Fedora 30+)
- **macOS** (10.14+)

## Versión de Python
- **Python 3.8 o superior** (recomendado Python 3.10+)

## Dependencias Principales

| Librería | Versión | Propósito en la Simulación |
|----------|---------|----------------------------|
| **Mesa** | 2.4.0 | Framework de modelado multi-agente para ejecutar simulaciones de evacuación con agentes autónomos |
| **Shapely** | 2.1.2 | Operaciones geométricas (unión, intersección, buffer) para modelar muros, puertas y detección de colisiones |
| **NetworkX** | 3.3 | Construcción y análisis de grafos para rutas de evacuación (algoritmo Dijkstra dinámico) |
| **Matplotlib** | 3.10.8 | Visualización interactiva del editor CAD y generación de animaciones GIF de simulaciones |
| **NumPy** | 2.4.4 | Cálculos numéricos vectoriales para física de agentes (fuerzas, velocidades, posiciones) |
| **Pandas** | 2.2.2 | Manipulación y exportación de datos CSV con métricas de evacuación por agente |

## Requisitos de Hardware
- **RAM**: Mínimo 4GB, recomendado 8GB+
- **CPU**: Procesador de 2 núcleos o superior
- **Espacio en disco**: 500MB para instalación + espacio para resultados de simulaciones

---

# 📦 INSTALACIÓN PASO A PASO

## Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/MLSM-Smart-Evacuation.git
cd MLSM-Smart-Evacuation
```

## Paso 2: Crear Entorno Virtual

### Opción A: Windows (PowerShell/Command Prompt)

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
venv\Scripts\activate
```

### Opción B: Linux/macOS (Terminal)

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate
```

## Paso 3: Instalar Dependencias

```bash
# Instalar todas las librerías requeridas
pip install -r requirements.txt
```

## Paso 4: Verificación de Instalación

```bash
# Verificar Python
python --version

# Verificar librerías clave
python -c "import mesa, shapely, networkx, matplotlib, numpy, pandas; print('Todas las dependencias instaladas correctamente')"
```

## Paso 5: Ejecutar una Simulación de Prueba (Opcional)

```bash
# Ejecutar el motor de simulación con un escenario de ejemplo
python src/MLSM_EvacEngine.py --scenario src/escenarios/Escenario_v4_FINAL.json
```

Si la instalación es exitosa, deberías ver la simulación ejecutándose y generando un archivo GIF en `src/resultados/`.

---

# 🏛️ ARQUITECTURA DETALLADA

## Flujo de Datos General

El sistema MLSM Smart Evacuation sigue una arquitectura modular de dos motores integrados que procesan datos de manera secuencial:

```
┌─────────────────────────────┐       ┌─────────────────────────────┐
│   MLSM_SpatialEngine.py     │       │   MLSM_EvacEngine.py        │
│   (Motor de Diseño CAD)     │       │   (Motor de Simulación)     │
│                             │       │                             │
│ 1. Diseño Interactivo       │──────▶│ 1. Carga JSON MLSM         │
│    - Muros, puertas, salidas│       │    - Geometría + Topología  │
│    - Habitaciones poligonales│      │    - Semántica IndoorGML   │
│                             │       │                             │
│ 2. Procesamiento CSG        │       │ 2. Instancia Agentes        │
│    - Operaciones booleanas  │       │    - Perfiles demográficos  │
│    - Geometría recortada    │       │    - Posiciones iniciales   │
│                             │       │                             │
│ 3. Inferencia Topológica    │       │ 3. Simulación Física        │
│    - Grafo de conexiones    │       │    - Steering behaviors     │
│    - Atributos de navegación│       │    - Pathfinding dinámico   │
│                             │       │                             │
│ 4. Exportación JSON MLSM    │       │ 4. Registro de Métricas     │
│    - Formato híbrido        │──────▶│    - Eventos por agente     │
│    - Compatible simulación  │       │    - Congestión, tiempos    │
└─────────────────────────────┘       └─────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   OUTPUTS           │
                    │ • GIF Animación     │
                    │ • CSV Métricas      │
                    └─────────────────────┘
```

## Componentes Clave

### Motor SpatialEngine: Diseño Paramétrico
La clase `DiseñadorConectado` implementa un editor CAD interactivo que:
- Interpreta clics del usuario para construir geometría 2D
- Aplica operaciones booleanas (Shapely) para recortar puertas en muros
- Infiera automáticamente grafos topológicos usando algoritmos de proximidad
- Exporta archivos JSON con las 3 capas MLSM (geométrica, topológica, semántica)

### Motor EvacEngine: Simulación Multi-Agente
La clase `AgentePro` representa agentes individuales con subsistemas cognitivos:
- **Cerebro**: Pathfinding con Dijkstra dinámico sobre NetworkX
- **Ojos**: Raycast para detección visual de atajos
- **Cuerpo**: Física continua con steering behaviors (atracción + repulsión)
- Integrado en el entorno `ModeloAvanzado` (hereda de Mesa) para simulación ABM

El `GestorDatos` registra métricas en tiempo real para auditoría posterior.

---

# 📂 ESTRUCTURA DE DIRECTORIOS

```
TFG-repo/
├── src/                          # Código fuente principal
│   ├── MLSM_EvacEngine.py        # Motor de simulación multi-agente
│   ├── MLSM_SpatialEngine.py     # Motor CAD paramétrico
│   ├── docs/                     # Documentación técnica detallada
│   │   ├── 01_Arquitectura_EvacEngine.md
│   │   └── 01_Arquitecture_SpatialEngine.md
│   ├── escenarios/               # Archivos JSON MLSM (diseños pre-hechos)
│   │   ├── Escenario_v4_FINAL.json
│   │   └── PLANTA_FINAL.json
│   └── resultados/                # Outputs de simulaciones
│       ├── evacuacion_demo.gif   # Animaciones GIF
│       └── simulacion_prueba_1.csv  # Métricas CSV
├── database/                     # Base de datos y diagramas
│   ├── sql/                      # Scripts SQL para BD relacional
│   │   ├── 00_create_database.sql
│   │   └── 02_tables.sql
│   └── diagramas_entidad_relacion/  # Diagramas ER
├── docs/                         # Documentación del proyecto
│   ├── Memoria.md                # Memoria completa del TFG
│   ├── bibliografia.md           # Referencias académicas
│   └── contenido/                # Contenido estructurado
├── research/                     # Investigaciones complementarias
│   ├── Centralidad_aplicada_a_la_evacuacion/
│   └── sim_estatica/
└── README.md                     # Este archivo
```

### Funciones de Carpetas Clave

- **`src/`**: Núcleo del sistema con los dos motores principales y sus dependencias (escenarios de prueba, documentación técnica)
- **`database/`**: Esquemas SQL antiguos para almacenamiento de configuraciones (no crítico para ejecución básica)
- **`docs/`**: Memoria del TFG y referencias bibliográficas (documentación académica)
- **`research/`**: Experimentos complementarios como análisis de centralidad y simulaciones estáticas

---

# 📊 RESULTADOS & MÉTRICAS

El resultado principal del proyecto incluye una animación GIF y un archivo CSV de métricas. El CSV real `src/resultados/simulacion_prueba_1.csv` registra eventos de simulación por agente y por step.

### Ejemplo de salida real

El CSV contiene estas columnas:

- `Step`: número de iteración de la simulación
- `AgenteID`: identificador único del agente
- `Evento`: tipo de evento registrado (por ejemplo, `CAMBIO_RUTA`, `RECALCULO`, `FUEGO_CREADO`)
- `Valor`: información adicional del evento, como la ruta seleccionada o el motivo del cambio
- `Pos_X`: coordenada X del agente en ese momento
- `Pos_Y`: coordenada Y del agente en ese momento

### Qué representa cada campo

- `Step` permite reconstruir la evolución temporal de la evacuación.
- `AgenteID` habilita análisis por individuo y agrupar trayectorias.
- `Evento` muestra decisiones clave del motor: recalculos de ruta, cambios de trayectoria y activación de amenazas.
- `Valor` documenta la ruta elegida o el estado, por ejemplo:
  - `Habitacion_2 -> Frontera_virtual_6 -> ... -> Salida_5`
  - `Fuego detectado`
- `Pos_X` / `Pos_Y` dan la posición física exacta del agente al registrar el evento.

### Uso práctico

Este formato permite:
- analizar desviaciones de ruta
- detectar congestiones en puertas y fronteras virtuales
- verificar cambios de ruta tras detección de fuego
- generar visualizaciones de trayectorias y mapas de densidad

---

# ⚙️ LIMITACIONES & TRABAJO FUTURO

## Limitaciones actuales

- La simulación es **bidimensional (2D)** y no modela desniveles complejos, rampas ni variaciones de altura.
- El modelo solo considera **física de colisión y steering behaviors**, sin un modelo completo de pánico social, estrés o comportamientos grupales avanzados.
- La persistencia de datos es mínima: los resultados se exportan a archivos locales (`GIF`, `CSV`, `JSON`) y no se integran en una base de datos relacional.
- Las capas semántica y de IndoorGML están encaminadas, pero la compatibilidad plena con el estándar OGC IndoorGML 2.0 aún está en fase de desarrollo.

## Trabajo futuro

- Integrar los scripts de `database/sql/` para gestionar la persistencia de escenarios, resultados y métricas en **PostgreSQL/PostGIS**.
- Añadir un módulo de **persistencia relacional** que almacene:
  - escenarios MLSM
  - rutas calculadas
  - métricas de evacuación
  - eventos de incendio o congestión
- Extender el modelo hacia **3D o semi-3D** para considerar desniveles y escaleras con más precisión.
- Mejorar el comportamiento de agentes con modelos sociales de evacuación, pánico y decisión colectiva.
- Vincular la salida de `MLSM_SpatialEngine.py` a una **pipeline de validación topológica** basada en estándares GIS (por ejemplo, usando PostGIS).

---

# 📚 REFERENCIAS ACADÉMICAS

## Documentación del proyecto

- `docs/Memoria.md` — documento principal de la memoria del TFG
- `docs/bibliografia.md` — bibliografía organizada sobre IndoorGML, bases de datos espaciales y evacuación
- `docs/estructura_tfg.md` — propuesta de estructura del trabajo académico

## Estándares y frameworks clave

- **OGC IndoorGML 2.0** — estándar de referencia para modelado semántico de espacios interiores
- **Mesa** — framework de modelado multi-agente en Python
- **Shapely** — operaciones geométricas y CSG en 2D
- **NetworkX** — análisis de grafos y cálculo de rutas dinámicas

## Referencias recomendadas

- OGC® IndoorGML 1.1 / IndoorGML 2.0
- Documentación de Mesa Framework
- Documentación de PostGIS para persistencia espacial
- Recursos académicos sobre evacuación y modelado indoor listados en `docs/bibliografia.md`


---

# ⚡ QUICK START (5 Minutos)

## 1. Diseñar un Escenario Nuevo

Ejecuta el motor CAD para crear un plano de edificio desde cero:

```bash
python src/MLSM_SpatialEngine.py
```

- Se abre una ventana interactiva de Matplotlib
- Haz clic para dibujar muros (tecla 'm'), puertas (tecla 'p'), habitaciones (tecla 'h')
- Presiona 'e' para exportar el diseño como JSON MLSM
- Cierra la ventana para finalizar

## 2. Ejecutar una Simulación Pre-Hecha

Usa un escenario existente para ver una evacuación completa:

```bash
python src/MLSM_EvacEngine.py --scenario src/escenarios/Escenario_v4_FINAL.json
```

- Carga automáticamente el JSON MLSM
- Ejecuta 1000 steps de simulación (aprox. 5-10 segundos)
- Genera automáticamente:
  - `src/resultados/evacuacion_demo.gif` (animación)
  - `src/resultados/simulacion_prueba_1.csv` (métricas)

## 3. Visualizar Resultados

Abre los archivos generados:
- **GIF**: Visualiza la animación de la multitud evacuando
- **CSV**: Analiza métricas por agente (tiempo de evacuación, trayectorias, congestiones)

¡Listo! Has completado un ciclo completo: diseño → simulación → análisis.

---

## Solución de Problemas Rápida

- **Error de importación**: Asegúrate de tener activado el entorno virtual (`venv\Scripts\activate` en Windows)
- **Ventana no se abre**: Verifica que tengas Matplotlib instalado y un backend gráfico disponible
- **Simulación lenta**: Reduce el número de agentes en el JSON o limita los steps de simulación

---

