import AppIntents
import SwiftUI

struct RepliesSnippetView: View {
    let response: ReplyResponse?
    let copiedIndex: Int?

    var body: some View {
        if let response {
            VStack(alignment: .leading, spacing: 10) {
                if !(response.options ?? []).isEmpty {
                    HStack(spacing: 6) {
                        ForEach(Audience.allCases) { audience in
                            let selected = audience.rawValue == response.context.audience
                            Button(intent: RestyleRepliesIntent(audience: audience)) {
                                Text(audience.label).font(.caption.weight(selected ? .semibold : .regular))
                                    .lineLimit(1).frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.bordered)
                            .tint(selected ? .accentColor : .gray)
                        }
                    }
                }
                Text(response.context.situation)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(response.context.summary)
                    .font(.subheadline)
                ForEach(Array(response.replies.enumerated()), id: \.offset) { index, reply in
                    Button(intent: CopyReplyIntent(index: index)) {
                        HStack(alignment: .top) {
                            Text(reply.text)
                                .multilineTextAlignment(.leading)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Image(systemName: copiedIndex == index ? "checkmark" : "doc.on.doc")
                                .foregroundStyle(copiedIndex == index ? .green : .secondary)
                        }
                    }
                    .buttonStyle(.bordered)
                    .tint(copiedIndex == index ? .green : .accentColor)
                }
                Text(copiedIndex == nil ? "Tap a reply to copy it" : "Copied — paste it in the chat")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding()
        } else {
            Text("No replies yet").padding()
        }
    }
}
