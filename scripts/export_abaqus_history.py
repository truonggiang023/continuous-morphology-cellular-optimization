"""Run with Abaqus Python 3 (2024+): export synchronized RP history, no third-party dependencies."""
import argparse
import csv
import json
from pathlib import Path


def synchronized_history(step, u_region, rf_region):
    u = step.historyRegions[u_region].historyOutputs['U2'].data
    rf = step.historyRegions[rf_region].historyOutputs['RF2'].data
    if len(u) != len(rf) or any(abs(a[0] - b[0]) > 1e-10 for a, b in zip(u, rf)):
        raise ValueError('U2/RF2 history times differ: request synchronized history output at the platen RP')
    return [(a[0], a[1], b[1]) for a, b in zip(u, rf)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--odb', required=True)
    parser.add_argument('--step', required=True)
    parser.add_argument('--u-region', required=True, help='Exact history region key at loading platen RP')
    parser.add_argument('--rf-region', required=True, help='Exact history region key holding total platen reaction')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from odbAccess import openOdb
    output = Path(args.output)
    if output.exists() or output.with_suffix('.provenance.json').exists():
        raise FileExistsError('Export outputs already exist')
    odb = openOdb(path=args.odb, readOnly=True)
    try:
        rows = synchronized_history(odb.steps[args.step], args.u_region, args.rf_region)
        with output.open('x', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['time', 'U2_mm', 'RF2_N'])
            writer.writerows(rows)
        output.with_suffix('.provenance.json').write_text(json.dumps({
            'odb': str(Path(args.odb).resolve()), 'step': args.step,
            'u_region': args.u_region, 'rf_region': args.rf_region,
            'unit_contract': 'ODB model MUST use mm, N, s, tonne; units are not detected or converted',
            'qa': 'Export does not establish convergence, quasi-static validity or correct RP selection'}, indent=2))
    finally:
        odb.close()


if __name__ == '__main__':
    main()
