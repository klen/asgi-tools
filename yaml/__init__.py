from __future__ import annotations

import base64

__all__ = ["load", "SafeLoader"]

class SafeLoader:  # pragma: no cover - compatibility stub
    pass

def load(stream, Loader=None):
    if hasattr(stream, "read"):
        text = stream.read()
        if isinstance(text, bytes):
            text = text.decode()
    else:
        text = stream.decode() if isinstance(stream, bytes) else str(stream)

    lines = text.splitlines()
    result = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("boundary:"):
            result["boundary"] = line.split(":", 1)[1].strip()
            i += 1
            continue
        if line.startswith("expected:"):
            i += 1
            items = []
            result["expected"] = items
            while i < len(lines) and lines[i].startswith("  -"):
                item = {}
                line = lines[i][4:]
                if ":" in line:
                    k, v = line.split(":", 1)
                    item[k.strip()] = v.strip()
                i += 1
                while i < len(lines) and lines[i].startswith("    "):
                    sub = lines[i].strip()
                    if sub.endswith(": !!binary |"):
                        key = sub.split(":", 1)[0]
                        i += 1
                        data_lines = []
                        while i < len(lines) and lines[i].startswith("      "):
                            data_lines.append(lines[i].strip())
                            i += 1
                        item[key] = base64.b64decode("".join(data_lines))
                    else:
                        if ":" in sub:
                            k2, v2 = sub.split(":", 1)
                            item[k2.strip()] = v2.strip()
                            i += 1
                        else:
                            i += 1
                items.append(item)
            continue
        i += 1
    return result
