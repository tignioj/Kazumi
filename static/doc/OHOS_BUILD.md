# Kazumi 2.3.9 鸿蒙测试构建

本分支基于上游正式标签 `2.3.9`（`025dcb5c2f62db881382c72f191d08b49a9feb41`），
移植 `feat-ohos` 的鸿蒙工程和平台实现。业务代码使用 2.3.9，规则 API 为 9。

## 工具链与依赖

- Flutter-OH 3.41.9+ohos-1.0.2，提交 `62357a93d653bf844f730bb1f4b7cc9e2139d14e`。
- HarmonyOS SDK 26.0.0.105、JDK 17、Python >=3.12、CMake、Ninja、Go。
- `pubspec_overrides.yaml` 从 `https://github.com/tignioj/ech_http.git` 引用鸿蒙适配，
  固定提交为 `c7c9132dfae816680df955a86f95f7b5e36704ad`，克隆本仓库后无需相邻的本地目录。
  若需联调本地修改，可临时将该 override 改为 `path: ../ech_http`。
- 鸿蒙插件及其 federated 实现均固定 Git 提交，解析结果记录在 `pubspec.lock`。
- OHOS 使用 media-kit 提交 `994465d9bfca3f39d0b41199d16e7fd93fe97881` 的
  插件式 mpv 打包。2.3.9 原本使用的新 mpv Native Assets hook 没有 OHOS 目标，
  不能直接替代这个鸿蒙插件。`ech_http` 独立使用其已适配的 Native Assets hook。

Flutter-OH 3.41 没有较新 Flutter 的 `appBuildName`、`MenuAnchor.animated`、
`ReorderableListView.onReorderItem`。本分支使用编译参数提供版本号，移除菜单动画参数，
并用旧重排回调配合索引调整，保留重排结果。全屏和系统栏控制按 2.3.9 的新接口接入 ArkTS。

## 构建

配置 Flutter-OH、`JAVA_HOME`、`HOS_SDK_HOME`、`DEVECO_NODE_HOME` 和构建工具 PATH 后：

```sh
flutter pub get
flutter test --no-pub
flutter build hap --debug --no-codesign --dart-define=KAZUMI_VERSION=2.3.9
```

HAP 位于 `ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`。
安装前需正常的华为调试签名。当前构建是 Debug；本机的 Flutter-OH Release AOT
编译器为 Intel 架构，Apple Silicon 上的 Release 构建还需要 Rosetta。

为避免覆盖用户已有安装和数据，测试工程使用包名 `com.predidit.kazumi.ohostest`，
应用名为“Kazumi 2.3.9 测试”。

## 真机集成检查

`tool/ohos_smoke.dart` 先启动完整 Kazumi，再将独立测试应用的 Bangumi 网络模式设为 ECH，
验证真实 `BangumiEchResolver`、Dio adapter、ECH 图片服务。正常入口仍为 `lib/main.dart`。

可生成一段本地测试视频，经 USB 反向端口转发验证 mpv 解码、纹理首帧和播放进度：

```sh
mkdir -p build/smoke
ffmpeg -f lavfi -i testsrc2=size=320x180:rate=24 -t 8 \
  -c:v libx264 -pix_fmt yuv420p -movflags +faststart build/smoke/player.mp4
# 在另一个终端运行，测试结束后停止：
python3 -m http.server 18765 --bind 127.0.0.1 --directory build/smoke
hdc rport tcp:18765 tcp:18765
flutter build hap --debug --no-codesign --no-pub \
  --target tool/ohos_smoke.dart \
  --dart-define=KAZUMI_VERSION=2.3.9 \
  --dart-define=OHOS_SMOKE_VIDEO=http://127.0.0.1:18765/player.mp4
```

签名安装并启动后，使用 `hdc shell hilog -x -e KAZUMI_OHOS_SMOKE` 读取检查结果。
播放检查会短暂显示静音测试画面，结束后移除画面并销毁测试播放器。
结束后用 `hdc fport ls` 查看并删除本次 USB 转发。

## 验证记录（2026-10-17）

- macOS 上 213 项 Flutter 测试通过。
- 将 `ech_http` 切换为 fork 中的固定 Git 提交后，213 项测试及 Debug HAP 构建复验通过。
- Dart 静态分析无 error/warning；仍有上游原有的 info 级 lint 提示。
- 鸿蒙 Debug HAP 构建通过，包含 arm64 `libmpv.so`、`libech_http.so` 和
  `package:ech_http/ech_http_bindings` 的 Native Assets 映射。
- MatePad mini（HarmonyOS API 26）签名安装、启动成功，首页番组与封面显示正常。
- 真实 Bangumi HTTPS 请求返回 HTTP 200、`ECH accepted: true`。
- 应用的 Bangumi Dio adapter 返回 HTTP 200，JSON 条目 ID 为 2。
- 应用的 ECH 图片服务返回 HTTP 200，成功接收 6643 字节封面数据。
- mpv 渲染测试视频首帧，播放进度超过 1 秒，总时长为 8 秒；network/playback 检查均 PASS。
- 自检后改用 `lib/main.dart` 重新构建、签名并更新同一独立测试应用，正常进入首页。
  最终安装版本不自动运行自检，不依赖本地视频服务；临时 HTTP 服务和 USB 转发已清理。
- 本地检查记录在 `build/ohos-runtime-smoke.log`，最终签名包为
  `build/Kazumi_2.3.9_OHOS_Debug_signed.hap`。
- 未运行远程 CI、Release AOT、第三方规则源逐个播放、后台续播和账号同步验证。
