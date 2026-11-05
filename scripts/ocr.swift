import Foundation
import Vision
import ImageIO

do {
    guard CommandLine.arguments.count == 2 else { throw NSError(domain: "ocr", code: 1) }
    let url = URL(fileURLWithPath: CommandLine.arguments[1])
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil), let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { throw NSError(domain: "image", code: 2) }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.usesLanguageCorrection = false
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])
    let rows: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return ["text": candidate.string, "confidence": candidate.confidence, "bbox": [box.minX, 1 - box.maxY, box.maxX, 1 - box.minY]]
    }
    let output: [String: Any] = ["engine": "Apple Vision", "revision": request.revision, "languages": request.recognitionLanguages, "width": image.width, "height": image.height, "blocks": rows]
    let data = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
    FileHandle.standardOutput.write(data)
} catch {
    FileHandle.standardError.write(Data("OCR failed: \(error.localizedDescription)".utf8))
    exit(1)
}
