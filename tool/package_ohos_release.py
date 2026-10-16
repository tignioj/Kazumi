#!/usr/bin/env python3
"""Validate a Release HAP and prepare unsigned, device-independent release assets."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parent.parent
FLUTTER_REVISION = "62357a93d653bf844f730bb1f4b7cc9e2139d14e"
BUNDLE_NAME = "com.predidit.kazumi.ohostest"


def version():
    match = re.search(r"^version: ([0-9.]+)\+([0-9]+)$", (ROOT / "pubspec.yaml").read_text(), re.M)
    if not match:
        raise ValueError("Cannot read application version from pubspec.yaml")
    return match.group(1), int(match.group(2))


def validate_tag(tag):
    name, _ = version()
    if not re.fullmatch(re.escape(name) + r"-ohos\.[1-9][0-9]*", tag):
        raise ValueError(f"Release tag must be {name}-ohos.<positive integer>")


def verify_hap(path):
    name, code = version()
    libraries = ("libapp.so", "libflutter.so", "libmpv.so",
                 "libmedia_kit_event_loop.so", "libc++_shared.so", "libech_http.so")
    with zipfile.ZipFile(path) as hap:
        corrupt = hap.testzip()
        if corrupt:
            raise ValueError(f"Corrupt HAP member: {corrupt}")
        module = json.loads(hap.read("module.json"))
        app = module["app"]
        expected = {"bundleName": BUNDLE_NAME, "versionName": name, "versionCode": code}
        for key, value in expected.items():
            if app.get(key) != value:
                raise ValueError(f"Unexpected {key}: {app.get(key)!r}, expected {value!r}")
        if app.get("debug") is not False:
            raise ValueError("Expected a Release HAP with debug=false")
        if any(entry.endswith("kernel_blob.bin") for entry in hap.namelist()):
            raise ValueError("Release HAP contains a Debug kernel")
        for library in libraries:
            header = hap.read(f"libs/arm64-v8a/{library}")[:20]
            if header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != 183:
                raise ValueError(f"{library} is not a little-endian arm64 ELF library")
        manifest = json.loads(hap.read("resources/rawfile/flutter_assets/NativeAssetsManifest.json"))
        assets = manifest["native-assets"]["ohos_arm64"]
        for asset, library in {
            "package:ech_http/ech_http_bindings": "libech_http.so",
            "package:media_kit/libmpv": "libmpv.so",
            "package:media_kit/src/player/native/core/native_event_loop_bindings.dart": "libmedia_kit_event_loop.so",
            "package:media_kit/native/libc++_shared.so": "libc++_shared.so",
        }.items():
            if assets.get(asset) != ["absolute", library]:
                raise ValueError(f"Missing or incorrect native asset: {asset}")
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hap", type=Path, nargs="?")
    parser.add_argument("--tag")
    parser.add_argument("--check-tag")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/ohos-release")
    args = parser.parse_args()
    if args.check_tag:
        validate_tag(args.check_tag)
        print(f"Valid release tag: {args.check_tag}")
        return
    if not args.hap or not args.tag:
        parser.error("hap and --tag are required when packaging")
    validate_tag(args.tag)
    app = verify_hap(args.hap)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"Kazumi_{args.tag}_HarmonyOS_arm64_unsigned.hap"
    shutil.copyfile(args.hap, destination)
    with destination.open("rb") as archive:
        digest = hashlib.file_digest(archive, "sha256").hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {destination.name}\n")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    info = {
        "tag": args.tag, "commit": commit, "flutter_revision": FLUTTER_REVISION,
        "bundle_name": app["bundleName"], "version": app["versionName"],
        "version_code": app["versionCode"], "min_api_version": app["minAPIVersion"],
        "compile_sdk_version": app["compileSdkVersion"],
        "architecture": "arm64", "build_mode": "release", "signed": False,
        "file": destination.name, "bytes": destination.stat().st_size, "sha256": digest,
    }
    (output / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    notes = f"""Kazumi {args.tag} 鸿蒙测试版，基于 Kazumi {app['versionName']}。

- arm64 Release AOT 构建；包含新版 media-kit Native Assets 和 ECH 网络支持。
- 独立测试包名 `{BUNDLE_NAME}`，应用名“Kazumi 2.3.9 测试”。
- 最低 HarmonyOS API {app['minAPIVersion'] % 1000}，面向真机 arm64，不支持 x64 模拟器。
- **HAP 未签名**：请使用 DevEco Studio 或小白调试助手为自己的设备签名后侧载安装。
  本 Release 不包含开发者私钥、证书或绑定其他设备的 Profile。
- 构建时执行静态分析、Flutter 测试，以及 HAP 的 AOT、架构和 Native Assets 完整性检查。
  远程 CI 不包含签名和真机播放测试；此前本地版本已完成 ECH 和视频播放/销毁检查。
- 可使用 `SHA256SUMS` 校验下载文件；`build-info.json` 记录源码提交与构建信息。

源码提交：`{commit}`
"""
    (output / "RELEASE_NOTES.md").write_text(notes)
    print(f"Verified and packaged {destination.name} ({info['bytes']} bytes, SHA-256 {digest})")


if __name__ == "__main__":
    main()
