import Foundation
import Speech

/// A second hearing of a voice note by the iPhone's own recognizer, on the device only (the audio never goes to
/// Apple). Muse Voice Transcribe still writes the note down; the server gives both hearings to Muse Spark, which
/// fixes what one of them misheard (accented English words, names), and falls back to this one if Muse fails.
enum OnDeviceSpeech {
    /// "en" or "ru": the app's language setting (`appLanguage`: en | ru | system), else the phone's language.
    /// Kazakh phones count as "ru": the user mixes both, and there is no on-device Kazakh recognizer.
    static var language: String {
        let stored = SharedStore.defaults.string(forKey: "appLanguage") ?? UserDefaults.standard.string(forKey: "appLanguage")
        if let stored, stored == "en" || stored == "ru" { return stored }
        let code = Locale.preferredLanguages.first.flatMap { Locale(identifier: $0).language.languageCode?.identifier }
        return code == "ru" || code == "kk" ? "ru" : "en"
    }

    /// Asks for speech recognition once (before the first recording, so the dialog doesn't interrupt a note).
    static func authorized() async -> Bool {
        switch SFSpeechRecognizer.authorizationStatus() {
        case .authorized: return true
        case .notDetermined:
            return await withCheckedContinuation { (done: CheckedContinuation<Bool, Never>) in
                SFSpeechRecognizer.requestAuthorization { done.resume(returning: $0 == .authorized) }
            }
        default: return false
        }
    }

    /// What the iPhone heard in the WAV, or nil: no permission, no on-device model for the language, or slower than
    /// `limit` (then Muse Voice Transcribe answers alone, nothing is lost).
    static func hear(_ wav: Data, language: String, limit: TimeInterval) async -> String? {
        guard SFSpeechRecognizer.authorizationStatus() == .authorized,
              let recognizer = SFSpeechRecognizer(locale: Locale(identifier: language == "ru" ? "ru-RU" : "en-US")),
              recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else { return nil }
        let url = FileManager.default.temporaryDirectory.appending(path: "sayso-heard-\(UUID().uuidString).wav")
        guard (try? wav.write(to: url)) != nil else { return nil }
        defer { try? FileManager.default.removeItem(at: url) }
        let request = SFSpeechURLRecognitionRequest(url: url)
        request.requiresOnDeviceRecognition = true
        request.shouldReportPartialResults = false
        request.addsPunctuation = true
        request.taskHint = .dictation
        let heard = await withTaskGroup(of: String?.self) { group -> String? in
            group.addTask { await recognize(recognizer, request) }
            group.addTask {
                try? await Task.sleep(nanoseconds: UInt64(limit * 1_000_000_000))
                return nil
            }
            let first = await group.next() ?? nil
            group.cancelAll()
            return first
        }
        let text = heard?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return text.isEmpty ? nil : text
    }

    private static func recognize(_ recognizer: SFSpeechRecognizer, _ request: SFSpeechURLRecognitionRequest) async -> String? {
        let running = Running()
        return await withTaskCancellationHandler {
            await withCheckedContinuation { (done: CheckedContinuation<String?, Never>) in
                running.wait(done)  // before the task starts, so its answer always finds the continuation
                running.run(recognizer.recognitionTask(with: request) { result, error in
                    if let result, result.isFinal {
                        running.finish(result.bestTranscription.formattedString)
                    } else if error != nil {
                        running.finish(nil)
                    }
                })
                if Task.isCancelled { running.cancel() }
            }
        } onCancel: {
            running.cancel()
        }
    }

    /// One recognition task and its continuation, resumed exactly once (the result, an error or a cancel).
    private final class Running: @unchecked Sendable {
        private let lock = NSLock()
        private var done: CheckedContinuation<String?, Never>?
        private var task: SFSpeechRecognitionTask?
        private var finished = false

        func wait(_ done: CheckedContinuation<String?, Never>) {
            lock.lock()
            if finished {  // cancelled before it began
                lock.unlock()
                done.resume(returning: nil)
                return
            }
            self.done = done
            lock.unlock()
        }

        func run(_ task: SFSpeechRecognitionTask) {
            lock.lock()
            let stop = finished
            if !stop { self.task = task }
            lock.unlock()
            if stop { task.cancel() }
        }

        func finish(_ text: String?) {
            lock.lock()
            let done = self.done
            self.done = nil
            finished = true
            lock.unlock()
            done?.resume(returning: text)
        }

        func cancel() {
            lock.lock()
            let task = self.task
            lock.unlock()
            task?.cancel()
            finish(nil)
        }
    }
}
