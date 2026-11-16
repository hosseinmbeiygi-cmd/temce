import socket

def probe(host, port, timeout=3):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception as e:
        return f"fail: {e!r}"
    finally:
        s.close()

results = {
    "postgres_5432": probe("localhost", 5432),
    "redis_6379": probe("localhost", 6379),
}
with open("_probe_ports_result.txt", "w", encoding="utf-8") as f:
    f.write(str(results))
