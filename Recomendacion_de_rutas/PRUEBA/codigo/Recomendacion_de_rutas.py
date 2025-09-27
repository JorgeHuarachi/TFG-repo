import networkx as nx 
import matplotlib.pyplot as plt
import numpy as np
from itertools import combinations as combs
from matplotlib.animation import FuncAnimation # GRACIAS A ESTO PUEDO ANIMAR LOS GRAFOS QUE OBTENGO
from matplotlib.lines import Line2D


# ###############################  FUNCIONES ###############################
## ANALISIS DE SENSIBILIDAD DE RUTAS MINIMAS 
# YO LO ENTIENDO COMO ALGO ASI COMO LA ROBUSTEZ ESTRUCTURAL DE LA RED EN CASO DE DEJAR DE TENER ARISTAS DISPONIBLES
# PARA MI SERIA COMO UNA CENTRALIDAD DE NODOS BASADO EN CAMINOS MINIMOS RESTRINGIDOS POR EL TIEMPO

def Agrupacion(camino):
    """Agrupa en conjuntos de tamaño 2 una lista de tamaño mayor a 2, esto se
    hace porque necesito tenermo en ese formati y no como una sola lista.
    
    Utiliza List Comprehension.
    
    Parameters
    ----------
    
    camino : Es una lista de varios valores de logitud mayor o igual a 2.
    
    return
    --------
    
    pares : Una colección de tuplas de tamaño 2 que contiene todos los 
        subconjuntos del parametro camino de forma secuencial (No los ordena
        de forma exacta pero ordena solo teniendo en cuenta el primer indice, 
        esto no es importante para lo que queremos que es simplemente tener esta
        lista para poder trabajar con ella) 
        
    Example
    -------
    >>> camino = [[5], [5, 2], [5, 2, 3, 1], [5, 6, 7]]
    >>> print(Agrupacion(camino))
    {(3, 1), (5, 4), (2, 3), (6, 7), (5, 6), (1, 0), (5, 2)}
    
    Notas
    -----
    Si hay elementos de una solo valor no los toma, si hay elementos de dos
    los toma directamente, si hay elementos de mas de dos valores los divide
    en grupos de dos consecutivos ya sean pares o impares, siempre daran 
    grupos de dos.
    
    """
    
    lista = [(camino[i],camino[i+1]) for i in range(len(camino)-1)]
    return lista

def Visualizar(G,posiciones,lista,aristas_quitadas,ax, title="Gráfico",coste=None, origen=None, destino=None,coste_max=None):
    """Permite visualizar ciertas aristas u nodos que pertenecen a un grafo más grande de un color diferente
    se debe conocer en la malla de graficos que posición ocupan (ejex,ejey)
    
    Parameters
    ----------
    
    G : Grafo completo dibujado anteriormente.
    
    pos : Las posiciones de todos los nodos ya definida.
    
    lista : Conjunto de nodos que se desea pintar (normalmente aquellos que pasan por las aristas)
    
    aristas : Conjunto de arista que se desea pintar (normalmente aquellas que pasan por los nodos)
    
    ax : matplotlib.axes.Axes
        Eje de Matplotlib para dibujar.
        
    Return
    --------
    Se limita a dibujar las aristas y los nodos del grafo con los colores, no los muestra por pantalla
    si se quiere ver los gráficos dibujados se debe usar: plt.show() despues de dibujar todo lo deseado.
    
    """
    ax.clear()
    aristas = Agrupacion(lista) # Agrupa en conjuntos de 2
    
    # Dibuja los nodos y las aristas, en instrucciones diferentes
    nx.draw_networkx_nodes(G, posiciones, ax=ax, node_size=150, node_color="lightblue")
    nx.draw_networkx_edges(G, posiciones, ax=ax, width=1, edge_color="gray")

    # if aristas_quitadas:
    #     nx.draw_networkx_edges(
    #         G, posiciones,
    #         edgelist=list(aristas_quitadas),
    #         ax=ax,
    #         style="--",
    #         edge_color="gray",
    #         width=2
    #     )
    
    # Camino “anterior” tenue (sombra): puedes guardar en estados previos si quieres
    # nx.draw_networkx_edges(G, posiciones, edgelist=[...], style="-", edge_color="pink", alpha=0.3, width=2)
 

    # color a una aristas y nodos
    nx.draw_networkx_edges(G, posiciones, aristas, ax=ax, width=2, edge_color="red")
    nx.draw_networkx_nodes(G, posiciones, lista, ax=ax, node_size=150, node_color="red")
    
    # etiquetas
    nx.draw_networkx_labels(G, posiciones, ax=ax)
    
    # Leyendas
    legend_items = [
        Line2D([0], [0], color="red", lw=2, label="Camino actual"),
        Line2D([0], [0], color="gray", linestyle="--", lw=2, label="Arista eliminada")
    ]
    # Titulo
    ax.legend(handles=legend_items, loc="upper right")
    
     
    ax.set_title(title)
    
    info = f"Coste máximo: {coste_max}\nCoste: {coste}"
    if origen is not None and destino is not None:
        info += f" | Origen: {origen} → Destino: {destino}"
    ax.text(0.02, 0.02, info, transform=ax.transAxes, verticalalignment="bottom")

def quitar_k_aristas(matriz, indices, k):   
    """Esta función permite obtener las matrices resultado de quitar elementos de una lista de aristas en conbinaciones de k aristas.
    es decir, de la lista de aristas quitando 1, 2, 3 o más aristas (todas las combinaciones de estas)
    
    
    Parameters
    ----------
    
    matriz : Matriz de adyacencia
    
    indices : lista de aristas para quitar en combinaciones de k aristas
    
    k : numero de combinacion de aristas para quitar
    
    Return
    ------
    
    
    Example
    -------
    
    
    """
    
    if k > len(indices):
        raise ValueError("k no puede ser mayor que la cantidad de aristas disponibles.") # Si por lo que sea pones mas numero de aristas de las que existne en indices
    for combinacion in combs(indices, k):
        temp = matriz.copy() # 
        for i, j in combinacion:
            temp[i, j] = 0
            temp[j, i] = 0
        yield temp,combinacion  #  Devuelve la matriz y las aristas quitadas


def Caminos_diferentes(G_costes,G_seguridades,posiciones,destinos,f_tolerancia,f_seguridad):
    """ 
    [MEJORAS PENDIENTES]
    **Diametro (para la visualizacion)**
    **f_toleranciaerancia VARIABLE? PERO COMO PUEDE VARIAR?**
    **NECESITO QUE SEA MÁS FLEXIBLE PARA MAXIMIZAR EL NUMERO DE CAMINOS DIFERENTES**
    **AÑADIR FILTRO DE SEGURIDAD**
    **Es funcional, pero, no proporciona un numero para los nodos destino, se queda sin valores.**
    **Muchas formas de optimizar (Yield) (deepcopy) (itertools.combinations()) (mediante lógica de indices)**

    Parameters
    ----------
    
    G_costes : Matriz adyacencia de costes de todas las aristas.
    
    G_seguridades : Matriz adyacencia de las seguridades de todas las aristas.
    
    posiciones : Coordenadas de los nodos en en plano xy (Para definir una visualicación).
    
    destinos : Aquellos nodos que se considerán como destinos seguros en la busqueda de caminos diferentes. 
    
    f_tolerancia : Factor de tolerancia con respecto al coste de camino minimo principal de un nodo a un destino, define el limite superior para los caminos minimos diferentes aceptables desde el mismo nodo al mismo destino por debajo de ese valor.
    
    f_seguridad : Factor de seguridad crítica, es el límite inferior de la seguridad aceptable para el tránsito o flujo a través de una arista, aquellas aristas que tengan una seguridad inferior a este limite, no se toman en cuenta en el calculo.
    
    returns
    -------
    
    centralidad_evacuacion : Diccinario con los nodos como clave que almacena el numero de caminos mínimos diferentes por cada nodo a cada nodo destino.
    
    Examples
    --------
    
    >>> matriz_costes=np.array([
        [00, 40, 00, 00, 70, 00, 00, 80], 
        [40, 00, 60, 10, 00, 00, 00, 00],
        [00, 60, 00, 10, 00, 20, 00, 00],
        [00, 10, 10, 00, 10, 00, 00, 00],
        [70, 00, 00, 10, 00, 30, 30, 20],
        [00, 00, 20, 00, 30, 00, 30, 00],
        [00, 00, 00, 00, 30, 30, 00, 10],
        [80, 00, 00, 00, 20, 00, 10, 00]])
        
    >>> matriz_seguridades=np.array([
        [0.0, 1.0, 0.4, 0.4, 1.0, 0.4, 0.4, 1.0], 
        [1.0, 0.0, 1.0, 1.0, 0.4, 0.4, 0.4, 0.4],
        [0.4, 1.0, 0.0, 1.0, 0.4, 1.0, 0.4, 0.4],
        [0.4, 1.0, 1.0, 0.0, 1.0, 0.4, 0.4, 0.4],
        [1.0, 0.2, 0.2, 1.0, 0.0, 0.9, 0.9, 0.2],
        [0.2, 0.6, 0.6, 0.6, 0.9, 0.0, 0.9, 0.6],
        [0.4, 0.4, 0.4, 0.4, 0.9, 0.9, 0.0, 1.0],
        [1.0, 0.1, 0.1, 0.1, 1.0, 0.1, 1.0, 0.0]])
    
    >>> coordenadas = {
        0: (0, 0.25), 
        1: (2, 0.00), 
        2: (4, 0.00), 
        3: (3, 0.15), 
        4: (4, 0.25),
        5: (6, 0.15),
        6: (5, 0.40),
        7: (3, 0.45),}
    
    >>> f_tol = 0.5
    
    >>> destinos_seguros = [3,6,7]

    >>> f_sec = 0.7

    >>> centralidades = Caminos_diferentes(
            G_costes = matriz_costes,
            G_seguridades = matriz_seguridades,
            posiciones = coordenadas,
            destinos = destinos_seguros,
            f_tolerancia = f_tol,
            f_seguridad = f_sec)
            
    >>> print(centralidades)
    
    Nodos destino: [3, 6, 7]
    Factor de tolerancia: 0.5
    Nodos origen [0, 1, 2, 3, 4, 5, 6, 7]
    Las centralidades de evacuación para cada nodo hacia los nodos destino:
    
    (0, [0, 4, 1])
    (1, [0, 1, 0])
    (2, [0, 1, 0])
    (3, [1, 0])
    (4, [0, 1, 0])
    (5, [2, 0, 2])
    (6, [1, 0])
    (7, [0, 0])
    
    {0: [0, 4, 1], 1: [0, 1, 0], 2: [0, 1, 0], 3: [1, 0], 4: [0, 1, 0], 5: [2, 0, 2], 6: [1, 0], 7: [0, 0]}
    
    Nota
    ----
    
    Actualmente la funcion saca por pantalla la visualizaicón de todos los grafos que ha calculado y analizado, esto no es necesario pero es muy interesante para la visualización
    
    """
    
    ## ---- FILTRO DE SEGURIDAD ---- 
    
    i_list,j_list=np.where(G_seguridades<f_seguridad)

    for iter in range(len(i_list)):
        
        G_costes[i_list[iter],j_list[iter]]=0
      
    ## ----------------------------- 

    G = nx.from_numpy_array(G_costes) # paso de matriz a grafo
    
    nodos = list(G.nodes) # Obtengo una lista de todos los nodos
    
    # Inicializo donde voy a guardar el nr de caminos diferentes diferentes estrictamente    
    centralidad_evacuacion = {nodo: [] for nodo in nodos}               
    centralidad_evacuacion_diferentes = {nodo: [] for nodo in nodos}   
    centralidad_evacuacion2 = {nodo: [] for nodo in nodos}
    centralidad_evacuacion2_diferentes = {nodo: [] for nodo in nodos}    
    
    # Almacenar caminos para animación
    caminos_animacion = []

    for exit in destinos: # Para cada uno de los DESTINOS
        
        print(f"\nHACIA EL NODO {exit}:\n\n")
        
        # Calculos el camino minimo de uno a todos, desde el nodoo destino a todos los nodos origen
        coste_principal, lista_camino = nx.multi_source_dijkstra(G,sources={exit})
        
        for k in lista_camino: lista_camino[k] = lista_camino[k][::-1] 
        
        [print(f"DESDE EL NODO {nodo}: Coste: {coste_principal[nodo]} Camino: {lista_camino[nodo]}") for nodo in sorted(lista_camino)]
        print("\n__________________________\n")
        
        for origenes in nodos: # Para cada uno de los nodos origen diferentes al destino
            
            # Para que haya coherencia, si el nodo que se estudia coindice con el destino en ese momento, en esa posicion se pone 0
            if exit == origenes: 
                centralidad_evacuacion[origenes].append(0)
                centralidad_evacuacion_diferentes[origenes].append(0)
                centralidad_evacuacion2[origenes].append(0)
                centralidad_evacuacion2_diferentes[origenes].append(0)
                continue
            
            num_caminos_aceptables = 0
            num_caminos_aceptables_dos = 0
            lista_temporal = set()
            lista_temporal2 = set()
            
            try:
                
                if exit not in coste_principal:
                    raise nx.NetworkXNoPath
                
                print(f"Desde el nodo {origenes} hacia el nodo {exit}\nCamino principal: {coste_principal[origenes]} {lista_camino[origenes]}\n ")
 
                # Para reprensentarlo y quitar lista_aristas una a una
                lista_aristas = Agrupacion(lista_camino[origenes])
                print(lista_aristas)
                # ---- Para visualización Camino principal --- 
                # 
                # ejey = nodos.index(origenes) 
                # Visualizar(G,posiciones,lista_camino,axes=axes1,ejex=0,ejey=ejey) # (en x siempre 0, empieza a la izq)
                # 
                # --------------------------------------------
                
                # ----- FACTOR DE TOLERANCIA ------
                coste_max = coste_principal[origenes]*(1+f_tolerancia) # en tanto por uno (un mismo factor de tolerancia para todos)
                print(f"Coste maximo: {coste_max}")
                # ---------------------------------
                
                # Añadir camino principal a la animación
                caminos_animacion.append((
                    G, 
                    lista_camino[origenes], 
                    set(), 
                    f"Camino: {origenes} a {exit}",
                    coste_principal[origenes],
                    origenes,
                    exit,
                    coste_max
                    ))

                
                for matriz_quitado,arista_quitada in quitar_k_aristas(G_costes, lista_aristas,k=1): # Para cada k aristas en la lista de aristas del camino minimo principal
                    
                    # Nuevo grafo con una arista quitada de lista_aristas porque k=1
                    G_temp = nx.from_numpy_array(matriz_quitado) 
                    
                    try:
                        
                        coste_nuevo, lista_camino_nuevo = nx.multi_source_dijkstra(G_temp,sources={exit})
                        for k in lista_camino_nuevo: lista_camino_nuevo[k] = lista_camino_nuevo[k][::-1] 
                        
                        if exit not in coste_nuevo:
                            raise nx.NetworkXNoPath
                        
                        print(f"|    Camino alternativo nivel 1: {coste_nuevo[origenes]} {lista_camino_nuevo[origenes]} Quitando la arista {arista_quitada}" )
                        
                        # Añadir camino alternativo a la animación
                        caminos_animacion.append((
                            G_temp, 
                            lista_camino_nuevo[origenes],
                            {arista_quitada}, 
                            f"Alternativo Nivel 1: {origenes} a {exit}",
                            coste_nuevo[origenes],
                            origenes,
                            exit,
                            coste_max
                            ))
                                                 
                        
                        if coste_nuevo[origenes]<=coste_max: # si el coste del nuevo camino minimo resultante de quitar una arista esta por debajo del maximo
                            
                            # ----- FACTOR DE TOLERANCIA ------

                            num_caminos_aceptables += 1

                            # --------- Para guardar los estrictamente diferentes -----

                            # guardo el nuevo camino, solo si es estrictamente nuevo, ya que antes hice set()
                            lista_temporal.add(tuple(lista_camino_nuevo[origenes])) 

                            lista_aristas_nuevo = Agrupacion(lista_camino_nuevo[origenes])
                            
                            for matriz_quitado2,arista_quitada2 in quitar_k_aristas(matriz_quitado, lista_aristas_nuevo,k=1):

                                G_temp2 = nx.from_numpy_array(matriz_quitado2)
                                
                                try:
                                    coste_nuevo2, lista_camino_nuevo2 = nx.multi_source_dijkstra(G_temp2,sources={exit})
                                    
                                    for k in lista_camino_nuevo2: lista_camino_nuevo2[k] = lista_camino_nuevo2[k][::-1] 

                                    if exit not in coste_nuevo2:
                                        raise nx.NetworkXNoPath
                                    
                                    print(f"|    |   Camino alternativo nivel 2: {coste_nuevo2[origenes]} {lista_camino_nuevo2[origenes]} Quitando la arista2 {arista_quitada2}" )
                                    
                                    # Añadir camino nivel 2 a la animación
                                    caminos_animacion.append((
                                        G_temp2, 
                                        lista_camino_nuevo2[origenes]
                                        ,{arista_quitada,arista_quitada2}, 
                                        f"Alternativo Nivel 2: {origenes} a {exit}",
                                        coste_nuevo2[origenes],
                                        origenes,
                                        exit,
                                        coste_max
                                        ))
                                    
                                    if coste_nuevo2[origenes]<=coste_max:

                                        num_caminos_aceptables_dos +=1

                                        lista_temporal2.add(tuple(lista_camino_nuevo2[origenes]))

                                except nx.NetworkXNoPath:
                                    continue
                    except nx.NetworkXNoPath:
                        continue
                    
                centralidad_evacuacion[origenes].append(num_caminos_aceptables)
                centralidad_evacuacion2[origenes].append(num_caminos_aceptables_dos)
                centralidad_evacuacion_diferentes[origenes].append(len(lista_temporal))
                centralidad_evacuacion2_diferentes[origenes].append(len(lista_temporal2))    
                print(f"{len(lista_temporal)} lista_temporal: {lista_temporal} ") # son los nuevos caminos estrictamente diferentes
                print(f"{len(lista_temporal2)} lista_temporal2: {lista_temporal2}\n ")
            
            except nx.NetworkXNoPath:
                centralidad_evacuacion[origenes].append(0)
                centralidad_evacuacion_diferentes[origenes].append(0)
                centralidad_evacuacion2[origenes].append(0)
                centralidad_evacuacion2_diferentes[origenes].append(0)
                print(f"No hay camino de {origenes} a {exit}") # Si no hay camino pes 0
            
    # -- Resultados por pantalla --
    
    print(f"\nNodos destino: {destinos}\nFactor de tolerancia: {f_tolerancia}\nNodos origen {nodos}")
    
    print(f"\n\nNumero de caminos minimos por debajo de maximo total \n para cada nodo hacia los nodos destino:\n")
    [print(i) for i in centralidad_evacuacion.items()]
    
    print(f"\n\nNumero de caminos minimos por debajo de maximo total ESTRICTAMENTE DIFERENTES \n para cada nodo hacia los nodos destino:\n")
    [print(i) for i in centralidad_evacuacion_diferentes.items()]
    
    print(f"\n\nNumero de caminos minimos DIFERENTES por debajo de maximo total \npara cada nodo hacia los nodos destino:\n")
    [print(i) for i in centralidad_evacuacion2.items()]

    print(f"\n\nNumero de caminos minimos DIFERENTES por debajo de maximo total ESTRICTAMENTE DIFERENTES \npara cada nodo hacia los nodos destino:\n")
    [print(i) for i in centralidad_evacuacion2_diferentes.items()]
    # ----------------------
    
    # Crear animación
    fig, ax = plt.subplots(figsize=(8, 6))
    
    def update(frame):
        G_frame, camino,aristas_quitadas, title, coste, origen, destino, coste_max = caminos_animacion[frame]
        Visualizar(G_frame, posiciones, camino,aristas_quitadas, ax, title, coste,  origen, destino,coste_max)
    
    ani = FuncAnimation(fig, update, frames=len(caminos_animacion), interval=3000, repeat=True)
    plt.show()
    
    return centralidad_evacuacion_diferentes, centralidad_evacuacion2_diferentes

# ---------------------------- FIN FUNCIONES ---------------------------- #


# ---------------------------- EJEMPLO APLICADO ---------------------------- #

# Matriz de adyacencia de costes de todas las aristas (conexiones)
matriz_costes=np.array([
    [00, 40, 00, 00, 70, 00, 00, 80], 
    [40, 00, 60, 10, 00, 00, 00, 00],
    [00, 60, 00, 10, 00, 20, 00, 00],
    [00, 10, 10, 00, 10, 00, 00, 00],
    [70, 00, 00, 10, 00, 30, 30, 20],
    [00, 00, 20, 00, 30, 00, 30, 00],
    [00, 00, 00, 00, 30, 30, 00, 10],
    [80, 00, 00, 00, 20, 00, 10, 00]])

# Matriz de adayacencia de las seguridades de todas las aristas (conexiones)
matriz_seguridades=np.array([
    [0.0, 0.8, 0.4, 0.4, 0.9, 0.4, 0.4, 1.0], 
    [0.8, 0.0, 1.0, 1.0, 0.4, 0.4, 0.4, 0.4],
    [0.4, 1.0, 0.0, 1.0, 0.4, 0.9, 0.4, 0.4],
    [0.4, 1.0, 1.0, 0.0, 1.0, 0.4, 0.4, 0.4],
    [0.9, 0.2, 0.2, 1.0, 0.0, 0.9, 0.9, 0.2],
    [0.2, 0.6, 0.6, 0.6, 0.9, 0.0, 0.9, 0.6],
    [0.4, 0.4, 0.4, 0.4, 0.9, 0.9, 0.0, 1.0],
    [1.0, 0.1, 0.1, 0.1, 0.9, 0.1, 1.0, 0.0]])

# Posiciones de cada uno de los nodos (coordenadas)
coordenadas = {
    0: (0, 0.25), 
    1: (2, 0.00), 
    2: (4, 0.00), 
    3: (3, 0.15), 
    4: (4, 0.25),
    5: (6, 0.15),
    6: (5, 0.40),
    7: (3, 0.45),}

# Factor de tolerancia respecto al tiempo de evacuación
f_tol = 0.5

# Destinos considerados seguros
destinos_seguros = [6,7]

# Factor de seguridad crítica 
f_sec = 0.7

# Parametros y llamada a la función

centralidades, centralidades2 = Caminos_diferentes(
    G_costes = matriz_costes,
    G_seguridades = matriz_seguridades,
    posiciones = coordenadas,
    destinos = destinos_seguros,
    f_tolerancia = f_tol,
    f_seguridad = f_sec)

# nodos = set(centralidades.keys()) | set(centralidades2.keys())

# resultado = {clave: sum(centralidades.get(clave, [])) + sum(centralidades2.get(clave, [])) for clave in nodos}

# [print(i) for i in resultado.items()]

# Para la visualización
# plt.show()

##################################################################################################################################
# A PARTIR DE AQUI PASO A PENSAR CON ESTOS VALORES DE CENTRALIDAD PASO FINAL, BUSQUEDA DE CAMINO CON MAYOR SUMA DE CENTRALIDADES 1, SI HAY VARIOS DE MAYOR CENTRALIDAD 2

""" G_post = nx.from_numpy_array(matriz_costes)

nx.set_node_attributes(G_post, resultado,name="weight")

nx.draw(
    G=G_post, 
    pos=coordenadas, 
    with_labels=False, 
    node_color='lightblue', 
    edge_color='gray', 
    node_size=2000, 
    font_size=12)

node_labels = {node: f"{node}\n({data['weight']})" for node, data in G_post.nodes(data=True)}
nx.draw_networkx_labels(
    G=G_post, 
    pos=coordenadas, 
    labels=node_labels, 
    font_size=12, 
    font_color='black')

plt.title("Grafo con pesos en los nodos")
plt.show() """