# CreativePannel 工作台

CreativePannel 现在按 `Python + Vue` 结构运行：

- `fronted/`：Vue 3 + Vite 前端工作台。
- `server/`：FastAPI 后端代理服务。

旧 Next.js 代码暂时保留在仓库中作为迁移参照，当前新项目入口以 `fronted` 和 `server` 为准。

## 功能范围

- 文案创作：调用聊天补全接口，支持选择模型、关键词、模板和高级 JSON 参数。
- 图片创作：支持模型选择、模板、参考图上传、尺寸/比例/清晰度参数。
- 视频创作：支持文生视频、参考图视频、首尾帧视频、任务提交和查询。
- 设置页面：支持新增/编辑模型配置、按模型保存 `baseURL` 和 `API Key`、获取模型列表、单模型测速、勾选批量测试、批量删除。
- 本地缓存：模型配置、密钥和历史记录保存在浏览器 `localStorage`。

## 后端启动

```bash
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## MySQL 与登录

本地 MySQL 使用 Docker：

```bash
docker compose up -d mysql
```

默认库名为 `genstudio`，连接串见 `server/.env.example`。首次启动后端时会自动创建用户、会话、密钥、模型、子模型和调用记录表。

官网授权采用短期授权码：

```text
/auth/callback?code=xxx
```

后端会用 `OFFICIAL_AUTH_EXCHANGE_URL` 将 code 换成用户信息，并写入 `genstudio_session` Cookie。本地开发可调用 `POST /api/auth/dev-login` 创建测试登录态。

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## 前端启动

```bash
cd fronted
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

Vite 已把 `/api` 代理到 `http://127.0.0.1:8000`。

## 构建验证

```bash
cd fronted
npm run build
```

```bash
python -m compileall server
```

## 后端接口

- `GET /api/health`
- `POST /api/proxy/models`
- `POST /api/proxy/test`
- `POST /api/proxy/text`
- `POST /api/proxy/image`
- `POST /api/proxy/video/create`
- `POST /api/proxy/video/query`
- `POST /api/proxy/upload/presign`
