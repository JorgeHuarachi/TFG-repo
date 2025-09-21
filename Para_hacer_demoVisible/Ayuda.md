¡Totalmente posible! Te doy **3 caminos** y te dejo **uno ya armado** (FastAPI + Leaflet + Plotly) para que lo ejecutes local y tengas un mini-dashboard con: plano de la planta, nodos coloreados por seguridad y un gráfico histórico por sala al hacer clic.

---

# Opciones rápidas

1. **FastAPI + Leaflet + Plotly (estático, local) – recomendado**

   * Backend: expone `/api/graph` (nodos/edges), `/api/rooms_geojson` (salas/puertas), `/api/series/{cell_id}?var=…&hours=…` (histórico).
   * Frontend: HTML simple con Leaflet (mapa 2D) y Plotly (gráfico).
   * Pros: muy flexible, zero magia.
2. **Streamlit + streamlit-folium + Plotly**

   * Un solo script Python; UI rápida con widgets.
   * Pros: ultra rápido para prototipos; contras: menos control sobre el mapa.
3. **Dash (Plotly) + dash-leaflet**

   * App Python con callbacks reactivos; muy potente para dashboards.
   * Pros: componentes robustos; contras: un pelín más de boilerplate.

Abajo te dejo la **opción 1 completa** (copia/pega y funciona).

---

# Opción 1 — Mini-demo local (FastAPI + Leaflet + Plotly)

## 0) Paquetes

```bash
pip install fastapi uvicorn asyncpg
```

(Usamos tu Postgres local con las vistas: `v_dual_nodes`, `v_dual_edges_idx`, y tablas `cellspace`, `reading_hist`, `variable`.)

## 1) `app.py` (backend API)

```python
# app.py
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import asyncpg

DATABASE_URL = "postgresql://postgres:DB032122@localhost/prueba_Indoor"

app = FastAPI()

@app.on_event("startup")
async def startup():
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)

@app.on_event("shutdown")
async def shutdown():
    await app.state.pool.close()

# Nodos (con x,y,safety, nombre) y aristas (i->j, coste_m)
@app.get("/api/graph")
async def graph():
    async with app.state.pool.acquire() as con:
        nodes = await con.fetch("""
          SELECT idx, state_id::text, cell_id::text, x, y,
                 COALESCE(cell_name,'') AS cell_name,
                 COALESCE(cell_category,'') AS cell_category,
                 COALESCE(safety,0.5) AS safety
          FROM v_dual_nodes
          ORDER BY idx
        """)
        edges = await con.fetch("""
          SELECT i, j, COALESCE(weight_m,0) AS cost
          FROM v_dual_edges_idx
          ORDER BY i, j
        """)
    return {
        "nodes": [dict(r) for r in nodes],
        "edges": [dict(r) for r in edges]
    }

# Salas/puertas/ventanas como GeoJSON (Leaflet)
@app.get("/api/rooms_geojson")
async def rooms_geojson():
    async with app.state.pool.acquire() as con:
        rows = await con.fetch("""
          SELECT cell_id::text AS id,
                 COALESCE(name,'') AS name,
                 COALESCE(category,'') AS category,
                 ST_AsGeoJSON(geom)::json AS geometry
          FROM cellspace
          WHERE category IN ('room','door','window')
        """)
    features = [{
        "type": "Feature",
        "id": r["id"],
        "geometry": r["geometry"],
        "properties": {"name": r["name"], "category": r["category"]}
    } for r in rows]
    return {"type": "FeatureCollection", "features": features}

# Serie temporal por sala y variable (últimas N horas)
@app.get("/api/series/{cell_id}")
async def series(cell_id: str, var: str = "temperatura", hours: int = 24):
    async with app.state.pool.acquire() as con:
        data = await con.fetch("""
          SELECT EXTRACT(EPOCH FROM ts)*1000 AS t_ms, value
          FROM reading_hist h
          JOIN variable v ON v.var_id=h.var_id
          WHERE h.cell_id=$1 AND v.name=$2
            AND ts >= now() - ($3 || ' hours')::interval
          ORDER BY ts
        """, cell_id, var, str(hours))
    return [{"t": r["t_ms"], "v": r["value"]} for r in data]

# Servir el front estático (index.html)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

## 2) `static/index.html` (frontend Leaflet + Plotly)

Crea una carpeta `static/` y dentro un `index.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>Indoor mini-dashboard</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
<style>
  html, body { height:100%; margin:0; display:flex; flex-direction:column; }
  #topbar { padding:8px 12px; background:#111; color:#eee; font-family:system-ui; display:flex; gap:12px; align-items:center; }
  #main { flex:1; display:flex; }
  #map { flex: 2; }
  #side { flex: 1; border-left: 1px solid #ddd; padding:8px; overflow:auto; }
  .badge { padding:2px 6px; border-radius:6px; background:#eee; margin-left:6px; font-size:12px; }
</style>
</head>
<body>
  <div id="topbar">
    <div><b>Indoor mini-dashboard</b></div>
    <div>Variable:
      <select id="varSel">
        <option value="temperatura">temperatura</option>
        <option value="co2">co2</option>
        <option value="humo">humo</option>
      </select>
      <span class="badge">Click sala para ver serie</span>
    </div>
  </div>
  <div id="main">
    <div id="map"></div>
    <div id="side">
      <h3 id="roomTitle">Sala: —</h3>
      <div id="chart"></div>
    </div>
  </div>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<script>
const map = L.map('map');
const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
  attribution:'&copy; OpenStreetMap'
}).addTo(map);

let cellLayer, nodeLayer, edgeLayer;
const varSel = document.getElementById('varSel');
const roomTitle = document.getElementById('roomTitle');

function colorByCategory(cat){
  if(cat==='room') return '#90CAF9';
  if(cat==='door') return '#FFB300';
  if(cat==='window') return '#00ACC1';
  return '#E0E0E0';
}
function colorBySafety(s){ // 0..1 -> verde
  const g = Math.round(255*s), r = Math.round(255*(1-s));
  return `rgb(${r},${g},80)`;
}

async function loadRooms(){
  const res = await fetch('/api/rooms_geojson');
  const data = await res.json();
  if(cellLayer) map.removeLayer(cellLayer);
  cellLayer = L.geoJSON(data, {
    style: f => ({ color:'#444', weight:1, fillOpacity:0.3, fillColor: colorByCategory(f.properties.category) }),
    onEachFeature: (f, l) => {
      l.bindPopup(`<b>${f.properties.name||'Sala'}</b><br>${f.id}`);
      l.on('click', () => showSeries(f.id));
    }
  }).addTo(map);
  const bounds = cellLayer.getBounds();
  if(bounds.isValid()) map.fitBounds(bounds.pad(0.05));
}

async function loadGraph(){
  const res = await fetch('/api/graph');
  const data = await res.json();
  // Edges (as polylines between node coords)
  if(edgeLayer) map.removeLayer(edgeLayer);
  const lines = [];
  data.edges.forEach(e=>{
    const ni = data.nodes[e.i], nj = data.nodes[e.j];
    if(!ni || !nj) return;
    lines.push(L.polyline([[ni.y,ni.x],[nj.y,nj.x]], { color:'#999', weight:1, opacity:0.7 }));
  });
  edgeLayer = L.layerGroup(lines).addTo(map);

  // Nodes as circle markers, colored by safety
  if(nodeLayer) map.removeLayer(nodeLayer);
  nodeLayer = L.layerGroup(
    data.nodes.map(n=>{
      const m = L.circleMarker([n.y, n.x], { radius:6, color:'#222', weight:1, fillOpacity:0.9, fillColor: colorBySafety(n.safety) });
      m.bindTooltip(`${n.cell_name||'state-'+n.idx}<br>safety: ${n.safety.toFixed(2)}`);
      m.on('click', ()=> showSeries(n.cell_id));
      return m;
    })
  ).addTo(map);
}

async function showSeries(cell_id){
  roomTitle.textContent = `Sala: ${cell_id}`;
  const varName = varSel.value;
  const data = await (await fetch(`/api/series/${cell_id}?var=${encodeURIComponent(varName)}&hours=24`)).json();
  const trace = {
    x: data.map(d=> new Date(d.t)),
    y: data.map(d=> d.v),
    mode: 'lines+markers',
    name: varName
  };
  Plotly.newPlot('chart', [trace], {
    margin:{l:40,r:20,t:30,b:40},
    xaxis:{title:'Tiempo'},
    yaxis:{title:varName}
  }, {displaylogo:false});
}

varSel.addEventListener('change', ()=>{
  const id = roomTitle.textContent.split(': ')[1];
  if(id && id !== '—') showSeries(id);
});

loadRooms();
loadGraph();
</script>
</body>
</html>
```

## 3) Arrancar

```bash
uvicorn app:app --reload
```

Abre `http://127.0.0.1:8000/` y prueba:

* Capa de salas/puertas coloreadas.
* Nodos (círculos) con color = seguridad (verde = 1).
* Clic en una sala → gráfico de la variable elegida (24h).

> Si tu geometría está en EPSG:4326 (lon/lat), Leaflet te lo pinta directo. Si usas un CRS métrico, puedes:
>
> * Transformar en SQL a 4326 para el GeoJSON (`ST_Transform(geom, 4326)`).
> * O usar una vista WGS84 para el front.

---

## Bonus: endpoints útiles

* **Último estado por sala** (para colorear salas por valor):

```sql
CREATE OR REPLACE VIEW v_last_by_room AS
SELECT r.cell_id, v.name AS var, r.value, r.ts
FROM reading r
JOIN variable v ON v.var_id=r.var_id;
```

Desde el front, puedes pedir `/api/rooms_geojson?var=temperatura` y colorear por valor (añades un parámetro en el endpoint y mezclas propiedades).

* **Serie por nodo (state)**: si algún día prefieres series por `state_id`, añade un endpoint que haga JOIN `state.dual_cell -> reading_hist`.

---

## ¿Y si quiero hacerlo con Streamlit?

Muy corto:

```python
# streamlit_app.py
import streamlit as st, psycopg2, pandas as pd
from streamlit_folium import st_folium
import folium, plotly.express as px

con = psycopg2.connect("dbname=prueba_Indoor user=postgres password=DB032122 host=localhost")

rooms = pd.read_sql("SELECT cell_id::text id, name, category, ST_AsGeoJSON(geom) gj FROM cellspace WHERE category IN ('room','door','window');", con)
nodes = pd.read_sql("SELECT idx, x, y, COALESCE(safety,0.5) safety, COALESCE(cell_name,'') name FROM v_dual_nodes;", con)

st.sidebar.title("Mini dashboard")
var = st.sidebar.selectbox("Variable", ["temperatura","co2","humo"])

m = folium.Map(tiles='OpenStreetMap')
for _, r in rooms.iterrows():
    folium.GeoJson(r.gj, name=r['name']).add_to(m)
for _, n in nodes.iterrows():
    folium.CircleMarker([n.y, n.x], radius=5, tooltip=f"{n.name} {n.safety:.2f}").add_to(m)

out = st_folium(m, width=900, height=600)

clicked_cell = st.text_input("cell_id", "")  # o recoge del mapa si deseas
if clicked_cell:
    q = """
      SELECT ts, value
      FROM reading_hist h JOIN variable v ON v.var_id=h.var_id
      WHERE h.cell_id=%s AND v.name=%s AND ts >= now() - interval '24 hours'
      ORDER BY ts;"""
    df = pd.read_sql(q, con, params=(clicked_cell, var))
    st.plotly_chart(px.line(df, x='ts', y='value', title=f"{var} — {clicked_cell}"))
```

---

## Qué te aporta este enfoque

* **Plano + grafo** en una vista: salas (GeoJSON) + nodos/edges (dual).
* **Series históricas** por sala al clic.
* **Extensible**: puedes añadir capas (ventanas, puertas) y colorear por variable o seguridad.
* **Reutiliza tus vistas SQL** (no duplicas lógica).

Si quieres, te preparo variantes:

* colorear **salas por última temperatura**,
* conmutar **nivel/planta**,
* o un botón para **exportar el grafo** a NetworkX directamente desde la UI.
