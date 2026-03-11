import mesa
import networkx as nx
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
import json
import random
import os
# Shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import nearest_points, unary_union
from matplotlib.patches import Polygon as MplPolygon

# --- 1. CONSTANTES GLOBALES Y LEYES FÍSICAS ---
RADIO_FISICO = 0.25         # Radio del "cuerpo duro" (evita solapamientos en marcos de puertas)
RADIO_PERSONAL = 0.5        # Radio de la "burbuja social" (repulsión suave entre agentes)
RADIO_VISION_MUROS = 0.3    # Distancia a la que los muros empiezan a ejercer fuerza de repulsión
FUERZA_PARED = 4.0          # Capacidad del muro para repeler (Debe ser mayor que la fuerza del agente)
FUERZA_MAXIMA = 6.0         # Límite absoluto de aceleración en un solo step (Anti-bugs físicos)
VELOCIDAD_BASE = 0.1        # Velocidad estándar de desplazamiento en metros/step
RADIO_ZONA_SALIDA = 2.0     # Área de aceptación para dar a un agente por evacuado
RADIO_FUEGO = 2.0           # Área de afectación directa de una fuente de incendio
FACTOR_CONGESTION = 2.0     # Penalización de peso en el grafo por cada agente atascado en un nodo

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
        
        # --- 3.1. INGESTA DE DATOS (JSON) ---
        try:
            with open(ruta_mapa, 'r', encoding='utf-8') as f:
                datos = json.load(f)
        except FileNotFoundError:
            print(f"❌ ERROR: No se encuentra el archivo {ruta_mapa}. Ejecuta MAPA.py primero.")
            exit()
        self.ancho = datos['configuracion']['ancho']
        self.alto = datos['configuracion']['alto']
        
        # --- 3.2. RECONSTRUCCIÓN MLSM (Multi-Layer Spatial Model) ---
        self.espacios_navegables = datos['espacios_navegables']
        
        # Extracción de Centroides: Usados como anclajes de enrutamiento
        self.hitos = {}
        for nombre_nodo, datos_nodo in self.espacios_navegables.items():
            self.hitos[nombre_nodo] = tuple(datos_nodo['centroide'])
        
        # Conciencia Espacial Restringida: Pre-calculamos zonas prohibidas para movilidad tipo "Rolling""
        # Esto optimiza el cálculo de visión, evitando que atajen por escaleras virtualmente.
        self.poligonos_prohibidos_rolling = []
        for nombre, datos_espacio in self.espacios_navegables.items():
            if "Rolling" not in datos_espacio['atributos'].get('locomotion', []):
                self.poligonos_prohibidos_rolling.append(Polygon(datos_espacio['poligono']))
        
        # --- 3.3. FÍSICAS Y TOPOLOGÍA ---
        # Inicialización del plano físico continuo
        self.space = mesa.space.ContinuousSpace(self.ancho, self.alto, torus=False)
        self.poligonos_muros = [] 
        self.construir_paredes_desde_json(datos['muros'])
        
        # Inicialización del cerebro topológico (Grafo NetworkX)
        self.grafo_logico = nx.Graph()
        self.construir_grafo_desde_json(datos['conexiones_horizontales'])
        
        self.fuegos = []
        self.evacuados = 0
        self.todos_los_agentes = []
        self.datos = GestorDatos()
        self.step_count = 0

        # --- 3.4. POBLACIÓN DE LA SIMULACIÓN ---
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

        # Inserción física y asignación estocástica de perfiles
        for i, pos in enumerate(lista_final_agentes):
            if self.es_transitable(pos):
                # Generamos una población variada (Ej: 70% Walking, 15% Rolling, 15% Elderly)
                perfil_asignado = random.choices(
                    population=["Walking", "Rolling", "Elderly"], 
                    weights=[0.7, 0.15, 0.15] # Distribución demográfica
                )[0]
                
                # Le pasamos el perfil al crear el agente
                a = AgentePro(i, self, perfil=perfil_asignado)
                self.agents.add(a)
                self.space.place_agent(a, pos)
                self.todos_los_agentes.append(a)
            else:
                print(f"⚠️ Aviso: Agente {i} en la pos {pos} está dentro de un muro.")

    def construir_paredes_desde_json(self, muros_json):
        self.poligonos_muros = [] # Guardará: (geometría, tipo_de_muro)
        ext = 0
        int_ = 0
        
        for m in muros_json:
            tipo = m.get('tipo')
            # Solo cargamos las físicas duras, ignoramos huecos o zonas semánticas
            if tipo in ['muro_exterior', 'muro_interior']:
                poly = Polygon(m['poligono'])
                self.poligonos_muros.append((poly, tipo))
                
                if tipo == 'muro_exterior': ext += 1
                else: int_ += 1
                
        print(f"✅ GEOMETRÍA LISTA: {ext} Muros Ext. | {int_} Muros Int. (Recortes pre-calculados)")

    def construir_grafo_desde_json(self, conexiones_horizontales):
        enlaces_creados = 0
        for conn in conexiones_horizontales:
            if conn['tipo'] in ['navegable_puerta', 'door_to_door']:
                u = conn['origen']
                v = conn['destino']
                
                p1 = np.array(self.hitos[u])
                p2 = np.array(self.hitos[v])
                distancia = np.linalg.norm(p1 - p2)
                
                # --- TRUCO DE PATHFINDING ---
                # Hacemos que la ruta door_to_door parezca un 20% más corta para que Dijkstra la prefiera
                # Y penalizamos la ruta por el centro geométrico para usarla solo si no hay door_to_door
                if conn['tipo'] == 'door_to_door':
                    peso_ruta = distancia * 0.8  
                else:
                    peso_ruta = distancia * 1.5  
                
                self.grafo_logico.add_edge(
                    u, v, 
                    weight=peso_ruta, 
                    base_weight=peso_ruta, 
                    tipo=conn['tipo'], 
                    contexto=conn.get('contexto')
                )                
                enlaces_creados += 1
                
        print(f"✅ TOPOLOGÍA LISTA: {enlaces_creados} conexiones navegables activas.")

    def tiene_linea_vision(self, p1, p2, dist_max=15.0, perfil="Walking"): 
        if np.linalg.norm(p2 - p1) > dist_max: 
            return False
            
        # 1. Comprobamos la Línea de Visión (Muros opacos que bloquean a todos)
        linea_visual = LineString([p1, p2])
        for muro_poly, tipo in self.poligonos_muros:
            if linea_visual.intersects(muro_poly):
                return False
                
        # 2. Comprobamos la Línea de Movimiento (Solo para Rolling)
        if perfil == "Rolling":
            for poly_prohibido in self.poligonos_prohibidos_rolling:
                if linea_visual.intersects(poly_prohibido):
                    return False # Pueden verlo, pero no pueden atajar por ahí
                    
        return True

    def es_transitable(self, pos): 
        if not (0 <= pos[0] < self.ancho and 0 <= pos[1] < self.alto):
            return False
            
        punto_agente = Point(pos[0], pos[1])
        for muro_poly, tipo in self.poligonos_muros:
            if muro_poly.contains(punto_agente):
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
    def __init__(self, unique_id, model, perfil="Walking"):
        super().__init__(model)

        # --- 4.1. FISIOLOGÍA Y PERFIL ---
        self.perfil = perfil 

        # Ajustamos la velocidad base máxima de la entidad según sus capacidades físicas
        if self.perfil == "Rolling":
            self.velocidad_base = VELOCIDAD_BASE * 1.2 # Mayor velocidad en llano por las ruedas (Rolling)
        elif self.perfil == "Elderly":
            self.velocidad_base = VELOCIDAD_BASE * 0.5 # Los ancianos (Elderly) van a la mitad de velocidad
        else:
            self.velocidad_base = VELOCIDAD_BASE       # Walking estándar

        # --- 4.2. VECTORES FÍSICOS Y COLISIONES ---
        self.velocidad_actual = np.zeros(2)     # Vector de fuerza que se aplicará en el step actual
        self.posiciones_recientes = []          # Memoria espacial a corto plazo (usada para detectar si está atascado)
        
        # --- 4.3. MEMORIA Y NAVEGACIÓN SEMÁNTICA ---
        self.plan_maestro = []          # Lista de coordenadas (x,y) de la ruta calculada
        self.plan_maestro_nombres = []  # Lista de strings (Nombres de puertas/salas) paralela a la ruta
        self.destino_actual = None      # El punto físico (x,y) inmediato al que se dirige
        self.destino_previo = None      # El punto del que viene (usado como ancla para dibujar curvas de inercia)

        # --- 4.4. SISTEMA DE INERCIA Y VOLANTE DINÁMICO ---
        self.frames_transicion = 0          # Cronómetro regresivo. Si es > 0, el agente está trazando una curva
        self.MAX_FRAMES_TRANSICION = 60     # Duración base de un giro completo (aprox 2 segundos a 30fps)
        self.tiempo_en_tramo = 0            # Fotogramas que lleva caminando en línea recta (Evita giros robóticos)

        # --- 4.5. ESTADO DEL AGENTE Y LOGS ---
        self.evacuado = False               # Bandera que desactiva físicas al llegar a la salida
        self.necesita_recalcular = False    # Bandera que fuerza un nuevo pathfinding (ej. al aparecer un fuego)
        self.ruta_actual_str = ""           # String semántico (Ej: "P1 -> Aula -> P2") usado para registrar cambios limpios en el CSV

        # Trazas visuales para renderizado (La "estela" amarilla/verde/magenta)
        self.traza_x = []
        self.traza_y = []
        
    def step(self):
        # 1. COMPROBACIÓN DE ESTADO VITAL
        if self.evacuado: return # Si ya está a salvo, apagamos su IA para ahorrar CPU

        # Guardamos la huella histórica para el renderizado visual (estela de colores)
        self.traza_x.append(self.pos[0])
        self.traza_y.append(self.pos[1])
        
        # --- 2. EL CEREBRO: GESTIÓN DE RUTAS (Pathfinding) ---
        # Si ocurre un evento dinámico (como la aparición de un fuego), la bandera 'necesita_recalcular' se activa.
        if self.necesita_recalcular:
            self.plan_maestro = []      # Borramos la memoria espacial a largo plazo
            self.destino_actual = None  # Borramos el objetivo inmediato
            self.necesita_recalcular = False
            self.model.datos.registrar_evento(self.model.step_count, self.unique_id, "RECALCULO", "Fuego detectado", self.pos)
        
        # Si el agente sufre amnesia (acaba de nacer o huyó de un fuego), solicita una nueva ruta al grafo.
        if not self.plan_maestro: 
            self.calcular_ruta_dijkstra()
        
        # 3.1. BLOQUEO DE ENFOQUE (Focus Lock)
        # Si el agente se dirige a una puerta física, se le "ponen orejeras". 
        # Ignoramos la línea de visión hacia la siguiente sala para obligarle a cruzar el marco físicamente y evitar que ataje contra la pared.
        nombre_actual = self.plan_maestro_nombres[0] if self.plan_maestro_nombres else ""
        es_puerta_actual = 'Puerta' in nombre_actual
        
        # 3.2. SENSOR GEOMÉTRICO (Raycast)
            # Trazamos una línea imaginaria desde los ojos del agente hasta el siguiente hito de su lista.
        if len(self.plan_maestro) > 1 and not es_puerta_actual:
            nodo_siguiente = self.plan_maestro[1]
            
            # ¡Lo vemos! Descartamos el objetivo actual (ej. el centro virtual de una sala)
            if self.model.tiene_linea_vision(np.array(self.pos), nodo_siguiente, perfil=self.perfil):
                
                self.plan_maestro.pop(0)
                if self.plan_maestro_nombres: self.plan_maestro_nombres.pop(0)
                
                # 3.3. ENCADENAMIENTO DE OBJETIVOS (Target Chaining)
                # Aquí conectamos el Cerebro con la Física sin dar tirones bruscos.

                # CASO A: El agente iba caminando en línea recta perfecta.
                if self.frames_transicion == 0:
                    self.destino_previo = self.destino_actual.copy()
                    self.frames_transicion = self.MAX_FRAMES_TRANSICION
                
                # CASO B: El agente YA estaba haciendo una curva.
                # Al NO reiniciar 'frames_transicion', el agente mantiene "las manos firmes en el volante".
                # La matemática de la Fase 4 mezclará la curva que ya estaba haciendo con el nuevo destino.
                
                # Actualizamos la meta visual a la nueva puerta/centro descubierto.
                self.destino_actual = self.plan_maestro[0]
                    
        # 4. Movimiento Físico
        if self.destino_actual is not None: 
            self.mover_pro()
            self.verificar_salida()

    def verificar_salida(self):
        # Busca todas las salidas posibles del mapa dinámicamente
        nodos_salida = [pos for n, pos in self.model.hitos.items() if 'Salida' in n]
        
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
        nodos_salida = [n for n in self.model.hitos.keys() if 'Salida' in n]
        if not nodos_salida: return
        
        # NUEVO: Copiamos el mapa mental para este agente
        grafo_permitido = self.model.grafo_logico.copy()
        
        # Si el agente va en silla de ruedas, le prohibimos las escaleras/steps
        if self.perfil == "Rolling":
            nodos_prohibidos = []
            
            for nodo in grafo_permitido.nodes():
                datos_nodo = self.model.espacios_navegables.get(nodo)
                if datos_nodo:
                    locomotion = datos_nodo['atributos'].get('locomotion', [])
                    if "Rolling" not in locomotion:
                        nodos_prohibidos.append(nodo)
            
            # Borramos las escaleras del grafo de este agente
            grafo_permitido.remove_nodes_from(nodos_prohibidos)
            
            # ---> NUEVO: Borramos las aristas door_to_door que cruzan zonas prohibidas <---
            aristas_a_borrar = []
            for u, v, datos_arista in grafo_permitido.edges(data=True):
                contexto_arista = datos_arista.get('contexto')
                if contexto_arista in nodos_prohibidos:
                    aristas_a_borrar.append((u, v))
                    
            grafo_permitido.remove_edges_from(aristas_a_borrar)
        
        mejor_ruta = None
        menor_peso = float('inf')
        
        for salida in nodos_salida:
            try:
                # Ahora usamos 'grafo_permitido' en vez de 'self.model.grafo_logico'
                ruta = nx.shortest_path(grafo_permitido, nodo_cercano, salida, weight='weight')
                peso_ruta = nx.path_weight(grafo_permitido, ruta, weight='weight')
                if peso_ruta < menor_peso:
                    menor_peso = peso_ruta
                    mejor_ruta = ruta
            except nx.NetworkXNoPath:
                # Si una salida era por escaleras y el agente va en silla, saltará aquí
                continue
                
        if mejor_ruta:
            # --- 1. COMUNICACIÓN CLARA (Traducción Semántica) ---
            # Aunque la física use Puerta->Puerta, el log dirá Puerta->Habitación->Puerta
            ruta_semantica = []
            for i in range(len(mejor_ruta) - 1):
                u, v = mejor_ruta[i], mejor_ruta[i+1]
                ruta_semantica.append(u)
                
                contexto = grafo_permitido.edges[u, v].get('contexto')
                # Si hay una sala de contexto y no la hemos añadido ya, la metemos en la frase
                if contexto and contexto != u and contexto != v:
                    if not ruta_semantica or ruta_semantica[-1] != contexto:
                        ruta_semantica.append(contexto)
            ruta_semantica.append(mejor_ruta[-1])
            
            ruta_str = " -> ".join(ruta_semantica)
            if ruta_str != self.ruta_actual_str:
                self.model.datos.registrar_evento(self.model.step_count, self.unique_id, "CAMBIO_RUTA", ruta_str, self.pos)
                self.ruta_actual_str = ruta_str

            # --- 2. ENRUTAMIENTO MLSM (Puerta -> Centro -> Puerta) ---
            ruta_expandida = [mejor_ruta[0]]
            for i in range(len(mejor_ruta) - 1):
                u, v = mejor_ruta[i], mejor_ruta[i+1]
                contexto = grafo_permitido.edges[u, v].get('contexto')
                
                # Intercalamos el centro de la sala si existe y no es la puerta misma
                if contexto and contexto != u and contexto != v:
                    ruta_expandida.append(contexto)
                ruta_expandida.append(v)

            # Guardamos coordenadas y nombres
            self.plan_maestro = [np.array(self.model.hitos[nodo]) for nodo in ruta_expandida[1:]]
            self.plan_maestro_nombres = ruta_expandida[1:]

            if self.plan_maestro: 
                self.destino_actual = self.plan_maestro[0]


    def mover_pro(self):
        # El vector de posición actual y la fuerza acumulada resultante para este frame
        pos = np.array(self.pos)
        fuerza = np.zeros(2)
        dist_meta = 0.0

        # --- 1. SEMÁNTICA DEL TERRENO (Speed Limit Dinámico) ---
        limite_velocidad = self.velocidad_base
        punto_agente = Point(pos[0], pos[1])
        
        # El motor consulta la capa semántica: Si el agente pisa una zona etiquetada como 'Step' (Escaleras),
        # sufre una penalización física en su velocidad máxima, simulando la dificultad del terreno.
        for nombre, datos_espacio in self.model.espacios_navegables.items():
            locomotion = datos_espacio['atributos'].get('locomotion', [])
            # Si la zona por la que pisa es de tipo 'Step' (Escaleras)
            if 'Step' in locomotion:
                poly = Polygon(datos_espacio['poligono'])
                if poly.contains(punto_agente):
                    limite_velocidad *= 0.4 # Cae al 40% de su capacidad
                    break

        # --- 2. EL VOLANTE DINÁMICO Y FRENO INERCIAL (Steering) ---
        if self.frames_transicion > 0:
            # 2.1. Extracción de Vectores de Dirección
            norm_vel = np.linalg.norm(self.velocidad_actual)
            if norm_vel > 0.001:
                dir_viejo = self.velocidad_actual / norm_vel
            else:
                vec_fallback = self.destino_previo - pos
                dist_fb = np.linalg.norm(vec_fallback)
                dir_viejo = (vec_fallback / dist_fb) if dist_fb > 0 else np.zeros(2)

            vec_nuevo = self.destino_actual - pos
            dist_nuevo = np.linalg.norm(vec_nuevo)
            dir_nuevo = (vec_nuevo / dist_nuevo) if dist_nuevo > 0 else np.zeros(2)

            # Producto escalar: Mide la "brusquedad" del giro (-1: atrás, 0: 90º, 1: recto)
            dot_giro = np.dot(dir_viejo, dir_nuevo)

            # Si la meta ha quedado totalmente a la espalda, rompe la inercia para no dar círculos inútiles
            if dot_giro < -0.5:
                self.frames_transicion = 0
                fuerza += dir_nuevo * 2.0
                dist_meta = dist_nuevo
            else:
                # 2.2. Acelerador del Volante (Sensibilidad de Giro)
                acelerador = 1.0 + (1.0 - dot_giro) * 3.0
                if dist_nuevo < 2.0: 
                    acelerador *= 2.0 

                # 2.3. Freno Inercial Escalonado (Anti-Derrape)
                # Si el giro es muy cerrado, el límite de velocidad cae drásticamente.
                # A medida que el agente encara la puerta, el freno se libera solo.
                if dot_giro < 0.0: limite_velocidad *= 0.3      # Límite muy estricto para giros agudos
                elif dot_giro < 0.5: limite_velocidad *= 0.6    # Límite medio para esquinas cerradas
                elif dot_giro < 0.86: limite_velocidad *= 0.85  # Freno ligero para desvíos

                # 2.4. Mezcla Matemática (Interpolación Inercial)
                factor_nuevo = 1.0 - (self.frames_transicion / self.MAX_FRAMES_TRANSICION) 
                factor_viejo = 1.0 - factor_nuevo

                direccion_mezclada = (dir_viejo * factor_viejo) + (dir_nuevo * factor_nuevo)
                norm_mezcla = np.linalg.norm(direccion_mezclada)
                if norm_mezcla > 0:
                    fuerza += (direccion_mezclada / norm_mezcla) * 2.0

                self.frames_transicion -= acelerador
                if self.frames_transicion < 0: self.frames_transicion = 0
                dist_meta = dist_nuevo
                
        else:
            # Movimiento balístico en línea recta (El agente ya está encarado hacia la meta)
            vec_objetivo = self.destino_actual - pos
            dist_meta = np.linalg.norm(vec_objetivo)
            if dist_meta > 0:
                fuerza_atraccion = min(2.0, dist_meta * 2.0)
                fuerza += (vec_objetivo / dist_meta) * fuerza_atraccion

        # --- 3. LLEGADA AL OBJETIVO Y CRUCE DE PLANOS GEOMÉTRICOS ---
        nombre_destino = self.plan_maestro_nombres[0] if self.plan_maestro_nombres else ""
        
        # Radios dinámicos según el tipo de meta
        if 'Puerta' in nombre_destino or 'Salida' in nombre_destino:radio_llegada = 0.25    # Exige precisión milimétrica para obligarles a entrar al hueco
        elif 'Frontera' in nombre_destino:radio_llegada = 1.0                               # Las fronteras virtuales son anchas, pueden cruzarlas por cualquier lado
        else:radio_llegada = 1.2                                                            # Centros de habitación
            
        ha_llegado = dist_meta < radio_llegada
        
        # Cruce de Umbral: Si el agente es empujado contra el lateral de una puerta doble,
        # la geometría detecta que ya "está al otro lado" y lo da por cruzado aunque no pise el centro.
        if not ha_llegado and ('Puerta' in nombre_destino or 'Frontera' in nombre_destino) and len(self.plan_maestro) > 1:
            nodo_siguiente = self.plan_maestro[1]
            dist_puerta_siguiente = np.linalg.norm(self.destino_actual - nodo_siguiente)
            dist_agente_siguiente = np.linalg.norm(pos - nodo_siguiente)
            
            # Si estamos a menos de 1m de la puerta y el agente ya está más cerca
            # del siguiente destino que la propia puerta, es que ha cruzado el umbral físico.
            if dist_meta < 1.0 and dist_agente_siguiente < dist_puerta_siguiente:
                ha_llegado = True

        # Transición al siguiente nodo de la ruta
        if ha_llegado:
            self.tiempo_en_tramo = 0 
            if len(self.plan_maestro) > 1:
                # Al llegar a un punto, iniciamos una curva suave hacia el siguiente
                self.destino_previo = self.destino_actual.copy()
                self.plan_maestro.pop(0)
                if self.plan_maestro_nombres: self.plan_maestro_nombres.pop(0)
                self.destino_actual = self.plan_maestro[0]
                self.frames_transicion = self.MAX_FRAMES_TRANSICION
            else:
                # Meta final alcanzada
                self.frames_transicion = 0 
                self.plan_maestro.pop(0)
                if self.plan_maestro_nombres: self.plan_maestro_nombres.pop(0)
                self.destino_actual = None
            return

        # --- 4. SISTEMA ANTI-ATASCO (Desempate Simétrico) ---
        self.posiciones_recientes.append(pos)
        if len(self.posiciones_recientes) > 20: 
            self.posiciones_recientes.pop(0)
            desplazamiento = np.linalg.norm(pos - self.posiciones_recientes[0])
            # Si en 20 frames se ha movido menos de 20cm, inyectamos "pánico" (ruido aleatorio)
            if desplazamiento < 0.2:
                self.velocidad_actual += np.random.uniform(-1.5, 1.5, 2)
                self.posiciones_recientes = [] 

        # --- 5. FUERZAS DE REPULSIÓN (Muros y Multitudes) ---
        # Repulsión de Muros (Fuerza dura)
        punto_agente = Point(pos[0], pos[1])
        for muro_poly, tipo in self.model.poligonos_muros:
            frontera_muro = muro_poly.exterior
            d = frontera_muro.distance(punto_agente)
            dist_piel = d - RADIO_FISICO 
            if dist_piel < RADIO_VISION_MUROS:
                if dist_piel < 0.001: dist_piel = 0.001
                if d < 0.001: d = 0.001 
                punto_pared, _ = nearest_points(frontera_muro, punto_agente)
                coord_pared = np.array([punto_pared.x, punto_pared.y])
                vec_muro = pos - coord_pared
                # Decaimiento exponencial: Cuanto más cerca, infinita más fuerza ejerce el muro
                intensidad = FUERZA_PARED * np.exp(-dist_piel * 8) 
                fuerza += (vec_muro / d) * intensidad

        # Repulsión Social (Burbuja interpersonal)
        vecinos = self.model.space.get_neighbors(self.pos, RADIO_PERSONAL, include_center=False)
        hay_vecinos = False
        for v in vecinos:
            if hasattr(v, 'evacuado') and v.evacuado: continue
            vec_alej = pos - np.array(v.pos)
            dist = np.linalg.norm(vec_alej)
            dist_piel = dist - (RADIO_FISICO * 2)
            hay_vecinos = True
            if dist < 0.001: 
                fuerza += np.random.uniform(-1, 1, 2) # Ruido para desempate si se solapan en (0,0)
                continue
            if dist < RADIO_PERSONAL:
                 # Fuerza suave que decae con la distancia
                 fuerza += (vec_alej / dist) * (1.5 * np.exp(-dist_piel))
        if hay_vecinos:
             # Micro-variaciones para naturalidad
             fuerza += np.random.uniform(-0.05, 0.05, 2)

        # Limitador absoluto del "Físico del Agente"
        norm_f = np.linalg.norm(fuerza)
        if norm_f > FUERZA_MAXIMA: fuerza = (fuerza / norm_f) * FUERZA_MAXIMA

        # --- 6. INTEGRACIÓN CINEMÁTICA FINAL ---
        # Sumamos la fuerza resultante a la velocidad actual (70% inercia retenida, 30% fuerza nueva)
        self.velocidad_actual = (self.velocidad_actual * 0.7) + (fuerza * 0.3)
        speed = np.linalg.norm(self.velocidad_actual)
        
        # Aplicamos el limitador semántico calculado al inicio de la función (Ej. Escaleras)
        if speed > limite_velocidad:
            self.velocidad_actual = (self.velocidad_actual / speed) * limite_velocidad

        # Intento de Movimiento
        nueva_pos = pos + self.velocidad_actual
        if self.model.es_transitable(nueva_pos):
            self.model.space.move_agent(self, tuple(nueva_pos))
        else:
            self.velocidad_actual *= 0.1 # Colisión "blanda": pierde casi toda su energía si toca un polígono

# --- 5. EJECUCIÓN (¡AQUÍ DEFINES TUS ESCENARIOS!) ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Unimos esa ruta base con las carpetas de nuestro proyecto
ruta_escenario = os.path.join(BASE_DIR, "escenarios", "v3_TEST5_FINAL.json")
ruta_resultados = os.path.join(BASE_DIR, "resultados", "simulacion_prueba_1.csv")
# Inicializar modelo 
model = ModeloAvanzado(
    ruta_mapa=ruta_escenario, # <--- Usamos la ruta dinámica
    posiciones_agentes=None 
)
# --- 6. VISUALIZACIÓN ---
# 1. Suelo Oscuro (Gris casi negro)
fig, ax = plt.subplots(figsize=(10, 7), facecolor='#151515')
ax.set_facecolor('#151515')

# Cuadrícula de fondo más tenue
lineas_x, lineas_y = [], []
for x in range(model.ancho): lineas_x.extend([x, x, None]); lineas_y.extend([0, model.alto, None])
for y in range(model.alto): lineas_x.extend([0, model.ancho, None]); lineas_y.extend([y, y, None])
ax.plot(lineas_x, lineas_y, c='#333333', linewidth=0.5, alpha=0.5, zorder=0)

# 2. Dibujar Muros Claros
for muro_poly, tipo in model.poligonos_muros:
    x, y = muro_poly.exterior.xy
    
    # Muros Exteriores: Blanco/Gris muy claro. Muros Interiores: Gris medio
    color_muro = '#E8E8E8' if tipo == 'muro_exterior' else '#888888'
    
    muro_patch = MplPolygon(list(zip(x, y)), closed=True, facecolor=color_muro, edgecolor='#FFFFFF', alpha=1.0, zorder=2)
    ax.add_patch(muro_patch)

# Dibujar Salidas dinámicamente
zonas_salida_dibujos = []
for nombre, pos_salida in model.hitos.items():
    if 'Salida' in nombre:
        zs = Circle(pos_salida, RADIO_ZONA_SALIDA, color='lime', alpha=0.2, zorder=1)
        ax.add_patch(zs)
        ax.text(pos_salida[0], pos_salida[1], "EXIT", color='lime', ha='center', fontweight='bold', zorder=2)
        zonas_salida_dibujos.append(zs)

# Dibujar Zonas Prohibidas para Rolling (Para verificar el mapa)
for nombre, datos_espacio in model.espacios_navegables.items():
    locomotion = datos_espacio['atributos'].get('locomotion', [])
    # Si la zona NO tiene Rolling, la pintamos de rojo rayado
    if "Rolling" not in locomotion:
        poly = Polygon(datos_espacio['poligono'])
        x, y = poly.exterior.xy
        
        zona_patch = MplPolygon(list(zip(x, y)), closed=True, facecolor='red', edgecolor='darkred', alpha=0.3, hatch='//', zorder=1)
        ax.add_patch(zona_patch)
        
        cx, cy = datos_espacio['centroide']
        ax.text(cx, cy, "NO ROLLING", color='darkred', ha='center', fontweight='bold', fontsize=8, zorder=2)

# Dibujar Centros de las Habitaciones (Puntitos/Cruces Cyan)
for nombre, pos_centro in model.hitos.items():
    # Solo dibujamos la cruz si NO es una Salida, NO es una Puerta y NO es una Frontera
    if not any(palabra in nombre for palabra in ['Salida', 'Puerta', 'Frontera']):
        # Dibujamos una cruz en el centro
        ax.plot(pos_centro[0], pos_centro[1], marker='+', color='cyan', markersize=8, zorder=3)
        # Le ponemos el nombre en pequeñito para identificar la sala
        ax.text(pos_centro[0], pos_centro[1] + 0.5, "Centro", color='cyan', fontsize=7, ha='center', zorder=3)

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

circulos_fisicos = []
circulos_personales = []
lineas_rastro = [] 
lineas_intencion = [] 
artistas_fuego = []

# --- NUEVO: ASIGNACIÓN DE COLORES SEGÚN EL PERFIL ---
for agente in model.todos_los_agentes:
    # Elegir colores según el perfil
    if agente.perfil == "Rolling":
        color_agente = '#FF00FF' # Magenta
        color_rastro = 'magenta'
    elif agente.perfil == "Elderly":
        color_agente = '#00FF00' # Verde Lima
        color_rastro = 'lime'
    else: # Walking (Estándar)
        color_agente = '#0088FF' # Azulito
        color_rastro = 'yellow'  # Amarillo clásico

    # 1. Crear la línea del rastro
    lr, = ax.plot([], [], c=color_rastro, linewidth=1.0, alpha=0.6, zorder=9)
    lineas_rastro.append(lr)
    
    # 2. Crear la línea de intención (hacia dónde mira, la dejamos blanca)
    li, = ax.plot([], [], c='white', linestyle=':', linewidth=1.0, alpha=0.7, zorder=9)
    lineas_intencion.append(li)
    
    # 3. Crear el círculo personal (el aura)
    cp = Circle((0,0), RADIO_PERSONAL, facecolor=color_agente, alpha=0.2, zorder=10, visible=False)
    ax.add_patch(cp)
    circulos_personales.append(cp)
    
    # 4. Crear el círculo físico (el cuerpo duro)
    cf = Circle((0,0), RADIO_FISICO, facecolor=color_agente, edgecolor='black', zorder=11, visible=False)
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

# =====================================================================
# --- 7. EXPORTACIÓN Y RENDERIZADO ---
# =====================================================================
GUARDAR_GIF = True   # <--- PONLO A 'False' PARA DESACTIVAR LA GRABACIÓN LUEGO
ARCHIVO_GIF = os.path.join(BASE_DIR, "resultados", "evacuacion_demo.gif")

# Generador inteligente: Solo crea frames mientras queden agentes dentro
def generador_frames():
    frame = 0
    # Mientras los evacuados sean menos que el total de agentes, sigue grabando
    while model.evacuados < len(model.todos_los_agentes):
        yield frame
        frame += 1

# Creamos la animación pasándole el generador en lugar de un número fijo
ani = animation.FuncAnimation(
    fig, update, 
    frames=generador_frames, 
    init_func=init, 
    interval=30, 
    blit=True,
    save_count=2000  # Un límite de seguridad (aprox 1 minuto de vídeo a 30fps)
)

if GUARDAR_GIF:
    print(f"🎥 Grabando simulación en segundo plano... (Ten paciencia)")
    ani.save(ARCHIVO_GIF, writer='pillow', fps=30)
    print(f"✅ ¡Video GIF guardado con éxito en '{ARCHIVO_GIF}'!")
else:
    # Si GUARDAR_GIF es False, simplemente abre la ventana interactiva
    plt.show()

# AL TERMINAR (ya sea al cerrar la ventana o al acabar el GIF), EXPORTA LOS DATOS
model.datos.exportar_csv(nombre_salida=ruta_resultados)

