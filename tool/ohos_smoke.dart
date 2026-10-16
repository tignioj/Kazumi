// A debug entry point that runs the real application and then checks its OHOS
// integrations. Normal builds continue to use lib/main.dart.
import 'dart:async';
import 'dart:convert';

import 'package:ech_http/ech_http.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:kazumi/main.dart' as app;
import 'package:kazumi/navigation.dart';
import 'package:kazumi/request/core/dio_factory.dart';
import 'package:kazumi/services/network/bangumi_ech_image_service.dart';
import 'package:kazumi/services/network/bangumi_ech_resolver.dart';
import 'package:kazumi/services/storage/storage.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';

Future<void> main() async {
  await app.main();
  // Use the ECH route in this separate test app, including the normal UI.
  await GStorage.putSetting(SettingsKeys.bangumiAcceleration, 'ech');
  DioFactory.reset();
  await _check('network', _network);
  const video = String.fromEnvironment('OHOS_SMOKE_VIDEO');
  if (video.isNotEmpty) await _check('playback', () => _playback(video));
}

Future<void> _check(String name, Future<void> Function() test) async {
  try {
    await test();
    debugPrint('KAZUMI_OHOS_SMOKE $name PASS');
  } catch (error, stack) {
    debugPrint('KAZUMI_OHOS_SMOKE $name FAIL: $error\n$stack');
  }
}

Future<void> _network() async {
  final bootstrap = EchClient();
  final client = EchClient(resolver: BangumiEchResolver.create(bootstrap));
  final images = BangumiEchImageService(proxyForUrl: (_) => null);
  try {
    final uri = Uri.https('api.bgm.tv', '/v0/subjects/2');
    final response = await client.send(http.Request('GET', uri));
    final body = await response.stream.bytesToString();
    if (response.statusCode != 200 || response.echAccepted != true) {
      throw StateError(
        'Bangumi HTTP ${response.statusCode}, ECH ${response.echAccepted}',
      );
    }
    debugPrint('KAZUMI_OHOS_SMOKE Bangumi HTTP 200, ECH accepted: true');
    final data = jsonDecode(body) as Map<String, dynamic>;
    final dio = await DioFactory.bangumiDio.get(uri.toString());
    if (dio.statusCode != 200 || dio.data['id'] != 2) {
      throw StateError('Bangumi Dio adapter response is invalid');
    }
    debugPrint('KAZUMI_OHOS_SMOKE Bangumi Dio adapter HTTP 200, JSON id=2');
    final image = await images.get(data['images']['small'] as String);
    final length = await image.content.fold<int>(
      0,
      (n, bytes) => n + bytes.length,
    );
    if (image.statusCode != 200 || length == 0) {
      throw StateError('Bangumi image HTTP ${image.statusCode}, bytes=$length');
    }
    debugPrint('KAZUMI_OHOS_SMOKE Bangumi ECH image HTTP 200, bytes=$length');
  } finally {
    images.close();
    client.close();
    bootstrap.close();
  }
}

Future<void> _playback(String url) async {
  OverlayState? overlay;
  for (var i = 0; i < 100 && overlay == null; i++) {
    overlay = rootNavigatorKey.currentState?.overlay;
    if (overlay == null) {
      await Future<void>.delayed(const Duration(milliseconds: 100));
    }
  }
  if (overlay == null) {
    throw StateError('Application navigator did not initialize');
  }
  final player = Player();
  final controller = VideoController(player);
  final entry = OverlayEntry(
    builder: (_) => Positioned(
      right: 16,
      bottom: 100,
      width: 320,
      height: 180,
      child: IgnorePointer(
        child: Video(controller: controller, controls: NoVideoControls),
      ),
    ),
  );
  overlay.insert(entry);
  final errors = <String>[];
  final subscription = player.stream.error.listen(errors.add);
  try {
    await player.setVolume(0);
    await player.open(Media(url));
    await controller.waitUntilFirstFrameRendered.timeout(
      const Duration(seconds: 30),
    );
    await player.stream.position
        .firstWhere((p) => p >= const Duration(seconds: 1))
        .timeout(const Duration(seconds: 20));
    if (errors.isNotEmpty) throw StateError(errors.join('; '));
    debugPrint(
      'KAZUMI_OHOS_SMOKE mpv first frame rendered, position > 1s, duration=${player.state.duration}',
    );
  } finally {
    entry.remove();
    await subscription.cancel();
    await player.dispose();
  }
}
