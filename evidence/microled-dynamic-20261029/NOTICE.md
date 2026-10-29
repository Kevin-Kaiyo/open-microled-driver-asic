# MicroLED dynamics source attribution and reuse boundaries

Numerical I–V/P–I/S21/bandwidth data are from Runze Lin, Yu Zhang, Yucheng Yang, Shengyuan Dong, Handan Xu, Daqi Shen, Cheng Gao, Zehui Liang, Junze Tong, Erdan Gu, Zhizhong Chen, Bo Shen and Pengfei Tian (2026), **Source data for “Transfer-printed yellow and red InGaN micro-LEDs on diamond for ultra-low-power high-speed optical interconnects”**, Zenodo record 20034288, [DOI:10.5281/zenodo.20034288](https://doi.org/10.5281/zenodo.20034288).

The numerical dataset is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), verified against [official metadata](https://zenodo.org/api/records/20034288). Attribution and that license remain applicable to imported data and their representations. This project's MIT license does not relicense the source data. The source authors do not endorse this project, extraction or interpretation.

Changes: selected five bias curves from `yellow20_s21_bandwidths.xlsx`, retained source current-density and cutoff data, converted frequency from MHz to Hz, independently recomputed first −3/−6 dB crossings, cross-checked the 100 µA curve against `frequency_response_low_current.xlsx`, selected yellow20 P–I from `diamond-optical-power.xlsx`, and rendered new plots and faithful cell-value tables. The tables are not Excel screenshots. Original model files and prior experiment results are unchanged.

The explanatory `reference-planes.svg/png` and `reference-plane-response.svg/png` are this project's original small-signal circuit calculations using the static I–V local slope, an assumed 200 fF and an illustrative 50 Ω. They are not measured dynamic parameters, a calibrated VNA fixture or a measured driver output impedance.

The associated Nature Communications article is separately licensed **CC BY-NC-ND 4.0**. No article figures or full text are included in this public directory. The original Fig. 4 is retained in the ignored local `build/microled-dynamic-20261029/` for private source inspection. Li et al.'s arXiv v1 has an arXiv non-exclusive distribution license; its original PDF/page is also private and not included in the public evidence package. Zhu et al. is cited at the explicitly stated abstract-only evidence level; no figure or full text is reproduced.

`source-ledger.json` records source locators, evidence depth, numerical precision, limitations and license status. A hash establishes file identity, not scientific validity. Do not upload the private originals as public Release assets by default.
