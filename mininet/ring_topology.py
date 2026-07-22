#!/usr/bin/env python
"""
Mininet mesh topology for the QSDN demo.

11 OpenFlow switches, one host each. The DPIDs are FIXED and must match
config/onos_mapping.yaml so the adapter can map each discovered device to
its KMS city:

    s1 of:...01 = Milano      s2 of:...02 = Torino     s3 of:...03 = Genova
    s4 of:...04 = Venezia     s5 of:...05 = Bologna     s6 of:...06 = Parma
    s7 of:...07 = La Spezia   s8 of:...08 = Padova      s9 of:...09 = Pavia
    s10 of:...0a = Ferrara    s11 of:...0b = Verona

Parma, La Spezia, Padova, Pavia and Ferrara are TRUSTED RELAY nodes (Verona is
an extra main KMS) added so every physical link respects the QKD fibre-distance
constraint AND the PCE gets redundant west/east corridors to reroute on (see
config/topology.yaml for the rationale). Links:

    Milano-Torino, Torino-Genova, Genova-La Spezia, La Spezia-Parma,
    Milano-Parma            (closes a ring: Milano-Torino-Genova-La Spezia-Parma)
    Parma-Bologna            (spur)
    Parma-Padova, Padova-Venezia   (spur)
    Milano-Pavia, Pavia-Genova, Pavia-Parma        (west redundancy)
    Bologna-Ferrara, Ferrara-Padova, Ferrara-Venezia   (east redundancy)
    Verona-Padova, Verona-Ferrara, Verona-Venezia  (north-east mesh)

Run inside the mininet container, pointing at the ONOS controller:
    docker exec -it mininet-c python ring_topology.py
"""
import os
import socket

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo

# Resolve the ONOS controller by its Docker service name (no static IP needed).
ONOS_HOST = os.environ.get("ONOS_HOST", "onos")
ONOS_OF_PORT = 6653


def _onos_ip() -> str:
    """Resolve the 'onos' service name to its current container IP."""
    return socket.gethostbyname(ONOS_HOST)

CITIES = [
    ("s1", "0000000000000001"),  # Milano
    ("s2", "0000000000000002"),  # Torino
    ("s3", "0000000000000003"),  # Genova
    ("s4", "0000000000000004"),  # Venezia
    ("s5", "0000000000000005"),  # Bologna
    ("s6", "0000000000000006"),  # Parma (trusted relay)
    ("s7", "0000000000000007"),  # La Spezia (trusted relay)
    ("s8", "0000000000000008"),  # Padova (trusted relay)
    ("s9", "0000000000000009"),  # Pavia (trusted relay)
    ("s10", "000000000000000a"), # Ferrara (trusted relay)
    ("s11", "000000000000000b"), # Verona (main KMS)
]

# Explicit mesh edges (city pairs), one per physical QKD link.
LINKS = [
    ("s1", "s2"),   # Milano-Torino
    ("s2", "s3"),   # Torino-Genova
    ("s3", "s7"),   # Genova-La Spezia
    ("s7", "s6"),   # La Spezia-Parma
    ("s1", "s6"),   # Milano-Parma
    ("s6", "s5"),   # Parma-Bologna
    ("s6", "s8"),   # Parma-Padova
    ("s8", "s4"),   # Padova-Venezia
    # Pavia relay — west redundancy.
    ("s1", "s9"),   # Milano-Pavia
    ("s9", "s3"),   # Pavia-Genova
    ("s9", "s6"),   # Pavia-Parma
    # Ferrara relay — east redundancy.
    ("s5", "s10"),  # Bologna-Ferrara
    ("s10", "s8"),  # Ferrara-Padova
    ("s10", "s4"),  # Ferrara-Venezia
    # Verona main KMS — dense north-east mesh.
    ("s11", "s8"),  # Verona-Padova
    ("s11", "s10"), # Verona-Ferrara
    ("s11", "s4"),  # Verona-Venezia
]


class MeshTopo(Topo):
    def build(self):
        for index, (name, dpid) in enumerate(CITIES, start=1):
            self.addSwitch(name, dpid=dpid, protocols="OpenFlow13")
            host = self.addHost("h%d" % index, ip="10.0.0.%d/24" % index)
            self.addLink(host, name)

        for a, b in LINKS:
            self.addLink(a, b)


def run():
    net = Mininet(topo=MeshTopo(), controller=None,
                  switch=OVSSwitch, autoSetMacs=True)
    net.addController(RemoteController("c0", ip=_onos_ip(), port=ONOS_OF_PORT))
    net.start()
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
