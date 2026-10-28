import AppIntents
import SwiftUI

struct RepliesSnippetView: View {
    let response: ReplyResponse?
    let copiedIndex: Int?

    var body: some View {
        if let response {
            VStack(alignment: .leading, spacing: 10) {
                Text("\(response.context.audience) · \(response.context.situation)")
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
