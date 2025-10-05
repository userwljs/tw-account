# 配置
数据目录默认位于 `$HOME/.local/share/tw-account`，如果设置了 `TW_ACCOUNT_DATA_PATH`，则为该环境变量的值。

配置文件位于数据目录下 `config.toml`。

该配置文件有以下必填项：
- `db_conn_scheme`：字符串。[DB URL](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls)，方言应为 `postgresql`，数据库驱动应为 `psycopg`。示例：`postgresql+psycopg://myRole@localhost/myDb`。
- `jwt_es256_private_key`：字符串。用于给 JWT 使用 ES256 算法签名的 PEM 格式私钥。
- `jwt_es256_public_key`:字符串。用于验证使用 ES256 算法签名的 JWT 的 PEM 格式公钥。

`root_path` 为 API 后端的根路径，应与前端配置一致。非必填项，但在部署中一般必需设置，用于反向代理的转发。考虑到部署，默认为 `/api`。该默认值是足够好的，一般无须进一步设置。
# 部署
应使用反向代理部署，这里使用 Caddy。

你还需要安装 uv（可使用 pip 安装）和 Python 3.13。你还需要顺畅的网络连接。
## 运行开发服务器
### 运行后端
在后端项目的根目录下，先执行：`uv sync`。这将设置虚拟环境、同步依赖。

然后，执行 `uv run fastapi dev src`。这将使用 FastAPI CLI，以开发模式运行后端，默认绑定 8000 端口。
### 运行前端
确保你安装了 pnpm。

在前端项目的根目录下，先执行：`pnpm i`。这将安装前端项目的依赖。

然后，执行 `pnpm dev`，这将运行开发服务器，默认绑定 5173 端口。
### 运行反向代理
`Caddyfile` 示例如下，该示例会在 `127.0.0.1:8003` 启动，并假设前端为 `127.0.0.1:5173`，且 API base URL 配置为 `/api`；后端为 `127.0.0.1:8000` 且 `root_path` 为 `/api`：
```
127.0.0.1:8003 {
	encode

	handle /api/* {
		reverse_proxy localhost:8000
	}

	handle {
		reverse_proxy localhost:5173
	}
}
```
## 生产部署
TODO

# 维护数据库
**每次升级时**都应使用 **[Alembic](https://alembic.sqlalchemy.org/)** 进行数据库迁移。
