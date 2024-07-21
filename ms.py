import socket
import struct
import threading
import time

# Configuration
# HOST = '127.0.0.1' 
HOST = '194.58.97.193'
PORT = 27010
UPDATE_INTERVAL = 60  
SERVERS_FILE = 'servers.txt'  
HEADER = b'\xff\xff\xff\xfff\n'  # Header constant

servers = {}

def load_servers_from_file():
    try:
        with open(SERVERS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    ip, port = line.split(':')
                    servers[ip + ':' + port] = {
                        'ip': ip,
                        'port': int(port),
                        'name': 'Unknown',
                        'mode': 'Unknown',
                        'game': 'cstrike',
                        'last_update': time.time()
                    }
        print(f"Loaded {len(servers)} servers from file.")
    except FileNotFoundError:
        print(f"No servers file found. Starting with an empty server list.")

def save_server_to_file(ip, port):
    with open(SERVERS_FILE, 'a') as f:
        f.write(f"{ip}:{port}\n")

def handle_client(data, addr, server_socket):
    try:
        msg_type = data[0]
        if msg_type == 0x30:  
            ip = addr[0]
            port, = struct.unpack('!H', data[1:3])
            name = data[3:data.find(b'\x00', 3)].decode('utf-8')
            mode = data[data.find(b'\x00', 3) + 1:data.find(b'\x00', data.find(b'\x00', 3) + 1)].decode('utf-8')
            game = data[data.find(b'\x00', data.find(b'\x00', 3) + 1) + 1:data.find(b'\x00', data.find(b'\x00', data.find(b'\x00', 3) + 1) + 1)].decode('utf-8')
            server_key = ip + ':' + str(port)
            servers[server_key] = {
                'ip': ip,
                'port': port,
                'name': name,
                'mode': mode,
                'game': game,
                'last_update': time.time()
            }
            save_server_to_file(ip, port)
            response = HEADER + b'\x30'  
            server_socket.sendto(response, addr)
        elif msg_type == 0x31:  
            server_list = b'\x31' + b''.join([socket.inet_aton(s['ip']) + struct.pack('!H', s['port']) for s in servers.values()])
            response = HEADER + server_list[1:]
            # print(response)
            server_socket.sendto(response, addr)
        elif msg_type == 0x32:  
            current_time = time.time()
            inactive_servers = [key for key, s in servers.items() if current_time - s['last_update'] > UPDATE_INTERVAL]
            for key in inactive_servers:
                del servers[key]
            response = HEADER + b'\x32'[1:] 
            server_socket.sendto(response, addr)
        elif data.startswith(b'1\xff'):
            handle_server_list_request(data, addr, server_socket)
    except Exception as e:
        print(f"Error handling client: {e}")

def handle_server_list_request(data, addr, server_socket):
    try:
        parts = data[2:].split(b'\x00')
        if len(parts) >= 2:
            ip_port_filter = parts[0].decode('utf-8')
            game_filter = parts[1].decode('utf-8')

            response = HEADER + b'\xff\xff\xff\xff'

            response += struct.pack('!H', len(servers))

            for server in servers.values():
                if ip_port_filter == '0.0.0.0:0' or ip_port_filter == f"{server['ip']}:{server['port']}":
                    if game_filter == 'Unknown' or server['game'] == game_filter:
                        response += socket.inet_aton(server['ip']) + struct.pack('!H', server['port'])
            
            response += b'\x00\x00'
        else:
            response = HEADER + b'\xff\xff\xff\xff' + b'\x00\x00'
        
        server_socket.sendto(response, addr)
    except Exception as e:
        print(f"Error handling server list request: {e}")

def update_servers():
    while True:
        load_servers_from_file()
        time.sleep(UPDATE_INTERVAL)
        current_time = time.time()
        inactive_servers = [key for key, s in servers.items() if current_time - s['last_update'] > UPDATE_INTERVAL]
        for key in inactive_servers:
            del servers[key]
        print(f"Updated server list, active servers: {len(servers)}")

def start_server():
    load_servers_from_file()
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((HOST, PORT))
    print(f"Master server listening on {HOST}:{PORT}")

    # threading.Thread(target=update_servers, daemon=True).start()

    while True:
        data, addr = server_socket.recvfrom(1024)
        threading.Thread(target=handle_client, args=(data, addr, server_socket)).start()

if __name__ == "__main__":
    start_server()
