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

## **EN LA RECOMENDACION DE RUTAS**
Que los valores de centralidad solo sumen 1 cuando el camino es nuevo, para lo que pasa con el nodo 6 por ejemplo, quitando todas las aristas marca un solo camino minimo siempre el mismo, da igual que arista quites pero lo cuenta como 4 caminos minimos, pero esos 4 son el mismo, es decir es el mismo, pero en otras circunstancias.
Esto quiere decir que aun quitando cualquiera de las aristas de ese camino el camino minimo nuevo siempre sera el mismo sin importar cual.

Vale para esto se me ocurre:
1. Crear un objeto que guarde todos los caminos minimos y que al finalizar quitando todas las aristas, quite las que se repiten de tal forma que el numero de caminos minimos serian realmente diferentes. En el caso mencionado antes seria 1, porque todos son iguales

## EL METODO DE ANIMACION DE MATPLOTIB

Fijate que los nuevos caminos tu has hecho que si ya se han procesado cno anterioridad no lo procesen otra vez, por ejemplo en nuestro caso a nodo 5.

el primer nuevo camino quitando 0,1 es 0,4,5 en el siguiente proceso quitas 0,4 y en el siguiente 4,5.
Pero Resulta que quitando el camino 1,4 queda el mismo camino 0,4,5 entonces hacer el mismo proceso, aunque:
CONSIDERALO quizas tiene sentido hacer el mismo proceso porque la hay diferencia con el anterior, que ademas no tiene 1,4 pero si tiene 0,1. **CUIDADO**