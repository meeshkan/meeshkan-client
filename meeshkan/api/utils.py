from typing import Optional
import os
import logging
from http import HTTPStatus

import requests
import ipykernel
from notebook import notebookapp

from ..core.service import Service

__all__ = ["submit_notebook"]

LOGGER = logging.getLogger(__file__)

def submit_notebook(job_name: str = None, poll_interval: Optional[float] = None, notebook_password: str = None):
    """
    Submits the current notebook to the Meeshkan agent. Requires the agent to be running.
    Can only be called from within a notebook instance.
    On password-protected notebooks, the `password` argument must be supplied a-priori.
    """
    try:  # Verifies this was run in an IPython with a non-terminal kernel
        ipython = get_ipython()  # type: ignore
        if ipython.__class__.__name__ != "ZMQInteractiveShell":  # Used for communication with the IPyKernel
            # This is only meant to run from Jupyter Notebook; once converted by Meeshkan, it may potentially run with
            # ipython interpreter, so `get_ipython()` will exist but will be 'TerminalInteractiveShell' instead.
            return
    except NameError:  # Not ran from IPython
        raise RuntimeError("`run_notebook` can only be run from within a jupyter notebook!")

    connection_file = os.path.basename(ipykernel.get_connection_file())
    # Connection file is e.g. /run/user/1000/jupyter/kernel-c5f9d570-3c1c-4ef9-b3b9-d8de11ce4d0c.json
    # kernel id is then c5f9d570-3c1c-4ef9-b3b9-d8de11ce4d0c
    # responses from Jupyter Notebook API are described here:
    # pylint: disable=line-too-long
    #     http://petstore.swagger.io/?url=https://raw.githubusercontent.com/jupyter/notebook/master/notebook/services/api/api.yaml
    kernel_id = os.path.splitext(connection_file)[0].split('-', 1)[1]
    for srv in notebookapp.list_running_servers():
        sessions_url = "{url}api/sessions".format(url=srv['url'])
        sess = _notebook_authenticated_session_or_none(base_url=srv['url'], uses_password=srv['password'],
                                                       port=srv['port'], notebook_password=notebook_password)
        if sess is None:
            continue

        if srv['token']:
            sessions_url += "?token={token}".format(token=srv["token"])

        nb_sessions = sess.get(sessions_url).json()
        sess.close()
        for nb_sess in nb_sessions:
            if nb_sess['kernel']['id'] == kernel_id:
                path = os.path.join(srv['notebook_dir'], nb_sess['notebook']['path'])
                return Service.api().submit((path,), name=job_name, poll_interval=poll_interval)  # Submit notebook


def _notebook_authenticated_session_or_none(base_url: str, uses_password: bool, port: int,
                                            notebook_password: str = None) -> Optional[requests.Session]:
    """Attempts to create a new requests.Session with access to the Notebook Server API:
            https://github.com/jupyter/jupyter/wiki/Jupyter-Notebook-Server-API
        This function does not handle token-based access.

        This function does not raise; instead, it prints any errors and returns None, failing silently.

        :param base_url: base URL to access notebook server API
        :param uses_password: whether the notebook server uses password protection
        :param port: port used in the base URL; used for prints
        :param notebook_password: the password to use in password protected servers (optional)
        :return authenticated requests.Session with access to the API, or None if fails.
    """
    login_url = "{url}login".format(url=base_url)
    sess = requests.Session()
    if not uses_password:
        return sess

    if notebook_password is None:
        print("Skipping notebook server on port {port} as it's password-protected".format(port=port))
        return None

    # Cookie authorization

    # 1. get the cookie xsrf (cross-site-request-forgery) from the login page
    res = sess.get(login_url)
    filtered_res = [line for line in res.text.splitlines() if "_xsrf" in line]
    if len(filtered_res) != 1:
        sess.close()
        logging.warning("Multiple xsrf cookie fields found in notebook loging page!")
        return None
    # Break the relevant line; it looks like this: <input type="hidden" name="_xsrf" value="..."/>
    xsrf = filtered_res[0].split("\"")[-2]

    # 2. attempt to authenticate
    res = sess.post(login_url, data={"_xsrf": xsrf, "password": notebook_password})
    if res.status_code != HTTPStatus.OK:
        print("Cannot authenticate to notebook server on port {port}! Did you provide the correct "
              "password? Skipping...".format(port=port))
        sess.close()
        return None
    return sess
