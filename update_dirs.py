#!/usr/bin/env python3
"""
HuggingFace 仓库目录自动更新脚本
遍历 9 个指定仓库 → ls-remote 获取 HEAD hash
→ 浅克隆 → 判断 bot 是否已处理 → 运行 mul.py → diff → 推送
"""

import os
import sys
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta

# ============================================================
# 配置区
# ============================================================
REPOS = [
    "datasets/VoiceOfML/MLMRL-Hub",
    "datasets/VoiceOfML/Omnibus",
    "datasets/VoiceOfML/MLMRL-Library",
    "datasets/VoiceOfML/Teachers",
    "datasets/VoiceOfML/A-Historical-Learning-Data",
    "datasets/VoiceOfML/Japanese-Materials",
    "datasets/VoiceOfML/GPCREducation",
    "datasets/VoiceOfML/SovMaterials",
    "datasets/VoiceOfML/VOMEBOOK"
]

HF_USERNAME = "VoiceOfML"
BOT_AUTHOR = "github-actions[bot]"
AUTO_COMMIT_PREFIX = "自动更新目录"
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MUL_PY_PATH = os.path.join(SCRIPT_DIR, "mul.py")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

if not HF_TOKEN:
    print("❌ 环境变量 HF_TOKEN 未设置，退出。")
    sys.exit(1)


def run_cmd(cmd_list, cwd=None):
    """运行命令，返回 CompletedProcess"""
    env = os.environ.copy()
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    try:
        return subprocess.run(
            cmd_list, cwd=cwd, env=env,
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        return e


def beijing_now_str():
    """返回北京时间日期字符串，如 2026-06-05"""
    beijing = timezone(timedelta(hours=8))
    return datetime.now(beijing).strftime("%Y-%m-%d")


def beijing_now_display():
    """返回带时间的北京时间字符串"""
    beijing = timezone(timedelta(hours=8))
    return datetime.now(beijing).strftime("%Y-%m-%d %H:%M:%S")


def process_repo(repo_path):
    """处理单个 HuggingFace 仓库"""
    repo_name = repo_path.split("/")[-1]
    clone_url = f"https://{HF_USERNAME}:{HF_TOKEN}@huggingface.co/{repo_path}"

    print(f"\n{'=' * 60}")
    print(f"📦 [{repo_name}]")
    print(f"{'=' * 60}")

    # ── 1. 获取远程 HEAD hash ──
    r = run_cmd(["git", "ls-remote", clone_url, "HEAD"])
    if r.returncode != 0:
        print(f"  ❌ ls-remote 失败: {r.stderr.strip()}")
        return
    remote_hash = r.stdout.strip().split()[0]
    print(f"  远程 HEAD: {remote_hash[:8]}")

    # ── 2. 浅克隆到临时目录 ──
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = os.path.join(tmpdir, "repo")
        r = run_cmd(["git", "clone", "--depth", "1", clone_url, repo_dir])
        if r.returncode != 0:
            print(f"  ❌ clone 失败: {r.stderr.strip()}")
            return
        print(f"  ✅ clone 完成")

        # ── 3. 检查 HEAD 是否本 bot 推送的 ──
        r = run_cmd(
            ["git", "log", "-1", "--format=%an|%s"],
            cwd=repo_dir
        )
        if r.returncode == 0:
            parts = r.stdout.strip().split("|", 1)
            author = parts[0] if len(parts) > 0 else ""
            msg = parts[1] if len(parts) > 1 else ""
        else:
            author, msg = "", ""

        if author == BOT_AUTHOR and msg.startswith(AUTO_COMMIT_PREFIX):
            print(f'  ⏭️  最新 commit 是本 bot 推送的 ("{msg}")，跳过。')
            return
        print(f"  最新 commit author: {author}, msg: {msg[:60]}")

        # ── 4. 复制 mul.py 并运行 ──
        dst = os.path.join(repo_dir, "mul.py")
        shutil.copy(MUL_PY_PATH, dst)
        r = subprocess.run(
            [sys.executable, "mul.py"],
            cwd=repo_dir,
            capture_output=True,
            text=True
        )
        os.remove(dst)
        if r.returncode != 0:
            print(f"  ⚠️  mul.py 可能部分失败:\n{r.stderr.strip()[:300]}")
        else:
            print(f"  ✅ mul.py 运行完成")

        # ── 5. 检查是否有实际变更 ──
        r = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
        if r.returncode != 0:
            print(f"  ❌ git status 失败")
            return

        changed = [line for line in r.stdout.strip().split("\n") if line]
        if not changed:
            print(f"  ⏭️  目录文件无变化，跳过 push。")
            return

        print(f"  📝 检测到 {len(changed)} 个文件变更:")
        for line in changed:
            print(f"     {line}")

        # ── 6. 提交并推送 ──
        date_str = beijing_now_str()
        commit_msg = f"{AUTO_COMMIT_PREFIX} [{date_str}] [auto-bot]"

        run_cmd(["git", "add", "树形目录.txt", "直接目录.txt"], cwd=repo_dir)
        run_cmd([
            "git", "-c", "user.name=github-actions[bot]",
            "-c", "user.email=github-actions[bot]@users.noreply.github.com",
            "commit", "-m", commit_msg
        ], cwd=repo_dir)
        r = run_cmd(["git", "push"], cwd=repo_dir)
        if r.returncode == 0:
            print(f"  🚀 推送成功: {commit_msg}")
        else:
            print(f"  ❌ 推送失败: {r.stderr.strip()[:300]}")


def main():
    print("=" * 60)
    print("HuggingFace 仓库目录自动更新")
    print(f"北京时间: {beijing_now_display()}")
    print(f"待处理仓库: {len(REPOS)} 个")
    print("=" * 60)

    for repo in REPOS:
        try:
            process_repo(repo)
        except Exception as e:
            print(f"  💥 未预期异常: {e}")

    print(f"\n{'=' * 60}")
    print("全部处理完毕。")
    print("=" * 60)


if __name__ == "__main__":
    main()
