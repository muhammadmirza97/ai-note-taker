import socket
import unittest

from launcher.readiness import infer_port_from_url, is_port_open, port_freed


class ReadinessTest(unittest.TestCase):
    def test_infers_port_from_url(self):
        self.assertEqual(infer_port_from_url("http://127.0.0.1:8765"), 8765)
        self.assertIsNone(infer_port_from_url("http://localhost"))

    def test_port_check_detects_open_and_freed_port(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        self.assertTrue(is_port_open(port))
        server.close()
        self.assertTrue(port_freed(port, timeout_seconds=3))


if __name__ == "__main__":
    unittest.main()

