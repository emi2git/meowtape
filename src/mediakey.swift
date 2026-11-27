// mediakey — press one of this Mac's media keys, from a script.
//
// The Ximalaya app has no AppleScript dictionary; what it does register is the
// system-wide media shortcuts (Electron's MediaPlayPause / MediaNextTrack /
// MediaPreviousTrack). Those listen for the special system-defined event the
// keyboard's own play/next keys send — which is what this posts.
//
// Posting it needs Accessibility permission for whatever runs this (your
// terminal): System Settings ▸ Privacy & Security ▸ Accessibility.
//
//   mediakey play | next | prev      press one
//   mediakey check [ask]             is that allowed here? (ask = show the dialog)
//
// build: ./build.sh (swiftc -O -o bin/mediakey src/mediakey.swift)

import Cocoa

let codes: [String: Int32] = [
    "play": 16,   // NX_KEYTYPE_PLAY — play/pause, a toggle
    "next": 17,   // NX_KEYTYPE_NEXT
    "prev": 18,   // NX_KEYTYPE_PREVIOUS
    "fast": 19,
    "rewind": 20,
]

func press(_ code: Int32) {
    for down in [true, false] {
        let state: Int32 = down ? 0x0A : 0x0B
        let data1 = Int((code << 16) | (state << 8))
        guard let e = NSEvent.otherEvent(with: .systemDefined,
                                         location: .zero,
                                         modifierFlags: NSEvent.ModifierFlags(rawValue: 0),
                                         timestamp: 0,
                                         windowNumber: 0,
                                         context: nil,
                                         subtype: 8,
                                         data1: data1,
                                         data2: -1),
              let cg = e.cgEvent else {
            FileHandle.standardError.write("mediakey: could not build the event\n".data(using: .utf8)!)
            exit(1)
        }
        cg.post(tap: .cghidEventTap)
    }
}

let args = Array(CommandLine.arguments.dropFirst())
let arg = args.first ?? ""

// Without Accessibility, a posted key press is dropped in silence — no error,
// nothing happens — so anything scripted has to ask first.
if arg == "check" {
    let ask = args.count > 1 && args[1] == "ask"
    let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: ask] as CFDictionary
    exit(AXIsProcessTrustedWithOptions(opts) ? 0 : 1)
}

guard let code = codes[arg] else {
    FileHandle.standardError.write("usage: mediakey \(codes.keys.sorted().joined(separator: "|"))|check\n".data(using: .utf8)!)
    exit(2)
}
press(code)
