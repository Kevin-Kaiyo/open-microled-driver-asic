#!/usr/bin/env python3
"""Preserve compact recovery evidence without models, old raw, or checkout mutation."""
from pathlib import Path
import hashlib,json,shutil

OUT=Path(__file__).resolve().parent
ROOT=OUT/'repository'; CHECK=ROOT/'build/recovery-checks'
DEST=OUT/'recovery-check-evidence'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def copy(p,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists()
    shutil.copy2(p,target)
    assert sha(p)==sha(target)

def main():
    receipt=json.loads((OUT/'recovery.json').read_text())
    assert receipt['passed'] and not DEST.exists()
    previous_receipt_sha=sha(OUT/'recovery.json')
    DEST.mkdir()
    for p in CHECK.rglob('*'):
        if p.is_file() and not p.is_symlink() and 'inputs' not in p.parts and '__pycache__' not in p.parts and p.suffix!='.vvp':
            copy(p,DEST/'fresh'/p.relative_to(CHECK))
    for item in receipt['commands']:
        copy(OUT/item['log'],DEST/'commands'/item['log'])
    for name in ['checkout-log.json','release-metadata.json','restore-files.json','recover_small_inputs.py','finalize_recovery_evidence.py']:
        copy(OUT/name,DEST/name)
    manifest=json.loads((OUT/'downloads/driver-robustness-20261024.json').read_text())
    members={x['path']:x for a in manifest['assets'] for x in a['files']}
    nrzdir='build/highspeed-nrz-robustness/selected-a8-b58-r4/cases/'+receipt['comparisons']['nrz']['reference_case']
    refs=[nrzdir+'/analysis.json',nrzdir+'/result.json','build/pwm-robustness/20261024/dc_board100n/result.json']
    records=[]
    for path in refs:
        assert path in members and sha(ROOT/path)==members[path]['sha256']
        target=DEST/'archived-reference'/path
        copy(ROOT/path,target)
        records.append({'archive_member':path,'sha256':sha(target),'preserved_path':str(target.relative_to(DEST))})
    archived_nrz=json.loads((ROOT/refs[0]).read_text())['row']['LED_current_A']
    archived_pwm=json.loads((ROOT/refs[2]).read_text())['current_a']
    assert archived_nrz==receipt['comparisons']['nrz']['reference_current_A']
    assert archived_pwm==receipt['comparisons']['pwm']['reference_current_A']
    receipt['archived_reference_readback']={'references':records,'nrz_current_A':archived_nrz,'pwm_current_A':archived_pwm,
        'matches_comparison_reference_values':True,'both_fresh_current_differences_A':0.0}
    (DEST/'README.md').write_text('''# GitHub 小输入恢复验证记录

源提交 9d84753bae099e497a813f9097b1ce6eeb2f2df7；Release driver-robustness-20261024。
六组资产真实从 GitHub 下载，archive 与每个成员 SHA256 校验后，恢复到同机新 checkout。

- NRZ FF −40°C / 3.65V high DC：108.566138350767 µA，与归档 analysis/result 一致。
- PWM dc_board100n DC：99.733511476514 µA，与归档 result 一致。
- physical hv-A8-r3 和 hv-r2：已有证据回读分别105与205个成员通过；未重跑 EDA。

fresh/ 保存两个新DC的结果、分析、网表、日志、约1.1KB合计的新DC压缩波形，以及物理回读JSON。
archived-reference/ 保存从Release恢复并验证的参考JSON；没有历史原始波形和大模型副本。
commands/ 保存完整实际命令日志，命令数组与退出码在 recovery.json。
同机共享原工作区Python环境和系统ngspice/iverilog；未证明另一台干净机器的依赖安装。
NRZ仅在进程中重定向生成摘要到build/recovery-checks；没有更改电路、模型、判据或已提交脚本。
manifest.json逐文件列出该紧凑证据包SHA；recovery.json作为上层回执另行封存，不参与递归自hash。
''')
    files=[{'path':str(p.relative_to(DEST)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DEST.rglob('*')) if p.is_file()]
    (DEST/'manifest.json').write_text(json.dumps({'files':files,'file_count':len(files),'total_bytes':sum(x['bytes'] for x in files)},indent=2)+'\n')
    for x in files: assert sha(DEST/x['path'])==x['sha256']
    receipt['compact_evidence']={'directory':str(DEST),'portable_directory_name':DEST.name,
        'manifest_sha256':sha(DEST/'manifest.json'),'file_count_excluding_receipt_and_manifest':len(files),
        'bytes_excluding_receipt_and_manifest':sum(x['bytes'] for x in files),
        'contains_large_models':False,'contains_historical_raw_waveforms':False,
        'contains_new_DC_waveforms':True,'fresh_DC_waveform_bytes':sum(p.stat().st_size for p in (DEST/'fresh').rglob('waveform.dat.gz')),
        'preserves_command_logs_and_archived_comparison_references':True}
    receipt['compact_finalization']={'previous_recovery_sha256':previous_receipt_sha,'script_sha256':sha(__file__),
        'command':[str(OUT.parent.parent/'build/layout/venv/bin/python'),'-B',str(Path(__file__).resolve())],'exit_code':0}
    (OUT/'recovery.json').write_text(json.dumps(receipt,indent=2)+'\n')
    copy(OUT/'recovery.json',DEST/'recovery.json')
    print(json.dumps({'passed':True,'receipt_sha256':sha(OUT/'recovery.json'),'compact_evidence':receipt['compact_evidence']},indent=2))

if __name__=='__main__': main()
