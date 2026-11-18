"""One offline HTTP smoke; fixtures are synthetic, never DayZ evidence."""
import io
import json
from pathlib import Path
import tempfile
import unittest


class WebmapSmoke(unittest.TestCase):
    def test_local_readonly_map_rereads_bounded_complete_snapshots(self):
        from tools.webmap import server

        class Connection:
            def __init__(self, request):
                self.input = io.BytesIO(request)
                self.output = io.BytesIO()

            def makefile(self, *_args):
                return self.input

            def sendall(self, data):
                self.output.write(data)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "snapshot.json"
            image = root / "operator.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic-not-a-game-image")
            handler = server.make_handler(snapshot, image)

            def get(path):
                connection = Connection(f"GET {path} HTTP/1.0\r\n\r\n".encode())
                handler(connection, ("127.0.0.1", 12345), None)
                head, body = connection.output.getvalue().split(b"\r\n\r\n", 1)
                return int(head.split()[1]), head, body

            self.assertEqual(server.BIND_ADDRESS, "127.0.0.1")
            self.assertEqual(get("/snapshot.json")[0], 503)
            fixture = {"version": 1, "time": 20, "map": "chernarusplus",
                       "layers": {"players": [{"id": "synthetic", "x": 1, "z": 2,
                                               "label": "<fixture>", "detail": "offline"}]},
                       "routes": [{"layer": "players", "id": "synthetic-route", "label": "fixture",
                                   "points": [[1, 2], [3, 4]]}]}
            snapshot.write_text(json.dumps(fixture), encoding="utf-8")
            status, headers, body = get("/snapshot.json")
            self.assertEqual(status, 200)
            self.assertIn(b"no-store", headers)
            self.assertEqual(json.loads(body), fixture)
            fixture["time"] = 40
            snapshot.write_text(json.dumps(fixture), encoding="utf-8")
            self.assertEqual(json.loads(get("/snapshot.json")[2])["time"], 40)
            intent = root / "snapshot.json.tmp"
            intent.write_text("synthetic intent", encoding="utf-8")
            self.assertEqual(get("/snapshot.json")[0], 503)
            intent.unlink()
            snapshot.write_bytes(b"{" + b" " * server.MAX_SNAPSHOT_BYTES)
            self.assertEqual(get("/snapshot.json")[0], 503)
            snapshot.write_text('{"version":1', encoding="utf-8")
            self.assertEqual(get("/snapshot.json")[0], 503)
            self.assertEqual(get("/../snapshot.json.bak")[0], 404)
            self.assertEqual(get("/map-image")[2], image.read_bytes())
            self.assertEqual(get("/")[0], 200)
            self.assertIn(b"<canvas", get("/")[2])
            self.assertEqual(server.make_handler(snapshot, None).map_image, None)
