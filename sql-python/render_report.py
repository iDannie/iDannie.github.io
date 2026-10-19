"""Rebuild a reviewed report only when its supporting results match the reference run."""
import csv
import json
import math
from pathlib import Path
import sys


def read_result(path):
    if path.suffix == '.json':
        return json.loads(path.read_text())
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def compare(expected, actual, location):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or expected.keys() != actual.keys():
            raise ValueError(f'{location}: fields differ')
        for key in expected:
            compare(expected[key], actual[key], f'{location}.{key}')
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise ValueError(f'{location}: row count differs')
        for index, (left, right) in enumerate(zip(expected, actual)):
            compare(left, right, f'{location}[{index}]')
    elif isinstance(expected, bool) or expected is None:
        if expected != actual:
            raise ValueError(f'{location}: expected {expected}, received {actual}')
    else:
        try:
            left, right = float(expected), float(actual)
        except (TypeError, ValueError):
            if expected != actual:
                raise ValueError(f'{location}: text differs')
            return
        # Counts and labels must agree; tiny floating-point differences are acceptable.
        exact_integer = (isinstance(expected, int) or
                         (isinstance(expected, str) and expected.lstrip('-').isdigit()))
        equal = left == right if exact_integer else math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-7)
        if not equal:
            raise ValueError(f'{location}: expected {expected}, received {actual}')


def render(project):
    project = Path(project).resolve()
    reference = json.loads((project / 'report_reference.json').read_text())
    for name, expected in reference.items():
        compare(expected, read_result(project / 'outputs' / name), name)
    template = project / 'report_template.html'
    page = template.read_text()
    import re
    for filename in re.findall(r'<img[^>]+src="([^"]+)"', page):
        if not (project / 'outputs' / filename).is_file():
            raise FileNotFoundError(f'Missing report figure: {filename}')
    (project / 'outputs' / 'report.html').write_text(page)
    print(f'{project.name}: reference results match; findings report rebuilt.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python render_report.py PATH_TO_PROJECT')
    render(sys.argv[1])
