"""Prepare the reviewed registry from completed preservation records (no push)."""
from pathlib import Path
from datetime import datetime, timezone
import json,subprocess,hashlib,argparse

ROOT=Path(__file__).resolve().parents[2]
RUN=Path('D:/FPGA-Project/codex-builds/project-management-20261022')

def write(path,value):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--local-only',action='store_true');args=ap.parse_args()
    records=json.loads((RUN/'snapshots.json').read_text(encoding='utf-8'))
    ids={r['id'] for r in records}
    expected={'main','4d37','06df','4a4b','4c43','4e09','66a4','6e70','8c56','a61b','b5b8','b6d6','ca03','cec2','eb59','instrument-engine-safety','workbuddy','m1-work','m1-reference','native-source57','native-trial50','native-r15'}
    if ids!=expected:raise ValueError('Incomplete inventory: missing='+str(expected-ids)+' extra='+str(ids-expected))
    live='' if args.local_only else subprocess.check_output(['git','-C',str(ROOT),'ls-remote','--heads','internal']).decode()
    remote={line.split()[1].replace('refs/heads/','',1):line.split()[0] for line in live.splitlines()}
    for r in records:
        if not args.local_only and remote.get(r['branch'])!=r['commit']:raise ValueError('Not uploaded: '+r['branch'])
        r['remote_verified_commit']=remote.get(r['branch'])
    captured=datetime.now(timezone.utc).isoformat()
    write('project/versions/workspace-preservation-20261022.json',dict(schema=1,captured_at=captured,
        classification='WIP/source preservation, not product acceptance or atomic multi-workspace release',
        remote='internal',remote_url='https://github.com/sakuyaShining/FPGA-Music-project-internal.git',snapshots=records))
    profiles={
      'music_integrated_07':dict(role='music-baseline',snapshot='66a4',source_branch='codex/project-version-closure',entry='project/CURRENT.md',validation='Existing 07 records report regression/PnR/board tests; not rerun here',complete_product=False),
      'music_engine_safety':dict(role='development-candidate',snapshot='instrument-engine-safety',source_branch='codex/instrument-engine-safety',entry='project/CURRENT.md',validation='Existing records report targeted tests/new PnR; not downloaded',complete_product=False),
      'nano20k_structural_probe':dict(role='probe',snapshot='4d37',entry='experiments/nano20k_feasibility_20261021/project/CURRENT.md',validation=dict(basis='Previously sealed source/evidence; not rerun here',route=True,bitstream_generated=True,sta=False,setup_ns=-6.397,hold_ns=-0.048),product_accepted=False,programming_allowed=False),
      'm1_area_work':dict(role='probe',snapshot='m1-work',entry='M1-CHANGE-NOTE.md',validation='Mutable area experiments; no acceptance inferred; inspect captured RTL including disabled visualizer',owner='unconfirmed independent M1 session',product_accepted=False,programming_allowed=False),
      'm1_reference':dict(role='reference',snapshot='m1-reference',entry='HANDOFF-WORKSPACE.json',validation='Independent baseline source; results do not sign off modified M1'),
      'gui_ca03':dict(role='development-source',snapshot='ca03',source_branch='backup/ca03-20261022',validation='Preserved GUI plus RTL edits; no integration acceptance'),
      'gui_6e70':dict(role='development-source',snapshot='6e70',source_branch='codex/v1-behavior-freeze',validation='Historical GUI/protocol source with subsequent uncommitted changes'),
      'hardware_wip':dict(role='hardware-construction',snapshot='06df',entry='hardware/review-manufacturing-20261019/REGIONAL-WORK-IN-PROGRESS.json',validation='Preserved pointer/evidence; no new native DRC or manufacturing validation',manufacturing_release=False,native_source_snapshot='native-source57',native_pending_snapshot='native-trial50',native_active_r15_snapshot='native-r15'),
      'complete_product_top':dict(role='product',snapshot=None,status='not_implemented_and_validated',product_accepted=False,programming_allowed=False)}
    write('project/state.json',dict(schema=2,updated_at=captured,entry='project/CURRENT.md',
        predecessor_state='codex/project-version-closure:project/state.json',
        implementation_boundary='This registry does not merge or change any functional source',
        wip_policy=dict(max_active_tasks_per_owner=1,snapshot_branches='Immutable recovery archives; not new active tasks',
                        start_gate='Named owner, branch, source identity, scope and completion criterion must be registered',
                        completion_gate='Commit, scoped verification, remote commit check and handoff; otherwise retain explicit WIP'),profiles=profiles))
    write('project/catalog.json',dict(schema=2,classification='Navigation and source roles; file existence does not prove wiring',
        predecessor_catalog='codex/project-version-closure:project/catalog.json',
        input_manifests='project/versions/workspace-preservation-20261022.json',
        areas=[dict(id='music',sources=['66a4','instrument-engine-safety'],role='music baseline and forward fixes'),
               dict(id='structural-integration',sources=['main','4d37','m1-work'],role='experiments/probes; not complete product top'),
               dict(id='host',sources=['6e70','ca03'],role='GUI/protocol sources needing explicit integration review'),
               dict(id='hardware',sources=['06df','native-source57','native-trial50','native-r15'],role='construction source, reference and pending native projects'),
               dict(id='historical-sources',sources=sorted(ids-{'main','4d37','66a4','instrument-engine-safety','m1-work','m1-reference','6e70','ca03','06df','native-source57','native-trial50','native-r15'}),role='Preserved history, not redundant/deletable by inference')]))
    write('project/dependencies.json',dict(schema=2,
        predecessor='codex/project-version-closure:project/dependencies.json',
        management=dict(python='3.8+',git=True,original_workspaces_required=False),
        fpga=dict(device='GW2AR-LV18QN88C8/I7 / Tang Nano20K',gowin='V1.9.11.03 Education, per frozen build records',iverilog='See portable handoff environment configuration',
                  tool_installation='Not bundled; no programming or hardware operations are part of management checks'),
        host=dict(requirements='Use the selected frozen host candidate requirements; not silently unified here'),
        archive=dict(path='project/archives/fpga-agent-handoff-20261022-v1.zip',sha256='115f7d8f3789af99fed182ad331352e861c2795bba371567d9008df9d5458a78'),
        publication='Independent reviewed export; never push internal source to origin/public'))
    board=ROOT/'docs/00-协作/AGENT-BOARD.md';s=board.read_text(encoding='utf-8')
    marker='## 9. 2026-10-22 管理收口检查点'
    if marker not in s:
        s+='\n\n---\n\n'+marker+'\n\n'
        s+='用户已授权执行保全版本、同步GitHub、统一入口三步。本轮管理分支为`codex/project-management-20261022`（4d37）；没有移动其他活跃工程、没有改写其他工作树索引或分支。\n\n'
        s+='- 共享入口：根README → `project/CURRENT.md` → `project/state.json`。旧正文中的工作区、会话和硬件计数是历史信息，当前取所选源码快照中的入口核对。\n'
        s+='- GitHub：已核实internal为private；main及既有有效分支已同步。各工作区保全分支与精确提交见`project/versions/workspace-preservation-20261022.json`。保全不是产品验收。\n'
        s+='- A轴：4d37候选已冻结；D盘M1有独立活跃工作区，owner身份尚待登记，临时关闭可视化的面积实验不得作为产品裁剪决定。\n'
        s+='- B轴：保持06df及其硬件入口所有权；原生来源、pending试作、R15候选分别保全，不改板、不重放会话、不制造放行。\n'
        s+='- 管理owner：本会话4d37，仅修改入口、登记、恢复工具和管理文档；未认领其他会话功能实现。main接合仍由用户完成。\n'
        s+='- 下一步：合并本管理PR后，各owner从登记的来源继续提交并同步新检查点；目录迁移及功能接合另行审查。\n'
        board.write_text(s,encoding='utf-8')
    print('Prepared registry for '+str(len(records))+(' local snapshots; remote unverified' if args.local_only else ' remotely verified snapshots'))

if __name__=='__main__':main()
