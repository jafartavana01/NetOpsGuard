"""Publish a version commit AND immutable tag atomically; no force push.

Run on a clean, verified main checkout. No increment happens in tests/imports.
A concurrent branch update, existing tag, or permission rejection publishes neither.
"""
import argparse
from pathlib import Path
import re
import subprocess


def bump(version, part='revision'):
    if not re.fullmatch(r'(0|[1-9]\d*)(\.(0|[1-9]\d*)){3}', version):
        raise ValueError('Expected MAJOR.MINOR.PATCH.REVISION')
    values = list(map(int, version.split('.')))
    index = ('major', 'minor', 'patch', 'revision').index(part)
    values[index] += 1
    values[index + 1:] = [0] * (3 - index)
    return '.'.join(map(str, values))


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def publish(part='revision', remote='origin', automatic=False, prepare=False, publish_prepared=False):
    if git('status', '--porcelain'):
        raise RuntimeError('Release requires a clean checkout.')
    head = git('rev-parse', 'HEAD')
    remote_head = git('ls-remote', remote, 'refs/heads/main').split()[0]
    if head != remote_head:
        raise RuntimeError('Main changed. Fetch and reverify before publishing.')
    if publish_prepared:
        version = Path('app/VERSION').read_text().strip()
        bump(version)  # validate canonical four-part format
        tag = 'v' + version
        if git('ls-remote', remote, 'refs/tags/' + tag):
            raise RuntimeError('This version is already published; tags are immutable.')
        previous = [t[1:] for t in git('tag', '--merged', head).splitlines()
                    if re.fullmatch(r'v(0|[1-9]\d*)(\.(0|[1-9]\d*)){3}', t)]
        if previous:
            latest = max(previous, key=lambda v: tuple(map(int, v.split('.'))))
            if version not in [bump(latest, part) for part in ('revision','patch','minor','major')]:
                raise RuntimeError('Prepared version must be one release increment after the latest tag.')
        git('push', remote, 'HEAD:refs/tags/' + tag)
        return version
    if automatic:
        # A queued workflow can check out an already published head. Do not
        # increment again unless application inputs changed after that release.
        current = Path('app/VERSION').read_text().strip()
        tags = git('tag', '--merged', head).splitlines()
        if 'v' + current in tags:
            changed = git('diff', '--name-only', 'v' + current, head).splitlines()
            application = [p for p in changed if p != 'app/VERSION' and
                           (p.startswith(('app/', 'installer/')) or p in
                            ('setup.py', 'bootstrap.sh', 'requirements.txt', 'scripts/release.py'))]
            if not application:
                return current
    path = Path('app/VERSION')
    version = bump(path.read_text().strip(), part)
    tag = 'v' + version
    if git('ls-remote', remote, 'refs/tags/' + tag):
        raise RuntimeError('Release tag already exists; no version was published.')
    path.write_text(version + '\n')
    git('add', 'app/VERSION')
    git('commit', '-m', 'Release ' + tag + ('' if prepare else ' [skip ci]'))
    if prepare:
        return version
    # A refspec creates the lightweight tag remotely in the same transaction.
    # Non-fast-forward checks reject concurrent writers; tag creation rejects duplicates.
    git('push', '--atomic', remote, 'HEAD:refs/heads/main', 'HEAD:refs/tags/' + tag)
    return version


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--part', choices=['revision','patch','minor','major'], default='revision')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--automatic', action='store_true')
    modes.add_argument('--prepare', action='store_true', help='Create a version commit for a release PR; publish nothing')
    modes.add_argument('--publish-prepared', action='store_true', help='Tag an already merged version PR without writing main')
    args = parser.parse_args()
    print(('Prepared (not published) ' if args.prepare else 'Published ') + publish(args.part, automatic=args.automatic, prepare=args.prepare, publish_prepared=args.publish_prepared))
