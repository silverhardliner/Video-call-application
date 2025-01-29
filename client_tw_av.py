import socket, sys, cv2, pickle, struct
from threading import Thread
from datetime import datetime
from time import sleep
import matplotlib.pyplot as plt
import numpy as np
import pyaudio

print("[DEBUG] Imported all required modules")

sending, receiving = False, False
HEADERSIZE = 10

print("[DEBUG] Initialized global variables")

class myClass:
    def __init__(self, name, img):
        print("[DEBUG] Initializing client")
        self.threads = []
        self.stop = False
        self.name = name
        self.img = img
        self.local_buffer = None
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=sample_format, channels=channels, rate=fs, frames_per_buffer=chunk, input=True, output=True
        )
        print("[DEBUG] Client initialized successfully")

    def send_to_client(self, clientsocket):
        print("[DEBUG] Starting video capture and sending")
        cam = cv2.VideoCapture(0)
        cam.set(3, 320)
        cam.set(4, 240)
        img_counter = 0
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        while True:
            ret, frame = cam.read()
            try:
                result, frame = cv2.imencode(".jpg", frame, encode_param)
            except:
                print("[DEBUG] Failed to encode frame")
                continue
            data = pickle.dumps(frame, 0)
            size = len(data)
            if self.stop:
                break
            else:
                print(f"[DEBUG] Sending frame {img_counter}, size: {size} bytes")
                clientsocket.sendall(bytes("{:<{}}".format(len(data), HEADERSIZE), "utf-8") + data)
                img_counter += 1
                sleep(0.5)
        print("[DEBUG] Client stopped sending video")
        cam.release()

    def receive_from_client(self, clientsocket):
        print("[DEBUG] Starting video reception")
        print("Receiving...", receiving)
        while not self.stop:
            data = b""
            payload_size = HEADERSIZE
            msg_size = int(clientsocket.recv(HEADERSIZE))
            print(f"[DEBUG] Receiving frame of size: {msg_size} bytes")
            while len(data) < msg_size:
                data += clientsocket.recv(4096)
            frame_data = data  # [:msg_size]
            if len(frame_data) == 0:
                print("[DEBUG] Received empty frame")
                continue
            frame = pickle.loads(frame_data, fix_imports=True, encoding="bytes")
            frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)

            cv2.imshow(self.name, frame)
            cv2.resizeWindow(str(clientsocket), 320, 240)
            cv2.waitKey(1)
        print("[DEBUG] Video reception stopped")
        cv2.destroyAllWindows()

    def fetchAudio(self, audio_socket):
        print("[DEBUG] Starting audio reception")
        frames = []
        while not self.stop:
            try:
                print("[DEBUG] Waiting for audio data...")
                data = audio_socket.recv(4096)
                frames.append(data)
                print(f"[DEBUG] Received audio chunk of size: {len(data)} bytes")
                self.stream.write(data)
            except:
                print("[DEBUG] Error receiving audio")
                continue
        print("[DEBUG] Audio reception stopped")

    def recordAudio(self, audio_socket):
        print("[DEBUG] Starting audio recording")
        while not self.stop:
            data = self.stream.read(chunk)
            print(f"[DEBUG] Sending audio chunk of size: {len(data)} bytes")
            audio_socket.sendall(data)
        print("[DEBUG] Audio recording stopped")

    def inititate(self, clientsocket, audio_socket):
        print("[DEBUG] Initiating connection threads")
        t = Thread(target=self.send_to_client, args=(clientsocket,))
        t2 = Thread(target=self.receive_from_client, args=(clientsocket,))
        
        audioSendingThread = Thread(target=self.recordAudio, args=(audio_socket,))
        audioReceivingThread = Thread(target=self.fetchAudio, args=(audio_socket,))

        self.stop = False
        sending_started = False
        receiving_started = False
        
        while len(self.threads) < 2:
            try:
                print("[DEBUG] Waiting for user input")
                c = int(input("1: initiate sending \n 2: initiate receiving:"))
            except:
                print("[DEBUG] Invalid input")
                continue
            
            if c == 1 and not sending_started:
                print("[DEBUG] Starting sending threads")
                t.start()
                audioReceivingThread.start()
                self.threads.append(t)
                sending_started = True
            elif c == 2 and not receiving_started:
                print("[DEBUG] Starting receiving threads")
                t2.start()
                audioSendingThread.start()
                self.threads.append(t2)
                receiving_started = True
            else:
                print("[DEBUG] This option has already been initiated")
            
        print("[DEBUG] All threads initiated")

    def end(self):
        print("[DEBUG] Stopping all threads")
        self.stop = True
        for t in self.threads:
            t.join()
        self.stream.close()
        self.p.terminate()
        print("[DEBUG] All threads stopped")


# IP = "192.168.0.108"
IP = "127.0.0.1"
PORT = 1234

chunk = 1024  # Record in chunks of 1024 samples
sample_format = pyaudio.paInt16  # 16 bits per sample
channels = 1  # Changed from 2 to 1 (mono audio)
fs = 44100  # Record at 44100 samples per second
seconds = 3

print("[DEBUG] Setting up sockets")
audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

print(f"[DEBUG] Connecting to server at {IP}")
s.connect((IP, 1222))
audio_socket.connect((IP, PORT))
print("[DEBUG] Connected successfully")

plt.show()
name = "client"
img = None
print("[DEBUG] Creating client object")
obj = myClass(name, img)
obj.inititate(s, audio_socket)
print("[DEBUG] Press Enter to stop")
input()
obj.end()
s.close()
print("[DEBUG] Connection closed")
