import socket
import threading
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 5500       # Change if needed

class ClientInfo:
    """Store client information"""
    def __init__(self, socket, addr):
        self.socket = socket
        self.addr = addr
        self.player_id = None
        self.language = None
        self.connected = True

class VoiceRelayServer:
    """
    Advanced voice relay server with language-aware routing
    """
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.clients = {}  # socket -> ClientInfo mapping
        self.player_clients = {}  # player_id -> ClientInfo mapping
        self.server_socket = None
        self.running = False
        
    def start(self):
        """Start the relay server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.running = True
        
        logger.info(f"Voice relay server listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                client_sock, addr = self.server_socket.accept()
                client_info = ClientInfo(client_sock, addr)
                self.clients[client_sock] = client_info
                
                # Start client handler thread
                threading.Thread(
                    target=self.handle_client, 
                    args=(client_info,), 
                    daemon=True
                ).start()
                
                logger.info(f"Client connected: {addr}")
                
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the relay server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        
        # Close all client connections
        for client_info in list(self.clients.values()):
            self.disconnect_client(client_info)
    
    def disconnect_client(self, client_info):
        """Disconnect a client and cleanup"""
        try:
            client_info.connected = False
            if client_info.socket in self.clients:
                del self.clients[client_info.socket]
            if client_info.player_id and client_info.player_id in self.player_clients:
                del self.player_clients[client_info.player_id]
            client_info.socket.close()
            logger.info(f"Client disconnected: {client_info.addr}")
        except Exception as e:
            logger.error(f"Error disconnecting client {client_info.addr}: {e}")
    
    def needs_translation(self, sender_language, receiver_language):
        """Check if translation is needed between two languages"""
        if not sender_language or not receiver_language:
            return True
        
        # Extract base language (e.g., "English" from "English (US)")
        sender_base = sender_language.split(" ")[0].lower()
        receiver_base = receiver_language.split(" ")[0].lower()
        
        return sender_base != receiver_base
    
    def route_voice_message(self, sender_info, sender_language, original_text):
        """Route voice message to appropriate clients with language-aware routing"""
        for client_info in self.clients.values():
            if client_info == sender_info or not client_info.connected:
                continue  # Skip sender and disconnected clients
            
            try:
                # Determine if translation is needed
                if self.needs_translation(sender_language, client_info.language):
                    # Different languages - send for translation
                    message = f"TRANSLATE:{sender_info.player_id}|{sender_language}|{client_info.language}|{original_text}"
                else:
                    # Same language - send original directly
                    message = f"DIRECT:{sender_info.player_id}|{sender_language}|{original_text}"
                
                client_info.socket.sendall(message.encode("utf-8"))
                logger.debug(f"Routed message from {sender_info.player_id} to {client_info.player_id}")
                
            except Exception as e:
                logger.error(f"Error routing message to {client_info.addr}: {e}")
                self.disconnect_client(client_info)
    
    def broadcast_language_update(self, updated_player_id, language):
        """Broadcast language preference update to all clients"""
        message = f"LANG_UPDATE:{updated_player_id}|{language}"
        for client_info in self.clients.values():
            if client_info.connected and client_info.player_id != updated_player_id:
                try:
                    client_info.socket.sendall(message.encode("utf-8"))
                except Exception as e:
                    logger.error(f"Error broadcasting language update to {client_info.addr}: {e}")
                    self.disconnect_client(client_info)
    
    def handle_client(self, client_info):
        """Handle messages from a client"""
        try:
            while client_info.connected and self.running:
                data = client_info.socket.recv(4096)
                if not data:
                    break
                
                try:
                    message = data.decode("utf-8")
                    self.process_message(client_info, message)
                except Exception as e:
                    logger.error(f"Error processing message from {client_info.addr}: {e}")
                    
        except Exception as e:
            logger.error(f"Client {client_info.addr} error: {e}")
        finally:
            self.disconnect_client(client_info)
    
    def process_message(self, client_info, message):
        """Process different types of messages from clients"""
        
        if message.startswith("REGISTER:"):
            # Register client: "REGISTER:player_id|language"
            try:
                _, data = message.split(":", 1)
                player_id, language = data.split("|", 1)
                
                client_info.player_id = player_id
                client_info.language = language
                self.player_clients[player_id] = client_info
                
                logger.info(f"Registered client {player_id} with language {language}")
                
                # Broadcast language to other clients
                self.broadcast_language_update(player_id, language)
                
                # Send current player list to new client
                self.send_player_list(client_info)
                
            except Exception as e:
                logger.error(f"Error processing REGISTER: {e}")
        
        elif message.startswith("LANG:"):
            # Language update: "LANG:player_id|language"
            try:
                _, data = message.split(":", 1)
                player_id, language = data.split("|", 1)
                
                if client_info.player_id == player_id:
                    client_info.language = language
                    logger.info(f"Updated language for {player_id}: {language}")
                    
                    # Broadcast to other clients
                    self.broadcast_language_update(player_id, language)
                
            except Exception as e:
                logger.error(f"Error processing LANG: {e}")
        
        elif message.startswith("VOICE:"):
            # Voice message: "VOICE:sender_id|sender_language|text"
            try:
                _, data = message.split(":", 1)
                parts = data.split("|", 2)
                if len(parts) == 3:
                    sender_id, sender_language, text = parts
                    
                    # Update sender's language
                    if client_info.player_id == sender_id:
                        client_info.language = sender_language
                    
                    # Route to appropriate clients
                    self.route_voice_message(client_info, sender_language, text)
                
            except Exception as e:
                logger.error(f"Error processing VOICE: {e}")
        
        else:
            # Legacy format - treat as voice message
            if "|" in message:
                try:
                    sender_id, text = message.split("|", 1)
                    if client_info.player_id == sender_id and client_info.language:
                        self.route_voice_message(client_info, client_info.language, text)
                except Exception as e:
                    logger.error(f"Error processing legacy message: {e}")
    
    def send_player_list(self, client_info):
        """Send current player list to a client"""
        try:
            for player_id, player_client in self.player_clients.items():
                if player_id != client_info.player_id and player_client.language:
                    message = f"LANG_UPDATE:{player_id}|{player_client.language}"
                    client_info.socket.sendall(message.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error sending player list to {client_info.addr}: {e}")

# Global server instance
relay_server = VoiceRelayServer()

def main():
    try:
        relay_server.start()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    finally:
        relay_server.stop()

if __name__ == "__main__":
    main()
