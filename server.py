#!/bin/env python

import json
from uuid import uuid4
from asyncio import sleep, create_task

import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse

TICK_RATE = 24
AFK_TIME = 4

app = FastAPI()
players = {}

async def send_data(ws: WebSocket):
    while 1:
        other_players = {key: value for key, value in players.items() if key != ws.cookies["uuid"]}
        await ws.send_text(json.dumps(list(other_players.values()), skipkeys=True))
        await sleep(1/TICK_RATE)

async def handle_data(ws: WebSocket):
    while 1:
        data = json.loads(await ws.receive_text())
        players[ws.cookies["uuid"]] = data
        players[ws.cookies["uuid"]][("system", "inactive")] = AFK_TIME

async def kick_afk():
    while 1:
        for uuid, value in players.items():
            value[("system", "inactive")] -= 1
            if value[("system", "inactive")] <= 0:
                players.pop(uuid)
        await sleep(1)

@app.on_event("startup")
async def startup():
    create_task(kick_afk())

@app.get("/")
async def index(request: Request):
    with open("index.html", "r") as f:
        response = HTMLResponse(f.read())
        if "uuid" not in request.cookies:
            response.set_cookie("uuid", str(uuid4()))
        return response

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    if "uuid" not in ws.cookies:
        await ws.close()
        return

    await ws.accept()
    tasks = []
    tasks.append(create_task(send_data(ws)))
    tasks.append(create_task(handle_data(ws)))
    for task in tasks:
        await task

if __name__ == "__main__":
    uvicorn.run(f"{__name__}:app", host="0.0.0.0", port=1215, reload=True)
