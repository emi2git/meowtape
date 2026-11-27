// audiodev — tiny CoreAudio CLI used by `mp3 rec`
//
//   audiodev get                     print UID of current default output device
//   audiodev set <uid>               set default output device by UID
//   audiodev name <uid>              print human name of a device UID
//   audiodev ensure-multi <uid>      make/refresh a stacked multi-output device
//                                    (<uid> = real speakers) + BlackHole 2ch,
//                                    print the multi-output device's UID
//
// A "multi-output device" is an aggregate device with IsStacked = true: audio
// sent to it is mirrored to every sub-device, so we can capture from BlackHole
// while the sound still comes out of the speakers.

import CoreAudio
import Foundation

let kMultiName = "mp3 rec (Speakers + BlackHole)"
let kMultiUID = "com.emi2mac.mp3rec.multiout"
let kBlackHoleUID = "BlackHole2ch_UID"

func die(_ msg: String) -> Never {
    FileHandle.standardError.write(("audiodev: " + msg + "\n").data(using: .utf8)!)
    exit(1)
}

func addr(_ sel: AudioObjectPropertySelector) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: sel,
                               mScope: kAudioObjectPropertyScopeGlobal,
                               mElement: kAudioObjectPropertyElementMain)
}

func allDevices() -> [AudioDeviceID] {
    var a = addr(kAudioHardwarePropertyDevices)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &a, 0, nil, &size) == noErr
    else { return [] }
    var ids = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &a, 0, nil, &size, &ids) == noErr
    else { return [] }
    return ids
}

func stringProp(_ dev: AudioDeviceID, _ sel: AudioObjectPropertySelector) -> String? {
    var a = addr(sel)
    var size = UInt32(MemoryLayout<CFString?>.size)
    let box = UnsafeMutablePointer<Unmanaged<CFString>?>.allocate(capacity: 1)
    defer { box.deallocate() }
    box.pointee = nil
    guard AudioObjectGetPropertyData(dev, &a, 0, nil, &size, box) == noErr else { return nil }
    return box.pointee?.takeRetainedValue() as String?
}

func deviceUID(_ dev: AudioDeviceID) -> String? { stringProp(dev, kAudioDevicePropertyDeviceUID) }
func deviceName(_ dev: AudioDeviceID) -> String? { stringProp(dev, kAudioObjectPropertyName) }

func device(forUID uid: String) -> AudioDeviceID? {
    allDevices().first { deviceUID($0) == uid }
}

func defaultOutput() -> AudioDeviceID {
    var a = addr(kAudioHardwarePropertyDefaultOutputDevice)
    var dev = AudioDeviceID(0)
    var size = UInt32(MemoryLayout<AudioDeviceID>.size)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &a, 0, nil, &size, &dev) == noErr
    else { die("cannot read default output device") }
    return dev
}

func setDefaultOutput(_ dev: AudioDeviceID) {
    var a = addr(kAudioHardwarePropertyDefaultOutputDevice)
    var d = dev
    let st = AudioObjectSetPropertyData(AudioObjectID(kAudioObjectSystemObject), &a, 0, nil,
                                        UInt32(MemoryLayout<AudioDeviceID>.size), &d)
    if st != noErr { die("cannot set default output device (status \(st))") }
}

// Rebuild the multi-output device so it always mirrors the *current* speakers.
func ensureMulti(speakerUID: String) -> String {
    if let old = device(forUID: kMultiUID) {
        AudioHardwareDestroyAggregateDevice(old)
    }
    guard device(forUID: kBlackHoleUID) != nil else {
        die("BlackHole 2ch not found — install it with: brew install blackhole-2ch")
    }
    let desc: [String: Any] = [
        kAudioAggregateDeviceNameKey as String: kMultiName,
        kAudioAggregateDeviceUIDKey as String: kMultiUID,
        kAudioAggregateDeviceIsStackedKey as String: 1,     // multi-output, not aggregate input
        kAudioAggregateDeviceIsPrivateKey as String: 0,     // visible in Audio MIDI Setup
        kAudioAggregateDeviceMasterSubDeviceKey as String: speakerUID,
        kAudioAggregateDeviceSubDeviceListKey as String: [
            [kAudioSubDeviceUIDKey as String: speakerUID],
            [kAudioSubDeviceUIDKey as String: kBlackHoleUID,
             kAudioSubDeviceDriftCompensationKey as String: 1],
        ],
    ]
    var newDev = AudioDeviceID(0)
    let st = AudioHardwareCreateAggregateDevice(desc as CFDictionary, &newDev)
    if st != noErr { die("cannot create multi-output device (status \(st))") }
    return deviceUID(newDev) ?? kMultiUID
}

let args = Array(CommandLine.arguments.dropFirst())
switch args.first {
case "get":
    print(deviceUID(defaultOutput()) ?? die("default output has no UID"))
case "set":
    guard args.count == 2 else { die("usage: audiodev set <uid>") }
    guard let d = device(forUID: args[1]) else { die("no device with UID \(args[1])") }
    setDefaultOutput(d)
case "name":
    guard args.count == 2 else { die("usage: audiodev name <uid>") }
    print(device(forUID: args[1]).flatMap(deviceName) ?? args[1])
case "ensure-multi":
    guard args.count == 2 else { die("usage: audiodev ensure-multi <speaker-uid>") }
    print(ensureMulti(speakerUID: args[1]))
default:
    die("usage: audiodev get|set <uid>|name <uid>|ensure-multi <speaker-uid>")
}
