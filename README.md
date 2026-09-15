# XMU Lecture Auto Booking

厦大经济学科讲座预约脚本。**代码已建立，尚未通过真实预约/取消及 GitHub 云端登录验收。定时任务默认关闭。**

## 规则

- 北京时间每日 00:00，预约前一天新开放的讲座，举办时间从近到远，不筛选内容。
- 若 GitHub 调度延迟到 06:00 以后，本次不补报，避免错过首次抽签后占票。
- 每日 06:10，检查脚本管理的预约。已抽中保留并发 QQ 邮件；其余有效状态（含等待抽签）有取消按钮即取消。
- 用户已选择上述策略：如果学校开奖延迟，可能在实际开奖前取消。
- 不处理脚本启用前手动报名的讲座。页面读取失败、账号不匹配、未知结构不取消。
- 操作前记录意图，操作后重新读取状态。结果不明会报错，不重复报名。

## 本地安装与登录

需要 Python 3.10+。在仓库目录打开终端：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python login.py
```

在弹出的浏览器中手动完成学校登录、扫码等认证，并进入讲座预约列表。回终端按回车后，会话保存在 `.auth/session.json`，该目录已加入 gitignore。
这不是永久登录：会话到期、绑定设备/IP 或额外安全验证都可能让云端运行失败，届时重新登录并更新 Secret。
脚本不读取或保存校园密码，不导出 Codex 浏览器的会话。

## GitHub 配置

进入仓库 **Settings → Secrets and variables → Actions**，添加 Repository secrets：

| 名称 | 内容 |
| --- | --- |
| `XMU_STUNO` | 你的学号 |
| `XMU_STORAGE_STATE` | `.auth/session.json` 文件的完整内容 |
| `STATE_KEY` | 下方命令生成的加密密钥，首次生成后请保留，不随意更换 |
| `QQ_EMAIL` | 发件 QQ 邮箱地址 |
| `QQ_SMTP_CODE` | QQ 邮箱启用 SMTP 后获得的授权码，不是 QQ 密码 |
| `NOTIFY_EMAIL` | 可选；留空发送到发件邮箱自身 |

生成 STATE_KEY（输出属于秘密，只粘贴到 GitHub Secret）：

```powershell
.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

账户会话是敏感数据，只放入上述 Secret，不提交、不发聊天、不上传为公开附件。
建议私有仓库；有仓库写权限的人能够修改工作流以访问 Secrets。
工作流使用 `automation-state` 分支保存加密的预约记录，不保存明文个人信息。
不要删除该分支或更换 STATE_KEY，否则会丢失跟踪能力。仓库 Actions 必须允许工作流写入内容。

## 先验收，再开启定时

1. Actions → Lecture automation → Run workflow，mode=reserve，apply=false：只验证云端登录和读取，不预约。
2. 再用 results、apply=false 验证结果路径。
3. 在需要报名的新讲座开放次日 00:00—06:00 之间，手动选择 reserve、apply=true，并在网页核对成功。
4. 验证结果处理与 QQ 邮件投递。空任务运行成功不等于预约/取消已验收。
5. 在同一设置页的 Variables 添加 `AUTOMATION_ENABLED=true`，才会启用定时执行。

GitHub 日程使用 UTC：16:00 对应北京时间次日 00:00，22:10 对应次日 06:10。GitHub 不保证准点，可能延迟或漏运行。

## 当前限制

- 仅适配当前英文表头及中文状态的讲座列表。页面布局变化时会停止。
- 未验证的 JS 确认弹窗会被关闭，操作不会确认为成功，需根据真实弹窗补充适配。
- 云端会话复用尚未测试；不能承诺永久无人值守。
- SMTP 已接受邮件但进程在保存通知记录前终止时，重试可能产生重复邮件。
- GitHub 状态分支推送失败时，应先人工核对网页和运行日志再重跑；无法保证跨网络故障的严格一次执行。
- 失败邮件只提供概括原因，日志不输出学号、会话、完整页面或异常中的认证地址。
- 预先存在的等待预约不会被自动取消；需要你手动处理现有占票后，新任务才可能有票可用。

测试：`python -m unittest -v`。

参考：[Playwright 登录会话](https://playwright.dev/python/docs/auth)、[GitHub Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。
