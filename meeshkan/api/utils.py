from typing import Optional, Callable, List, Dict, Any
import os
import logging
from http import HTTPStatus
from pathlib import Path
import tempfile
import inspect
from random import choice
import string

from dill.detect import globalvars
import requests
import ipykernel
from notebook import notebookapp

from ..core.service import Service
from ..core.job.jobs import Job
from ..exceptions import MismatchingIPythonKernelException
from ..core.serializer import Serializer

__all__ = ["submit_notebook", "submit_function"]

LOGGER = logging.getLogger(__file__)

def submit_notebook(job_name: str = None, report_interval: Optional[float] = None, notebook_password: str = None):
    """
    Submits the current notebook to the Meeshkan agent. Requires the agent to be running.
    Can only be called from within a notebook instance.
    On password-protected notebooks, the `password` argument must be supplied.
    """
    # try:
    try:
        # ignoring Mypy static type checking as `get_ipython` will only be dynamically defined if the calling script
        # was run from ipython shell (terminal or ZMQ based)
        get_ipython_func = get_ipython  # type: ignore
    except NameError:
        get_ipython_func = None

    try:
        api = Service.api()  # Raise if agent is not running
        path = _get_notebook_path_generic(get_ipython_function=get_ipython_func,
                                          list_servers_function=notebookapp.list_running_servers,
                                          connection_file_function=ipykernel.get_connection_file,
                                          notebook_password=notebook_password)
        return api.submit((path,), name=job_name, poll_interval=report_interval)  # Submit notebook
    except MismatchingIPythonKernelException:  # Ran from ipython but not from jupyter notebook -> expected behaviour
        print("submit_notebook(): Not run from notebook interpreter; ignoring...")
    return None  # Return None so we don't crash the notebook/caller;


def submit_function(function_or_name, *args, **kwargs):
    api = Service.api()  # Raise if agent is not running
    try:
        globs = get_ipython().user_ns
    except NameError:
        globs = globals()

    if callable(function_or_name):
        func = function_or_name
    else:
        func = globs[function_or_name]  # Attempt to get Callable from global scope

    script_path = Path(tempfile.mkdtemp())  # Create a temporary folder for the script and all that
    globs_file = _write_globals(func, script_path)  # Serialize and write the globals relevant for the function
    # Write the actual code  (contains a logical entry point and the function code)
    script_file = _write_function_script_file(script_path, globs_file, func, args, kwargs)

    return api.submit((str(script_file), ))  # Create a job


def _write_function_script_file(path: Path, globs_file: Path, entry_point_function, args, kwargs) -> Path:
    """Writes a .py file with basic functionality: an entry point, a deserializer, and a globals-loading function.

    :param path: The path to write in (absolute path)
    :param globs_file: Absolute path to global file
    :param entry_point_function: Callable - entry point function
    :param args: Serialized *args argument for entry point function
    :param kwargs: Serialized **kwargs argument for entry point function
    :return Path to generated script file
    """
    # Get random function names and serialize args and kwargs
    load_globs_func_name = _generate_random_function_name()
    deserialize_func_name = _generate_random_function_name()
    serialized_args = repr(Serializer.serialize(args))  # `repr` to escape any special characters
    serialized_kwargs = repr(Serializer.serialize(kwargs))
    script_file = path.joinpath("{fname}.ipy".format(fname=entry_point_function.__name__))

    with script_file.open('w') as script_fd:
        script_fd.write(Serializer.deserialize_func_as_str(deserialize_func_name))
        script_fd.write("\n\n")
        script_fd.write(_global_loading_function(load_globs_func_name, globs_file, deserialize_func_name))
        script_fd.write(inspect.getsource(entry_point_function))
        script_fd.write("\n\n")
        script_fd.write(_entry_point_for_custom_script(entry_point_function.__name__, load_globs_func_name,
                                                       deserialize_func_name, serialized_args, serialized_kwargs))
        script_fd.flush()
    return script_file


def _write_globals(func, path: Path) -> Path:
    """Fetches, serialized and writes current globals required for `func` to `path`.

    :param func: A callable that may or may not use global variables
    :param path: Where to write the serialized globals
    :return Path object to the serialized globals file
    """
    globs = globalvars(func)  # Globals that are relevant for the function to run
    globs.update({'__name__': '__main__'})  # Include the entry point for the script
    globs_serialized = Serializer.serialize(globs)
    globs_file = path.joinpath("globs.msk")
    with globs_file.open('w') as globs_fd:
        globs_fd.write(globs_serialized)
        globs_fd.flush()
    return globs_file


def _entry_point_for_custom_script(func_name, load_globals_func_name, deserialize_func_name, args, kwargs):
    """Writes an entry point to `func_name` by first calling the globals-loading function."""
    return "if __name__ == \"__main__\":\n" \
           "    {load_globals}()\n" \
           "    {func}(*{deserialize}({args}), **{deserialize}({kwargs}))\n".format(load_globals=load_globals_func_name,
                                                                                    func=func_name, args=args,
                                                                                    deserialize=deserialize_func_name,
                                                                                    kwargs=kwargs)


def _global_loading_function(func_name, globals_file, deserialize_func_name):
    """Writes a globals-loading function: reads from a given file and loads to `globals`, after which it deletes the
       globals source file."""
    return "def {func_name}():\n" \
           "    import os\n" \
           "    with open('{globs_file}', 'rb') as globs_fd:\n" \
           "        globs = {deserialize_func_name}(globs_fd.read().decode())\n" \
           "    globals().update(globs)\n" \
           "    os.unlink('{globs_file}')\n".format(globs_file=str(globals_file), func_name=func_name,
                                                    deserialize_func_name=deserialize_func_name)


def _generate_random_function_name(length=16):
    characters = string.ascii_letters + '_'
    return "".join(choice(characters) for _ in range(length))


def _verify_ipython_notebook_kernel(ipython_kernel):
    valid_type = "ZMQInteractiveShell"
    kernel_type = ipython_kernel.__class__.__name__
    if ipython_kernel.__class__.__name__ != valid_type:  # Used for communication with the IPyKernel
        raise MismatchingIPythonKernelException(found_kernel_type=kernel_type, expected_kernel_type=valid_type)


def _get_notebook_path_generic(get_ipython_function: Optional[Callable[[], Any]],
                               list_servers_function: Callable[[], List[Dict]],
                               connection_file_function: Callable[[], str],
                               notebook_password: str = None) -> str:
    """Looks up the name of the current notebook (i.e. the one from which this function was called).

    :param list_servers_function: Callable that returns a list of dictionaries, describing the currently running
                                    notebook servers
    :param connection_file_function: Callable that returns the location to file containing the IPyKernel details
    :param notebook_password: Password for the notebook server if needed.

    :return Location to the current notebook if found, otherwise None.
    :raises RuntimeError if get_ipython_function is None, if invalid connection file is given,
                            or if notebook path is not found
    :raises MismatchingIPythonKernelException if calling get_ipython_function returns a non-ZMQ Interactive Shell.
    """
    if get_ipython_function is None:  # Can't verify ipython kernel...
        raise RuntimeError("Can only get path to notebook if run from within a notebook!")
    # This is only meant to run from Jupyter Notebook; once converted by Meeshkan, it may potentially run with
    # ipython interpreter, so `get_ipython()` will exist but will be 'TerminalInteractiveShell' instead.
    _verify_ipython_notebook_kernel(get_ipython_function())  # Verifies this was run with non-terminal IPython kernel

    connection_file = connection_file_function()
    if not os.path.isfile(connection_file):
        LOGGER.debug("Notebook connection file given but does not exist! %s", connection_file)
        raise RuntimeError("Cannot find connection file {file}".format(file=connection_file))
    connection_file = os.path.basename(connection_file)
    # Connection file is e.g. /run/user/1000/jupyter/kernel-c5f9d570-3c1c-4ef9-b3b9-d8de11ce4d0c.json
    # kernel id is then c5f9d570-3c1c-4ef9-b3b9-d8de11ce4d0c
    # responses from Jupyter Notebook API are described here:
    # pylint: disable=line-too-long
    #     http://petstore.swagger.io/?url=https://raw.githubusercontent.com/jupyter/notebook/master/notebook/services/api/api.yaml
    kernel_id = os.path.splitext(connection_file)[0].split('-', 1)[1]
    for srv in list_servers_function():
        sessions_url = "{url}api/sessions".format(url=srv['url'])
        try:
            sess = _notebook_authenticated_session(base_url=srv['url'], port=srv['port'], nb_password=notebook_password)
        except RuntimeError as excinfo:  # Failure to authenticate
            print(excinfo)
            continue

        if srv['token']:
            sessions_url += "?token={token}".format(token=srv['token'])

        nb_sessions = sess.get(sessions_url).json()
        sess.close()
        for nb_sess in nb_sessions:
            if nb_sess['kernel']['id'] == kernel_id:  # Found path!
                return os.path.join(srv['notebook_dir'], nb_sess['notebook']['path'])
    raise RuntimeError("Something went terribly wrong; Meeshkan couldn't locate the matching notebook server! Contact "
                       "Meeshkan development (via Github or meeshkan-community Slack channel) if you see this message.")


def _notebook_authenticated_session(base_url: str, port: int, nb_password: str = None) -> requests.Session:
    """Attempts to create a new requests.Session with access to the Notebook Server API:
            https://github.com/jupyter/jupyter/wiki/Jupyter-Notebook-Server-API
        This function does not handle token-based access.

        This function does not raise; instead, it prints any errors and returns None, failing silently.

        :param base_url: base URL to access notebook server API
        :param port: port used in the base URL; used for prints
        :param nb_password: the password to use in password protected servers (optional)
        :return authenticated requests.Session with access to the API
        :raises RuntimeError on failure to authenticate
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
    if nb_password is None:
        raise RuntimeError("Skipping notebook server on port {port} as it's password-protected".format(port=port))

    # Break the relevant line; it looks like this: <input type="hidden" name="_xsrf" value="..."/>
    xsrf = filtered_res[0].split("\"")[-2]

    # 2. attempt to authenticate
    res = sess.post(login_url, data={"_xsrf": xsrf, "password": nb_password})
    if res.status_code != HTTPStatus.OK:
        sess.close()
        raise RuntimeError("Cannot authenticate to notebook server on port {port}! Did you provide the correct "
                           "password? Skipping...".format(port=port))
    return sess
