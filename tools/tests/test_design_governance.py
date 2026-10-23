"""Failure-oriented checks for design authority and long-lived handoffs."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import design_governance as g


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def producer(root):
    return dict(id='fpga', activity='active', root=str(root), owner='fixture',
                observation_max_hours=6, publication_status='UNMERGED_WIP',
                exclude_dirs=['build'], exclude_prefixes=['build_'],
                watch=[dict(path='.', recursive=True, suffixes=['.v', '.md'], max_bytes=1024)])


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 10, 23, 5, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self):
        r = self.root
        live = r / 'live'
        live.mkdir()
        (live / 'core.v').write_text('module core; endmodule\n')
        p = producer(live)
        observation = g.inventory(p)
        stamp = self.now.isoformat()
        review = dict(reviewed_at=stamp, producers={'fpga':dict(observed_at=stamp, **observation)})
        write(r / 'project/review.json', review)
        write(r / 'project/producers.json', dict(producers=[p]))
        evidence = r / 'project/evidence.json'
        write(evidence, dict(human='Keep 32 groups'))
        decision = dict(id='D-32', status='accepted', facts={'groups':32},
                        evidence=dict(path='project/evidence.json', sha256=g.digest(evidence.read_bytes()), authority='human excerpt'))
        write(r / 'project/decisions.json', dict(decisions=[decision]))
        write(r / 'project/design-state.json', dict(entry_branch='main', scope={'groups':32}))
        write(r / 'project/handoff.json', dict(entry_branch='main'))
        policy = dict(authority=dict(remote=g.REMOTE, branch='main'), controlled_files={},
                      decision_ledger='project/decisions.json', producer_registry='project/producers.json',
                      review_record='project/review.json', review_sha256=g.digest((r/'project/review.json').read_bytes()),
                      reviewed_at=stamp, review_max_hours=24, required_scope_facts=['groups'])
        write(r / 'project/governance.json', policy)
        return p, observation, policy

    def test_new_modified_and_deleted_source_requires_review(self):
        p, before, _ = self.fixture()
        live = Path(p['root'])
        (live/'new.v').write_text('new')
        (live/'core.v').write_text('changed')
        report = g.assess_live(p, before)
        self.assertEqual(report['status'], 'UNREVIEWED_DRIFT')
        self.assertEqual(report['changes']['added'], ['new.v'])
        self.assertEqual(report['changes']['modified'], ['core.v'])
        (live/'core.v').unlink()
        self.assertEqual(g.assess_live(p, before)['changes']['removed'], ['core.v'])

    def test_missing_source_is_unobserved_not_green(self):
        p, before, _ = self.fixture()
        p['root'] = str(self.root/'not-present')
        self.assertEqual(g.assess_live(p, before)['status'], 'UNOBSERVED')

    def test_generated_tree_excluded_but_new_design_document_detected(self):
        p, before, _ = self.fixture()
        live = Path(p['root'])
        (live/'build').mkdir()
        (live/'build/noise.v').write_text('generated')
        self.assertEqual(g.assess_live(p, before)['status'], 'MATCHES_REVIEWED_OBSERVATION')
        (live/'new-design.md').write_text('proposal')
        self.assertEqual(g.assess_live(p, before)['changes']['added'], ['new-design.md'])

    def test_observation_does_not_renew_review_and_refuses_overwrite(self):
        self.fixture()
        policy = self.root/'project/governance.json'
        before = policy.read_bytes()
        output = self.root/'new/observation.json'
        result = g.observe(output, self.root)
        self.assertFalse(result['renews_review'])
        self.assertEqual(policy.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            g.observe(output, self.root)

    def test_expired_active_observation_requires_review(self):
        self.fixture()
        r = g.status(self.root, now=self.now+timedelta(hours=7))
        self.assertEqual(r['review_age_status'], 'WITHIN_REVIEW_WINDOW')
        self.assertIn('fpga: REVIEW_DUE', r['errors'])
        self.assertEqual(r['status'], 'REVIEW_REQUIRED')

    def test_expired_design_review_and_future_clock_rejected(self):
        self.fixture()
        r = g.status(self.root, now=self.now+timedelta(hours=25))
        self.assertIn('Design review: REVIEW_DUE', r['errors'])
        self.assertEqual(g.age_status((self.now+timedelta(hours=1)).isoformat(),24,self.now), 'FUTURE_TIMESTAMP')
        with self.assertRaisesRegex(ValueError, 'Timezone'):
            g.timestamp('2026-10-23T05:00:00')

    def test_changing_date_alone_cannot_renew_review(self):
        _, _, policy = self.fixture()
        policy['reviewed_at'] = (self.now+timedelta(hours=1)).isoformat()
        write(self.root/'project/governance.json',policy)
        self.assertIn('Review date cannot be renewed without a new matching record',g.validate(self.root))

    def test_evidence_mutation_and_scope_conflict_rejected(self):
        self.fixture()
        write(self.root/'project/evidence.json',dict(human='Keep 16 groups'))
        errors=g.validate(self.root)
        self.assertTrue(any('evidence mismatch' in x for x in errors))
        write(self.root/'project/design-state.json',dict(entry_branch='main',scope={'groups':16}))
        self.assertTrue(any('contradicts accepted decision' in x for x in g.validate(self.root)))

    def test_dated_branch_cannot_be_authority(self):
        _,_,policy=self.fixture()
        policy['authority']['branch']='codex/dated-old-entry'
        write(self.root/'project/governance.json',policy)
        self.assertTrue(any('authority must' in x for x in g.validate(self.root)))

    def test_new_producer_cannot_skip_observation(self):
        self.fixture()
        registry=g.read_json(self.root/'project/producers.json')
        registry['producers'].append(dict(id='new-owner',activity='active'))
        write(self.root/'project/producers.json',registry)
        self.assertIn('Active producer not observed in review: new-owner',g.validate(self.root))

    def test_review_cannot_silently_replace_observed_source(self):
        _,_,policy=self.fixture()
        raw=g.read_json(self.root/'project/review.json')
        write(self.root/'project/observation.json',dict(producers=raw['producers']))
        raw['raw_observation']='project/observation.json'
        raw['raw_observation_sha256']=g.digest((self.root/'project/observation.json').read_bytes())
        raw['producers']['fpga']['files']['core.v']['sha256']='0'*64
        write(self.root/'project/review.json',raw)
        policy['review_sha256']=g.digest((self.root/'project/review.json').read_bytes())
        write(self.root/'project/governance.json',policy)
        self.assertIn('Reviewed producer state differs from the actual observation record',g.validate(self.root))

    def test_compact_review_keeps_inventory_only_in_raw_record(self):
        self.fixture()
        p=self.root/'project/review.json';review=g.read_json(p)
        raw=dict(producers=review.pop('producers'))
        write(self.root/'project/observation.json',raw)
        review.update(raw_observation='project/observation.json',
                      raw_observation_sha256=g.digest((self.root/'project/observation.json').read_bytes()),
                      producer_ids=['fpga'])
        write(p,review)
        policy=g.read_json(self.root/'project/governance.json');policy['review_sha256']=g.digest(p.read_bytes())
        write(self.root/'project/governance.json',policy)
        self.assertFalse(g.validate(self.root))
        self.assertEqual(g.status(self.root,now=self.now)['status'],'REVIEWED_WITH_DECLARED_WIP')
        review['producer_ids'].append('invented-producer');write(p,review)
        policy['review_sha256']=g.digest(p.read_bytes());write(self.root/'project/governance.json',policy)
        self.assertTrue(any('IDs differ' in x for x in g.validate(self.root)))

    def test_supersession_cycles_rejected(self):
        self.fixture()
        item=g.read_json(self.root/'project/decisions.json')['decisions'][0]
        a=dict(item,id='A',status='superseded',supersedes='B')
        b=dict(item,id='B',status='superseded',supersedes='A')
        errors=g.verify_decisions(self.root,dict(decisions=[a,b]))
        self.assertTrue(any('cycle' in x for x in errors))

    def test_unresolved_human_decision_conflict_is_not_ready(self):
        self.fixture()
        ledger=g.read_json(self.root/'project/decisions.json')
        pending=dict(ledger['decisions'][0],id='P-CONFLICT',status='proposed',blocking=True,facts={})
        ledger['decisions'].append(pending)
        write(self.root/'project/decisions.json',ledger)
        result=g.status(self.root,now=self.now)
        self.assertIn('Unresolved design conflict: P-CONFLICT',result['errors'])

    def test_recorded_review_never_claims_live_observation_or_acceptance(self):
        self.fixture()
        r=g.status(self.root,now=self.now)
        self.assertEqual(r['status'],'REVIEWED_WITH_DECLARED_WIP')
        self.assertFalse(r['live_checked'])
        self.assertFalse(r['implementation_start_authorized'])
        self.assertFalse(r['product_acceptance'])

    def test_registered_remote_producer_advancing_requires_review(self):
        self.fixture()
        p=g.read_json(self.root/'project/producers.json')
        p['producers'][0]['published_ref']=dict(branch='codex/producer',commit='1'*40)
        write(self.root/'project/producers.json',p)
        answer=subprocess.CompletedProcess([],0,stdout=(('2'*40)+'\trefs/heads/codex/producer\n').encode())
        with mock.patch.object(g,'published_entry',return_value=dict(status='CURRENT_PUBLISHED_MAIN')):
            with mock.patch.object(g,'run_git',return_value=answer):
                r=g.status(self.root,remote=True,now=self.now)
        self.assertIn('fpga: PRODUCER_REF_ADVANCED_OR_MISSING',r['errors'])


class PublishedMainTests(unittest.TestCase):
    def test_main_advances_while_legacy_branch_stays_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);remote=base/'remote.git';author=base/'author';consumer=base/'consumer'
            def cmd(*args,cwd=None):
                return subprocess.check_output(list(args),cwd=cwd,stderr=subprocess.DEVNULL).decode().strip()
            cmd('git','init','--bare',str(remote))
            cmd('git','init','-b','main',str(author))
            cmd('git','config','user.name','Fixture',cwd=author)
            cmd('git','config','user.email','fixture@local.invalid',cwd=author)
            (author/'README.md').write_text('old')
            cmd('git','add','README.md',cwd=author);cmd('git','commit','-m','old',cwd=author)
            old=cmd('git','rev-parse','HEAD',cwd=author)
            cmd('git','remote','add','origin',str(remote),cwd=author)
            cmd('git','push','origin','main','HEAD:refs/heads/codex/legacy',cwd=author)
            cmd('git','clone','--branch','main',str(remote),str(consumer))
            self.assertEqual(g.published_entry(consumer,str(remote))['status'],'CURRENT_PUBLISHED_MAIN')
            (author/'README.md').write_text('new')
            cmd('git','add','README.md',cwd=author);cmd('git','commit','-m','new',cwd=author)
            cmd('git','push','origin','main',cwd=author)
            cmd('git','fetch','origin',cwd=consumer)
            self.assertEqual(g.published_entry(consumer,str(remote))['status'],'STALE_ENTRY')
            self.assertTrue(cmd('git','ls-remote',str(remote),'refs/heads/codex/legacy').startswith(old))
            # Same entry after a squash merge is valid despite different ancestry.
            cmd('git','config','user.name','Fixture',cwd=consumer)
            cmd('git','config','user.email','fixture@local.invalid',cwd=consumer)
            tree=cmd('git','rev-parse','origin/main^{tree}',cwd=consumer)
            sibling=cmd('git','commit-tree',tree,'-p',old,'-m','squash',cwd=consumer)
            cmd('git','checkout','--detach',sibling,cwd=consumer)
            self.assertEqual(g.published_entry(consumer,str(remote))['status'],'CURRENT_PUBLISHED_MAIN')
            (consumer/'README.md').write_text('uncommitted')
            self.assertEqual(g.published_entry(consumer,str(remote))['status'],'UNPUBLISHED_ENTRY')


if __name__=='__main__':
    unittest.main()
