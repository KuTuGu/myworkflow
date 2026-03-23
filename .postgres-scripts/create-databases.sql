-- 创建额外的数据库
CREATE DATABASE deepagent_checkpointer_db;
CREATE DATABASE deepagent_store_db;
CREATE DATABASE deepagent_history_db;

-- 可选：授予权限
GRANT ALL PRIVILEGES ON DATABASE deepagent_checkpointer_db TO ${POSTGRES_USER};
GRANT ALL PRIVILEGES ON DATABASE deepagent_store_db TO ${POSTGRES_USER};
GRANT ALL PRIVILEGES ON DATABASE deepagent_history_db TO ${POSTGRES_USER};
