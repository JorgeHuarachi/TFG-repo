# Complex Event Processing (CEP) - Evaluación de Peligrosidad

Este anexo documenta el módulo de **Complex Event Processing** para análisis dinámico de seguridad en espacios interiores durante evacuaciones.

## Contenido

- **CEP_EVENTOS.md** — Especificación del motor CEP simulado, reglas de peligrosidad y métricas ambientales

## Notas

En cuanto a esto se ha decidido simular el resultado que se obtiene tras este proceso, que se traduce en un score de seguridad.

De otra forma debería modelar y definir reglas propias de un motor de CEP real.

Todo lo que va detrás se deja indicado, sería conectar una baliza y simular, al mejor uno de los nodos y que el resultado de analizar el flujo y stream de datos se traduzca un score de seguridad dinámico.

---

## 📌 Reclasificación Futura

**Nota:** Este contenido fue clasificado como **anexo del TFG** en la reorganización de documentación (2026). 

En futuras versiones, podría reclasificarse como documentación técnica en `docs/technical/` si:
- Se implementa un motor CEP real (no simulado)
- Se separa de la memoria del TFG
- Se convierte en especificación técnica mantenida independientemente

Por ahora, se mantiene en `tfg/anexos/` para preservar su contexto académico.
