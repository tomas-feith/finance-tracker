"""Tests for the free-port picker.

The interesting case is an occupied port: on Windows a bare bind() succeeds
even when another process holds the port, so is_free had to ask for exclusive
semantics explicitly. These tests hold a real listening socket open, which is
what the launch scripts actually collide with.

Run either way:
    python tests/test_freeport.py     # plain asserts
    pytest                             # auto-discovered test_* functions
"""
import socket
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from freeport import find_free_port, is_free


@contextmanager
def listening(reuse=True):
    """A real server socket on an OS-assigned port, as Streamlit would hold.

    Defaults to SO_REUSEADDR because that is what uvicorn sets, and it is
    exactly the case a bind()-only probe gets wrong on Windows: a second bind
    to the same port succeeds, so the port looks free while a dashboard is
    serving on it.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if reuse:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("", 0))
        srv.listen(1)
        yield srv.getsockname()[1]
    finally:
        srv.close()


def test_occupied_port_is_not_free():
    with listening() as port:
        assert is_free(port) is False


def test_reuseaddr_listener_is_not_free():
    """The regression: a SO_REUSEADDR listener (what Streamlit runs) is still
    detected, even though a second bind() to its port would succeed."""
    with listening(reuse=True) as port:
        assert is_free(port) is False


def test_free_port_is_free():
    with listening() as port:
        pass                       # closed on exit, so the port is now free
    assert is_free(port) is True


def test_find_skips_occupied_preferred_port():
    with listening() as port:
        chosen = find_free_port(port)
        assert chosen != port
        assert chosen > port
        assert is_free(chosen)


def test_find_returns_preferred_when_free():
    with listening() as port:
        pass
    assert find_free_port(port) == port


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
