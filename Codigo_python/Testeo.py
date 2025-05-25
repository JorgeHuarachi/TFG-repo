import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from itertools import combinations as combs
from matplotlib.animation import FuncAnimation # GRACIAS A ESTO PUEDO ANIMAR LOS GRAFOS QUE OBTENGO

# ############################### FUNCIONES ###############################

def Agrupacion(camino):
    """Agrupa en conjuntos de tamaño 2 una lista de tamaño mayor a 2.
    
    Parameters
    ----------
    camino : list
        Lista de nodos que forman un camino (longitud >= 2).
    
    Returns
    -------
    set
        Conjunto de tuplas (i, j) representando aristas consecutivas.
    """
    if len(camino) < 2:
        return set()
    lista = {(camino[i], camino[i+1]) for i in range(len(camino)-1)}
    pares = sorted(lista)
    return pares

def Visualizar(G, pos, camino, ax, title="Gráfico"):
    """Dibuja un camino en el grafo con nodos y aristas resaltados.
    
    Parameters
    ----------
    G : nx.Graph
        Grafo completo.
    pos : dict
        Diccionario con las posiciones de los nodos (coordenadas x, y).
    camino : list
        Lista de nodos que forman un camino a resaltar.
    ax : matplotlib.axes.Axes
        Eje de Matplotlib para dibujar.
    title : str
        Título del gráfico.
    """
    ax.clear()
    aristas = Agrupacion(camino)
    
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=150, node_color="lightblue")
    nx.draw_networkx_edges(G, pos, ax=ax, width=1, edge_color="gray")
    nx.draw_networkx_edges(G, pos, aristas, ax=ax, width=2, edge_color="red")
    nx.draw_networkx_nodes(G, pos, camino, ax=ax, node_size=150, node_color="red")
    nx.draw_networkx_labels(G, pos, ax=ax)
    ax.set_title(title)

def quitar_k_aristas(matriz, indices, k):
    """Genera matrices resultado de quitar k aristas de una lista de aristas.
    
    Parameters
    ----------
    matriz : np.ndarray
        Matriz de adyacencia.
    indices : set
        Lista de aristas para quitar en combinaciones de k aristas.
    k : int
        Número de aristas a eliminar.
    
    Yields
    ------
    tuple
        (Matriz modificada, tupla de aristas eliminadas).
    """
    if k > len(indices):
        raise ValueError("k no puede ser mayor que la cantidad de aristas disponibles.")
    for combinacion in combs(indices, k):
        temp = matriz.copy()
        for i, j in combinacion:
            temp[i, j] = 0
            temp[j, i] = 0
        yield temp, combinacion

def Caminos_diferentes(G_costes, G_seguridades, posiciones, destinos, f_tolerancia, f_seguridad):
    """Calcula caminos mínimos alternativos considerando eliminación de aristas y restricciones de costo y seguridad.
    
    Parameters
    ----------
    G_costes : np.ndarray
        Matriz de adyacencia con costos de las aristas.
    G_seguridades : np.ndarray
        Matriz de adyacencia con valores de seguridad de las aristas.
    posiciones : dict
        Diccionario con posiciones de los nodos para visualización.
    destinos : list
        Lista de nodos destino considerados seguros.
    f_tolerancia : float
        Factor de tolerancia para el costo máximo permitido.
    f_seguridad : float
        Umbral mínimo de seguridad para considerar una arista.
    
    Returns
    -------
    tuple
        (centralidad_evacuacion_diferentes, centralidad_evacuacion2_diferentes)
        Diccionarios con nodos como claves y listas de caminos estrictamente diferentes por destino.
    """
    i_list, j_list = np.where(G_seguridades < f_seguridad)
    G_costes_filtrado = G_costes.copy()
    for iter in range(len(i_list)):
        G_costes_filtrado[i_list[iter], j_list[iter]] = 0
    
    G = nx.from_numpy_array(G_costes_filtrado)
    nodos = list(G.nodes)
    
    centralidad_evacuacion = {nodo: [] for nodo in nodos}
    centralidad_evacuacion_diferentes = {nodo: [] for nodo in nodos}
    centralidad_evacuacion2 = {nodo: [] for nodo in nodos}
    centralidad_evacuacion2_diferentes = {nodo: [] for nodo in nodos}
    
    # Almacenar caminos para animación
    caminos_animacion = []
    
    for exit in destinos:
        print(f"\nHACIA EL NODO {exit}:")
        for origenes in nodos:
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
                distancias, caminos = nx.multi_source_dijkstra(G, sources={origenes})
                if exit not in distancias:
                    raise nx.NetworkXNoPath
                coste_principal = distancias[exit]
                lista_camino = caminos[exit]
                print(f"\nprincipal: {coste_principal} {lista_camino}")
                coste_max = coste_principal * (1 + f_tolerancia)
                lista_aristas = Agrupacion(lista_camino)
                
                # Añadir camino principal a la animación
                caminos_animacion.append((G, lista_camino, f"Principal: {origenes} a {exit}"))
                
                for matriz_quitado, arista_quitada in quitar_k_aristas(G_costes, lista_aristas, k=1):
                    G_temp = nx.from_numpy_array(matriz_quitado)
                    try:
                        distancias_nuevo, caminos_nuevo = nx.multi_source_dijkstra(G_temp, sources={origenes})
                        if exit not in distancias_nuevo:
                            raise nx.NetworkXNoPath
                        coste_nuevo = distancias_nuevo[exit]
                        lista_camino_nuevo = caminos_nuevo[exit]
                        print(f"    nuevo camino: {coste_nuevo} {lista_camino_nuevo} quitando la arista {arista_quitada}")
                        
                        # Añadir camino alternativo a la animación
                        caminos_animacion.append((G_temp, lista_camino_nuevo, f"Alternativo: {origenes} a {exit} sin {arista_quitada}"))        
                        
                        if coste_nuevo <= coste_max:
                            num_caminos_aceptables += 1
                            
                            lista_temporal.add(tuple(lista_camino_nuevo))
                            
                            lista_camino_nuevo_aristas = Agrupacion(lista_camino_nuevo)
                            for matriz_quitado2, arista_quitada2 in quitar_k_aristas(matriz_quitado, lista_camino_nuevo_aristas, k=1):
                                G_temp2 = nx.from_numpy_array(matriz_quitado2)
                                try:
                                    distancias_nuevo2, caminos_nuevo2 = nx.multi_source_dijkstra(G_temp2, sources={origenes})
                                    if exit not in distancias_nuevo2:
                                        raise nx.NetworkXNoPath
                                    coste_nuevo2 = distancias_nuevo2[exit]
                                    lista_camino_nuevo2 = caminos_nuevo2[exit]
                                    print(f"        nuevo camino2: {coste_nuevo2} {lista_camino_nuevo2} quitando la arista2 {arista_quitada2}")
                                    
                                    # Añadir camino nivel 2 a la animación
                                    caminos_animacion.append((G_temp2, lista_camino_nuevo2, f"Nivel 2: {origenes} a {exit} sin {arista_quitada,arista_quitada2}"))
                                    
                                    if coste_nuevo2 <= coste_max:
                                        num_caminos_aceptables_dos += 1
                                        
                                        lista_temporal2.add(tuple(lista_camino_nuevo2))
                                            
                                            
                                except nx.NetworkXNoPath:
                                    continue
                    except nx.NetworkXNoPath:
                        continue
                
                centralidad_evacuacion[origenes].append(num_caminos_aceptables)
                centralidad_evacuacion_diferentes[origenes].append(len(lista_temporal))
                centralidad_evacuacion2[origenes].append(num_caminos_aceptables_dos)
                centralidad_evacuacion2_diferentes[origenes].append(len(lista_temporal2))
                print(f"{len(lista_temporal)} lista_temporal: {lista_temporal}")
                print(f"{len(lista_temporal2)} lista_temporal2: {lista_temporal2}")
            
            except nx.NetworkXNoPath:
                centralidad_evacuacion[origenes].append(0)
                centralidad_evacuacion_diferentes[origenes].append(0)
                centralidad_evacuacion2[origenes].append(0)
                centralidad_evacuacion2_diferentes[origenes].append(0)
                print(f"No hay camino de {origenes} a {exit}")
    
    # Imprimir resultados
    print(f"\nNodos destino: {destinos}\nFactor de tolerancia: {f_tolerancia}\nNodos origen: {nodos}")
    print("\nNumero de caminos minimos por debajo de maximo total:")
    [print(i) for i in centralidad_evacuacion.items()]
    print("\nNumero de caminos minimos por debajo de maximo total ESTRICTAMENTE DIFERENTES:")
    [print(i) for i in centralidad_evacuacion_diferentes.items()]
    print("\nNumero de caminos minimos DIFERENTES por debajo de maximo total:")
    [print(i) for i in centralidad_evacuacion2.items()]
    print("\nNumero de caminos minimos DIFERENTES por debajo de maximo total ESTRICTAMENTE DIFERENTES:")
    [print(i) for i in centralidad_evacuacion2_diferentes.items()]
    
    # Crear animación
    fig, ax = plt.subplots(figsize=(8, 6))
    
    def update(frame):
        G_frame, camino, title = caminos_animacion[frame]
        Visualizar(G_frame, posiciones, camino, ax, title)
    
    ani = FuncAnimation(fig, update, frames=len(caminos_animacion), interval=3000, repeat=True)
    plt.show()
    
    return centralidad_evacuacion_diferentes, centralidad_evacuacion2_diferentes

# ############################### EJEMPLO APLICADO ###############################

matriz_costes = np.array([
    [0, 40, 0, 0, 70, 0, 0, 80],
    [40, 0, 60, 10, 0, 0, 0, 0],
    [0, 60, 0, 10, 0, 20, 0, 0],
    [0, 10, 10, 0, 10, 0, 0, 0],
    [70, 0, 0, 10, 0, 30, 30, 20],
    [0, 0, 20, 0, 30, 0, 30, 0],
    [0, 0, 0, 0, 30, 30, 0, 10],
    [80, 0, 0, 0, 20, 0, 10, 0]
])

matriz_seguridades = np.array([
    [0.0, 0.8, 0.4, 0.4, 0.9, 0.4, 0.4, 1.0],
    [0.8, 0.0, 1.0, 1.0, 0.4, 0.4, 0.4, 0.4],
    [0.4, 1.0, 0.0, 1.0, 0.4, 0.9, 0.4, 0.4],
    [0.4, 1.0, 1.0, 0.0, 1.0, 0.4, 0.4, 0.4],
    [0.9, 0.2, 0.2, 1.0, 0.0, 0.9, 0.9, 0.2],
    [0.2, 0.6, 0.6, 0.6, 0.9, 0.0, 0.9, 0.6],
    [0.4, 0.4, 0.4, 0.4, 0.9, 0.9, 0.0, 1.0],
    [1.0, 0.1, 0.1, 0.1, 0.9, 0.1, 1.0, 0.0]
])

coordenadas = {
    0: (0, 0.25),
    1: (2, 0.00),
    2: (4, 0.00),
    3: (3, 0.15),
    4: (4, 0.25),
    5: (6, 0.15),
    6: (5, 0.40),
    7: (3, 0.45),
}

f_tol = 0.5
destinos_seguros = [5]
f_sec = 0.7

centralidades, centralidades2 = Caminos_diferentes(
    G_costes=matriz_costes,
    G_seguridades=matriz_seguridades,
    posiciones=coordenadas,
    destinos=destinos_seguros,
    f_tolerancia=f_tol,
    f_seguridad=f_sec
)

nodos = set(centralidades.keys()) | set(centralidades2.keys())
resultado = {clave: sum(centralidades.get(clave, [])) + sum(centralidades2.get(clave, [])) for clave in nodos}
[print(i) for i in resultado.items()]

# Visualización del grafo final con pesos
G_post = nx.from_numpy_array(matriz_costes)
nx.set_node_attributes(G_post, resultado, name="weight")
nx.draw(
    G=G_post,
    pos=coordenadas,
    with_labels=False,
    node_color='lightblue',
    edge_color='gray',
    node_size=2000,
    font_size=12
)
node_labels = {node: f"{node}\n({data['weight']})" for node, data in G_post.nodes(data=True)}
nx.draw_networkx_labels(
    G=G_post,
    pos=coordenadas,
    labels=node_labels,
    font_size=12,
    font_color='black'
)
plt.title("Grafo con pesos en los nodos")
plt.show()