"""SHA-crypt password hashes: ``$5$`` (what a PAN-OS ``<phash>`` accepts) and ``$6$`` (Viptela accounts), so no
plaintext password has to reach the guest.

The standard library no longer ships ``crypt``, so the algorithm of Ulrich Drepper's specification
(https://www.akkadia.org/drepper/SHA-crypt.txt) is implemented here, with the default 5000 rounds
(the same output as ``openssl passwd -5`` / ``-6``).
"""

import hashlib
import secrets

ALPHABET = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
ROUNDS = 5000
MAX_SALT = 16
# Digest byte triples (B2, B1, B0) in the order the specification encodes them.
SHA256_ORDER = (
    (0, 10, 20), (21, 1, 11), (12, 22, 2), (3, 13, 23), (24, 4, 14),
    (15, 25, 5), (6, 16, 26), (27, 7, 17), (18, 28, 8), (9, 19, 29),
)  # fmt: skip
SHA512_ORDER = (
    (0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4), (47, 5, 26), (6, 27, 48),
    (28, 49, 7), (50, 8, 29), (9, 30, 51), (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13),
    (56, 14, 35), (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19), (62, 20, 41),
)  # fmt: skip


def _characters(word, count):
    return "".join(ALPHABET[(word >> (6 * index)) & 0x3F] for index in range(count))


def _repeat(digest, length):
    return (digest * (length // len(digest) + 1))[:length]


def _sha_crypt(algorithm, password, salt):
    """The digest of the SHA-crypt rounds, and the salt as used."""
    secret = password.encode("utf-8")
    salt = salt if salt is not None else "".join(secrets.choice(ALPHABET) for _ in range(MAX_SALT))
    salt_bytes = salt[:MAX_SALT].encode("ascii")
    alternate = algorithm(secret + salt_bytes + secret).digest()
    context = algorithm(secret + salt_bytes)
    context.update(_repeat(alternate, len(secret)))
    length = len(secret)
    while length > 0:
        context.update(alternate if length & 1 else secret)
        length >>= 1
    digest = context.digest()
    password_bytes = _repeat(algorithm(secret * len(secret)).digest(), len(secret))
    salt_sequence = _repeat(algorithm(salt_bytes * (16 + digest[0])).digest(), len(salt_bytes))
    for index in range(ROUNDS):
        round_context = algorithm()
        round_context.update(password_bytes if index & 1 else digest)
        if index % 3:
            round_context.update(salt_sequence)
        if index % 7:
            round_context.update(password_bytes)
        round_context.update(digest if index & 1 else password_bytes)
        digest = round_context.digest()
    return digest, salt_bytes.decode("ascii")


def _groups(digest, order):
    return "".join(_characters((digest[a] << 16) | (digest[b] << 8) | digest[c], 4) for a, b, c in order)


def sha256_crypt(password, salt=None):
    """``$5$<salt>$<hash>`` of the password (a random salt unless one is given)."""
    digest, salt = _sha_crypt(hashlib.sha256, password, salt)
    return f"$5${salt}${_groups(digest, SHA256_ORDER)}{_characters((digest[31] << 8) | digest[30], 3)}"


def sha512_crypt(password, salt=None):
    """``$6$<salt>$<hash>`` of the password (a random salt unless one is given)."""
    digest, salt = _sha_crypt(hashlib.sha512, password, salt)
    return f"$6${salt}${_groups(digest, SHA512_ORDER)}{_characters(digest[63], 2)}"
