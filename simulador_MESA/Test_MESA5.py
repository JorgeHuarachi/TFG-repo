import mesa
import networkx as nx
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
import json
# Shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import nearest_points, unary_union
from matplotlib.patches import Polygon as MplPolygon

# --- 1. CONFIGURACIÓN GENERAL ---
RADIO_FISICO = 0.4        
RADIO_PERSONAL = 0.8      
RADIO_VISION_MUROS = 0.8
FUERZA_PARED = 1.2
FUERZA_MAXIMA = 4.0
VELOCIDAD_BASE = 0.1
RADIO_ZONA_SALIDA = 2.0   
RADIO_FUEGO = 2.0
FACTOR_CONGESTION = 2.0 

# --- 2. SISTEMA DE MÉTRICAS ---
class GestorDatos:
    def __init__(self):
        self.registros = []
        
    def registrar_evento(self, step, agente_id, tipo_evento, valor, posicion):
        self.registros.append({
            'Step': step, 'AgenteID': agente_id, 'Evento': tipo_evento,
            'Valor': str(valor), 'Pos_X': posicion[0], 'Pos_Y': posicion[1]
        })
    
    def exportar_csv(self, nombre_salida="metricas_evacuacion.csv"):
        df = pd.DataFrame(self.registros)
        df.to_csv(nombre_salida, index=False)
        print(f"\n✅ Datos de simulación exportados a '{nombre_salida}'")
        return df

# --- 3. MODELO DINÁMICO ---
class ModeloAvanzado(mesa.Model):
    def __init__(self, ruta_mapa, posiciones_agentes=None):
        super().__init__()
        
        # 1. CARGAR DATOS DEL MAPA
        try:
            with open(ruta_mapa, 'r', encoding='utf-8') as f:
                datos = json.load(f)
        except FileNotFoundError:
            print(f"❌ ERROR: No se encuentra el archivo {ruta_mapa}. Ejecuta MAPA.py primero.")
            exit()
            
        self.ancho = datos['configuracion']['ancho']
        self.alto = datos['configuracion']['alto']
        
        # Convertir listas a tuplas para las coordenadas
        self.hitos = {k: tuple(v) for k, v in datos['hitos'].items()}
        
        # 2. INICIALIZAR ESPACIO
        self.space = mesa.space.ContinuousSpace(self.ancho, self.alto, torus=False)
        self.poligonos_muros = [] 
        self.construir_paredes_desde_json(datos['muros'])
        
        # 3. CONSTRUIR GRAFO
        self.grafo_logico = nx.Graph()
        self.construir_grafo_desde_json(datos['conexiones'])
        
        self.fuegos = []
        self.evacuados = 0
        self.todos_los_agentes = []
        self.datos = GestorDatos()
        self.step_count = 0

        lista_final_agentes = []
        
        if posiciones_agentes is not None:
            # Si le pasas una lista, ignora el JSON y usa la tuya
            print(f"🔵 Cargando {len(posiciones_agentes)} agentes manualmente desde el script.")
            lista_final_agentes = posiciones_agentes
        else:
            # Si le pasas None, busca la lista 'agentesspawn' dentro del JSON
            agentes_json = datos.get('agentesspawn', [])
            print(f"🔵 Cargando {len(agentes_json)} agentes guardados en el JSON.")
            # Convertimos las listas [x, y] del JSON a tuplas (x, y)
            lista_final_agentes = [tuple(p) for p in agentes_json]

        # 4. COLOCAR AGENTES DEFINITIVOS
        for i, pos in enumerate(lista_final_agentes):
            if self.es_transitable(pos):
                a = AgentePro(i, self)
                self.agents.add(a)
                self.space.place_agent(a, pos)
                self.todos_los_agentes.append(a)
            else:
                print(f"⚠️ Aviso: Agente {i} en la pos {pos} está dentro de un muro y fue ignorado.")

    def construir_paredes_desde_json(self, muros_json):
        # Variables temporales (sin self) para hacer los cálculos
        muros_crudos = []
        puertas = []

        # 1. Separamos los polígonos según su tipo
        for m in muros_json:
            poly = Polygon(m['poligono'])
            if m.get('tipo') in ['muro_exterior', 'muro_interior']:
                muros_crudos.append(poly)
            elif m.get('tipo') == 'puerta':
                puertas.append(poly)
                
        # 2. Unimos todos los muros en un solo bloque sólido gigante
        if muros_crudos:
            masa_muros = unary_union(muros_crudos)
        else:
            masa_muros = Polygon() # Polígono vacío si no hay muros
            
        # 3. Unimos todas las puertas en otro bloque
        if puertas:
            masa_puertas = unary_union(puertas)
        else:
            masa_puertas = Polygon()

        # 4. Hacemos el "taladro" (Diferencia booleana)
        muros_finales = masa_muros.difference(masa_puertas)
        
        # 5. Guardamos el resultado FINAL en 'self' para que el resto del simulador lo use
        self.poligonos_muros = []
        
        if muros_finales.is_empty:
            pass # No hay muros en el mapa
        elif muros_finales.geom_type == 'MultiPolygon':
            # Si al recortar quedaron varios trozos separados
            self.poligonos_muros = list(muros_finales.geoms)
        elif muros_finales.geom_type == 'Polygon':
            # Si quedó un solo bloque continuo de muro
            self.poligonos_muros = [muros_finales]

    def construir_grafo_desde_json(self, conexiones_json):
        for u, v in conexiones_json:
            p1 = np.array(self.hitos[u])
            p2 = np.array(self.hitos[v])
            distancia = np.linalg.norm(p1 - p2)
            self.grafo_logico.add_edge(u, v, weight=distancia, base_weight=distancia)

    def tiene_linea_vision(self, p1, p2,dist_max=15.0):
        if np.linalg.norm(p2 - p1) > dist_max: 
            return False
            
        linea_visual = LineString([p1, p2])
        # Si la línea cruza CUALQUIER polígono, no hay visión
        for muro in self.poligonos_muros:
            if linea_visual.intersects(muro):
                return False
        return True
    
    def es_transitable(self, pos):
        # 1. No salir del mapa
        if not (0 <= pos[0] < self.ancho and 0 <= pos[1] < self.alto):
            return False
            
        punto_agente = Point(pos[0], pos[1])
        # 2. No estar dentro de un muro
        for muro in self.poligonos_muros:
            if muro.contains(punto_agente):
                return False
        return True
    
    def crear_fuego(self, x, y):
        self.fuegos.append({'pos': np.array([x, y]), 'radio': RADIO_FUEGO})
        self.datos.registrar_evento(self.step_count, "SYSTEM", "FUEGO_CREADO", f"Pos: {x},{y}", (x,y))
        
        for u, v in self.grafo_logico.edges():
            peso = self.grafo_logico[u][v]['base_weight']
            p1, p2 = np.array(self.hitos[u]), np.array(self.hitos[v])
            for f in self.fuegos:
                mid = (p1 + p2) / 2
                if np.linalg.norm(mid - f['pos']) < (RADIO_FUEGO + 3.0): 
                    peso += 5000 
            self.grafo_logico[u][v]['weight'] = peso

        for agente in self.agents: agente.necesita_recalcular = True

    def actualizar_pesos_congestion(self):
        if self.step_count % 10 != 0: return 
        for u, v in self.grafo_logico.edges():
            p1, p2 = np.array(self.hitos[u]), np.array(self.hitos[v])
            mid = (p1 + p2) / 2
            agentes_cerca = sum(1 for a in self.agents if np.linalg.norm(a.pos - mid) < 3.0)
            peso_actual = self.grafo_logico[u][v]['weight']
            self.grafo_logico[u][v]['weight'] = peso_actual + (agentes_cerca * FACTOR_CONGESTION)

    def step(self):
        self.step_count += 1
        self.actualizar_pesos_congestion()
        self.agents.shuffle_do("step")

# --- 4. AGENTE ---
class AgentePro(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.velocidad_actual = np.zeros(2)
        self.destino_actual = None
        self.plan_maestro = []
        self.necesita_recalcular = False
        self.traza_x = []
        self.traza_y = []
        self.posiciones_recientes = [] 
        self.evacuado = False
        self.ruta_actual_str = "" 
        self.cooldown_atajo = 0

    def step(self):
        if self.evacuado: return 
        
        self.traza_x.append(self.pos[0])
        self.traza_y.append(self.pos[1])
        
        # 1. Recálculo si hay fuego
        if self.necesita_recalcular:
            self.plan_maestro = []
            self.destino_actual = None
            self.necesita_recalcular = False
            self.model.datos.registrar_evento(self.model.step_count, self.unique_id, "RECALCULO", "Fuego detectado", self.pos)
        
        # 2. Pedir ruta nueva si no tiene
        if not self.plan_maestro: 
            self.calcular_ruta_dijkstra()
        
        # 3. NUEVA LÓGICA DE ATAJOS (Visión de 2 nodos + Cooldown)
        if self.cooldown_atajo > 0:
            self.cooldown_atajo -= 1  # Esperando para volver a mirar...
            
        elif len(self.plan_maestro) > 1:
            # Mirar máximo 2 nodos por delante
            nodos_visibles = min(2, len(self.plan_maestro) - 1)
            
            # Revisar desde el más lejano (dentro de los 2) hasta el más cercano
            for i in range(nodos_visibles, 0, -1):
                nodo_futuro = self.plan_maestro[i]
                
                if self.model.tiene_linea_vision(np.array(self.pos), nodo_futuro):
                    # ¡Bingo! Vemos un nodo futuro. Borramos los pasos intermedios.
                    for _ in range(i):
                        self.plan_maestro.pop(0)
                        
                    self.destino_actual = self.plan_maestro[0]
                    # Aplicamos un bloqueo de medio segundo (15 frames)
                    self.cooldown_atajo = 15 
                    break # Importante: Salimos del bucle si ya encontramos el atajo más largo posible
                    
        # 4. Movimiento Físico
        if self.destino_actual is not None: 
            self.mover_pro()
            self.verificar_salida()

    def verificar_salida(self):
        # Busca todas las salidas posibles del mapa dinámicamente
        nodos_salida = [pos for n, pos in self.model.hitos.items() if 'SALIDA' in n]
        
        for pos_salida in nodos_salida:
            dist_salida = np.linalg.norm(np.array(self.pos) - np.array(pos_salida))
            if dist_salida < RADIO_ZONA_SALIDA:
                self.model.evacuados += 1
                self.evacuado = True 
                
                tiempo_total = self.model.step_count
                self.model.datos.registrar_evento(tiempo_total, self.unique_id, "EVACUACION_COMPLETA", f"Tiempo: {tiempo_total}", self.pos)
                
                self.model.space.remove_agent(self)
                self.remove() 
                break # Evacuado exitosamente

    def calcular_ruta_dijkstra(self):
        pos = np.array(self.pos)
        nodo_cercano = min(self.model.hitos, key=lambda k: np.linalg.norm(pos - np.array(self.model.hitos[k])))
        
        # Buscar el nombre de todos los nodos de salida disponibles
        nodos_salida = [n for n in self.model.hitos.keys() if 'SALIDA' in n]
        if not nodos_salida: return
        
        # Buscar la ruta a la salida más óptima
        mejor_ruta = None
        menor_peso = float('inf')
        
        for salida in nodos_salida:
            try:
                ruta = nx.shortest_path(self.model.grafo_logico, nodo_cercano, salida, weight='weight')
                peso_ruta = nx.path_weight(self.model.grafo_logico, ruta, weight='weight')
                if peso_ruta < menor_peso:
                    menor_peso = peso_ruta
                    mejor_ruta = ruta
            except nx.NetworkXNoPath:
                continue
                
        if mejor_ruta:
            ruta_str = "->".join(mejor_ruta)
            if ruta_str != self.ruta_actual_str:
                self.model.datos.registrar_evento(self.model.step_count, self.unique_id, "CAMBIO_RUTA", ruta_str, self.pos)
                self.ruta_actual_str = ruta_str

            self.plan_maestro = [np.array(self.model.hitos[n]) for n in mejor_ruta]
            if self.plan_maestro: self.destino_actual = self.plan_maestro[0]

    def mover_pro(self):
        pos = np.array(self.pos)
        vec_objetivo = self.destino_actual - pos
        dist_meta = np.linalg.norm(vec_objetivo)
        
        if dist_meta < 0.5:
            if self.plan_maestro: self.plan_maestro.pop(0); self.destino_actual = self.plan_maestro[0] if self.plan_maestro else None
            return

        # Anti-atasco
        self.posiciones_recientes.append(pos)
        if len(self.posiciones_recientes) > 20: 
            self.posiciones_recientes.pop(0)
            desplazamiento = np.linalg.norm(pos - self.posiciones_recientes[0])
            if desplazamiento < 0.2:
                self.velocidad_actual += np.random.uniform(-1.5, 1.5, 2)
                self.posiciones_recientes = [] 
        
        fuerza = np.zeros(2)
        if dist_meta > 0: 
            fuerza += (vec_objetivo / dist_meta) * 2.0 

        # Paredes
        punto_agente = Point(pos[0], pos[1])
        
        for muro in self.model.poligonos_muros:
            # 1. Distancia exacta a la superficie del muro
            d = muro.distance(punto_agente)
            
            # 2. Si está a menos de 0.8m, empieza la repulsión
            if d < RADIO_VISION_MUROS and d > 0.001:
                # 3. Buscamos el punto de la pared que tenemos más cerca
                punto_pared, _ = nearest_points(muro, punto_agente)
                coord_pared = np.array([punto_pared.x, punto_pared.y])
                
                # 4. Generamos la fuerza de empuje
                vec_muro = pos - coord_pared
                intensidad = FUERZA_PARED * np.exp(-d * 2) 
                fuerza += (vec_muro/d) * intensidad
        # Social
        vecinos = self.model.space.get_neighbors(self.pos, RADIO_PERSONAL, include_center=False)
        hay_vecinos = False
        for v in vecinos:
            if hasattr(v, 'evacuado') and v.evacuado: continue
            
            vec_alej = pos - np.array(v.pos)
            dist = np.linalg.norm(vec_alej)
            dist_piel = dist - (RADIO_FISICO * 2)
            hay_vecinos = True

            if dist < 0.001: 
                fuerza += np.random.uniform(-1, 1, 2) 
                continue

            if dist < RADIO_PERSONAL:
                 fuerza += (vec_alej / dist) * (1.5 * np.exp(-dist_piel))
        
        if hay_vecinos:
             fuerza += np.random.uniform(-0.05, 0.05, 2)

        norm_f = np.linalg.norm(fuerza)
        if norm_f > FUERZA_MAXIMA: fuerza = (fuerza / norm_f) * FUERZA_MAXIMA

        self.velocidad_actual = (self.velocidad_actual * 0.7) + (fuerza * 0.3)
        speed = np.linalg.norm(self.velocidad_actual)
        if speed > VELOCIDAD_BASE:
            self.velocidad_actual = (self.velocidad_actual / speed) * VELOCIDAD_BASE

        nueva_pos = pos + self.velocidad_actual
        if self.model.es_transitable(nueva_pos):
            self.model.space.move_agent(self, tuple(nueva_pos))
        else:
            self.velocidad_actual *= 0.1 

# --- 5. EJECUCIÓN (¡AQUÍ DEFINES TUS ESCENARIOS!) ---

# Crea la lista de agentes como tú quieras para esta prueba concreta
# Ejemplo 1: Poner un grupo grande en la habitación inferior izquierda
agentes_prueba_1 = [
    (2, 21), (3, 21), (4, 21), (5, 21),
    (2, 20), (3, 20), (4, 20), (5, 20),
    (2, 19), (3, 19), (4, 19), (5, 19),
    (30, 22), (32, 15), (10, 5) # Y un par dispersos
]

# Inicializar modelo pasándole el mapa guardado y los agentes
model = ModeloAvanzado(
    ruta_mapa="20x20_MurosParaSimular_FINAL.json", 
    posiciones_agentes=None # Cambia a agentes_prueba_1 para usar la lista personalizada
)

# --- 6. VISUALIZACIÓN ---
fig, ax = plt.subplots(figsize=(10, 7), facecolor='#101010')
ax.set_facecolor('#101010')

# Dibujar Fondo basado en las medidas del JSON
lineas_x, lineas_y = [], []
for x in range(model.ancho): lineas_x.extend([x, x, None]); lineas_y.extend([0, model.alto, None])
for y in range(model.alto): lineas_x.extend([0, model.ancho, None]); lineas_y.extend([y, y, None])
ax.plot(lineas_x, lineas_y, c='#004400', linewidth=0.5, alpha=0.3)
for muro in model.poligonos_muros:
    # Extraemos las coordenadas X e Y del polígono de Shapely
    x, y = muro.exterior.xy
    # Lo pintamos como un parche gris
    muro_patch = MplPolygon(list(zip(x, y)), closed=True, facecolor='gray', edgecolor='black', alpha=0.8, zorder=2)
    ax.add_patch(muro_patch)

# Dibujar Salidas dinámicamente
zonas_salida_dibujos = []
for nombre, pos_salida in model.hitos.items():
    if 'SALIDA' in nombre:
        zs = Circle(pos_salida, RADIO_ZONA_SALIDA, color='lime', alpha=0.2, zorder=1)
        ax.add_patch(zs)
        ax.text(pos_salida[0], pos_salida[1], "EXIT", color='lime', ha='center', fontweight='bold', zorder=2)
        zonas_salida_dibujos.append(zs)

# Dibujar Grafo
lineas_grafo = []
for u, v in model.grafo_logico.edges():
    p1, p2 = model.hitos[u], model.hitos[v]
    l, = ax.plot([p1[0], p2[0]], [p1[1], p2[1]], c='#00FFFF', linewidth=1, alpha=0.4, zorder=3)
    lineas_grafo.append(l)

circulos_fisicos = []
circulos_personales = []
lineas_rastro = [] 
lineas_intencion = [] 
artistas_fuego = []

for _ in range(len(model.todos_los_agentes)):
    lr, = ax.plot([], [], c='yellow', linewidth=0.8, alpha=0.5, zorder=9)
    lineas_rastro.append(lr)
    li, = ax.plot([], [], c='white', linestyle=':', linewidth=1.0, alpha=0.7, zorder=9)
    lineas_intencion.append(li)
    cp = Circle((0,0), RADIO_PERSONAL, facecolor='#0088FF', alpha=0.2, zorder=10, visible=False)
    ax.add_patch(cp)
    circulos_personales.append(cp)
    cf = Circle((0,0), RADIO_FISICO, facecolor='orange', edgecolor='black', zorder=11, visible=False)
    ax.add_patch(cf)
    circulos_fisicos.append(cf)

texto_info = ax.text(2, model.alto-2, "", color="white", fontsize=12, zorder=20)
ax.axis('off')

cid = fig.canvas.mpl_connect('button_press_event', lambda e: model.crear_fuego(e.xdata, e.ydata) if e.xdata else None)

def init():
    return circulos_fisicos + circulos_personales + lineas_rastro + lineas_intencion + lineas_grafo + [texto_info] + zonas_salida_dibujos + artistas_fuego

def update(frame):
    model.step()
    agentes_activos = 0
    
    for i, agente in enumerate(model.todos_los_agentes):
        lineas_rastro[i].set_data(agente.traza_x, agente.traza_y)
        lineas_rastro[i].set_visible(True)

        if not agente.evacuado:
            pos = agente.pos
            circulos_fisicos[i].center = pos; circulos_fisicos[i].set_visible(True)
            circulos_personales[i].center = pos; circulos_personales[i].set_visible(True)
            
            if agente.destino_actual is not None:
                lineas_intencion[i].set_data([pos[0], agente.destino_actual[0]], [pos[1], agente.destino_actual[1]])
                lineas_intencion[i].set_visible(True)
            else:
                lineas_intencion[i].set_visible(False)
            agentes_activos += 1
        else:
            circulos_fisicos[i].set_visible(False)
            circulos_personales[i].set_visible(False)
            lineas_intencion[i].set_visible(False)
            
    if model.fuegos:
        for i, (u, v) in enumerate(model.grafo_logico.edges()):
            peso = model.grafo_logico[u][v]['weight']
            if peso > 2000: color = 'red'; width = 2
            elif peso > 20: color = 'yellow'; width = 1.5 
            else: color = '#00FFFF'; width = 1
            lineas_grafo[i].set_color(color)
            lineas_grafo[i].set_linewidth(width)
            
    while len(artistas_fuego) < len(model.fuegos) * 2:
        idx_fuego = len(artistas_fuego) // 2
        f = model.fuegos[idx_fuego]
        nucleo = Circle(tuple(f['pos']), f['radio'] * 0.5, color='red', alpha=0.9, zorder=5)
        aura = Circle(tuple(f['pos']), f['radio'], color='orange', alpha=0.3, zorder=4)
        ax.add_patch(nucleo); ax.add_patch(aura)
        artistas_fuego.append(nucleo); artistas_fuego.append(aura)
    
    texto_info.set_text(f"Evacuados: {model.evacuados} | Activos: {agentes_activos}")
    return circulos_fisicos + circulos_personales + lineas_rastro + lineas_intencion + lineas_grafo + [texto_info] + artistas_fuego

ani = animation.FuncAnimation(fig, update, frames=600, init_func=init, interval=30, blit=True)
plt.show()

# AL CERRAR LA VENTANA, EXPORTA LOS DATOS
model.datos.exportar_csv(nombre_salida="simulacion_prueba_1.csv")