import cv2
import numpy as np
import socket
import threading
import argparse
import logging
import select
import time
import pyaudio

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class VideoChat:
    def __init__(self, is_server=True, server_ip="0.0.0.0", port=12345, timeout=5, audio_index=0):
        logger.info("Initializing VideoChat...")
        self.is_server = is_server
        self.server_ip = server_ip
        self.port = port
        self.timeout = timeout
        self.audio_index = audio_index

        # Remove camera initialization from here
        self.cap = None  # Camera will be set later

        # Initialize audio with specific parameters
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100

        self.p = pyaudio.PyAudio()
        self.audio_input_stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            input_device_index=self.audio_index,
            frames_per_buffer=self.CHUNK,
        )

        self.audio_output_stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK,
        )

        logger.info("VideoChat initialized")

    def start_server(self):
        logger.info("Starting server...")
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.settimeout(self.timeout)
        self.server.bind((self.server_ip, self.port))
        self.server.listen(5)
        logger.info(f"Server listening on port {self.port}")

        while True:
            try:
                logger.info("Waiting for client connection...")
                client_socket, addr = self.server.accept()
                client_socket.settimeout(self.timeout)
                logger.info(f"Client connected from {addr}")
                self.handle_client(client_socket)
            except socket.timeout:
                logger.warning("Timeout waiting for client connection. Retrying...")
                continue
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")
                break

    def handle_client(self, client_socket):
        logger.info("Handling client connection...")
        try:
            while True:
                # Handle audio
                try:
                    # Read audio from microphone
                    audio_data = self.audio_input_stream.read(self.CHUNK, exception_on_overflow=False)
                    # Send audio length first
                    audio_length = len(audio_data)
                    client_socket.sendall(audio_length.to_bytes(4, byteorder="big"))
                    # Send audio data
                    client_socket.sendall(audio_data)

                    # Receive audio from client
                    audio_length_data = client_socket.recv(4)
                    if audio_length_data:
                        audio_length = int.from_bytes(audio_length_data, byteorder="big")
                        received_audio = client_socket.recv(audio_length)
                        if received_audio:
                            self.audio_output_stream.write(received_audio)
                except Exception as e:
                    logger.error(f"Error handling audio: {e}")
                    continue

                # Show server's own video feed
                ret, frame = self.cap.read()
                if not ret:
                    logger.error("Failed to capture frame")
                    break
                cv2.imshow("Server Camera", frame)

                # Receive client's video
                try:
                    # Use select to check for data with timeout
                    ready = select.select([client_socket], [], [], self.timeout)
                    if not ready[0]:
                        logger.warning("Timeout waiting for client data")
                        continue

                    # First receive the length of the frame
                    length_data = client_socket.recv(4)
                    if not length_data:
                        break
                    frame_length = int.from_bytes(length_data, byteorder="big")

                    # Then receive the frame data with timeout
                    data = b""
                    start_time = time.time()
                    while len(data) < frame_length:
                        if time.time() - start_time > self.timeout:
                            logger.warning("Timeout receiving frame data")
                            break
                        packet = client_socket.recv(min(frame_length - len(data), 4096))
                        if not packet:
                            break
                        data += packet

                    if len(data) == frame_length:
                        img_array = np.frombuffer(data, dtype=np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        if frame is not None:
                            cv2.imshow("Client Video", frame)
                except Exception as e:
                    logger.error(f"Error receiving frame: {e}")
                    continue

                if cv2.waitKey(1) & 0xFF == 27:  # Press 'Esc' to exit
                    break
        finally:
            logger.info("Closing client connection...")
            client_socket.close()
            cv2.destroyAllWindows()

    def start_client(self):
        logger.info("Starting client...")
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(self.timeout)
        try:
            logger.info(f"Connecting to server at {self.server_ip}:{self.port}")
            self.client.connect((self.server_ip, self.port))
            logger.info("Connected to server")
        except socket.timeout:
            logger.error("Timeout connecting to server")
            return
        except ConnectionRefusedError:
            logger.error("Connection refused by server")
            return

        while True:
            try:
                # Handle audio
                audio_data = self.audio_input_stream.read(self.CHUNK, exception_on_overflow=False)
                # Send audio length first
                audio_length = len(audio_data)
                self.client.sendall(audio_length.to_bytes(4, byteorder="big"))
                # Send audio data
                self.client.sendall(audio_data)

                # Receive audio from server
                audio_length_data = self.client.recv(4)
                if audio_length_data:
                    audio_length = int.from_bytes(audio_length_data, byteorder="big")
                    received_audio = self.client.recv(audio_length)
                    if received_audio:
                        self.audio_output_stream.write(received_audio)
            except Exception as e:
                logger.error(f"Error handling audio: {e}")
                continue

            ret, frame = self.cap.read()
            if not ret:
                logger.error("Failed to capture frame")
                break

            frame = cv2.resize(frame, (640, 480))
            encoded_frame = cv2.imencode(".jpg", frame)[1].tobytes()
            try:
                # Send the length of the frame first
                frame_length = len(encoded_frame)
                self.client.sendall(frame_length.to_bytes(4, byteorder="big"))
                # Then send the frame data
                self.client.sendall(encoded_frame)
            except socket.timeout:
                logger.warning("Timeout sending frame to server")
                continue
            except Exception as e:
                logger.error(f"Error sending frame: {e}")
                break

            if cv2.waitKey(1) == 27:  # Press 'Esc' to exit
                logger.info("Client stopping - Esc pressed")
                break

        logger.info("Closing client connection...")
        self.cap.release()
        self.client.close()
        cv2.destroyAllWindows()

    def run(self):
        logger.info(f"Starting VideoChat in {'server' if self.is_server else 'client'} mode")
        if self.is_server:
            self.start_server()
        else:
            self.start_client()

    def __del__(self):
        # Clean up audio resources
        if hasattr(self, "audio_input_stream"):
            self.audio_input_stream.stop_stream()
            self.audio_input_stream.close()
        if hasattr(self, "audio_output_stream"):
            self.audio_output_stream.stop_stream()
            self.audio_output_stream.close()
        if hasattr(self, "p"):
            self.p.terminate()


# Main function
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Chat Application")
    parser.add_argument(
        "-m", "--mode", choices=["server", "client"], required=True, help="Run as server or client"
    )
    parser.add_argument("-i", "--ip", default="127.0.0.1", help="Server IP address (default: 127.0.0.1)")
    parser.add_argument(
        "-sc", "--server_camera", type=int, default=0, help="Server camera index (default: 0)"
    )
    parser.add_argument(
        "-cc", "--client_camera", type=int, default=1, help="Client camera index (default: 1)"
    )
    parser.add_argument("-sa", "--server_audio", type=int, default=0, help="Server audio index (default: 0)")
    parser.add_argument("-ca", "--client_audio", type=int, default=1, help="Client audio index (default: 1)")
    args = parser.parse_args()

    logger.info("Starting application...")
    if args.mode == "server":
        server = VideoChat(is_server=True, audio_index=args.server_audio)
        server.cap = cv2.VideoCapture(args.server_camera)  # Use specified server camera
        if not server.cap.isOpened():
            logger.error(f"Could not open server camera {args.server_camera}")
            exit(1)
        server.run()
    else:
        client = VideoChat(is_server=False, server_ip=args.ip, audio_index=args.client_audio)
        client.cap = cv2.VideoCapture(args.client_camera)  # Use specified client camera
        if not client.cap.isOpened():
            logger.error(f"Could not open client camera {args.client_camera}")
            exit(1)
        client.run()
