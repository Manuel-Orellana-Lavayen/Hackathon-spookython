import osmnx as ox
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Carga el grafo de Manta guardado en formato GraphML, es un grafo de NetworkX compatible con OSMnx.
grafo_manta = ox.load_graphml(BASE_DIR / "mapa_manta_300.graphml")

# Velocidades estimadas en metros por segundo para cada tipo de vía. Permiten calcular cuánto tiempo se tardaría en recorrer cada conexión del grafo
VELOCIDADES_VIA = {
    "avenida": 5.0,   # Vías rápidas y amplias
    "puente": 4.5,    # Fluido pero crítico si colapsa
    "calle": 3.5,     # Velocidad estándar residencial
    "callejon": 2.0,  # Pasajes peatonales (footway / service) más lentos
}

def clasificar_calle(datos_arista: dict) -> str:
    """
    Clasifica una conexión del mapa en uno de los cuatro tipos de vía definidos por el juego.

    Parámetros:
        datos_arista (dict): atributos de una conexión del grafo.
            Por ejemplo, puede incluir:
            - bridge: indica si la conexión corresponde a un puente.
            - highway: indica si la conexión corresponde a una carretera.
            - name: nombre de la calle.

    Retorna:
        str: uno de estos valores:
            "puente", "avenida", "callejon" o "calle".

    Nota:
        Si una conexión tiene el atributo bridge="yes", se clasifica
        directamente como puente.
    """
    # comprobamos si la conexión está marcada como puente.
    if str(datos_arista.get("bridge", "")).lower() == "yes":
        return "puente"

    # Si no existe el atributo "highway", utiliza "residential"
    highway = datos_arista.get("highway", "residential")

    # verificamos que sea una instancia de lista, y si lo es, agarramos su primer elemento y lo convertimos en minuscula
    if isinstance(highway, list):
        highway = highway[0]
    highway = str(highway).lower()

    # Obtiene el nombre de la calle. Si no existe, utiliza una cadena vacía.
    nombre = str(datos_arista.get("name", "")).lower()

    # Clasifica como avenida las vías principales indicadas o aquellas cuyo nombre contiene la palabra "avenida".
    if highway in ("primary", "secondary", "tertiary", "tertiary_link") or "avenida" in nombre:
        return "avenida"
    # Clasifica como callejón las vías de uso peatonal, servicio, caminos estrechos o escaleras.
    if highway in ("footway", "service", "track", "path", "steps"):
        return "callejon"
    # Cualquier conexión que no cumpla las condiciones anteriores se clasifica como calle.
    return "calle"


def construir_estructuras_rapidas(grafo_nx):
    """
    Transforma el grafo en dos diccionarios de Python para facilitar y acelerar las consultas del algoritmo de búsqueda.

    Parámetros:
        grafo_nx:
            Grafo de NetworkX que contiene los nodos y las conexiones de las calles.

    Retorna:
        tuple: (nodos_coords, adyacencia)

        nodos_coords:
            Diccionario que relaciona cada identificador de nodo con sus coordenadas geográficas:
            {
                "identificador": (latitud, longitud)
            }

        adyacencia:
            Diccionario de vecinos y atributos de las conexiones:
            {
                "nodo_origen": {
                    "nodo_destino": {
                        "distancia_m": distancia,
                        "tipo": tipo_de_via,
                        "velocidad": velocidad,
                        "costo_base": tiempo_estimado}}}

    Nota:
        Si existen varias conexiones dirigidas entre los mismos nodos, conserva la que tenga menor costo de tiempo
    """

    # Guardará las coordenadas de cada nodo
    nodos_coords: dict[str, tuple[float, float]] = {}
    # Guardará los vecinos accesibles desde cada nodo y los datos de la conexión que los une.
    adyacencia: dict[str, dict[str, dict]] = {}

    # Recorre todos los nodos del grafo.
    # data contiene los atributos asociados a cada nodo.
    for node_id, data in grafo_nx.nodes(data=True):
        nid = str(node_id) # Convierte el identificador a texto
        # y = latitud, x = longitud
        lat = float(data.get("y", 0.0))
        lng = float(data.get("x", 0.0))
        # Guarda las coordenadas geográficas del nodo.
        nodos_coords[nid] = (lat, lng)
        # Inicializa el diccionario de vecinos de este nodo.
        adyacencia[nid] = {}

    # Recorre todas las conexiones del grafo
    for u, v, data in grafo_nx.edges(data=True):
        # Convierte los identificadores a texto
        u_id, v_id = str(u), str(v)

        # Ignora conexiones que parten y terminan en el mismo nodo.
        if u_id == v_id:
            continue  # Ignorar auto-bucles
        # Obtiene la longitud de la conexión en metros. Si el dato no existe, utiliza 50 metros como valor predeterminado.
        distancia = float(data.get("length", 50.0))
        # Clasifica la conexión en uno de los cuatro tipos de vía.
        tipo_via = clasificar_calle(data)
        # Obtiene la velocidad estimada para ese tipo de vía.
        velocidad = VELOCIDADES_VIA[tipo_via]
        # Calcula el tiempo estimado para recorrer la conexión
        tiempo_costo = distancia / velocidad

        # Si todavía no hay una conexión guardada entre u y v,o si esta conexión tiene menor costo que la guardada, conserva sus atributos.
        if v_id not in adyacencia[u_id] or tiempo_costo < adyacencia[u_id][v_id]["costo_base"]:
            adyacencia[u_id][v_id] = {
                "distancia_m": distancia, # Longitud de la conexión.
                "tipo": tipo_via,         # Clasificación de la vía.
                "velocidad": velocidad,   # Velocidad estimada.
                "costo_base": tiempo_costo, # Tiempo estimado en segundos.
            }

    # Devuelve los dos diccionarios construidos.
    return nodos_coords, adyacencia

# Construye las estructuras rápidas una sola vez al importar este módulo.
# NODOS_COORDS contiene las coordenadas de los nodos.
# ADYACENCIA contiene sus conexiones y los costos de recorrido.
NODOS_COORDS, ADYACENCIA = construir_estructuras_rapidas(grafo_manta)

# Obtiene la velocidad más alta entre los tipos de vía (Sirve como heurística)
VELOCIDAD_MAXIMA = max(VELOCIDADES_VIA.values())