"""Design authority, review expiry and read-only producer observations.

An unchanged archive proves identity, not that active work is synchronized.
This tool never edits a producer, updates an archive or invents a decision.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REMOTE = 'https://github.com/sakuyaShining/FPGA-Music-project-internal.git'
BRANCH = 'main'
ENTRY_PATHS = ['.gitattributes', '.github/workflows/project-entry.yml', 'README.md',
               'AGENTS.md', 'project', 'docs/00-协作/AGENT-BOARD.md',
               'tools/scripts/project_control.py', 'tools/scripts/design_governance.py',
               'fpga/current', 'hardware/current', 'host/current',
               'tools/scripts/engineering.py', 'tools/requirements-engineering-host.txt']


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def reviewed_producers(root, review):
    """Keep large inventories once, in their immutable raw observation."""
    if 'producer_ids' in review:
        return read_json(root / relative(review['raw_observation']))['producers']
    return review.get('producers', {})


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe project path: ' + name)
    return Path(*p.parts)


def timestamp(value):
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Timezone required: ' + value)
    return t.astimezone(timezone.utc)


def age_status(value, hours, now):
    age = (now - timestamp(value)).total_seconds()
    if age < -300:
        return 'FUTURE_TIMESTAMP'
    return 'REVIEW_DUE' if age > hours * 3600 else 'WITHIN_REVIEW_WINDOW'


def run_git(root, *args, check=True):
    return subprocess.run(['git', '-C', str(root), *args], check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)


def published_entry(root=ROOT, remote=REMOTE):
    """Always compare actual remote main; dated branches are never authority."""
    result = dict(branch=BRANCH, remote=remote, status='UNKNOWN')
    try:
        rows = run_git(root, 'ls-remote', '--heads', remote, 'refs/heads/main').stdout.splitlines()
        if len(rows) != 1:
            result['reason'] = 'Published main unavailable'
            return result
        latest = rows[0].split()[0].decode('ascii')
        result['remote_commit'] = latest
        if run_git(root, 'cat-file', '-e', latest + '^{commit}', check=False).returncode:
            result.update(status='STALE_ENTRY', reason='Fetch actual remote main before implementation')
            return result
        current = run_git(root, 'ls-tree', '-r', 'HEAD', '--', *ENTRY_PATHS).stdout
        expected = run_git(root, 'ls-tree', '-r', latest, '--', *ENTRY_PATHS).stdout
        dirty = run_git(root, 'status', '--porcelain=v1', '--untracked-files=all', '--', *ENTRY_PATHS).stdout
        if dirty:
            result.update(status='UNPUBLISHED_ENTRY', reason='Working entry differs from committed entry')
        elif current != expected:
            ancestor = run_git(root, 'merge-base', '--is-ancestor', latest, 'HEAD', check=False).returncode == 0
            result.update(status='UNPUBLISHED_ENTRY' if ancestor else 'STALE_ENTRY',
                          reason='Entry content differs from actual remote main')
        else:
            result['status'] = 'CURRENT_PUBLISHED_MAIN'
    except (subprocess.SubprocessError, OSError) as e:
        result['reason'] = str(e)
    return result


def verify_decisions(root, ledger):
    errors = []
    items = ledger.get('decisions', [])
    ids = [x['id'] for x in items]
    if len(ids) != len(set(ids)):
        errors.append('Duplicate decision ID')
    lookup = {x['id']: x for x in items}
    for item in items:
        if item.get('status') not in {'accepted', 'superseded', 'proposed'}:
            errors.append('Invalid decision status: ' + item['id'])
        evidence = item.get('evidence', {})
        path = root / relative(evidence.get('path', ''))
        if not path.is_file() or digest(path.read_bytes()) != evidence.get('sha256'):
            errors.append('Decision evidence mismatch: ' + item['id'])
        if item.get('status') == 'accepted' and not evidence.get('authority'):
            errors.append('Accepted decision missing authority: ' + item['id'])
        parent = item.get('supersedes')
        if parent and (parent not in lookup or lookup[parent]['status'] != 'superseded'):
            errors.append('Superseded decision missing or still active: ' + item['id'])
        seen = {item['id']}
        while parent:
            if parent in seen:
                errors.append('Decision supersession cycle: ' + item['id'])
                break
            seen.add(parent)
            parent = lookup.get(parent, {}).get('supersedes')
    return errors


def validate(root=ROOT):
    policy = read_json(root / 'project/governance.json')
    errors = []
    if policy.get('authority') != dict(remote=REMOTE, branch=BRANCH):
        errors.append('Design authority must be the verified target repository main')
    for name in ('project/handoff.json', 'project/design-state.json'):
        if read_json(root / name).get('entry_branch') != BRANCH:
            errors.append('Non-main entry branch in ' + name)
    for name, expected in policy['controlled_files'].items():
        p = root / relative(name)
        if not p.is_file() or digest(p.read_bytes()) != expected:
            errors.append('Governance controlled file changed: ' + name)
    ledger = read_json(root / relative(policy['decision_ledger']))
    errors.extend(verify_decisions(root, ledger))
    review_path = root / relative(policy['review_record'])
    if digest(review_path.read_bytes()) != policy['review_sha256']:
        errors.append('Review record changed without reviewed identity')
    review = read_json(review_path)
    if review['reviewed_at'] != policy['reviewed_at']:
        errors.append('Review date cannot be renewed without a new matching record')
    if review.get('raw_observation'):
        raw_path = root / relative(review['raw_observation'])
        if digest(raw_path.read_bytes()) != review.get('raw_observation_sha256'):
            errors.append('Raw observation identity mismatch')
        raw = read_json(raw_path)
        if 'producer_ids' in review:
            ids = review['producer_ids']
            if len(ids) != len(set(ids)) or set(ids) != set(raw.get('producers', {})):
                errors.append('Reviewed producer IDs differ from the actual observation record')
        elif raw.get('producers') != review.get('producers'):
            errors.append('Reviewed producer state differs from the actual observation record')
    observations = reviewed_producers(root, review)
    producers = read_json(root / relative(policy['producer_registry']))['producers']
    if len({p['id'] for p in producers}) != len(producers):
        errors.append('Duplicate producer ID')
    for p in producers:
        if p['activity'] == 'active' and p['id'] not in observations:
            errors.append('Active producer not observed in review: ' + p['id'])
        elif p['activity'] == 'active':
            observed = observations[p['id']]
            if observed.get('status') != 'OBSERVED' or not observed.get('files'):
                errors.append('Active producer lacks a readable observation: ' + p['id'])
    facts = {}
    for decision in ledger['decisions']:
        if decision['status'] != 'accepted':
            continue
        for key, value in decision.get('facts', {}).items():
            if key in facts:
                errors.append('Multiple active decisions for fact: ' + key)
            facts[key] = value
    scope = read_json(root / 'project/design-state.json')['scope']
    for key in policy['required_scope_facts']:
        if key not in facts or scope.get(key) != facts[key]:
            errors.append('Current design scope contradicts accepted decision: ' + key)
    return errors


def reparse(path):
    s = path.lstat()
    return path.is_symlink() or bool(getattr(s, 'st_file_attributes', 0) & 0x400)


def inventory(producer):
    """Hash only declared inputs. Never follow junctions or generated trees."""
    root = Path(producer['root'])
    if not root.is_dir():
        return dict(status='UNOBSERVED', reason='Producer root unavailable', files={})
    selected = {}
    omissions = []
    for spec in producer['watch']:
        base = root / relative(spec['path']) if spec['path'] != '.' else root
        if not base.exists():
            # Missing declared trees must not disappear from the observation.
            omissions.append(spec['path'])
            continue
        if reparse(base):
            omissions.append(spec['path'] + ':reparse')
            continue
        if base.is_file():
            selected[base.relative_to(root).as_posix()] = base
            continue
        for parent, dirs, files in os.walk(str(base), followlinks=False):
            dirs[:] = [d for d in dirs if d not in producer['exclude_dirs']
                       and not d.startswith(tuple(producer['exclude_prefixes']))
                       and not reparse(Path(parent) / d)]
            for name in files:
                p = Path(parent) / name
                if p.suffix.lower() not in spec['suffixes'] or reparse(p):
                    continue
                if p.stat().st_size > spec['max_bytes']:
                    omissions.append(p.relative_to(root).as_posix() + ':oversize')
                    continue
                selected[p.relative_to(root).as_posix()] = p
            if not spec.get('recursive', False):
                break
    records = {}
    try:
        for name, path in sorted(selected.items()):
            raw = path.read_bytes()
            records[name] = dict(bytes=len(raw), sha256=digest(raw))
        changed = [name for name, path in selected.items()
                   if not path.exists() or digest(path.read_bytes()) != records[name]['sha256']]
        if changed:
            return dict(status='UNSTABLE', files=records, changing_files=changed, omissions=omissions)
    except OSError as e:
        return dict(status='UNOBSERVED', files=records, reason=str(e), omissions=omissions)
    if not records:
        return dict(status='UNOBSERVED', files={}, reason='No declared readable inputs', omissions=omissions)
    return dict(status='OBSERVED', files=records, omissions=omissions)


def compare_files(expected, observed):
    return dict(added=sorted(set(observed) - set(expected)), removed=sorted(set(expected) - set(observed)),
                modified=sorted(p for p in set(expected) & set(observed)
                                if expected[p]['sha256'] != observed[p]['sha256']))


def assess_live(producer, reviewed):
    observed = inventory(producer)
    if observed['status'] != 'OBSERVED':
        return observed
    changes = compare_files(reviewed['files'], observed['files'])
    changed = any(changes.values()) or observed['omissions'] != reviewed.get('omissions', [])
    return dict(status='UNREVIEWED_DRIFT' if changed else 'MATCHES_REVIEWED_OBSERVATION',
                changes=changes, omissions=observed['omissions'], files=observed['files'])


def status(root=ROOT, live=False, remote=False, now=None):
    now = now or datetime.now(timezone.utc)
    errors = validate(root)
    policy = read_json(root / 'project/governance.json')
    review = read_json(root / relative(policy['review_record']))
    ledger = read_json(root / relative(policy['decision_ledger']))
    for decision in ledger['decisions']:
        if decision.get('blocking') and decision['status'] == 'proposed':
            errors.append('Unresolved design conflict: ' + decision['id'])
    producers = read_json(root / relative(policy['producer_registry']))['producers']
    observations = reviewed_producers(root, review)
    age = age_status(review['reviewed_at'], policy['review_max_hours'], now)
    if age != 'WITHIN_REVIEW_WINDOW':
        errors.append('Design review: ' + age)
    result = dict(status='REVIEWED_WITH_DECLARED_WIP', checked_at=now.isoformat(),
                  authority=policy['authority'], review_record=policy['review_record'], review_age_status=age,
                  scope='Recorded review and declared producer scope; no automatic functional or manufacturing acceptance',
                  live_checked=live, producers={}, errors=errors, product_acceptance=False,
                  implementation_start_authorized=False)
    advertised = None
    if remote:
        result['published_entry'] = published_entry(root)
        if result['published_entry']['status'] != 'CURRENT_PUBLISHED_MAIN':
            errors.append('Published entry: ' + result['published_entry']['status'])
        try:
            advertised = {row.split()[1].decode(): row.split()[0].decode()
                          for row in run_git(root, 'ls-remote', '--heads', REMOTE).stdout.splitlines()}
        except (subprocess.SubprocessError, OSError) as e:
            errors.append('Remote producer refs unavailable: ' + str(e))
    for producer in producers:
        ident = producer['id']
        reviewed = observations.get(ident)
        if producer['activity'] != 'active':
            result['producers'][ident] = dict(status='DORMANT_SOURCE', activation_requires_review=True)
            continue
        if reviewed is None:
            errors.append('Unobserved active producer: ' + ident)
            continue
        expiry = age_status(reviewed['observed_at'], producer['observation_max_hours'], now)
        p = dict(observation_age_status=expiry, observed_at=reviewed['observed_at'],
                 publication_status=producer['publication_status'], owner=producer['owner'],
                 live_status='NOT_CHECKED_ON_THIS_MACHINE', source_archive=producer.get('recovery_manifest'))
        if expiry != 'WITHIN_REVIEW_WINDOW':
            errors.append(ident + ': ' + expiry)
        if live:
            observation = assess_live(producer, reviewed)
            p['live_status'] = observation['status']
            p['changes'] = observation.get('changes', {})
            if observation['status'] != 'MATCHES_REVIEWED_OBSERVATION':
                errors.append(ident + ': ' + observation['status'])
        published = producer.get('published_ref')
        if published and advertised is not None:
            if advertised.get('refs/heads/' + published['branch']) != published['commit']:
                errors.append(ident + ': PRODUCER_REF_ADVANCED_OR_MISSING')
        result['producers'][ident] = p
    if errors:
        result['status'] = 'REVIEW_REQUIRED'
    return result


def observe(output, root=ROOT):
    """Write an unreviewed observation, never renew the governing review."""
    output = Path(output)
    if output.exists():
        raise ValueError('Refuse to overwrite observation: ' + str(output))
    policy = read_json(root / 'project/governance.json')
    producers = read_json(root / relative(policy['producer_registry']))['producers']
    stamp = datetime.now(timezone.utc).isoformat()
    result = dict(schema=1, observed_at=stamp, classification='UNREVIEWED_OBSERVATION',
                  renews_review=False, product_acceptance=False, producers={})
    for p in producers:
        if p['activity'] == 'active':
            result['producers'][p['id']] = dict(observed_at=stamp, **inventory(p))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    s = sub.add_parser('status')
    s.add_argument('--live', action='store_true', help='Read-only comparison of available producer roots')
    s.add_argument('--remote', action='store_true', help='Verify actual published main and registered producer refs')
    o = sub.add_parser('observe', help='Create an unreviewed observation; never refreshes a review')
    o.add_argument('--output', type=Path, required=True)
    sub.add_parser('validate', help='Validate evidence, main authority and review identities without claiming freshness')
    a = ap.parse_args()
    if a.command == 'observe':
        r = observe(a.output)
        print(json.dumps(dict(output=str(a.output), classification=r['classification'], renews_review=False)))
        return 0
    if a.command == 'validate':
        errors = validate()
        print(json.dumps(dict(status='FAIL' if errors else 'PASS', errors=errors), ensure_ascii=False, indent=2))
        return 1 if errors else 0
    result = status(live=a.live, remote=a.remote)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
