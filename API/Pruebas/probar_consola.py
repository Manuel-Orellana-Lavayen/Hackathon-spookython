from Pruebas.FuncionesSimulador import inicializar_simulacion, ejecutar_turno, comprobar_fin_simulacion, MUNDO

RONDAS_PRUEBA_DE_FUEGO = [
    {
        "nombre": "Ronda 1 - Anochecer",
        "sobrevivientes": 20,
        "zombies": {"caminante": 15, "corredor": 0, "horda": 0, "dormido": 0},
        "max_turnos": 60,
    },
    {
        "nombre": "Ronda 2 - Medianoche",
        "sobrevivientes": 80,
        "zombies": {"caminante": 20, "corredor": 8, "horda": 3, "dormido": 0},
        "max_turnos": 80,
    },
    {
        "nombre": "Ronda 3 - Apocalipsis",
        "sobrevivientes": 200,
        "zombies": {"caminante": 30, "corredor": 15, "horda": 5, "dormido": 15},
        "max_turnos": 100,
    },
]

if __name__ == "__main__":
    print("=" * 72)
    print(" SIMULADOR APOCALIPSIS ZOMBIE MANTA - MODO CONSOLA (SIN WEB)")
    print("=" * 72)

    for idx, config in enumerate(RONDAS_PRUEBA_DE_FUEGO, start=1):
        print(f"\n>>> INICIANDO {config['nombre']} ({config['sobrevivientes']} sobrevivientes)")
        inicializar_simulacion(
            num_sobrevivientes=config["sobrevivientes"],
            config_zombies=config["zombies"],
            semilla=100 + idx,
        )

        for _ in range(config["max_turnos"]):
            estado = ejecutar_turno()
            m = estado["metricas"]

            if estado["turno"] % 5 == 0 or comprobar_fin_simulacion():
                print(
                    f"  [Turno {estado['turno']:03d}] "
                    f"En calle: {m['activos']:3d} | "
                    f"Rescatados: {m['rescatados']:3d} | "
                    f"Mordidos: {m['mordidos']:3d} | "
                    f"p95 /paso: {m['latencia_p95_ms']:.3f} ms"
                )

            if comprobar_fin_simulacion():
                break

        for ev in MUNDO.eventos_log[-3:]:
            print(f"   * {ev}")

        porcentaje = (m["rescatados"] / config["sobrevivientes"]) * 100
        print(f"--> RESULTADO {config['nombre']}: {porcentaje:.1f}% rescatados | Latencia p95: {m['latencia_p95_ms']:.3f} ms")