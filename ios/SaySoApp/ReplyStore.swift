import Foundation

/// Latest replies from a screenshot, shared between the intent, its snippet and the app.
/// Moves to the App Group later so the keyboard can read it too.
enum ReplyStore {
    private static let defaults = UserDefaults.standard
    private static let latestKey = "latestReply"
    private static let copiedKey = "copiedReplyIndex"

    static var latest: ReplyResponse? {
        get { defaults.data(forKey: latestKey).flatMap { try? JSONDecoder().decode(ReplyResponse.self, from: $0) } }
        set {
            defaults.set(try? JSONEncoder().encode(newValue), forKey: latestKey)
            copiedIndex = nil
        }
    }

    static var copiedIndex: Int? {
        get { defaults.object(forKey: copiedKey) as? Int }
        set { defaults.set(newValue, forKey: copiedKey) }
    }
}
