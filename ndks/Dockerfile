# Next Door Key Simulator, patched for multi-KME FULL MESH.
#
# Upstream: https://github.com/CreepPork/next-door-key-simulator
# Patch (see ndks/patches/, documented in the thesis):
#   * scanner.py     - network I/O moved OUTSIDE the KME lock + request timeout
#                      (upstream held the lock during blocking calls to every
#                       other KME; in full mesh the circular wait deadlocked)
#   * broadcaster.py - explicit timeout on key-exchange broadcasts
FROM creeppork/next-door-key-simulator:latest
COPY patches/scanner.py     /opt/next-door-key-simulator/network/scanner.py
COPY patches/broadcaster.py /opt/next-door-key-simulator/network/broadcaster.py
