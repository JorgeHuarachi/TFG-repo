# DOCUMENTACIÓN ``evac_db`` 

*Pendientes

- pasar todo a ingles
- imcluir imagenes de figuras 
- Hacer el video antes de todo, porque voy a tardar en hacer lo anterior

## Breve introducción del documento y la base de datos

En este documento se explicara la estructutra y funcionamiento de la base de datos ``evac_db`` el nombre se ha decidido asi, por el objetivo que tiene en principio, pero esta base de datos se divide en 4 bloques conceptuales muy bien diferenciados, estos bloques son:

- **Bloque 1: Edificio y Espacios**
- **Bloque 2: Sensores y Lecturas**
- **Bloque 3: Seguridad y Eventos**
- **Bloque 4: Usuario y Rutask**

Primero se va presentar una imagen completa de la base de datos, para posteriormente centrarnos en cada uno de los bloques para comprender como funcionan y se conectan o relacionan entre si.

![Boceto Wireframe](Figuras_BBDD/evac_db(completo).png)

### **`AREA`**
Algo que se puede explicar y apreciar desde ya es la entidad central ``AREA`` con la cual estan conectadas todos los bloques, esta entidad modela todos los espacioes existentes en todas las plantas del edificio y gracias a indices como ``id_planta`` las que pertenencen a una misma planta estan asociadas a una sola planta.

Brevemente los atributos dan información sobre el espacio, como superficie en metros cuadrados, o capacidad de personas, si contiene salidas de evacuación y el tipo de area que es.

Idealmente me gustaria añadir información sobre la posición espacial de la superficie de la sala y las dimensiones, para poder reprensentarlo en un mapa o dibujarlo en algun sitio. Se que existen datos de tipo ``GEOMETRY`` que si me permite meter datos como poligonos, lineas o puntos, pero de momento no lo he implementado. He dado prioridad a conocer las conexiones que existen entre Areas/salas/espacios. 



## Explicación de los bloques

### Bloque 1: Edificios y Espacios (Conexiones)

![Boceto Wireframe](Figuras_BBDD/evac_db(bloque1).png)

El primer bloque además de modelar el Edificio y los Espacios/Areas fisicos modela también las conexiones que existen entre ellos mediante un entidad especifica que es `CONEXION` y `CONEXION_CONDICIONAL`.

Estas dos entidades tienen atributos muy similares porque modelan cosas tremendamente similares pero que se usan en diferentes condiciones.

#### **`CONEXION`** 
Modela las puertas o espacios de acceso que conectan un area con otra y que son **navegables en condiciones normales**, esto es lo que diferencia una entidad con otra, esta entidad generalmente van a ser puertas, se podria renombrar a `PUERTAS` o `DOORS` en inglés.

**Funcionamiento:** Desde aquí se extrae un primer grafo `GRAFO_AREAS_NAVEGABLE`, ya que las conexiones nos dan información de que salas se conectan con que salas mediante que puertas y es el que se usa desde el principio.

Ejemplo de registro:

| id_conexion | id_area_origen | id_area_destino | Nombre   | descripcion                            | ancho_metros | alto_metros | flujo de personas min | bidireccional | id_tipo_conexion |
|-------------|-----------|------------|----------|----------------------------------------|--------|------|-------------------|----------------|------------------|
| 01          | Sala A    | Sala B     | Puerta AB | acceso| 1.2    | 2.2  | 1                 | sí             | 01               |
| 02          | Sala B    | Sala C     | Puerta BC | acceso | 1.2    | 2.2  | 2                 | sí             | 02               |

Con esta información podria tomar como nodos las Salas A B C y conectarlas A-B mediante la puerta AB y B-C mediante la puerta BC.[AÑADIR IMAGEN REPRESENTATIVA]

*Nota: Desde aqui tambien se puede extraer un grafp extraer un grafo DOOR-TO-DOOR del que me gustaria hablar mas adelante y es muy interesante ne modealdo de  espacios interiores*


#### **`CONEXION_CONDICIONAL`** 
Modela todo aquello que no es una puerta y que conecta salas/areas/espacios entre si (Ventanas, huecos, ductos de ventilación) y que son **no navegables en condiciones normales**, esto quiere decir que estas conexiones no se deben tener en cuenta desde el principio, solo se deben tener en cuenta en caso de emergencia extrema, donde se bloquen muchos caminos, se bloqueen muchas puertas o se entre en una situación de callejón sin salida, el objetivo en esta situaciones será de proporcinoar una alternativa que conecte con otro espacio desde el cual exista una ruta adecuada o directamente con el exterior.