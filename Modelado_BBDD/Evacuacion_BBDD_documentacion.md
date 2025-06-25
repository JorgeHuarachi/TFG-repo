# DOCUMENTACIÓN ``evac_db`` 

## Breve introducción del documento y la base de datos

En este documento se explicara la estructutra y funcionamiento de la base de datos ``evac_db`` el nombre se ha decidido asi, por el objetivo que tiene en principio, pero esta base de datos se divide en 4 bloques conceptuales muy bien diferenciados, estos bloques son:

- **Bloque 1: Edificio y Espacios**
- **Bloque 2: Sensores y Lecturas**
- **Bloque 3: Seguridad y Eventos**
- **Bloque 4: Usuario y Rutask**

Primero se va presentar una imagen completa de la base de datos, para posteriormente centrarnos en cada uno de los bloques para comprender como funcionan y se conectan o relacionan entre si.

![Boceto Wireframe](Figuras_BBDD\evac_db(completo).png)

Algo que se puede explicar y apreciar desde ya es la entidad central ``AREA`` con la cual estan conectadas todos los bloques, esta entidad modela todos los espacioes existentes en todas las plantas del edificio y gracias a indices como ``id_planta`` las que pertenencen a una misma planta estan asociadas a una sola planta.

Brevemente los atributos dan información sobre el espacio, como superficie en metros cuadrados, o capacidad de perosnas, si contiene salidas de evacuación y el tipo de area que es.

Idealmente me gustaria añadir información de las coordenadas del centroide de la superficie de la sala y las dimensiones, para poder reprensentarlo en un mapa o dashboard. seria lo ideal



## Explicación de los bloques

### Bloque 1: Edificios y Espacios (Conexiones)

![Boceto Wireframe](Figuras_BBDD\evac_db(bloque1).png)

El primer bloque además de modelar el Edificio y los Espacios/Areas fisicos modela también las conexiones que existen entre ellos mediante un entidad especifica que es ``CONEXION`` y ``CONEXION_CONDICIONAL``.
