import Foundation

/// The last screenshot's replies, shown in the app. The summary of the other person's messages is not kept.
enum ReplyStore {
    private static let defaults = UserDefaults.standard
    private static let latestKey = "latestReply"

    static var latest: ReplyResponse? {
        get { defaults.data(forKey: latestKey).flatMap { try? JSONDecoder().decode(ReplyResponse.self, from: $0) } }
        set {
            let kept = newValue.map {
                ReplyResponse(context: ReplyContext(audience: $0.context.audience, situation: $0.context.situation, summary: ""),
                              replies: $0.replies)
            }
            defaults.set(try? JSONEncoder().encode(kept), forKey: latestKey)
        }
    }
}
