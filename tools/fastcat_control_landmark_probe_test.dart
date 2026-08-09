// Fast-CAT PILOT_001 non-affiliative control landmark preflight.
//
// Runs the pinned cat_detection faceOnly backend on two preregistered spatial
// ROIs for the deterministic sampled control frames. The result is candidate
// geometry only and is not a CatFACS/action/latency measurement.

import 'dart:convert';
import 'dart:io';

import 'package:cat_detection/cat_detection.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:opencv_dart/opencv_dart.dart' as cv;

Map<String, dynamic> _bboxGlobal(BoundingBox b, int offsetX, int offsetY) => {
      'left': b.left + offsetX,
      'top': b.top + offsetY,
      'right': b.right + offsetX,
      'bottom': b.bottom + offsetY,
    };

Map<String, dynamic> _faceToJson(
  Cat cat,
  int detectionIndex,
  int offsetX,
  int offsetY,
) {
  final face = cat.face;
  return {
    'detection_index': detectionIndex,
    'backend_score': cat.score,
    'face': face == null
        ? null
        : {
            'bbox': _bboxGlobal(face.boundingBox, offsetX, offsetY),
            'landmark_count': face.landmarks.length,
            'landmarks': [
              for (final lm in face.landmarks)
                {
                  'index': lm.type.index,
                  'type': lm.type.name,
                  'x': lm.x + offsetX,
                  'y': lm.y + offsetY,
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

Map<String, int> _pixelRoi(int width, int height, List<double> xyxy) {
  final x1 = (width * xyxy[0]).round().clamp(0, width - 1).toInt();
  final y1 = (height * xyxy[1]).round().clamp(0, height - 1).toInt();
  final x2 = (width * xyxy[2]).round().clamp(x1 + 1, width).toInt();
  final y2 = (height * xyxy[3]).round().clamp(y1 + 1, height).toInt();
  return {'x': x1, 'y': y1, 'width': x2 - x1, 'height': y2 - y1};
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Fast-CAT sampled conflict-control dual-ROI landmark preflight',
      (tester) async {
    final inputDirValue = Platform.environment['FASTCAT_INPUT_DIR'];
    final outPathValue = Platform.environment['FASTCAT_OUT'];
    final backendCommit = Platform.environment['FASTCAT_BACKEND_COMMIT'];
    final sourceId = Platform.environment['FASTCAT_SOURCE_ID'];

    expect(inputDirValue, isNotNull);
    expect(outPathValue, isNotNull);
    expect(backendCommit, isNotNull);
    expect(sourceId, isNotNull);

    final frameFiles = Directory(inputDirValue!)
        .listSync()
        .whereType<File>()
        .where((f) => f.path.toLowerCase().endsWith('.png'))
        .toList()
      ..sort((a, b) => a.path.compareTo(b.path));
    expect(frameFiles.length, 83, reason: 'Frozen sampled control set changed');

    const roiPolicy = <String, List<double>>{
      'cat_C_brown_left': [0.25, 0.10, 0.54, 0.55],
      'cat_D_gray_right': [0.49, 0.08, 0.82, 0.55],
    };

    final detector = CatDetector(mode: CatDetectionMode.faceOnly);
    final reports = <Map<String, dynamic>>[];
    await detector.initialize();
    try {
      for (final frameFile in frameFiles) {
        final name = frameFile.uri.pathSegments.last;
        final bytes = await frameFile.readAsBytes();
        final mat = cv.imdecode(bytes, cv.IMREAD_COLOR);
        expect(mat.isEmpty, isFalse, reason: 'Failed to decode $name');
        final channels = <Map<String, dynamic>>[];
        try {
          for (final entry in roiPolicy.entries) {
            final roi = _pixelRoi(mat.cols, mat.rows, entry.value);
            final crop = mat.region(cv.Rect(
              roi['x']!,
              roi['y']!,
              roi['width']!,
              roi['height']!,
            ));
            try {
              final cats = await detector.detectFromMat(
                crop,
                imageWidth: crop.cols,
                imageHeight: crop.rows,
              );
              channels.add({
                'candidate_cat_id': entry.key,
                'roi_normalized_xyxy': entry.value,
                'roi_pixels': roi,
                'detection_count': cats.length,
                'detections': [
                  for (var i = 0; i < cats.length; i++)
                    _faceToJson(cats[i], i, roi['x']!, roi['y']!),
                ],
              });
            } finally {
              crop.dispose();
            }
          }
        } finally {
          mat.dispose();
        }
        reports.add({
          'filename': name,
          'frame_index': _frameIndexFromName(name),
          'roi_channels': channels,
        });
      }
    } finally {
      await detector.dispose();
    }

    final report = {
      'schema': 'Fast-CAT/PILOT-001/control-roi-raw-probe/v1.0',
      'source_id': sourceId,
      'backend': {
        'repository': 'hugocornellier/cat_detection',
        'commit': backendCommit,
        'mode': 'faceOnly-dual-fixed-roi',
        'model_version': CatDetector.modelVersionFor(
          mode: CatDetectionMode.faceOnly,
        ),
      },
      'roi_policy_normalized_xyxy': roiPolicy,
      'frames_processed': reports.length,
      'frames': reports,
      'claim_ceiling':
          'Sampled control candidate geometry only; no landmark-accuracy, CatFACS, action-onset, mimicry or latency claim.',
    };
    final out = File(outPathValue!);
    await out.parent.create(recursive: true);
    await out.writeAsString(
      const JsonEncoder.withIndent('  ').convert(report) + '\n',
      flush: true,
    );
  }, timeout: const Timeout(Duration(minutes: 45)));
}
