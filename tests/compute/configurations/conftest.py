import pytest

from tests.support.configurations.fixtures import iol as iol
from tests.support.configurations.fixtures import scripted_session as scripted_session


@pytest.fixture
def isolated_compute_project():
    # The shared compute_project fixture reuses a fixed ID in a process-wide
    # manager. Native file tests need their own project and current temp root.
    from uuid import uuid4

    from gns3server.compute.project_manager import ProjectManager

    return ProjectManager.instance().create_project(project_id=str(uuid4()))
