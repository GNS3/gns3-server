"""Classify Docker nodes using the same ordered markers on controller and compute."""


def docker_node_kind(console_type, environment):
    if console_type == "docker_exec":
        return "vendor"
    for line in (environment or "").splitlines():
        marker = line.strip().rstrip(",")
        if marker.startswith("GNS3_IOL_RUNNER="):
            return "iol"
        if marker.startswith("GNS3_UNIX_SOCKET_NIO="):
            return "vendor"
    return "standard"


# The saved routing configuration of an FRRouting container, in its persisted ``/etc/frr`` volume, and the file
# a startup configuration is staged in until init.sh installs it (after the volume was seeded from the image).
FRR_VOLUME = "/etc/frr"
FRR_CONFIG = "etc/frr/frr.conf"
FRR_STAGED_CONFIG = "etc/frr/.gns3-startup.conf"


def is_frr_node(console_type, environment, image):
    """An FRRouting container: an image repository named ``frr``, or the GNS3 FRR image's ``FRR_PROFILE`` setting.

    Containers that GNS3 runs as vendor or IOL nodes are never one.
    """
    if docker_node_kind(console_type, environment) != "standard":
        return False
    repository = (image or "").split("@")[0].rsplit("/", 1)[-1].split(":")[0]
    return repository == "frr" or any(
        line.strip().startswith("FRR_PROFILE=") for line in (environment or "").splitlines()
    )
