# GitHub 上传教程

本教程将指导你如何将 `/opt/S-Recorder.zip` 解压后的源码上传至 GitHub 仓库：
https://github.com/rsxbgdurxbjcx-arch/S-Recorder

## 前置要求

- 系统已安装 `git`、`unzip` 和 `curl`
- 已配置 GitHub 账号 SSH 密钥或拥有仓库写入权限的 Personal Access Token

## 步骤

### 1. 解压项目压缩包

将 `/opt` 目录下的 `S-Recorder.zip` 解压到 `/opt`：

```bash
sudo unzip /opt/S-Recorder.zip -d /opt
```

解压后，项目源码将位于 `/opt/S-Recorder` 目录。

### 2. 进入项目目录

```bash
cd /opt/S-Recorder
```

### 3. 初始化 Git 仓库

```bash
git init
```

### 4. 添加所有文件到暂存区

```bash
git add .
```

### 5. 提交代码

```bash
git commit -m "Initial commit: S-Recorder v1.0.0"
```

### 6. 重命名主分支为 main

```bash
git branch -M main
```

### 7. 添加远程仓库

```bash
git remote add origin https://github.com/rsxbgdurxbjcx-arch/S-Recorder.git
```

> 如果你使用 SSH 方式，请将上面的 HTTPS 地址替换为：
> `git@github.com:rsxbgdurxbjcx-arch/S-Recorder.git`

### 8. 推送到 GitHub

```bash
git push -u origin main
```

推送成功后，打开 https://github.com/rsxbgdurxbjcx-arch/S-Recorder 即可查看源码。

## 完整命令示例

```bash
# 1. 解压
sudo unzip /opt/S-Recorder.zip -d /opt

# 2. 进入目录
cd /opt/S-Recorder

# 3. 初始化仓库
git init

# 4. 添加文件
git add .

# 5. 提交
git commit -m "Initial commit: S-Recorder v1.0.0"

# 6. 重命名分支
git branch -M main

# 7. 添加远程仓库
git remote add origin https://github.com/rsxbgdurxbjcx-arch/S-Recorder.git

# 8. 推送
git push -u origin main
```

## 常见问题

### 推送时提示权限不足

如果你使用 HTTPS 地址推送，GitHub 可能要求输入用户名和密码。此时应使用 Personal Access Token 替代密码。

如果你已配置 SSH 密钥，请使用 SSH 地址：

```bash
git remote set-url origin git@github.com:rsxbgdurxbjcx-arch/S-Recorder.git
git push -u origin main
```

### 远程仓库已存在内容

如果目标仓库已存在文件，请先拉取并合并：

```bash
git pull origin main --rebase
git push -u origin main
```

### 不想上传 node_modules 或录制文件

项目根目录已包含 `.dockerignore`，如需 Git 忽略，可创建 `.gitignore`：

```bash
cat > .gitignore << 'EOF'
node_modules/
dist/
data/
__pycache__/
*.pyc
*.log
.venv/
venv/
EOF
git add .gitignore
git commit -m "Add .gitignore"
git push
```
