import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from Elementos.Grafo import NODOS_COORDS, ADYACENCIA
from Pruebas import FuncionesSimulador as simulador

# Configuraciones de las 3 rondas oficiales para cambiar con el teclado (Teclas 1, 2, 3)
RONDAS = {
    "1": {
        "nombre": "Ronda 1 - Anochecer (20 Sobrevivientes)",
        "sobrevivientes": 20,
        "zombies": {"caminante": 15, "corredor": 0, "horda": 0, "dormido": 0},
        "semilla": 101,
    },
    "2": {
        "nombre": "Ronda 2 - Medianoche (80 Sobrevivientes)",
        "sobrevivientes": 80,
        "zombies": {"caminante": 20, "corredor": 8, "horda": 3, "dormido": 0},
        "semilla": 111,
    },
    "3": {
        "nombre": "Ronda 3 - Apocalipsis (200 Sobrevivientes)",
        "sobrevivientes": 200,
        "zombies": {"caminante": 30, "corredor": 15, "horda": 5, "dormido": 15},
        "semilla": 103,
    },
    "4": {
            "nombre": "Ronda 4 - Apocalipsis (1 Sobrevivientes)",
            "sobrevivientes": 1,
            "zombies": {"caminante": 3, "corredor": 1, "horda": 1, "dormido": 11},
            "semilla": 104,
        },
}


class VisualizadorApocalipsis:
    def __init__(self, ronda_inicial: str = "2"):
        plt.style.use("dark_background")
        self.fig, self.ax = plt.subplots(figsize=(13, 9))
        self.fig.canvas.manager.set_window_title("Simulador Zombie Manta - Vista de Grafo")

        self.pausado = False
        self.ronda_actual = ronda_inicial
        self.velocidad_pausa = 0.6  # Segundos entre turnos

        # Temporizador gestionado por Matplotlib
        self.timer = self.fig.canvas.new_timer(
            interval=int(self.velocidad_pausa * 1000)
        )
        self.timer.add_callback(self._tick)


        # Conectar controles de teclado
        self.fig.canvas.mpl_connect("key_press_event", self.al_presionar_tecla)

        # Pre-calcular geometría estática del grafo (X = longitud, Y = latitud)
        self.segmentos_avenidas = []
        self.segmentos_calles = []
        self.segmentos_callejones = []
        self.segmentos_puentes = []

        for u, vecinos in ADYACENCIA.items():
            lat_u, lon_u = NODOS_COORDS[u]
            for v, datos in vecinos.items():
                lat_v, lon_v = NODOS_COORDS[v]
                seg = [(lon_u, lat_u), (lon_v, lat_v)]
                tipo = datos["tipo"]
                if tipo == "puente":
                    self.segmentos_puentes.append(seg)
                elif tipo == "avenida":
                    self.segmentos_avenidas.append(seg)
                elif tipo == "callejon":
                    self.segmentos_callejones.append(seg)
                else:
                    self.segmentos_calles.append(seg)

        self.todos_lons = [coord[1] for coord in NODOS_COORDS.values()]
        self.todos_lats = [coord[0] for coord in NODOS_COORDS.values()]

        self.cargar_ronda(self.ronda_actual)

    def _tick(self):
        """Actualización periódica de la simulación."""
        if self.pausado:
            return True

        try:
            if simulador.comprobar_fin_simulacion():
                self.pausado = True
                self.dibujar_estado()
                return True

            self.avanzar_turno()

        except Exception:
            import traceback
            self.pausado = True
            traceback.print_exc()
            self.timer.stop()

        return True

    def cargar_ronda(self, clave_ronda: str) -> None:
        if clave_ronda not in RONDAS:
            return

        self.ronda_actual = clave_ronda
        cfg = RONDAS[clave_ronda]

        simulador.inicializar_simulacion(
            num_sobrevivientes=cfg["sobrevivientes"],
            config_zombies=cfg["zombies"],
            semilla=cfg["semilla"],
        )

        self.dibujar_estado()

    def avanzar_turno(self) -> None:
        """Ejecuta un turno y actualiza la visualización."""
        try:
            if simulador.comprobar_fin_simulacion():
                self.dibujar_estado()
                return

            simulador.ejecutar_turno()
            self.dibujar_estado()

        except Exception:
            import traceback
            self.pausado = True
            traceback.print_exc()
            self.timer.stop()

    def al_presionar_tecla(self, event) -> None:
        if event.key == " ":
            self.pausado = not self.pausado

        elif event.key == "right":
            # Avanza exactamente un turno al pulsar la flecha.
            self.avanzar_turno()

        elif event.key in ("1", "2", "3"):
            self.cargar_ronda(event.key)

        elif event.key == "r":
            self.cargar_ronda(self.ronda_actual)

        elif event.key == "up":
            self.velocidad_pausa = max(
                0.05, self.velocidad_pausa - 0.15
            )

        elif event.key == "down":
            self.velocidad_pausa = min(
                2.0, self.velocidad_pausa + 0.15
            )

        self.timer.interval = int(self.velocidad_pausa * 1000)
        self.dibujar_estado()

    def dibujar_estado(self) -> None:
        self.ax.clear()
        mundo = simulador.MUNDO

        # 1. Dibujar las aristas (calles) por tipo
        self.ax.add_collection(
            LineCollection(self.segmentos_callejones, colors="#2b2b2b", linewidths=0.8, alpha=0.7, zorder=1)
        )
        self.ax.add_collection(
            LineCollection(self.segmentos_calles, colors="#444444", linewidths=1.3, alpha=0.8, zorder=1)
        )
        self.ax.add_collection(
            LineCollection(self.segmentos_avenidas, colors="#666666", linewidths=2.2, alpha=0.9, zorder=1)
        )
        self.ax.add_collection(
            LineCollection(self.segmentos_puentes, colors="#38bdf8", linewidths=2.8, alpha=0.9, zorder=2)
        )

        # 2. Dibujar intersecciones (nodos del grafo)
        self.ax.scatter(self.todos_lons, self.todos_lats, c="#555555", s=8, alpha=0.6, zorder=2)

        # 3. Dibujar calles o puentes bloqueados en vivo
        if mundo.aristas_bloqueadas:
            seg_bloqueados = []
            for u, v in mundo.aristas_bloqueadas:
                if u in NODOS_COORDS and v in NODOS_COORDS:
                    lat_u, lon_u = NODOS_COORDS[u]
                    lat_v, lon_v = NODOS_COORDS[v]
                    seg_bloqueados.append([(lon_u, lat_u), (lon_v, lat_v)])
            self.ax.add_collection(
                LineCollection(seg_bloqueados, colors="#ef4444", linewidths=3.5, linestyles="dashed", zorder=4)
            )

        # 4. Dibujar rutas planificadas de los sobrevivientes activos
        segmentos_rutas = []
        for s in mundo.sobrevivientes.values():
            if s.activo and len(s.ruta_planificada) > 1:
                for i in range(len(s.ruta_planificada) - 1):
                    u, v = s.ruta_planificada[i], s.ruta_planificada[i + 1]
                    lat_u, lon_u = NODOS_COORDS[u]
                    lat_v, lon_v = NODOS_COORDS[v]
                    segmentos_rutas.append([(lon_u, lat_u), (lon_v, lat_v)])
        if segmentos_rutas:
            self.ax.add_collection(
                LineCollection(segmentos_rutas, colors="#00ffcc", linewidths=1.2, alpha=0.35, zorder=3)
            )

        # 5. Dibujar área de bloqueo de las Hordas (su nodo + todos sus vecinos)
        lons_horda_zona, lats_horda_zona = [], []
        for z in mundo.zombies.values():
            if z.activo and z.tipo == "horda":
                nodos_afectados = [z.nodo_actual] + list(ADYACENCIA.get(z.nodo_actual, {}).keys())
                for n in nodos_afectados:
                    lat, lon = NODOS_COORDS[n]
                    lons_horda_zona.append(lon)
                    lats_horda_zona.append(lat)
        if lons_horda_zona:
            self.ax.scatter(
                lons_horda_zona, lats_horda_zona, c="#a855f7", s=260, alpha=0.22, edgecolors="none", zorder=3
            )

        # 6. Dibujar Refugios y su ocupación/capacidad
        for r in mundo.refugios.values():
            lat, lon = NODOS_COORDS[r.nodo]
            color_ref = "#22c55e" if r.tiene_espacio() else "#eab308"
            self.ax.scatter([lon], [lat], c=color_ref, s=220, marker="s", edgecolors="white", linewidths=1.5, zorder=6)
            self.ax.annotate(
                f"{r.id}\n({r.ocupacion}/{r.capacidad})",
                (lon, lat),
                textcoords="offset points",
                xytext=(0, 12),
                ha="center",
                fontsize=8,
                fontweight="bold",
                color="white",
                bbox=dict(boxstyle="round,pad=0.2", fc="#111827", ec=color_ref, alpha=0.85),
                zorder=8,
            )

        # 7. Dibujar Sobrevivientes (Activos vs Mordidos)
        lons_act, lats_act = [], []
        lons_mor, lats_mor = [], []
        for s in mundo.sobrevivientes.values():
            lat, lon = NODOS_COORDS[s.nodo_actual]
            if s.activo:
                lons_act.append(lon)
                lats_act.append(lat)
            elif not s.rescatado:
                lons_mor.append(lon)
                lats_mor.append(lat)

        if lons_mor:
            self.ax.scatter(lons_mor, lats_mor, c="#991b1b", s=45, marker="x", alpha=0.7, zorder=4)
        if lons_act:
            self.ax.scatter(
                lons_act, lats_act, c="#00ffff", s=55, marker="o", edgecolors="black", linewidths=0.7, zorder=7
            )

        # 8. Dibujar Zombies por tipo
        tipos_estilo = {
            "caminante": {"color": "#f97316", "size": 70, "marker": "^"},
            "corredor": {"color": "#ef4444", "size": 95, "marker": "D"},
            "horda": {"color": "#d946ef", "size": 180, "marker": "h"},
            "dormido": {"color": "#9ca3af", "size": 45, "marker": "v"},
        }
        for tipo, est in tipos_estilo.items():
            lons_z, lats_z = [], []
            for z in mundo.zombies.values():
                if z.activo and z.tipo == tipo:
                    lat, lon = NODOS_COORDS[z.nodo_actual]
                    lons_z.append(lon)
                    lats_z.append(lat)
            if lons_z:
                self.ax.scatter(
                    lons_z,
                    lats_z,
                    c=est["color"],
                    s=est["size"],
                    marker=est["marker"],
                    edgecolors="black",
                    linewidths=0.8,
                    zorder=6,
                )

        # 9. Métricas en el encabezado y eventos recientes
        activos = sum(1 for s in mundo.sobrevivientes.values() if s.activo)
        rescatados = sum(1 for s in mundo.sobrevivientes.values() if s.rescatado)
        mordidos = len(mundo.sobrevivientes) - activos - rescatados
        lat_ord = sorted(mundo.latencias_ms)
        p95 = lat_ord[int(len(lat_ord) * 0.95)] if lat_ord else 0.0

        estado_txt = "PAUSADO (Usa Flecha Derecha para avanzar 1 turno)" if self.pausado else "EN VIVO"
        self.ax.set_title(
            f"{RONDAS[self.ronda_actual]['nombre']}  |  Turno: {mundo.turno:03d}  [{estado_txt}]\n"
            f"Vivos en calle: {activos}   |   Rescatados: {rescatados}   |   "
            f"Mordidos: {mordidos}   |   Latencia p95: {p95:.2f} ms",
            fontsize=11,
            fontweight="bold",
            color="#f8fafc",
            pad=12,
        )

        # Mostrar últimos eventos de ciudad abajo a la izquierda
        ultimos_eventos = "\n".join(mundo.eventos_log[-3:]) if mundo.eventos_log else "Sin eventos de ciudad aún"
        self.ax.text(
            0.01,
            0.02,
            f"EVENTOS RECIENTES:\n{ultimos_eventos}\n\n"
            f"CONTROLES: [Espacio] Pausar/Reanudar | [->] Avanzar 1 turno | [1/2/3] Cambiar Ronda | [R] Reiniciar",
            transform=self.ax.transAxes,
            fontsize=8.5,
            color="#e2e8f0",
            bbox=dict(boxstyle="round,pad=0.4", fc="#0f172a", ec="#334155", alpha=0.9),
            zorder=10,
        )

        # Leyenda visual
        leyenda = [
            Line2D([0], [0], marker="s", color="w", label="Refugio (Ocup/Cap)", markerfacecolor="#22c55e", markersize=9, linestyle="None"),
            Line2D([0], [0], marker="o", color="w", label="Sobreviviente + Ruta A*", markerfacecolor="#00ffff", markersize=7, linestyle="-"),
            Line2D([0], [0], marker="^", color="w", label="Zombie Caminante", markerfacecolor="#f97316", markersize=8, linestyle="None"),
            Line2D([0], [0], marker="D", color="w", label="Zombie Corredor (2 calles)", markerfacecolor="#ef4444", markersize=8, linestyle="None"),
            Line2D([0], [0], marker="h", color="w", label="Horda (+ Zona Vecinos)", markerfacecolor="#d946ef", markersize=10, linestyle="None"),
            Line2D([0], [0], marker="v", color="w", label="Zombie Dormido (Oculto)", markerfacecolor="#9ca3af", markersize=7, linestyle="None"),
            Line2D([0], [0], color="#ef4444", lw=2.5, ls="--", label="Calle / Puente Colapsado"),
        ]
        self.ax.legend(handles=leyenda, loc="upper right", fontsize=8, framealpha=0.85, facecolor="#0f172a")

        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.fig.tight_layout()
        self.fig.canvas.draw_idle()

    def iniciar(self) -> None:
        plt.ion()
        self.timer.start()
        plt.show(block=False)

        try:
            while plt.fignum_exists(self.fig.number):
                plt.pause(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            self.timer.stop()


if __name__ == "__main__":
    vis = VisualizadorApocalipsis(ronda_inicial="2")
    vis.iniciar()