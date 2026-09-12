# SIDE 一程｜项目知识库

独立项目：SIDE-OS。整理日期：2026-09-12。仓库：[buxahomes/SIDE-OS](https://github.com/buxahomes/SIDE-OS)。用户已明确选择保持 **Public** 并上传已整理资料；本提交为知识库初始导入，不写入 BUXA-OS。

这里保存城市同行服务的规则、流程、人物档案、照片系统和研究资料；保留原件与出处，使后续回答、报价和素材制作能追溯依据。

## 从这里开始

| 要做的事 | 入口 |
| --- | --- |
| 了解品牌与服务内容 | [项目定位](docs/01-brand.md) |
| 给客户报价 | [现行测试阶段 V1](docs/02-pricing.md) · [价格数据](config/pricing.json) |
| 执行订单 | [运营流程](docs/03-operations.md) · [话术和表单](templates/operations.md) |
| 查看人物资料 | [Side档案](docs/04-people.md) |
| 生成和修改照片 | [照片系统](docs/05-photos.md) · [去AI感规范原件](sources/originals/SIDE_照片生成去AI感规范_V1.md) |
| 找素材和历史文件 | [素材索引](assets/README.md) · [全部目录](assets/catalog.csv) |
| 读取小红书、抖音 | [读取说明](docs/06-social-reading.md) |
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

`fetch` 尝试读取公开网页中的正文或元数据，不能保证平台允许访问。截图、音视频导入会登记文件和校验值，**不等于已完成OCR、语音转写或视频理解**；正文、人工识别结果和字幕可单独入库。官方抖音账号API尚未接通。没有定时抓取、自动发布或自动推送。

## 使用顺序

当前用户明确指令 → 本次整理的现行规则 → 原始文件 → 历史草稿 → 外部研究。日期新的文件也可能包含过时规则，不能仅凭文件名决定生效版本。研究材料不自动成为SIDE承诺。

知识文字和核心原件已打包；大型照片包和其余参考图目前保留来源索引，尚未将全部二进制素材迁入GitHub。目录中不明归属素材与无关资料有单独状态。具体数量以迁移报告为准。
