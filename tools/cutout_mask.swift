import Foundation
import Vision
import CoreImage
import AppKit

// usage: mask IN.jpg OUT.pgm  -> one byte per pixel: 0 = background, 1..n = the people / objects Vision found in the foreground
let args = CommandLine.arguments
guard args.count == 3, let img = NSImage(contentsOfFile: args[1]), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("cannot read image"); exit(1) }
let req = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([req])
guard let res = req.results?.first else { print("no foreground found"); exit(2) }
let buf = res.instanceMask
CVPixelBufferLockBaseAddress(buf, .readOnly)
let w = CVPixelBufferGetWidth(buf), h = CVPixelBufferGetHeight(buf), bpr = CVPixelBufferGetBytesPerRow(buf)
let base = CVPixelBufferGetBaseAddress(buf)!.assumingMemoryBound(to: UInt8.self)
var data = Data("P5\n\(w) \(h)\n255\n".utf8)
for y in 0..<h { data.append(Data(bytes: base + y * bpr, count: w)) }
CVPixelBufferUnlockBaseAddress(buf, .readOnly)
try data.write(to: URL(fileURLWithPath: args[2]))
print("instances: \(res.allInstances.sorted()) mask \(w)x\(h)")
