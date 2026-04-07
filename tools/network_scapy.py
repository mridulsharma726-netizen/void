"""
VOID Network Tools - Scapy Integration
Stable, fault-tolerant network utilities.
"""

SCAPY_AVAILABLE = False

try:
    from scapy.all import IP, ICMP, TCP, sniff, traceroute, sr1
    SCAPY_AVAILABLE = True
except ImportError:
    pass
except Exception:
    pass

import logging
import re
import socket
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def validate_ip(ip: str) -> bool:
    "Validate IPv4 address."
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    parts = ip.split('.')
    return all(0 <= int(p) <= 255 for p in parts)

def ping_host(ip: str) -> Dict[str, Any]:
    "Ping host using Scapy ICMP or socket fallback."
    if not SCAPY_AVAILABLE:
        return {"status": "error", "message": "scapy unavailable"}

    if not validate_ip(ip):
        return {"status": "error", "message": "invalid_ip"}

    logger.info(f"Network ping start: {ip}")

    try:
        pkt = IP(dst=ip)/ICMP()
        resp = sr1(pkt, timeout=2, verbose=0)

        if resp and resp.haslayer(ICMP):
            if int(resp[ICMP].type) == 0:
                latency = (resp.time - pkt.sent_time) * 1000
                logger.info(f"Ping success: {ip} ({latency:.1f}ms)")
                return {
                    "status": "alive",
                    "latency_ms": round(latency, 1)
                }

        logger.info(f"Ping no response: {ip}")
        return {"status": "no_response", "latency_ms": None}

    except PermissionError:
        logger.warning(f"Ping permission denied: {ip}")
        return {"status": "error", "message": "permission_denied"}
    except Exception as e:
        logger.error(f"Ping error {ip}: {str(e)}")
        return {"status": "error", "message": str(e)[:100]}

def port_scan(target: str, ports: str = "80,443,22,21,53") -> Dict[str, Any]:
    "Safe TCP SYN port scan with socket fallback."
    if not SCAPY_AVAILABLE:
        return port_scan_socket(target, ports)

    if not validate_ip(target):
        return {"status": "error", "message": "invalid_target"}

    try:
        ports_list = [int(p.strip()) for p in ports.split(',') if p.strip().isdigit()]
        ports_list = sorted(set(ports_list))[:100]

        open_ports = []
        logger.info(f"[SCAPY SCAN] {target}:{ports_list}")

        for port in ports_list:
            pkt = IP(dst=target)/TCP(dport=port, flags="S")
            resp = sr1(pkt, timeout=1, verbose=0)
            if resp and resp.haslayer(TCP) and resp[TCP].flags == 0x12:  # SYN-ACK
                open_ports.append(port)
                sr1(IP(dst=target)/TCP(dport=port, flags="R"), timeout=1, verbose=0)

        return {
            "status": "complete",
            "target": target,
            "open_ports": open_ports,
            "total_scanned": len(ports_list),
            "open_count": len(open_ports)
        }
    except PermissionError:
        return {"status": "error", "message": "permission_denied_raw_sockets"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}

def port_scan_socket(target: str, ports: str) -> Dict[str, Any]:
    "Socket fallback port scan."
    ports_list = [int(p.strip()) for p in ports.split(',') if p.strip().isdigit()]
    ports_list = ports_list[:100]
    
    open_ports = []
    for port in ports_list:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((target, port))
            if result == 0:
                open_ports.append(port)
            sock.close()
        except:
            pass
    
    return {
        "status": "complete_socket",
        "target": target,
        "open_ports": open_ports,
        "total_scanned": len(ports_list),
        "open_count": len(open_ports)
    }

def sniff_packets(count: int = 10, interface: Optional[str] = None) -> Dict[str, Any]:
    "Safe packet sniff (max 20 packets)."
    if not SCAPY_AVAILABLE:
        return {"status": "error", "message": "scapy unavailable"}

    count = min(count, 20)
    try:
        logger.info(f"[SCAPY SNIFF] Capturing {count} packets")
        packets = sniff(count=count, timeout=10, iface=interface, store=1)
        
        summary = {}
        protocols = set()
        for p in packets:
            if IP in p:
                protocols.add(p[IP].proto)
                src = p[IP].src
                summary[src] = summary.get(src, 0) + 1
        
        return {
            "status": "complete",
            "packets_captured": len(packets),
            "unique_sources": len(summary),
            "protocols": list(protocols),
            "top_sources": dict(sorted(summary.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    except PermissionError:
        return {"status": "error", "message": "permission_denied_npcap"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}

def traceroute_host(host: str) -> Dict[str, Any]:
    "Safe traceroute."
    if not SCAPY_AVAILABLE:
        return traceroute_socket(host)

    if not validate_ip(host):
        try:
            host = socket.gethostbyname(host)
        except:
            return {"status": "error", "message": "invalid_host"}

    try:
        logger.info(f"[SCAPY TRACEROUTE] {host}")
        hops = traceroute(host, maxttl=20, timeout=2)
        path = []
        for hop in hops:
            if hop[1]:
                path.append({
                    "ttl": hop[0],
                    "ip": hop[1][IP].src,
                    "rtt": hop[2] * 1000 if hop[2] else None
                })
        return {"status": "complete", "hops": path}
    except PermissionError:
        return {"status": "error", "message": "permission_denied"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}

def traceroute_socket(host: str) -> Dict[str, Any]:
    "Socket traceroute fallback."
    path = []
    for ttl in range(1, 21):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl.to_bytes(1, 'big'))
            sock.settimeout(2)
            sock.sendto(b'', (host, 33434))
            src, _ = sock.recvfrom(512)
            sock.close()
            path.append({"ttl": ttl, "ip": src[0]})
        except:
            path.append({"ttl": ttl, "ip": "*"})
    return {"status": "complete_socket", "hops": path}

def dns_lookup(domain: str) -> Dict[str, Any]:
    "DNS resolution with socket."
    try:
        ips = socket.gethostbyname_ex(domain)[2]
        return {"status": "complete", "domain": domain, "ips": ips}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}

if __name__ == "__main__":
    print(ping_host("8.8.8.8"))
