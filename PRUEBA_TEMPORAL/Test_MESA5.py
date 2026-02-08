import mesa
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# --- 1. CONFIGURACIÓN ---
ANCHO, ALTO = 40, 25
HITOS = {
    'Sala_Reuniones': (8, 20), 'Puerta_Reuniones': (8, 15),
    'Oficina_Jefe': (8, 5), 'Puerta_Jefe': (12, 5),
    'Comedor': (20, 20), 'Puerta_Comedor': (20, 15),
    'Pasillo_Oeste': (12, 15), 'Pasillo_Centro': (20, 15),
    'Pasillo_Este': (32, 15), 'SALIDA': (38, 15)
}

# --- 2. MODELO CON RAYCASTING (VISIÓN) ---
class ModeloGrid(mesa.Model):
    def __init__(self):
        super().__init__()
        self.space = mesa.space.ContinuousSpace(ANCHO, ALTO, torus=False)
        self.mapa_muros = np.zeros((ANCHO, ALTO)) # 0=Libre, 1=Muro
        self.construir_paredes()
        
        self.grafo_logico = nx.Graph()
        self.construir_grafo()
        self.fuegos = []

        # Crear Agentes
        posiciones = [(5, 22), (10, 22), (5, 5), (10, 5), (18, 22), (22, 22)]
        for i, pos in enumerate(posiciones):
            a = AgenteOptimizado(i, self)
            self.agents.add(a)
            self.space.place_agent(a, pos)

    def tiene_linea_vision(self, p1, p2):
        """
        Algoritmo de Raycasting simplificado.
        Comprueba si la línea recta entre p1 y p2 toca algún muro.
        """
        # Número de pasos para muestrear la línea (precisión)
        dist = np.linalg.norm(p2 - p1)
        pasos = int(dist * 2) # 2 muestras por cada unidad de distancia
        if pasos == 0: return True
        
        for i in range(pasos + 1):
            t = i / pasos
            # Interpolación lineal (Punto intermedio)
            x = int(p1[0] + (p2[0] - p1[0]) * t)
            y = int(p1[1] + (p2[1] - p1[1]) * t)
            
            # Chequear limites y colisión
            if 0 <= x < ANCHO and 0 <= y < ALTO:
                if self.mapa_muros[x, y] == 1:
                    return False # ¡Choca con muro!
        return True

    def construir_paredes(self):
        # Bordes
        self.mapa_muros[0,:] = 1; self.mapa_muros[-1,:] = 1
        self.mapa_muros[:,0] = 1; self.mapa_muros[:,-1] = 1
        # Habitaciones
        self.mapa_muros[0:15, 15] = 1  # Muro Pasillo Oeste
        self.mapa_muros[15, 15:25] = 1 # Divisor vertical
        self.mapa_muros[15:30, 15] = 1 # Muro Pasillo Centro
        self.mapa_muros[0:15, 8] = 1   # Muro Oficina Jefe (horizontal)
        
        # Huecos (Puertas)
        # Puerta Reuniones (8, 15) -> Abrimos hueco en el muro Y=15
        self.mapa_muros[7:10, 15] = 0 
        # Puerta Jefe (12, 5) -> No hay muro ahi exactamente, es zona abierta
        # Puerta Comedor (20, 15)
        self.mapa_muros[19:22, 15] = 0
        # Salida
        self.mapa_muros[ANCHO-2:ANCHO, 13:17] = 0

    def construir_grafo(self):
        conexiones = [
            ('Sala_Reuniones', 'Puerta_Reuniones'), ('Puerta_Reuniones', 'Pasillo_Oeste'),
            ('Oficina_Jefe', 'Puerta_Jefe'), ('Puerta_Jefe', 'Pasillo_Oeste'),
            ('Comedor', 'Puerta_Comedor'), ('Puerta_Comedor', 'Pasillo_Centro'),
            ('Pasillo_Oeste', 'Pasillo_Centro'), ('Pasillo_Centro', 'Pasillo_Este'), 
            ('Pasillo_Este', 'SALIDA')
        ]
        for u, v in conexiones:
            p1, p2 = np.array(HITOS[u]), np.array(HITOS[v])
            self.grafo_logico.add_edge(u, v, weight=np.linalg.norm(p1 - p2))

    def es_transitable(self, pos):
        x, y = int(pos[0]), int(pos[1])
        if 0 <= x < ANCHO and 0 <= y < ALTO:
            return self.mapa_muros[x, y] == 0
        return False
    
    def crear_fuego(self, x, y):
        self.fuegos.append({'pos': np.array([x, y]), 'radio': 3.0})
        # Actualizar pesos (simplificado)
        for u, v in self.grafo_logico.edges():
            p1, p2 = np.array(HITOS[u]), np.array(HITOS[v])
            peso = np.linalg.norm(p1 - p2)
            for f in self.fuegos:
                mid = (p1 + p2) / 2
                if np.linalg.norm(mid - f['pos']) < 5.0: peso += 1000
            self.grafo_logico[u][v]['weight'] = peso
    
    def step(self): self.agents.shuffle_do("step")

# --- 3. AGENTE CON OPTIMIZACIÓN (ATAJOS) ---
class AgenteOptimizado(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.unique_id = unique_id
        self.velocidad = 0.6
        self.destino_actual = None
        self.plan_maestro = [] # Coordenadas
        self.traza_x = []
        self.traza_y = []

    def step(self):
        if self.pos is not None:
            self.traza_x.append(self.pos[0])
            self.traza_y.append(self.pos[1])
            
        # 1. ¿Necesito plan?
        if not self.plan_maestro:
            self.calcular_ruta_base()
        
        # 2. OPTIMIZACIÓN EN TIEMPO REAL (Tu petición)
        # Si tengo un plan con varios pasos, miro si puedo saltarme el siguiente
        if len(self.plan_maestro) >= 2:
            siguiente_hito = self.plan_maestro[0]
            hito_despues = self.plan_maestro[1]
            
            pos_actual = np.array(self.pos)
            
            # ¿Veo directamente el hito subsiguiente?
            if self.model.tiene_linea_vision(pos_actual, hito_despues):
                # ¡SÍ! Atajo encontrado. Me salto el inmediato.
                self.plan_maestro.pop(0) # Elimino el intermedio
                self.destino_actual = self.plan_maestro[0]

        # 3. Movimiento
        if self.destino_actual is not None:
            self.mover()

    def calcular_ruta_base(self):
        pos = np.array(self.pos)
        nodo_cercano = min(HITOS, key=lambda k: np.linalg.norm(pos - np.array(HITOS[k])))
        try:
            ruta = nx.shortest_path(self.model.grafo_logico, nodo_cercano, 'SALIDA', weight='weight')
            self.plan_maestro = [np.array(HITOS[n]) for n in ruta]
            if self.plan_maestro: self.destino_actual = self.plan_maestro[0]
        except: pass

    def mover(self):
        pos = np.array(self.pos)
        vec = self.destino_actual - pos
        dist = np.linalg.norm(vec)
        
        if dist < 0.5: # Llegada
            if self.plan_maestro:
                self.plan_maestro.pop(0)
                self.destino_actual = self.plan_maestro[0] if self.plan_maestro else None
            return

        # Repulsión simple de muros para no chocar al coger atajos
        fuerza_muro = np.zeros(2)
        xi, yi = int(pos[0]), int(pos[1])
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if self.model.mapa_muros[xi+dx, yi+dy] == 1:
                    diff = pos - np.array([xi+dx, yi+dy])
                    fuerza_muro += diff * 0.5

        move = (vec/dist) + fuerza_muro
        norm = np.linalg.norm(move)
        move = (move/norm) * self.velocidad if norm > 0 else np.zeros(2)
        
        new_pos = pos + move
        if self.model.es_transitable(new_pos):
            self.model.space.move_agent(self, tuple(new_pos))

# --- 4. VISUALIZACIÓN "GRID & NEON" ---
model = ModeloGrid()
fig, ax = plt.subplots(figsize=(10, 7), facecolor='#202020')
ax.set_facecolor('#101010')

# Generamos las líneas del Grid (NavMesh) para pintarlas una sola vez
lineas_grid_x = []
lineas_grid_y = []
# Líneas verticales
for x in range(ANCHO):
    lineas_grid_x.extend([x, x, None])
    lineas_grid_y.extend([0, ALTO, None])
# Líneas horizontales
for y in range(ALTO):
    lineas_grid_x.extend([0, ANCHO, None])
    lineas_grid_y.extend([y, y, None])

cid = fig.canvas.mpl_connect('button_press_event', lambda e: model.crear_fuego(e.xdata, e.ydata) if e.xdata else None)

def update(frame):
    model.step()
    ax.clear()

    # 1. GRID (NavMesh) - Estilo TRON
    # Pintamos todas las lineas de la cuadrícula muy finas y tenues
    ax.plot(lineas_grid_x, lineas_grid_y, c='#004400', linewidth=0.5, alpha=0.3, zorder=0)
    
    # Pintamos los MUROS encima (Tapan la cuadrícula)
    ax.imshow(model.mapa_muros.T, cmap=plt.cm.gray, origin='lower', alpha=0.8, extent=[0, ANCHO, 0, ALTO], zorder=1)

    # 2. NAVGRAPH (Grafo Lógico) - FLOTANDO ENCIMA
    # Nodos
    for nombre, pos in HITOS.items():
        # Nodo Magenta Brillante
        ax.scatter(*pos, c='#FF00FF', s=100, edgecolors='white', zorder=10)
        # Etiqueta
        ax.text(pos[0], pos[1]+0.8, nombre.split('_')[-1], color='#FF00FF', fontsize=7, ha='center', zorder=10)
    
    # Aristas
    for u, v in model.grafo_logico.edges():
        p1, p2 = HITOS[u], HITOS[v]
        peso = model.grafo_logico[u][v]['weight']
        col = 'red' if peso > 500 else '#00FFFF' # Cian para normal, Rojo peligro
        width = 2 if peso > 500 else 1.5
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], c=col, linewidth=width, zorder=9)

    # 3. AGENTES Y ATAJOS
    if len(model.agents) > 0:
        for a in model.agents:
            # Traza real
            ax.plot(a.traza_x, a.traza_y, c='yellow', linewidth=1, alpha=0.5)
            # Linea de visión (hacia donde mira realmente)
            if a.destino_actual is not None:
                ax.plot([a.pos[0], a.destino_actual[0]], [a.pos[1], a.destino_actual[1]], 
                        c='white', linestyle=':', linewidth=1, alpha=0.8)
        
        xs = [a.pos[0] for a in model.agents]
        ys = [a.pos[1] for a in model.agents]
        ax.scatter(xs, ys, c='orange', s=60, edgecolors='black', zorder=11)

    # 4. FUEGOS
    for f in model.fuegos:
        ax.add_patch(plt.Circle(tuple(f['pos']), f['radio'], color='red', alpha=0.5, zorder=5))

    ax.set_xlim(0, ANCHO); ax.set_ylim(0, ALTO)
    ax.set_title(f"NavMesh (Grid) | NavGraph (Magenta/Cian) | Atajos Activados", color='white')
    ax.axis('off') # Quitar ejes numéricos para look más limpio

ani = animation.FuncAnimation(fig, update, frames=300, interval=40)
plt.show()