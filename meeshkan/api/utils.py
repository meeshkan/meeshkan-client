from typing import List
import os
import ipykernel
from notebook import notebookapp
import requests
import json

from ..__utils__ import _get_api

__all__ = ["run_notebook"]  # type: List[str]


def run_notebook():
    try:
        ip = get_ipython()  # Verifies this was run in Jupyter
        if ip.__class__.__name__ != "ZMQInteractiveShell":  # Used for communication with the IPyKernel
            return
    except NameError:
        raise RuntimeError("`run_notebook` can only be run from within a jupyter notebook!")
    connection_file = os.path.basename(ipykernel.get_connection_file())
    # Connection file is e.g. /run/user/1000/jupyter/kernel-c5f9d570-3c1c-4ef9-b3b9-d8de11ce4d0c.json
    # kernel id is then c5f9d570-3c1c-4ef9-b3b9-d8de11ce4d0c
    kernel_id = os.path.splitext(connection_file)[0].split('-', 1)[1]
    for srv in notebookapp.list_running_servers():
        url = srv['url'] + "api/sessions"
        if srv['password']:
            print("Skipping notebook server on port {port} as it's password-protected".format(port=srv['port']))
            continue
        if srv['token']:
            url += "?token={token}".format(token=srv["token"])

        sessions = requests.get(url).json()
        for sess in sessions:
            if sess['kernel']['id'] == kernel_id:
                path = os.path.join(srv['notebook_dir'], sess['notebook']['path'])
                _get_api().submit((path,))
                return

