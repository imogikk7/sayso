import AppIntents
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

/// The Back Tap shortcut: Take Screenshot → Reply from Screenshot → Choose from List → Copy to Clipboard.
/// It asks who the reply is for and an optional note ("politely decline, I'm busy" or some context), then
/// returns only the replies, one message each, for the system list; Copy to Clipboard copies the chosen one.
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

    func perform() async throws -> some IntentResult & ReturnsValue<[String]> {
        var note = note
        if note == nil && asksForNote {
            // Cancelling or leaving it empty just means "no note".
            note = try? await $note.requestValue("Anything to add? An instruction or some context, or leave it empty.")
        }
        let response = try await SaySoAPI.reply(screenshot: screenshot.data, audience: audience.audience, instruction: note)
        ReplyStore.latest = response
        return .result(value: response.replies.map(\.text))
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
