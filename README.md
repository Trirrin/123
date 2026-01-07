# Kiro 自动补号脚本

自动注册 Kiro 账号并添加到 Kiro Proxy。

## 快速开始

```bash
cd /www/auto-add-account
docker compose up --build
```

## 配置文件

编辑 `config.json`：

```json
{
  "imap": {
    "host": "mail.example.com",
    "port": 143,
    "username": "user@example.com",
    "password": "password",
    "use_ssl": false,
    "starttls": true,
    "verify_cert": false
  },
  "email_domain": "example.com",
  "backend_url": "http://149.13.91.124:8000",
  "admin_password": "your_admin_password"
}
```

| 字段 | 说明 |
|------|------|
| `imap.*` | IMAP 邮箱配置，用于接收验证码 |
| `email_domain` | 注册用的邮箱域名 |
| `backend_url` | Kiro Proxy 地址 |
| `admin_password` | Kiro Proxy 管理密码 |

## 运行

```bash
# 前台运行（查看日志）
docker compose up --build

# 后台运行
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止
docker compose down
```
