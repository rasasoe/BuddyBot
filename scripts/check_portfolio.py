"""Read-only README link/image checks. Run from the repository root."""
import argparse
import html
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
from PIL import Image


def check(root):
    root = Path(root).resolve()
    text = (root / 'README.md').read_text(encoding='utf-8-sig')
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    headings = re.findall(r'^#{1,6}\s+(.+)$', text, flags=re.M)
    anchors = set(re.findall(r'\bid=["\']([^"\']+)', text))
    for heading in headings:
        label = re.sub(r'<[^>]+>|[*`]', '', heading).lower()
        anchors.add(re.sub(r'[^\w\- ]', '', label).replace(' ', '-'))
    targets = re.findall(r'\]\(([^\s)]+)', text)
    targets += re.findall(r'(?:src|href|srcset)=["\']([^"\']+)', text)
    errors = []
    images = set()
    for raw in sorted(set(targets)):
        target = urlsplit(html.unescape(raw))
        if target.scheme or target.netloc:
            continue  # Remote URL availability is a separate check.
        if not target.path:
            if target.fragment and unquote(target.fragment) not in anchors:
                errors.append('Missing README anchor: ' + raw)
            continue
        path = (root / unquote(target.path)).resolve()
        if not path.is_relative_to(root) or not path.exists():
            errors.append('Missing/out-of-repository path: ' + raw)
            continue
        if path.suffix.lower() in {'.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp'}:
            images.add(path)
    for path in sorted(images):
        try:
            if path.suffix.lower() == '.svg':
                tree = ET.parse(path)
                assert tree.getroot().tag.endswith('svg'), 'Not an SVG document'
                assert not any(node.tag.rsplit('}', 1)[-1] in {'script', 'foreignObject'} for node in tree.iter()), 'Active SVG content'
            else:
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    for frame in range(getattr(image, 'n_frames', 1)):
                        image.seek(frame)
                        image.load()
        except Exception as error:
            errors.append(f'Invalid image {path.relative_to(root)}: {error}')
    return errors, len(images)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    errors, count = check(args.root)
    for error in errors:
        print('FAIL:', error)
    print(f'{len(errors)} error(s); {count} referenced image(s) decoded. Remote URLs, video playback and product behavior are not covered.')
    raise SystemExit(bool(errors))
