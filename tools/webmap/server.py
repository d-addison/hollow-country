"""Read-only loopback viewer for HC snapshots. Standard library only."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

BIND_ADDRESS = "127.0.0.1"
MAX_SNAPSHOT_BYTES = 1048576
MAX_LOOTMAP_BYTES = 65536
MAX_IMAGE_BYTES = 32 * 1024 * 1024


def _coordinate(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 15360


def _text(value, limit):
    return isinstance(value, str) and len(value) <= limit


def _validate(data):
    if not isinstance(data, dict):
        raise ValueError("snapshot must be an object")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("unsupported snapshot version")
    if data.get("map") != "chernarusplus" or type(data.get("time")) is not int or data["time"] < 0:
        raise ValueError("invalid map/time")
    layers, routes = data.get("layers"), data.get("routes")
    if not isinstance(layers, dict) or not isinstance(routes, list) or len(routes) > 128:
        raise ValueError("invalid layer/route structure")
    count = 0
    for layer, points in layers.items():
        if not _text(layer, 48) or not layer or not isinstance(points, list):
            raise ValueError("invalid layer")
        count += len(points)
        if count > 1024:
            raise ValueError("point cap exceeded")
        for point in points:
            if not isinstance(point, dict):
                raise ValueError("invalid point")
            valid_text = all(_text(point.get(key), limit) for key, limit in
                             (("id", 96), ("label", 128), ("detail", 256)))
            if not valid_text or not _coordinate(point.get("x")) or not _coordinate(point.get("z")):
                raise ValueError("invalid point fields")
    stats = data.get("layerStats", [])
    if not isinstance(stats, list) or len(stats) > 16:
        raise ValueError("invalid layer stats")
    for row in stats:
        if not isinstance(row, dict) or not _text(row.get("layer"), 48) or not row["layer"]:
            raise ValueError("invalid layer stat")
        total, shown, truncated = (row.get(key) for key in ("total", "shown", "truncated"))
        if not all(type(value) is int for value in (total, shown, truncated)):
            raise ValueError("invalid layer stat counts")
        if not 0 <= shown <= total <= 1000000 or truncated != int(shown < total):
            raise ValueError("inconsistent layer stat")
        # w29 #194: optional count of rows with no drawable position (not in total).
        unplaced = row.get("unplaced", 0)
        if type(unplaced) is not int or not 0 <= unplaced <= 1000000:
            raise ValueError("invalid layer stat unplaced count")
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("invalid route")
        if not all(_text(route.get(key), limit) for key, limit in
                   (("layer", 48), ("id", 96), ("label", 128))):
            raise ValueError("invalid route fields")
        vertices = route.get("points")
        if not isinstance(vertices, list) or not 2 <= len(vertices) <= 64:
            raise ValueError("invalid route vertices")
        for pair in vertices:
            if not isinstance(pair, list) or len(pair) != 2 or not all(map(_coordinate, pair)):
                raise ValueError("invalid route coordinate")


def _validate_lootmap(data):
    """Ground observations, never a complete CE/hoarder inventory count."""
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("unsupported lootmap version")
    if data.get("world") != "chernarusplus" or type(data.get("time")) is not int or data["time"] < 0:
        raise ValueError("invalid lootmap world/time")
    if data.get("state") not in ("pending", "observed", "refused"):
        raise ValueError("invalid lootmap state")
    if data.get("mode") not in ("", "exact", "prefix"):
        raise ValueError("invalid lootmap mode")
    if data.get("scope") != "ground_world_observations" or data.get("census") != "refused_ce_inventory_enumeration_unavailable":
        raise ValueError("unsupported lootmap census claim")
    if not _text(data.get("filter"), 96) or not _text(data.get("reason"), 96):
        raise ValueError("invalid lootmap text")
    for key, cap in (("scanned", 65536), ("cells", 1024), ("matched", 8192), ("truncated", 8192)):
        if type(data.get(key)) is not int or not 0 <= data[key] <= cap:
            raise ValueError("invalid lootmap count")
    types, points = data.get("types"), data.get("points")
    if not isinstance(types, list) or len(types) > 32 or not isinstance(points, list) or len(points) > 128:
        raise ValueError("lootmap output cap")
    by_class = {}
    for row in types:
        if not isinstance(row, dict) or not _text(row.get("className"), 96) or not row["className"]:
            raise ValueError("invalid lootmap class")
        name = row["className"]
        if name in by_class or type(row.get("count")) is not int or not 1 <= row["count"] <= 8192:
            raise ValueError("invalid lootmap class count")
        if type(row.get("nominal")) is not int or not -1 <= row["nominal"] <= 2147483647:
            raise ValueError("invalid lootmap nominal")
        by_class[name] = row["count"]
    if sum(by_class.values()) != data["matched"] or len(points) + data["truncated"] != data["matched"]:
        raise ValueError("inconsistent lootmap counts")
    per_class = {}
    for point in points:
        if not isinstance(point, dict) or not _text(point.get("className"), 96):
            raise ValueError("invalid lootmap point")
        name = point["className"]
        if name not in by_class or not _coordinate(point.get("x")) or not _coordinate(point.get("z")):
            raise ValueError("invalid lootmap position")
        per_class[name] = per_class.get(name, 0) + 1
        if per_class[name] > by_class[name]:
            raise ValueError("inconsistent lootmap points")


def make_handler(snapshot, map_image=None):
    """Only these explicit resources are served; never expose a directory."""
    snapshot_path = Path(snapshot)
    image_path = Path(map_image) if map_image is not None else None
    intent_path = Path(str(snapshot_path) + ".tmp")
    lootmap_path = snapshot_path.with_name("lootmap.json")
    lootmap_intent = Path(str(lootmap_path) + ".tmp")

    class Handler(BaseHTTPRequestHandler):
        map_image = image_path
        server_version = "HCWebmap/1"
        sys_version = ""

        def log_message(self, *_args):
            pass

        def do_GET(self):
            self._serve(False)

        def do_HEAD(self):
            self._serve(True)

        def _serve(self, head_only):
            path = urlsplit(self.path).path
            status, kind, body = 404, "text/plain; charset=utf-8", b"Not found\n"
            try:
                if path in ("/", "/index.html"):
                    body = Path(__file__).with_name("index.html").read_bytes()
                    status, kind = 200, "text/html; charset=utf-8"
                elif path == "/snapshot.json":
                    if intent_path.exists():
                        raise ValueError("snapshot write/recovery pending")
                    with snapshot_path.open("rb") as source:
                        body = source.read(MAX_SNAPSHOT_BYTES + 1)
                    if len(body) > MAX_SNAPSHOT_BYTES or intent_path.exists():
                        raise ValueError("snapshot incomplete or too large")
                    _validate(json.loads(body.decode("utf-8")))
                    status, kind = 200, "application/json; charset=utf-8"
                elif path == "/lootmap.json":
                    if lootmap_intent.exists():
                        raise ValueError("lootmap write/recovery pending")
                    with lootmap_path.open("rb") as source:
                        body = source.read(MAX_LOOTMAP_BYTES + 1)
                    if len(body) > MAX_LOOTMAP_BYTES or lootmap_intent.exists():
                        raise ValueError("lootmap incomplete or too large")
                    _validate_lootmap(json.loads(body.decode("utf-8")))
                    status, kind = 200, "application/json; charset=utf-8"
                elif path == "/map-image" and image_path is not None:
                    with image_path.open("rb") as source:
                        body = source.read(MAX_IMAGE_BYTES + 1)
                    if len(body) > MAX_IMAGE_BYTES:
                        raise ValueError("image too large")
                    if image_path.suffix.lower() == ".png" and body.startswith(b"\x89PNG\r\n\x1a\n"):
                        kind = "image/png"
                    elif image_path.suffix.lower() in (".jpg", ".jpeg") and body.startswith(b"\xff\xd8\xff"):
                        kind = "image/jpeg"
                    else:
                        raise ValueError("expected PNG/JPEG")
                    status = 200
            except (OSError, ValueError, OverflowError, RecursionError):
                status, kind, body = 503, "text/plain; charset=utf-8", b"Resource unavailable; retry after export or recovery\n"
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            if not head_only:
                self.wfile.write(body)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--map-image", type=Path, help="operator's full-map PNG/JPG (not distributed)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.map_image is not None and args.map_image.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        parser.error("map image must be PNG/JPG")
    with HTTPServer((BIND_ADDRESS, args.port), make_handler(args.snapshot, args.map_image)) as server:
        server.timeout = 1
        print(f"Hollow Country debug map: http://{BIND_ADDRESS}:{args.port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
