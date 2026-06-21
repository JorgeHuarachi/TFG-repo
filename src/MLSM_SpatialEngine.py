"""
================================================================================
MOTOR DE AUTORÍA Y PROCESAMIENTO ESPACIAL PARA SIMULACIÓN DE MULTITUDES
================================================================================
Descripción: 
Herramienta CAD basada en Python para la generación paramétrica de entornos 
interiores. Implementa Operaciones Booleanas 2D (Shapely) para la extracción 
de mallas de colisión física (CSG) y algoritmos de inferencia topológica para 
la generación automática de Modelos Espaciales Multicapa (MLSM).

Características principales:
- Exportación semántica alineada con el estándar OGC IndoorGML 2.0. (TO BE DONE)
- Extracción de grafos de navegación (Adyacencias, Habitaciones, Door-to-Door).
- Atributos de accesibilidad y locomoción integrados.
================================================================================
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path
import numpy as np
import json
import datetime
import os
import subprocess
import sys
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint, LineString as ShapelyLineString, box as ShapelyBox
from shapely.geometry.polygon import orient as orient_polygon
from shapely.ops import unary_union
from indoor_data_model import build_indoor_model, derive_wall_mass_from_snapshot
from indoor_authoring import BuildingAuthoringState, SnapshotHistory, detect_spaces
from indoor_authoring.connectors import create_elevator_connector, create_tile_chain_connector

# --- CONFIGURACIÓN ---
ANCHO = 30
ALTO = 20

class DiseñadorConectado:
    LINEAR_AUTHORING_TYPES = {
        "muro_exterior",
        "muro_interior",
        "puerta_simple",
        "puerta_doble",
        "salida",
        "ventana",
        "frontera_virtual",
    }
    POLYGON_AUTHORING_TYPES = {"hitos"}

    def __init__(self, ancho, alto, nombre_archivo="escenario_base"):
        self.nombre_archivo_base = nombre_archivo 
        self.ancho = ancho
        self.alto = alto
        
        # --- MEMORIA GEOMÉTRICA Y TOPOLÓGICA ---
        self.muros = []        # Lista principal de colisionadores físicos (CSG)
        self.agentes = []      # Spawns iniciales para la simulación
        self.hitos = {}        # Diccionario de nodos matemáticos (Nombre -> Coordenadas X,Y)
        self.hitos_bounds = [] # Guarda el polígono delimitador exacto de cada nodo para el grafo 
        self.authoring_state = BuildingAuthoringState(
            project_id=nombre_archivo,
            building_id=f"BUILDING_{nombre_archivo}",
        )
        self.history = SnapshotHistory(self.authoring_state)
        # Aclaracion conceptual: self.muros contiene elementos de autoria lineal
        # (muros, puertas, salidas y fronteras virtuales), no solo muros solidos.
        # self.hitos_bounds contiene footprints/poligonos de espacios, no boundaries MLSM/IndoorGML.
        # self.agentes contiene spawns geometricos, no agentes simulados completos.
        
        # Contadores autoincrementales para nombrar instancias automáticamente
        self.cont_hab = 1
        self.cont_muro = 1
        self.cont_puerta = 1
        self.cont_salida = 1
        
        # --- PARAMETRIZACIÓN BIM (Evitando Magic Numbers) ---
        # Definimos las propiedades físicas del entorno antes de dibujar.
        self.GROSORES = {
            'muro_exterior': 0.40,          # Muros de carga (gruesos)
            'muro_interior': 0.15,          # Tabiques (delgados)
            'puerta_simple': 0.15,
            'puerta_doble': 0.15,
            'ventana': 0.15,
            'salida': 0.20,                 # La salida ahora tiene grosor
            'frontera_virtual': 0.05        # Fina: Actúa como puente topológico, no como obstáculo físico
        }
        
        self.ANCHOS_PUERTA = {'puerta_simple': 0.9, 'puerta_doble': 1.8, 'salida': 2.0, 'ventana': 1.2}
        self.RADIO_AGENTE = 0.25 # 50cm de diámetro por defecto

        # --- MÁQUINA DE ESTADOS (STATE MACHINE) ---
        self.modo = 'muro_exterior'      # Herramienta seleccionada actualmente
        self.puntos_temp = None          # Guarda el primer clic (origen de la línea)
        self.puntos_zona_temp = []       # Acumula vértices (clics) para construir polígonos libres
        self.ortogonal = True            # Forzar dibujo en ángulos de 90 grados

        # MAGIA CAD: Variables para la restricción de dibujo de puertas
        self.vector_muro_temp = None     # Guarda el vector direccional del muro donde se pegará la puerta
        self.host_wall_metadata_temp = None
        self.authoring_line_metadata = {}
        self.connector_scope = "same_level"
        self.connector_entry_side = None
        self.connector_exit_side = None
        self.connector_side_focus = "entry"
        self.connector_tile_size = 1.0
        self.connector_tiles_temp = []
        self.connector_candidate_tile = None
        self.auto_visual_checks_on_export = os.environ.get("MLSM_AUTO_VISUAL_CHECKS", "").lower() in {
            "1",
            "true",
            "yes",
            "si",
        }

        # --- MEMORIA SEMÁNTICA (IndoorGML) ---
        self.propiedades_zonas = {}                     # Diccionario: Nombre -> {Atributos IndoorGML}
        self.locomotion_actual = ["Walking", "Rolling"] # Atributo asignado por defecto al dibujar

        # Visual
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        plt.subplots_adjust(bottom=0.22, top=0.90)
        self.texto_instrucciones = self.fig.text(
            0.03,
            0.03,
            "",
            ha='left',
            va='bottom',
            fontsize=8,
            color='black',
            bbox=dict(facecolor='white', edgecolor='#808080', alpha=0.9, pad=4),
        )
        self.ax.set_aspect('equal')
        self.configurar_lienzo()
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_move)
        # Sombra para hitos (Rectángulo)
        self.rect_temp = patches.Rectangle((0,0), 0, 0, alpha=0.5, color='magenta')
        self.ax.add_patch(self.rect_temp)
        # Sombra para Muros/Puertas (Polígono que soporta diagonales)
        self.poly_temp = patches.Polygon(np.zeros((4,2)), closed=True, alpha=0.5, color='gray')
        self.ax.add_patch(self.poly_temp)
        self.poly_temp.set_visible(False)
        # Línea roja directriz
        self.linea_temp, = self.ax.plot([], [], color='red', linestyle='-', linewidth=1.5, alpha=0.9, zorder=4)
        self.dibujar_interfaz()

    def get_authoring_elements(self):
        return self.muros

    def get_space_centroids(self):
        return self.hitos

    def get_space_footprints(self):
        return self.hitos_bounds

    def get_space_attributes(self):
        return self.propiedades_zonas

    def get_agent_spawns(self):
        return self.agentes

    def _sync_legacy_from_authoring_state(self):
        level = self.authoring_state.active_level
        self.muros = level.legacy_lines()
        self.hitos = level.legacy_space_centroids()
        self.hitos_bounds = level.legacy_space_bounds()
        self.propiedades_zonas = level.legacy_attributes()
        self.cont_hab = self.authoring_state.counters.get("space", self.cont_hab)
        self.cont_muro = self.authoring_state.counters.get("wall", self.cont_muro)
        self.cont_puerta = self.authoring_state.counters.get("opening", self.cont_puerta)

    def _checkpoint(self, label):
        self.history.checkpoint(label, self.authoring_state)

    def _restore_authoring_state(self, state):
        if state is None:
            print("No hay operacion disponible en historial.")
            return False
        self.authoring_state = state
        self._sync_legacy_from_authoring_state()
        self.limpiar_temporales_autoria(limpiar_poligono=True)
        return True

    def _next_counter(self, name):
        value = self.authoring_state.next_counter(name)
        self._sync_legacy_from_authoring_state()
        return value

    def is_wall_type(self, tipo):
        return tipo in ["muro_exterior", "muro_interior"]

    def is_door_type(self, tipo):
        return tipo in ["puerta_simple", "puerta_doble"]

    def is_window_type(self, tipo):
        return tipo in ["ventana", "ventana_practicable"]

    def is_exit_type(self, tipo):
        return tipo == "salida"

    def is_virtual_boundary_type(self, tipo):
        return tipo == "frontera_virtual"

    def is_opening_type(self, tipo):
        return self.is_door_type(tipo) or self.is_exit_type(tipo) or self.is_window_type(tipo)

    def is_solid_wall_type(self, tipo):
        return self.is_wall_type(tipo)

    def is_transfer_authoring_type(self, tipo):
        return self.is_door_type(tipo) or self.is_exit_type(tipo) or self.is_window_type(tipo)

    def is_non_solid_topology_type(self, tipo):
        return self.is_virtual_boundary_type(tipo)

    def limpiar_temporales_autoria(self, limpiar_poligono=True):
        self.puntos_temp = None
        if limpiar_poligono:
            self.puntos_zona_temp = []
        self.vector_muro_temp = None
        self.host_wall_metadata_temp = None
        self.connector_candidate_tile = None
        self.poly_temp.set_visible(False)
        self.linea_temp.set_data([], [])
        if limpiar_poligono:
            self.connector_tiles_temp = []
            self.connector_entry_side = None
            self.connector_exit_side = None
            self.connector_side_focus = "entry"

    def cambiar_modo(self, nuevo_modo):
        self.modo = nuevo_modo
        self.limpiar_temporales_autoria(limpiar_poligono=True)
        if nuevo_modo in {"escalera", "rampa", "ascensor"}:
            self.connector_entry_side = None
            self.connector_exit_side = None
            self.connector_side_focus = "entry"

    def configurar_lienzo(self):
        self.ax.set_xlim(-1, self.ancho)
        self.ax.set_ylim(-1, self.alto)
        self.ax.set_xticks(np.arange(0, self.ancho, 5))
        self.ax.set_yticks(np.arange(0, self.alto, 5))
        self.ax.set_xticks(np.arange(-0.5, self.ancho, 1), minor=True)
        self.ax.set_yticks(np.arange(-0.5, self.alto, 1), minor=True)
        self.ax.grid(which='minor', color='lightgray', linestyle='-', linewidth=0.5, alpha=0.5)
        self.ax.grid(which='major', color='gray', linestyle='-', linewidth=1, alpha=0.8)
        self.ax.invert_yaxis()

    def actualizar_titulo(self, error=None):
        color = 'black'
        tit = ""
        # --- AQUÍ AÑADIMOS LOS NUEVOS MODOS ---
        if self.modo.startswith('muro') or self.modo in ['puerta_simple', 'puerta_doble', 'salida', 'ventana', 'frontera_virtual']:
            tit = f"MODO: {self.modo.replace('_', ' ').upper()}"
        elif self.modo in ['columna', 'escalera', 'rampa', 'ascensor']:
            tit = f"MODO: {self.modo.upper()}"
        elif self.modo == 'agentes':
            tit = "MODO: AGENTES"
            color = 'blue'
        elif self.modo == 'hitos':
            tit = "MODO: HITOS (Auto-Relleno)"
            color = 'green'
        
        if error: tit, color = error, 'red'
        # Mostramos también el atributo IndoorGML actual
        estado_cad = f"Ortogonal: {'ON' if self.ortogonal else 'OFF'}"
        estado_indoor = f"Locomoción: {self.locomotion_actual}"
        level = self.authoring_state.active_level
        detectado = "detected" if level.detected_spaces and not level.geometry_dirty else "dirty"
        estado_nivel = f"Nivel: {level.id} ({detectado})"
        estado_connector = f"Scope: {self.connector_scope} lado:{self.connector_side_focus} entry:{self.connector_entry_side or '-'} exit:{self.connector_exit_side or '-'}"
        self.ax.set_title(f"{tit} | {estado_nivel} | {estado_cad} | {estado_indoor} | {estado_connector}", color=color, fontweight='bold', fontsize=10)
        self.texto_instrucciones.set_text(self.texto_ayuda_teclas())

    def texto_ayuda_teclas(self):
        return (
            "m exterior | n interior | p puerta | d doble | s salida | w ventana | v virtual | h espacio | c columna\n"
            "f detectar | t escalera | r rampa | l ascensor | b same/inter | tab entry/exit | flechas lado | backspace tile\n"
            "[ ] nivel | + nivel | 1 walk/roll | 2 walk | z undo | y redo | e export | x all adjacency | esc cancelar | ?/f1 ayuda"
        )

    def dibujar_ayuda_teclas(self):
        self.texto_instrucciones.set_text(self.texto_ayuda_teclas())

    def imprimir_ayuda_teclas(self):
        print("\nControles SpatialEngine:")
        print(self.texto_ayuda_teclas().replace("\n", " | "))

    def calcular_esquinas_muro(self, x1, y1, x2, y2, grosor):
        """Calcula los 4 vértices de un rectángulo a partir de una línea central y un grosor."""
        dx = x2 - x1
        dy = y2 - y1
        longitud = np.sqrt(dx**2 + dy**2)
        
        if longitud == 0: 
            return None
        
        # Vector normalizado perpendicular
        nx = -dy / longitud
        ny = dx / longitud
        
        mitad = grosor / 2.0
        
        # Calcular las 4 esquinas expandiendo desde la directriz
        p1 = (x1 + nx * mitad, y1 + ny * mitad)
        p2 = (x1 - nx * mitad, y1 - ny * mitad)
        p3 = (x2 - nx * mitad, y2 - ny * mitad)
        p4 = (x2 + nx * mitad, y2 + ny * mitad)
        
        return [p1, p2, p3, p4]

    def _is_opening_marker(self, nombre, attrs):
        categoria = str(attrs.get("categoria") or attrs.get("category") or "").lower()
        nom_lower = str(nombre).lower()
        return (
            categoria in {"door", "window", "transition", "virtualboundary"}
            or "puerta" in nom_lower
            or "salida" in nom_lower
            or "ventana" in nom_lower
            or "frontera" in nom_lower
        )

    def _opening_style(self, nombre, attrs):
        categoria = str(attrs.get("categoria") or attrs.get("category") or "").lower()
        nom_lower = str(nombre).lower()
        if categoria == "window" or "ventana" in nom_lower:
            return "#5dade2", "W", "--"
        if categoria == "transition" or "salida" in nom_lower:
            return "#e74c3c", "S", "-"
        if categoria == "virtualboundary" or "frontera" in nom_lower:
            return "#00bcd4", "V", ":"
        return "#f39c12", "D", "-"

    def _draw_opening_marker(self, nombre, coords, attrs):
        if not coords or len(coords) < 3:
            return
        color, etiqueta, estilo = self._opening_style(nombre, attrs)
        poly = patches.Polygon(
            coords,
            closed=True,
            facecolor=color,
            edgecolor="black",
            linewidth=1.2,
            linestyle=estilo,
            alpha=0.82,
            zorder=7,
        )
        self.ax.add_patch(poly)
        try:
            shp = ShapelyPolygon(coords)
            cx, cy = shp.representative_point().x, shp.representative_point().y
        except Exception:
            cx = sum(p[0] for p in coords) / len(coords)
            cy = sum(p[1] for p in coords) / len(coords)
        self.ax.text(
            cx,
            cy,
            etiqueta,
            ha="center",
            va="center",
            fontsize=7,
            fontweight="bold",
            color="black",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.2),
            zorder=8,
        )

    def _connector_candidate_is_valid(self, tile):
        if tile is None:
            return False
        tile_key = self._connector_tile_key(tile)
        if any(self._connector_tile_key(existing) == tile_key for existing in self.connector_tiles_temp):
            return False
        if not self.connector_tiles_temp:
            return True
        last_key = self._connector_tile_key(self.connector_tiles_temp[-1])
        return abs(tile_key[0] - last_key[0]) + abs(tile_key[1] - last_key[1]) == 1

    def _connector_tile_key(self, tile):
        size = self.connector_tile_size
        return (int(round(float(tile[0]) / size)), int(round(float(tile[1]) / size)))

    def _snap_connector_tile_origin(self, x, y):
        size = self.connector_tile_size
        snapped_x = float(np.floor(float(x) / size + 0.5) * size)
        snapped_y = float(np.floor(float(y) / size + 0.5) * size)
        return (snapped_x, snapped_y)

    def _normalized_connector_tiles(self, tiles):
        return [self._snap_connector_tile_origin(tile[0], tile[1]) for tile in tiles]

    def _connector_chain_error(self, tiles):
        seen = set()
        previous = None
        for index, tile in enumerate(tiles, start=1):
            key = self._connector_tile_key(tile)
            if key in seen:
                return f"tile {index} duplica otro tile"
            seen.add(key)
            if previous is not None:
                distance = abs(key[0] - previous[0]) + abs(key[1] - previous[1])
                if distance != 1:
                    return f"tile {index} no comparte lado con el tile {index - 1}"
            previous = key
        return None

    def _side_vector(self, side):
        return {
            "west": (-1, 0),
            "east": (1, 0),
            "north": (0, -1),
            "south": (0, 1),
        }.get(side, (0, 0))

    def _side_midpoint(self, tile, side):
        x, y = tile
        size = self.connector_tile_size
        return {
            "west": (x, y + size / 2),
            "east": (x + size, y + size / 2),
            "north": (x + size / 2, y),
            "south": (x + size / 2, y + size),
        }.get(side, (x + size / 2, y + size / 2))

    def _draw_rect_side_marker(self, bounds, side, label, color):
        if not side:
            return
        minx, miny, maxx, maxy = bounds
        midpoint_by_side = {
            "west": (minx, (miny + maxy) / 2),
            "east": (maxx, (miny + maxy) / 2),
            "north": ((minx + maxx) / 2, miny),
            "south": ((minx + maxx) / 2, maxy),
        }
        mx, my = midpoint_by_side.get(side, ((minx + maxx) / 2, (miny + maxy) / 2))
        vx, vy = self._side_vector(side)
        inward = label == "ENTRY"
        if inward:
            start = (mx + vx * 0.45, my + vy * 0.45)
            end = (mx - vx * 0.12, my - vy * 0.12)
        else:
            start = (mx - vx * 0.12, my - vy * 0.12)
            end = (mx + vx * 0.45, my + vy * 0.45)
        self.ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops=dict(arrowstyle="->", color=color, lw=2.0),
            zorder=9,
        )
        self.ax.text(
            start[0],
            start[1],
            label,
            ha="center",
            va="center",
            fontsize=5.5,
            fontweight="bold",
            color=color,
            bbox=dict(facecolor="white", edgecolor=color, alpha=0.85, pad=0.15),
            zorder=10,
        )

    def _draw_connector_side_marker(self, tile, side, label, color):
        if not side:
            return
        x, y = tile
        size = self.connector_tile_size
        self._draw_rect_side_marker((x, y, x + size, y + size), side, label, color)

    def _connector_footprint_from_tiles(self, tile_origins, tile_size=None):
        tile_size = float(tile_size or self.connector_tile_size)
        tiles = [ShapelyBox(x, y, x + tile_size, y + tile_size) for x, y in tile_origins]
        return unary_union(tiles) if tiles else None

    def _connector_side_coverages_for_footprint(self, footprint, open_sides):
        if footprint is None or footprint.is_empty:
            return []
        minx, miny, maxx, maxy = footprint.bounds
        thickness = 0.12
        side_boxes = {
            "north": ShapelyBox(minx, miny - thickness, maxx, miny),
            "south": ShapelyBox(minx, maxy, maxx, maxy + thickness),
            "east": ShapelyBox(maxx, miny, maxx + thickness, maxy),
            "west": ShapelyBox(minx - thickness, miny, minx, maxy),
        }
        pieces = [geom for side, geom in side_boxes.items() if side not in set(open_sides or [])]
        if not pieces:
            return []
        try:
            coverage = unary_union(pieces).difference(footprint)
        except Exception:
            coverage = unary_union(pieces)
        return self._iter_visual_polygons(coverage)

    def _draw_connector_coverages(self, coverages, zorder=5):
        for coverage in coverages:
            self._add_polygon_with_holes(
                coverage,
                facecolor="#7f8c8d",
                edgecolor="#34495e",
                linewidth=1.0,
                alpha=0.30,
                hatch="///",
                zorder=zorder,
            )

    def _draw_connector_draft_coverage(self):
        if self.modo not in {"escalera", "rampa"}:
            return
        tiles = list(self.connector_tiles_temp)
        if self.connector_candidate_tile is not None and self._connector_candidate_is_valid(self.connector_candidate_tile):
            tiles.append(self.connector_candidate_tile)
        tiles = self._normalized_connector_tiles(tiles)
        if not tiles:
            return
        footprint = self._connector_footprint_from_tiles(tiles)
        open_sides = [side for side in (self.connector_entry_side, self.connector_exit_side) if side]
        self._draw_connector_coverages(self._connector_side_coverages_for_footprint(footprint, open_sides), zorder=2.8)

    def _draw_committed_connectors(self, level_id):
        for connector in self.authoring_state.vertical_connectors:
            endpoints = [endpoint for endpoint in connector.endpoints if endpoint.level_id == level_id]
            if not endpoints:
                continue
            attrs = getattr(connector, "attributes", {}) or {}
            tile_size = float(attrs.get("tileSizeM", self.connector_tile_size) or self.connector_tile_size)
            tile_origins = attrs.get("tileOrigins") or []
            if connector.connector_type == "Stair":
                color = "#8e44ad"
                short_label = "STAIR"
            elif connector.connector_type == "Ramp":
                color = "#16a085"
                short_label = "RAMP"
            else:
                color = "#2e86c1"
                short_label = "ELEV"
            for index, origin in enumerate(tile_origins, start=1):
                tx, ty = float(origin[0]), float(origin[1])
                self.ax.add_patch(
                    patches.Rectangle(
                        (tx, ty),
                        tile_size,
                        tile_size,
                        facecolor=color,
                        edgecolor=color,
                        alpha=0.22,
                        linewidth=1.0,
                        zorder=5,
                    )
                )
                self.ax.text(
                    tx + tile_size / 2,
                    ty + tile_size / 2,
                    str(index),
                    ha="center",
                    va="center",
                    fontsize=6,
                    fontweight="bold",
                    color=color,
                    zorder=6,
                )
            for endpoint in endpoints:
                if not endpoint.footprint or len(endpoint.footprint) < 3:
                    continue
                coverage_polys = []
                for coverage in endpoint.attributes.get("sideCoverages", []):
                    try:
                        coverage_polys.append(ShapelyPolygon(coverage))
                    except Exception:
                        continue
                self._draw_connector_coverages(coverage_polys, zorder=4.8)
                self.ax.add_patch(
                    patches.Polygon(
                        endpoint.footprint,
                        closed=True,
                        facecolor=color,
                        edgecolor=color,
                        alpha=0.18,
                        linewidth=1.8,
                        zorder=5,
                    )
                )
                try:
                    shp = ShapelyPolygon(endpoint.footprint)
                    cx, cy = shp.representative_point().x, shp.representative_point().y
                    bounds = shp.bounds
                except Exception:
                    cx = sum(p[0] for p in endpoint.footprint) / len(endpoint.footprint)
                    cy = sum(p[1] for p in endpoint.footprint) / len(endpoint.footprint)
                    xs = [p[0] for p in endpoint.footprint]
                    ys = [p[1] for p in endpoint.footprint]
                    bounds = (min(xs), min(ys), max(xs), max(ys))
                self.ax.text(
                    cx,
                    cy,
                    short_label,
                    ha="center",
                    va="center",
                    fontsize=6,
                    fontweight="bold",
                    color=color,
                    bbox=dict(facecolor="white", edgecolor=color, alpha=0.78, pad=0.15),
                    zorder=8,
                )
                self._draw_rect_side_marker(bounds, endpoint.entry_side, "ENTRY", "#1e8449")
                self._draw_rect_side_marker(bounds, endpoint.exit_side, "EXIT", "#922b21")

    def _iter_visual_polygons(self, geometry):
        if geometry is None or geometry.is_empty:
            return []
        geoms = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
        return [geom for geom in geoms if isinstance(geom, ShapelyPolygon) and not geom.is_empty and geom.area > 1e-9]

    def _add_polygon_with_holes(self, polygon, **style):
        polygon = orient_polygon(polygon, sign=1.0)
        vertices = []
        codes = []

        def add_ring(coords):
            ring = list(coords)
            if len(ring) < 4:
                return
            vertices.extend(ring)
            codes.extend([Path.MOVETO] + [Path.LINETO] * (len(ring) - 2) + [Path.CLOSEPOLY])

        add_ring(polygon.exterior.coords)
        for interior in polygon.interiors:
            add_ring(interior.coords)
        if vertices:
            self.ax.add_patch(patches.PathPatch(Path(vertices, codes), **style))

    def _visual_wall_mass(self):
        try:
            result = derive_wall_mass_from_snapshot(self.build_authoring_snapshot(), self.authoring_state.active_level_id)
            wall_union = result.get("wallUnion")
            if wall_union is not None and not wall_union.is_empty:
                return wall_union
        except Exception:
            pass

        wall_polys = []
        opening_polys = []
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            if self.is_solid_wall_type(tipo):
                line = ShapelyLineString([(x1, y1), (x2, y2)])
                if line.is_empty or line.length <= 0:
                    continue
                thickness = self.GROSORES.get(tipo, 0.15)
                try:
                    # Square caps are visual-only: they fill wall junctions so the UI does
                    # not show false triangular slivers at corners or T contacts.
                    wall_polys.append(line.buffer(thickness / 2.0, cap_style=3, join_style=2))
                except Exception:
                    esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, thickness)
                    if esquinas:
                        wall_polys.append(ShapelyPolygon(esquinas))
            elif self.is_opening_type(tipo):
                thickness = self.GROSORES.get(tipo, 0.15)
                esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, thickness)
                if esquinas:
                    opening_polys.append(ShapelyPolygon(esquinas))

        if not wall_polys:
            return None
        try:
            wall_mass = unary_union(wall_polys)
            if opening_polys:
                wall_mass = wall_mass.difference(unary_union(opening_polys))
            return wall_mass.buffer(0)
        except Exception:
            return unary_union(wall_polys)

    def _draw_visual_wall_mass(self):
        wall_mass = self._visual_wall_mass()
        for polygon in self._iter_visual_polygons(wall_mass):
            self._add_polygon_with_holes(
                polygon,
                facecolor="#9aa0a6",
                edgecolor="black",
                linewidth=1.1,
                alpha=0.92,
                zorder=2,
            )

    def dibujar_interfaz(self, error=None):
        self.ax.clear()
        self.configurar_lienzo()
        self.actualizar_titulo(error)
        self.ax.add_patch(self.rect_temp)
        self.ax.add_patch(self.poly_temp) 
        self.ax.add_line(self.linea_temp)
        self.ax.add_patch(plt.Rectangle((-0.5, -0.5), self.ancho, self.alto, fill=False, edgecolor='black', linewidth=2))

        level = self.authoring_state.active_level
        for space in level.detected_spaces:
            if space.polygon:
                exterior = space.polygon[0]
                poly = patches.Polygon(exterior, closed=True, facecolor='#7fb3d5', edgecolor='#2874a6', alpha=0.18, zorder=1)
                self.ax.add_patch(poly)
                try:
                    shp = ShapelyPolygon(exterior)
                    self.ax.text(shp.representative_point().x, shp.representative_point().y, space.id, ha='center', va='center', fontsize=5, color='#1b4f72')
                except Exception:
                    pass

        self._draw_connector_draft_coverage()

        for idx, (tile_x, tile_y) in enumerate(self.connector_tiles_temp, start=1):
            self.ax.add_patch(
                patches.Rectangle(
                    (tile_x, tile_y),
                    self.connector_tile_size,
                    self.connector_tile_size,
                    facecolor='#a3e4d7',
                    edgecolor='#117a65',
                    alpha=0.45,
                    zorder=3,
                )
            )
            self.ax.text(
                tile_x + self.connector_tile_size / 2,
                tile_y + self.connector_tile_size / 2,
                str(idx),
                ha="center",
                va="center",
                fontsize=7,
                fontweight="bold",
                color="#0b5345",
                zorder=4,
            )
        if self.connector_tiles_temp:
            self._draw_connector_side_marker(self.connector_tiles_temp[0], self.connector_entry_side, "ENTRY", "#1e8449")
            self._draw_connector_side_marker(self.connector_tiles_temp[-1], self.connector_exit_side, "EXIT", "#922b21")
        if self.modo in {"escalera", "rampa"} and self.connector_candidate_tile is not None:
            valid_candidate = self._connector_candidate_is_valid(self.connector_candidate_tile)
            color = "#27ae60" if valid_candidate else "#c0392b"
            self.ax.add_patch(
                patches.Rectangle(
                    self.connector_candidate_tile,
                    self.connector_tile_size,
                    self.connector_tile_size,
                    facecolor=color,
                    edgecolor=color,
                    linestyle="--",
                    linewidth=1.6,
                    alpha=0.18 if valid_candidate else 0.28,
                    zorder=3,
                )
            )

        # Hitos
        # Hitos (Ahora Poligonales)
        for item in self.hitos_bounds:
            if len(item) == 2: # Nos aseguramos de que sea el nuevo formato (nombre, esquinas)
                nombre, coords = item[0], item[1]
                prop = getattr(self, 'propiedades_zonas', {}).get(nombre, {})
                if self._is_opening_marker(nombre, prop):
                    continue
                if "Salida" in nombre: c = 'red'
                elif "Ventana" in nombre: c = 'skyblue'
                elif "Columna" in nombre: c = 'gold'
                elif "Puerta" in nombre: c = 'orange'
                else: c = 'green'
                
                poly = patches.Polygon(coords, closed=True, facecolor=c, edgecolor=c, alpha=0.3)
                self.ax.add_patch(poly)
                
                cx, cy = self.hitos[nombre]

                # --- NUEVO: Extraer iniciales de la locomoción (W, R, S) ---
                locs = prop.get("locomotion", [])
                etiqueta_loc = "+".join([l[0] for l in locs]) # Convierte ["Walking", "Rolling"] en "W+R"
                texto_final = f"{nombre}\n[{etiqueta_loc}]" if etiqueta_loc else nombre

                self.ax.text(cx, cy, nombre, ha='center', va='center', fontsize=6, fontweight='bold', bbox=dict(facecolor='white', alpha=0.5, pad=0.1))

        # Dibujar muros como una masa visual unificada para evitar picos falsos en junctions.
        self._draw_visual_wall_mass()
        for muro in self.muros:
            id_muro, tipo, x1, y1, x2, y2 = muro
            
            if tipo in ['muro_exterior', 'muro_interior']:
                self.ax.plot([x1, x2], [y1, y2], color='red', linestyle='-', linewidth=1.0, zorder=3)

        for item in self.hitos_bounds:
            if len(item) == 2:
                nombre, coords = item[0], item[1]
                prop = getattr(self, 'propiedades_zonas', {}).get(nombre, {})
                if self._is_opening_marker(nombre, prop):
                    self._draw_opening_marker(nombre, coords, prop)

        self._draw_committed_connectors(level.id)

        # Agentes
        if self.agentes:
            ags = np.array(self.agentes)
            self.ax.scatter(ags[:,0], ags[:,1], c='blue', s=60, zorder=10, edgecolors='white')
        
        self.dibujar_ayuda_teclas()
        self.fig.canvas.draw()

    def es_punto_valido_inicio(self, x, y):
        if x < 0.8 or x > self.ancho - 0.8: return True
        if y < 0.8 or y > self.alto - 0.8: return True
        MARGEN = 0.8 
        for id_muro, tipo, mx1, my1, mx2, my2 in self.muros:
            if mx1 == mx2: # Vertical
                ymin, ymax = min(my1, my2), max(my1, my2)
                if abs(x - mx1) <= MARGEN and (ymin - MARGEN <= y <= ymax + MARGEN): return True
            else: # Horizontal
                xmin, xmax = min(mx1, mx2), max(mx1, mx2)
                if abs(y - my1) <= MARGEN and (xmin - MARGEN <= x <= xmax + MARGEN): return True
        return False
    
    def obtener_muro_cercano(self, px, py, tolerancia=0.5):
        """
        El 'Imán': Busca si el clic del usuario está cerca de un muro existente.
        Si es así, proyecta el punto matemáticamente sobre la línea del muro para garantizar
        que la puerta empiece exactamente en el eje central de la pared.
        """
        mejor_dist = float('inf')
        mejor_punto = None
        mejor_vector = None
        mejor_metadata = None
        
        # Iterar sobre todos los muros físicos construidos
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            if tipo.startswith('muro'):
                # Vector del muro (dirección de la pared)
                dx, dy = x2 - x1, y2 - y1
                # Longitud al cuadrado (para optimizar, evitamos la raíz cuadrada aquí)
                l2 = dx*dx + dy*dy 
                if l2 == 0: continue
                
                # Proyección matemática (Dot Product / Producto Escalar)
                # 't' es un porcentaje (de 0 a 1) que indica dónde cae el clic a lo largo del segmento.
                # max(0, min(1, ...)) fuerza a que la proyección no se salga por los extremos del muro.
                t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / l2))
                
                # Coordenadas exactas proyectadas sobre la línea directriz del muro
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                
                # Distancia euclidiana entre el clic del usuario y el punto proyectado
                dist = np.hypot(px - proj_x, py - proj_y)
                
                # Si está dentro de la tolerancia (0.5m), nos quedamos con este muro
                if dist < mejor_dist and dist <= tolerancia:
                    mejor_dist = dist
                    mejor_punto = (proj_x, proj_y)
                    
                    # Normalizamos el vector del muro (longitud = 1) para usarlo luego al arrastrar el ratón
                    length = np.sqrt(l2)
                    mejor_vector = (dx/length, dy/length)
                    mejor_metadata = {
                        "hostWallName": id_muro,
                        "hostWallType": tipo,
                        "hostWallThicknessM": self.GROSORES.get(tipo),
                        "hostWallRef": id_muro,
                        "projectedPoint": (float(proj_x), float(proj_y)),
                        "wallUnitVector": (float(mejor_vector[0]), float(mejor_vector[1])),
                    }

        # Devuelve la coordenada corregida y la dirección del riel del muro              
        if mejor_punto:
            return mejor_punto[0], mejor_punto[1], mejor_vector[0], mejor_vector[1], mejor_metadata
        return None

    def on_click(self, event):
        """
        EVENT LOOP (Cierre): Consolida las matemáticas temporales en estructuras de datos permanentes.
        """
        if event.inaxes != self.ax: return
        
        # Snap a 0.5 metros para mayor precisión en CAD y evitar huecos
        x = round(event.xdata * 2) / 2
        y = round(event.ydata * 2) / 2

        if self.modo == 'agentes' and event.button == 1:
            self.agentes.append((x, y))
            self.dibujar_interfaz()

        elif self.modo in self.LINEAR_AUTHORING_TYPES:
            if self.puntos_temp is None:
                # --- SNAP INICIAL: Obligar a empezar en un muro si es puerta/salida ---
                if self.is_transfer_authoring_type(self.modo):
                    snap = self.obtener_muro_cercano(x, y)
                    if snap:
                        self.puntos_temp = (snap[0], snap[1])
                        self.vector_muro_temp = (snap[2], snap[3])
                        self.host_wall_metadata_temp = snap[4] if len(snap) > 4 else None
                    else:
                        print("⛔ ERROR: Las puertas/salidas deben empezar SOBRE UN MURO.")
                        self.dibujar_interfaz("ERROR: Haz clic sobre un muro")
                else:
                    self.puntos_temp = (x, y) # Muros o fronteras empiezan donde sea
            else:
                x_ini, y_ini = self.puntos_temp
                
                # --- APLICAR RESTRICCIÓN FINAL ---
                if self.is_transfer_authoring_type(self.modo) and self.vector_muro_temp:
                    vx, vy = self.vector_muro_temp
                    dot = (x - x_ini) * vx + (y - y_ini) * vy
                    signo = 1 if dot >= 0 else -1
                    ancho_real = self.ANCHOS_PUERTA[self.modo]
                    x = x_ini + vx * ancho_real * signo
                    y = y_ini + vy * ancho_real * signo
                elif self.ortogonal:
                    if abs(x - x_ini) > abs(y - y_ini): y = y_ini
                    else: x = x_ini
                
                if x == x_ini and y == y_ini:
                    self.limpiar_temporales_autoria(limpiar_poligono=False)
                    self.dibujar_interfaz(); return
                
                # Guardado de la geometría
                es_puerta = self.is_transfer_authoring_type(self.modo) or self.is_virtual_boundary_type(self.modo)
                nombre = f"{self.modo.capitalize()}_{self.cont_puerta if es_puerta else self.cont_muro}"
                
                self._checkpoint(f"add_{self.modo}")
                self.muros.append((nombre, self.modo, x_ini, y_ini, x, y))
                
                if es_puerta:
                    if self.is_transfer_authoring_type(self.modo):
                        metadata = dict(self.host_wall_metadata_temp or {})
                        metadata["widthM"] = self.ANCHOS_PUERTA[self.modo]
                        metadata["thicknessM"] = metadata.get("hostWallThicknessM") or self.GROSORES[self.modo]
                        self.authoring_line_metadata[nombre] = metadata

                    cx, cy = x_ini + (x - x_ini)/2, y_ini + (y - y_ini)/2
                    self.hitos[nombre] = (cx, cy)
                    grosor_puerta = self.authoring_line_metadata.get(nombre, {}).get("thicknessM", self.GROSORES[self.modo])
                    esquinas_puerta = self.calcular_esquinas_muro(x_ini, y_ini, x, y, grosor_puerta)
                    self.hitos_bounds.append((nombre, esquinas_puerta))   
                    
                    # Semántica IndoorGML
                    clase_indoor = "AnchorSpace" if self.modo == 'salida' else "TransferSpace"
                    categoria = "VirtualBoundary" if self.modo == 'frontera_virtual' else ("Window" if self.modo == 'ventana' else ("Transition" if self.modo == 'salida' else "Door"))
                    attrs = {"clase_indoor": clase_indoor, "categoria": categoria, "locomotion": self.locomotion_actual, "footprint": esquinas_puerta}
                    if self.modo == 'ventana':
                        attrs.update({
                            "windowType": "fixed",
                            "defaultTraversable": False,
                            "scenarioControllable": True,
                            "sillHeightM": 0.9,
                        })
                    attrs.update(self.authoring_line_metadata.get(nombre, {}))
                    self.propiedades_zonas[nombre] = attrs
                    self.authoring_state.add_line_to_active(
                        nombre,
                        self.modo,
                        (x_ini, y_ini),
                        (x, y),
                        thickness_m=grosor_puerta,
                        width_m=self.ANCHOS_PUERTA.get(self.modo),
                        attributes=attrs,
                    )

                    self.cont_puerta += 1
                    self.authoring_state.counters["opening"] = self.cont_puerta
                    self.puntos_temp = None
                    self.vector_muro_temp = None
                    self.host_wall_metadata_temp = None
                else:
                    self.authoring_state.add_line_to_active(
                        nombre,
                        self.modo,
                        (x_ini, y_ini),
                        (x, y),
                        thickness_m=self.GROSORES.get(self.modo),
                        attributes={"locomotion": self.locomotion_actual},
                    )
                    self.cont_muro += 1
                    self.authoring_state.counters["wall"] = self.cont_muro
                    self.puntos_temp = (x, y) 

                self._sync_legacy_from_authoring_state()
                self.poly_temp.set_visible(False); self.linea_temp.set_data([], [])
                self.dibujar_interfaz()

        elif self.modo in {'escalera', 'rampa'} and event.button == 1:
            tile = self._snap_connector_tile_origin(event.xdata, event.ydata)
            if not self._connector_candidate_is_valid(tile):
                self.connector_candidate_tile = tile
                self.dibujar_interfaz("ERROR: tile no contiguo")
                print("El siguiente tile de escalera/rampa debe compartir lado con el anterior y no repetirse.")
                return
            self.connector_tiles_temp.append(tile)
            self.connector_candidate_tile = None
            print(f"Tile {len(self.connector_tiles_temp)} anadido. Pulsa Enter para cerrar el conector.")
            self.dibujar_interfaz()

        elif self.modo == 'ascensor' and event.button == 1:
            if self.puntos_temp is None:
                self.puntos_temp = (x, y)
            else:
                if not self.connector_entry_side or not self.connector_exit_side:
                    self.dibujar_interfaz("ERROR: falta entry/exit")
                    print("Selecciona entry y exit con flechas antes de cerrar el ascensor.")
                    return
                x0, y0 = self.puntos_temp
                coords = [(x0, y0), (x, y0), (x, y), (x0, y)]
                served = [self.authoring_state.active_level_id]
                if self.connector_scope == "inter_level":
                    levels = self.authoring_state.sorted_levels()
                    idx = next((i for i, level in enumerate(levels) if level.id == self.authoring_state.active_level_id), 0)
                    if idx + 1 < len(levels):
                        served.append(levels[idx + 1].id)
                self._checkpoint("add_elevator")
                create_elevator_connector(
                    self.authoring_state,
                    coords,
                    served,
                    entry_side=self.connector_entry_side,
                    exit_side=self.connector_exit_side,
                )
                self.limpiar_temporales_autoria(limpiar_poligono=True)
                self._sync_legacy_from_authoring_state()
                self.dibujar_interfaz()

        elif self.modo == 'columna' and event.button == 1:
            if self.puntos_temp is None:
                self.puntos_temp = (x, y)
            else:
                x0, y0 = self.puntos_temp
                if x == x0 or y == y0:
                    self.dibujar_interfaz("ERROR: columna necesita area")
                    return
                self._checkpoint("add_column")
                coords = [(x0, y0), (x, y0), (x, y), (x0, y)]
                nombre = f"Columna_{self.authoring_state.next_counter('column')}"
                poly_shapely = ShapelyPolygon(coords)
                attrs = {
                    "clase_indoor": "ObjectSpace",
                    "navigationType": "ObjectSpace",
                    "navigationClass": "NonNavigableSpace",
                    "categoria": "Column",
                    "category": "Column",
                    "function": "Column",
                    "traversable": False,
                }
                self.authoring_state.add_area_to_active(
                    nombre,
                    "columna",
                    coords,
                    centroid=(poly_shapely.centroid.x, poly_shapely.centroid.y),
                    attributes=attrs,
                )
                self.limpiar_temporales_autoria(limpiar_poligono=True)
                self._sync_legacy_from_authoring_state()
                self.dibujar_interfaz()

        # 1. GENERACIÓN DE HITOS POLIGONALES (Múltiples Clics)
        elif self.modo == 'hitos' and event.button == 1:
            # Si el clic actual coincide exactamente con el último clic (Doble Clic), cerramos la forma
            if len(self.puntos_zona_temp) > 0 and x == self.puntos_zona_temp[-1][0] and y == self.puntos_zona_temp[-1][1]:
                if len(self.puntos_zona_temp) >= 3:
                    self._checkpoint("add_manual_space")
                    nombre_final = f"Habitacion_{self.cont_hab}"
                    self.cont_hab += 1
                    # MAGIA SHAPELY: Usamos el polígono para calcular el Centro de Masa (Centroide)
                    # Esto asegura que la etiqueta del texto y el nodo del grafo queden perfectamente centrados
                    poly_shapely = ShapelyPolygon(self.puntos_zona_temp)
                    cx, cy = poly_shapely.centroid.x, poly_shapely.centroid.y
                    
                    self.hitos[nombre_final] = (cx, cy)
                    self.hitos_bounds.append((nombre_final, list(self.puntos_zona_temp)))
                    
                    # GUARDADO SEMÁNTICO INDOORGML
                    self.propiedades_zonas[nombre_final] = {
                        "clase_indoor": "NavigableSpace",
                        "categoria": "Room",
                        "locomotion": self.locomotion_actual # Herencia del estado global
                    }
                    self.authoring_state.add_area_to_active(
                        nombre_final,
                        "hitos",
                        list(self.puntos_zona_temp),
                        centroid=(cx, cy),
                        attributes=self.propiedades_zonas[nombre_final],
                    )
                    self.authoring_state.counters["space"] = self.cont_hab
                    self._sync_legacy_from_authoring_state()
                # Resetear memoria temporal para la próxima habitación
                self.puntos_zona_temp = []
                self.poly_temp.set_visible(False)
            else:
                # Si no es doble clic, añadimos el vértice al polígono en construcción
                self.puntos_zona_temp.append((x, y))
                
            self.dibujar_interfaz()
        

    def on_move(self, event):
        """
        EVENT LOOP (Cuerpo): Se ejecuta docenas de veces por segundo al mover el ratón.
        Su función principal es ofrecer Feedback Visual (la "sombra" del muro/puerta) 
        antes de que el usuario haga el clic definitivo.
        """
        # Ignorar si el ratón está fuera del lienzo de dibujo
        if event.inaxes != self.ax: return
        
        # Grid Snapping: Redondea las coordenadas a la media unidad (0.5m) 
        # Esto asegura que los muros encajen en una cuadrícula perfecta, evitando huecos.
        x_curr, y_curr = round(event.xdata * 2) / 2, round(event.ydata * 2) / 2

        # LÓGICA PARA HERRAMIENTAS DE GEOMETRÍA LINEAL (Muros, Puertas, Salidas)
        if self.modo in self.LINEAR_AUTHORING_TYPES:
            if self.puntos_temp is None: return # Si no hay un primer clic, no hay nada que proyectar
            x_start, y_start = self.puntos_temp
            
            # --- RESTRICCIÓN 1: Bloqueo Magnético (Rail Vector) ---
            # Si estamos dibujando una puerta, forzamos la coordenada actual a proyectarse
            # sobre el vector del muro anfitrión (self.vector_muro_temp).
            if self.is_transfer_authoring_type(self.modo) and self.vector_muro_temp:
                vx, vy = self.vector_muro_temp
                dot = (x_curr - x_start) * vx + (y_curr - y_start) * vy
                signo = 1 if dot >= 0 else -1
                
                # Anulamos la posición del ratón y forzamos la longitud paramétrica exacta (ej. 0.9m)
                ancho_real = self.ANCHOS_PUERTA[self.modo]
                x_curr = x_start + vx * ancho_real * signo
                y_curr = y_start + vy * ancho_real * signo

            # --- RESTRICCIÓN 2: Modo Ortogonal ---
            # Si no es una puerta (muros libres) y el modo ortogonal está activado ('o'),
            # aplanamos el diferencial menor para forzar ángulos rectos de 90º.
            elif self.ortogonal:
                if abs(x_curr - x_start) > abs(y_curr - y_start): y_curr = y_start
                else: x_curr = x_start

            # --- RENDERIZADO TEMPORAL ---
            # 1. Dibujamos la línea directriz (eje central)
            self.linea_temp.set_data([x_start, x_curr], [y_start, y_curr])
            
            # 2. Extruimos la línea para crear la sombra 2D del polígono
            grosor = self.GROSORES[self.modo]
            esquinas = self.calcular_esquinas_muro(x_start, y_start, x_curr, y_curr, grosor)
            if esquinas:
                self.poly_temp.set_xy(esquinas)
                self.poly_temp.set_visible(True)
                # Color feedback: Naranja para puertas, Gris para muros, Rojo para salidas
                c = 'gray' if self.modo == 'muro_exterior' else 'lightgray'
                if self.modo.startswith('puerta'): c = 'orange'
                elif self.modo == 'salida': c = 'red'
                elif self.modo == 'frontera_virtual': c = 'cyan'
                self.poly_temp.set_color(c)

        # LÓGICA PARA HERRAMIENTAS POLIGONALES LIBRES (Habitaciones)
        elif self.modo == 'hitos':
            # Dibuja la "banda elástica" (Rubber-band) desde el último vértice hasta el ratón actual
            if hasattr(self, 'puntos_zona_temp') and len(self.puntos_zona_temp) > 0:
                last_x, last_y = self.puntos_zona_temp[-1]
                self.linea_temp.set_data([last_x, x_curr], [last_y, y_curr])
                
                # Si tenemos al menos 2 clics, proyectamos cómo quedaría el polígono cerrado
                puntos_dibujo = self.puntos_zona_temp + [(x_curr, y_curr)]
                if len(puntos_dibujo) >= 3:
                    self.poly_temp.set_xy(puntos_dibujo)
                    self.poly_temp.set_visible(True)
                    self.poly_temp.set_color('green')
                else:
                    self.poly_temp.set_visible(False)
        elif self.modo in {'columna', 'ascensor'} and self.puntos_temp is not None:
            x0, y0 = self.puntos_temp
            coords = [(x0, y0), (x_curr, y0), (x_curr, y_curr), (x0, y_curr)]
            self.poly_temp.set_xy(coords)
            self.poly_temp.set_visible(True)
            self.poly_temp.set_color('gold' if self.modo == 'columna' else '#76d7c4')
        elif self.modo in {'escalera', 'rampa'}:
            self.connector_candidate_tile = self._snap_connector_tile_origin(event.xdata, event.ydata)
            self.poly_temp.set_visible(False)
            self.linea_temp.set_data([], [])
            
        # Pide a Matplotlib que redibuje el frame lo antes posible
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        key = (event.key or "").lower().strip()

        # --- NUEVOS MODOS DE MUROS ---
        if key == 'm': self.cambiar_modo('muro_exterior')
        elif key == 'n': self.cambiar_modo('muro_interior')
        elif key == 'p': self.cambiar_modo('puerta_simple')
        elif key == 'd': self.cambiar_modo('puerta_doble')
        elif key == 'w': self.cambiar_modo('ventana')
        elif key == 'o': self.ortogonal = not self.ortogonal # Alternar Diagonal
        # --- MODOS CLÁSICOS ---
        elif key == 'a': self.cambiar_modo('agentes')
        elif key == 'h': self.cambiar_modo('hitos')
        elif key == 'c': self.cambiar_modo('columna')
        elif key == 's': self.cambiar_modo('salida')
        elif key == 'v': self.cambiar_modo('frontera_virtual') # NUEVA
        elif key == 't': self.cambiar_modo('escalera')
        elif key == 'r': self.cambiar_modo('rampa')
        elif key == 'l': self.cambiar_modo('ascensor')
        elif key == 'b':
            self.connector_scope = "inter_level" if self.connector_scope == "same_level" else "same_level"
            print(f"Scope de conector: {self.connector_scope}")
        elif key == 'tab':
            self.connector_side_focus = "exit" if self.connector_side_focus == "entry" else "entry"
            print(f"Editando lado {self.connector_side_focus}.")
        elif key in {'left', 'right', 'up', 'down'}:
            side = {'left': 'west', 'right': 'east', 'up': 'north', 'down': 'south'}[key]
            if self.connector_side_focus == "entry":
                self.connector_entry_side = side
                self.connector_side_focus = "exit"
                print(f"Entry side seleccionado: {side}")
            else:
                self.connector_exit_side = side
                print(f"Exit side seleccionado: {side}")
        elif key in {'backspace', 'delete'} and self.modo in {'escalera', 'rampa'}:
            if self.connector_tiles_temp:
                removed = self.connector_tiles_temp.pop()
                print(f"Tile eliminado: {removed}")
            else:
                print("No hay tiles de conector que borrar.")
        # --- NUEVO: Etiquetas de Locomoción IndoorGML ---
        elif key == '1': self.locomotion_actual = ["Walking", "Rolling"] # Accesible universal
        elif key == '2': self.locomotion_actual = ["Walking"]            # No accesible (ej. terreno irregular)
        elif key == '3': self.locomotion_actual = ["Walking"]
        # --- LÓGICA DE DESHACER (ACTUALIZADA) ---
        elif key == 'z':
            self._restore_authoring_state(self.history.undo(self.authoring_state))
        elif key == 'y':
            self._restore_authoring_state(self.history.redo(self.authoring_state))

        elif key in {'+', '='}:
            self._checkpoint("add_level")
            level = self.authoring_state.add_level()
            self._sync_legacy_from_authoring_state()
            print(f"Nivel anadido y activo: {level.id}")
        elif key == '[':
            level = self.authoring_state.previous_level()
            self.limpiar_temporales_autoria(limpiar_poligono=True)
            self._sync_legacy_from_authoring_state()
            print(f"Nivel activo: {level.id}")
        elif key == ']':
            level = self.authoring_state.next_level()
            self.limpiar_temporales_autoria(limpiar_poligono=True)
            self._sync_legacy_from_authoring_state()
            print(f"Nivel activo: {level.id}")

        elif key == 'f':
            self._checkpoint("detect_spaces")
            result = detect_spaces(self.authoring_state, self.authoring_state.active_level_id)
            self._sync_legacy_from_authoring_state()
            if result.ok:
                print(f"{result.report.get('detectedSpaces', 0)} espacios detectados en {result.level_id}; autoria manual preservada.")
            else:
                print(f"ERROR deteccion {result.level_id}: {result.report.get('message')}")

        elif key in {'enter', 'return'} and self.modo in {'escalera', 'rampa'}:
            if not self.connector_entry_side or not self.connector_exit_side:
                self.dibujar_interfaz("ERROR: falta entry/exit")
                print("Selecciona entry y exit con flechas antes de cerrar el conector.")
                return
            if not self.connector_tiles_temp:
                self.dibujar_interfaz("ERROR: sin tiles")
                print("Dibuja al menos un tile para la escalera/rampa.")
                return
            connector_tiles = self._normalized_connector_tiles(self.connector_tiles_temp)
            chain_error = self._connector_chain_error(connector_tiles)
            if chain_error:
                self.connector_tiles_temp = connector_tiles
                self.dibujar_interfaz(f"ERROR: {chain_error}")
                print(f"No se puede cerrar la escalera/rampa: {chain_error}. Borra el ultimo tile con Backspace o cancela con Esc.")
                return
            connector_type = "Stair" if self.modo == "escalera" else "Ramp"
            target_level = None
            if self.connector_scope == "inter_level":
                levels = self.authoring_state.sorted_levels()
                idx = next((i for i, level in enumerate(levels) if level.id == self.authoring_state.active_level_id), 0)
                target_level = levels[idx + 1].id if idx + 1 < len(levels) else None
            self._checkpoint("add_vertical_connector")
            try:
                connector = create_tile_chain_connector(
                    self.authoring_state,
                    connector_type,
                    connector_tiles,
                    self.connector_entry_side,
                    self.connector_exit_side,
                    scope=self.connector_scope,
                    target_level_id=target_level,
                    tile_size_m=self.connector_tile_size,
                )
            except ValueError as exc:
                self.dibujar_interfaz(f"ERROR: {exc}")
                print(f"No se puede cerrar la escalera/rampa: {exc}. Borra el ultimo tile con Backspace o cancela con Esc.")
                return
            self.connector_tiles_temp = []
            self.connector_candidate_tile = None
            self.connector_entry_side = None
            self.connector_exit_side = None
            self.connector_side_focus = "entry"
            self._sync_legacy_from_authoring_state()
            print(f"Conector cerrado: {connector.id}. Puedes elegir otra herramienta o dibujar otro conector.")

        # --- SECCIÓN PARA EXPORTAR ---
        elif key == 'e':
            self.exportar_indoor_model(edge_mode="navigation")
            print("Guardado rapido Indoor Data Model completado.")

        elif key == 'x':
            self.exportar_indoor_model(edge_mode="all_adjacency")
            print("Guardado debug Indoor Data Model all_adjacency completado.")
        
        elif key == 'escape':
            self.limpiar_temporales_autoria(limpiar_poligono=True)
            print("Operacion actual cancelada.")

        elif key in {'?', 'f1'}:
            self.imprimir_ayuda_teclas()

        elif key == 'i':
            conexiones = self.calcular_conexiones()
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            nombre_final = f"{self.nombre_archivo_base}_IndoorGML_{timestamp}.json"
            self.exportar_indoor_gml(conexiones, nombre_final)
            print(f"🌍 Guardado en formato OGC IndoorGML 2.0 completado.")
        else:
            print(f"Tecla no asignada: {key or '<sin tecla>'}")
        self.dibujar_interfaz()

    def calcular_conexiones(self):
        """
        MOTOR DE INFERENCIA TOPOLÓGICA MULTICAPA (MLSM):
        Analiza las distancias y solapamientos de la geometría para inferir 3 grafos distintos.
        Implementa un blindaje anti-esquinas basado en el porcentaje de área interceptada.
        """
        conexiones_enriquecidas = []
        habitaciones = {}
        puertas = {}

        # 1. Clasificación Semántica (Sensible a Mayúsculas/Minúsculas)
        for item in self.hitos_bounds:
            if len(item) == 2:
                nombre, coords = item[0], item[1]
                if len(coords) >= 3:
                    nom_lower = nombre.lower()
                    # Salidas y Fronteras Virtuales se comportan topológicamente como puertas
                    if "puerta" in nom_lower or "salida" in nom_lower or "frontera" in nom_lower:
                        puertas[nombre] = ShapelyPolygon(coords)
                    else:
                        habitaciones[nombre] = ShapelyPolygon(coords)

        # 2. GRAFO MESO: Navegabilidad (Habitación <-> Puerta/Frontera/Salida)
        for nom_hab, poly_hab in habitaciones.items():
            hab_inflada = poly_hab.buffer(0.15) # Inflamos 15cm la habitación para que "toque" la pared
            for nom_pta, poly_pta in puertas.items():
                interseccion = hab_inflada.intersection(poly_pta)
                
                # FILTRO RELATIVO ANTI-ESQUINAS:
                # El solapamiento debe cubrir al menos el 30% del área total de la puerta.
                # Esto evita que una frontera virtual exterior conecte por error rozando una esquina.
                if interseccion.area > (poly_pta.area * 0.30):
                    conexiones_enriquecidas.append({
                        "origen": nom_hab, "destino": nom_pta, 
                        "tipo": "navegable_puerta", "color": "cyan", "estilo": "-"
                    })

        # 3. GRAFO MICRO (Door-to-Door): Navegación avanzada intraroom
        for nom_hab, poly_hab in habitaciones.items():
            hab_inflada = poly_hab.buffer(0.15)
            
            # Filtramos qué puertas pertenecen realmente a esta habitación usando la regla del 30%
            puertas_en_hab = []
            for nom_pta, poly_pta in puertas.items():
                interseccion = hab_inflada.intersection(poly_pta)
                if interseccion.area > (poly_pta.area * 0.30):
                    puertas_en_hab.append(nom_pta)
            
            # Permutación completa: Conectamos todas las puertas de la habitación entre sí
            for i in range(len(puertas_en_hab)):
                for j in range(i + 1, len(puertas_en_hab)):
                    conexiones_enriquecidas.append({
                        "origen": puertas_en_hab[i], "destino": puertas_en_hab[j], 
                        "tipo": "door_to_door", "contexto": nom_hab, "color": "magenta", "estilo": ":"
                    })

        # 4. GRAFO MACRO (Adyacencias Físicas): Navegación de alto nivel (Habitación <-> Habitación)
        nombres_hab = list(habitaciones.keys())
        for i in range(len(nombres_hab)):
            for j in range(i + 1, len(nombres_hab)):
                poly_a = habitaciones[nombres_hab[i]]
                poly_b = habitaciones[nombres_hab[j]]
                
                interseccion = poly_a.buffer(0.15).intersection(poly_b)
                # Filtro Absoluto: Exigimos un área > 0.05m² para asegurar que comparten un segmento de muro real
                if interseccion.area > 0.05:
                    conexiones_enriquecidas.append({
                        "origen": nombres_hab[i], "destino": nombres_hab[j], 
                        "tipo": "adyacencia_fisica", "color": "gold", "estilo": "--"
                    })

        return conexiones_enriquecidas
    
    def procesar_geometria_booleana(self):
        """
        MOTOR CSG (Geometría Constructiva de Sólidos):
        Usa la librería matemática Shapely para restar el volumen físico de las puertas 
        a los muros sólidos. Esto evita que los agentes colisionen con paredes invisibles 
        al intentar cruzar un umbral.
        """
        poligonos_corte = []
        datos_aperturas = []
        
        # 1. Agrupación de Geometría Sustractiva (Las "Herramientas de Corte")
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            if self.is_opening_type(tipo):
                grosor = self.GROSORES[tipo]
                esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, grosor)
                if esquinas:
                    poly = ShapelyPolygon(esquinas)
                    poligonos_corte.append(poly)
                    datos_aperturas.append((id_muro, tipo, esquinas))
                    
        # unary_union fusiona todas las puertas superpuestas en un único "Súper-Polígono"
        # Optimizando masivamente la operación matemática de resta posterior.
        todas_las_aperturas = unary_union(poligonos_corte) if poligonos_corte else ShapelyPolygon()
        
        muros_recortados = []
        
        # 2. Recorte del Sólido Base (Muros)
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            if not self.is_solid_wall_type(tipo): continue # Puertas/salidas cortan; frontera_virtual no es solido.
            
            grosor = self.GROSORES[tipo]
            esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, grosor)
            if not esquinas: continue
            
            poly_muro = ShapelyPolygon(esquinas)
            
            # MAGIA SHAPELY: Operación de Diferencia Booleana (Muro - Puertas)
            muro_final = poly_muro.difference(todas_las_aperturas)
            
            if muro_final.is_empty: continue # El muro fue borrado por completo por una puerta enorme
            
            # Gestión de Fragmentación: Si una puerta parte un muro exactamente por la mitad,
            # Shapely devuelve un 'MultiPolygon' (dos trozos desconectados).
            geometrias = muro_final.geoms if hasattr(muro_final, 'geoms') else [muro_final]
            
            for i, geom in enumerate(geometrias):
                # Extraemos las coordenadas matemáticas resultantes y quitamos el último punto 
                # (redundante) para que el formato GeoJSON/Simulador lo procese correctamente.
                coords = list(geom.exterior.coords)[:-1] 
                muros_recortados.append((f"{id_muro}_part{i + 1:03d}", tipo, coords))
                
        return muros_recortados, datos_aperturas

    def _v2_point(self, x, y):
        return {"type": "Point", "coordinates": [float(x), float(y)]}

    def _v2_linestring(self, coords):
        return {
            "type": "LineString",
            "coordinates": [[float(x), float(y)] for x, y in coords]
        }

    def _v2_polygon(self, coords):
        ring = [[float(x), float(y)] for x, y in coords]
        if ring and ring[0] != ring[-1]:
            ring.append(list(ring[0]))
        return {"type": "Polygon", "coordinates": [ring]}

    def _v2_normalizar_id(self, prefix, nombre):
        texto = str(nombre).strip().upper()
        normalizado = []
        for char in texto:
            normalizado.append(char if char.isalnum() else "_")
        compacto = "_".join(parte for parte in "".join(normalizado).split("_") if parte)
        return f"{prefix}_{compacto}" if compacto else prefix

    def _v2_locomotion(self, valores):
        mapping = {"Walking": "walking", "Rolling": "rolling", "Step": "step"}
        normalizados = []
        for valor in valores or []:
            normalizado = mapping.get(valor, str(valor).strip().lower())
            if normalizado and normalizado not in normalizados:
                normalizados.append(normalizado)
        return normalizados

    def _v2_is_exit_name(self, nombre):
        return "salida" in str(nombre).lower()

    def _v2_is_virtual_name(self, nombre):
        return "frontera" in str(nombre).lower()

    def _v2_is_door_name(self, nombre):
        lower = str(nombre).lower()
        return "puerta" in lower or self._v2_is_exit_name(nombre)

    def _v2_space_type_and_category(self, nombre, atributos):
        lower = str(nombre).lower()
        clase = atributos.get("clase_indoor", "")
        categoria_original = str(atributos.get("categoria", "")).lower()

        if "salida" in lower:
            return "exit_space", "exit", "ExitSpace"
        if "frontera" in lower:
            return "transfer_space", "virtual_boundary", "VirtualBoundary"
        if "puerta" in lower or categoria_original == "door":
            return "transfer_space", "door_space", "ConnectionSpace"
        if clase == "TransferSpace":
            return "transfer_space", categoria_original or "transfer_space", "ConnectionSpace"
        if clase == "AnchorSpace":
            return "exit_space", "exit", "ExitSpace"
        return "navigable_space", categoria_original or "room", "General"

    def _v2_catalogs(self):
        return {
            "wall_types": [
                {
                    "catalog_id": "WALL_EXTERIOR_40CM",
                    "element_type": "wall",
                    "wall_type": "exterior",
                    "default_thickness_m": self.GROSORES["muro_exterior"],
                    "default_height_m": 3.0,
                    "default_material": "generic",
                    "description": "Muro exterior exportado desde SpatialEngine"
                },
                {
                    "catalog_id": "WALL_INTERIOR_15CM",
                    "element_type": "wall",
                    "wall_type": "interior",
                    "default_thickness_m": self.GROSORES["muro_interior"],
                    "default_height_m": 3.0,
                    "default_material": "generic",
                    "description": "Muro interior exportado desde SpatialEngine"
                }
            ],
            "door_types": [
                {
                    "catalog_id": "DOOR_SINGLE_90CM",
                    "element_type": "door",
                    "door_type": "single",
                    "default_width_m": self.ANCHOS_PUERTA["puerta_simple"],
                    "default_height_m": 2.1,
                    "description": "Puerta simple exportada desde SpatialEngine"
                },
                {
                    "catalog_id": "DOOR_DOUBLE_180CM",
                    "element_type": "door",
                    "door_type": "double",
                    "default_width_m": self.ANCHOS_PUERTA["puerta_doble"],
                    "default_height_m": 2.1,
                    "description": "Puerta doble exportada desde SpatialEngine"
                },
                {
                    "catalog_id": "DOOR_EXIT_200CM",
                    "element_type": "door",
                    "door_type": "emergency_exit",
                    "default_width_m": self.ANCHOS_PUERTA["salida"],
                    "default_height_m": 2.1,
                    "description": "Salida exportada como puerta de emergencia"
                }
            ],
            "window_types": [],
            "column_types": [],
            "space_types": [
                {
                    "catalog_id": "SPACE_NAVIGABLE",
                    "space_type": "navigable_space",
                    "category": "room",
                    "default_function": "General",
                    "default_locomotion": ["walking", "rolling"],
                    "description": "Espacio navegable exportado desde hitos"
                },
                {
                    "catalog_id": "SPACE_DOOR_TRANSFER",
                    "space_type": "transfer_space",
                    "category": "door_space",
                    "default_function": "ConnectionSpace",
                    "default_locomotion": ["walking", "rolling"],
                    "description": "Espacio de transferencia asociado a puerta"
                },
                {
                    "catalog_id": "SPACE_EXIT",
                    "space_type": "exit_space",
                    "category": "exit",
                    "default_function": "ExitSpace",
                    "default_locomotion": ["walking", "rolling"],
                    "description": "Espacio de salida"
                },
                {
                    "catalog_id": "SPACE_VIRTUAL_BOUNDARY",
                    "space_type": "transfer_space",
                    "category": "virtual_boundary",
                    "default_function": "VirtualBoundary",
                    "default_locomotion": ["walking", "rolling"],
                    "description": "Frontera virtual topologica"
                }
            ],
            "beacon_types": [],
            "hazard_types": [],
            "stair_types": [],
            "ramp_types": [],
            "elevator_types": []
        }

    def _v2_physical_catalog_ref(self, tipo):
        if tipo == "muro_exterior":
            return "WALL_EXTERIOR_40CM"
        if tipo == "muro_interior":
            return "WALL_INTERIOR_15CM"
        if tipo == "puerta_doble":
            return "DOOR_DOUBLE_180CM"
        if self.is_exit_type(tipo):
            return "DOOR_EXIT_200CM"
        return "DOOR_SINGLE_90CM"

    def _v2_physical_elements(self):
        elementos = []
        element_id_map = {}
        authoring_elements = self.get_authoring_elements()

        for nombre, tipo, x1, y1, x2, y2 in authoring_elements:
            if self.is_virtual_boundary_type(tipo):
                # En v2 la frontera virtual es topologica; no se exporta como muro solido.
                continue

            if self.is_wall_type(tipo):
                element_type = "wall"
            elif self.is_door_type(tipo) or self.is_exit_type(tipo):
                element_type = "door"
            else:
                continue

            grosor = self.GROSORES.get(tipo)
            esquinas = self.calcular_esquinas_muro(x1, y1, x2, y2, grosor)
            if not esquinas:
                continue

            element_id = self._v2_normalizar_id("PE", nombre)
            attrs = {
                "original_type": tipo,
                "thickness_m": grosor,
                "is_virtual": False
            }
            if tipo in self.ANCHOS_PUERTA:
                attrs["width_m"] = self.ANCHOS_PUERTA[tipo]
            if self.is_exit_type(tipo):
                attrs["is_exit"] = True
                attrs["connector_type"] = "emergency_exit"

            elementos.append({
                "element_id": element_id,
                "level_id": "LEVEL_00",
                "element_type": element_type,
                "catalog_ref": self._v2_physical_catalog_ref(tipo),
                "centerline_2d": self._v2_linestring([(x1, y1), (x2, y2)]),
                "derived_footprint_2d": self._v2_polygon(esquinas),
                "label": nombre,
                "attributes": attrs
            })
            element_id_map[nombre] = element_id

        return elementos, element_id_map

    def _v2_spaces(self, element_id_map):
        spaces = []
        space_id_map = {}
        space_centroids = self.get_space_centroids()
        # self.hitos_bounds stores space footprints, not IndoorGML/MLSM boundaries.
        space_footprints = self.get_space_footprints()
        space_attributes = self.get_space_attributes()

        for nombre, coords in space_footprints:
            if nombre not in space_centroids or not coords:
                continue

            atributos_originales = space_attributes.get(nombre, {})
            space_type, category, function = self._v2_space_type_and_category(nombre, atributos_originales)
            cx, cy = space_centroids[nombre]
            locomotion_original = atributos_originales.get("locomotion", [])
            locomotion_v2 = self._v2_locomotion(locomotion_original)
            space_id = self._v2_normalizar_id("SPACE", nombre)

            attrs = dict(atributos_originales)
            attrs["locomotion_original"] = locomotion_original
            attrs["locomotion"] = locomotion_v2
            attrs["source"] = "spatialengine_hitos_bounds"

            space = {
                "space_id": space_id,
                "level_id": "LEVEL_00",
                "space_type": space_type,
                "name": nombre,
                "category": category,
                "function": function,
                "poi": False,
                "centroid_2d": self._v2_point(cx, cy),
                "footprint_2d": self._v2_polygon(coords),
                "attributes": attrs
            }

            if nombre in element_id_map:
                space["physical_element_ref"] = element_id_map[nombre]

            spaces.append(space)
            space_id_map[nombre] = space_id

        return spaces, space_id_map

    def _v2_space_polygon_by_name(self, nombre):
        # self.hitos_bounds stores space footprints, not MLSM boundaries.
        for space_name, coords in self.get_space_footprints():
            if space_name != nombre or not coords:
                continue
            try:
                poly = ShapelyPolygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_empty or poly.area <= 0:
                    return None
                return poly
            except Exception:
                return None
        return None

    def _v2_line_segments_from_coords(self, coords):
        lines = []
        points = list(coords)
        for start, end in zip(points, points[1:]):
            line = ShapelyLineString([start, end])
            if not line.is_empty and line.length > 1e-9:
                lines.append(line)
        return lines

    def _v2_extract_lines_from_geometry(self, geom):
        if geom is None or geom.is_empty:
            return []

        geom_type = geom.geom_type
        if geom_type == "LineString":
            return [geom] if geom.length > 1e-9 else []
        if geom_type == "LinearRing":
            return self._v2_line_segments_from_coords(geom.coords)
        if geom_type == "MultiLineString":
            lines = []
            for part in geom.geoms:
                lines.extend(self._v2_extract_lines_from_geometry(part))
            return lines
        if geom_type == "Polygon":
            return self._v2_line_segments_from_coords(geom.exterior.coords)
        if geom_type == "MultiPolygon":
            lines = []
            for part in geom.geoms:
                lines.extend(self._v2_extract_lines_from_geometry(part))
            return lines
        if geom_type == "GeometryCollection":
            lines = []
            for part in geom.geoms:
                lines.extend(self._v2_extract_lines_from_geometry(part))
            return lines

        return []

    def _v2_longest_line(self, lines):
        useful_lines = [line for line in lines if line is not None and not line.is_empty and line.length > 1e-9]
        if not useful_lines:
            return None
        return max(useful_lines, key=lambda line: line.length)

    def _v2_boundary_centroid_fallback(self, origen, destino):
        space_centroids = self.get_space_centroids()
        return self._v2_linestring([space_centroids[origen], space_centroids[destino]]), True, "centroid_fallback"

    def _v2_boundary_geometry_between(self, origen, destino):
        poly_a = self._v2_space_polygon_by_name(origen)
        poly_b = self._v2_space_polygon_by_name(destino)

        if poly_a is None or poly_b is None:
            return self._v2_boundary_centroid_fallback(origen, destino)

        try:
            boundary_contact = poly_a.boundary.intersection(poly_b.boundary)
            line = self._v2_longest_line(self._v2_extract_lines_from_geometry(boundary_contact))
            if line is None:
                overlap = poly_a.intersection(poly_b)
                line = self._v2_longest_line(self._v2_extract_lines_from_geometry(overlap))
            if line is None:
                return self._v2_boundary_centroid_fallback(origen, destino)
            return self._v2_linestring(list(line.coords)), False, "geometry_contact"
        except Exception:
            return self._v2_boundary_centroid_fallback(origen, destino)

    def _v2_find_space_for_point(self, x, y, spaces):
        point = ShapelyPoint(x, y)
        fallback = spaces[0]["space_id"] if spaces else "UNKNOWN_SPACE"

        for space in spaces:
            coords = space.get("footprint_2d", {}).get("coordinates", [[]])[0]
            if len(coords) < 4:
                continue
            poly = ShapelyPolygon(coords)
            if poly.contains(point) or poly.touches(point):
                return space["space_id"], True

        return fallback, False

    def _v2_agent_spawns(self, spaces):
        spawns = []
        agent_positions = self.get_agent_spawns()

        for index, (x, y) in enumerate(agent_positions, start=1):
            space_ref, inferred = self._v2_find_space_for_point(x, y, spaces)
            spawns.append({
                "spawn_id": f"SPAWN_{index:03d}",
                "level_id": "LEVEL_00",
                "space_ref": space_ref,
                "position": self._v2_point(x, y),
                "capacity": 1,
                "allowed_profiles": ["walking", "rolling"],
                "attributes": {
                    "space_ref_inferred": inferred
                }
            })

        return spawns

    def _v2_boundary_type_for_connection(self, origen, destino):
        if self._v2_is_virtual_name(origen) or self._v2_is_virtual_name(destino):
            return "special_boundary"
        return "navigable_boundary"

    def _v2_boundaries_navegables(self, conexiones, space_id_map):
        boundaries = []
        boundary_id_map = {}

        for index, conn in enumerate(conexiones, start=1):
            if conn.get("tipo") != "navegable_puerta":
                continue

            origen = conn.get("origen")
            destino = conn.get("destino")
            if origen not in space_id_map or destino not in space_id_map:
                continue
            space_centroids = self.get_space_centroids()
            if origen not in space_centroids or destino not in space_centroids:
                continue

            boundary_id = f"BOUNDARY_NAV_{index:03d}"
            geometry_2d, approximate_geometry, derivation_source = self._v2_boundary_geometry_between(origen, destino)
            boundary = {
                "boundary_id": boundary_id,
                "level_id": "LEVEL_00",
                "boundary_type": self._v2_boundary_type_for_connection(origen, destino),
                "source_space_id": space_id_map[origen],
                "target_space_id": space_id_map[destino],
                "source_ref": {
                    "entity_type": "space",
                    "entity_id": space_id_map[origen]
                },
                "target_ref": {
                    "entity_type": "space",
                    "entity_id": space_id_map[destino]
                },
                "geometry_2d": geometry_2d,
                "attributes": {
                    "traversable": True,
                    "bidirectional": True,
                    "derived": True,
                    "approximate_geometry": approximate_geometry,
                    "derivation_source": derivation_source
                }
            }
            boundaries.append(boundary)
            boundary_id_map[(origen, destino)] = boundary_id
            boundary_id_map[(destino, origen)] = boundary_id

        return boundaries, boundary_id_map

    def _v2_distance_between(self, origen, destino):
        space_centroids = self.get_space_centroids()
        if origen not in space_centroids or destino not in space_centroids:
            return None
        x1, y1 = space_centroids[origen]
        x2, y2 = space_centroids[destino]
        return float(np.hypot(x2 - x1, y2 - y1))

    def _v2_connection_profiles(self, origen, destino):
        space_attributes = self.get_space_attributes()
        props_origen = space_attributes.get(origen, {})
        props_destino = space_attributes.get(destino, {})
        loc_origen = self._v2_locomotion(props_origen.get("locomotion", []))
        loc_destino = self._v2_locomotion(props_destino.get("locomotion", []))

        if loc_origen and loc_destino:
            comunes = [loc for loc in loc_origen if loc in loc_destino]
            return comunes or ["walking"]
        return loc_origen or loc_destino or ["walking"]

    def _v2_node_type_for_name(self, nombre):
        if self._v2_is_exit_name(nombre):
            return "exit_space"
        if self._v2_is_virtual_name(nombre):
            return "virtual_boundary"
        if "puerta" in str(nombre).lower():
            return "door_space"
        return "space"

    def _v2_connector_type_for_connection(self, origen, destino):
        if self._v2_is_exit_name(origen) or self._v2_is_exit_name(destino):
            return "emergency_exit"
        if self._v2_is_virtual_name(origen) or self._v2_is_virtual_name(destino):
            return "virtual_boundary"
        return "door_passage"

    def _v2_through_space_name(self, origen, destino):
        for nombre in (origen, destino):
            if self._v2_is_door_name(nombre) or self._v2_is_virtual_name(nombre):
                return nombre
        return None

    def _v2_add_graph_node(self, nodes, node_ids, graph_prefix, nombre, space_id_map):
        if nombre not in space_id_map:
            return None
        if nombre not in node_ids:
            node_id = self._v2_normalizar_id(graph_prefix, nombre)
            cx, cy = self.get_space_centroids().get(nombre, (0, 0))
            nodes.append({
                "node_id": node_id,
                "space_ref": space_id_map[nombre],
                "node_type": self._v2_node_type_for_name(nombre),
                "level_id": "LEVEL_00",
                "position": self._v2_point(cx, cy)
            })
            node_ids[nombre] = node_id
        return node_ids[nombre]

    def _v2_graphs(self, conexiones, spaces, physical_elements, boundaries, space_id_map, element_id_map, boundary_id_map):
        graph_defs = {
            "adyacencia_fisica": {
                "key": "adjacency_graph",
                "graph_id": "GRAPH_ADJ_LEVEL_00",
                "node_prefix": "N_ADJ",
                "edge_prefix": "E_ADJ",
                "purpose": "Contactos fisicos/topologicos derivados de conexiones adyacencia_fisica."
            },
            "navegable_puerta": {
                "key": "connectivity_graph",
                "graph_id": "GRAPH_CONN_LEVEL_00",
                "node_prefix": "N_CONN",
                "edge_prefix": "E_CONN",
                "purpose": "Conexiones atravesables derivadas de conexiones navegable_puerta."
            },
            "door_to_door": {
                "key": "door_to_door_graph",
                "graph_id": "GRAPH_D2D_LEVEL_00",
                "node_prefix": "N_D2D",
                "edge_prefix": "E_D2D",
                "purpose": "Grafo principal de evacuacion entre puertas, salidas y pasos."
            }
        }

        graphs = {}
        for conn_type, config in graph_defs.items():
            nodes = []
            node_ids = {}
            edges = []
            edge_index = 1
            space_centroids = self.get_space_centroids()

            for conn in conexiones:
                if conn.get("tipo") != conn_type:
                    continue

                origen = conn.get("origen")
                destino = conn.get("destino")
                if origen not in space_id_map or destino not in space_id_map:
                    continue
                if origen not in space_centroids or destino not in space_centroids:
                    continue

                source_node_id = self._v2_add_graph_node(nodes, node_ids, config["node_prefix"], origen, space_id_map)
                target_node_id = self._v2_add_graph_node(nodes, node_ids, config["node_prefix"], destino, space_id_map)
                if not source_node_id or not target_node_id:
                    continue

                edge = {
                    "edge_id": f"{config['edge_prefix']}_{edge_index:03d}",
                    "source_node_id": source_node_id,
                    "target_node_id": target_node_id,
                    "geometry_2d": self._v2_linestring([space_centroids[origen], space_centroids[destino]])
                }

                distance = self._v2_distance_between(origen, destino)
                if distance is not None:
                    edge["distance_m"] = distance

                if conn_type == "adyacencia_fisica":
                    edge["relationship_type"] = "physical_adjacency"
                    edge["traversable"] = False

                elif conn_type == "navegable_puerta":
                    through_name = self._v2_through_space_name(origen, destino)
                    edge["connector_type"] = self._v2_connector_type_for_connection(origen, destino)
                    edge["boundary_ref"] = boundary_id_map.get((origen, destino))
                    edge["allowed_flows"] = ["pedestrian"]
                    if edge["connector_type"] == "emergency_exit":
                        edge["allowed_flows"].append("emergency_exit")
                    edge["allowed_profiles"] = self._v2_connection_profiles(origen, destino)
                    edge["base_weight"] = distance if distance is not None else 1.0
                    edge["traversable"] = True
                    if through_name:
                        edge["through_space_id"] = space_id_map.get(through_name)
                        if through_name in element_id_map:
                            edge["through_element_id"] = element_id_map[through_name]
                        if self._v2_is_door_name(through_name):
                            width_key = "salida" if self._v2_is_exit_name(through_name) else "puerta_simple"
                            edge["width_m"] = self.ANCHOS_PUERTA.get(width_key)

                elif conn_type == "door_to_door":
                    contexto = conn.get("contexto")
                    edge["relationship_type"] = "door_to_door"
                    edge["through_space_id"] = space_id_map.get(contexto) if contexto in space_id_map else None
                    edge["traversable_by"] = self._v2_connection_profiles(origen, destino)
                    edge["base_weight"] = distance if distance is not None else 1.0
                    edge["capacity_persons"] = 1

                edge = {k: v for k, v in edge.items() if v is not None}
                edges.append(edge)
                edge_index += 1

            graphs[config["key"]] = {
                "graph_id": config["graph_id"],
                "graph_type": config["key"],
                "level_id": "LEVEL_00",
                "purpose": config["purpose"],
                "nodes": nodes,
                "edges": edges
            }

        graphs["vertical_connectivity_graph"] = {
            "graph_id": "GRAPH_VERTICAL_LEVEL_00",
            "graph_type": "vertical_connectivity_graph",
            "purpose": "Reservado para conexiones verticales; vacio en la primera exportacion v2.",
            "nodes": [],
            "edges": []
        }

        return graphs

    def _v2_write_json(self, datos, nombre_archivo):
        directorio_script = os.path.dirname(os.path.abspath(__file__))
        carpeta_destino = os.path.join(directorio_script, "escenarios")
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_completa = os.path.join(carpeta_destino, nombre_archivo)

        with open(ruta_completa, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)

        print(f"\n✅ PERFIL MLSM JSON v2 EXPORTADO A: '{ruta_completa}'")

    def exportar_mlsm_core_v2(self, conexiones, nombre_archivo="escenario_mlsm_v2.json"):
        """
        LEGACY/DEPRECATED transitional export.
        Exportacion paralela MLSM JSON v2.
        Traduce las estructuras actuales sin alterar el contrato v1 ni el dibujo.
        """
        physical_elements, element_id_map = self._v2_physical_elements()
        spaces, space_id_map = self._v2_spaces(element_id_map)
        boundaries, boundary_id_map = self._v2_boundaries_navegables(conexiones, space_id_map)
        graphs = self._v2_graphs(
            conexiones,
            spaces,
            physical_elements,
            boundaries,
            space_id_map,
            element_id_map,
            boundary_id_map
        )
        agent_spawns = self._v2_agent_spawns(spaces)

        ahora = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        datos = {
            "schema_version": "2.0.0",
            "metadata": {
                "name": self.nombre_archivo_base,
                "description": "Exportacion MLSM JSON v2 generada desde SpatialEngine.",
                "created_at": ahora,
                "modified_at": ahora,
                "author": "MLSM SpatialEngine",
                "reference_standard": "Perfil MLSM JSON v2 inspirado en IndoorGML/IndoorJSON"
            },
            "crs": {
                "type": "local",
                "srid": 0,
                "unit": "meters",
                "origin": {"x": 0, "y": 0, "z": 0},
                "description": "Sistema local 2D de SpatialEngine."
            },
            "levels": [
                {
                    "level_id": "LEVEL_00",
                    "name": "Planta baja",
                    "floor_index": 0,
                    "floor_z": 0.0,
                    "ceiling_z": 3.0,
                    "height_m": 3.0,
                    "description": "Planta unica exportada desde SpatialEngine.",
                    "spatial_extent_2d": self._v2_polygon([
                        (0, 0),
                        (self.ancho, 0),
                        (self.ancho, self.alto),
                        (0, self.alto)
                    ])
                }
            ],
            "catalogs": self._v2_catalogs(),
            "physical_elements": physical_elements,
            "spaces": spaces,
            "boundaries": boundaries,
            "graphs": graphs,
            "agent_spawns": agent_spawns,
            "agents": [],
            "beacons": [],
            "hazards": [],
            "simulation": {
                "time_step_s": 1.0,
                "max_steps": 600,
                "routing": {
                    "source_graph": "door_to_door_graph",
                    "use_dynamic_weights": False,
                    "use_beacon_risk": False,
                    "use_hazard_risk": False,
                    "use_congestion": False
                },
                "population": {
                    "mode": "from_agent_spawns",
                    "default_profile": "walking",
                    "default_count": len(agent_spawns)
                }
            },
            "indoorjson_mapping": {
                "core_mapping": {
                    "spaces": "CellSpace",
                    "boundaries": "CellBoundary",
                    "graphs.nodes": "Node",
                    "graphs.edges": "Edge"
                },
                "navigation_mapping": {
                    "navigable_space": "NavigableSpace",
                    "transfer_space": "TransferSpace",
                    "exit_space": "TransferSpace",
                    "special_boundary": "NavigableBoundary"
                },
                "mlsm_extensions": [
                    "physical_elements",
                    "catalogs",
                    "agent_spawns",
                    "simulation",
                    "door_to_door_graph"
                ],
                "compatibility": "Perfil propio MLSM inspirado en IndoorGML/IndoorJSON; no compatibilidad formal completa."
            }
        }

        self._v2_write_json(datos, nombre_archivo)

    def build_authoring_snapshot(self):
        if hasattr(self, "authoring_state"):
            for level in self.authoring_state.levels:
                level.spatial_extent_2d = [
                    (0.0, 0.0),
                    (float(self.ancho), 0.0),
                    (float(self.ancho), float(self.alto)),
                    (0.0, float(self.alto)),
                ]
            return self.authoring_state.to_snapshot(
                model_name=self.nombre_archivo_base,
                canvas={"width": self.ancho, "height": self.alto},
                crs={
                    "type": "local",
                    "unit": "meters",
                    "origin": {"x": 0, "y": 0, "z": 0},
                    "axisOrder": "xyz",
                    "description": "Sistema local 2D de SpatialEngine.",
                },
            )

        authoring_elements = []
        for nombre, tipo, x1, y1, x2, y2 in self.get_authoring_elements():
            grosor = self.GROSORES.get(tipo)
            metadata = dict(self.authoring_line_metadata.get(nombre, {}))
            snapshot_thickness = metadata.get("thicknessM", grosor)
            footprint = self.calcular_esquinas_muro(x1, y1, x2, y2, snapshot_thickness) if snapshot_thickness else None
            attrs = dict(self.propiedades_zonas.get(nombre, {}))
            element = {
                "name": nombre,
                "type": tipo,
                "level": "LEVEL_00",
                "centerline": [(x1, y1), (x2, y2)],
                "footprint": footprint,
                "thicknessM": snapshot_thickness,
                "attributes": attrs,
            }
            if tipo in self.ANCHOS_PUERTA:
                element["widthM"] = self.ANCHOS_PUERTA[tipo]
                if metadata:
                    for key in (
                        "hostWallName",
                        "hostWallType",
                        "hostWallThicknessM",
                        "hostWallRef",
                        "projectedPoint",
                        "wallUnitVector",
                    ):
                        if metadata.get(key) is not None:
                            element[key] = metadata[key]
                    attrs["authoringThicknessM"] = grosor
                    attrs["openingThicknessSource"] = "host_wall"
                else:
                    attrs["openingThicknessSource"] = "opening_fallback"
                    attrs["warning"] = "opening_host_wall_metadata_missing"
            authoring_elements.append(element)

        line_type_by_name = {element["name"]: element["type"] for element in authoring_elements}
        space_footprints = []
        for nombre, coords in self.get_space_footprints():
            if not coords:
                continue
            space_footprints.append({
                "name": nombre,
                "level": "LEVEL_00",
                "footprint": coords,
                "centroid": self.get_space_centroids().get(nombre),
                "attributes": dict(self.get_space_attributes().get(nombre, {})),
                "authoringType": line_type_by_name.get(nombre),
            })

        return {
            "modelName": self.nombre_archivo_base,
            "canvas": {"width": self.ancho, "height": self.alto},
            "crs": {
                "type": "local",
                "unit": "meters",
                "origin": {"x": 0, "y": 0, "z": 0},
                "axisOrder": "xyz",
                "description": "Sistema local 2D de SpatialEngine.",
            },
            "levels": [
                {
                    "id": "LEVEL_00",
                    "name": "Ground floor",
                    "levelIndex": 0,
                    "floorZ": 0.0,
                    "ceilingZ": 3.0,
                    "heightM": 3.0,
                }
            ],
            "authoringElements": authoring_elements,
            "spaceFootprints": space_footprints,
        }

    def _validar_indoor_model_si_posible(self, datos, schema_path):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            print("Aviso: jsonschema no esta instalado; se omite validacion de indoor_model.json.")
            return None

        try:
            with open(schema_path, "r", encoding="utf-8") as schema_file:
                schema = json.load(schema_file)
            errors = sorted(Draft202012Validator(schema).iter_errors(datos), key=lambda e: list(e.path))
        except Exception as exc:
            print(f"ERROR: no se pudo validar indoor_model.json contra el schema: {exc}")
            return False

        if errors:
            print("ERROR: indoor_model.json no valida contra schemas/indoor/indoor_model.schema.json")
            for error in errors[:50]:
                path = "/".join(map(str, error.path)) or "<root>"
                print(f" - {path}: {error.message}")
            return False

        print("OK: indoor_model.json valida contra schemas/indoor/indoor_model.schema.json")
        return True

    def generar_visual_check_indoor_model(self, json_path, layers="all", labels="none", level=None, graph_view=None, preset=None):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        visualizer_path = os.path.join(repo_root, "tools", "visualize_indoor_model.py")
        carpeta_destino = os.path.join(repo_root, "outputs", "visual_checks")
        os.makedirs(carpeta_destino, exist_ok=True)

        json_path = os.path.abspath(json_path)
        layer_suffix = str(preset or layers).replace(",", "_")
        if level:
            layer_suffix += f"_{level}"
        if graph_view:
            layer_suffix += f"_{graph_view}"
        png_path = os.path.join(
            carpeta_destino,
            f"{os.path.splitext(os.path.basename(json_path))[0]}_{layer_suffix}.png",
        )
        cmd = [
            sys.executable,
            visualizer_path,
            json_path,
            "--labels",
            labels,
            "--save",
            png_path,
            "--no-show",
        ]
        if preset:
            cmd.extend(["--preset", preset])
        else:
            cmd.extend(["--layers", layers])
        if level:
            cmd.extend(["--level", level])
        if graph_view:
            cmd.extend(["--graph-view", graph_view])
        subprocess.run(cmd, check=True)
        print(f"Visual check indoor_model generado en: '{png_path}'")
        return png_path

    def exportar_indoor_model(self, nombre_archivo=None, edge_mode="navigation"):
        """
        Nuevo flujo principal: exporta indoor_model.json basado en indoor_data_model.
        No incluye agentes, spawns, beacons, hazards ni configuracion de simulacion.
        """
        for level in self.authoring_state.sorted_levels():
            if level.geometry_dirty or not level.detected_spaces:
                result = detect_spaces(self.authoring_state, level.id)
                if not result.ok:
                    print(f"WARNING: no se pudieron detectar espacios en {level.id}: {result.report.get('message')}")
        snapshot = self.build_authoring_snapshot()
        datos = build_indoor_model(snapshot, edge_mode=edge_mode)

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        carpeta_destino = os.path.join(repo_root, "outputs", "indoor_models")
        os.makedirs(carpeta_destino, exist_ok=True)

        if nombre_archivo is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            mode_suffix = "_all_adjacency" if edge_mode == "all_adjacency" else ""
            nombre_archivo = f"{self.nombre_archivo_base}_indoor_model{mode_suffix}_{timestamp}.json"
        if not nombre_archivo.endswith(".json"):
            nombre_archivo += ".json"

        ruta_completa = os.path.join(carpeta_destino, nombre_archivo)
        with open(ruta_completa, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)

        schema_path = os.path.join(repo_root, "schemas", "indoor", "indoor_model.schema.json")
        self._validar_indoor_model_si_posible(datos, schema_path)
        print(f"\nINDOOR DATA MODEL EXPORTADO A: '{ruta_completa}' (edge_mode={edge_mode})")
        if self.auto_visual_checks_on_export:
            try:
                self.generar_visual_check_indoor_model(ruta_completa, preset="basic")
                for level in snapshot.get("levels", []):
                    level_id = level.get("id")
                    if level_id:
                        self.generar_visual_check_indoor_model(ruta_completa, preset="basic", level=level_id)
                        self.generar_visual_check_indoor_model(ruta_completa, preset="spaces", level=level_id)
                        self.generar_visual_check_indoor_model(ruta_completa, preset="navigable-boundaries", level=level_id)
                        self.generar_visual_check_indoor_model(ruta_completa, preset="non-navigable", level=level_id)
                        self.generar_visual_check_indoor_model(ruta_completa, preset="graph-base-dual", level=level_id)
                        self.generar_visual_check_indoor_model(ruta_completa, preset="graph-room-adjacency", level=level_id)
                        self.generar_visual_check_indoor_model(ruta_completa, preset="graph-room-transfer", level=level_id)
                        self.generar_visual_check_indoor_model(ruta_completa, preset="graph-door-to-door", level=level_id)
                if snapshot.get("verticalConnectors"):
                    self.generar_visual_check_indoor_model(ruta_completa, preset="graph-vertical")
            except Exception as exc:
                print(f"WARNING: No se pudo generar visual check de indoor_model.json: {exc}")
        else:
            print("Visual checks no generados automaticamente. Usa tools/visualize_indoor_model.py para las vistas que necesites.")
        return ruta_completa

    def verificar_visual_y_exportar(self):
        """
        PANTALLA DE VALIDACIÓN FINAL:
        Renderiza el resultado exacto de las operaciones CSG y topológicas antes 
        de empaquetarlas, permitiendo al usuario auditar el modelo matemáticamente.
        """
        conexiones_detectadas = self.calcular_conexiones()
        muros_recortados, datos_puertas = self.procesar_geometria_booleana()

        plt.figure("VERIFICACIÓN GEOMÉTRICA EXACTA (SHAPELY)", figsize=(12, 8))
        ax = plt.gca()
        ax.set_aspect('equal')
        ax.set_xlim(-1, self.ancho)
        ax.set_ylim(-1, self.alto)
        ax.invert_yaxis()
        
        # 1. Dibujar Muros Recortados (CSG Validado)
        for id_muro, tipo, coords in muros_recortados:
            c = 'dimgray' if tipo == 'muro_exterior' else 'silver'
            poly = patches.Polygon(coords, closed=True, facecolor=c, edgecolor='black', alpha=0.9)
            ax.add_patch(poly)
            
        # 2. Dibujar Puertas
        for id_puerta, tipo, coords in datos_puertas:
            poly = patches.Polygon(coords, closed=True, facecolor='orange', edgecolor='black', alpha=0.6)
            ax.add_patch(poly)

        # 3. Dibujar Grafos Topológicos Múltiples (MLSM)
        for conn in conexiones_detectadas:
            u, v = conn["origen"], conn["destino"]
            if u in self.hitos and v in self.hitos:
                p1, p2 = self.hitos[u], self.hitos[v]
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 
                        color=conn["color"], linewidth=2, linestyle=conn["estilo"], zorder=5)
                        
        # 4. Dibujar Nodos y Etiquetas Semánticas
        for nombre, (x, y) in self.hitos.items():
            color_nodo = 'red' if "Salida" in nombre else 'green'
            ax.plot(x, y, 'o', color=color_nodo, markeredgecolor='black', zorder=6)
            
            # Extracción de iniciales de locomoción (Ej: [W+R])
            prop = getattr(self, 'propiedades_zonas', {}).get(nombre, {})
            locs = prop.get("locomotion", [])
            etiqueta_loc = "+".join([l[0] for l in locs])
            texto_final = f"{nombre}\n[{etiqueta_loc}]" if etiqueta_loc else nombre
            ax.text(x, y, texto_final, ha='center', va='center', fontsize=6, fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, pad=0.2))
                
        # 5. Dibujar Agentes (Validación de Escala Física)
        if self.agentes:
            for ax_ag, ay_ag in self.agentes:
                ax.add_patch(patches.Circle((ax_ag, ay_ag), self.RADIO_AGENTE, facecolor='blue', edgecolor='white', zorder=8))
            
        plt.title("MAPA GEOMÉTRICO (Muros CSG y Topología MLSM)")
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.show() # Pausa la ejecución hasta que el usuario cierra la ventana
        
        # EXPORTACIÓN AUTOMÁTICA AL CERRAR
        try:
            self.exportar_indoor_model()
        except Exception as exc:
            print(f"\nWARNING: No se pudo exportar indoor_model.json: {exc}")

    def generar_codigo(self, conexiones):
        print("\n" + "="*60)
        print("=== CÓDIGO FINAL (CON SALIDAS Y GRAFO) ===")
        print("HITOS = {")
        for k, v in self.hitos.items():
            print(f"    '{k}': ({int(v[0]) if v[0].is_integer() else v[0]}, {int(v[1]) if v[1].is_integer() else v[1]}),")
        print("}")
        print("\n        conexiones = [")
        for u, v in conexiones: print(f"            ('{u}', '{v}'),")
        print("        ]")
        print(f"\n    posiciones_iniciales = {self.agentes}")
        print("\n        self.mapa_muros = np.zeros(({self.ancho}, {self.alto}))")
        print("        self.mapa_muros[0,:] = 1; self.mapa_muros[-1,:] = 1")
        print("        self.mapa_muros[:,0] = 1; self.mapa_muros[:,-1] = 1")
        for id_muro, tipo, x1, y1, x2, y2 in self.muros:
            val = 1 if tipo == 'muro' else 0
            if x1 == x2: print(f"        self.mapa_muros[{x1}, {min(y1,y2)}:{max(y1,y2)+1}] = {val}")
            else: print(f"        self.mapa_muros[{min(x1,x2)}:{max(x1,x2)+1}, {y1}] = {val}")
        print("="*60)

    def exportar_mlsm_core(self, conexiones, nombre_archivo="escenario_mlsm.json"):
        """
        LEGACY/DEPRECATED export.
        SERIALIZADOR DE DATOS:
        Empaqueta la geometría, topología y semántica en un perfil JSON híbrido 
        (MLSM Core) optimizado para el motor de simulación.
        """
        muros_recortados, datos_puertas = self.procesar_geometria_booleana()
        
        # Estructura base del contrato de datos
        datos = {
            "configuracion": {"ancho": self.ancho, "alto": self.alto},
            "conexiones_horizontales": conexiones,
            "conexiones_verticales": [], # InterLayerConnections (MLSM)
            "agentesspawn": self.agentes,
            "espacios_navegables": {}, 
            "muros": []
        }
        
        # 1. Empaquetar los Espacios Navegables y Generar Conexiones Verticales
        for nombre, bounds in self.hitos_bounds:
            poligono_coords = bounds[1] if len(bounds) == 2 else bounds
                
            datos["espacios_navegables"][nombre] = {
                "centroide": self.hitos.get(nombre, [0,0]),
                "poligono": poligono_coords,
                "atributos": self.propiedades_zonas.get(nombre, {})
            }
            
            # MAGIA MLSM: Generación dinámica de InterLayerConnections
            clase = self.propiedades_zonas.get(nombre, {}).get("clase_indoor", "")
            
            # Si es habitación, existe en la Capa Macro y Meso simultáneamente
            if clase == "NavigableSpace":
                datos["conexiones_verticales"].append({
                    "nodo_id": nombre,
                    "capa_superior": "adyacencia_fisica",
                    "capa_inferior": "navegable_puerta",
                    "tipo_conexion": "representa_el_mismo_espacio"
                })
            # Si es zona de tránsito, existe en la Capa Meso y Micro
            elif clase in ["TransferSpace", "AnchorSpace"]:
                datos["conexiones_verticales"].append({
                    "nodo_id": nombre,
                    "capa_superior": "navegable_puerta",
                    "capa_inferior": "door_to_door",
                    "tipo_conexion": "representa_el_mismo_espacio"
                })
        
        # 2. Empaquetar Geometría CSG (Muros listos para instanciar Colliders)
        for id_muro, tipo, coords in muros_recortados:
            datos["muros"].append({"id": id_muro, "tipo": tipo, "poligono": coords})
            
        for id_puerta, tipo, coords in datos_puertas:
            datos["muros"].append({"id": id_puerta, "tipo": tipo, "poligono": coords})

        # 3. Enrutamiento del File System Absoluto
        # __file__ obtiene la ruta exacta de este script (MLSM_SpatialEngine.py)
        directorio_script = os.path.dirname(os.path.abspath(__file__))
        carpeta_destino = os.path.join(directorio_script, "escenarios")
        
        os.makedirs(carpeta_destino, exist_ok=True) 
        ruta_completa = os.path.join(carpeta_destino, nombre_archivo)

        # Escritura en disco
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4)
            
        print(f"\n✅ PERFIL MLSM CORE EXPORTADO A: '{ruta_completa}'")

    def exportar_indoor_gml(self, conexiones, nombre_archivo="escenario_indoorgml.json"):
        datos_indoorgml = {
            "featureType": "IndoorFeatures",
            "layers": [] # Aquí construiremos el estándar en el futuro
        }
        
        carpeta_destino = "escenarios"
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_completa = os.path.join(carpeta_destino, nombre_archivo)
        
        with open(ruta_completa, 'w', encoding='utf-8') as f:
            json.dump(datos_indoorgml, f, indent=4)

if __name__ == "__main__":
    print("=== CONFIGURACIÓN INICIAL ===")
    nombre_base = input("Introduce el nombre base para tu escenario (ej. 'nivel_1'): ")
    # Si el usuario pulsa Enter sin escribir nada, le damos un nombre por defecto
    if not nombre_base.strip(): 
        nombre_base = "escenario_custom"
        
    # Necesitamos pasarle este nombre a la clase
    app = DiseñadorConectado(ANCHO, ALTO, nombre_base) 
    plt.show()
    app.verificar_visual_y_exportar()
