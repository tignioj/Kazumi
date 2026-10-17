# Kazumi 2.3.9 鸿蒙测试构建

本分支基于上游正式标签 `2.3.9`（`025dcb5c2f62db881382c72f191d08b49a9feb41`），
移植 `feat-ohos` 的鸿蒙工程和平台实现。业务代码使用 2.3.9，规则 API 为 9。

## 工具链与依赖

- Flutter-OH 3.41.9+ohos-1.0.2，提交 `62357a93d653bf844f730bb1f4b7cc9e2139d14e`。
- HarmonyOS SDK 26.0.0.105、JDK 17、Python >=3.12、CMake、Ninja。
- `pubspec_overrides.yaml` 从上游 `https://github.com/ech-research/ech_http.git` 引用鸿蒙适配，
  固定提交为 `2c58622b3596593b1c6818ddca7cdd0a0631aa15`（上游 PR #1），
  克隆本仓库后无需相邻的本地目录。构建钩子下载组织仓库
  `ech-research/libechhttp-ohos-build` 的 `v0.1.0` SDK 并校验 SHA-256，
  本地仅编译 C++ 桥接代码。
  若需联调本地修改，可临时将该 override 改为 `path: ../ech_http`。
- 鸿蒙插件及其 federated 实现均固定 Git 提交，解析结果记录在 `pubspec.lock`。
- `pubspec.yaml` 的 `media_kit` 与 `media_kit_video` 均引用
  上游 `https://github.com/Predidit/media-kit.git`，固定提交为
  `9c31fe57c5c4492835dcd6fea968920f3b01bcb1`（上游 PR #43），
  克隆后无需本地 media-kit 目录。
  构建钩子识别 Flutter-OH 以 Linux 上报的 OHOS 编译器，选取鸿蒙版 `libmpv.so`，
  用 OHOS triple/sysroot 编译 `libmedia_kit_event_loop.so`，并打包 SDK 的 C++ 运行库。
  不再固定旧版 `994465d9`，也不再依赖任何 `media_kit_libs_*` 插件。
- hooks/code_assets/native_toolchain_c 版本范围兼容 Flutter-OH 的 `meta 1.17`，
  同时保留新版协议的支持。播放器继续使用新版 C 事件循环和确定性销毁流程。
  当前鸿蒙预编译包支持 arm64；其他鸿蒙架构和模拟器不在支持范围。

Flutter-OH 3.41 没有较新 Flutter 的 `appBuildName`、`MenuAnchor.animated`、
`ReorderableListView.onReorderItem`。本分支使用编译参数提供版本号，移除菜单动画参数，
并用旧重排回调配合索引调整，保留重排结果。全屏和系统栏控制按 2.3.9 的新接口接入 ArkTS。

## 构建

配置 Flutter-OH、`JAVA_HOME`、`HOS_SDK_HOME`、`DEVECO_NODE_HOME` 和构建工具 PATH 后：

```sh
flutter pub get
dart analyze lib tool test
flutter test --no-pub
flutter build hap --debug --no-codesign --dart-define=KAZUMI_VERSION=2.3.9
```

HAP 位于 `ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`。
安装前需正常的华为调试签名。默认示例为 Debug，Release 使用 `--release`。
本机 Flutter-OH 的 Release AOT 编译器为 Intel 架构；已安装 Rosetta，
Apple Silicon 上现在可以完成 Release AOT。

为避免覆盖用户已有安装和数据，测试工程使用包名 `com.predidit.kazumi.ohostest`，
应用名为“Kazumi 2.3.9 测试”。

## GitHub Actions 自动构建与发布

`.github/workflows/ohos-release.yaml` 使用 GitHub 托管的 Ubuntu 24.04 runner，
安装固定版本的 HarmonyOS CLI 26.0.0.821 和上述固定提交的 Flutter-OH。
不需要自托管 runner 或本地路径依赖。首次运行会下载工具链、ECH 预编译 SDK 并编译桥接代码，
后续运行复用 SDK 与 Flutter 缓存。

从包含鸿蒙适配的分支推送 `<pubspec 版本>-ohos.<序号>` 标签即可自动发布测试版：

```sh
git tag 2.3.9-ohos.1
git push origin 2.3.9-ohos.1
```

每次使用新序号。工作流先检查标签与 `pubspec.yaml` 的版本一致，再按 lockfile
解析依赖、执行 Dart 静态分析与 Flutter 测试、构建正常入口的 arm64 Release HAP。
`tool/package_ohos_release.py` 校验包名、版本、非 Debug AOT、ELF 架构及
ECH/media-kit Native Assets 映射，最后发布 GitHub prerelease，包含：

- `Kazumi_<标签>_HarmonyOS_arm64_unsigned.hap`
- `SHA256SUMS`
- `build-info.json`（源码提交、Flutter 提交、SDK、版本和 SHA-256）

这些标签不会触发原来的 Android/Windows/iOS/macOS/Linux Release 工作流。
工作流也声明了手动运行入口：指定 `tag`，默认只生成 Actions artifact；
开启 `publish` 才发布。GitHub 的手动运行入口要求默认分支也包含此工作流。

公开下载的 HAP **未签名**，下载者需要使用自己的华为设备证书/Profile 签名后侧载。
CI 不上传本机私钥、证书、设备 Profile，也不使用本机绑定设备的签名包。
需要 API 凭据的功能可按原工作流使用仓库的 `DANDANAPI_APPID`、`DANDANAPI_KEY`、
`KAZUMI_APPID`、`KAZUMI_KEY` Secrets；未配置时以空值构建。

## CLI 签名与安装

本机小白调试助手包含可独立调用的 `assets/macos/signer`。首次使用助手为
对应包名和设备生成证书/Profile 后，可以直接复用本地材料，无需 GUI 选择文件。
`tool/sign_ohos.py` 从助手的 `signConfig.json` 读取现有配置，按包名选择 Profile，
完成 HAP 和原生代码签名后执行 `verify-app`；不在源码或日志中记录密钥密码。
可用 `--config`、`--profile`、`--signer` 指定其他路径。

```sh
mkdir -p /tmp/kz
cp build/ohos/hap/entry-default-unsigned.hap /tmp/kz/kazumi.hap
python3 tool/sign_ohos.py /tmp/kz/kazumi.hap /tmp/kz/kazumi-signed.hap
hdc install -r /tmp/kz/kazumi-signed.hap
hdc shell aa start -a EntryAbility -b com.predidit.kazumi.ohostest
```

安装包使用短路径；正常入口包是 `/tmp/kz/kazumi-signed.hap`。
启动前需要解锁真机屏幕。签名仅复用已有本地证书和设备 Profile，不申请新凭据。

## 真机集成检查

`tool/ohos_smoke.dart` 先启动完整 Kazumi，再将独立测试应用的 Bangumi 网络模式设为 ECH，
验证真实 `BangumiEchResolver`、Dio adapter、ECH 图片服务。正常入口仍为 `lib/main.dart`。

可生成一段本地测试视频，经 USB 反向端口转发验证 mpv 解码、视频纹理、播放进度及生命周期：

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
播放检查在软解/自动硬解与同步/异步模式的四种组合下各运行 3 次，
总计 12 次。每次确认纹理 ID、视频尺寸和播放进度，检查并发销毁复用同一个
Future、重复销毁正常完成、销毁后 mpv 句柄归零；另做 3 次初始化期间直接销毁。
测试画面静音显示，结束后移除并销毁播放器。
结束后用 `hdc fport ls` 查看并删除本次 USB 转发。

## 新版 Native Assets Debug 验证记录（2026-10-17）

- media-kit 的 19 项 hook/核心生命周期测试通过；补充 C++ 运行库打包后，
  12 项 hook 测试再次通过，hook 静态分析无问题。
- Kazumi 的 213 项 Flutter 测试通过；`dart analyze lib tool test` 无 error/warning，
  有 27 条现有 info 级 lint。精简 Flutter-OH SDK 的 `flutter analyze` 会因缺少
  `dev/` 目录退出，使用内置 Dart analyzer 验证。
- 鸿蒙 Debug 自检包和正常入口 HAP 均构建、签名、验签通过，包含 arm64
  `libmpv.so`、`libmedia_kit_event_loop.so`、`libc++_shared.so`、`libech_http.so`。
  `NativeAssetsManifest.json` 的 `ohos_arm64` 包含 media-kit 的 libmpv、
  C 事件循环及 C++ 运行库映射。
- MatePad mini（HarmonyOS API 26）通过 CLI 覆盖安装独立测试应用成功。
  真机日志显示 ECH 请求、Bangumi Dio adapter、封面请求均返回 HTTP 200，
  `ECH accepted: true`，接收 6643 字节封面数据。
- 12 轮视频播放/销毁全部通过：软解为 `hwdec=no`，硬解为 `hwdec=ohcodec`；
  播放进度超过 1 秒，测试视频时长 8 秒；每轮并发及重复销毁均完成，
  mpv 句柄归零，首轮销毁耗时 78–126 ms。另 3 次初始化期间直接销毁通过。
  为确认实际纹理画面重复运行一轮，累计 24 次播放/销毁和 6 次提前销毁均通过，
  两轮销毁耗时范围为 69–136 ms。
- 真机截图确认彩色动态测试画面经 Flutter 纹理实际显示。
  `build/ohos-native-assets-screen.jpeg` 保存播放截图。
- 日志记录在 `build/ohos-native-assets-smoke.log`；包含
  `lifecycle 12 render/dispose cycles, 3 early disposals PASS` 和 `playback PASS`。
  第二轮记录为 `build/ohos-native-assets-visual-smoke.log`。
  原始 E/F 日志中仍有 Flutter-OH 图片方向和纹理初始空 buffer 等平台日志，
  本次未出现 Dart 未处理异常、进程崩溃或销毁超时。
- 自检后重新安装正常 `lib/main.dart` 入口包，保留相同的新版 media-kit 依赖。
  最终包已正常进入首页，封面显示正常；未产生自检日志，也不依赖本地视频服务。
  临时 HTTP 服务和 USB 反向转发已清理。
- 最终签名包为 `/tmp/kz/kazumi-signed.hap`，工作区副本为
  `build/Kazumi_2.3.9_OHOS_NativeAssets_Debug_signed.hap`。
- 本节为 Debug 验证；Release AOT 结果见下节。未运行远程 CI、第三方规则源逐个播放、
  后台续播和账号同步验证。


## Release AOT 构建与验证（2026-10-17）

Flutter-OH 当前的 macOS AOT 工具是 x86_64；本机安装 Rosetta 后编译成功。
以下命令生成正常入口包，仍使用独立测试包名与现有设备 Profile：

```sh
flutter build hap --release --no-codesign --no-pub \
  --dart-define=KAZUMI_VERSION=2.3.9
cp build/ohos/hap/entry-default-unsigned.hap /tmp/kz/release.hap
python3 tool/sign_ohos.py /tmp/kz/release.hap /tmp/kz/release-signed.hap
hdc install -r /tmp/kz/release-signed.hap
hdc shell aa start -a EntryAbility -b com.predidit.kazumi.ohostest
```

Release 自检使用相同命令加上 `--target tool/ohos_smoke.dart` 和
`--dart-define=OHOS_SMOKE_VIDEO=http://127.0.0.1:18765/player.mp4`，
按前述方法启用临时 HTTP 服务与 USB 反向转发。自检入口记录
`KAZUMI_OHOS_SMOKE mode=release`，可区分 AOT 与 Debug。


- 自检与正常入口 Release HAP 均构建、CLI 签名及验签成功。
  正常签名包为 83,375,167 字节（约 79.5 MiB）。
- 两个 HAP 均为 `debug=false`，包含 arm64 AOT `libapp.so`，不包含
  `kernel_blob.bin`。Native Assets 映射保留 libmpv、C 事件循环和 C++ 运行库。
- MatePad mini 上两轮自检均记录 `mode=release`、`network PASS`、
  `playback PASS`。每轮完成 12 次渲染/销毁和 3 次初始化期间销毁，
  累计 24 次播放/销毁、6 次提前销毁全部通过。
- 软解 `hwdec=no`、硬解 `hwdec=ohcodec`；同步/异步模式均通过。
  每轮并发销毁共用 Future、重复销毁正常返回、mpv 句柄归零，
  两轮销毁耗时 76–160 ms。未观察到进程崩溃、未处理 Dart 异常或销毁超时。
- `build/ohos-release-playback.jpeg` 记录 Release 硬解的实际测试画面。
- `build/ohos-release-smoke-first.log`、`build/ohos-release-smoke.log`
  保存两轮检查结果；对应完整日志为 `build/ohos-release-runtime-first.log`、
  `build/ohos-release-runtime.log`。
- 检查完成后已换回正常 `lib/main.dart` 入口的 Release 包。
  正常包为 `/tmp/kz/release-signed.hap`，工作区副本为
  `build/Kazumi_2.3.9_OHOS_NativeAssets_Release_signed.hap`。
  正常包启动后首页与封面显示正常，没有自检日志；临时 HTTP 服务和 USB 转发已清理。


固定 Git 依赖后的验证：`flutter pub get` 成功，两个 media-kit 包均来自
Pub 的 Git 缓存，并解析为提交 `049278dee62e18bb008fabc293fbcbbaa2739d7c`。
没有本地路径依赖；213 项 Flutter 测试通过，静态分析无 error/warning，
正常入口 Release HAP 再次构建成功。

## 切回上游依赖后的 Release 回归（2026-10-17）

- `media_kit` / `media_kit_video` 固定到上游 `Predidit/media-kit` 的
  `9c31fe57c5c4492835dcd6fea968920f3b01bcb1`，`ech_http` 固定到
  `ech-research/ech_http` 的 `2c58622b3596593b1c6818ddca7cdd0a0631aa15`。
  `flutter pub get` 成功，lockfile 仅变更这三个包的来源及提交，其他包版本保持不变。
- `dart analyze lib tool test` 无 error/warning，保留 27 条现有 info 级 lint；
  213 项 Flutter 测试全部通过。
- 正常入口与自检入口的 arm64 Release AOT HAP 均构建、签名、验签通过。
  `tool/package_ohos_release.py` 的 `verify_hap` 检查确认 `debug=false`、
  无 Debug kernel，AOT、ECH、mpv、事件循环、C++ 运行库及 Native Assets 映射完整。
- ECH hook 从组织仓库下载 `libechhttp-ohos-build/v0.1.0` 的 arm64 SDK，
  归档 SHA-256 为 `986aaea773733301b66a1f94a1986f71b1a31f54e89c4909fcc2fd4b0ea982fc`，
  本地重新核验一致。CMake 的 `EH_DEPS_ROOT` 指向该预编译 SDK，
  源码指向新上游提交，仅编译 C++ 桥接代码。
- MatePad mini（MLR-AL10，API 26）上，正常入口首页与封面显示正常。
  使用已有 mgnacg 规则播放《游戏人生》第 5 话，确认实际视频画面与播放进度推进。
  截图为 `build/upstream-release-online.png` 和
  `build/upstream-release-online-progress.png`。
- Release 自检日志明确记录 `mode=release`，Bangumi ECH 握手被接受，
  直接请求、Dio adapter、封面请求均 HTTP 200，封面接收 6643 字节。
  软解 `hwdec=no` / 硬解 `hwdec=ohcodec` 与同步/异步模式的四种组合
  各播放、销毁 3 次，合计 12 次；每次渲染首帧、播放进度达到 1 秒，
  并发销毁复用 Future、重复销毁正常完成、mpv 句柄归零，销毁耗时 96–172 ms。
  另 3 次初始化期间提前销毁通过。未观察到 Dart 未处理异常、进程崩溃或销毁超时。
- 本轮日志为 `build/upstream-analyze.log`、`build/upstream-tests.log`、
  `build/upstream-release-build.log`、`build/upstream-release-smoke-build.log`、
  `build/upstream-release-smoke.log` 与 `build/upstream-release-smoke-runtime.log`；
  `build/upstream-release-smoke.png` 确认测试视频纹理实际显示。
  仍可见 Flutter-OH 图片方向等平台 E/F 日志。
- 自检后重新构建并安装正常 `lib/main.dart` 入口的 Release 包，确认首页与封面
  正常、没有自检日志。已清理本次 HTTP 服务与 USB 反向转发。
  正常未签名包为 `build/Kazumi_2.3.9_OHOS_Upstream_Release_unsigned.hap`，
  本机设备签名包为 `build/Kazumi_2.3.9_OHOS_Upstream_Release_signed.hap`。
  `build/upstream-release-final-home.png` 保存最终首页截图。
- 验证范围为上述 arm64/API 26 真机与一条实际规则；未逐个验证其他规则、
  低 API、其他设备、后台续播、下载和账号同步，未运行远程 CI。
