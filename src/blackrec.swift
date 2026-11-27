// blackrec — glitch-free capture from a CoreAudio input device.
//
//   blackrec [-d <seconds>] [-q] <out.caf> [device-uid]
//
// Records until SIGINT/SIGTERM (or Return on a tty), or for exactly -d seconds.
//
// ffmpeg's avfoundation input drops buffers on virtual devices, which shows up
// as full-scale clicks under the music. This taps the device through
// AVAudioEngine (the native CoreAudio path) and writes 32-bit float WAV, so the
// capture is bit-exact with what the app played. Encoding happens afterwards.

import AVFoundation
import CoreAudio
import Foundation

let kBlackHoleUID = "BlackHole2ch_UID"

func die(_ msg: String) -> Never {
    FileHandle.standardError.write(("blackrec: " + msg + "\n").data(using: .utf8)!)
    exit(1)
}

func addr(_ sel: AudioObjectPropertySelector) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: sel,
                               mScope: kAudioObjectPropertyScopeGlobal,
                               mElement: kAudioObjectPropertyElementMain)
}

func device(forUID uid: String) -> AudioDeviceID? {
    var a = addr(kAudioHardwarePropertyDevices)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &a, 0, nil, &size) == noErr
    else { return nil }
    var ids = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &a, 0, nil, &size, &ids) == noErr
    else { return nil }
    var ua = addr(kAudioDevicePropertyDeviceUID)
    for id in ids {
        var s = UInt32(MemoryLayout<CFString?>.size)
        let box = UnsafeMutablePointer<Unmanaged<CFString>?>.allocate(capacity: 1)
        defer { box.deallocate() }
        box.pointee = nil
        if AudioObjectGetPropertyData(id, &ua, 0, nil, &s, box) == noErr,
           box.pointee?.takeRetainedValue() as String? == uid { return id }
    }
    return nil
}

var rest = Array(CommandLine.arguments.dropFirst())
var limit: Double? = nil       // -d: stop after N seconds
var quiet = false              // -q: no live meter (for scripted/batch use)
while let f = rest.first, f.hasPrefix("-") {
    switch f {
    case "-d":
        rest.removeFirst()
        guard let v = rest.first, let s = Double(v), s > 0 else { die("-d needs a positive number of seconds") }
        limit = s
    case "-q": quiet = true
    default: die("unknown option \(f)")
    }
    rest.removeFirst()
}
guard let outPath = rest.first else { die("usage: blackrec [-d secs] [-q] <out.caf> [device-uid]") }
let uid = rest.count > 1 ? rest[1] : kBlackHoleUID
guard var devID = device(forUID: uid) else { die("no audio device with UID \(uid)") }

let engine = AVAudioEngine()
let input = engine.inputNode
guard let unit = input.audioUnit else { die("no input audio unit") }
let st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice,
                              kAudioUnitScope_Global, 0, &devID,
                              UInt32(MemoryLayout<AudioDeviceID>.size))
if st != noErr { die("cannot bind input to \(uid) (status \(st)) — grant Microphone access to your terminal in System Settings ▸ Privacy & Security") }

let fmt = input.inputFormat(forBus: 0)
guard fmt.sampleRate > 0, fmt.channelCount > 0 else {
    die("device reports no input format — grant Microphone access to your terminal in System Settings ▸ Privacy & Security")
}

// 32-bit float WAV: lossless, exactly the samples CoreAudio handed us.
let settings: [String: Any] = [
    AVFormatIDKey: kAudioFormatLinearPCM,
    AVSampleRateKey: fmt.sampleRate,
    AVNumberOfChannelsKey: fmt.channelCount,
    AVLinearPCMBitDepthKey: 32,
    AVLinearPCMIsFloatKey: true,
    AVLinearPCMIsBigEndianKey: false,
    AVLinearPCMIsNonInterleaved: false,
]
let file: AVAudioFile
do {
    file = try AVAudioFile(forWriting: URL(fileURLWithPath: outPath), settings: settings,
                           commonFormat: .pcmFormatFloat32, interleaved: false)
} catch { die("cannot open \(outPath): \(error.localizedDescription)") }

let lock = NSLock()
var frames: Int64 = 0
var peak: Float = 0
var writeError: String? = nil

input.installTap(onBus: 0, bufferSize: 8192, format: fmt) { buf, _ in
    do { try file.write(from: buf) } catch {
        lock.lock(); writeError = error.localizedDescription; lock.unlock(); return
    }
    var p: Float = 0
    if let ch = buf.floatChannelData {
        for c in 0..<Int(buf.format.channelCount) {
            for i in 0..<Int(buf.frameLength) { p = max(p, abs(ch[c][i])) }
        }
    }
    lock.lock(); frames += Int64(buf.frameLength); peak = max(peak, p); lock.unlock()
}

do { try engine.start() } catch { die("cannot start capture: \(error.localizedDescription)") }

FileHandle.standardError.write("capturing \(Int(fmt.sampleRate)) Hz × \(fmt.channelCount)ch (32-bit float)\n".data(using: .utf8)!)
// stdout line the caller can block on: capture is live, safe to start playback
print("READY"); fflush(stdout)

var stopping = false
func finish() {
    if stopping { return }
    stopping = true
    input.removeTap(onBus: 0)
    engine.stop()
    lock.lock(); let f = frames, err = writeError; lock.unlock()
    FileHandle.standardError.write("\ncaptured \(String(format: "%.1f", Double(f) / fmt.sampleRate))s\n".data(using: .utf8)!)
    if let err { die("write failed: \(err)") }
    exit(0)
}

var signalSources: [DispatchSourceSignal] = []
for sig in [SIGINT, SIGTERM] {
    signal(sig, SIG_IGN)
    let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
    src.setEventHandler { finish() }
    src.resume()
    signalSources.append(src)  // keep alive for the process lifetime
}

// Return also stops, so there's no need to reach for Ctrl-C. Only when stdin is
// a terminal — otherwise EOF on a redirected stdin would stop us immediately.
var stdinSource: DispatchSourceRead? = nil
if isatty(0) == 1 && limit == nil {
    let src = DispatchSource.makeReadSource(fileDescriptor: 0, queue: .main)
    src.setEventHandler { finish() }
    src.resume()
    stdinSource = src
}
withExtendedLifetime(stdinSource) {}

if let limit {
    Timer.scheduledTimer(withTimeInterval: limit, repeats: false) { _ in finish() }
}

// live meter on stderr
if !quiet {
    Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
        lock.lock(); let f = frames, p = peak; peak = 0; lock.unlock()
        let secs = Double(f) / fmt.sampleRate
        let db = p > 0 ? 20 * log10(p) : -120
        let bars = max(0, min(20, Int((db + 60) / 3)))
        let meter = String(repeating: "█", count: bars) + String(repeating: "·", count: 20 - bars)
        let line = String(format: "\r  %02d:%02d  [%@] %6.1f dB ", Int(secs) / 60, Int(secs) % 60, meter, db)
        FileHandle.standardError.write(line.data(using: .utf8)!)
    }
}

RunLoop.main.run()
