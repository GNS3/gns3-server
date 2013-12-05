import sys
import os
import pytest
import subprocess
import time


@pytest.fixture(scope="session", autouse=True)
def server(request):

    cwd = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(cwd, "../gns3server/main.py")
    process = subprocess.Popen([sys.executable, server_script, "--port=8000"])
    time.sleep(0.1)  # give some time for the process to start
    request.addfinalizer(process.kill)
    return process
