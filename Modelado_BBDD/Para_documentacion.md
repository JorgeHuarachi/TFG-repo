# Ayuda en el orden, y que debe estar en la documentación de la creación de la BBDD

Cosas que deben estar en la documentación del modelado de la base de datos.

¿Demasiado, en el Anexo?

| Fase                          | Resultado esperado (documento/artefacto)               |
| ----------------------------- | ------------------------------------------------------ |
| 1. **Análisis de requisitos** | Documento de requisitos + Diccionario de datos inicial |
| 2. **Diseño conceptual**      | Diagrama Entidad-Relación (ER)                         |
| 3. **Diseño lógico**          | Modelo relacional: tablas, claves, tipos               |
| 4. **Diseño físico**          | Esquema en SQL, índices, constraints, particiones      |

## 1. Análisis de requisitos

Objetivo:
Entender qué necesita el sistema y qué datos deben almacenarse.

Acciones:
Reuniones con usuarios y stakeholders.

Revisión de procesos, reglas del negocio.

Identificación de entidades, relaciones, atributos.

Requisitos funcionales y no funcionales.

Documentos de salida:
✅ Documento de requisitos:

Descripción de los procesos del sistema.

Actores involucrados.

Casos de uso o historias de usuario.

Necesidades de persistencia de información.

✅ Lista preliminar de entidades y atributos.

✅ Glosario / Diccionario de datos:

Qué significa cada dato, quién lo usa, si es obligatorio, etc.

## 2. Diseño conceptual

Objetivo:
Convertir los requisitos en un modelo abstracto de alto nivel, independiente del sistema gestor.

Técnicas:
Modelo Entidad-Relación (E-R)

UML si estás en un entorno más orientado a objetos.

Documentos de salida:
✅ Diagrama ER (o DER):

Entidades

Relaciones

Cardinalidades

Atributos

Atributos clave

(Opcional: jerarquías, agregaciones)

✅ Descripción textual del modelo: para complementar el diagrama.

## 3. Diseño lógico
Objetivo:
Traducir el modelo conceptual a un modelo relacional (tablas, columnas, tipos).

Consideraciones:
Normalización (1FN, 2FN, 3FN…)

Relaciones transformadas en tablas (1:N, N:M, etc.)

Definición de claves primarias y foráneas.

Documentos de salida:
✅ Esquema relacional completo (tablas con atributos, claves primarias y foráneas)

✅ Dicionario de datos completo con tipo de datos, restricciones, etc.

✅ Reglas de integridad descritas.

## Ejemplo concreto:
Supón que estás modelando un sistema de gestión de estancias en un hospital:

1. Análisis de requisitos
- El hospital necesita rastrear el movimiento de pacientes por estancias.
- Cada estancia puede tener una o varias balizas.
- Cada paciente tiene una pulsera BLE.
- El sistema debe almacenar lecturas para análisis de rutas y tiempos de permanencia.
2. Diseño conceptual
Entidades: Estancia, Baliza, Lectura, Paciente

Relaciones:

Estancia tiene Balizas (1:N)

Baliza genera Lecturas (1:N)

Paciente detectado en Lecturas (1:N)

Diagrama E-R

3. Diseño lógico
Tablas: Estancia, Baliza, Lectura, Paciente

Relaciones con FK

Atributos normalizados

4. Diseño físico
SQL para cada tabla

Índices en Lectura(Timestamp, Dispositivo)

Optimización para lecturas por fecha y dispositivo

## 🧩 Documentación final ideal:
Una buena documentación incluiría:

✅ Documento de requisitos (narrativa + actores)

✅ Diagrama E-R (diseño conceptual)

✅ Esquema relacional detallado (tablas y relaciones)

✅ Diccionario de datos (tipo, restricciones, descripción de cada campo)

✅ Script SQL de creación del esquema

✅ Plan de índices y rendimiento (si aplica)

✅ Notas sobre uso futuro: por ejemplo, uso con grafos, visualización, etc.

---

