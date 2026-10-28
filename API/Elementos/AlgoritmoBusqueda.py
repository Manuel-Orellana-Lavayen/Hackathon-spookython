import math
import heapq # lista de prioridad (el elemento más pequeño siempre está al principio)
from collections import deque # Cola de doble extremo (orden cronológico)
from API.Elementos.Grafo import NODOS_COORDS, ADYACENCIA, VELOCIDAD_MAXIMA

def distancia_haversine_m(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """
    Calcula una aproximación de la distancia en línea recta entre dos coordenadas geográficas, expresada en metros.

    Parámetros:
        coord1 (tuple[float, float]):
            Coordenadas (latitud, longitud) del primer punto.

        coord2 (tuple[float, float]):
            Coordenadas (latitud, longitud) del segundo punto.

    Retorna:
        float:
            Distancia aproximada en metros entre los dos puntos.

    Uso:
        Puede servir como heurística para A*, estimando cuánto falta hasta el destino sin recorrer las calles intermedias.
    """
    # Separa la latitud y la longitud de ambos puntos.
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # Aproxima la distancia norte-sur.
    dy = (lat2 - lat1) * 111_320.0
    # Aproxima la distancia este-oeste.
    dx = (lon2 - lon1) * 111_320.0 * math.cos(math.radians((lat1 + lat2) * 0.5))
    return math.hypot(dx, dy)


def nodos_a_distancia_k(nodo_origen: str, k: int, aristas_bloqueadas: set[tuple[str, str]]) -> dict[str, int]:
    """
    Busca todos los nodos que pueden alcanzarse desde un nodo determinado utilizando como máximo k calles. Utiliza BFS

    Parámetros:
        nodo_origen:
            Nodo desde el cual comienza la búsqueda.

        k:
            Número máximo de calles que se pueden recorrer.

        aristas_bloqueadas:
            Conjunto de conexiones que actualmente están cerradas.

    Retorna:
        dict[str, int]:
            Diccionario donde:
                clave   = identificador del nodo.
                valor   = cantidad de calles necesarias para llegar.
    """
    # Guarda los nodos encontrados y la cantidad de saltos necesarios para llegar a ellos.
    visitados = {nodo_origen: 0}  # El nodo inicial está a distancia 0 de sí mismo.
    # Cola utilizada por BFS. Cada elemento contiene: (nodo_actual, cantidad_de_saltos)
    cola = deque([(nodo_origen, 0)])

    # Continúa mientras existan nodos pendientes de explorar.
    while cola:
        # Obtiene el siguiente nodo de la cola
        actual, dist = cola.popleft()
        # Si ya alcanzamos el límite de saltos permitido, no seguimos explorando desde este nodo.
        if dist >= k:
            continue
        # Recorre todos los vecinos del nodo actual.
        for vecino in ADYACENCIA.get(actual, {}):
            # Si la calle está bloqueada, no podemos utilizarla.
            if (actual, vecino) in aristas_bloqueadas:
                continue
            # Si todavía no hemos visitado el vecino, registramos su distancia y lo añadimos a la cola.
            if vecino not in visitados:
                visitados[vecino] = dist + 1
                cola.append((vecino, dist + 1))
    return visitados

def obtener_aristas_contraflujo_zombies(zombies: list) -> set[tuple[str, str]]:
    """
    Genera el conjunto de aristas dirigidas (destino -> origen) que los zombies
    acaban de recorrer en el turno actual. Si un sobreviviente las recorre en
    sentido inverso, morirá por cruce opuesto.
    """
    aristas_contraflujo: set[tuple[str, str]] = set()
    for z in zombies:
        if not z.activo or not z.despierto:
            continue
        recorrido = getattr(z, "nodos_recorridos_turno", [])
        for i in range(len(recorrido) - 1):
            z_origen = recorrido[i]
            z_destino = recorrido[i + 1]
            if z_origen != z_destino:
                # Prohibimos al sobreviviente ir de z_destino hacia z_origen en este turno
                aristas_contraflujo.add((z_destino, z_origen))
    return aristas_contraflujo

def calcular_zonas_peligro(zombies: list, aristas_bloqueadas: set[tuple[str, str]]):
    """
    Analiza la posición de los zombies y determina qué partes del mapa representan peligro para los sobrevivientes.

        Reglas implementadas:

            Caminante:
                Su nodo queda prohibido.

            Horda:
                Su nodo y todos sus vecinos quedan prohibidos.

            Corredor:
                Su zona cercana recibe una penalización de riesgo.

    Parámetros:
        zombies:
            Entidades que hay que evitar.

        aristas_bloqueadas:
            Conjunto de conexiones que actualmente están cerradas.

    Retorna:
        tuple:
            (nodos_prohibidos, penalizacion_riesgo)

        nodos_prohibidos:
            Nodos donde un sobreviviente no debería entrar.

        penalizacion_riesgo:
            Costo adicional que A* agrega a determinados nodos para evitar zonas cercanas a zombies.
    """

    # Conjunto de nodos que A* no debería utilizar.
    nodos_prohibidos: set[str] = set()

    # Diccionario con costos adicionales de riesgo.
    penalizacion_riesgo: dict[str, float] = {}

    # Analiza cada zombie existente.
    for z in zombies:
        # Zombies inactivos o invisibles no representan peligro para la navegación actual.
        if not z.activo or not z.visible:
            continue

        # El nodo donde se encuentra cualquier zombie visible queda prohibido.
        nodos_prohibidos.add(z.nodo_actual)

        # HORDA
        if z.tipo == "horda":
            # Bloquea vecinos de salida y de entrada (por si hay vías de un solo sentido)
            for vecino in ADYACENCIA.get(z.nodo_actual, {}):
                nodos_prohibidos.add(vecino)
            for u, vecinos_u in ADYACENCIA.items():
                if z.nodo_actual in vecinos_u:
                    nodos_prohibidos.add(u)

            """
                -- Para solo bloquear el nodo de la horda y no los cercanos reemplazar este bloquepor el anterior
                if z.tipo == "horda":
                    nodos_prohibidos.add(z.nodo_actual)
            """

        # CORREDOR
        elif z.tipo == "corredor":
            # Busca todos los nodos que el corredor podría alcanzar en un máximo de 2 calles.
            alcanzables = nodos_a_distancia_k(z.nodo_actual, 2, aristas_bloqueadas)
            # Analiza los nodos alcanzables.
            for nodo_peligro, saltos in alcanzables.items():
                # A un salto del corredor: riesgo muy alto.
                if saltos == 1:
                    penalizacion_riesgo[nodo_peligro] = penalizacion_riesgo.get(nodo_peligro, 0.0) + 500.0
                # A dos saltos: riesgo menor, pero todavía importante.
                elif saltos == 2:
                    penalizacion_riesgo[nodo_peligro] = penalizacion_riesgo.get(nodo_peligro, 0.0) + 150.0

        # CAMINANTE
        elif z.tipo == "caminante":
            # Los vecinos del caminante reciben una penalización.
            for vecino in ADYACENCIA.get(z.nodo_actual, {}):
                penalizacion_riesgo[vecino] = penalizacion_riesgo.get(vecino, 0.0) + 80.0

    # Devuelve tanto los nodos completamente prohibidos como las penalizaciones que A* debe considerar.
    return nodos_prohibidos, penalizacion_riesgo


def a_estrella(
                inicio: str,
                objetivo: str,
                nodos_prohibidos: set[str],
                penalizacion_riesgo: dict[str, float],
                aristas_bloqueadas: set[tuple[str, str]],
                ) -> tuple[list[str], float]:
    """
    Busca la mejor ruta entre dos nodos utilizando A*.

    A* considera:

        1. Tiempo estimado de las calles.
        2. Velocidad según el tipo de calle.
        3. Calles bloqueadas.
        4. Nodos peligrosos.
        5. Penalizaciones por proximidad a zombies.

    Parámetros:
        inicio:
            Nodo donde se encuentra el sobreviviente.

        objetivo:
            Nodo del refugio.

        nodos_prohibidos:
            Nodos que no deben utilizarse.

        penalizacion_riesgo:
            Costos adicionales asociados al peligro.

        aristas_bloqueadas:
            Calles que actualmente no pueden utilizarse.

    Retorna:
        tuple[list[str], float]:

            ruta:
                Lista ordenada de nodos desde el inicio hasta el objetivo.

            costo:
                Costo total estimado de la ruta en segundos más las penalizaciones de riesgo.
    """
    # No dirigir sobrevivientes hacia un refugio que está en una zona prohibida.
    if objetivo in nodos_prohibidos:
        return [], float("inf")

    # Si el sobreviviente ya está en un objetivo seguro, no hace falta buscar.
    if inicio == objetivo:
        return [inicio], 0.0

    # Coordenadas del objetivo.
    coord_obj = NODOS_COORDS[objetivo]
    frontera = [(0.0, inicio)]
    # Guarda desde qué nodo llegamos a cada nodo. Se utiliza posteriormente para reconstruir la ruta
    vino_de: dict[str, str | None] = {inicio: None}
    # Guarda el menor costo conocido para llegar a cada nodo.
    costo_g: dict[str, float] = {inicio: 0.0}

    # Continúa mientras existan nodos pendientes de explorar.
    while frontera:
        # Obtiene el nodo con menor prioridad.
        _, actual = heapq.heappop(frontera)

        # Si llegamos al objetivo, reconstruimos la ruta.
        if actual == objetivo:
            ruta = [] # Lista donde se almacenará la ruta
            curr: str | None = actual # Comenzamos desde el objetivo.
            # Retrocedemos utilizando el diccionario vino_de
            while curr is not None:
                ruta.append(curr)
                curr = vino_de[curr]
            ruta.reverse()
            # Devuelve la ruta y su costo.
            return ruta, costo_g[objetivo]

        # Explora todos los vecinos del nodo actual.
        for vecino, datos_calle in ADYACENCIA.get(actual, {}).items():
            # No podemos utilizar una calle bloqueada.
            if (actual, vecino) in aristas_bloqueadas:
                continue
            # No entrar a nodos prohibidos (salvo que sea el refugio mismo)
            if vecino in nodos_prohibidos and vecino != objetivo:
                continue
            # Calcula el costo de llegar al vecino
            nuevo_costo = (costo_g[actual]+ datos_calle["costo_base"]+ penalizacion_riesgo.get(vecino, 0.0))
            # Si nunca habíamos llegado al vecino o encontramos una ruta más barata, actualizamos su información.
            if vecino not in costo_g or nuevo_costo < costo_g[vecino]:
                costo_g[vecino] = nuevo_costo
                heuristica = distancia_haversine_m(NODOS_COORDS[vecino], coord_obj) / VELOCIDAD_MAXIMA
                prioridad = nuevo_costo + heuristica
                heapq.heappush(frontera, (prioridad, vecino))
                vino_de[vecino] = actual
    # Si no existe ninguna ruta válida, devuelve una ruta vacía y costo infinito.
    return [], float("inf")


def algoritmo_busqueda(
    nodo_actual: str,
    refugios: list,
    zombies: list,
    aristas_bloqueadas: set[tuple[str, str]],
    nodos_prohibidos: set[str] | None = None,
    penalizacion_riesgo: dict[str, float] | None = None,
    en_camino_por_refugio: dict[str, int] | None = None,
) -> tuple[list[str], str | None]:
    """
    Decide a qué refugio debería dirigirse un sobreviviente y calcula la ruta correspondiente,
    reutilizando las zonas de peligro precalculadas, evitando cruces frontales con zombies
    y repartiendo sobrevivientes según la saturación proyectada de cada refugio.
    """
    # 1. Reutilizar zonas de peligro si ya fueron calculadas en el turno (evita recalcular 200 veces)
    if nodos_prohibidos is None or penalizacion_riesgo is None:
        nodos_prohibidos, penalizacion_riesgo = calcular_zonas_peligro(zombies, aristas_bloqueadas)

    # 2. Bloquear temporalmente en este turno las aristas por donde acaban de venir los zombies
    aristas_contraflujo = obtener_aristas_contraflujo_zombies(zombies)
    aristas_invalidas_turno = aristas_bloqueadas | aristas_contraflujo

    mejor_ruta: list[str] = []
    mejor_refugio_id: str | None = None
    mejor_costo = float("inf")

    # 3. Evaluar refugios disponibles considerando tanto ocupación actual como sobrevivientes en camino
    for refugio in refugios:
        if not refugio.tiene_espacio():
            continue

        ruta, costo_ruta = a_estrella(
            nodo_actual,
            refugio.nodo,
            nodos_prohibidos,
            penalizacion_riesgo,
            aristas_invalidas_turno,
        )

        if not ruta:
            continue

        # Penalización por congestión para repartir sobrevivientes antes de que el refugio se llene
        penalizacion_congestion = 0.0
        if refugio.capacidad is not None and en_camino_por_refugio is not None:
            en_camino = en_camino_por_refugio.get(refugio.id, 0)
            ocupacion_proyectada = refugio.ocupacion + en_camino
            espacios_fisicos = max(1, refugio.capacidad - refugio.ocupacion)

            if ocupacion_proyectada >= refugio.capacidad:
                # Si ya van suficientes sobrevivientes en camino para llenarlo,
                # aplicamos una penalización alta para desviar a los más lejanos a otro refugio.
                exceso = ocupacion_proyectada - refugio.capacidad + 1
                penalizacion_congestion = 500.0 + (exceso * 150.0)
            else:
                # Penalización suave proporcional a qué tan comprometido está el refugio
                penalizacion_congestion = (en_camino / espacios_fisicos) * 80.0

        costo_total = costo_ruta + penalizacion_congestion

        if costo_total < mejor_costo:
            mejor_costo = costo_total
            mejor_ruta = ruta
            mejor_refugio_id = refugio.id

    # 4. Si está acorralado, moverse al vecino libre menos peligroso sin cruzar de frente con un zombie
    if not mejor_ruta:
        vecinos_validos = [
            v for v in ADYACENCIA.get(nodo_actual, {})
            if (nodo_actual, v) not in aristas_invalidas_turno and v not in nodos_prohibidos
        ]
        if vecinos_validos:
            vecinos_validos.sort(key=lambda v: penalizacion_riesgo.get(v, 0.0))
            return [nodo_actual, vecinos_validos[0]], None
        return [nodo_actual], None

    return mejor_ruta, mejor_refugio_id