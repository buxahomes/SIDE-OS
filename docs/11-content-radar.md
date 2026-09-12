# Side 地陪内容观察日报 V0.1

状态：2026-09-12 已通过 GitHub Actions 完成红狐密钥与两个搜索接口的真实接入测试；模型配置已通过GitHub Secrets注入，首次分析调用未成功；每日完整任务和定时器尚未启用。完整日报仍待联调。

[首次接入测试记录](https://github.com/buxahomes/SIDE-OS/actions/runs/34693756942)：关键词“地陪”，截至前一天的7日窗口，共2次请求；抖音返回并保留5条，小红书返回并保留3条。仅验证接口响应与规则筛选，未人工核对原帖，也未进行模型分析；未公开原帖正文。

## 每天能看到什么

两个平台分别展示相关帖子、作者、发布时间、原链接、点赞/收藏/评论/分享数量，以及可核对的评分依据。全部有效样本做规则初筛，每个平台最多选10条交给模型，输出参考分、理由、原创选题、待验证的需求假设、分析局限。模型分与规则分独立保留。

默认关键词：地陪、男地陪、北京地陪、城市陪游、北京陪拍、胡同漫步。全国关键词观察行业，北京关键词观察本地；城市命中依据是文本，不等于核实了作者所在地。相邻玩法只作为参考素材。

每天北京时间00:30执行，检索截至昨天的近7个完整自然日。数据源是第三方接口收录的样本，不能承诺平台全量，也不是全部昨日新增热帖。第一版不追踪窗口外的老帖翻红。未知发布时间的记录保留并标注，不能据此断言是新帖。

## 数据接口依据

2026-09-12核对红狐官方开源仓库版本 `289d6d99ee58a663c49daed78c50d7338ff68ce1`：

- [抖音搜索参考实现](https://github.com/redfox-data/redfox-community/blob/289d6d99ee58a663c49daed78c50d7338ff68ce1/skills/douyin-search/scripts/search_douyin.py)：POST `https://redfox.hk/story/api/dy/data/searchWork`，头 `REDFOX_API_KEY`，读取 `data.list`。
- [小红书搜索参考实现](https://github.com/redfox-data/redfox-community/blob/289d6d99ee58a663c49daed78c50d7338ff68ce1/skills/xiaohongshu-search/scripts/fetch_xhs_hot_articles.py)：POST `https://redfox.hk/story/api/xhs/search/search`，头 `X-API-KEY`，读取 `data.articles`。
- 两者使用keyword、pageNum、pageSize、startDate、endDate、source参数。不同鉴权头按各自实现保留，不能只照搬文章的统一鉴权说法。
- [模型JSON输出参数说明](https://api-docs.deepseek.com/guides/json_mode/)；使用可配置的兼容Chat Completions接口，要求支持JSON对象输出。模型名称在账户中确认，代码不固定过时型号。

本项目独立实现采集器，未复制或安装上述Skill。接口参数已对照源码，两个搜索接口已完成一次真实查询；更广关键词、其他额度权限和低粉内容覆盖仍须联调。缺字段保留null，响应结构改变报错，不静默当成零条。

## 评分与分析边界

初筛分 = 同平台样本互动总量百分位×35% + 文本相关性×40% + 新鲜度×25%。

- 热度：四项互动均有数据才计算总量；同平台当次样本内计算百分位，同量同分。少于2个完整样本不计算百分位。两个平台的分数不作直接高低比较。
- 相关性：核心词命中80分，相邻玩法命中40分，北京文本命中加20分，上限100。此为可调整的初始规则，不是经过验证的业务模型。
- 新鲜度：按发布距采集时刻的天数在14天内线性下降。缺发布时间或热度则不生成总分。
- `5000+`、`1.5w`等保留原始表示及近似标记。累计互动既非当日互动，也非播放量或成交量。
- 只有上次快照包含同一帖子、两次指标均完整且精确时，计算快照差值及实际间隔小时数。数据源可能更新滞后；不把这个差值称为实时增长率。
- 模型参考分为主观研究判断。证据必须是输入标题或描述中的连续短文；出现陌生ID、重复ID、越界评分、捏造引文则整批拒收，保留采集事实并标记分析失败。
- 默认没有评论正文、图像理解和视频转写。评论数量不能支持“客户在评论里要求什么”；标题不能支持“封面为什么有效”。后续可选取少量作品另行深读。
- 模型不执行外部文本里的指令，无工具权限。建议必须人工复核，不能自动作为SIDE价格、服务承诺或平台规则。

## 调用量与配置

`config/radar.json`定义关键词、日期窗口、页数和候选量。默认6词×2平台×1页，最多12次数据请求，每页30条，去重前最多360条；模型最多1次请求、20条分析。没有自动重试，失败保留状态，以免重复扣费。增加页数必须同时检查max_requests上限。

费用取决于账户实际接口单价和模型token价格；未确认单价前不承诺月费。一次预检不会联网或扣费：

```bash
python3 scripts/side_radar.py
python3 -m unittest discover -s tests -v
```

实际运行前，在运行环境或服务器的私有配置中设置以下变量，不要把密钥发到公开仓库：

| 环境变量 | 用途 |
| --- | --- |
| REDFOX_API_KEY | 红狐数据账户密钥 |
| RADAR_LLM_URL | 模型完整HTTPS接口地址，如 `https://api.deepseek.com/chat/completions` |
| RADAR_LLM_API_KEY | 模型服务密钥；ChatGPT订阅不能替代独立API凭证 |
| RADAR_LLM_MODEL | 账户当前可用且支持JSON输出的模型名 |

```bash
python3 scripts/side_radar.py --live
# 如需先单独验证数据覆盖：
python3 scripts/side_radar.py --live --collect-only
```

前者调用数据和模型，后者仅调用数据，两者可能消耗服务额度。缺少必要配置会在任何请求之前停止。

## 结果与持久化

默认写入 `research/local/radar/`，该目录已被git忽略。`latest.html`用于阅读、`latest.json`保存当次结构化数据，每次另存带时间戳的HTML和JSON。HTML无第三方脚本，外部内容会转义。输出文件权限600；仅作内部研究。签名链接去掉查询参数后可能不能直接打开，应回到平台查找原帖。

当前SIDE-OS是公开仓库，只保存工具代码和说明。研究正文、生成建议和模型输出不自动提交、不公开发布、不发送私信。长期数据需在实际运行主机上备份；本地临时工作区不能承担每日持久运行。

## Linux服务器部署

### GitHub Actions 接入测试（可先执行）

仓库 Settings → Secrets and variables → Actions 中添加 `REDFOX_API_KEY` 后，
`.github/workflows/redfox-check.yml` 可验证凭证与接口覆盖。
首次在 `feat/dipei-radar` 分支上传此工作流或修改专用检查脚本会触发测试；
其他文件修改不触发，PR事件和定时事件也不会触发。
合入默认分支后可以在 Actions 页面手动选择 `RedFox connection check` → Run workflow。

每次最多2次数据调用：两个平台各查一次“地陪”，每页最多5条，窗口为截至昨天的7个完整自然日。
不调用LLM、不上传原帖、日报或其他Artifacts；公开日志和任务摘要只包含请求状态及数量。
密钥只注入调用步骤的环境变量，不输出到日志，不复制回聊天或仓库。
`connection_ok`只表示两个接口接受查询，仍需看有效样本数量；`missing_secret`表示运行步骤没有拿到凭证；
`failed`需根据HTTP状态或结构错误继续排查。实际结果以Actions运行记录为准。

此工作流用于验证接入，尚未实现GitHub上的每日完整日报和私有持久存储。
此前的服务器定时模板仍是独立部署选项；GitHub Secrets不会自动传给服务器。

### 服务器完整日报

要求：Python3.11+、systemd、可联网访问所选服务。需要一台持续运行的服务器；这里提供模板，尚未创建或购买服务器。

1. 将本分支的仓库代码部署到 `/opt/side-radar`。代码目录只读，运行数据独立存放。
2. 管理员创建专用系统用户，并安装模板：

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin side-radar
sudo install -m 644 deploy/side-radar.service /etc/systemd/system/side-radar.service
sudo install -m 644 deploy/side-radar.timer /etc/systemd/system/side-radar.timer
sudo install -m 600 /dev/null /etc/side-radar.env
sudoedit /etc/side-radar.env
```

在私有文件中按 `变量名=值` 填入上表4项。不要重复执行创建空配置文件的命令，以免覆盖已有密钥。

3. 先单次验证，再开启每日运行：

```bash
sudo systemctl daemon-reload
sudo systemctl start side-radar.service
sudo systemctl status side-radar.service
# 确认两个平台均有目标数据、模型分析成功且成本符合预期后：
sudo systemctl enable --now side-radar.timer
sudo systemctl list-timers side-radar.timer
```

数据保存在 `/var/lib/side-radar/`。通过服务器管理员下载日报供内部查看，未配置公开网页或自动推送。定时器使用北京时间，不依赖服务器系统时区；停机错过的任务开机后补跑一次。停用：`sudo systemctl disable --now side-radar.timer`。

任何平台无有效数据或请求有错误，进程返回1并保存带状态的部分报告；缺配置等启动错误返回2。日志仅打印计数和状态，不能误报完整日报成功。定时器不会自动创建商业账户、充值、授权或购买服务器。

## 上线验收

先核实“地陪”和“北京地陪”在两个平台能否返回足够相关内容，再根据实际数据调整词表和窗口。核对原帖日期、互动字段、签名链接可访问性，验证模型引文与建议。第二次运行才能验证跨次差值。真实覆盖率、接口权限、模型成本和服务器定时执行均未通过离线测试替代。

## 模型接入检查

新增 `.github/workflows/analysis-check.yml`，使用GitHub Secrets中的 `RADAR_LLM_URL`、`RADAR_LLM_API_KEY`、`RADAR_LLM_MODEL` 及 `REDFOX_API_KEY`。
在草案分支更新该工作流或 `scripts/check_analysis.py` 会触发一次检查；合入默认分支后也可手动触发。
每次最多2次数据请求、1次模型请求，每个平台最多分析3条。先验证全部配置存在，再开始付费请求。
测试只公开状态、数量及token用量，不公开原帖、作者、模型分析文本或凭证。
DeepSeek请求使用官方非思考模式，结构化输出验证保持不变，错误只保留安全状态码。

[首次模型检查记录](https://github.com/buxahomes/SIDE-OS/actions/runs/34694366077)：采集成功，模型调用未成功，分析结果为0条；待服务问题处理后重试。未启用每日任务。
