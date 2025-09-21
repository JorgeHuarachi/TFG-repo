import psycopg2, pandas as pd, networkx as nx, matplotlib.pyplot as plt, numpy as np

con = psycopg2.connect("dbname=prueba_Indoor user=postgres password=DB032122 host=localhost")

df = pd.read_sql("SELECT * FROM v_dual_nodepack ORDER BY idx;", con)
con.close()

# Seguridad por defecto si hay NULL (ej. en transfers)
default_safety = 0.5
df['safety'] = df['safety'].fillna(default_safety)

# Construye G (no dirigido) usando los neighbors
G = nx.Graph()
for _, r in df.iterrows():
    i = int(r.idx)
    G.add_node(i,
               label = r.cell_name if r.cell_name else f"state-{i}",
               pos   = (float(r.x), float(r.y)),
               role  = r.role,
               safety= float(r.safety))
    for j in r.neighbors:         # neighbors es un array de ints
        if i < j:                 # evita duplicar arista
            # Peso de la arista = seguridad del nodo destino (tu criterio)
            w = float(df.loc[df.idx==j, 'safety'].iloc[0])
            G.add_edge(i, int(j), weight = w)

# Dibujo
pos = {n: G.nodes[n]['pos'] for n in G.nodes}
plt.figure(figsize=(9,6))
nx.draw(G, pos,
        labels={n:G.nodes[n]['label'] for n in G.nodes},
        with_labels=True,
        node_size=700,
        node_color=[G.nodes[n]['safety'] for n in G.nodes],
        cmap=plt.cm.YlGn, vmin=0, vmax=1, font_size=9)

edge_labels = {(u,v): f"{G[u][v]['weight']:.2f}" for u,v in G.edges()}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color="firebrick")

plt.title("Grafo dual — peso(arista)=seguridad del nodo destino")
plt.tight_layout(); plt.show()

# Si quieres matrices:
N = df.shape[0]
mat_cost = np.zeros((N,N))  # si luego le pondrás otros costes
mat_safe = np.zeros((N,N))
safety_by_i = dict(zip(df.idx.astype(int), df.safety.astype(float)))
for u,v in G.edges():
    mat_safe[u,v] = safety_by_i[v]
    mat_safe[v,u] = safety_by_i[u]
