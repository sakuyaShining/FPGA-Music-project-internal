from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import shutil

from verify_renderer import PROJECT, ROOT, CAPTURED, digest, run


def main():
    parser = argparse.ArgumentParser(description='Exhaustive captured-ROM velocity scaling arithmetic regression')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() or output == PROJECT or PROJECT in output.parents:
        raise ValueError('Use a new output outside repository')
    compiler = Path(os.environ.get('FPGA_IVERILOG') or shutil.which('iverilog') or 'D:/iverilog/bin/iverilog.exe').resolve()
    simulator = Path(os.environ.get('FPGA_VVP') or shutil.which('vvp') or 'D:/iverilog/bin/vvp.exe').resolve()
    if not compiler.is_file() or not simulator.is_file():
        raise ValueError('Icarus and vvp required')
    sources = [CAPTURED / 'vel_shape.v', ROOT / 'rtl/vel_shape_scaled.v', ROOT / 'tb/tb_velocity_scaling.v',
               CAPTURED / 'vel_wtab.hex', ROOT / 'verify_velocity.py', ROOT / 'verify_renderer.py', ROOT / 'reference.py']
    inputs = {path.relative_to(PROJECT).as_posix(): digest(path) for path in sources}
    output.mkdir(parents=True)
    (output / 'INPUTS.json').write_text(json.dumps(inputs, indent=2) + '\n', encoding='utf-8')
    for source in sources[:4]:
        shutil.copyfile(source, output / source.name)
    binary = output / 'velocity.vvp'
    compilation = run([str(compiler), '-g2012', '-s', 'tb_velocity_scaling', '-o', str(binary)] +
                      [str(output / source.name) for source in sources[:3]], output / 'compile.log', output)
    simulation = None
    if compilation['returncode'] == 0:
        simulation = run([str(simulator), str(binary)], output / 'run.log', output)
    marker = 'PASS velocity_scaling checked=2097152 default_compatible=524288 corrected=218790'
    changed = [name for name, expected in inputs.items() if digest(PROJECT / name) != expected]
    passed = simulation is not None and simulation['returncode'] == 0 and marker in simulation['text'] and not changed
    result = dict(schema=1, tested_at=datetime.now(timezone.utc).isoformat(), inputs=inputs,
                  tools={str(path): digest(path) for path in (compiler, simulator)}, compilation=compilation,
                  simulation=simulation, source_changes=changed, status='PASS' if passed else 'FAIL',
                  scope='All1024 captured ROM addresses x256 base amplitudes x8 explicit scales; default0/256 compatibility and signed arithmetic oracle, not full PCM or musical calibration',
                  product_acceptance=False, hardware_accessed=False)
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], output=str(output))))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
