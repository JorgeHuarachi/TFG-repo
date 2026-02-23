import mesa
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# --- CONFIGURACIÓN ---
ANCHO, ALTO = 40, 20

# Definimos los nodos del grafo lógico (Igual que antes)
nodos_clave = {
    'H1_Centro': (8, 10), 'Puerta_A': (15, 10),
    'Pasillo_C': (20, 10), 'Puerta_B': (25, 10),
    'H2_Centro': (32, 10), 'SALIDA': (38, 10),
    'Ruta_Alt': (20, 18) # Un pasillo alternativo por arriba
}

# Conexiones: (Origen, Destino)
# Nota: Añadimos una ruta alternativa para que tenga opciones
conexiones_base = [
    ('H1_Centro', 'Puerta_A'), ('Puerta_A', 'Pasillo_C'),
    ('Pasillo_C', 'Puerta_B'), ('Puerta_B', 'H2_Centro'),
    ('H2_Centro', 'SALIDA'),
    # Ruta alternativa (un rodeo)
    ('Puerta_A', 'Ruta_Alt'), ('Ruta_Alt', 'Puerta_B') 
]

class AgenteInteligente(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.unique_id = unique_id
        self.velocidad = 0.6
        self.destino_actual = None 
        self.plan_maestro = []     # Lista de nombres de nodos: ['Puerta_A', ...]
        self.recalculos = 0        # CONTADOR DE VECES QUE CAMBIA DE IDEA

    def step(self):
        # 1. PERCEPCIÓN: ¿Mi plan actual sigue siendo seguro?
        if self.plan_maestro:
            if self.verificar_seguridad_ruta():
                self.recalculos += 1
                print(f"¡PELIGRO DETECTADO! Recalculando... (Total: {self.recalculos})")
                self.calcular_ruta_estrategica()

        # 2. SI NO TENGO PLAN, LO CALCULO
        if not self.plan_maestro:
            self.calcular_ruta_estrategica()

        # 3. MOVERSE
        if self.destino_actual is not None:
            self.mover_hacia_destino()

    def verificar_seguridad_ruta(self):
        # Mira los siguientes pasos de su plan. Si alguno pasa por una arista
        # con peso muy alto (fuego), devuelve True (Necesito recalcular)
        
        # Obtenemos el nodo donde estoy (o el ultimo visitado)
        nodo_anterior = self.determinar_nodo_cercano()
        
        for siguiente_nodo in self.plan_maestro:
            # Consultamos al modelo el peso actual de esa conexión
            try:
                datos_arista = self.model.grafo_edificio[nodo_anterior][siguiente_nodo]
                peso = datos_arista['weight']
                # Si el peso es > 50, significa que hay fuego/humo
                if peso > 50: 
                    return True # ¡Mi ruta está quemada!
                nodo_anterior = siguiente_nodo
            except KeyError:
                pass # No hay conexión directa, ignorar
        return False

    def calcular_ruta_estrategica(self):
        start_node = self.determinar_nodo_cercano()
        try:
            ruta = nx.shortest_path(self.model.grafo_edificio, source=start_node, target='SALIDA', weight='weight')
            # Convertimos la ruta (nodos) en coordenadas, ignorando el nodo donde ya estoy
            if len(ruta) > 1:
                self.plan_maestro = ruta[1:] # Quitamos el inicio
                self.destino_actual = np.array(nodos_clave[self.plan_maestro[0]])
        except nx.NetworkXNoPath:
            print("No hay ruta posible a la salida.")

    def determinar_nodo_cercano(self):
        # Busca cuál es el nodo lógico más cerca de mi posición física
        pos = np.array(self.pos)
        dists = {name: np.linalg.norm(pos - np.array(coord)) for name, coord in nodos_clave.items()}
        return min(dists, key=dists.get)

    def mover_hacia_destino(self):
        pos_actual = np.array(self.pos)
        vector = self.destino_actual - pos_actual
        dist = np.linalg.norm(vector)

        if dist < 0.5: # Llegué al hito
            if self.plan_maestro:
                self.plan_maestro.pop(0)
                if self.plan_maestro:
                    self.destino_actual = np.array(nodos_clave[self.plan_maestro[0]])
                else:
                    self.destino_actual = None 
                    self.remove()
            return

        direccion = vector / dist
        nueva_pos = pos_actual + (direccion * self.velocidad)
        self.model.space.move_agent(self, tuple(nueva_pos))

class ModeloReactivo(mesa.Model):
    def __init__(self):
        super().__init__()
        self.space = mesa.space.ContinuousSpace(ANCHO, ALTO, torus=False)
        
        # 1. CONSTRUIR GRAFO LÓGICO
        self.grafo_edificio = nx.Graph()
        self.actualizar_pesos_grafo(fuego_pos=None) # Pesos iniciales

        # 2. AGENTE
        agente = AgenteInteligente(1, self)
        self.agents.add(agente)
        self.space.place_agent(agente, (5, 5))
        
        self.fuego_pos = None

    def crear_fuego(self, x, y):
        self.fuego_pos = np.array([x, y])
        self.actualizar_pesos_grafo(self.fuego_pos)

    def actualizar_pesos_grafo(self, fuego_pos):
        # Reiniciar o actualizar pesos basados en el fuego
        self.grafo_edificio.clear()
        for u, v in conexiones_base:
            p1 = np.array(nodos_clave[u])
            p2 = np.array(nodos_clave[v])
            dist_base = np.linalg.norm(p1 - p2)
            
            peso = dist_base
            
            if fuego_pos is not None:
                # Comprobar si el fuego afecta a esta arista (línea)
                # Simplificación: medimos distancia del fuego al punto medio de la arista
                punto_medio = (p1 + p2) / 2
                dist_fuego = np.linalg.norm(punto_medio - fuego_pos)
                
                if dist_fuego < 4.0: # Radio de peligro
                    peso = 1000 # Bloqueado
            
            self.grafo_edificio.add_edge(u, v, weight=peso)

    def step(self):
        self.agents.shuffle_do("step")

# --- VISUALIZACIÓN ---
model = ModeloReactivo()
fig, ax = plt.subplots(figsize=(10, 6))

def on_click(event):
    if event.xdata:
        model.crear_fuego(event.xdata, event.ydata)

cid = fig.canvas.mpl_connect('button_press_event', on_click)

def update(frame):
    model.step()
    ax.clear()
    
    # 1. DIBUJAR GRAFO (Colores según peso)
    for u, v in model.grafo_edificio.edges():
        p1 = nodos_clave[u]
        p2 = nodos_clave[v]
        peso = model.grafo_edificio[u][v]['weight']
        color = 'red' if peso > 50 else 'lightgray'
        grosor = 3 if peso > 50 else 1
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], c=color, linestyle='--', linewidth=grosor, zorder=1)

    # 2. NODOS
    for nombre, pos in nodos_clave.items():
        ax.scatter(*pos, c='black', s=30, zorder=2)

    # 3. AGENTE
    if len(model.agents) > 0:
        agente = list(model.agents)[0]
        ax.scatter(*agente.pos, c='blue', s=120, zorder=3, label='Agente')
        # Mostrar contador de Recálculos encima del agente
        ax.text(agente.pos[0], agente.pos[1]+1, f"Recalculos: {agente.recalculos}", 
                color='blue', fontweight='bold', ha='center')
        
        # Dibujar línea de intención actual
        if agente.destino_actual is not None:
             ax.plot([agente.pos[0], agente.destino_actual[0]], 
                     [agente.pos[1], agente.destino_actual[1]], c='blue', alpha=0.3)

    # 4. FUEGO
    if model.fuego_pos is not None:
        ax.scatter(*model.fuego_pos, c='red', s=500, marker='X', zorder=5)

    ax.set_xlim(0, ANCHO)
    ax.set_ylim(0, ALTO)
    ax.set_title(f"Haz CLIC en una línea gris para bloquearla (simular fuego)\nFrame: {frame}")

ani = animation.FuncAnimation(fig, update, frames=200, interval=100)
plt.show()