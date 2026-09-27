from pathlib import Path
import hashlib
import json
import platform

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(paths):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths)) if p.is_file()}


def source_manifest(dataset_paths, protocol_path):
    files = list((ROOT / 'backend/app').rglob('*.py')) + list((ROOT / 'eval').glob('*.py'))
    files += [ROOT / 'backend/pyproject.toml', protocol_path] + list(dataset_paths)
    hashes = fingerprint(files)
    return {'files': hashes, 'manifest_sha256': hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            'python': platform.python_version(), 'platform': platform.platform(), 'synthetic_only': True}
