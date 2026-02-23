import mesa
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# --- CONFIGURACIÓN ---
ANCHO, ALTO = 40, 20

# --- 1. DEFINICIÓN DEL GRAFO LÓGICO (MACRO) ---
# Aquí definimos el "Mapa Mental" del edificio
grafo_edificio = nx.Graph()

# Coordenadas de los hitos importantes (Puertas y zonas clave)
nodos_clave = {
    'H1_Centro': (8, 10),   # Referencia Habitación 1
    'Puerta_A': (15, 10),   # Puerta que une H1 con Pasillo
    'Pasillo_C': (20, 10),  # Centro del pasillo
    'Puerta_B': (25, 10),   # Puerta que une Pasillo con H2
    'H2_Centro': (32, 10),  # Referencia Habitación 2
    'SALIDA': (38, 10)      # La meta
}

# Conectamos los nodos (Esto define por dónde se puede pasar)
# Arista = (Nodo1, Nodo2, Distancia)
conexiones = [
    ('H1_Centro', 'Puerta_A'),
    ('Puerta_A', 'Pasillo_C'),
    ('Pasillo_C', 'Puerta_B'),
    ('Puerta_B', 'H2_Centro'),
    ('H2_Centro', 'SALIDA'),
    # Conexión directa extra por si acaso (Pasillo largo)
    ('Puerta_A', 'Puerta_B') 
]

for u, v in conexiones:
    p1 = np.array(nodos_clave[u])
    p2 = np.array(nodos_clave[v])
    dist = np.linalg.norm(p1 - p2)
    grafo_edificio.add_edge(u, v, weight=dist)

# --- 2. EL AGENTE JERÁRQUICO ---
class AgenteInteligente(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(model) # Ajuste Mesa 3.0
        self.unique_id = unique_id
        self.velocidad = 0.5
        self.destino_actual = None # Coordenada (x,y)
        self.plan_maestro = []     # Lista de nodos: ['Puerta_A', 'Puerta_B', 'SALIDA']

    def step(self):
        # 1. SI NO TENGO PLAN, LO CALCULO (Conexión Dinámica)
        if not self.plan_maestro:
            self.calcular_ruta_estrategica()

        # 2. MOVERSE AL SIGUIENTE HITO
        if self.destino_actual is not None:
            self.mover_hacia_destino()

    def calcular_ruta_estrategica(self):
        # A. Identificar dónde estoy (Simulado: buscamos el nodo visible más cercano)
        # En una versión compleja, usarías raycasting para ver qué puertas ves.
        # Aquí simplificamos: conectamos al nodo más cercano del grafo.
        pos_agent = np.array(self.pos)
        nodo_mas_cercano = None
        min_dist = float('inf')

        for nombre_nodo, coords in nodos_clave.items():
            dist = np.linalg.norm(pos_agent - np.array(coords))
            if dist < min_dist:
                min_dist = dist
                nodo_mas_cercano = nombre_nodo

        # B. Calcular ruta en el Grafo Lógico
        # Nota: El agente "sabe" que está cerca de 'nodo_mas_cercano'
        try:
            # Dijkstra sobre el grafo de puertas
            ruta_nodos = nx.shortest_path(grafo_edificio, source=nodo_mas_cercano, target='SALIDA', weight='weight')
            
            # Convertimos nombres de nodos a coordenadas reales
            self.plan_maestro = [nodos_clave[n] for n in ruta_nodos]
            
            # El primer paso es mi primer objetivo
            if len(self.plan_maestro) > 0:
                self.destino_actual = np.array(self.plan_maestro[0])
                
        except nx.NetworkXNoPath:
            print("¡Socorro! No sé cómo llegar a la salida.")

    def mover_hacia_destino(self):
        # Lógica MICRO (Física simple)
        pos_actual = np.array(self.pos)
        vector = self.destino_actual - pos_actual
        dist = np.linalg.norm(vector)

        # Si llegué al hito (puerta), paso al siguiente
        if dist < 0.5:
            self.plan_maestro.pop(0) # Elimino el hito alcanzado
            if self.plan_maestro:
                self.destino_actual = np.array(self.plan_maestro[0])
            else:
                self.destino_actual = None # ¡Llegué al final!
                self.remove() # Salir de la simulación
            return

        # Movimiento normal
        direccion = vector / dist
        nueva_pos = pos_actual + (direccion * self.velocidad)
        self.model.space.move_agent(self, tuple(nueva_pos))


# --- 3. MODELO Y VISUALIZACIÓN (CORREGIDO) ---
class ModeloJerarquico(mesa.Model):
    def __init__(self):
        # 1. ¡IMPORTANTE! Inicializar el modelo padre de Mesa
        # Esto crea self.random y self.agents automáticamente
        super().__init__() 
        
        self.space = mesa.space.ContinuousSpace(ANCHO, ALTO, torus=False)
        
        # Crear un agente en la Habitación 1 (lejos de la salida)
        # Usamos self.next_id() si falla usamos un numero fijo, pero en este ejemplo simple:
        agente = AgenteInteligente(1, self)
        
        # Añadir al gestor de agentes (que ya existe gracias a super().__init__())
        self.agents.add(agente)
        self.space.place_agent(agente, (5, 5)) # Empieza en (5,5)

    def step(self):
        # En Mesa 3.0, self.agents ya tiene el método shuffle_do incorporado
        self.agents.shuffle_do("step")

# --- RENDERIZADO ---
model = ModeloJerarquico()
fig, ax = plt.subplots(figsize=(10, 5))

def update(frame):
    model.step()
    ax.clear()
    
    # 1. DIBUJAR EL GRAFO LÓGICO (Líneas grises fijas)
    for u, v in grafo_edificio.edges():
        p1 = nodos_clave[u]
        p2 = nodos_clave[v]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], c='gray', linestyle='--', alpha=0.5, linewidth=2)
        
    # 2. DIBUJAR NODOS DEL GRAFO (Puntos negros)
    for nombre, pos in nodos_clave.items():
        ax.scatter(*pos, c='black', s=50, zorder=2)
        ax.text(pos[0], pos[1]+0.5, nombre, fontsize=8, ha='center')

    # 3. DIBUJAR AGENTE (Punto azul)
    if len(model.agents) > 0:
        agente = list(model.agents)[0]
        ax.scatter(agente.pos[0], agente.pos[1], c='blue', s=100, zorder=3, label='Agente')
        
        # Dibujar línea hacia su objetivo actual (Visualizar su intención)
        if agente.destino_actual is not None:
            ax.plot([agente.pos[0], agente.destino_actual[0]], 
                    [agente.pos[1], agente.destino_actual[1]], c='blue', alpha=0.3)

    ax.set_xlim(0, ANCHO)
    ax.set_ylim(0, ALTO)
    ax.set_title(f"Navegación Jerárquica: Grafo de Puertas (Frame {frame})")

ani = animation.FuncAnimation(fig, update, frames=100, interval=50)
plt.show()