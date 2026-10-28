from dataclasses import dataclass, field

@dataclass
class Sobreviviente:
    """
    Representa a una persona que intenta escapar del mapa y llegar a un refugio.

    El sobreviviente mantiene su posición actual, la posición anterior, el refugio al que se dirige y la ruta que debe seguir.
    """
    id: str
    nodo_actual: str
    nodo_anterior: str | None = None
    refugio_destino: str | None = None
    ruta_planificada: list[str] = field(default_factory=list)
    siguiente_nodo: str | None = None
    activo: bool = True
    rescatado: bool = False

    def planificar_ruta(self, ruta: list[str], refugio_id: str) -> None:
        """
            Guarda la ruta calculada por el algoritmo y asigna el refugio destino.

            Parámetros:
                ruta:
                     Lista ordenada de nodos que debe recorrer el sobreviviente.
                refugio_id:
                    Identificador del refugio seleccionado.
        """
        self.ruta_planificada = list(ruta)
        self.refugio_destino = refugio_id
        self.siguiente_nodo = ruta[1] if len(ruta) > 1 else self.nodo_actual

    def actualizar_posicion(self, nodo: str) -> None:
        """
            Actualiza la posición del sobreviviente después de un movimiento.
            También sincroniza la ruta planificada para eliminar los nodos que ya fueron recorridos y determina el siguiente nodo.
        """

        # Guarda la posición anterior antes de actualizarla.
        self.nodo_anterior = self.nodo_actual
        self.nodo_actual = nodo

        # Elimina de la ruta los nodos que ya quedaron atrás.
        while self.ruta_planificada and self.ruta_planificada[0] != nodo:
            self.ruta_planificada.pop(0)

        # Si todavía quedan nodos por recorrer, el siguiente es el segundo elemento de la ruta
        if len(self.ruta_planificada) > 1:
            self.siguiente_nodo = self.ruta_planificada[1]
        else:
            self.siguiente_nodo = None

    def morder(self) -> None:
        """
        Marca al sobreviviente como eliminado después de ser mordido. Se desactiva y se elimina cualquier movimiento pendiente.
        """
        self.activo = False
        self.siguiente_nodo = None
        self.ruta_planificada.clear()

    def rescatar(self) -> None:
        """
        Marca al sobreviviente como rescatado después de llegar a un refugio.
        Un sobreviviente rescatado deja de participar en los movimientos normales de la simulación.
        """
        self.rescatado = True
        self.activo = False
        self.siguiente_nodo = None
        self.ruta_planificada.clear()


@dataclass
class Zombie:
    """
       Representa a un zombie dentro de la simulación.

       Existen cuatro tipos principales:
           - caminante: se mueve lentamente.
           - corredor: se mueve rápidamente y puede perseguir sobrevivientes.
           - horda: permanece prácticamente inmóvil y bloquea una zona.
           - dormido: caminante que permanece oculto hasta detectar un sobreviviente cercano.
    """
    id: str
    tipo: str  # "caminante", "corredor", "horda", "dormido"
    nodo_actual: str
    nodo_anterior: str | None = None
    nodos_recorridos_turno: list[str] = field(default_factory=list)
    activo: bool = True
    visible: bool = True
    despierto: bool = True
    turno_ultimo_movimiento: int = -2

    def __post_init__(self) -> None:
        """
        Configura automáticamente el estado inicial de un zombie dormido.

        Los zombies dormidos comienzan invisibles y no pueden moverse hasta que un sobreviviente se encuentre suficientemente cerca.
        """
        if self.tipo == "dormido":
            self.visible = False
            self.despierto = False

    def despertar(self, turno_actual: int) -> None:
        """
        Despierta a un zombie dormido.
        Al despertar se vuelve visible y pasa a comportarse como un zombie caminante.
        """
        self.despierto = True
        self.visible = True
        self.tipo = "caminante"
        self.turno_ultimo_movimiento = turno_actual - 1
    def puede_moverse(self, turno: int) -> bool:
        """
            Determina si el zombie puede realizar un movimiento en el turno actual.

            Parámetros:
                turno:
                    Número del turno actual de la simulación.

            Retorna:
                True si el zombie puede moverse.
                False si debe permanecer en su posición.
        """
        # Zombies eliminados o dormidos no pueden moverse.
        if not self.activo or not self.despierto:
            return False
        # Los caminantes se mueven solamente cada dos turnos.
        if self.tipo == "caminante":
            return (turno - self.turno_ultimo_movimiento) >= 2
        # Los corredores pueden moverse en cada turno
        if self.tipo == "corredor":
            return True
        # Las hordas permanecen inmóviles.
        if self.tipo == "horda":
            return False
        return False


@dataclass
class Refugio:
    """
        Representa un punto seguro al que los sobrevivientes pueden llegar.

        Un refugio está ubicado en un nodo específico del grafo y puede
        tener una capacidad máxima de sobrevivientes.
    """
    id: str
    nodo: str
    capacidad: int | None = None
    ocupacion: int = 0
    activo: bool = True

    def tiene_espacio(self) -> bool:
        """
            Comprueba si el refugio puede recibir a otro sobreviviente.

            Retorna:
                True si está activo y tiene espacio disponible.
                False si está inactivo o lleno.
        """
        if not self.activo:
            return False
        # Si capacidad es None, el refugio no tiene límite.
        return self.capacidad is None or self.ocupacion < self.capacidad

    def recibir_sobreviviente(self) -> bool:
        """
            Intenta ingresar un sobreviviente al refugio.

            Retorna:
                True si el sobreviviente pudo ingresar.
                False si el refugio está lleno o inactivo.
        """
        if not self.tiene_espacio():
            return False
        self.ocupacion += 1
        return True