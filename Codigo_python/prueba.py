import numpy as np
from itertools import combinations as combs
import networkx as nx 
import matplotlib.pyplot as plt

# AQUI ESTABA PROBANDO UNA MANERA MAS FLEXIBLE DE ITERAR ARISTAS EN UN CONJUNTO DE ARISTAS, LO NECESITABA PARA LA RECOMENDACIONN DE RUTAS.
# BASICAMENTE COGE UNA LISTA DE 8 ARISTAS Y ME DA TODOS GRUPOS DE 1, 2 o 3 ARISTAS POSIBLES QUE HAY, DEPENDE DE LO QUE LE PONGA EN K.

# Matriz original
matriz = np.array([
    [0, 40, 0, 0, 70, 0, 0, 80],
    [40, 0, 60, 10, 0, 0, 0, 0],
    [0, 60, 0, 10, 0, 20, 0, 0],
    [0, 10, 10, 0, 10, 0, 0, 0],
    [70, 0, 0, 10, 0, 30, 30, 20],
    [0, 0, 20, 0, 30, 0, 30, 0],
    [0, 0, 0, 0, 30, 30, 0, 10],
    [80, 0, 0, 0, 20, 0, 10, 0]
])

# Índices de aristas
indices = [[0,1], [1,2], [2,3], [3,4], [4,6]]

k = 1

def quitar_k_aristas(matriz, indices, k):
    if k > len(indices):
        raise ValueError("k no puede ser mayor que la cantidad de aristas disponibles.")
    for combinacion in combs(indices, k):
        temp = matriz.copy()
        # Desempaquetamos cada combinación (esto elimina la coma extra)
        for i, j in combinacion:
            temp[i, j] = 0
            temp[j, i] = 0
        yield temp, combinacion  #  devuelve la matriz Y las aristas quitadas

# Ejemplo de uso para k=1
#for variante, aristas_quitadas in quitar_k_aristas(matriz, indices, k):
#    print(f"\nSe han quitado las istas: {aristas_quitadas}")
#    print(type(aristas_quitadas[0]))
#    print("Matriz modificada:")
#    print(variante)
#    print("-----")

# # Combinar claves y sumar valores (si prefieres este enfoque)
# dict1 = {'a': 10, 'b': 20, 'c': 30}
# dict2 = {'a': 5, 'b': 15, 'd': 25}

# # Obtener todas las claves
# claves = set(dict1.keys()) | set(dict2.keys())

# # Crear diccionario con valores sumados
# resultado = {clave: dict1.get(clave, 0) + dict2.get(clave, 0) for clave in claves}

# print("Diccionario combinado:", resultado)
G = nx.from_numpy_array(matriz)
# distancias= nx.all_shortest_paths(G,source=6,target=0)
print([p for p in nx.all_shortest_paths(G, source=6, target=0,weight=any)])
# print(f"distancias: {distancias}")

nx.draw(G,with_labels=True)
plt.show()