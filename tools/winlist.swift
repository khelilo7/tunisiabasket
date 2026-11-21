// The windows on the screen, one per line: id<TAB>app<TAB>width<TAB>height<TAB>title. Used by live_reader.py --window to find the Diwan Sport windows and capture
// each one directly (screencapture -l), even when other windows cover it. Titles are only given to a process with the Screen Recording permission.
import CoreGraphics
import Foundation

let opts: CGWindowListOption = [.optionAll, .excludeDesktopElements]
let list = (CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]]) ?? []
for w in list {
    guard (w[kCGWindowLayer as String] as? Int) == 0 else { continue }
    let id = w[kCGWindowNumber as String] as? Int ?? 0
    let app = w[kCGWindowOwnerName as String] as? String ?? ""
    let title = (w[kCGWindowName as String] as? String ?? "").replacingOccurrences(of: "\t", with: " ")
    let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
    let width = b["Width"] as? Int ?? 0, height = b["Height"] as? Int ?? 0
    let onscreen = (w[kCGWindowIsOnscreen as String] as? Bool) ?? false
    print("\(id)\t\(app)\t\(width)\t\(height)\t\(onscreen ? 1 : 0)\t\(title)")
}
