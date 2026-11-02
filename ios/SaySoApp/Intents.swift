import AppIntents
import SwiftUI
import UIKit
import UniformTypeIdentifiers

/// Who the reply is for. Asked on every run; "Auto" takes it from the chat title on the screenshot.
enum ReplyAudience: String, AppEnum {
    case auto, partner, friends, family, elders

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Audience"
    static var caseDisplayRepresentations: [ReplyAudience: DisplayRepresentation] = [
        .auto: "Auto (from the chat)", .partner: "Partner", .friends: "Friends", .family: "Family",
        .elders: "Elders / formal",
    ]

    var audience: Audience? {
        switch self {
        case .auto: nil
        case .partner: .partner
        case .friends: .friends
        case .family: .family
        case .elders: .elder_informal
        }
    }
}

/// The Back Tap shortcut: Take Screenshot → Reply from Screenshot (→ optionally Choose from List → Copy to Clipboard).
/// It asks who the reply is for and an optional note ("politely decline, I'm busy" or some context), shows the
/// replies right in the shortcut, copies the first one, and returns all of them for a Choose from List step.
struct ReplyFromScreenshotIntent: AppIntent {
    static var title: LocalizedStringResource = "Reply from Screenshot"
    static var description = IntentDescription("Reads the chat on the screenshot and writes replies in your style.")

    /// Takes the output of the shortcut's previous action ("Take Screenshot") automatically.
    @Parameter(title: "Screenshot", supportedContentTypes: [.image, .png, .jpeg],
               inputConnectionBehavior: .connectToPreviousIntentResult)
    var screenshot: IntentFile

    /// No default on purpose: Shortcuts asks for it on every run.
    @Parameter(title: "Audience", requestValueDialog: "Who is it for?")
    var audience: ReplyAudience

    @Parameter(title: "Ask for a note", default: true)
    var asksForNote: Bool

    @Parameter(title: "Note", description: "Optional: what to say or some context.",
               inputOptions: String.IntentInputOptions(multiline: false))
    var note: String?

    static var parameterSummary: some ParameterSummary {
        Summary("Reply to \(\.$screenshot) for \(\.$audience)") {
            \.$asksForNote
            \.$note
        }
    }

    func perform() async throws -> some IntentResult & ReturnsValue<[String]> & ProvidesDialog & ShowsSnippetView {
        var note = note
        if note == nil && asksForNote {
            // Cancelling or leaving it empty just means "no note".
            note = try? await $note.requestValue("Anything to add? An instruction or some context, or leave it empty.")
        }
        let response = try await SaySoAPI.reply(screenshot: screenshot.data, audience: audience.audience, instruction: note)
        ReplyStore.latest = response
        let replies = response.replies.map(\.text)
        if let first = replies.first {
            await MainActor.run { UIPasteboard.general.string = first }
        }
        let dialog: IntentDialog = replies.isEmpty ? "No reply this time. Try again with a note." : "Copied the first one. Paste it in the chat."
        return .result(value: replies, dialog: dialog, view: RepliesSnippet(replies: replies))
    }
}

/// The replies, shown inside the shortcut: the first one is already on the clipboard.
struct RepliesSnippet: View {
    let replies: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(replies.enumerated()), id: \.offset) { index, reply in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: index == 0 ? "doc.on.clipboard.fill" : "bubble.left")
                        .foregroundStyle(Color.accentColor)
                        .frame(width: 18)
                    Text(reply).font(.subheadline)
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.accentColor.opacity(index == 0 ? 0.14 : 0.06), in: .rect(cornerRadius: 12))
            }
        }
        .padding()
    }
}

struct SaySoShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: ReplyFromScreenshotIntent(),
            phrases: ["Reply with \(.applicationName)"],
            shortTitle: "Reply from Screenshot",
            systemImageName: "text.bubble"
        )
    }
}
