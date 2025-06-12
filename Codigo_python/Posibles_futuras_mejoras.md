## **UBICACIÓN DEL USIARIO**
La ubicación del usuario en principio seria mediante una triangulació de señales de las balizas (Debe haber un apartado de optimización de la triangulación del usuario, algo que todavia no se hacer).

Esta triangilación me señalara a un punto o región especifico en el espacio para que esta triangulación sea efectiva o tenga sentido y poder visualizarlo tengo que tener la distrubución tanto de los espacios como de donde estan situados las baliza, seguramente en coordenadas (latitud, longitud) pero referenciadas a un punto fijo en la planta, este punto de coordenadsa (0,0) podria ser por ejemplo una baliza de referencia.

Nota: Existe en SQL un tipo de dato, el dato geométrico, con el que toqué cosas con ayuda de chat gpt para ver de que se trataba, y junto con html, vi que es posible representar un punto, una linea o un poligono sobre un mapa en una especie de web, pero nada sobre poder refrescar o actualizar los datos y que cambien continuamente, lo ideal y deseable es que eso se represente en un mapa/plano de la planta a evacuar en cuestión y que sea capaz de dibujar un punto donde se situe en usuario y se mueva junto con el.

Por lo tanto, necesito:
1. Que las tablas BALIZA tenga de atributos las coordenadas donde se encuantran dentro del edicifio/planta.
2. Que la tabla LECTURA tenga atributos de intensidad, frecuencia de la señal con un timestamp y quizas algo como la fiabilidad/calidad de la señal.
3. Reprenentar todos los espacios con coodenadas.
4. Con estos datos y un algortimo de triangulación obtener la ubicación estimada del usuario y guardar esta información en una tabla UBICACIÓN_ESTIMADA que claramente debe estar asociada a un usiario, esta información debe ir guardandose en un histórico.

[Usuario] ---[tiene]--- [PosiciónUsuario] ---[en]--- [Espacio]

Tabla PosicionUsuario:

| id | usuario_id (FK) | timestamp | espacio_id (FK) | coordenadas (x, y, z) | precisión | fuente (BLE, UWB, etc.) |

El algoritmo de triangulación como tal va fuera de la base de datos.

## **PROCESAMIENTO DE DATOS/SERIES_TEMPORALES EN UN MOTOR CEP (Complex Event processing)**
Esto viene de la necesidad de aplicar CEP (Complex Event processing) o (PRocesamiento de eventos complejos) y de que los datos de las lecturas se tienen que procesar en tiempo real.
Se puede hacer en python, la opción más indicada ahoracmismo puede se pyFlink por la similaridad con SQL.

Para esto necesito:
1. Que los datos, no pasen por la base de datos relacional, sino que los datos lleguen al motor CEP desde un kafka (o MQTT).
Para trabajar con kafka necesito diseñar una estructura de datos basada en eventos.
2. A su vez para ir al kafka necesita un intermediario gateway.
3. Luego de kafka para procesarlo se puede ir a flink.

Lo bueno de esto es que en teoria trabaja con MongoDB o PostgreSQL

## **EN LA RECOMENDACION DE RUTAS (nota)**
Que los valores de centralidad solo sumen 1 cuando el camino es nuevo, para lo que pasa con el nodo 6 por ejemplo, quitando todas las aristas marca un solo camino minimo siempre el mismo, da igual que arista quites pero lo cuenta como 4 caminos minimos, pero esos 4 son el mismo, es decir es el mismo, pero en otras circunstancias.
Esto quiere decir que aun quitando cualquiera de las aristas de ese camino el camino minimo nuevo siempre sera el mismo sin importar cual.

Vale para esto se me ocurre:
1. Crear un objeto que guarde todos los caminos minimos y que al finalizar quitando todas las aristas, quite las que se repiten de tal forma que el numero de caminos minimos serian realmente diferentes. En el caso mencionado antes seria 1, porque todos son iguales
2. poner nodo final jsonb
3. floyd warshall
4. estudiar el problema de congestion y choque de flujos

## EL METODO DE ANIMACION DE MATPLOTIB

Fijate que los nuevos caminos tu has hecho que si ya se han procesado cno anterioridad no lo procesen otra vez, por ejemplo en nuestro caso a nodo 5.

el primer nuevo camino quitando 0,1 es 0,4,5 en el siguiente proceso quitas 0,4 y en el siguiente 4,5.
Pero Resulta que quitando el camino 1,4 queda el mismo camino 0,4,5 entonces hacer el mismo proceso, aunque:
CONSIDERALO quizas tiene sentido hacer el mismo proceso porque la hay diferencia con el anterior, que ademas no tiene 1,4 pero si tiene 0,1. **CUIDADO**

## FORMAS DE INTERACTUAR CON EL USUARIO

Sobretodo para recomendar la ruta y el usuario sepa donde ir

- proyectores tipo ikea
- buzers
- tipo maps (cochecito)

## (movilidad) SOBRE LA RECOMENDACIÓN DE RUTAS DE EVACUACIÓN (SOBRE EL MODELADO ESPACIAL A GRAFO)

Leyendo al respecto de modelado de espacios como grafos, es cierto que existe una problemática importante a tener en cuenta, y es respecto a las presonas con movilidad reducida, es trementamente interesante estudiar este como un caso aparte, ya que para estas personas el grafo navegable es diferente muchas veces, basta con tener un escalón para que la navegabilidad de estas personas no sea el mismo que para otras personas.

En pocas palabras, debido a la existencia de escalones y escaleras el grafo navegable de una persona con movilidad reducida (silla de ruedas) va a ser diferente, por lo que estas personas tienen que tener una reocmendación de rutas diferentes.

A cada usuario le asignas:
puede_usar_ventanas: true/false
puede_usar_escaleras: true/false
velocidad estándar: (m/s)

Esto permite a tu algoritmo de rutas generar:

Rutas personalizadas por usuario.

Costes diferenciados por segmento.

Validación de transitabilidad real.

## (ventanas emergencia) SOBRE LA RECOMENDACION DE RUTAS
Ya lo pense antes, sobre utilizar las ventanas de los pisos bajos o que no tengan gran altura como salidas de escape extrema, bajo ciertasc condiciones importantes.

Tambien porque los bomberos utilizan las ventanas (ciertas ventanas) como puntos de acceso claves para el rescate.

Planta baja / baja altura
Correcto: en plantas bajas o primeras plantas, es razonable pensar que una ventana puede ser salida de emergencia última instancia.

Algunos protocolos de bomberos consideran incluso ventanas como puntos de acceso/rescate.

Las ventanas accesibles podrían modelarse como nodos adicionales de "escape extremo".

Puedes modelarlas así:

En tu Espacio, defines VentanaDeEmergencia (booleano).

Cada ventana se convierte en un posible nodo adicional del grafo.

Solo es "navegable" en situaciones extremas, cuando:

Todas las puertas bloqueadas.

El usuario puede físicamente usar la ventana (limitación de movilidad).

 Planta alta (no recomendable)
A partir de segundas o terceras plantas, el riesgo de daño supera la utilidad salvo con equipos externos (bomberos, helicópteros).

Normalmente no las incluirías como nodos de evacuación.

### Uso de ventanas para conectar espacios en el interior del edificio, entre salas

Esta ventana forma parte del grafo no navegable realmente.
En Area podría definir un atributo VentanaDeEmergencia (booleano) se convertiría en un nuevo nodo? quizas tiene mas sentido que se convierta en una arista que conecta directamente con el exterior

También es un razonamiento muy bueno.

Si dos espacios colindantes tienen ventanas comunicadas (ej. oficinas vecinas), puede tener sentido modelar esa ventana como una arista de escape secundaria.

Este tipo de rutas sólo serían habilitadas:

Bajo emergencia grave.

Si el perfil del usuario lo permite (movilidad total).

Si el sistema detecta un "callejón sin salida".

En cuanto a que las ventanas conecten espacios, una nueva entidad
PuntoAccesoEspecial.
| id | espacio_id | tipo (ventana, escotilla, trampilla) | altura | conectividad (espacio objetivo) | uso_permitido (booleano por tipo de usuario) |

Relación Espacio -- contiene --> PuntoAccesoEspecial.

Relación PuntoAccesoEspecial → añade arista especial al grafo de rutas.

### Bloqueo de puertas
Basicamente eso
Añadir entidad EstadoPuerta:

| id | puerta_id | timestamp | estado (abierta, cerrada, bloqueada) | origen_evento |

De esta forma:

El sistema puede marcar puertas como bloqueadas por:

Algoritmos automáticos (si los tuvieras).

Input manual de usuarios (app móvil, emergencias, seguridad).

Inferencia de CEP (si correlacionas flujos de movimiento + sensores).

El algoritmo de rutas simplemente excluye del grafo las aristas cuya puerta.estado sea bloqueada.

Usuario recibe ruta sugerida.

Si llega a una puerta bloqueada:

Opción: "Reportar bloqueo de puerta".

El sistema marca la puerta como bloqueada.

Se recalculan rutas dinámicas evitando esa arista.

Usuario -- tiene --> PosiciónUsuario
Usuario -- recibe --> RutaSugerida
Espacio -- tiene --> EstadoEspacio
Puerta -- tiene --> EstadoPuerta
Baliza -- mide --> Medida
Baliza -- genera --> Evento (vía CEP)
Evento -- afecta --> Espacio / Puerta

## (para TFM como mucho) TEMA FUTURO DELCIADO

Sobre hacer este proyecto adaptativo a peligros dinámicos.

Ahoramismo se esta toamndo en cuenta peligros ambientale sdinamicos en el tiempo, que progresan y se pueden propagar.

Pero, quiero que sea escalable al punto de tener en cuenta un peligro de intrusion peligrosa inmintente, como el problema de los tiroteos en escuelas de EEUU, esto lo planteo de la siguiente forma:
1. Si se detecta una intrusión y de determina su naturaleza peligrosa para todas las personas tratar de dar recomendaciones de accion a todas las personas menos al peligro, es decir, que no solo eviten el peligro, sino que se alejen de el peligro.

2. Que existan sistemas de actuación automático, con muchisimo cuidado para evitar que el peligro se acerque a la gente, por ejemplo, dejarlo sin luz, desorientarlo, bloquear el paso, en un caso ideal encerrarlo en una habitación y alejarlo de la gente. Esto conlleva muchas cosas y da miedo pensarlo pero seria un paso adelante en la actuación ante estas situaciones que no se deberían dar.

Idea:
- Que gracias a un despliegue de altavoces o buzzers muy potentes, o sirenas de emergencia, se puedan hacer sonar aquellas que estan con la amenaza movil a medida que avanza, de tal forma que las demas personas pueden tener una referencia de donde esta, y hacia donde no tienen que ir, que es evitando el sonido.

## Me gustaria (Ambicioso)

Que existiera el modelo BIM IFC de las torres gemelas, y simular la emergencia ocurrida en la tragedia que termino con su derrumbe y la perdida de muchas vidas que no se pudieron evacuar.

Con el modelo BIM y el material existente me serviria para poder probar mi motor de actuación y recomendación de rutas de emergencia.

## cosas de como se dice:
Lo que tú describes se suele llamar en términos más formales:

Tipo de conexión	Nombre técnico habitual
Puerta normal	Navigable Connection
Ventana, hueco, ruptura	Non-Navigable Adjacency o Conditional Connection
Paredes adyacentes	Physical Adjacency
Escalones o rampas intransitables	Accessibility Constraints

Muchos de estos conceptos aparecen en algunas extensiones de IFC, como el IfcSpaceBoundary, IfcDoor, IfcWindow, IfcOpeningElement, etc.

Por tanto: ✅ sí, el razonamiento de fondo es completamente correcto.

## Conductos de ventilación

Los típicos ductos (HVAC, aire, extracción).

En algunas películas de acción — y en algunos casos reales — la gente puede desplazarse por dentro.

Muy ocasionalmente (pero real en rescates), bomberos o robots de rescate podrían acceder a través de ellos.

Sí, los puedes ver como una subcapa aún más extrema dentro de ACCESO_CONDICIONAL.

No es habitual conectarlos al grafo de navegación principal.

Solo se activan:

Si la evacuación primaria ha fallado.

Si el perfil de movilidad es muy especializado (bomberos, rescate robotizado, situaciones límite).

¿Los conductos conectan todas las salas?
❌ No necesariamente.

Normalmente:

Conectan zonas técnicas, cuartos de máquinas, salas principales, núcleos de ventilación.

Las bocas de salida están dentro de las áreas, pero el conducto central puede no conectar todas las salas directamente.

Su topología suele estar disponible en los modelos BIM (IFC → IfcDuctSegment).

Para qué casos te resulta útil?
🚑 Rescate interno: bomberos robóticos, drones, microbots.

🏚 Evacuación extrema: zonas atrapadas completamente, última alternativa.

🧪 Simulaciones de riesgo: propagación de fuego, humo, gases.

## sobre los atributos repetidos:
✔️ Conclusión: Está bien tenerlos en ambos sitios. Asegúrate de definir una regla de herencia o prioridad en la lógica de negocio:
Ej. “si se define en la conexión individual, tiene prioridad sobre el tipo”.

## cep conexion
⚙️ “Los eventos se derivan de las lecturas mediante un motor externo CEP (Complex Event Processing), por lo que no existe una relación directa en el modelo físico. No obstante, existe una dependencia lógica entre LECTURA → EVENTO, importante para entender el flujo de datos.”


__
Este chat empieza a ser algo lento, crees ser capaz de darme un prompt suficicientemente elaborado como para dirigirme a un nuevo chat contigo y poder continuar con la misma calidad de conversación que tengo aqui pero con mas velocidad?
__
