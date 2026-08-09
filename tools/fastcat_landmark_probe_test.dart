// Fast-CAT PILOT_001 candidate landmark probe.
//
// This file is copied into the pinned hugocornellier/cat_detection example
// integration_test directory by CI and run on Linux desktop under xvfb.
// It records raw backend detections without promoting them to ground truth.

import 'dart:convert';
import 'dart:io';

import 'package:cat_detection/cat_detection.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

Map<String, dynamic> _bbox(BoundingBox b) => {
      'left': b.left,
      'top': b.top,
      'right': b.right,
      'bottom': b.bottom,
    };

Map<String, dynamic> _catToJson(Cat cat, int detectionIndex) {
  final face = cat.face;
  return {
    'detection_index': detectionIndex,
    'body_score': cat.score,
    'body_bbox': _bbox(cat.boundingBox),
    'species': cat.species?.toString(),
    'breed': cat.breed?.toString(),
    'species_confidence': cat.speciesConfidence,
    'face': face == null
        ? null
        : {
            'bbox': _bbox(face.boundingBox),
            'landmark_count': face.landmarks.length,
            'landmarks': [
              for (final lm in face.landmarks)
                {
                  'index': lm.type.index,
                  'type': lm.type.name,
                  'x': lm.x,
                  'y': lm.y,
                }
            ],
          },
  };
}

int _frameIndexFromName(String name) {
  final match = RegExp(r'^f(\d{6})_').firstMatch(name);
  if (match == null) {
    throw FormatException('Unexpected Fast-CAT frame filename: $name');
  }
  return int.parse(match.group(1)!);
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Fast-CAT pinned 48-landmark candidate probe', (tester) async {
    final inputDirValue = Platform.environment['FASTCAT_INPUT_DIR'];
    final outPathValue = Platform.environment['FASTCAT_OUT'];
    final backendCommit = Platform.environment['FASTCAT_BACKEND_COMMIT'];
    final sourceId = Platform.environment['FASTCAT_SOURCE_ID'];

    expect(inputDirValue, isNotNull, reason: 'FASTCAT_INPUT_DIR missing');
    expect(outPathValue, isNotNull, reason: 'FASTCAT_OUT missing');
    expect(backendCommit, isNotNull, reason: 'FASTCAT_BACKEND_COMMIT missing');
    expect(sourceId, isNotNull, reason: 'FASTCAT_SOURCE_ID missing');

    final inputDir = Directory(inputDirValue!);
    final frameFiles = inputDir
        .listSync()
        .whereType<File>()
        .where((f) => f.path.toLowerCase().endsWith('.png'))
        .toList()
      ..sort((a, b) => a.path.compareTo(b.path));

    expect(frameFiles, isNotEmpty, reason: 'No Fast-CAT PNG frames found');

    final detector = CatDetector(
      mode: CatDetectionMode.full,
      detThreshold: 0.5,
      cropMargin: 0.20,
    );

    final frameReports = <Map<String, dynamic>>[];
    await detector.initialize();
    try {
      for (final frameFile in frameFiles) {
        final name = frameFile.uri.pathSegments.last;
        final bytes = await frameFile.readAsBytes();
        final cats = await detector.detect(bytes);
        frameReports.add({
          'filename': name,
          'frame_index': _frameIndexFromName(name),
          'file_byte_length': bytes.length,
          'detection_count': cats.length,
          'detections': [
            for (var i = 0; i < cats.length; i++) _catToJson(cats[i], i),
          ],
        });
      }
    } finally {
      await detector.dispose();
    }

    final report = {
      'schema': 'Fast-CAT/PILOT-001/cat-detection-raw-probe/v1.0',
      'source_id': sourceId,
      'backend': {
        'repository': 'hugocornellier/cat_detection',
        'commit': backendCommit,
        'mode': 'full',
        'det_threshold': 0.5,
        'crop_margin': 0.20,
        'model_version': CatDetector.modelVersionFor(
          mode: CatDetectionMode.full,
        ),
      },
      'frames_processed': frameReports.length,
      'frames': frameReports,
      'claim_ceiling':
          'Raw candidate detector output only. Body score is not landmark confidence; finite 48-point output is not ground truth and does not establish CatFACS action onset or latency.',
    };

    final outFile = File(outPathValue!);
    await outFile.parent.create(recursive: true);
    await outFile.writeAsString(
      const JsonEncoder.withIndent('  ').convert(report) + '\n',
      flush: true,
    );

    expect(frameReports, isNotEmpty);
  }, timeout: const Timeout(Duration(minutes: 30)));
}
