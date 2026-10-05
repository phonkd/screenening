#!/usr/bin/env python3
"""Small fzf front end for the installed Monique profile format."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def load_models():
    # Nix wraps Monique's interpreter; its pure Python models need no GTK.
    executable = shutil.which('monique')
    if not executable:
        raise RuntimeError('Install Monique first (already included in your nixconfig).')
    root = Path(executable).resolve().parent.parent
    for directory in root.glob('lib/python*/site-packages'):
        if (directory / 'monique/models.py').exists():
            sys.path.insert(0, str(directory))
            break
    from monique.models import MonitorConfig, Profile, WorkspaceRule
    return MonitorConfig, Profile, WorkspaceRule


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def choose(prompt, rows):
    result = subprocess.run(['fzf', '--height=40%', '--layout=reverse', '--no-multi',
                             '--prompt', prompt, '--header', 'Enter selects · Esc cancels'],
                            input='\n'.join(rows), text=True, stdout=subprocess.PIPE)
    if result.returncode in (1, 130):
        raise KeyboardInterrupt
    if result.returncode:
        raise RuntimeError('fzf failed')
    return rows.index(result.stdout.rstrip('\n'))


def make_profiles(monitors, left_name=None):
    _, Profile, WorkspaceRule = load_models()
    from monique.models import ResolutionMode
    monitors = copy.deepcopy(monitors)
    internal = [m for m in monitors if m.is_internal]
    if len(internal) != 1:
        raise RuntimeError('Expected exactly one active laptop panel.')
    laptop = internal[0]
    external = [m for m in monitors if not m.is_internal]
    if len(external) not in (0, 2):
        raise RuntimeError('Connect either just the laptop or the laptop plus two external screens.')
    descriptions = [m.description for m in monitors]
    if any(not d for d in descriptions) or len(set(descriptions)) != len(descriptions):
        raise RuntimeError('Monique needs unique display descriptions for reliable dock matching.')
    for m in monitors:
        if m.mirror_of:
            raise RuntimeError('Turn off mirroring in Monique before arranging these screens.')
        m.resolution_mode = ResolutionMode.HIGHRR
    solo = copy.deepcopy(laptop)
    solo.x = solo.y = 0

    def profile(name, outputs, owners):
        return Profile(name=name, monitors=outputs, workspace_rules=[
            WorkspaceRule(workspace=str(i + 1), monitor='desc:' + m.description,
                          default=(i == 0 or owners[i - 1] is not m))
            for i, m in enumerate(owners)], last_applied_time=time.time())

    solo_profile = profile('screenening-laptop', [solo], [solo] * 9)
    if not external:
        return [solo_profile]
    if left_name not in [m.name for m in external]:
        raise RuntimeError('Select a connected external output as the left screen.')
    left = next(m for m in external if m.name == left_name)
    right = next(m for m in external if m is not left)
    # Bottom-align the upper pair, leaving no gap above the laptop.
    height = round(max(left.logical_height, right.logical_height))
    left.x, left.y = 0, height - round(left.logical_height)
    right.x, right.y = round(left.logical_width), height - round(right.logical_height)
    laptop.x = round((left.logical_width + right.logical_width - laptop.logical_width) / 2)
    laptop.y = height
    fingerprint = '\n'.join(sorted(descriptions)).encode()
    name = 'screenening-dock-' + hashlib.sha256(fingerprint).hexdigest()[:10]
    dock = profile(name, [laptop, left, right], [laptop] * 3 + [left] * 3 + [right] * 3)
    return [solo_profile, dock]


def save_profile(directory, profile):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (profile.name + '.json')
    if target.exists():
        shutil.copy2(target, target.with_suffix('.json.bak'))
    with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as stream:
        json.dump(profile.to_dict(), stream, indent=2)
        stream.write('\n')
        temporary = stream.name
    os.replace(temporary, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--left', help='Initial left external connector (default: current leftmost)' )
    parser.add_argument('--dry-run', action='store_true', help='Print profiles without saving or applying')
    parser.add_argument('--yes', action='store_true', help='Apply without asking whether to swap')
    args = parser.parse_args()
    MonitorConfig, _, _ = load_models()
    raw = json.loads(run('hyprctl', 'monitors', '-j'))
    if any(m.get('mirrorOf', 'none') not in ('none', '', None) for m in raw):
        raise RuntimeError('Turn off mirroring in Monique before arranging these screens.')
    monitors = [MonitorConfig.from_hyprctl(m) for m in raw if not m.get('disabled')]
    external = sorted([m for m in monitors if not m.is_internal], key=lambda m: m.x)
    left = args.left
    if len(external) == 2 and left is None:
        left = external[0].name
    profiles = make_profiles(monitors, left)
    if args.dry_run:
        print(json.dumps([p.to_dict() for p in profiles], indent=2))
        return
    directory = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'monique/profiles'

    def save_and_apply(profiles):
        current = profiles[-1]
        for profile in profiles:
            save_profile(directory, profile)
        print(run('monique', '--switch-profile', current.name).strip())
        # Rules govern future workspaces; also move those which already exist.
        existing = {str(w['name']) for w in json.loads(run('hyprctl', 'workspaces', '-j'))}
        for rule in current.workspace_rules:
            if rule.workspace in existing:
                output = next(m.name for m in current.monitors if 'desc:' + m.description == rule.monitor)
                reply = run('hyprctl', 'dispatch', 'moveworkspacetomonitor', rule.workspace, output)
                if reply.strip() != 'ok':
                    raise RuntimeError(reply.strip())
        for m in current.monitors:
            keys = ''.join('qweasduio'[int(w.workspace)-1] for w in current.workspace_rules
                           if w.monitor == 'desc:' + m.description)
            print(f'{m.name}: {keys} at {m.x}x{m.y} — {m.description}')

    save_and_apply(profiles)
    if len(external) == 2 and not args.yes:
        print('Applied. Check the screens: asd should be on the left, uio on the right.')
        try:
            swap = choose('Swap left and right? > ', ['Keep this layout', 'Swap left and right'])
        except KeyboardInterrupt:
            swap = 0  # The layout is already applied; Esc keeps it.
        if swap == 1:
            left = next(m.name for m in external if m.name != left)
            profiles = make_profiles(monitors, left)
            save_and_apply(profiles)
    print(f'Saved {len(profiles)} Monique profile(s). moniqued handles future dock/undock events.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (RuntimeError, OSError, ValueError, ImportError, subprocess.CalledProcessError) as error:
        print(f'screenening: {error}', file=sys.stderr)
        sys.exit(1)
