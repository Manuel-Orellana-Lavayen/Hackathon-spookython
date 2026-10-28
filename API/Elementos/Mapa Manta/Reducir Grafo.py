import osmnx as ox
import networkx as nx
from pathlib import Path
from collections import deque

BASE_DIR = Path(__file__).resolve().parent

# Cargar el grafo original
G = ox.load_graphml(BASE_DIR / "mapa_manta.graphml")

# Usar una copia no dirigida para seleccionar una zona conectada
U = nx.Graph(G)

# Elegir como inicio el nodo con más vecinos
inicio = max(U.degree, key=lambda x: x[1])[0]

# Recorrido en anchura para seleccionar nodos conectados
visitados = {inicio}
cola = deque([inicio])

while cola and len(visitados) < 300:
    actual = cola.popleft()

    for vecino in U.neighbors(actual):
        if vecino not in visitados:
            visitados.add(vecino)
            cola.append(vecino)

        if len(visitados) >= 300:
            break

# Crear el subgrafo conservando las calles originales
G_reducido = G.subgraph(visitados).copy()

print("Nodos:", G_reducido.number_of_nodes())
print("Conexiones:", G_reducido.number_of_edges())

# Guardar el nuevo grafo
ox.save_graphml(
    G_reducido,
    BASE_DIR / "mapa_manta_300.graphml"
)

# Visualizar el resultado
ox.plot_graph(G_reducido)