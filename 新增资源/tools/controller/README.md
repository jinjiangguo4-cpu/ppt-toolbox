# PPT 知识库批量生产

在独立的 Windows 本机终端运行。需要 Python 3.11+、Git、已配置的 GitHub 写权限和提交身份。运行既有图表生成器时另外需要 Node.js 和 pptxgenjs。只使用专门为批量任务创建的干净仓库检出，避免两个程序同时操作同一检出。关闭 Codex 不影响从独立终端启动的程序，关闭终端、关机或休眠会中断运行。

```powershell
git clone https://github.com/jinjiangguo4-cpu/ppt-toolbox.git C:\PPT\toolbox
py -3 C:\PPT\toolbox\新增资源\tools\controller\run_knowledge_base_batch.py --repo C:\PPT\toolbox --baseline C:\PPT\private\index.sqlite --plan C:\PPT\private\plan.json --state C:\PPT\private\run.json --target 1000 --batch-size 50
```

可重复指定 `--category`，值使用增量索引里的分类名称。执行之前请复制并填写示例计划。每个包可配置 `directory` 指向已有候选目录，或配置 `command` 调用受信任的现有生成器。例如 `["py","-3","palettes.py","snapshot","{out}"]`。程序在计划文件所在目录运行命令。生成器必须把资源和 `资源描述.json` 写入 `{out}`。仅使用自己信任的计划，命令会在本机执行。

每个描述行使用现有批次格式，包括 id、名称、category、motif_key、file_path、extra_paths 和 license。原创 CC0 包须声明 original_cc0。Apache-2.0 包须附原许可证、必要声明、来源及作者。documents 列出的许可文件会随素材保存。经视觉或设计审核后，用批准表登记 id 和签名。签名为主文件及 extra_paths 顺序的 SHA-256 十六进制文本，以 LF 拼接后再次计算 SHA-256，不带末尾换行。未签名、未支持或命中内容疑似的条目在本地状态中列出，源候选包保留。计划、批准表、旧库和运行状态保存在仓库外。

自动入库覆盖 SVG、配色 SVG/JSON 和符合现有单页规则的原生 PPTX。PNG、字体、研究记录和其他许可证目前需要另行审核，不能由本入口直接发布。结构检查不能代替视觉审阅，PowerPoint 客户端实测状态明确记录。运行目标是合格数上限；候选不足时记录 shortfall。随附计划是模板，不包含一千份获批候选。

中断后用完全相同的命令恢复。程序记录尚未完成的提交，推送失败会有限重试。若远端已由其他人推进，保留本地提交并停止，先处理分支冲突。不要手工删除 run.json。目标、旧库或计划变动时先结束旧运行，再为新运行选用新的状态文件。GitHub 认证使用 Git Credential Manager 或已配置的 gh 凭据助手。

## 多来源与供给测试

计划可以使用有序的 `sources`，每个条目提供唯一 `id`，并沿用上述 command 或 directory 配置。控制器按需拉取下一来源，缓存取得的候选，并在状态中记录来源处理结果。失败来源会记下原因并切换。以独立状态文件运行 `--supply-only --target 200`，可检查真实候选数量、结构、许可证与索引查重，全程不提交资源。供给测试允许完整扫描最后一包，候选数可能高于目标。正式运行仍要求预审签名。

`open_svg_pack.py` 支持从本地固定版本的 Tabler 官方 npm 包读取指定主题，例如 `["py","-3","open_svg_pack.py","tabler.tgz","Health","{out}"]`。对应来源配置 `"documents":["Tabler-LICENSE.txt"]`。供给测试通过表示可处理，不代表通过视觉审核或跨库视觉查重。
