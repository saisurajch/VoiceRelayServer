import socket
import threading

HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 5500       # Change if needed

clients = []

def broadcast(sender_sock, message):
    for client in clients:
        if client != sender_sock:
            try:
                client.sendall(message)
            except Exception:
                pass

def handle_client(client_sock, addr):
    print(f"Client connected: {addr}")
    clients.append(client_sock)
    try:
        while True:
            data = client_sock.recv(4096)
            if not data:
                break
            broadcast(client_sock, data)
    except Exception as e:
        print(f"Client {addr} error: {e}")
    finally:
        clients.remove(client_sock)
        client_sock.close()
        print(f"Client disconnected: {addr}")

def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen()
    print(f"Relay server listening on {HOST}:{PORT}")
    try:
        while True:
            client_sock, addr = server_sock.accept()
            threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        server_sock.close()

if __name__ == "__main__":
    main()
