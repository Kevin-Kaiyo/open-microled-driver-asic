# 待启用的 Linux CI

`phase1.yml` 是 GitHub Actions template，尚未位于 `.github/workflows/`，因此没有自动运行。2026-10-03 创建仓库时，GitHub 拒绝首次推送：当前 OAuth credential 缺少 `workflow` scope。本机已有 Git SSH 身份也未通过 GitHub authentication。项目代码、文档和 Mac 验证证据仍可通过原 credential 发布。

Template 将在 Ubuntu 24.04 上安装 Icarus / ngspice，使用 locked Python dependencies，执行 bridge checks 和完整 Phase 1 regression，并上传成功或失败的原始输出。Linux tool versions 来自 apt，须以实际 CI summary 为准；本项目当前没有 Linux 通过证据。

拥有 workflow 写权限的凭证可执行以下启用步骤；`gh auth refresh` 可能需要在浏览器完成 GitHub 授权。

```sh
gh auth refresh -h github.com -s workflow
mkdir -p .github/workflows
git mv docs/ci/phase1.yml .github/workflows/phase1.yml
git add .github/workflows docs/ci
git commit -m 'Enable Phase 1 Linux CI'
git push
```

随后确认 Actions run 的真实结果，保存 log / summary，才可增加 Linux regression 的通过声明。这个权限限制没有改变本地 RTL / SPICE 的已验证结果。
