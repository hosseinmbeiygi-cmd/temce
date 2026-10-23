import sys
text = sys.argv[1]
print("LEN", len(text))
print("REPR_TAIL", repr(text[-60:]))
print("LINES_TAIL", repr(text.splitlines()[-3:]))
