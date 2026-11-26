"""SHA-256 crypt against vectors produced by ``openssl passwd -5``."""

import shutil
import subprocess

import pytest

from gns3server.services.configurations.shared.password_hash import MAX_SALT, sha256_crypt, sha512_crypt


@pytest.mark.parametrize(
    ("password", "salt", "expected"),
    [
        ("Palo1234", "abcdefgh", "$5$abcdefgh$vOg35JND40maa9/.JqZ0sOAywE2jfv.t31XYK.iSOFD"),
        ("a", "x", "$5$x$85aGabM7xSEYcp0wkefjwtqWAYi1Rrq3b01Gtllmmh7"),
    ],
)
def test_known_vectors(password, salt, expected):
    assert sha256_crypt(password, salt) == expected


def test_a_random_salt_is_used_and_long_salts_are_cut():
    first, second = sha256_crypt("secret"), sha256_crypt("secret")
    assert first != second and len(first.split("$")[2]) == MAX_SALT
    assert sha256_crypt("secret", "s" * 40) == sha256_crypt("secret", "s" * MAX_SALT)


def test_sha512_crypt_matches_the_reference_implementation():
    # A published test vector of the algorithm (Drepper's specification).
    assert sha512_crypt("Hello world!", "saltstring") == (
        "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1"
    )
    openssl = shutil.which("openssl")
    if openssl:
        reference = subprocess.run(  # noqa: S603
            [openssl, "passwd", "-6", "-salt", "testsalt", "-stdin"],
            input="päss word\n",
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert sha512_crypt("päss word", "testsalt") == reference
