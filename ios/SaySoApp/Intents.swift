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

/// No replies came back: the shortcut stops here with this message instead of an empty list.
enum ScreenshotReplyError: Error, CustomLocalizedStringResourceConvertible {
    case empty

    var localizedStringResource: LocalizedStringResource {
        switch self {
        case .empty: "No reply this time. Try again with a note."
        }
    }
}

/// What both screenshot actions do: ask for a note if wanted, write the replies, and keep them in the App Group for
/// the SaySo keyboard (Replies tab and the strip it shows right after the shortcut).
///
/// They don't touch the clipboard: iOS drops pasteboard writes from an intent running in the background (Back Tap
/// runs it over another app). Copying is the shortcut's job: Choose from List → Copy to Clipboard, which Shortcuts
/// does itself in the foreground.
private enum ScreenshotReplies {
    static func write(screenshot: IntentFile, audience: ReplyAudience, note: String?, asksForNote: Bool,
                      ask: () async throws -> String?) async throws -> [String] {
        AppLanguage.install()
        var note = note
        if note == nil && asksForNote {
            // Cancelling or leaving it empty just means "no note".
            note = try? await ask()
        }
        let response = try await SaySoAPI.reply(screenshot: screenshot.data, audience: audience.audience, instruction: note)
        ReplyStore.latest = response
        return response.replies.map(\.text).filter { !$0.isEmpty }
    }
}

/// The Back Tap shortcut that copies: Take Screenshot → Reply with SaySo → Choose from List → Copy to Clipboard.
/// It asks who the reply is for and an optional note, then hands the replies to the next action as a list; it shows
/// nothing itself, so Choose from List is the only thing on screen.
struct ReplyWithSaySoIntent: AppIntent {
    static var title: LocalizedStringResource = "Reply with SaySo"
    static var description = IntentDescription(
        "Reads the chat on the screenshot and passes replies in your style to the next action. Add Choose from List and Copy to Clipboard after it to copy one."
    )

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
        Summary("Replies to \(\.$screenshot) for \(\.$audience)") {
            \.$asksForNote
            \.$note
        }
    }

    func perform() async throws -> some IntentResult & ReturnsValue<[String]> {
        let replies = try await ScreenshotReplies.write(screenshot: screenshot, audience: audience, note: note,
                                                        asksForNote: asksForNote) {
            try await $note.requestValue("Anything to add? An instruction or some context, or leave it empty.")
        }
        guard !replies.isEmpty else { throw ScreenshotReplyError.empty }
        return .result(value: replies)
    }
}

/// The first Back Tap shortcut: Take Screenshot → Reply from Screenshot. It shows the replies right in the shortcut;
/// the SaySo keyboard then offers the same ones to insert with a tap. It also returns them, so a Choose from List →
/// Copy to Clipboard step after it works too.
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
        let replies = try await ScreenshotReplies.write(screenshot: screenshot, audience: audience, note: note,
                                                        asksForNote: asksForNote) {
            try await $note.requestValue("Anything to add? An instruction or some context, or leave it empty.")
        }
        let dialog: IntentDialog = replies.isEmpty
            ? "No reply this time. Try again with a note."
            : "Switch to the SaySo keyboard: your replies are there, tap one to put it in the chat."
        return .result(value: replies, dialog: dialog, view: RepliesSnippet(replies: replies))
    }
}

/// The replies, shown inside the shortcut; the SaySo keyboard offers the same ones to insert with a tap.
struct RepliesSnippet: View {
    let replies: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(replies.enumerated()), id: \.offset) { index, reply in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "bubble.left.fill")
                        .foregroundStyle(Color.accentColor)
                        .frame(width: 18)
                    Text(verbatim: reply).font(.subheadline)
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.accentColor.opacity(index == 0 ? 0.14 : 0.06), in: .rect(cornerRadius: 12))
            }
        }
        .padding()
        .environment(\.locale, AppLanguage.current.locale)
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
