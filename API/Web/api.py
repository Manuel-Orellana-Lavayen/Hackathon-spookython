import os
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware # Importamos el middleware de CORS para permitir que otras páginas (nuestro frontend HTML/JS) hagan peticiones a esta API sin ser bloqueadas por el navegador.
from pydantic import BaseModel, Field
from typing import Literal

# --- IMPORTACIONES LOCALES DEL SIMULADOR ---
from API.Elementos.FuncionesSimulador import comprobar_fin_simulacion, ejecutar_turno, inicializar_simulacion, obtener_estado
from API.Elementos.AlgoritmoBusqueda import algoritmo_busqueda
from API.Elementos.Grafo import ADYACENCIA, NODOS_COORDS
from API.Elementos import FuncionesSimulador as sim

API_KEY_ESPERADA = os.getenv("APOCALIPSIS_API_KEY", "clave-desarrollo-local")

def verificar_api_key(x_api_key: str = Header(..., alias="x-api-key")):
    if x_api_key != API_KEY_ESPERADA:
        raise HTTPException(status_code=401, detail="API Key inválida o faltante")
app = FastAPI()

# Añadimos el middleware de CORS (Intercambio de Recursos de Origen Cruzado).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite peticiones desde cualquier origen.
    allow_methods=["*"],  # Permite todos los métodos HTTP (GET, POST, etc.).
    allow_headers=["*"],  # Permite todos los encabezados personalizados
)

# Definimos la estructura exacta del cuerpo (JSON body) que esperamos recibir.
class PeticionPaso(BaseModel):
    sobrevivienteId: str
    nodoActual: str
    turno: int  # El número del turno actual.


# Diccionario que actúa como base de datos estática para la configuración oficial de las rondas de la "Prueba de Fuego".
RONDAS_CONFIG = {
    "1": {"sobrevivientes": 20, "zombies": {"caminante": 15, "corredor": 0, "horda": 0, "dormido": 0}, "semilla": 101,
          "eventos": {}},  # Ronda 1: Sin eventos climáticos ni de bloqueos.
    "2": {"sobrevivientes": 80, "zombies": {"caminante": 20, "corredor": 4, "horda": 2, "dormido": 0}, "semilla": 111,
          "eventos": {15: "puente"}},  # Ronda 2: Colapso de puente programado en el turno 15.
    "3": {"sobrevivientes": 200, "zombies": {"caminante": 30, "corredor": 8, "horda": 3, "dormido": 10},
          "semilla": 1053, "eventos": {10: "calle", 30: "calle"}}
}


# -----------------------------------------------------------------------------
# ENDPOINT que es consultado por cada sobreviviente para decidir a dónde moverse.
# -----------------------------------------------------------------------------
from API.Elementos.AlgoritmoBusqueda import calcular_zonas_peligro, obtener_aristas_contraflujo_zombies


@app.post("/paso", dependencies=[Depends(verificar_api_key)])
def calcular_paso(peticion: PeticionPaso):
    s = sim.MUNDO.sobrevivientes.get(peticion.sobrevivienteId)

    if not s or not s.activo:
        return {"siguienteNodo": peticion.nodoActual}

    # 1. Reconstruir el estado de peligro (idéntico al simulador)
    lista_zombies = list(sim.MUNDO.zombies.values())
    lista_refugios = list(sim.MUNDO.refugios.values())

    nodos_prohibidos, penalizacion_riesgo = calcular_zonas_peligro(lista_zombies, sim.MUNDO.aristas_bloqueadas)

    # 2. Contabilizar ocupación en camino para evitar la estampida
    en_camino_por_refugio = {r.id: 0 for r in lista_refugios}
    for sob in sim.MUNDO.sobrevivientes.values():
        if sob.activo and sob.refugio_destino in en_camino_por_refugio:
            en_camino_por_refugio[sob.refugio_destino] += 1

    # 3. Ejecutar A* con las mismas reglas
    ruta, ref_id = algoritmo_busqueda(
        peticion.nodoActual,
        lista_refugios,
        lista_zombies,
        sim.MUNDO.aristas_bloqueadas,
        nodos_prohibidos=nodos_prohibidos,
        penalizacion_riesgo=penalizacion_riesgo,
        en_camino_por_refugio=en_camino_por_refugio
    )

    siguiente = ruta[1] if len(ruta) > 1 else peticion.nodoActual
    return {"siguienteNodo": siguiente}

# -----------------------------------------------------------------------------
# ENDPOINT DE VISUALIZACIÓN: Alimenta el mapa web con posiciones geográficas en vivo.
# -----------------------------------------------------------------------------
@app.get("/estado", dependencies=[Depends(verificar_api_key)])
def obtener_estado_actual():
    # Obtenemos las métricas puras y el recuento del simulador.
    estado = obtener_estado()

    # Preparamos una lista para inyectar coordenadas precisas al frontend.
    estado["sobrevivientes"] = []
    for s in sim.MUNDO.sobrevivientes.values():
        # Descartamos enviar datos de sobrevivientes que ya fueron rescatados para aliviar la red.
        if not s.rescatado:
            # Extraemos Lat/Lng de cada nodo de la ruta planificada para que Leaflet dibuje la trayectoria cian.
            ruta_coords = [[NODOS_COORDS[n][0], NODOS_COORDS[n][1]] for n in s.ruta_planificada] if s.activo else []

            estado["sobrevivientes"].append({
                "id": s.id,
                "lat": NODOS_COORDS[s.nodo_actual][0],  # Latitud geográfica del OSM
                "lng": NODOS_COORDS[s.nodo_actual][1],  # Longitud geográfica del OSM
                "mordido": not s.activo,                # Si no está activo (pero no ha sido rescatado), es una baja.
                "ruta": ruta_coords                     # Puntos de la polilínea en Leaflet.
            })

    # Empaquetamos los refugios con su localización, capacidad y ocupación para la leyenda en el mapa.
    estado["refugios"] = [
        {"id": r.id, "lat": NODOS_COORDS[r.nodo][0], "lng": NODOS_COORDS[r.nodo][1], "ocupacion": r.ocupacion,
         "capacidad": r.capacidad}
        for r in sim.MUNDO.refugios.values()
    ]

    # Lista para rastrear los nodos de bloqueo/peligro de las Hordas.
    zonas_horda = []
    for z in estado["zombies"]:
        # Agregamos Lat/Lng directamente al objeto zombie enviado previamente por el simulador.
        z["lat"] = NODOS_COORDS[z["nodo"]][0]
        z["lng"] = NODOS_COORDS[z["nodo"]][1]

        # Regla del Reto: Si el zombie es una Horda, afecta su nodo y TODOS los vecinos conectados.
        if z["tipo"] == "horda":
            afectados = set([z["nodo"]])
            # Vecinos de salida
            afectados.update(ADYACENCIA.get(z["nodo"], {}).keys())
            # Vecinos de entrada (calles que apuntan hacia la horda)
            for u, vecinos_u in ADYACENCIA.items():
                if z["nodo"] in vecinos_u:
                    afectados.add(u)

            # Convertimos a coordenadas
            zonas_horda.extend([{"lat": NODOS_COORDS[n][0], "lng": NODOS_COORDS[n][1]} for n in afectados])

    estado["zonas_horda"] = zonas_horda

    # Convertimos los pares de nodos bloqueados (u, v) en segmentos espaciales para marcarlos en el grafo web.
    bloqueos = []
    for u, v in sim.MUNDO.aristas_bloqueadas:
        if u in NODOS_COORDS and v in NODOS_COORDS:
            bloqueos.append([[NODOS_COORDS[u][0], NODOS_COORDS[u][1]], [NODOS_COORDS[v][0], NODOS_COORDS[v][1]]])

    estado["bloqueos_coords"] = bloqueos              # Envia la lista geométrica de desastres viales.
    estado["eventos_log"] = sim.MUNDO.eventos_log[-3:]    # Extrae las últimas 3 líneas del log de consola.
    estado["terminado"] = comprobar_fin_simulacion()  # Check booleano (True) si el motor dictaminó el final.

    return estado


# -----------------------------------------------------------------------------
# ENDPOINT DE CONTROL: Reinicia el motor interno cargando la configuración base.
# -----------------------------------------------------------------------------
@app.post("/iniciar/{ronda}", dependencies=[Depends(verificar_api_key)])
def iniciar_ronda(ronda: str):
    cfg = RONDAS_CONFIG.get(ronda, RONDAS_CONFIG["1"])

    sim.inicializar_simulacion(
        num_sobrevivientes=cfg["sobrevivientes"],
        config_zombies=cfg["zombies"],
        semilla=cfg["semilla"]
    )
    return {"mensaje": f"Ronda {ronda} inicializada"}


# -----------------------------------------------------------------------------
# ENDPOINT DE MOTOR: Avanza el reloj de la simulación paso a paso.
# -----------------------------------------------------------------------------
@app.post("/avanzar", dependencies=[Depends(verificar_api_key)])
def avanzar_turno():
    # Llama a coordinar un turno global (mover zombies -> sobrevivientes -> resolver mordidas).
    if not comprobar_fin_simulacion():
        ejecutar_turno()
    # Retorna inmediatamente la "fotografia" post-turno para que JS renderice los cambios.
    return obtener_estado_actual()


# -----------------------------------------------------------------------------
# ENDPOINT DE MAPA: Envia una sola vez el esqueleto vial para dibujar la malla de fondo.
# -----------------------------------------------------------------------------
@app.get("/grafo", dependencies=[Depends(verificar_api_key)])
def obtener_geometria_grafo():
    calles = []
    # Recorre toda la caché RAM del grafo (ADYACENCIA).
    for u, vecinos in ADYACENCIA.items():
        for v, datos in vecinos.items():
            # Extrae la lat/lng de inicio y fin y el tipo de vía ("calle", "avenida", "puente").
            calles.append({
                "lat1": NODOS_COORDS[u][0], "lng1": NODOS_COORDS[u][1],
                "lat2": NODOS_COORDS[v][0], "lng2": NODOS_COORDS[v][1],
                "tipo": datos["tipo"]
            })
    # Este array masivo permite que el frontend no dependa de OSMnx ni Python para dibujar el trazado gris del mapa.
    return {"calles": calles}


# ---------------------------
# PARTIDAS PERSONALIZADAS
# ---------------------------

class ConfiguracionPersonalizada(BaseModel):
    sobrevivientes: int = Field(ge=1, le=1000)
    caminantes: int = Field(default=20, ge=0, le=1000)
    corredores: int = Field(default=8, ge=0, le=1000)
    hordas: int = Field(default=3, ge=0, le=100)
    dormidos: int = Field(default=0, ge=0, le=1000)

    semilla: int = Field(default=111, ge=0, le=2**32 - 1)

    turno_evento: int = Field(default=0, ge=0, le=10000)
    tipo_evento: Literal["puente", "calle"] = "puente"

@app.post("/simulacion-personalizada", dependencies=[Depends(verificar_api_key)])
def iniciar_simulacion_personalizada(cfg: ConfiguracionPersonalizada):
    sim.inicializar_simulacion(
        num_sobrevivientes=cfg.sobrevivientes,
        config_zombies={
            "caminante": cfg.caminantes,
            "corredor": cfg.corredores,
            "horda": cfg.hordas,
            "dormido": cfg.dormidos,
        },
        semilla=cfg.semilla,
    )
    return {"mensaje": "Simulación personalizada inicializada"}
app.mount("/", StaticFiles(directory=".", html=True), name="static")