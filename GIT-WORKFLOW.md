# Animal Gateway - LiteLLM Fork Git 工作流

本文档说明如何管理 Fork 仓库，保持代码与上游同步，同时维护团队自定义品牌。

---

## 📋 分支策略

我们使用以下分支策略：

```
upstream (BerriAI/litellm)
    ↓ fetch
main                              ← 保持与上游同步（干净，无修改）
    ↓ branch off
custom-branding-animal-gateway   ← 团队自定义品牌修改
```

### 为什么使用分支而不是直接修改 main？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **直接修改 main** | 简单 | ❌ 难以同步上游<br>❌ 冲突多<br>❌ 无法回退 |
| **使用专用分支** ⭐ | ✅ 易于同步上游<br>✅ 冲突少<br>✅ 可回退<br>✅ 清晰的修改历史 | 稍微复杂 |

---

## 🚀 初始设置（已完成）

```bash
# 1. 克隆 Fork 仓库
cd ~/workspace/xykong
git clone https://github.com/xykong/litellm.git
cd litellm

# 2. 添加上游远程仓库
git remote add upstream https://github.com/BerriAI/litellm.git

# 3. 创建自定义分支
git checkout -b custom-branding-animal-gateway

# 4. 进行品牌修改（已完成）
# ... 修改文件 ...

# 5. 提交并推送
git add -A
git commit -m "feat: 更新品牌为 Animal Gateway"
git push origin custom-branding-animal-gateway
```

---

## 🔄 日常工作流

### 方式 A：使用 custom-branding-animal-gateway 分支（当前）

```bash
# 始终在自定义分支上工作
git checkout custom-branding-animal-gateway

# 进行修改
# ... edit files ...

# 提交
git add -A
git commit -m "feat: 添加新功能"
git push origin custom-branding-animal-gateway

# 构建 Docker 镜像
docker build -t animal-gateway/litellm:custom .
```

### 方式 B：直接使用 main 分支（如果您更喜欢）

如果您觉得分支管理太复杂，也可以将自定义合并到 main：

```bash
# 切换到 main
git checkout main

# 合并自定义分支
git merge custom-branding-animal-gateway

# 推送到远程
git push origin main

# 以后就在 main 上工作
git checkout main
# ... make changes ...
git commit -am "feat: 新功能"
git push origin main
```

**注意**：使用方式 B 后，main 分支将包含自定义修改，同步上游时会有更多冲突。

---

## 🔃 同步上游更新

### 使用分支策略（推荐）

```bash
# 1. 获取上游最新代码
git fetch upstream

# 2. 更新本地 main（保持与上游一致）
git checkout main
git merge upstream/main
# 或使用 rebase：git rebase upstream/main

# 3. 推送更新后的 main
git push origin main

# 4. 将上游更新应用到自定义分支
git checkout custom-branding-animal-gateway
git rebase main

# 5. 解决冲突（如果有）
# Git 会提示冲突文件，手动编辑解决
# 通常只会在 4 个已修改的文件中产生冲突

# 6. 继续 rebase
git add <resolved-files>
git rebase --continue

# 7. 强制推送自定义分支（因为 rebase 改变了历史）
git push origin custom-branding-animal-gateway --force

# 8. 重新构建 Docker 镜像
docker build -t animal-gateway/litellm:custom .
```

### 使用 main 分支直接修改

```bash
# 1. 获取上游最新代码
git fetch upstream

# 2. 合并上游更新到 main
git checkout main
git merge upstream/main

# 3. 解决冲突（会有很多）
# 手动编辑冲突文件，保留自定义修改

# 4. 提交合并
git add -A
git commit -m "chore: 合并上游更新"

# 5. 推送
git push origin main

# 6. 重新构建 Docker 镜像
docker build -t animal-gateway/litellm:custom .
```

---

## 🛠️ 常用命令

### 查看当前分支

```bash
git branch
# * custom-branding-animal-gateway
#   main
```

### 查看远程仓库

```bash
git remote -v
# origin    https://github.com/xykong/litellm.git (fetch)
# origin    https://github.com/xykong/litellm.git (push)
# upstream  https://github.com/BerriAI/litellm.git (fetch)
# upstream  https://github.com/BerriAI/litellm.git (push)
```

### 查看自定义修改

```bash
# 查看自定义分支与 main 的差异
git diff main..custom-branding-animal-gateway

# 查看修改的文件列表
git diff main..custom-branding-animal-gateway --name-only
```

### 查看上游更新

```bash
# 获取上游信息
git fetch upstream

# 查看 main 与上游的差异
git log main..upstream/main --oneline

# 查看上游有哪些新功能
git log --oneline --graph upstream/main ^main
```

---

## 🎯 推荐策略

### 对于团队内部 Fork：

我的建议是**使用分支策略**，原因如下：

1. **易于同步**：main 保持干净，与上游同步时冲突最少
2. **清晰的修改历史**：可以清楚看到哪些是自定义，哪些是上游代码
3. **灵活性**：可以随时切换到原始版本（main）或自定义版本（custom-branding）
4. **团队协作**：其他团队成员可以清楚知道哪些是自定义代码

### 实际操作建议：

**选项 1：保持当前分支策略（推荐）**
- ✅ main: 镜像上游，不做修改
- ✅ custom-branding-animal-gateway: 所有自定义
- ✅ 构建镜像时使用 custom-branding 分支

**选项 2：简化为 main 分支**
- ✅ 删除 custom-branding 分支
- ✅ 将自定义合并到 main
- ✅ 以后只维护 main 分支
- ⚠️ 同步上游时会有更多冲突

---

## 📝 决策建议

如果您的团队：

### 选择分支策略，如果：
- ✅ 希望经常同步上游更新
- ✅ 团队有多人协作
- ✅ 希望保持代码管理的灵活性
- ✅ 愿意学习稍微复杂的 Git 工作流

### 选择直接使用 main，如果：
- ✅ 很少同步上游更新
- ✅ 团队只有 1-2 人
- ✅ 希望简单直接
- ✅ 不介意手动解决更多冲突

---

## 🔧 如何切换策略

### 从分支策略切换到 main：

```bash
# 切换到 main
git checkout main

# 合并自定义分支
git merge custom-branding-animal-gateway

# 推送
git push origin main

# 删除自定义分支（可选）
git branch -d custom-branding-animal-gateway
git push origin --delete custom-branding-animal-gateway

# 以后就在 main 上工作
```

### 从 main 切换到分支策略：

```bash
# 重置 main 到上游（丢失自定义）
git checkout main
git fetch upstream
git reset --hard upstream/main
git push origin main --force

# 恢复自定义分支
git checkout custom-branding-animal-gateway

# 以后在自定义分支上工作
```

---

## 📚 相关文档

- [ANIMAL-GATEWAY-BRANDING.md](ANIMAL-GATEWAY-BRANDING.md) - 品牌修改说明
- [Git Branching Strategies](https://git-scm.com/book/en/v2/Git-Branching-Branching-Workflows)
- [Managing Remotes](https://git-scm.com/book/en/v2/Git-Basics-Working-with-Remotes)

---

**推荐**: 继续使用分支策略，这是大多数团队的最佳实践！
