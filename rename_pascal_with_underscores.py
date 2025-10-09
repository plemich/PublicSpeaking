#!/usr/bin/env python3
import os
import re
import argparse
import json
import subprocess

def pascal_with_underscores(title):
    # keep original word casing where possible; remove punctuation
    # replace certain separators with space
    s = title
    # replace common separators with spaces
    s = re.sub(r"[\-\/,&]", " ", s)
    # remove punctuation except unicode letters/numbers and spaces
    s = re.sub(r"[^\w\s\u00C0-\u017F]", " ", s)
    # collapse spaces
    parts = [p for p in re.split(r"\s+", s) if p]
    out_parts = []
    for p in parts:
        if p.isupper():
            out_parts.append(p)
        elif p.islower():
            out_parts.append(p.capitalize())
        else:
            out_parts.append(p[0].upper() + p[1:])
    return "_".join(out_parts)


def make_new_name(name):
    # keep trailing slash handling outside
    # detect leading date (8 digits)
    m = re.match(r"^(\d{8})\s*[-_\s]*(.+)$", name)
    if m:
        date = m.group(1)
        title = m.group(2)
        new_title = pascal_with_underscores(title)
        return f"{date}-{new_title}"
    else:
        # no date
        new_title = pascal_with_underscores(name)
        return new_title


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default='.', help="Path to PublicSpeaking folder")
    parser.add_argument("--apply", action='store_true', help="Actually perform git mv operations")
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    os.chdir(path)

    entries = sorted(os.listdir(path))
    mapping = {}
    errors = []

    for e in entries:
        # skip git internals and files
        if e in ('.git', '.gitignore', '.git 2', '.DS_Store'):
            continue
        full = os.path.join(path, e)
        if not os.path.isdir(full):
            # skip files, we only rename folders
            continue
        newname = make_new_name(e)
        if newname == e:
            continue
        # ensure no leading/trailing spaces
        newname = newname.strip()
        # avoid name collisions
        target = os.path.join(path, newname)
        if os.path.exists(target):
            errors.append(f"Target already exists, skipping: {newname}")
            continue
        mapping[e] = newname

    # write mapping for backup
    with open('rename_mapping_pascal.json', 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    if not mapping:
        print('No directories to rename.')
        if errors:
            print('\n'.join(errors))
        return

    print('Planned renames:')
    for k,v in mapping.items():
        print(f"  {k} -> {v}")

    if not args.apply:
        print('\nRun with --apply to execute git mv for each mapping.')
        return

    # perform git mv
    for src, dst in mapping.items():
        try:
            subprocess.run(['git', 'mv', src, dst], check=True)
            print(f"Renamed: {src} -> {dst}")
        except subprocess.CalledProcessError as e:
            errors.append(f"git mv failed for {src} -> {dst}: {e}")

    if errors:
        print('\nErrors:')
        for err in errors:
            print('  ' + err)
    else:
        print('\nAll renames applied successfully.')

if __name__ == '__main__':
    main()
