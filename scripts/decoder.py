import base64
import sys

data = sys.stdin.read()
with open(sys.argv[1], "wb") as f:
    f.write(base64.b64decode(data))
