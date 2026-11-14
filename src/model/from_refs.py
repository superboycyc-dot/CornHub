"""Read unmerged A/B handoffs without editing teammates' directories.

Resolve refs to immutable commits, extract only contract inputs to a temporary
folder, run the normal model entry point, then remove the read-only snapshot.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

from .pipeline import run


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True).stdout


def snapshot(core_ref, satellite_ref, target):
    specs = [(core_ref, ['core/labels.csv', 'core/validation_folds.csv', 'core/fields.geojson']),
             (satellite_ref, ['satellite/features.csv'])]
    provenance = {'mode': 'git_snapshot', 'sources': []}
    for ref, files in specs:
        commit = git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()
        source = dict(requested_ref=ref, commit=commit, present_files=[], missing_files=[])
        for relative in files:
            repository_path = 'data/processed/' + relative
            # Distinguish genuinely absent input from a Git failure.
            listed = git('ls-tree', '--name-only', commit, '--', repository_path).decode().strip()
            if not listed:
                source['missing_files'].append(repository_path)
                continue
            content = git('show', commit + ':' + repository_path)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            source['present_files'].append(repository_path)
        provenance['sources'].append(source)
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-ref', required=True)
    parser.add_argument('--satellite-ref', required=True)
    parser.add_argument('--output', type=Path, default=Path('data/processed/model'))
    parser.add_argument('--report', type=Path, default=Path('reports/c_model'))
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--inference', action='store_true')
    args = parser.parse_args()
    if args.inference and not args.train:
        parser.error('--inference requires --train')
    with tempfile.TemporaryDirectory(prefix='cornhub-real-handoff-') as directory:
        root = Path(directory)
        provenance = snapshot(args.core_ref, args.satellite_ref, root)
        code = run(root, args.output, args.report, args.train, args.inference, provenance)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
