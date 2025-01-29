import socket, sys, cv2, pickle, struct
from threading import Thread
from datetime import datetime
from time import sleep
import pyaudio
from array import array

print("[DEBUG] Imported all required modules")

sending, receiving = False, False
HEADERSIZE = 10
chunk = 1024  # Record in chunks of 1024 samples
sample_format = pyaudio.paInt16  # 16 bits per sample
channels = 1  # Changed from 2 to 1 (mono audio)
fs = 44100  # Record at 44100 samples per second
seconds = 3

print("[DEBUG] Initialized global variables")


class myClass:
    def __init__(self, i, clientsocket, audiosocket):
        print(f"[DEBUG] Initializing client {i}")
        self.i = i
        self.name = str(i)
        self.threads = []
        self.stop = False
        self.buffer = None
        self.clientsocket = clientsocket
        self.audiosocket = audiosocket
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=sample_format, channels=channels, rate=fs, frames_per_buffer=chunk, input=True, output=True
        )
        print(f"[DEBUG] Client {i} initialized successfully")

    def receive_and_send(self, clientsocket, audiosocket):
        print(f"[DEBUG] Client {self.i} starting receive_and_send loop")
        print("Receiving...", self.stop)
        while not self.stop:
            data = b""
            msg_size = int(clientsocket.recv(HEADERSIZE))
            print(f"[DEBUG] Client {self.i} received message size: {msg_size}")
            while len(data) < msg_size:
                data += clientsocket.recv(4096)
            audio_data = audiosocket.recv(4096)
            print(f"[DEBUG] Client {self.i} received audio data length: {len(audio_data)}")

            ##############  send as soon as you receive it  #############
            o = 1 if (self.i == 0) else 0
            print(f"[DEBUG] Client {self.i} forwarding video data to client {o}")
            clients[o].clientsocket.sendall(bytes("{:<{}}".format(len(data), HEADERSIZE), "utf-8") + data)
            if len(audio_data) == 4096:
                print("S", end=" | ")
                print(f"[DEBUG] Client {self.i} forwarding audio data to client {o}")
                self.stream.write(audio_data)
                print(max(array("h", audio_data)))
                clients[o].audiosocket.sendall(audio_data)
            ##############################################################
        print(f"[DEBUG] Client {self.i} receive_and_send loop stopped")
        print("Receiving(stopped)...", self.stop)

    def inititate(self):
        print(f"[DEBUG] Client {self.i} initiating connection")
        clientsocket, audiosocket = self.clientsocket, self.audiosocket

        t = Thread(
            target=self.receive_and_send,
            args=(
                clientsocket,
                audiosocket,
            ),
        )
        self.stop = False
        t.start()
        print(f"[DEBUG] Client {self.i} thread started")
        sleep(1)
        self.threads.append(t)

    def end(self):
        print(f"[DEBUG] Client {self.i} ending connection")
        self.stop = True
        self.clientsocket.close()
        for t in self.threads:
            t.join()
        self.stream.close()
        self.p.terminate()
        print(f"[DEBUG] Client {self.i} ended successfully")


# IP = "192.168.0.108"
IP = "127.0.0.1"
audio_PORT = 1234

print("[DEBUG] Setting up server sockets")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((IP, 1222))
s.listen()
print("[DEBUG] Video socket bound to port 1222")

audio_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
audio_s.bind((IP, audio_PORT))
audio_s.listen()
print("[DEBUG] Audio socket bound to port", audio_PORT)

clients = []
print("[DEBUG] Waiting for client connections...")
for i in range(2):
    print(f"[DEBUG] Waiting for client {i}")
    print(i)
    clientsocket, addr = s.accept()
    print(f"[DEBUG] Client {i} video connection accepted from {addr}")
    audiosocket, addr = audio_s.accept()
    print(f"[DEBUG] Client {i} audio connection accepted from {addr}")
    obj = myClass(i, clientsocket, audiosocket)
    clients.append(obj)

print("[DEBUG] Initiating connections for both clients")
clients[0].inititate()
clients[1].inititate()

print("[DEBUG] Server running. Press Enter to stop.")
# sleep(10)
input()
print("closing all")
print("[DEBUG] Closing all client connections")
for obj in clients:
    obj.end()
