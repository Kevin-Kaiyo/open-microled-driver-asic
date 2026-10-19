"""Build product-development framework document and explicit unready deliverables."""
from pathlib import Path
import hashlib,json,re
import markdown
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/research/product-framework-20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    gates=[
      ('G0','需求与模型','接口、电压、温区、LED范围、测量定义','冻结需求及模型有效域','partial','单像素研究合同已有；完整产品／高速合同待定'),
      ('G1','DC与compliance','新参考/TG/像素、真实R/C及LED','工作点、电流误差、端压与余量','partial','新TG仅三包络联测；不能继承旧servo180点为全域通过'),
      ('G2','数值可靠性','积分定义、容差、步长与求解法','相对／绝对误差预算、窗口及失败解释','failed','startup Q+4.909%超过既有0.2%；保留overall=false'),
      ('G3','环路与噪声','新参考负载、补偿、供电、输入误差','loop/phase、settling、PSRR、noise','pending','新环路完整矩阵未执行'),
      ('G4','异常与供电顺序','POR/brownout、rails、fault、时钟、开短路','默认off、端压、Q+/Q-、恢复与重复fault','partial','仅有效logic/LED下reference启动；非完整POR'),
      ('G5','失配与均匀性','合法MC模型、梯度、PG、LED数据','样本数/seed/分布、全域校准残差','partial','旧像素失配证据不能代表新参考或阵列'),
      ('G6','数字实现','PWM、保护存储、receiver、CDC、时钟','RTL与门级/等价/STA/SDF，异常测试','partial','旧PWM已有物理实现；新安全存储与接收器缺口'),
      ('G7','模拟布局及共同top','新宏、真实被动、body/well/PG、pins','DRC/LVS/ERC/完整PEX及GDS回读','pending','新参考/TG/保护未进入旧GDS'),
      ('G8','版图后电气闭环','RC角、PG/body、pad/ESD、package','DC/transient/loop/fault/IR/EM对照','pending','旧selected PEX不能替代全新top'),
      ('G9','可制造／可靠性','被接受PDK/stack/deck/IP与报告','density/fill/antenna/端压/ESD/waivers','pending','公开旧DRC选项未全覆盖制造要求'),
      ('G10','封装及测试','pad map/bond/PCB/limits/仪器','可观测性、供电时序、测试程序与校准','pending','无已选定封装/ATE/光测实现'),
      ('G11','制造冻结','最终top/GDS/hash、接受版本、签核','同版本数据包与接收方审核','pending','没有最终提交文件或制造接受'),
      ('G12','实物／产品验证','真实LED/封装ASIC/板卡/仪器','电气和光学关联、温度、失效分析','pending','未流片、未测量光学'),
      ('H1','高速单通道','器件E/O模型、目标速率、I/O与receiver','晶体管/PEX/封装、eye/jitter/BER/pJbit','concept','本轮两极点教学计算不替代高速电路或测量'),
    ]
    rows=[dict(id=i,question=q,required_inputs=inp,required_outputs=out,current_status=st,current_boundary=b) for i,q,inp,out,st,b in gates]
    plan=dict(schema_version=1,date='2026-10-14',scope='产品开发框架；状态来自当前证据，未执行新的EDA验收',
        existing_research_limits=dict(full_on_nominal_uA=100,full_on_tolerance_percent=5,min_pwm_charge_error_percent=2,fault_abs_current_guard_nA=1,fault_max_delay_us=1,legacy_relative_convergence_percent=.2),
        limits_status='Existing research contracts only. Product operating ranges, highspeed rate/BER and reliability limits must be frozen separately.',
        latest_experiment_overall_passed=False,gates=rows)
    (BASE/'verification-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    packet=dict(schema_version=1,document_type='unpopulated_tapeout_package_template',ready_for_submission=False,
       warning='没有最终芯片、制造接受或签核。null为待确认；旧GDS只是研究证据，不能填为最终设计。',
       project='open-microled-driver-asic',intended_first_vehicle='one-pixel mixed-signal test ASIC with external MicroLED',
       release=dict(commit=None,approved_by=None,release_date=None),
       technology=dict(research_platform='GF180MCU D',foundry_or_mpw_provider=None,accepted_pdk_revision=None,accepted_rule_deck_revision=None,accepted_metal_stack=None,accepted_io_esd_library=None),
       layout=dict(final_file=None,sha256=None,top_cell=None,format=None,dbu_um=None,die_bbox_um=None,layer_map=None,seal_ring=None,fill_complete=False),
       engineering_views={k:None for k in ['schematic_netlist','extracted_netlist','lef','def','liberty','sdc','spef','sdf','package_model']},
       verification=dict(drc=None,lvs=None,erc=None,antenna=None,density=None,sta=None,pex_electrical=None,ir_em=None,esd_latchup=None,voltage_reliability=None,waivers=[]),
       package_and_test=dict(package_drawing=None,pad_coordinate_map=None,pinout=None,bond_map=None,probe_plan=None,wafer_test_limits=None,packaged_test_limits=None,optical_test_plan=None,pcb_revision=None,power_sequence=None),
       submission=dict(provider_checklist=None,accepted_formats=None,slot=None,packaging_included=None,tests_included=None,acceptance_record=None),
       usage='确认接收方规范后填写；网表/工程视图上传范围由合同决定；不要把网页或3D图代替GDS。')
    (BASE/'tapeout-package-template.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
    txt=(BASE/'report.md').read_text(); pages=txt.split('<!-- PAGE -->')
    css="""@page{size:A4;margin:18mm 19mm 19mm}*{box-sizing:border-box}body{margin:0;color:#263d45;font:10.6pt/1.58 'Avenir Next','PingFang SC',sans-serif}h1,h2,h3{color:#185a67;line-height:1.25}h1{font-size:24pt;margin:0 0 5mm}h2{font-size:16.6pt;border-bottom:1px solid #bdced0;margin:0 0 4mm;padding-bottom:3mm}h3{font-size:12pt;margin:3mm 0}p{margin:0 0 3mm}a{color:#176c79;text-decoration:none;overflow-wrap:anywhere}strong{color:#174c59}table{width:100%;border-collapse:collapse;font-size:9.3pt;line-height:1.45;margin:3mm 0}th{background:#edf3f3;text-align:left}th,td{padding:1.8mm 2mm;vertical-align:top;border-bottom:1px solid #dce5e5;overflow-wrap:anywhere}tr{break-inside:avoid}ul,ol{padding-left:5.8mm;margin:2mm 0 3mm}li{margin:1mm 0}img{display:block;width:100%;max-height:103mm;object-fit:contain;margin:2mm 0 3mm}.caption{font-size:8.7pt;color:#596f76;line-height:1.45}.eq{padding:2.5mm 3mm;background:#f1f6f5;border-left:2px solid #3b7d88;font-size:10pt;line-height:1.55;margin:3mm 0}code{font-family:inherit;font-size:.94em;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7f7;padding:3mm;font-size:8.5pt;line-height:1.45}.page{break-after:page}.page:last-child{break-after:auto}#page-7 img{max-height:150mm}#page-15 img{max-height:130mm}#page-16 img{max-height:95mm}#page-21 img{max-height:105mm}nav{background:#15515f;color:white;padding:18px;max-width:1050px;margin:auto}nav a{color:white;display:inline-block;margin:5px 10px;font-size:14px}.page-no{display:none}@media print{body,.page{width:172mm}nav{display:none}}@media screen{body{background:#ecf1f1}.page{width:210mm;min-height:297mm;padding:18mm 19mm 19mm;margin:8mm auto;background:white;box-shadow:0 1px 8px #bac9ca}.page-no{display:block;color:#64818b;font-size:12px;margin-bottom:10px}}@media screen and (max-width:820px){.page{width:100%;min-height:0;padding:24px;margin:12px auto}body{font-size:16px}table{font-size:13px}h1{font-size:28px}h2{font-size:24px}img{max-height:none}}"""
    titles=[];sections=[]
    for i,p in enumerate(pages,1):
        title=re.search(r'^#{1,2}\s+(.*)',p,re.M).group(1);titles.append(title)
        sections.append(f'<section class="page" id="page-{i}"><div class="page-no">{i} / {len(pages)}</div>'+markdown.markdown(p.strip(),extensions=['tables','fenced_code'])+'</section>')
    nav='<nav><b>MicroLED驱动ASIC · 产品开发框架</b><br>'+''.join(f'<a href="#page-{n}">{t}</a>' for n,t in enumerate(titles,1) if n in [1,2,4,7,9,12,15,17,19,23,25,27,28])+'<a href="layout/viewer.html">打开二维／三维版图</a></nav>'
    (BASE/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroLED驱动ASIC：产品开发框架</title><style>'+css+'</style><body>'+nav+''.join(sections)+'</body></html>\n')
    local_sources=['rtl/pixel_pwm.v','analog/driver/pixel_driver.spice','analog/reference/vset_servo_with_junctions.spice','analog/startup_v2/reference_isolator_tg.spice','analog/safety/fault_gate.spice','analog/safety/fault_led_clamp.spice','rtl/safety/pixel_safety.v','evidence/startup-v2/summary.json','evidence/startup-v2/peer-audit.json','evidence/integration/summary.json','evidence/joint-pex/summary.json','docs/research/interface.md','docs/research/measured-led.md','docs/research/startup-tapeout-20261014/area-baseline.json','docs/research/startup-tapeout-20261014/fabrication-sources.json']
    for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)',txt):
        p=(BASE/m[1]).resolve();local_sources.append(str(p.relative_to(ROOT)))
    for p in ['current-evidence.json','current-architecture-audit.md','highspeed-chapter.md','highspeed-sources.json','highspeed-calculations.json','layout-chapter.md','layout/manifest.json','layout/browser-validation.json','calculations.json']:
        local_sources.append(str((BASE/p).relative_to(ROOT)))
    missing=[p for p in local_sources if not (ROOT/p).exists()]
    if missing:raise FileNotFoundError(str(missing))
    ledger=dict(date='2026-10-14',purpose='source-backed synthesis and actual GDS visualization; no new transistor or signoff run',pages=len(pages),sources={p:sha(ROOT/p) for p in sorted(set(local_sources))},
       new_artifacts={'GDS_views':'actual old XY; arbitrary Z layer projection','highspeed_model':'synthetic linear normalized model; no GF180 or measured optical result','framework':'verification gates and unready submission template'},
       experiment_passed=False,manufacturing_acceptance=False,report_source_sha256=sha(BASE/'report.md'))
    (BASE/'evidence-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'pages':len(pages),'source_hashes':len(ledger['sources']),'html':str((BASE/'report.html').relative_to(ROOT))}))
if __name__=='__main__':main()
