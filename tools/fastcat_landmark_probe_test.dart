// Fast-CAT PILOT_001 candidate landmark probe.
//
// This file is copied into the pinned hugocornellier/cat_detection example
// integration_test directory by CI and run on Linux desktop under xvfb.
// It records raw backend detections without promoting them to ground truth.
//
// v1.1 runs CatDetectionMode.faceOnly on two preregistered spatial ROIs for
// every decoded frame of the short hugging source. The ROI policy is frozen in
// experiments/pilot_001/landmark_backend_candidate.json before this full-rate
// run. Returned coordinates are translated back into full-frame pixel space.

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

Map<String, dynamic> _faceDetectionToJson(
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

Map<String, int> _pixelRoi(
  int width,
  int height,
  List<double> xyxy,
) {
  final x1 = (width * xyxy[0]).round().clamp(0, width - 1).toInt();
  final y1 = (height * xyxy[1]).round().clamp(0, height - 1).toInt();
  final x2 = (width * xyxy[2]).round().clamp(x1 + 1, width).toInt();
  final y2 = (height * xyxy[3]).round().clamp(y1 + 1, height).toInt();
  return {
    'x': x1,
    'y': y1,
    'width': x2 - x1,
    'height': y2 - y1,
  };
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Fast-CAT pinned full-rate dual-ROI 48-landmark candidate probe',
      (tester) async {
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

    const roiPolicy = <String, List<double>>{
      'cat_A_tabby_left': [0.20, 0.02, 0.52, 0.46],
      'cat_B_black_right': [0.38, 0.02, 0.70, 0.46],
    };

    final detector = CatDetector(mode: CatDetectionMode.faceOnly);
    final frameReports = <Map<String, dynamic>>[];

    await detector.initialize();
    try {
      for (final frameFile in frameFiles) {
        final name = frameFile.uri.pathSegments.last;
        final bytes = await frameFile.readAsBytes();
        final mat = cv.imdecode(bytes, cv.IMREAD_COLOR);
        expect(mat.isEmpty, isFalse, reason: 'Failed to decode $name');

        final roiReports = <Map<String, dynamic>>[];
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
              roiReports.add({
                'candidate_cat_id': entry.key,
                'roi_normalized_xyxy': entry.value,
                'roi_pixels': roi,
                'detection_count': cats.length,
                'detections': [
                  for (var i = 0; i < cats.length; i++)
                    _faceDetectionToJson(
                      cats[i],
                      i,
                      roi['x']!,
                      roi['y']!,
                    ),
                ],
              });
            } finally {
              crop.dispose();
            }
          }
        } finally {
          mat.dispose();
        }

        frameReports.add({
          'filename': name,
          'frame_index': _frameIndexFromName(name),
          'file_byte_length': bytes.length,
          'roi_channels': roiReports,
        });
      }
    } finally {
      await detector.dispose();
    }

    final report = {
      'schema': 'Fast-CAT/PILOT-001/cat-detection-roi-raw-probe/v1.1',
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
      'frames_processed': frameReports.length,
      'frames': frameReports,
      'claim_ceiling':
          'Raw fixed-ROI candidate detector output only. ROI identity and finite 48-point output are not ground truth; the backend exposes no calibrated per-landmark confidence channel and this result does not establish CatFACS action onset or latency.',
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
