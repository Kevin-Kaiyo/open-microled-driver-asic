"""Independent functional architectures; no new high-speed circuit simulation."""
from pathlib import Path
import html
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/reference-safety-20261013/figures'
def make(name,title,nodes,foot):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="235" viewBox="0 0 900 235" role="img">',
         '<style>text{font-family:"PingFang SC","Avenir Next",sans-serif;fill:#263c43} .head{font-size:22px;font-weight:600}.body{font-size:18px}.note{font-size:17px}</style>',
         '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#386f7b"/></marker></defs>',
         '<rect width="900" height="235" fill="white"/>',f'<text x="18" y="31" class="head">{html.escape(title)}</text>']
    for i,lines in enumerate(nodes):
        x=18+i*175
        out.append(f'<rect x="{x}" y="69" width="153" height="83" rx="3" fill="#f3f7f6" stroke="#95b1b7"/>')
        for j,line in enumerate(lines):out.append(f'<text x="{x+76.5}" y="{96+j*25}" text-anchor="middle" class="body">{html.escape(line)}</text>')
        if i<4:out.append(f'<path d="M{x+153} 110H{x+169}" fill="none" stroke="#386f7b" stroke-width="2" marker-end="url(#arrow)"/>')
    for i,line in enumerate(foot):out.append(f'<text x="18" y="{185+i*26}" class="note">{html.escape(line)}</text>')
    out.append('</svg>');(OUT/name).write_text(''.join(out)+'\n')
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    make('highspeed-ook.svg','高速 OOK：比特决定两档电流／光输出',
         [('PRBS／数据','比特流'),('输入接收','时钟＋锁存'),('pre-driver','共模／摆幅'),('开关输出级','偏置＋选择'),('MicroLED','电流→光')],
         ['另需光接收器＋判决／BER测量；电气快边沿不等于链路验证。','独立功能方案，未实现高速ASIC；关断保护作为独立优先路径。'])
    make('highspeed-dac.svg','多级通信：每个数字样本对应一个电流幅度',
         [('PAM／OFDM','数字幅度样本'),('编码＋锁存','binary／分段'),('单元pre-driver','同步／时差'),('电流DAC','单位电流相加'),('MicroLED','偏置＋调制')],
         ['I[n] ≈ IBIAS + Σ bj[n] · Ij；需先定义有效电流范围和调制线性区。','独立功能方案；DAC采样率、光学带宽与链路比特率分别报告。'])
if __name__=='__main__':main()
