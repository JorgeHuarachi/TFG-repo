import networkx as nx
import numpy as np
from itertools import combinations as combs
from pyvis.network import Network
import matplotlib.pyplot as plt

# ############################### FUNCIONES ###############################

def Agrupacion(camino):
    """Agrupa en conjuntos de tamaño 2 una lista de tamaño mayor a 2.
    
    Parameters
    ----------
    camino : list
        Lista de nodos que forman un camino (longitud >= 2).
    
    Returns
    -------
    list
        Lista de tuplas (i, j) representando aristas consecutivas.
    """
    if len(camino) < 2:
        return [] # Return empty list for consistency, not set
    lista = sorted([(camino[i], camino[i+1]) for i in range(len(camino)-1)])
    return lista

def Add_Path_To_Pyvis_Network(net, pos, camino, path_color, path_width, node_color_in_path, path_label_prefix, G_of_path_for_weights):
    """
    Highlights a specific path on an existing Pyvis Network object.
    Nodes in the path are re-colored. Edges in the path are re-colored and thickened.
    Assumes base nodes and edges are already on 'net' with default styling.

    Parameters
    ----------
    net : pyvis.network.Network
        The Pyvis Network object to modify.
    pos : dict
        Dictionary with the positions of the nodos (coordenadas x, y).
    camino : list
        Lista de nodos que forman un camino a resaltar.
    path_color : str
        Color for the path's edges.
    path_width : float
        Width for the path's edges.
    node_color_in_path : str
        Color for the nodes in the path.
    path_label_prefix : str
        Prefix for the edge tooltip (e.g., "Principal:", "Alt:").
    G_of_path_for_weights : nx.Graph
        The NetworkX graph from which to get edge weights for the tooltip.
    """
    aristas_camino = Agrupacion(camino)

    # Recolor nodes in the current path
    for node_id in camino:
        node_x = pos[node_id][0] * 100
        node_y = pos[node_id][1] * 100
        # Update node properties. add_node will update if node_id already exists.
        net.add_node(node_id, label=str(node_id), x=node_x, y=node_y,
                     color=node_color_in_path, size=17, borderWidth=2, font={'size': 14, 'color': 'black'})

    # Recolor/thicken edges in the current path
    for u, v in aristas_camino:
        cost = 'N/A'
        if G_of_path_for_weights.has_edge(u,v) and 'weight' in G_of_path_for_weights[u][v]:
            cost = G_of_path_for_weights[u][v]['weight']
        # Update edge properties. add_edge will update if edge (u,v) already exists.
        net.add_edge(u, v, color=path_color, width=path_width, title=f"{path_label_prefix} Cost: {cost:.2f}")


def quitar_k_aristas(matriz, indices, k):
    """Genera matrices resultado de quitar k aristas de una lista de aristas.
    
    Parameters
    ----------
    matriz : np.ndarray
        Matriz de adyacencia.
    indices : list 
        Lista de aristas (tuples) para quitar en combinaciones de k aristas.
    k : int
        Número de aristas a eliminar.
    
    Yields
    ------
    tuple
        (Matriz modificada, tupla de aristas eliminadas).
    """
    if k > len(indices):
        # No longer raising an error, just yield nothing if k is too large
        # This can happen if a path is shorter than k.
        return
        # raise ValueError("k no puede ser mayor que la cantidad de aristas disponibles.")
    for combinacion_k_aristas in combs(indices, k): # combinacion is a tuple of k edges
        temp = matriz.copy()
        for i, j in combinacion_k_aristas: # iterate through edges in the current combination
            temp[i, j] = 0
            temp[j, i] = 0 # Assuming undirected for removal, adjust if graph is directed
        yield temp, combinacion_k_aristas # Yield the combination of edges removed

def Caminos_diferentes(G_costes, G_seguridades, posiciones, destinos, f_tolerancia, f_seguridad):
    """Calcula caminos mínimos alternativos considerando eliminación de aristas y restricciones de costo y seguridad.
    Genera un archivo HTML por cada par origen-destino con todos los caminos relevantes visualizados.
    """
    # Filtrar aristas por seguridad
    i_list, j_list = np.where(G_seguridades < f_seguridad)
    G_costes_filtrado = G_costes.copy()
    for iter_idx in range(len(i_list)): # Renamed iter to iter_idx
        G_costes_filtrado[i_list[iter_idx], j_list[iter_idx]] = 0
        G_costes_filtrado[j_list[iter_idx], i_list[iter_idx]] = 0 # Ensure symmetry if costs imply undirected edges
    
    G_base = nx.from_numpy_array(G_costes_filtrado) # Base graph for pathfinding and visualization
    nodos = list(G_base.nodes)
    
    centralidad_evacuacion = {nodo: [] for nodo in nodos}
    centralidad_evacuacion_diferentes = {nodo: [] for nodo in nodos}
    centralidad_evacuacion2 = {nodo: [] for nodo in nodos}
    centralidad_evacuacion2_diferentes = {nodo: [] for nodo in nodos}
    
    for exit_node in destinos: # Renamed exit to exit_node
        print(f"\nPROCESANDO DESTINO: NODO {exit_node}")
        for origen_node in nodos: # Renamed origenes to origen_node
            if exit_node == origen_node:
                centralidad_evacuacion[origen_node].append(0)
                centralidad_evacuacion_diferentes[origen_node].append(0)
                centralidad_evacuacion2[origen_node].append(0)
                centralidad_evacuacion2_diferentes[origen_node].append(0)
                continue
            
            print(f"  Calculando caminos de {origen_node} a {exit_node}...")
            num_caminos_aceptables_lvl1 = 0
            num_caminos_aceptables_lvl2 = 0
            
            # Stores unique paths (as tuples of nodes) for level 1 alternatives
            unique_alternative_paths_lvl1 = set()
            # Stores unique paths (as tuples of nodes) for level 2 alternatives, keyed by the first removed edge
            # lista_temporal2 maps first_removed_edge -> set(path_tuples_lvl2)
            # For visualization, we'll collect all unique level 2 paths globally for this O-D pair
            unique_alternative_paths_lvl2_global = set()
            
            # Initialize ONE Pyvis network for this (origen_node, exit_node) pair
            net_combined = Network(height="750px", width="100%", directed=True, notebook=False,
                                   heading=f"Caminos de {origen_node} a {exit_node} (Tol: {f_tolerancia*100}%, Seg: {f_seguridad})")

            # Add all nodes from G_base with default styling
            for node_id in G_base.nodes():
                net_combined.add_node(node_id, label=str(node_id), 
                                      x=posiciones[node_id][0]*100, y=posiciones[node_id][1]*100,
                                      color="lightgrey", size=12, font={'size': 10})
            # Add all edges from G_base with default styling
            for u, v in G_base.edges():
                weight = G_base[u][v].get('weight', 0)
                net_combined.add_edge(u, v, color="lightgrey", width=1, title=f"Base Cost: {weight:.2f}")

            net_combined.options = {
                "nodes": {"font": {"strokeWidth": 0, "strokeColor": 'white'}}, # Default font settings
                "edges": {"smooth": False, "arrows": "to"},
                "physics": {"enabled": False}, # Crucial for fixed positions
                "interaction": {"hover": True, "tooltipDelay": 200},
                "manipulation": {"enabled": False} # Disable editing graph in browser
            }

            coste_principal = float('inf')
            
            try:
                # Calculate principal path on G_base
                distancias, caminos = nx.multi_source_dijkstra(G_base, sources={origen_node})
                if exit_node not in distancias or not caminos[exit_node]: # Check if path is empty
                    raise nx.NetworkXNoPath(f"No path found from {origen_node} to {exit_node} in G_base.")
                
                coste_principal = distancias[exit_node]
                lista_camino_principal = caminos[exit_node]
                print(f"    Principal: Coste={coste_principal:.2f}, Camino={lista_camino_principal}")
                
                coste_max = coste_principal * (1 + f_tolerancia)
                
                # Add principal path to combined_net
                Add_Path_To_Pyvis_Network(net_combined, posiciones, lista_camino_principal,
                                          path_color="red", path_width=3.5, node_color_in_path="#e60000", # Darker red for nodes
                                          path_label_prefix="Principal:", G_of_path_for_weights=G_base)
                
                aristas_del_camino_principal = Agrupacion(lista_camino_principal)
                
                # First level alternatives (removing 1 edge from principal path)
                for G_temp_matrix, arista_quitada_tuple in quitar_k_aristas(G_costes_filtrado, aristas_del_camino_principal, 1):
                    if not arista_quitada_tuple: continue # Should not happen if k=1 and aristas_del_camino_principal not empty
                    arista_quitada_lvl1 = arista_quitada_tuple[0] # quitar_k_aristas yields tuple of removed edges

                    G_temp_lvl1 = nx.from_numpy_array(G_temp_matrix)
                    try:
                        dist_lvl1, caminos_lvl1 = nx.multi_source_dijkstra(G_temp_lvl1, sources={origen_node})
                        if exit_node not in dist_lvl1 or not caminos_lvl1[exit_node]:
                            raise nx.NetworkXNoPath
                        
                        coste_alt_lvl1 = dist_lvl1[exit_node]
                        path_alt_lvl1 = caminos_lvl1[exit_node]
                        
                        if coste_alt_lvl1 <= coste_max:
                            num_caminos_aceptables_lvl1 += 1
                            path_alt_lvl1_tuple = tuple(path_alt_lvl1)
                            if path_alt_lvl1_tuple != tuple(lista_camino_principal) and path_alt_lvl1_tuple not in unique_alternative_paths_lvl1:
                                unique_alternative_paths_lvl1.add(path_alt_lvl1_tuple)
                                print(f"      Alt Lvl1 (sin {arista_quitada_lvl1}): Coste={coste_alt_lvl1:.2f}, Camino={path_alt_lvl1}")
                                Add_Path_To_Pyvis_Network(net_combined, posiciones, path_alt_lvl1,
                                                          path_color="blue", path_width=2.5, node_color_in_path="#0000e6", # Darker blue
                                                          path_label_prefix=f"Alt_L1 (no {arista_quitada_lvl1}):", G_of_path_for_weights=G_temp_lvl1)

                                # Second level alternatives (removing 1 edge from this path_alt_lvl1)
                                aristas_del_camino_alt_lvl1 = Agrupacion(path_alt_lvl1)
                                for G_temp_matrix_lvl2, arista_quitada_tuple_lvl2 in quitar_k_aristas(G_temp_matrix, aristas_del_camino_alt_lvl1, 1):
                                    if not arista_quitada_tuple_lvl2: continue
                                    arista_quitada_lvl2 = arista_quitada_tuple_lvl2[0]

                                    G_temp_lvl2 = nx.from_numpy_array(G_temp_matrix_lvl2)
                                    try:
                                        dist_lvl2, caminos_lvl2 = nx.multi_source_dijkstra(G_temp_lvl2, sources={origen_node})
                                        if exit_node not in dist_lvl2 or not caminos_lvl2[exit_node]:
                                            raise nx.NetworkXNoPath
                                        
                                        coste_alt_lvl2 = dist_lvl2[exit_node]
                                        path_alt_lvl2 = caminos_lvl2[exit_node]

                                        if coste_alt_lvl2 <= coste_max:
                                            num_caminos_aceptables_lvl2 +=1 # This counts all valid L2 paths found
                                            path_alt_lvl2_tuple = tuple(path_alt_lvl2)
                                            # Ensure it's different from principal and L1 alternatives already drawn, and other L2s
                                            if (path_alt_lvl2_tuple != tuple(lista_camino_principal) and
                                                path_alt_lvl2_tuple not in unique_alternative_paths_lvl1 and
                                                path_alt_lvl2_tuple not in unique_alternative_paths_lvl2_global):
                                                unique_alternative_paths_lvl2_global.add(path_alt_lvl2_tuple)
                                                print(f"        Alt Lvl2 (sin {arista_quitada_lvl1} -> {arista_quitada_lvl2}): Coste={coste_alt_lvl2:.2f}, Camino={path_alt_lvl2}")
                                                Add_Path_To_Pyvis_Network(net_combined, posiciones, path_alt_lvl2,
                                                                          path_color="green", path_width=2, node_color_in_path="#009900", # Darker green
                                                                          path_label_prefix=f"Alt_L2 (no {arista_quitada_lvl1} then {arista_quitada_lvl2}):", G_of_path_for_weights=G_temp_lvl2)
                                    except nx.NetworkXNoPath:
                                        continue # No L2 path after removing second edge
                    except nx.NetworkXNoPath:
                        continue # No L1 path after removing first edge
            
            except nx.NetworkXNoPath:
                print(f"    No hay camino principal de {origen_node} a {exit_node} con los filtros aplicados.")
                # Still save the base graph for this O-D pair
                net_combined.save_graph(f"caminos_combinados_{origen_node}_a_{exit_node}.html")
                centralidad_evacuacion[origen_node].append(0)
                centralidad_evacuacion_diferentes[origen_node].append(0)
                centralidad_evacuacion2[origen_node].append(0)
                centralidad_evacuacion2_diferentes[origen_node].append(0)
                continue # Skip to next origen_node

            # Save the combined network for this (origen_node, exit_node) pair
            if coste_principal != float('inf'): # Only save if a principal path was found
                net_combined.save_graph(f"caminos_combinados_{origen_node}_a_{exit_node}.html")

            centralidad_evacuacion[origen_node].append(num_caminos_aceptables_lvl1) # Total L1 paths found (could be non-unique paths)
            centralidad_evacuacion_diferentes[origen_node].append(len(unique_alternative_paths_lvl1)) # Strictly unique L1 paths
            centralidad_evacuacion2[origen_node].append(num_caminos_aceptables_lvl2) # Total L2 paths found
            centralidad_evacuacion2_diferentes[origen_node].append(len(unique_alternative_paths_lvl2_global)) # Strictly unique L2 paths
            
            print(f"    Resumen para {origen_node}->{exit_node}: {len(unique_alternative_paths_lvl1)} caminos L1 únicos, {len(unique_alternative_paths_lvl2_global)} caminos L2 únicos.")

    # Imprimir resultados (same as before)
    print(f"\nNodos destino: {destinos}\nFactor de tolerancia: {f_tolerancia}\nNodos origen: {nodos}")
    print("\nNumero de caminos (Lvl1) aceptables (pueden repetirse si distintas aristas eliminadas llevan al mismo camino):")
    [print(i) for i in centralidad_evacuacion.items()]
    print("\nNumero de caminos (Lvl1) aceptables ESTRICTAMENTE DIFERENTES:")
    [print(i) for i in centralidad_evacuacion_diferentes.items()]
    print("\nNumero de caminos (Lvl2) aceptables (pueden repetirse):")
    [print(i) for i in centralidad_evacuacion2.items()]
    print("\nNumero de caminos (Lvl2) aceptables ESTRICTAMENTE DIFERENTES (globalmente):")
    [print(i) for i in centralidad_evacuacion2_diferentes.items()]
    
    return centralidad_evacuacion_diferentes, centralidad_evacuacion2_diferentes


# ############################### EJEMPLO APLICADO ###############################

# Matriz de adyacencia de costos
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

# Matriz de adyacencia de seguridades
matriz_seguridades = np.array([
    [0.0, 0.8, 0.4, 0.4, 0.9, 0.4, 0.4, 1.0],
    [0.8, 0.0, 1.0, 1.0, 0.4, 0.4, 0.4, 0.4],
    [0.4, 1.0, 0.0, 1.0, 0.4, 0.9, 0.4, 0.4],
    [0.4, 1.0, 1.0, 0.0, 1.0, 0.4, 0.4, 0.4],
    [0.9, 0.2, 0.2, 1.0, 0.0, 0.9, 0.9, 0.2], # Adjusted some 0.0 to 0.2 for safety example
    [0.2, 0.6, 0.6, 0.6, 0.9, 0.0, 0.9, 0.6], # Adjusted some 0.0 to 0.6
    [0.4, 0.4, 0.4, 0.4, 0.9, 0.9, 0.0, 1.0],
    [1.0, 0.1, 0.1, 0.1, 0.9, 0.1, 1.0, 0.0]  # Adjusted some 0.0 to 0.1
])

# Posiciones de los nodos
coordenadas = {
    0: (0, 0.25), 1: (2, 0.00), 2: (4, 0.00), 3: (3, 0.15),
    4: (4, 0.25), 5: (6, 0.15), 6: (5, 0.40), 7: (3, 0.45),
}

# Parámetros
f_tol = 0.5
destinos_seguros = [7, 6, 5] # Example, can be a subset
f_sec = 0.7 # Security threshold

# Llamada a la función
centralidades, centralidades2 = Caminos_diferentes(
    G_costes=matriz_costes,
    G_seguridades=matriz_seguridades,
    posiciones=coordenadas,
    destinos=destinos_seguros,
    f_tolerancia=f_tol,
    f_seguridad=f_sec
)

# Calcular centralidad total (based on your original logic for strictly different paths)
nodos_set = set(centralidades.keys()) | set(centralidades2.keys()) # Renamed nodos to nodos_set
resultado = {clave: sum(val for val_list in centralidades.get(clave, []) for val in ([val_list] if isinstance(val_list, int) else val_list) ) + \
                    sum(val for val_list in centralidades2.get(clave, []) for val in ([val_list] if isinstance(val_list, int) else val_list) )
             for clave in nodos_set}

print("\nCentralidad total combinada (suma de caminos únicos L1 y L2 por cada destino):")
[print(i) for i in resultado.items()]


# Visualización del grafo final con pesos (Matplotlib part remains)
G_post = nx.from_numpy_array(matriz_costes) 
# Ensure all nodes are in G_post if 'resultado' includes nodes not in matriz_costes (e.g., isolated nodes if any)
all_nodes_for_plotting = list(range(matriz_costes.shape[0]))
for node_p in all_nodes_for_plotting:
    if node_p not in G_post:
        G_post.add_node(node_p)


# Update node weights, ensure all nodes from 'resultado' have a weight, default to 0 if not present.
node_weights_for_plot = {node: resultado.get(node, 0) for node in G_post.nodes()}
nx.set_node_attributes(G_post, node_weights_for_plot, name="weight")


plt.figure(figsize=(10, 8))
nx.draw(
    G=G_post,
    pos=coordenadas,
    with_labels=False, # Labels will be drawn by draw_networkx_labels
    node_color='lightblue',
    edge_color='gray',
    node_size=[ (v*200 + 500) for v in node_weights_for_plot.values()], # Vary size by weight
    font_size=10 # Base font size
)
node_labels = {node: f"{node}\n({data.get('weight',0)})" for node, data in G_post.nodes(data=True)}
nx.draw_networkx_labels(
    G=G_post,
    pos=coordenadas,
    labels=node_labels,
    font_size=9,
    font_color='black'
)
edge_labels = nx.get_edge_attributes(G_post,'weight')
nx.draw_networkx_edge_labels(G_post, coordenadas, edge_labels=edge_labels, font_size=7)

plt.title("Grafo con pesos en los nodos (Centralidad Total de Caminos Únicos)")
plt.show()