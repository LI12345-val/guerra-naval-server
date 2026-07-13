"""
Servidor relay para Guerra Naval Estratégica.

Este servidor NO tiene lógica del juego. Solo hace de "cartero": empareja a
dos jugadores mediante un código de sala de 4 dígitos y reenvía los mensajes
que uno le manda al otro. Toda la lógica del juego (dónde están los barcos,
quién ganó, etc.) sigue viviendo en main.py, exactamente igual que antes.

CÓMO CORRERLO:
    pip install websockets
    python server.py

Por defecto escucha en el puerto 8765 en todas las interfaces (0.0.0.0),
así que para que los celulares se conecten desde internet necesitas
correrlo en un servidor con IP/dominio público (una VPS, Railway, Render,
Fly.io, etc.) — no alcanza con correrlo en tu PC de casa salvo que abras
el puerto en tu router o uses un servicio como ngrok para pruebas rápidas.
"""

import asyncio
import json
import os
import random
import websockets

# codigo (str) -> {"j1": websocket, "j2": websocket | None}
salas = {}

# Render (y hostings similares) asignan el puerto mediante esta variable de
# entorno. En tu PC, si no existe, usa 8765 por defecto.
PUERTO = int(os.environ.get("PORT", 8765))


def nuevo_codigo():
    codigo = f"{random.randint(1000, 9999)}"
    while codigo in salas:
        codigo = f"{random.randint(1000, 9999)}"
    return codigo


async def enviar(ws, tipo, **datos):
    try:
        await ws.send(json.dumps({"tipo": tipo, **datos}))
    except Exception:
        pass


async def manejar_cliente(ws):
    codigo_actual = None
    soy = None  # "j1" o "j2"

    try:
        async for mensaje in ws:
            try:
                datos = json.loads(mensaje)
            except json.JSONDecodeError:
                continue

            accion = datos.get("accion")

            # ---- Crear una sala nueva (jugador 1) ----
            if accion == "crear_sala":
                codigo = nuevo_codigo()
                salas[codigo] = {"j1": ws, "j2": None}
                codigo_actual, soy = codigo, "j1"
                await enviar(ws, "sala_creada", codigo=codigo)

            # ---- Unirse a una sala existente (jugador 2) ----
            elif accion == "unirse_sala":
                codigo = str(datos.get("codigo", "")).strip()
                sala = salas.get(codigo)
                if not sala:
                    await enviar(ws, "error", mensaje="Código no encontrado.")
                    continue
                if sala["j2"] is not None:
                    await enviar(ws, "error", mensaje="Esa sala ya está llena.")
                    continue
                sala["j2"] = ws
                codigo_actual, soy = codigo, "j2"
                await enviar(ws, "union_exitosa", codigo=codigo)
                await enviar(sala["j1"], "rival_conectado")

            # ---- Reenviar un mensaje del juego al rival ----
            elif accion == "reenviar" and codigo_actual:
                sala = salas.get(codigo_actual)
                if not sala:
                    continue
                destino = sala["j2"] if soy == "j1" else sala["j1"]
                if destino:
                    await enviar(destino, "mensaje", payload=datos.get("payload"))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Avisar al rival si alguien se desconecta y limpiar la sala
        if codigo_actual and codigo_actual in salas:
            sala = salas[codigo_actual]
            otro = sala["j2"] if soy == "j1" else sala["j1"]
            if otro:
                await enviar(otro, "rival_desconectado")
            if soy == "j1":
                sala["j1"] = None
            else:
                sala["j2"] = None
            if not sala["j1"] and not sala["j2"]:
                salas.pop(codigo_actual, None)


async def principal():
    print(f"🚢 Servidor de Guerra Naval escuchando en el puerto {PUERTO}")
    async with websockets.serve(manejar_cliente, "0.0.0.0", PUERTO):
        await asyncio.Future()  # corre para siempre


if __name__ == "__main__":
    asyncio.run(principal())
