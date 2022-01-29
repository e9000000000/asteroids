#!/bin/python

import socket
import json
from os import getenv
from _thread import start_new_thread
from datetime import datetime
from time import sleep
from hashlib import sha1
from base64 import b64encode


IP = getenv("SERVER_IP", "0.0.0.0")
HTTP_PORT = int(getenv("SERVER_HTTP_PORT", "1215"))
WS_PORT = int(getenv("SERVER_WS_PORT", "1150"))
AFK_TIME = int(getenv("SERVER_AFK_TIME", "60"))
MAX_PLAYERS = int(getenv("SERVER_MAX_PLAYERS", "166"))
TICK_RATE = 24

HTTP_RESPONSE = """\
HTTP/1.1 200 OK
Date: {date}
Server: a
Last-Modified: {date}
Accept-Ranges: bytes
Content-Length: {content_length}
Connection: close
Content-Type: text/html; charset=ascii

{content}
"""
with open("index.html", "r") as f:
    CONTENT = f.read()

HTTP_ERROR = """\
HTTP/1.1 404 Not Found
Date: {date}
Server: a
Last-Modified: {date}
Accept-Ranges: bytes
Content-Length: 6
Connection: close
Content-Type: text/html; charset=ascii

only /
"""

HTTP_TO_WS = """\
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: {key}
"""

WS_MAGIC_STRING = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

http_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
web_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
players = {}

def delete_afk_players() -> None:
    while 1:
        sleep(1)
        for addr in list(players.keys()):
            try:
                players[addr][("system", "time_before_kick")] -= 1
                if players[addr][("system", "time_before_kick")] <= 0:
                    player_data = players.pop(addr)
                    print(f"[AFK KICKED] {player_data['name']}")
            except Exception as e:
                print(f"[DELETE AFK ERROR {type(e)}] {e=} {addr=}")


def handle_data(data: dict, addr) -> None:
    if "delete" in data:
        players.pop(addr)
        return

    if "name" not in data:
        raise Exception("no 'name' in data")

    name = data["name"]
    if addr not in players:
        if len(players) >= MAX_PLAYERS:
            raise Exception(f"players limit reached. players limit: {MAX_PLAYERS}")
        names = tuple(map(lambda x: x["name"], players.values()))
        if name in names:
            raise Exception(f"player with {name=} already in game.")

    players[addr] = data
    players[addr][("system", "time_before_kick")] = AFK_TIME

def send_players_data(ws):
    while 1:
        ws.send(json.dumps(list(players.values()), skipkeys=True).encode("ascii"))
        sleep(1000/TICK_RATE)


def ws_serve(ws, addr) -> None:
    start_new_thread(send_players_data, (ws, ))
    while 1:
        rawdata, _ = ws.recvfrom(1024 * 10)
        try:
            data = json.loads(rawdata.decode("ascii"))
            print(f"[{addr}] {data}")
            handle_data(data, addr)
            send_data = json.dumps(list(players.values()), skipkeys=True)
            print(f"[RESPONSE] {send_data}")
        except Exception as e:
            print(f"[ERROR {type(e)}] {addr=} {e=} {rawdata=}")
            ws.sendto(f'{{"error": "{e}"}}'.encode("ascii"), addr)

def http_serve() -> None:
    while 1:
        socket, addr = http_sock.accept()
        rawdata, _ = socket.recvfrom(10*1024)
        data = rawdata.decode("ascii")
        if data.startswith("GET / "):
            print(f"[HTTP GET] /")
            http = HTTP_RESPONSE.format(
                date=datetime.now().isoformat(),
                content=CONTENT,
                content_length=len(CONTENT),
            )
        elif data.startswith("GET /ws ") or data.startswith("GET /ws/ "):
            print(f"[HTTP GET] /ws/")
            headers = data.splitlines()
            for header in headers:
                if not header.startswith("Sec-WebSocket-Key: "):
                    continue
                client_key = header.replace("Sec-WebSocket-Key: ", "")
                break
            else:
                socket.close()
                continue
            key = b64encode(sha1((client_key + WS_MAGIC_STRING).encode()).digest())

            http = HTTP_TO_WS.format(key=key)
            socket.send(http.encode("ascii"))
            start_new_thread(ws_serve, (socket, addr))
            continue
        else:
            print(f"[HTTP GET] 404")
            http = HTTP_ERROR.format(
                date=datetime.now().isoformat()
            )
        socket.send(http.encode("ascii"))
        socket.close()

if __name__ == "__main__":
    http_sock.bind((IP, HTTP_PORT))
    http_sock.listen(MAX_PLAYERS)
    start_new_thread(delete_afk_players, ())

    http_serve()
