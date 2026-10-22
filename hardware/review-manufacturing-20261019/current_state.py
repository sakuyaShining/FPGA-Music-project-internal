"""One authoritative pointer for current manufacturing/acceptance preparation.

Historical planners keep their explicit source hashes. Current ledgers use this
pointer so a new PCB checkpoint cannot leave them silently reporting old data.
"""
import hashlib,json
from pathlib import Path

def current_checkpoint(root):
    root=Path(root)
    pointer=root/'CURRENT-STATE.json'
    state=json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else {}
    manifest_path=root/state.get('checkpoint','route-checkpoint-0clear-78open-quality-r1-20261021.json')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    capture_path=root/state.get('source_capture',manifest.get('source_capture','quality-r1-source-78.json'))
    if state:assert state['pcb_sha256']==manifest['pcb_sha256'],'Current pointer/checkpoint mismatch'
    if manifest.get('source_capture_sha256'):
        assert hashlib.sha256(capture_path.read_bytes()).hexdigest()==manifest['source_capture_sha256'],'Current capture hash mismatch'
    return manifest_path,manifest,capture_path
