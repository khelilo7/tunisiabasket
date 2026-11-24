// The sound of the apps that play the game (the browser showing Diwan Sport), for tools/live_scorer.py: 16 kHz mono float32 samples on stdout, as they come.
// macOS 13+ (ScreenCaptureKit), with the same Screen Recording permission as the Live reader. Nothing is written to disk.
//
//   audiocap "Firefox" ["Safari" ...]       app names (or bundle ids) to listen to; part of the name is enough
//
// macOS gives the sound of a whole app, not of one window: two games in two windows of the same browser would be mixed (use two browsers).
import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit

func fail(_ msg: String, _ code: Int32 = 1) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(code)
}

final class Sink: NSObject, SCStreamOutput, SCStreamDelegate {
    let out = FileHandle.standardOutput
    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio, sb.isValid, let block = CMSampleBufferGetDataBuffer(sb) else { return }
        let length = CMBlockBufferGetDataLength(block)
        guard length > 0 else { return }
        var data = Data(count: length)
        let status = data.withUnsafeMutableBytes { CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: length, destination: $0.baseAddress!) }
        if status == kCMBlockBufferNoErr { out.write(data) }
    }
    func stream(_ stream: SCStream, didStopWithError error: Error) { fail("audio capture stopped: \(error.localizedDescription)", 2) }
}

let wanted = CommandLine.arguments.dropFirst().map { $0.lowercased() }
if wanted.isEmpty { fail("usage: audiocap APP [APP...]") }
let sink = Sink()
var stream: SCStream?

SCShareableContent.getExcludingDesktopWindows(false, onScreenWindowsOnly: false) { content, error in
    guard let content = content else {
        fail("screen capture refused: give the Screen Recording permission to the app running this (System Settings > Privacy & Security). \(error?.localizedDescription ?? "")", 3)
    }
    let apps = content.applications.filter { app in
        wanted.contains { w in app.applicationName.lowercased().contains(w) || app.bundleIdentifier.lowercased() == w }
    }
    guard !apps.isEmpty else { fail("no running app matches \(wanted)", 4) }
    guard let display = content.displays.first else { fail("no display", 5) }
    let cfg = SCStreamConfiguration()
    cfg.capturesAudio = true
    cfg.sampleRate = 16000
    cfg.channelCount = 1
    cfg.excludesCurrentProcessAudio = true
    cfg.width = 2                                   // the picture is not used: as small and rare as possible
    cfg.height = 2
    cfg.minimumFrameInterval = CMTime(value: 1, timescale: 1)
    cfg.queueDepth = 3
    let filter = SCContentFilter(display: display, including: apps, exceptingWindows: [])
    let s = SCStream(filter: filter, configuration: cfg, delegate: sink)
    do {
        try s.addStreamOutput(sink, type: .audio, sampleHandlerQueue: DispatchQueue(label: "audio"))
    } catch { fail("audio output: \(error.localizedDescription)", 6) }
    s.startCapture { error in
        if let error = error { fail("audio capture refused: \(error.localizedDescription)", 7) }
        FileHandle.standardError.write("listening to \(apps.map { $0.applicationName }.joined(separator: ", "))\n".data(using: .utf8)!)
    }
    stream = s
}
signal(SIGPIPE) { _ in exit(0) }                    // the reader stopped reading: stop too
RunLoop.main.run()
