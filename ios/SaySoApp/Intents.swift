import AppIntents
import UIKit
import UniformTypeIdentifiers

/// Run by the "SaySo Reply" Shortcut (Back Tap / Action Button): Take Screenshot → this intent.
struct ReplyFromScreenshotIntent: AppIntent {
    static var title: LocalizedStringResource = "Reply from Screenshot"
    static var description = IntentDescription("Reads the conversation on the screenshot and suggests replies in your style.")

    /// Takes the output of the shortcut's previous action ("Take Screenshot") automatically,
    /// so the user doesn't have to pick a variable (Shortcuts otherwise offers only "Choose File").
    @Parameter(title: "Screenshot", supportedContentTypes: [.image, .png, .jpeg],
               inputConnectionBehavior: .connectToPreviousIntentResult)
    var screenshot: IntentFile

    /// Empty = detected from the chat title. Set to "Ask Each Time" in Shortcuts to pick it on every run.
    @Parameter(title: "Audience", description: "Leave empty to detect it from the chat.")
    var audience: Audience?

    /// Optional instruction or context, e.g. "politely decline, I'm busy". "Ask Each Time" shows a text field.
    @Parameter(title: "What to say", description: "Optional: an instruction or extra context.",
               inputOptions: String.IntentInputOptions(multiline: true))
    var instruction: String?

    static var parameterSummary: some ParameterSummary {
        Summary("Reply to \(\.$screenshot)") {
            \.$audience
            \.$instruction
        }
    }

    func perform() async throws -> some IntentResult & ShowsSnippetIntent {
        ReplyStore.latest = try await SaySoAPI.reply(screenshot: screenshot.data, audience: audience, instruction: instruction)
        return .result(snippetIntent: RepliesSnippetIntent())
    }
}

/// The card shown over the current app: context line + reply buttons.
struct RepliesSnippetIntent: SnippetIntent {
    static var title: LocalizedStringResource = "SaySo Replies"
    static var isDiscoverable = false

    func perform() async throws -> some IntentResult & ShowsSnippetView {
        .result(view: RepliesSnippetView(response: ReplyStore.latest, copiedIndex: ReplyStore.copiedIndex))
    }
}

/// Tapped from a reply button in the snippet: copies the reply and marks it in the card.
struct CopyReplyIntent: AppIntent {
    static var title: LocalizedStringResource = "Copy Reply"
    static var isDiscoverable = false

    @Parameter(title: "Index")
    var index: Int

    init() {}

    init(index: Int) {
        self.index = index
    }

    func perform() async throws -> some IntentResult {
        guard let replies = ReplyStore.latest?.replies, replies.indices.contains(index) else { return .result() }
        UIPasteboard.general.string = replies[index].text
        ReplyStore.copiedIndex = index
        RepliesSnippetIntent.reload()
        return .result()
    }
}

/// Audience chip in the snippet: the same replies, rewritten for another audience (no new screenshot read).
struct RestyleRepliesIntent: AppIntent {
    static var title: LocalizedStringResource = "Restyle Replies"
    static var isDiscoverable = false

    @Parameter(title: "Audience")
    var audience: Audience

    init() {}

    init(audience: Audience) {
        self.audience = audience
    }

    func perform() async throws -> some IntentResult {
        guard let latest = ReplyStore.latest, !(latest.options ?? []).isEmpty else { return .result() }
        ReplyStore.latest = try await SaySoAPI.restyle(latest, for: audience)
        RepliesSnippetIntent.reload()
        return .result()
    }
}

extension Audience: AppEnum {
    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Audience"
    static var caseDisplayRepresentations: [Audience: DisplayRepresentation] = [
        .partner: "Partner", .friends: "Friends", .family: "Family", .elder_informal: "Elders",
    ]
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
