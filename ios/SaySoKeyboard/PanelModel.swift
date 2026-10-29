import SwiftUI
import UIKit

enum PanelTab: String, CaseIterable, Identifiable {
    case rewrite = "Rewrite"
    case compose = "Write"
    case replies = "Replies"

    var id: String { rawValue }
}

struct PanelOption: Identifiable, Hashable {
    let id = UUID()
    let label: String?
    let text: String
}

@MainActor
final class PanelModel: ObservableObject {
    @Published var tab: PanelTab = .rewrite
    @Published var audience: Audience {
        didSet { UserDefaults.standard.set(audience.rawValue, forKey: "audience") }
    }
    @Published var draft = ""
    @Published var options: [PanelOption] = []
    @Published var busy = false
    @Published var message: String?
    @Published var warming = false
    @Published var showsGlobe = true
    @Published var hasFullAccess = false

    private weak var controller: UIInputViewController?
    private var proxy: UITextDocumentProxy? { controller?.textDocumentProxy }

    init(controller: UIInputViewController) {
        self.controller = controller
        audience = UserDefaults.standard.string(forKey: "audience").flatMap(Audience.init(rawValue:)) ?? .friends
    }

    /// The text in the field before the cursor is the user's draft (or instruction).
    /// iOS may only expose part of a long field; for a chat message that is the whole draft.
    func readDraft() {
        draft = proxy?.documentContextBeforeInput ?? ""
    }

    func nextKeyboard() {
        controller?.advanceToNextInputMode()
    }

    func run() {
        switch tab {
        case .rewrite: generate { try await SaySoAPI.rewrite($0, audience: $1) }
        case .compose: generate { try await SaySoAPI.compose($0, audience: $1) }
        case .replies: loadLatest()
        }
    }

    private func generate(_ call: @escaping (String, Audience) async throws -> StyledResponse) {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            message = tab == .rewrite ? "Type a draft with your keyboard first." : "Type what to say, e.g. “say I'm 20 min late”."
            return
        }
        perform {
            let response = try await call(text, self.audience)
            var seen = Set<String>()
            let texts = ([response.text] + response.candidates).filter { !$0.isEmpty && seen.insert($0).inserted }
            return texts.prefix(4).map { PanelOption(label: nil, text: $0) }
        }
    }

    func loadLatest() {
        perform {
            let latest = try await SaySoAPI.latest()
            guard let replies = latest.replies, !replies.isEmpty else {
                throw SaySoError.invalid("No screenshot replies yet. Double-tap the back of your iPhone in a chat.")
            }
            if let raw = latest.audience, let audience = Audience(rawValue: raw) { self.audience = audience }
            return replies.map { PanelOption(label: $0.intent, text: $0.text) }
        }
    }

    /// Their copied messages (handed over by the system Paste button, no clipboard prompt) → three replies.
    func reply(to copied: String) {
        let copied = copied.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !copied.isEmpty else {
            message = "Copy their message first."
            return
        }
        perform {
            let response = try await SaySoAPI.reply(messages: copied, audience: self.audience)
            return response.replies.map { PanelOption(label: $0.intent, text: $0.text) }
        }
    }

    /// Replaces the draft (Rewrite / Write) or inserts at the cursor (Replies).
    func insert(_ option: PanelOption) {
        guard let proxy else { return }
        if tab != .replies {
            for _ in 0..<(proxy.documentContextBeforeInput ?? "").count { proxy.deleteBackward() }
        }
        proxy.insertText(option.text)
        options = []
        readDraft()
    }

    private func perform(_ work: @escaping () async throws -> [PanelOption]) {
        guard hasFullAccess else {
            message = "SaySo needs Full Access to reach your model: Settings → General → Keyboard → Keyboards → SaySo."
            return
        }
        busy = true
        message = nil
        warming = false
        Task {
            do {
                options = try await work()
                if options.isEmpty { message = "Nothing came back, try again." }
            } catch SaySoError.warming {
                warming = true
                message = SaySoError.warming.errorDescription
            } catch {
                message = error.localizedDescription
            }
            busy = false
        }
    }
}
