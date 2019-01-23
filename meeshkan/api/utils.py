from typing import Optional, Callable, List, Dict, Any
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
    On password-protected notebooks, the `password` argument must be supplied.
    """
    try:
        path = get_notebook_path_generic(get_ipython_function=globals().get('get_ipython'),
                                         list_servers_function=notebookapp.list_running_servers,
                                         connection_file=ipykernel.get_connection_file(),
                                         notebook_password=notebook_password)
        if path is not None:
            return Service.api().submit((path,), name=job_name, poll_interval=poll_interval)  # Submit notebook
    except ValueError:  # Ran from ipython but not from jupyter notebook -> expected behaviour
        return None
    # In theory, should never get here...
    raise RuntimeError("Something went terribly wrong; Meeshkan couldn't locate the matching notebook server! Contact"
                       " Meeshkan development (dev@meeshkan.com) if you see this message.")


def get_notebook_path_generic(get_ipython_function: Optional[Callable[[], Any]],
                              list_servers_function: Callable[[], List[Dict]], connection_file: str,
                              notebook_password: Optional[str]) -> Optional[str]:
    """Looks up the name of the current notebook (i.e. the one from which this function was called).

    :param get_ipython_function: Optional callable that returns the ipython shell used. Used to verify the executing
                                    interpreter.
    :param list_servers_function: Callable that returns a list of dictionaries, describing the currently running
                                    notebook servers.
    :param connection_file: Location to file containing the IPyKernel details
    :param notebook_password: Password for the notebook server if needed.

    :return Location to the current notebook if found, otherwise None.
    :raises RuntimeError if get_ipython_function is None
    :raises ValueError if calling get_ipython_function returns a non-ZMQ Interactive Shell.
    """
    try:  # Verifies this was run in an IPython with a non-terminal kernel
        ipython = get_ipython_function()  # type: ignore
        if ipython.__class__.__name__ != "ZMQInteractiveShell":  # Used for communication with the IPyKernel
            # This is only meant to run from Jupyter Notebook; once converted by Meeshkan, it may potentially run with
            # ipython interpreter, so `get_ipython()` will exist but will be 'TerminalInteractiveShell' instead.
            raise ValueError("Not run from notebook interpreter")
    except TypeError:  # Not ran from IPython
        raise RuntimeError("Can only get path to notebook if run from within a notebook!")

    connection_file = os.path.basename(connection_file or ipykernel.get_connection_file())
    # Connection file is e.g. /run/user/1000/jupyter/kernel-c5f9d570-3c1c-4ef9-b3b9-d8de11ce4d0c.json
    # kernel id is then c5f9d570-3c1c-4ef9-b3b9-d8de11ce4d0c
    # responses from Jupyter Notebook API are described here:
    # pylint: disable=line-too-long
    #     http://petstore.swagger.io/?url=https://raw.githubusercontent.com/jupyter/notebook/master/notebook/services/api/api.yaml
    kernel_id = os.path.splitext(connection_file)[0].split('-', 1)[1]
    for srv in list_servers_function():
        sessions_url = "{url}api/sessions".format(url=srv['url'])
        sess = _notebook_authenticated_session_or_none(base_url=srv['url'], port=srv['port'],
                                                       notebook_password=notebook_password)
        if sess is None:
            continue

        if srv['token']:
            sessions_url += "?token={token}".format(token=srv["token"])

        nb_sessions = sess.get(sessions_url).json()
        sess.close()
        for nb_sess in nb_sessions:
            if nb_sess['kernel']['id'] == kernel_id:  # Found path!
                return os.path.join(srv['notebook_dir'], nb_sess['notebook']['path'])
    return None


def _notebook_authenticated_session_or_none(base_url: str, port: int,
                                            notebook_password: str = None) -> Optional[requests.Session]:
    """Attempts to create a new requests.Session with access to the Notebook Server API:
            https://github.com/jupyter/jupyter/wiki/Jupyter-Notebook-Server-API
        This function does not handle token-based access.

        This function does not raise; instead, it prints any errors and returns None, failing silently.

        :param base_url: base URL to access notebook server API
        :param port: port used in the base URL; used for prints
        :param notebook_password: the password to use in password protected servers (optional)
        :return authenticated requests.Session with access to the API, or None if fails.
    """
    login_url = "{url}login".format(url=base_url)
    sess = requests.Session()

    # Cookie authorization

    # 1. get the cookie xsrf (cross-site-request-forgery) from the login page
    res = sess.get(login_url)
    filtered_res = [line for line in res.text.splitlines() if "_xsrf" in line]
    if len(filtered_res) != 1:
        # No _xsrf reference -> no password is needed
        # Multiple _xsrf reference -> requires a token
        # --> either way, no password.
        return sess

    # Requires password but no password was given
    if notebook_password is None:
        print("Skipping notebook server on port {port} as it's password-protected".format(port=port))
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
