Apocalipsis Manta — Simulador Táctico de Supervivencia Urbana

Plataforma de simulación en tiempo real y motor inteligente de evacuación urbana sobre el grafo vial real de **Manta, Ecuador** (OpenStreetMap). Con recálculo dinámico ante colapsos viales, predicción de zombies corredores y balanceo de carga en refugios.

---

## Links de Entrega
- **Web Desplegada (Mapa en Vivo):** ``
- **Documentación Interactiva API (Swagger):** ``
- **Región de AWS utilizada:** `us-east-1` (N. Virginia)

---

## Arquitectura y Decisiones Técnicas (Por qué ganamos en Latencia)

Para evitar las trampas clásicas de arquitecturas serverless en simulaciones por turnos (como el estado fragmentado entre instancias de AWS Lambda o los *cold starts* > 500 ms en la Ronda 3 con 200 sobrevivientes simultáneos), diseñamos una arquitectura **Stateful In-Memory sobre Amazon EC2**:

1. **Pre-cálculo del Grafo en RAM (`Grafo.py`):** Al iniciar el servidor, el archivo `mapa_manta_300.graphml` se transforma en diccionarios nativos de adyacencia (`O(1)` de acceso) con costos precalculados en segundos según la velocidad de cada vía (`avenida`: 5.0 m/s, `puente`: 4.5 m/s, `calle`: 3.5 m/s, `callejon`: 2.0 m/s).
2. **Cálculo Unificado de Zonas de Peligro (`AlgoritmoBusqueda.py`):** En lugar de recalcular el mapa de calor de zombies 200 veces por turno, las zonas de peligro y las aristas de contraflujo se calculan una sola vez al inicio del movimiento de los sobrevivientes.
3. **Invalidación Selectiva de Rutas (`FuncionesSimulador.py`):** Cada sobreviviente audita su ruta planificada en cada turno (`_necesita_recalculo`). Solo ejecuta `A*` si:
   - Una calle o puente de su ruta futura colapsó en vivo.
   - Su siguiente paso o ruta entró en el radio de bloqueo de una **Horda** (nodo central + todos sus vecinos de entrada y salida) o en la zona de caza de un **Corredor**.
   - Su refugio destino alcanzó el límite de capacidad física o proyectada.
4. **Latencia p95 obtenida:** **< 15 ms** 

---

## Funcionalidades Nivel Pro Implementadas

- **Predicción de Corredores:** Mediante búsqueda en anchura (`BFS` a distancia $k \le 2$), el algoritmo anticipa todos los nodos que un corredor puede alcanzar en su próximo turno y aplica penalizaciones graduadas de riesgo (+500 en salto 1, +150 en salto 2) en la función de costo de `A*`.
- **Control de Capacidad y Prevención de Estampidas:** El motor rastrea tanto la `ocupacion` actual como los sobrevivientes `en_camino_por_refugio`. Los sobrevivientes más cercanos aseguran su cupo primero y los más lejanos reciben una penalización de congestión dinámica que los redistribuye automáticamente hacia refugios con espacio libre.
- **Prevención de Mordidas por Cruce Opuesto:** El motor registra el vector de desplazamiento `(origen -> destino)` de cada zombie en el turno actual y bloquea temporalmente la arista inversa `(destino -> origen)` para evitar choques frontales.

---

## 🔌 Contrato Técnico y Endpoints

Autenticación requerida en todos los endpoints mediante cabecera:
`x-api-key: <TU_API_KEY>` (Por defecto en entorno local: `clave-desarrollo-local`).

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/paso` | **Contrato Oficial:** Recibe `{"sobrevivienteId": "S-0089", "nodoActual": "N-0117", "turno": 142}` y responde `{"siguienteNodo": "N-0118"}` en < 50 ms. |
| `GET` | `/estado` | Devuelve turno, métricas (activos, rescatados, mordidos, latencia p95), posiciones de zombies visibles, sobrevivientes con rutas, refugios y `aristasBloqueadas`. |
| `POST` | `/iniciar/{ronda}` | Inicializa las rondas oficiales de la Prueba de Fuego (`1`: Anochecer, `2`: Medianoche, `3`: Apocalipsis). |
| `POST` | `/avanzar` | Ejecuta un turno completo (Eventos → Zombies → Sobrevivientes → Mordidas → Refugios) y retorna el estado actualizado. |
| `POST` | `/simulacion-personalizada` | Permite al jurado calibrar en vivo la cantidad de sobrevivientes, zombies por tipo, semilla y turno/tipo de colapso vial. |
| `GET` | `/grafo` | Entrega la geometría vial clasificada para el renderizado en Leaflet.js. |

---

## Declaración de Costos y Presupuesto en AWS

- **Servicio utilizado:** 1 instancia Amazon EC2 `t3.micro` (2 vCPUs, 1 GB RAM, 8 GB EBS gp3) en la región `us-east-1`.
- **Costo por hora:** USD $0.0104 / hora (cubierto al 100 % por los créditos del Free Tier de AWS).
- **Costo total acumulado durante el reto:** **USD $0.00** (Consumo bruto estimado < USD $0.50).

### Captura de AWS Budgets (Alerta configurada desde el Día 1)

![AWS Budget Alert](./imagenes/budget.png)

---

##  Ejecución Local

```bash
# 1. Clonar el repositorio
git clone [https://github.com/TU_USUARIO/TU_REPOSITORIO.git](https://github.com/TU_USUARIO/TU_REPOSITORIO.git)
cd TU_REPOSITORIO

# 2. Crear entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install fastapi uvicorn osmnx networkx pydantic

# 3. Configurar API Key y levantar el servidor
export APOCALIPSIS_API_KEY="clave-desarrollo-local" # En Windows PowerShell: $env:APOCALIPSIS_API_KEY="clave-desarrollo-local"
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 1