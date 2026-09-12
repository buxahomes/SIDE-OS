# SIDE 一程｜项目知识库

独立项目：SIDE-OS。整理日期：2026-09-12。仓库：[buxahomes/SIDE-OS](https://github.com/buxahomes/SIDE-OS)。用户已明确选择保持 **Public** 并上传已整理资料；本提交为知识库部分资料导入，不写入 BUXA-OS。

这里保存城市同行服务的规则、流程、通用照片规范和研究工具，保留核心原件与出处。人物档案及身份参考资料暂缓公开，状态见迁移记录。

## 从这里开始

| 要做的事 | 入口 |
| --- | --- |
| 了解品牌与服务内容 | [项目定位](docs/01-brand.md) |
| 查看Logo与VI规范 | [Side Land 一程 · V1.1原标锁定版](docs/10-logo-vi.md) |
| 给客户报价 | [现行测试阶段 V1](docs/02-pricing.md) · [价格数据](config/pricing.json) |
| 执行订单 | [运营流程](docs/03-operations.md) · [话术和表单](templates/operations.md) |
| 查看人物资料 | [Side档案](docs/04-people.md) |
| 生成和修改照片 | [照片系统](docs/05-photos.md) · [去AI感规范公开版](docs/photo-naturalism-public.md) |
| 找素材和历史文件 | [本次公开资料索引](assets/README.md) |
| 读取小红书、抖音 | [读取说明](docs/06-social-reading.md) |
| 每日观察地陪热帖 | [地陪内容观察日报：配置与部署草案](docs/11-content-radar.md) |
| 查看仍未确定的规则 | [待定事项](docs/07-open-decisions.md) |
| 核对哪些内容已迁入 | [迁移范围](docs/08-migration.md) · [来源清单](sources/manifest.json) |
| 上传独立GitHub仓库 | [部署说明](docs/09-github.md) |

## 已有读取工具

Python 3.10+，只用标准库，无需安装依赖。在仓库根目录执行：

```bash
python3 scripts/side_kb.py search '小酌'
python3 scripts/side_kb.py fetch '粘贴小红书或抖音分享链接'
python3 scripts/side_kb.py ingest --platform xiaohongshu --url '原始链接' --file /本地/笔记正文.txt --title '笔记标题'
python3 scripts/side_kb.py ingest --platform douyin --url '原始链接' --file /本地/视频字幕.srt --kind transcript
python3 scripts/side_kb.py ingest --platform xiaohongshu --file /本地/截图.png --kind image --title '待识别的参考截图'
python3 -m unittest discover -s tests -v
```

`fetch` 尝试读取公开网页中的正文或元数据，不能保证平台允许访问。截图、音视频导入会登记文件和校验值，**不等于已完成OCR、语音转写或视频理解**；正文、人工识别结果和字幕可单独入库。官方抖音账号API尚未接通。

新增的 `scripts/side_radar.py` 提供红狐数据采集、规则初筛、模型分析和HTML日报；运行不带参数时只做离线预检。每天北京时间00:30的服务器定时模板见 `deploy/`。**红狐密钥已通过 GitHub Actions 真实查询测试；模型配置已注入，分析联调尚未通过，每日定时运行未启用**。研究输出默认保存在被git忽略的 `research/local/radar/`，不自动公开发布或推送。详见[部署说明](docs/11-content-radar.md)。

## 使用顺序

当前用户明确指令 → 本次整理的现行规则 → 原始文件 → 历史草稿 → 外部研究。日期新的文件也可能包含过时规则，不能仅凭文件名决定生效版本。研究材料不自动成为SIDE承诺。

本次已上传范围见[迁移记录](docs/08-migration.md)。人物档案、人物参考及完整素材目录因公开授权需进一步明确而暂缓；大型照片包尚未迁入。

补充上传状态：内部对话决策日志被自动审批拦截，公开上传需更具体授权。历史SOP原件和全文一并暂缓，现仅纳入不含真实客户数据的通用运营流程与空白表单。
