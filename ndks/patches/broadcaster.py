import json
import os

import requests

# Patched for multi-KME full mesh (QSDN thesis): explicit timeout so a slow
# or wedged peer cannot stall key-exchange broadcasts (which run inside a
# Flask request that holds both app locks).
REQUEST_TIMEOUT = float(os.getenv('BROADCAST_TIMEOUT', '5'))


class Broadcaster:
    def __init__(self):
        self.other_kmes = os.getenv('OTHER_KMES').split(',')
        self.certs = (os.getenv('KME_CERT'), os.getenv('KME_KEY'))

    def send_keys(self, master_sae_id: str, slave_sae_id: str, keys: list) -> None:
        self.__broadcast('/api/v1/kme/keys/exchange', {
            'master_sae_id': master_sae_id, 'slave_sae_id': slave_sae_id, 'keys': keys
        })

    def remove_keys(self, master_sae_id: str, slave_sae_id: str, keys: list) -> None:
        self.__broadcast('/api/v1/kme/keys/remove', {
            'master_sae_id': master_sae_id, 'slave_sae_id': slave_sae_id, 'keys': keys
        })

    def __broadcast(self, url: str, data: dict) -> None:
        data = json.loads(json.dumps(data, default=str))

        for kme in self.other_kmes:
            try:
                requests.post(f'{kme}{url}', verify=False, cert=self.certs,
                              json=data, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.RequestException as exception:
                print(f'Broadcast to {kme}{url} failed: {exception}')
