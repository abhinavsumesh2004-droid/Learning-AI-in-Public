import json
from pathlib import Path


class Registry:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            self.path.write_text('{"sessions": {}}')

    def load(self):
        return json.loads(self.path.read_text())

    def save(self, data):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)

    def upsert(self, session_id, **fields):
        data = self.load()
        entry = data["sessions"].setdefault(session_id, {})
        entry.update(fields)
        self.save(data)

    def sessions(self):
        return self.load()["sessions"]
