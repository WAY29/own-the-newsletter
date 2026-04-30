[English](README.md)

# Own the Newsletter

一个自托管工具，从你的 IMAP 邮箱中读取邮件并转换为私有 RSS 订阅源，附带简洁的 Web UI 进行管理。

> 本项目绝大部分代码由 Codex 和 Claude 编写。

## 启发

灵感来自 [kill-the-newsletter.com](https://kill-the-newsletter.com/)，该项目通过自建邮件服务器来接收 newsletter。与之不同的是，**Own the Newsletter** 不需要部署邮件服务，而是利用你已有邮箱的 IMAP 服务（Gmail、Outlook、Fastmail 等）来获取 newsletter 邮件。

这样做的好处是：你可以使用知名邮箱服务商，避免因为邮箱域名白名单/黑名单机制而被某些 newsletter 拒绝订阅。

## 快速安装

### Docker（推荐）

```bash
git clone https://github.com/WAY29/own-the-newsletter.git
cd own-the-newsletter
cp .env.example .env
# 编辑 .env 文件，设置你自己的值（参见下方环境变量说明）
docker compose up --build
```

打开 `http://localhost:8080/admin/`，使用你设置的 `OTN_ADMIN_TOKEN` 登录。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OTN_ADMIN_TOKEN` | `change-this-admin-token` | 登录管理面板的令牌。**部署前请务必修改。** |
| `OTN_SECRET_KEY` | `change-this-long-random-secret-key` | 用于加密存储的 IMAP 密码的密钥。必须保持稳定——修改后所有已保存的凭据将失效。**部署前请务必修改。** |
| `OTN_DATABASE_PATH` | `/data/own-newsletter.sqlite` | SQLite 数据库文件路径。 |
| `OTN_FEEDS_DIR` | `/data/feeds` | 生成的 RSS XML 文件存储目录。 |
| `OTN_BACKEND_PORT` | `8000` | FastAPI 后端的主机映射端口（直接访问）。 |
| `OTN_FRONTEND_PORT` | `8080` | Nginx 代理的主机映射端口，用于访问完整应用。 |
| `OTN_PUBLIC_ORIGIN` | `http://localhost:8080` | 应用的外部可见 URL。如果修改了 `OTN_FRONTEND_PORT` 或部署在反向代理后面，请同步更新此值。 |
| `OTN_COOKIE_SECURE` | `false` | 如果通过 HTTPS 提供服务，设为 `true` 以启用安全 Cookie。 |
| `OTN_SESSION_DAYS` | `30` | 管理员会话的有效天数。 |
| `OTN_SCHEDULER_ENABLED` | `true` | 是否启用后台 IMAP 同步调度器。 |
| `OTN_SCHEDULER_TICK_SECONDS` | `60` | 调度同步检查的间隔秒数。 |
| `OTN_IMAP_TIMEOUT_SECONDS` | `30` | IMAP 连接超时秒数。 |
| `OTN_LOG_LEVEL` | `INFO` | 应用日志级别（`DEBUG`、`INFO`、`WARNING`、`ERROR`）。 |

## 本地开发

**后端：**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

**后端测试：**

```bash
cd backend
uv run pytest
```

**前端：**

```bash
cd frontend
npm install
npm run dev
```

## 贡献

欢迎贡献！请提交 Issue 或 Pull Request。

1. Fork 本仓库
2. 创建你的功能分支（`git checkout -b feature/my-feature`）
3. 提交你的更改（`git commit -m 'feat: add my feature'`）
4. 推送到分支（`git push origin feature/my-feature`）
5. 创建 Pull Request

## License

本项目基于 [MIT License](LICENSE) 开源。
