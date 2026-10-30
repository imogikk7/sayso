import SwiftUI
import UIKit

/// The last screenshot's replies inside the app; tap to copy.
struct RepliesView: View {
    let response: ReplyResponse
    @State private var copied: Int?

    var body: some View {
        ForEach(Array(response.replies.enumerated()), id: \.offset) { index, reply in
            Button {
                UIPasteboard.general.string = reply.text
                copied = index
            } label: {
                HStack(alignment: .top) {
                    Text(reply.text).frame(maxWidth: .infinity, alignment: .leading)
                    Image(systemName: copied == index ? "checkmark" : "doc.on.doc")
                        .foregroundStyle(copied == index ? .green : .secondary)
                }
            }
            .foregroundStyle(.primary)
        }
    }
}
