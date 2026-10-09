// OCR Apple Vision de pages de PDF. Usage : ocr_pdf <fichier.pdf> <page,page,...>   (pages à partir de 1)
// Sortie : une ligne JSON par page {"page":N,"text":"..."} sur stdout.
import Foundation
import PDFKit
import Vision
import CoreGraphics

let args = CommandLine.arguments
guard args.count >= 3, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    FileHandle.standardError.write("usage: ocr_pdf file.pdf 1,2,3\n".data(using: .utf8)!); exit(2)
}
let pages = args[2].split(separator: ",").compactMap { Int($0) }

func render(_ page: PDFPage) -> CGImage? {
    let b = page.bounds(for: .mediaBox)
    let scale = min(3.0, 2200.0 / max(b.width, b.height))
    let w = Int(b.width * scale), h = Int(b.height * scale)
    guard w > 0, h > 0, let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    return ctx.makeImage()
}

for n in pages {
    guard n >= 1, n <= doc.pageCount, let page = doc.page(at: n - 1), let img = autoreleasepool(invoking: { render(page) }) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["fr-FR", "en-US"]
    req.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    let obs = (req.results ?? []).sorted {
        abs($0.boundingBox.midY - $1.boundingBox.midY) > 0.012 ? $0.boundingBox.midY > $1.boundingBox.midY : $0.boundingBox.minX < $1.boundingBox.minX
    }
    let text = obs.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
    let data = try! JSONSerialization.data(withJSONObject: ["page": n, "text": text])
    print(String(data: data, encoding: .utf8)!)
}
