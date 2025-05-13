import numpy as np
from itertools import combinations as combs

# AQUI ESTABA PROBANDO UNA MANERA MAS FLEXIBLE DE ITERAR ARISTAS EN UN CONJUNTO DE ARISTAS, LO NECESITABA PARA LA RECOMENDACIONN DE RUTAS.
# BASICAMENTE COGE UNA LISTA DE 8 ARISTAS Y ME DA TODOS GRUPOS DE 1, 2 o 3 ARISTAS POSIBLES QUE HAY, DEPENDE DE LO QUE LE PONGA EN K.

# Matriz original
matriz = np.array([
    [0, 4, 0, 0, 7, 0, 0, 8], 
    [4, 0, 6, 1, 0, 0, 0, 0],
    [0, 6, 0, 1, 0, 2, 0, 0],
    [0, 1, 1, 0, 1, 0, 0, 0],
    [7, 0, 0, 1, 0, 3, 3, 2],
    [0, 0, 2, 0, 3, 0, 3, 0],
    [0, 0, 0, 0, 3, 3, 0, 1],
    [8, 0, 0, 0, 2, 0, 1, 0]])

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
for variante, aristas_quitadas in quitar_k_aristas(matriz, indices, k):
    print(f"\nSe han quitado las istas: {aristas_quitadas}")
    print(type(aristas_quitadas[0]))
    print("Matriz modificada:")
    print(variante)
    print("-----")
