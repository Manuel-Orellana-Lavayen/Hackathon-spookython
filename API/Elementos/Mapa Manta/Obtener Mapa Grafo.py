import osmnx as ox
import time


def cargar_mapa():
    intentos = 5

    for intento in range(intentos):
        try:
            print(f"Descargando mapa de Manta... Intento {intento + 1}/{intentos}")

            G = ox.graph_from_place(
                "Manta, Manabi, Ecuador",
                network_type="walk" # Vias y caminos aptas para peatones
            )

            ox.save_graphml(G, "mapa_manta.graphml")

            print("Mapa descargado y guardado correctamente.")
            return G

        except ox._errors.ResponseStatusCodeError as e:
            print(f"Error del servidor: {e}")

            if intento < intentos - 1:
                espera = 5 * (2 ** intento)
                print(f"Esperando {espera} segundos antes de reintentar...")
                time.sleep(espera)
            else:
                raise


if __name__ == "__main__":
    G = cargar_mapa()

    print("Nodos:", len(G.nodes))
    print("Conexiones:", len(G.edges))

    ox.plot_graph(G)