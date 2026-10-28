import random
import time
from API.Elementos.Clases import Sobreviviente, Zombie, Refugio
from API.Elementos.Grafo import ADYACENCIA, NODOS_COORDS
from API.Elementos.AlgoritmoBusqueda import algoritmo_busqueda, nodos_a_distancia_k, calcular_zonas_peligro,obtener_aristas_contraflujo_zombies


class EstadoMundo:
    """Agrupa todos los datos mutables de una partida.

        Se usa un objeto para evitar repartir el estado por muchas variables globales.
        Sus diccionarios permiten buscar entidades por su identificador.
    """
    def __init__(self):
        self.turno: int = 0
        self.sobrevivientes: dict[str, Sobreviviente] = {}
        self.zombies: dict[str, Zombie] = {}
        self.refugios: dict[str, Refugio] = {}
        self.aristas_bloqueadas: set[tuple[str, str]] = set()
        self.latencias_ms: list[float] = []
        self.eventos_log: list[str] = []

# Estado global inicial.
MUNDO = EstadoMundo()


def inicializar_simulacion(
    num_sobrevivientes: int = 20,
    config_zombies: dict[str, int] | None = None,
    semilla: int = 42,

    ) -> EstadoMundo:

    """Reinicia el estado y crea las entidades iniciales.

    Args:
        num_sobrevivientes: cantidad de sobrevivientes a crear.
        config_zombies: cantidad de zombies por tipo; usa valores por defecto si no se proporciona.
        semilla: semilla aleatoria para que las posiciones iniciales sean reproducibles al repetir la misma configuración.

    Returns:
        El nuevo objeto EstadoMundo, también asignado a la variable global MUNDO.

    Nota: `random.seed` afecta al generador aleatorio global del proceso.
    """
    global MUNDO
    random.seed(semilla)
    MUNDO = EstadoMundo()

    if config_zombies is None:
        config_zombies = {"caminante": 15, "corredor": 5, "horda": 2, "dormido": 5}

    # Se prefieren nodos con al menos dos salidas para reducir la probabilidad
    # de colocar entidades en calles sin alternativas.
    todos_los_nodos = [n for n, vecinos in ADYACENCIA.items() if len(vecinos) >= 2]

    # 1. Crear 4 refugios y hacer cálculo de capacidad con base en los sobrevivientes
    nodos_ordenados = sorted(todos_los_nodos, key=lambda n: (NODOS_COORDS[n][0], NODOS_COORDS[n][1]))
    indices_refugios = [0, len(nodos_ordenados) // 3, (2 * len(nodos_ordenados)) // 3, -1]
    capacidad_por_refugio = max(10, (num_sobrevivientes // 4) + 5)

    nodos_refugio = set()
    for i, idx in enumerate(indices_refugios, start=1):
        nodo_ref = nodos_ordenados[idx]
        ref_id = f"R-0{i}"
        MUNDO.refugios[ref_id] = Refugio(id=ref_id, nodo=nodo_ref, capacidad=capacidad_por_refugio)
        nodos_refugio.add(nodo_ref)

    nodos_disponibles = [n for n in todos_los_nodos if n not in nodos_refugio]

    # 2. Crear Zombies lejos de los refugios
    contador_z = 1
    nodos_ocupados_zombies = set()
    for tipo, cantidad in config_zombies.items():
        for _ in range(cantidad):
            nodo_z = random.choice(nodos_disponibles)
            z_id = f"Z-{contador_z:04d}"
            MUNDO.zombies[z_id] = Zombie(id=z_id, tipo=tipo, nodo_actual=nodo_z)
            nodos_ocupados_zombies.add(nodo_z)
            contador_z += 1

    # 3. Crear Sobrevivientes en nodos sin zombies iniciales
    nodos_seguros = [n for n in nodos_disponibles if n not in nodos_ocupados_zombies] or nodos_disponibles
    for i in range(1, num_sobrevivientes + 1):
        s_id = f"S-{i:04d}"
        nodo_s = random.choice(nodos_seguros)
        MUNDO.sobrevivientes[s_id] = Sobreviviente(id=s_id, nodo_actual=nodo_s)

    return MUNDO


def procesar_eventos() -> None:
    """
    Aplica los eventos programados y despierta zombies cercanos.

    Los cierres se registran en `MUNDO.aristas_bloqueadas`. Para cada calle
    cerrada se añade (u, v) y (v, u), porque el cierre se trata como bilateral.
    Después se revisa si algún sobreviviente activo está a dos aristas o menos
    de un zombie dormido.
    """
    # 1. Eventos de ciudad en turnos específicos (colapso de puente o bloqueo de avenida)
    if MUNDO.turno == 25:
        for u, vecinos in ADYACENCIA.items():
            for v, datos in vecinos.items():
                if datos["tipo"] == "puente" and (u, v) not in MUNDO.aristas_bloqueadas:
                    # Se bloquea la dirección u -> v.
                    MUNDO.aristas_bloqueadas.add((u, v))
                    # También se bloquea la dirección inversa v -> u.
                    MUNDO.aristas_bloqueadas.add((v, u))
                    MUNDO.eventos_log.append(f"Turno {MUNDO.turno}: ¡Colapsó puente ({u} <-> {v})!")
                    break
            else:
                continue
            break

    elif MUNDO.turno in (55, 70):
        candidatas = [
            (u, v)
            for u, vecinos in ADYACENCIA.items()
            for v, d in vecinos.items()
            if d["tipo"] == "avenida" and (u, v) not in MUNDO.aristas_bloqueadas
        ]
        if candidatas:
            u, v = random.choice(candidatas)
            MUNDO.aristas_bloqueadas.add((u, v))
            MUNDO.aristas_bloqueadas.add((v, u))
            MUNDO.eventos_log.append(f"Turno {MUNDO.turno}: ¡Avenida bloqueada ({u} <-> {v})!")

    # 2. Despertar zombies dormidos si hay un sobreviviente a <= 2 nodos
    nodos_sobrevivientes_activos = {s.nodo_actual for s in MUNDO.sobrevivientes.values() if s.activo}
    for z in MUNDO.zombies.values():
        if z.activo and z.tipo == "dormido" and not z.despierto:
            cercanos = nodos_a_distancia_k(z.nodo_actual, 2, MUNDO.aristas_bloqueadas)
            if any(nodo in nodos_sobrevivientes_activos for nodo in cercanos):
                z.despertar(MUNDO.turno)
                MUNDO.eventos_log.append(f"Turno {MUNDO.turno}: Zombie {z.id} despertó en {z.nodo_actual}")


def _siguiente_paso_hacia_objetivo(origen: str, destino: str) -> str:
    """Devuelve el primer nodo de una ruta BFS desde origen hasta destino.

    BFS busca por número de aristas, no por distancia física ni tiempo de viaje.
    Se usa para que el corredor persiga a un objetivo. Si no hay ruta, devuelve
    `origen`, indicando que no debe avanzar hacia ese objetivo.
    """
    if origen == destino:
        return origen
    # Cada nodo visitado guarda su predecesor; None marca el inicio.
    visitados = {origen: None}
    # Cola FIFO para explorar primero los nodos más cercanos en cantidad de aristas.
    cola = [origen]
    while cola:
        # Extraer el primer nodo. Para grafos grandes, collections.deque sería más eficiente.
        actual = cola.pop(0)
        if actual == destino:
            break
        for vecino in ADYACENCIA.get(actual, {}):
            if (actual, vecino) not in MUNDO.aristas_bloqueadas and vecino not in visitados:
                visitados[vecino] = actual
                cola.append(vecino)
    if destino not in visitados:
        return origen
    # Reconstruir la ruta hacia atrás hasta encontrar el nodo inmediatamente
    # posterior al origen: ese es el siguiente paso que debe dar el corredor.
    paso = destino
    while visitados[paso] != origen and visitados[paso] is not None:
        paso = visitados[paso]
    return paso


def mover_zombis() -> None:
    """Actualiza las posiciones de los zombies según su tipo.

        Antes de mover cada zombie se guarda su posición anterior y se reinicia
        `nodos_recorridos_turno`; esta lista permite detectar cruces de calle con
        sobrevivientes al final del turno.
    """

    # Conjunto de posiciones ocupadas por sobrevivientes activos. Se usa comov objetivo de persecución de los corredores.
    nodos_sobrevivientes = {s.nodo_actual for s in MUNDO.sobrevivientes.values() if s.activo}

    for z in MUNDO.zombies.values():
        z.nodo_anterior = z.nodo_actual
        z.nodos_recorridos_turno = [z.nodo_actual]

        if not z.puede_moverse(MUNDO.turno):
            continue
        # Solo se consideran salidas no bloqueadas desde la posición actual.
        vecinos = [
            v for v in ADYACENCIA.get(z.nodo_actual, {})
            if (z.nodo_actual, v) not in MUNDO.aristas_bloqueadas
        ]
        if not vecinos:
            continue

        # Caminante: el método puede_moverse decide si le corresponde moverse
        # en este turno; al moverse elige una salida aleatoria.
        if z.tipo == "caminante":
            nuevo_nodo = random.choice(vecinos)
            z.nodo_actual = nuevo_nodo
            z.nodos_recorridos_turno.append(nuevo_nodo)
            z.turno_ultimo_movimiento = MUNDO.turno

        # Corredor: puede recorrer hasta dos aristas en el mismo turno.
        # En cada paso vuelve a buscar sobrevivientes cercanos desde su posición.
            # Corredor: puede recorrer hasta dos aristas en el mismo turno.
        elif z.tipo == "corredor":
            for paso_idx in range(2):
                vecinos_actuales = [
                    v for v in ADYACENCIA.get(z.nodo_actual, {})
                    if (z.nodo_actual, v) not in MUNDO.aristas_bloqueadas
                ]
                if not vecinos_actuales:
                    break

                # Si en el primer salto ya cayó sobre un sobreviviente, en el segundo
                # salto intenta anticipar hacia dónde escapará ese sobreviviente.
                if z.nodo_actual in nodos_sobrevivientes:
                    sobreviviente_aqui = next(
                        (s for s in MUNDO.sobrevivientes.values()
                         if s.activo and s.nodo_actual == z.nodo_actual),
                        None
                    )
                    if (
                            sobreviviente_aqui
                            and sobreviviente_aqui.siguiente_nodo in vecinos_actuales
                    ):
                        paso = sobreviviente_aqui.siguiente_nodo
                        z.nodo_actual = paso
                        z.nodos_recorridos_turno.append(paso)
                    break

                cercanos = nodos_a_distancia_k(z.nodo_actual, 3, MUNDO.aristas_bloqueadas)
                objetivos = [
                    (dist, nodo) for nodo, dist in cercanos.items()
                    if nodo in nodos_sobrevivientes and dist > 0
                ]

                if objetivos:
                    objetivos.sort()
                    paso = _siguiente_paso_hacia_objetivo(z.nodo_actual, objetivos[0][1])
                else:
                    paso = random.choice(vecinos_actuales)

                z.nodo_actual = paso
                z.nodos_recorridos_turno.append(paso)

                z.turno_ultimo_movimiento = MUNDO.turno

def _necesita_recalculo(
    s: Sobreviviente,
    nodos_prohibidos: set[str],
    penalizacion_riesgo: dict[str, float],
    aristas_invalidas_turno: set[tuple[str, str]],
    en_camino_por_refugio: dict[str, int],
) -> bool:
    if not s.ruta_planificada or len(s.ruta_planificada) < 2 or not s.siguiente_nodo:
        return True

    siguiente = s.siguiente_nodo
    actual = s.nodo_actual

    if siguiente not in ADYACENCIA.get(actual, {}):
        return True
    if (actual, siguiente) in aristas_invalidas_turno:
        return True
    if siguiente in nodos_prohibidos:
        return True
    if penalizacion_riesgo.get(siguiente, 0.0) > 0.0:
        return True

    if s.refugio_destino is not None:
        refugio = MUNDO.refugios.get(s.refugio_destino)
        if refugio is None or not refugio.tiene_espacio():
            return True
        # Si el refugio destino ya tiene su cupo sobrecargado por otros sobrevivientes
        # y este sobreviviente aún está lejos (> 5 calles), recalcula para buscar otro refugio.
        if (
            refugio.capacidad is not None
            and (refugio.ocupacion + en_camino_por_refugio.get(refugio.id, 0)) > refugio.capacidad
            and len(s.ruta_planificada) > 6
        ):
            return True

    # Validar que ningún tramo futuro de la ruta haya colapsado o caído en zona prohibida
    ruta = s.ruta_planificada
    for i in range(len(ruta) - 1):
        if (ruta[i], ruta[i + 1]) in MUNDO.aristas_bloqueadas:
            return True
        if ruta[i + 1] in nodos_prohibidos:
            return True

    return False


def mover_sobrevivientes() -> None:
    """Calcula y ejecuta un movimiento para cada sobreviviente activo."""
    lista_zombies = list(MUNDO.zombies.values())
    lista_refugios = list(MUNDO.refugios.values())

    # Se calcula UNA sola vez por turno para todos los sobrevivientes
    nodos_prohibidos, penalizacion_riesgo = calcular_zonas_peligro(
        lista_zombies,
        MUNDO.aristas_bloqueadas,
    )
    aristas_contraflujo = obtener_aristas_contraflujo_zombies(lista_zombies)
    aristas_invalidas_turno = MUNDO.aristas_bloqueadas | aristas_contraflujo

    # Contabilizar cuántos sobrevivientes activos van en camino a cada refugio
    en_camino_por_refugio: dict[str, int] = {r.id: 0 for r in lista_refugios}
    for s in MUNDO.sobrevivientes.values():
        if s.activo and s.refugio_destino in en_camino_por_refugio:
            en_camino_por_refugio[s.refugio_destino] += 1

    # Ordenar sobrevivientes priorizando a los que tienen ruta más corta al refugio,
    # para que los más cercanos aseguren su cupo primero y los lejanos se redistribuyan.
    sobrevivientes_activos = [s for s in MUNDO.sobrevivientes.values() if s.activo]
    sobrevivientes_activos.sort(
        key=lambda s: len(s.ruta_planificada) if len(s.ruta_planificada) > 1 else 9999
    )

    for s in sobrevivientes_activos:
        t0 = time.perf_counter()

        if _necesita_recalculo(
            s,
            nodos_prohibidos,
            penalizacion_riesgo,
            aristas_invalidas_turno,
            en_camino_por_refugio,
        ):
            # Restar temporalmente su reserva anterior antes de buscar nuevo refugio
            if s.refugio_destino in en_camino_por_refugio:
                en_camino_por_refugio[s.refugio_destino] = max(
                    0, en_camino_por_refugio[s.refugio_destino] - 1
                )

            ruta, ref_id = algoritmo_busqueda(
                s.nodo_actual,
                lista_refugios,
                lista_zombies,
                MUNDO.aristas_bloqueadas,
                nodos_prohibidos=nodos_prohibidos,
                penalizacion_riesgo=penalizacion_riesgo,
                en_camino_por_refugio=en_camino_por_refugio,
            )

            s.planificar_ruta(ruta, ref_id)

            # Registrar la nueva reserva de cupo en camino
            if ref_id in en_camino_por_refugio:
                en_camino_por_refugio[ref_id] += 1

            latencia_ms = (time.perf_counter() - t0) * 1000.0
            MUNDO.latencias_ms.append(latencia_ms)
        else:
            latencia_ms = (time.perf_counter() - t0) * 1000.0

        candidato = s.siguiente_nodo or s.nodo_actual

        # Validar conexión, bloqueos de mapa y que no sea un cruce frontal con un zombie
        es_vecino_valido = (
            candidato == s.nodo_actual
            or (
                candidato in ADYACENCIA.get(s.nodo_actual, {})
                and (s.nodo_actual, candidato) not in aristas_invalidas_turno
            )
        )

        nodo_seguro = (
            candidato == s.nodo_actual
            or candidato not in nodos_prohibidos
        )

        decision_valida = (
            latencia_ms <= 500.0
            and es_vecino_valido
            and nodo_seguro
        )

        if decision_valida:
            s.actualizar_posicion(candidato)
        else:
            s.actualizar_posicion(s.nodo_actual)
            if candidato != s.nodo_actual and (not es_vecino_valido or not nodo_seguro):
                s.ruta_planificada = []
                s.siguiente_nodo = None

        if s.refugio_destino is not None:
            refugio = MUNDO.refugios.get(s.refugio_destino)
            if refugio is None or not refugio.tiene_espacio():
                s.ruta_planificada = []
                s.siguiente_nodo = None
                s.refugio_destino = None


def comprobar_mordidas() -> None:
    """
    Elimina a los sobrevivientes que comparten nodo con un zombie
    o se cruzan con él en sentidos opuestos por la misma calle.

    Las hordas bloquean su nodo y sus vecinos para la navegación,
    pero estar en un nodo vecino no provoca una mordida automática.
    """

    for s in MUNDO.sobrevivientes.values():

        if not s.activo:
            continue

        for z in MUNDO.zombies.values():

            if not z.activo or not z.despierto:
                continue

            # 1. Mordida: terminan el turno en el mismo nodo.
            if s.nodo_actual == z.nodo_actual:
                s.morder()
                break

            # 2. Mordida: cruzaron la misma calle en sentidos opuestos.
            if s.nodo_anterior is None:
                continue

            recorrido_zombie = z.nodos_recorridos_turno

            for i in range(len(recorrido_zombie) - 1):
                z_origen = recorrido_zombie[i]
                z_destino = recorrido_zombie[i + 1]

                cruce_opuesto = (
                    s.nodo_anterior == z_destino
                    and s.nodo_actual == z_origen
                )

                if cruce_opuesto:
                    s.morder()
                    break

            if not s.activo:
                break


def gestionar_refugios() -> None:
    """Registra los rescates y actualiza la ocupación de los refugios."""
    refugios_por_nodo = {r.nodo: r for r in MUNDO.refugios.values() if r.activo}

    for s in MUNDO.sobrevivientes.values():
        if s.activo and s.nodo_actual in refugios_por_nodo:
            refugio = refugios_por_nodo[s.nodo_actual]
            if refugio.recibir_sobreviviente():
                s.rescatar()


def actualizar_estado() -> None:
    """Actualiza el estado general de la partida."""
    MUNDO.turno += 1


def comprobar_fin_simulacion() -> bool:
    """Determina si la partida terminó (no quedan sobrevivientes activos en las calles)."""
    activos = sum(1 for s in MUNDO.sobrevivientes.values() if s.activo)
    return activos == 0


def obtener_estado() -> dict:
    """
    Construye y devuelve una fotografía del estado actual de la simulación.

    Incluye:
    - Turno actual.
    - Métricas de sobrevivientes y latencia.
    - Zombies activos y visibles.
    - Sobrevivientes, sus posiciones y rutas planificadas.
    - Refugios y su estado.
    - Calles bloqueadas.

    Retorna:
        dict: Diccionario que FastAPI puede convertir en una respuesta JSON.
    """

    # 1. Calcular las métricas de los sobrevivientes

    # Cuenta a los sobrevivientes que siguen vivos y todavía
    # no han sido rescatados.
    activos = sum(
        1
        for s in MUNDO.sobrevivientes.values()
        if s.activo
    )

    # Cuenta a quienes llegaron a un refugio y fueron rescatados.
    rescatados = sum(
        1
        for s in MUNDO.sobrevivientes.values()
        if s.rescatado
    )
    # Los que no están activos ni rescatados se consideran mordidos.
    mordidos = len(MUNDO.sobrevivientes) - activos - rescatados

    # 2. Calcular el percentil 95 (p95) de las latencias
    # Ordena de menor a mayor los tiempos de decisión registrados.
    # Se utiliza una copia ordenada para no modificar la lista original.
    lat_ordenadas = sorted(MUNDO.latencias_ms)

    # Si existen mediciones, selecciona el valor ubicado en el índice
    # correspondiente al 95 % de la lista ordenada.
    # Si todavía no hay mediciones, devuelve 0.0.
    p95 = (
        lat_ordenadas[int(len(lat_ordenadas) * 0.95)]
        if lat_ordenadas
        else 0.0
    )

    # 3. Preparar los datos de los zombies

    # Incluye únicamente zombies activos y visibles.
    zombies_estado = [
        {
            "id": z.id,                    # Identificador único del zombie.
            "tipo": z.tipo,                # Caminante, corredor, horda o dormido.
            "nodo": z.nodo_actual,         # Nodo que ocupa en el mapa.
        }
        for z in MUNDO.zombies.values()
        if z.activo and z.visible
    ]

    # 4. Preparar los datos de los sobrevivientes

    # Se incluyen todos los sobrevivientes para que el frontend pueda
    # distinguir entre quienes siguen escapando, quienes fueron mordidos
    # y quienes ya llegaron a un refugio.
    sobrevivientes_estado = [
        {
            "id": s.id,                           # Identificador único.
            "nodo": s.nodo_actual,                # Posición actual.
            "nodoAnterior": s.nodo_anterior,      # Posición previa al último movimiento.
            "siguienteNodo": s.siguiente_nodo,    # Próximo paso de la ruta.
            "rutaPlanificada": s.ruta_planificada.copy(),
            # Se copia la lista para entregar los nodos de la ruta
            # sin exponer directamente la lista interna del objeto.
            "refugioDestino": s.refugio_destino,  # Refugio elegido actualmente.
            "activo": s.activo,                   # Si continúa escapando.
            "rescatado": s.rescatado,             # Si alcanzó un refugio.
        }
        for s in MUNDO.sobrevivientes.values()
    ]

    # 5. Preparar los datos de los refugios

    # Publica la ubicación, la capacidad y la ocupación de cada refugio.
    # El frontend podrá mostrar cuántos sobrevivientes han llegado
    # y cuántos todavía puede recibir cada refugio.
    refugios_estado = [
        {
            "id": r.id,  # Identificador único del refugio.
            "nodo": r.nodo,  # Nodo del grafo donde se encuentra.
            "activo": r.activo,  # Indica si el refugio está disponible.
            "capacidad": r.capacidad,  # Número máximo de sobrevivientes permitidos.
            "ocupacion": r.ocupacion,  # Número de sobrevivientes que ya recibió.
            "espaciosDisponibles": (
                max(0, r.capacidad - r.ocupacion)
                if r.capacidad is not None
                else None
            ),  # Espacios restantes; None significa capacidad ilimitada.
        }
        for r in MUNDO.refugios.values()
    ]

    # 6. Construir el estado completo de la simulación

    return {
        # Número del turno que se está ejecutando.
        "turno": MUNDO.turno,

        # Resumen numérico de la partida.
        "metricas": {
            "activos": activos,
            "rescatados": rescatados,
            "mordidos": mordidos,
            "latencia_p95_ms": round(p95, 3),
        },

        # Elementos que el frontend dibujará sobre el mapa.
        "zombies": zombies_estado,
        "sobrevivientes": sobrevivientes_estado,
        "refugios": refugios_estado,

        # Cada elemento representa una calle bloqueada entre dos nodos.
        # Ejemplo: [["N-0117", "N-0118"], ["N-0201", "N-0202"]].
        "aristasBloqueadas": [
            [origen, destino]
            for origen, destino in MUNDO.aristas_bloqueadas
        ]
    }


def ejecutar_turno() -> dict:
    """Coordina todas las acciones de un turno en el orden reglamentario."""
    actualizar_estado()
    procesar_eventos()
    mover_zombis()
    mover_sobrevivientes()
    comprobar_mordidas()
    gestionar_refugios()
    return obtener_estado()