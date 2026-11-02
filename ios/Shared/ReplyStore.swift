import Foundation

/// The last screenshot's replies, from the Back Tap shortcut: shown in the app and in the keyboard, so they can be
/// inserted even when the clipboard didn't take them. Kept in the App Group; the summary of the other person's
/// messages is not kept.
enum ReplyStore {
    private static let defaults = SharedStore.defaults
    private static let latestKey = "latestReply"
    private static let savedKey = "latestReplyAt"
    private static let takenKey = "latestReplyTaken"

    static var latest: ReplyResponse? {
        get { defaults.data(forKey: latestKey).flatMap { try? JSONDecoder().decode(ReplyResponse.self, from: $0) } }
        set {
            let kept = newValue.map {
                ReplyResponse(context: ReplyContext(audience: $0.context.audience, situation: $0.context.situation, summary: ""),
                              replies: $0.replies)
            }
            defaults.set(try? JSONEncoder().encode(kept), forKey: latestKey)
            defaults.set(Date().timeIntervalSince1970, forKey: savedKey)
            defaults.set(false, forKey: takenKey)
        }
    }

    /// The shortcut's replies if they are new (the last few minutes) and the keyboard hasn't shown them yet; marks
    /// them as shown, so they come up once, right after the shortcut.
    static func takeFresh(within seconds: TimeInterval = 600) -> ReplyResponse? {
        let saved = defaults.double(forKey: savedKey)
        guard saved > 0, Date().timeIntervalSince1970 - saved < seconds, !defaults.bool(forKey: takenKey),
              let latest, !latest.replies.isEmpty else { return nil }
        defaults.set(true, forKey: takenKey)
        return latest
    }

    /// The replies if the shortcut made them in the last few minutes (the keyboard offers only fresh ones).
    static func fresh(within seconds: TimeInterval = 600) -> [String] {
        let saved = defaults.double(forKey: savedKey)
        guard saved > 0, Date().timeIntervalSince1970 - saved < seconds else { return [] }
        return latest?.replies.map(\.text) ?? []
    }
}
