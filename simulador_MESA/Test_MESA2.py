import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

# --- CONFIGURACIÓN DEL LABORATORIO ---
ANCHO = 20  # Más pequeño para que veas bien los nodos individuales
ALTO = 20
PAREDES_CENTRALES = True

class LaboratorioGrafo:
    def __init__(self):
        # 1. Crear el Grafo de Rejilla
        self.G = nx.grid_2d_graph(ANCHO, ALTO)
        
        # 2. Definir Muros
        if PAREDES_CENTRALES:
            nodos_a_borrar = []
            for x in range(8, 12): 
                for y in range(5, 15):
                    nodos_a_borrar.append((x, y))
            self.G.remove_nodes_from(nodos_a_borrar)

        # 3. Configuración de Ruta
        self.origen = (2, 10)
        self.destino = (18, 10)
        self.fuego_pos = None
        self.ruta = []

        # --- CORRECCIÓN AQUÍ ---
        # Inicializamos los pesos a 1 antes de intentar calcular nada
        self.actualizar_pesos() 
        # -----------------------
        
        # Calcular ruta inicial
        self.recalcular_ruta()

    def poner_fuego(self, x, y):
        # Convertir clic float a nodo entero más cercano
        nx_node = (int(round(x)), int(round(y)))
        
        if nx_node in self.G.nodes:
            self.fuego_pos = nx_node
            print(f"Fuego en nodo: {self.fuego_pos}")
            self.actualizar_pesos()
            self.recalcular_ruta()

    def actualizar_pesos(self):
        # Reiniciar pesos a 1
        for u, v in self.G.edges():
            self.G[u][v]['weight'] = 1
            
        if self.fuego_pos:
            # Penalizar nodos cercanos al fuego
            fx, fy = self.fuego_pos
            radio = 3
            
            for nodo in self.G.nodes():
                dist = np.sqrt((nodo[0]-fx)**2 + (nodo[1]-fy)**2)
                
                # Si el nodo está cerca del fuego, penalizamos TODAS sus aristas
                if dist < radio:
                    penalizacion = 1000 if dist < 1.5 else 10
                    # Actualizar aristas conectadas a este nodo
                    for vecino in self.G.neighbors(nodo):
                        self.G[nodo][vecino]['weight'] = penalizacion

    def recalcular_ruta(self):
        try:
            self.ruta = nx.shortest_path(self.G, self.origen, self.destino, weight='weight')
        except nx.NetworkXNoPath:
            self.ruta = []
            print("¡Camino bloqueado!")

# --- VISUALIZACIÓN ---
lab = LaboratorioGrafo()

fig, ax = plt.subplots(figsize=(8, 8))
ax.set_facecolor('#f0f0f0')

def dibujar():
    ax.clear()
    
    # 1. DIBUJAR LAS ARISTAS (Conexiones)
    # NetworkX tiene funciones de dibujo, pero son lentas. Lo hacemos manual para control total.
    for u, v in lab.G.edges():
        x_vals = [u[0], v[0]]
        y_vals = [u[1], v[1]]
        
        # Color de la arista según su peso
        peso = lab.G[u][v]['weight']
        color = 'lightgray'
        grosor = 1
        if peso > 100: 
            color = 'red' # Arista quemada
            grosor = 2
        elif peso > 1:
            color = 'orange' # Arista caliente
        
        ax.plot(x_vals, y_vals, color=color, linewidth=grosor, zorder=1)

    # 2. DIBUJAR LOS NODOS (Puntos)
    nodos_x = [n[0] for n in lab.G.nodes()]
    nodos_y = [n[1] for n in lab.G.nodes()]
    ax.scatter(nodos_x, nodos_y, s=10, c='gray', zorder=2)

    # 3. DIBUJAR LA RUTA (El resultado del algoritmo)
    if lab.ruta:
        ruta_x = [n[0] for n in lab.ruta]
        ruta_y = [n[1] for n in lab.ruta]
        # Dibujamos la ruta encima de todo
        ax.plot(ruta_x, ruta_y, color='blue', linewidth=3, zorder=3, label='Ruta Dijkstra')
        ax.scatter(ruta_x, ruta_y, color='blue', s=30, zorder=3)

    # 4. Origen y Destino
    ax.scatter([lab.origen[0]], [lab.origen[1]], c='green', s=200, label='Origen', zorder=4)
    ax.scatter([lab.destino[0]], [lab.destino[1]], c='purple', s=200, label='Destino', zorder=4)

    # 5. Fuego
    if lab.fuego_pos:
        ax.scatter([lab.fuego_pos[0]], [lab.fuego_pos[1]], c='red', s=500, marker='X', label='Fuego', zorder=5)

    ax.set_title("Visualizador de Grafo NetworkX\nHaz CLIC para poner fuego y cambiar la ruta")
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=4)
    ax.grid(False)
    # Forzar aspecto cuadrado para que no se deforme la rejilla
    ax.set_aspect('equal')
    fig.canvas.draw()

# Evento de clic
def on_click(event):
    if event.xdata is not None and event.ydata is not None:
        lab.poner_fuego(event.xdata, event.ydata)
        dibujar()

cid = fig.canvas.mpl_connect('button_press_event', on_click)

# Dibujo inicial
dibujar()
plt.show()