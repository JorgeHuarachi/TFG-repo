# **UBICACIÓN DEL USIARIO**
La ubicación del usuario en principio seria mediante una triangulació de señales de las balizas (Debe haber un apartado de optimización de la triangulación del usuario, algo que todavia no se hacer).

Esta triangilación me señalara a un punto o región especifico en el espacio para que esta triangulación sea efectiva o tenga sentido y poder visualizarlo tengo que tener la distrubución tanto de los espacios como de donde estan situados las baliza, seguramente en coordenadas (latitud, longitud) pero referenciadas a un punto fijo en la planta, este punto de coordenadsa (0,0) podria ser por ejemplo una baliza de referencia.

Nota: Existe en SQL un tipo de dato, el dato geométrico, con el que toqué cosas con ayuda de chat gpt para ver de que se trataba, y junto con html, vi que es posible representar un punto, una linea o un poligono sobre un mapa en una especie de web, pero nada sobre poder refrescar o actualizar los datos y que cambien continuamente, lo ideal y deseable es que eso se represente en un mapa/plano de la planta a evacuar en cuestión y que sea capaz de dibujar un punto donde se situe en usuario y se mueva junto con el.

Por lo tanto, necesito:
1. Que las tablas BALIZA tenga de atributos las coordenadas donde se encuantran dentro del edicifio/planta.
2. Que la tabla LECTURA tenga atributos de intensidad, frecuencia de la señal con un timestamp y quizas algo como la fiabilidad/calidad de la señal.
3. Reprenentar todos los espacios con coodenadas.
4. Con estos datos y un algortimo de triangulación obtener la ubicación estimada del usuario y guardar esta información en una tabla UBICACIÓN_ESTIMADA que claramente debe estar asociada a un usiario, esta información debe ir guardandose en un histórico.

# **PROCESAMIENTO DE DATOS/SERIES_TEMPORALES EN UN MOTOR CEP (Complex Event processing)**
Esto viene de la necesidad de aplicar CEP (Complex Event processing) o (PRocesamiento de eventos complejos) y de que los datos de las lecturas se tienen que procesar en tiempo real.
Se puede hacer en python, la opción más indicada ahoracmismo puede se pyFlink por la similaridad con SQL.

Para esto necesito:
1. Que los datos, no pasen por la base de datos relacional, sino que los datos lleguen al motor CEP desde un kafka (o MQTT).
Para trabajar con kafka necesito diseñar una estructura de datos basada en eventos.
2. A su vez para ir al kafka necesita un intermediario gateway.
3. Luego de kafka para procesarlo se puede ir a flink.

Lo bueno de esto es que en teoria trabaja con MongoDB o PostgreSQL