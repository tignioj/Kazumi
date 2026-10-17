#!/usr/bin/env python3
"""Package an unsigned integration prerelease from the checked-out source."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "tool"))
from verify_ohos_hap import verify_hap


def validate_tag(tag):
    version = re.search(r"^version: ([0-9.]+)\+", (ROOT / "pubspec.yaml").read_text(), re.M)
    if not version or not re.fullmatch(re.escape(version[1]) + r"-ohos\.[1-9][0-9]*", tag):
        raise ValueError("Expected an application-version-ohos.<positive integer> prerelease tag")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hap", type=Path, nargs="?")
    parser.add_argument("--tag")
    parser.add_argument("--check-tag")
    args = parser.parse_args()
    if args.check_tag:
        validate_tag(args.check_tag)
        print(f"Validated prerelease tag: {args.check_tag}")
        return
    if not args.hap or not args.tag:
        parser.error("hap and --tag are required")
    validate_tag(args.tag)
    app = verify_hap(args.hap)
    output = ROOT / "build/ohos-release"
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"Kazumi_{args.tag}_HarmonyOS_arm64_unsigned.hap"
    shutil.copyfile(args.hap, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {destination.name}\n")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    has_credentials = os.environ.get("API_CREDENTIALS_PRESENT") == "true"
    info = {
        "tag": args.tag,
        "source_branch": "codex/feat-ohos-2.3.9-integration",
        "source_ref": os.environ.get("SOURCE_REF", commit),
        "commit": commit,
        "workflow_commit": os.environ.get("GITHUB_SHA"),
        "workflow_run": os.environ.get("GITHUB_RUN_ID"),
        "flutter_revision": os.environ.get("FLUTTER_OHOS_REVISION"),
        "bundle_name": app["bundleName"],
        "version": app["versionName"],
        "version_code": app["versionCode"],
        "min_api_version": app["minAPIVersion"],
        "compile_sdk_version": app["compileSdkVersion"],
        "architecture": "arm64",
        "build_mode": "release",
        "signed": False,
        "api_credentials_present": has_credentials,
        "file": destination.name,
        "bytes": destination.stat().st_size,
        "sha256": digest,
    }
    (output / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    limitation = (
        "- 已在 CI 中注入配置的 API 凭据；本次发布未做在线鉴权回归。\n"
        if has_credentials else
        "- **本版未配置弹弹与 Kazumi 镜像 API 密钥**：弹弹弹幕、需要签名鉴权的镜像接口可能返回鉴权错误或不可用。\n"
        "  此限制不影响本次屏幕方向修复；实际视频播放已在本地真机验证。\n"
    )
    notes = f"""Kazumi {args.tag} 鸿蒙预发布版，基于 Kazumi {app['versionName']}，包含 [PR #45](https://github.com/ErBWs/Kazumi/pull/45) 的全屏退出方向修复。

- 修复平板及展开态设备退出全屏后仍保留横屏锁定，无法恢复竖屏 UI 的问题；退出时恢复自动旋转策略。
- 应用源码来自 `codex/feat-ohos-2.3.9-integration`，提交 `{commit}`；发布流程独立于 PR 分支。
- arm64 Release AOT 构建，包含 ECH、mpv 与 Native Assets；最低 HarmonyOS API {app['minAPIVersion'] % 1000}，本地真机回归设备为 MatePad mini / API 26，其他设备及低 API 尚未全面回归。
- 本版采用正式包名 `{app['bundleName']}`，与此前 `com.predidit.kazumi.ohostest` 独立测试包不同。
{limitation}- **下载的 HAP 未签名**：请使用 DevEco Studio 或小白调试助手为自己的设备签名后安装。
- CI 执行静态分析、Flutter 测试和 Release HAP 原生库完整性校验；本地已验证全屏按钮、系统返回、重复全屏切换及退出播放页后恢复竖屏。
- `SHA256SUMS` 用于下载校验；`build-info.json` 记录源码、构建和凭据配置状态。

这是用于验证修复的预发布版，欢迎反馈问题。
"""
    (output / "RELEASE_NOTES.md").write_text(notes)
    print(f"Verified and packaged {destination.name}, source={commit}, API credentials={has_credentials}")


if __name__ == "__main__":
    main()
