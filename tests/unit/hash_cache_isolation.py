"""Shared test helper (#194): point the PBO hash cache at a throwaway directory.

Test modules whose code paths reach tools.package.hash_cache (through snafu_optional's
whole-PBO hashing) call enter() from setUpModule and leave() from tearDownModule, so they
never read or write the user's ~/.cache/hollow-country/pbo-hash. test_hash_cache lists them.
"""
import os
import shutil
import tempfile

_STACK = []


def enter():
    directory = tempfile.mkdtemp(prefix='hc-hash-cache-')
    _STACK.append((directory, os.environ.get('HC_HASH_CACHE_DIR')))
    os.environ['HC_HASH_CACHE_DIR'] = directory
    return directory


def leave():
    directory, previous = _STACK.pop()
    if previous is None:
        os.environ.pop('HC_HASH_CACHE_DIR', None)
    else:
        os.environ['HC_HASH_CACHE_DIR'] = previous
    shutil.rmtree(directory, ignore_errors=True)
