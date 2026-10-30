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

    func perform() async throws -> some IntentResult & ShowsSnippetIntent {
        ReplyStore.latest = try await SaySoAPI.reply(screenshot: screenshot.data)
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
