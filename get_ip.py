import socket
import os

def get_best_ip():
    # 1. Try dummy connection with a short timeout to prevent hanging when offline
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass

    # 2. Grab all local IPs and filter/prioritize physical ones
    try:
        addr_info = socket.getaddrinfo(socket.gethostname(), None)
        ips = list(set([info[4][0] for info in addr_info if info[0] == socket.AF_INET]))
        
        # Prioritize physical Wi-Fi/Ethernet (192.168.x.x) excluding VM adapters
        preferred = [ip for ip in ips if ip.startswith("192.168.") and not any(sub in ip for sub in ["56.", "232.", "214."])]
        if preferred:
            return preferred[0]
            
        # Prioritize Radmin VPN (26.x.x.x)
        radmin = [ip for ip in ips if ip.startswith("26.")]
        if radmin:
            return radmin[0]
            
        # Fallback to any other non-localhost IP
        other = [ip for ip in ips if ip != "127.0.0.1"]
        if other:
            return other[0]
    except Exception:
        pass
        
    return "127.0.0.1"

if __name__ == "__main__":
    ip = get_best_ip()
    # Write to _ip.tmp so batch can read it
    with open("_ip.tmp", "w") as f:
        f.write(ip)
    print(ip)
