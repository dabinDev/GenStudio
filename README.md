# CreativePannel 工作台

一个本地运行的多模型调试工作台，面向 `sub2api / newapi` 这类统一网关场景，支持：

- 文案创作
- 图片创作
- 视频创作
- 按模型独立配置 `baseURL`、`API Key`、模型标识
- 浏览器本地缓存配置
- 参考图预上传
- 视频任务轮询与结果预览

## 启动方式

```bash
npm install
npm run dev
```

默认访问地址：

```text
http://localhost:3000
```

如果本机 `3000` 已被占用，可以指定其它端口：

```bash
npm run dev -- --hostname 127.0.0.1 --port 3001
```

## 当前支持的能力

### 文案创作

- 走 `POST /v1/chat/completions`
- 适合脚本生成、提示词改写、营销文案和结构化输出

### 图片创作

- 走 `POST /v1/images/generations`
- 支持纯文生图
- 支持上传参考图后做图生图
- 上传流程先走 `/api/upload/presign`，再把返回的公网 URL 传给图片接口

### 视频创作

当前内置支持以下适配器：

- 即梦统一视频：`POST /v1/video/create` + `GET /v1/video/query`
- Vidu 统一视频：`POST /v1/video/create` + `GET /v1/video/query`
- Veo 统一视频：`POST /v1/video/create` + `GET /v1/video/query`
- Seedance 2.0：`POST /v1/video/generations` + `GET /v1/video/generations/{task_id}`

支持模式：

- 纯文生视频
- 参考图视频
- 首尾帧视频

## 设置页

设置页支持：

- 给每个模型单独设置 `baseURL`
- 给每个模型单独设置 `API Key`
- 单独覆盖模型名
- 新增自定义模型
- 删除自定义模型

所有设置保存在浏览器 `localStorage` 中，不会写入仓库。

## 自定义模型建议

如果你的网关中还有这些模型：

- `happyhorse`
- `banana`
- 其他你自己映射过的中转模型

建议按下面方式新增：

1. 先判断它是文案、图片还是视频
2. 再选择最接近的适配器
3. 如果是视频模型，优先判断它更像：
   - 统一视频 `POST /v1/video/create`
   - Seedance 风格 `POST /v1/video/generations`

如果后续你要继续扩展更多视频协议，重点改这几个文件：

- [src/lib/catalog.ts](</E:/WebProject/CreativePannel/src/lib/catalog.ts>)
- [src/components/settings-page.tsx](</E:/WebProject/CreativePannel/src/components/settings-page.tsx>)
- [src/components/video-workbench.tsx](</E:/WebProject/CreativePannel/src/components/video-workbench.tsx>)
- [src/app/api/proxy/video/create/route.ts](</E:/WebProject/CreativePannel/src/app/api/proxy/video/create/route.ts>)
- [src/app/api/proxy/video/query/route.ts](</E:/WebProject/CreativePannel/src/app/api/proxy/video/query/route.ts>)
