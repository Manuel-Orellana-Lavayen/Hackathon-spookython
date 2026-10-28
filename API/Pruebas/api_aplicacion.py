# Creado Por Manuel Elias Orellana Lavayen - 2026
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from Pruebas.FuncionesApi import prediccion_individual, prediccion_recursiva_individual, prediccion_grupo_familia, grafico
# Instancia de FastApi
app = FastAPI()

class Modelo_Datos_prediccion_individual(BaseModel):
    numero_tienda: int
    numero_articulo: int
    fecha: str
    en_promocion: int

class Modelo_Datos_prediccion_familia(BaseModel):
    numero_tienda: int
    nombre_familia: str
    fecha: str

@app.post("/PredecirIndividual")
async def pred_individual(datos : Modelo_Datos_prediccion_individual):
    numero_tienda = datos.numero_tienda
    numero_articulo = datos.numero_articulo
    fecha =  datos.fecha
    en_promocion = datos.en_promocion
    prediccion, unidades_vendidas_real, figurabase64 = prediccion_individual(numero_tienda= numero_tienda, numero_articulo= numero_articulo, fecha= fecha, en_promocion= en_promocion)


    return {
            "Predicción": prediccion,
            "Unidadesreales": unidades_vendidas_real,
            "Figurabase64": figurabase64

           }

@app.post("/PredecirRecursivoIndividual")
async def pred_recursivo_individual(datos : Modelo_Datos_prediccion_individual):
    numero_tienda = datos.numero_tienda
    numero_articulo = datos.numero_articulo
    fecha = datos.fecha
    en_promocion = datos.en_promocion
    prediccion, unidades_vendidas_real = prediccion_recursiva_individual(numero_tienda= numero_tienda, numero_articulo= numero_articulo, fecha= fecha, en_promocion= en_promocion)

    return {
            "Predicción": prediccion,
            "Unidadesreales": unidades_vendidas_real
           }

@app.post("/PredecirFamilia")
async def pred_familia(datos : Modelo_Datos_prediccion_familia):
    numero_tienda = datos.numero_tienda
    nombre_familia = datos.nombre_familia
    fecha = datos.fecha

    predicciones, figurabase64  = prediccion_grupo_familia(numero_tienda= numero_tienda, nombre_familia = nombre_familia, fecha= fecha)
    grafico_dispersion = grafico(predicciones= predicciones)
    return {
            "Predicción": predicciones,
            "Gráfico Dispersion": grafico_dispersion,
            "Figurabase64": figurabase64
           }

if __name__ == "__main__":
    uvicorn.run(
        app= "api_aplicacion:app",
        host= "127.0.0.1",
        port= 8000,
        reload= False
    )
