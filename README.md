# AI 妆造巡检

每 10 分钟通过接口读取新心和中鼎的在线直播间，只检查 WPS 固定主播名单内的抖音账号。程序复用两个后台已有页面的登录状态，通过接口导出在线主播并筛选；命中后直接从 FLV 接口抽取直播画面，不裁剪、不叠加文字。低于 720 像素宽的直播源会使用高质量算法放大至 720 像素宽并轻度锐化，原本已经清晰的高分辨率直播源不会放大。整个过程不会打开跟播列表，不会在用户桌面截图，也不会在用户正在使用的 Edge 中新开标签、跳转页面或抢占焦点。程序通过“化妆师人员表”的“小队”列识别归属，只发送到对应小队群并按手机号 @ 化妆师；不再发送总群，未分队或未配置群机器人的记录也不会回退到总群：

- 开播时长大于等于 2 小时
- 累计观众小于 500
- 同一抖音号当天尚未提醒

累计观众使用跟播列表和详情页共同依赖的 `get_room_data` 接口，不使用数值更高的 `data_ext` 口径。程序会先通过接口刷新累计观众和开播时长，再生成截图和群消息。

程序使用固定主播名单中的“化妆师”名称关联“化妆师人员表”，再读取人员表中的手机号：手机号非空时 @ 对应成员，手机号为空或找不到对应化妆师时照常发送截图和文字但不 @。支持“手机号”“手机号码”“联系电话”“电话”四种表头名称。AI 妆容分析和调整建议暂未启用。

## 名单规则

程序每轮优先读取 `WPSDrive` 中的云盘同步文件，并把成功读取的最新版保存到
`daily_data/_source_cache/`。同步文件暂时不可用时会依次使用稳定缓存和 WPS 自动恢复备份；
云端同步到本机后会自动覆盖缓存。

固定主播名单使用与原表一致的有效规则：

- 主播编号不为空
- 化妆师不等于“未分组”
- 状态为“线下”
- 结束日期为空、0，或不早于当天
- 在最近 60 天经纪人原始数据中存在抖音账号

一个主播编号近 60 天出现过的所有抖音号都会加入监控。后台归属不写死：账号在哪个实时后台出现，就使用该后台。

WPS 云端修改必须先同步到本机 WPS，程序才能读到最新备份。建议本机保持 WPS 登录并打开这两份云文档。

## 首次配置

安装依赖：

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

七个小队群分别使用独立的用户环境变量保存机器人 webhook key，变量名称在
`config.json` 的 `wechat.team_webhook_envs` 中配置。总群 webhook 不参与发送，
key 不写入代码或配置文件。

## 运行

1. 从 `../直播数据导出` 启动并登录新心、中鼎两个 Edge。
2. 先双击 `START_PREVIEW.cmd`。预览模式会读取后台并截图，但不发群、不写当天去重。
3. 确认预览日志正确后，双击 `START_MONITOR.cmd` 正式运行。

每轮结束后，运行窗口会按秒显示下一轮倒计时；日志仅记录下一轮预计开始时间。

也可以在项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\makeup_monitor.ps1 -Mode CheckRoster
powershell -ExecutionPolicy Bypass -File .\scripts\makeup_monitor.ps1 -Mode CheckEdges
powershell -ExecutionPolicy Bypass -File .\scripts\makeup_monitor.ps1 -Mode Preview
powershell -ExecutionPolicy Bypass -File .\scripts\makeup_monitor.ps1 -Mode RunOnce
powershell -ExecutionPolicy Bypass -File .\scripts\makeup_monitor.ps1 -Mode Monitor
```

## 数据目录

```text
daily_data/YYYYMMDD/
├─ roster_snapshot.json
├─ screenshots/
├─ state/notified.json
└─ logs/makeup_monitor.log
```

只有图片和带手机号 @ 的文字都发送成功后，账号才会写入 `notified.json`。发送或截图失败不会去重，下一轮会自动重试。

同一个提醒的图片和文字可以连续发送，同时程序保证每个机器人不超过 20 条消息/分钟，并对企业微信限流自动退避重试。
