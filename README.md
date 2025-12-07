Archivos relacionados al TFG como:

* [Boceto WireFrame](Boceto_wireframe/)
* [Centralidad aplicada a la evacuación](Centralidad_aplicada_a_la_evacuacion/)
* [CEP](CEP/) _(se simula un "Score" final)_
* [Doc_TFG](Doc_TFG/) _(organización docuemntal)_
* [Modelado_BBDD](Modelado_BBDD/)
* [visual_simulacion](visual_simulacion/) _(se ven las primeras simulaciones y preubas)_

> [_Nota para alguien que recien clona este repositorio_](Notas/Nota_venv_requiremetns.md)

| Tema                   | SOTA (referencia)                                                                                 | Decisión adoptada en el TFG                                                                                    | Justificación técnica                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Modelo de datos indoor | **IndoorGML**: espacio celular + grafo dual [Kang et al., 2017; OGC, 2020; Diakité et al., 2020]. | Esquemas `indoorgml_core`/`indoorgml_navigation` en **PostGIS**, *views* por nivel, validaciones geométricas.  | Alinear con estándar facilita interoperabilidad y extracción de redes navegables. |
| Extracción/redes 3D    | Red basada en geometría (SFCGAL) [Tekavec et al., 2020].                                          | Soporte 2.5D inicial con rutas en planta; extensión 3D como trabajo futuro.                                    | Reduce complejidad, mantiene compatibilidad con IndoorGML.                        |
| Rutas dinámicas        | Campo dinámico, quickest vs shortest [Xiong et al., 2017; Wagoum et al., 2011].                   | Coste (w' = w(1+\beta r)), filtro **τ**, **EMA** para *scores*; replan por evento/tiempo.                      | Modelo simple, interpretable y reproducible; capta riesgo y evita parpadeo.       |
| Robustez               | **k-shortest paths** (Yen; mejoras) [Yen, 1971; Hershberger et al., 2003].                        | Cálculo de *k-rutas* y métrica **R** para redundancia.                                                         | Alternativas preparadas ante fallos locales, coste controlable.                   |
| CEP/contexto           | FlinkCEP; definición de patrones y *event sinks* [FlinkCEP Docs].                                 | **Contrato de eventos** estable y *adapters*; **se asume** CEP y **se simula** su salida.                      | Desacopla ingestión y ruteo; facilita sustitución por plataformas reales.         |
| Posicionamiento        | BLE para entornos confinados [Belka et al., 2021].                                                | App móvil BLE **futura**; el TFG no la implementa.                                                             | Mantener foco en núcleo de decisión; compatibilidad futura.                       |
