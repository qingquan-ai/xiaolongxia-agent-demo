# 定时日报任务自检清单

用于检查服务器 crontab 是否能稳定触发小龙虾经营日报生成和飞书推送。

## 1. 检查服务状态

```bash
systemctl status xiaolongxia-demo --no-pager
```

确认服务处于 `active (running)`。如果服务异常，先查看应用日志：

```bash
journalctl -u xiaolongxia-demo -n 100 --no-pager -o cat
```

## 2. 检查环境变量

确认 `.env` 文件存在：

```bash
ls -l /root/xiaolongxia-agent-demo/.env
```

确认 `.env` 中配置了 `CRON_SECRET`：

```bash
grep '^CRON_SECRET=' /root/xiaolongxia-agent-demo/.env
```

不要把 `CRON_SECRET` 复制到聊天、日志或截图里。

## 3. 检查脚本文件

```bash
ls -l /root/xiaolongxia-agent-demo/scripts/cron_daily_report.sh
bash -n /root/xiaolongxia-agent-demo/scripts/cron_daily_report.sh
```

`bash -n` 没有输出且退出码为 0，表示脚本语法正常。

## 4. 手动执行一次脚本

```bash
/bin/bash /root/xiaolongxia-agent-demo/scripts/cron_daily_report.sh
```

执行完成后查看脚本日志：

```bash
tail -n 100 /root/xiaolongxia-agent-demo/cron_daily_report.log
```

日志里应能看到：

- `cron daily report started`
- `http_status=200`
- `curl_exit_code=0`
- 接口返回内容
- `result=success`
- `cron daily report finished`

## 5. 检查 crontab 配置

```bash
crontab -l
```

正式任务只保留每天 22:00 执行：

```bash
0 22 * * * /bin/bash /root/xiaolongxia-agent-demo/scripts/cron_daily_report.sh
```

如果旧任务里还有直接 `curl http://127.0.0.1:8000/api/reports/daily` 的配置，需要删除，避免重复生成和重复推送。

## 6. 测试任务清理

如果为了验证临时添加过每分钟执行的测试任务，例如：

```bash
* * * * * /bin/bash /root/xiaolongxia-agent-demo/scripts/cron_daily_report.sh
```

测试完成后必须删除，只保留每天 22:00 的正式任务。

## 7. 常见异常

- `result=failed reason=CRON_SECRET missing`：检查 `.env` 是否存在，以及是否配置了 `CRON_SECRET=`。
- `http_status=401`：检查 `.env` 中的 `CRON_SECRET` 是否和服务读取到的密钥一致。
- `curl_exit_code` 非 0：检查 FastAPI 服务是否在本机 `127.0.0.1:8000` 正常运行。
- 没有飞书消息：先看 `cron_daily_report.log`，再看 `journalctl -u xiaolongxia-demo -n 100 --no-pager -o cat`。
