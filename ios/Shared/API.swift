import Foundation
import UIKit

/// Shared by the app (Back Tap intent) and the keyboard panel.

struct ReplyContext: Codable, Hashable {
    let audience: String
    let situation: String
    let summary: String
}

struct ReplyOption: Codable, Hashable {
    let intent: String
    let text: String
    var tone: String? = nil
    var thought: String? = nil
}

struct ReplyResponse: Codable, Hashable {
    let context: ReplyContext
    let replies: [ReplyOption]
}

struct StyledResponse: Codable, Hashable {
    let text: String
    let candidates: [String]
}

/// The last screenshot replies, as the keyboard fetches them (no summary of the other person's messages).
struct LatestReplies: Codable, Hashable {
    var audience: String? = nil
    var situation: String? = nil
    var replies: [ReplyOption]? = nil
    var at: Double? = nil
}

enum Audience: String, CaseIterable, Identifiable {
    case partner, friends, family, elder_informal

    var id: String { rawValue }
    var label: String {
        switch self {
        case .partner: "Partner"
        case .friends: "Friends"
        case .family: "Family"
        case .elder_informal: "Elders"
        }
    }
}

enum SaySoError: LocalizedError {
    case warming, unauthorized, invalid(String), server(Int)

    var errorDescription: String? {
        switch self {
        case .warming: "Your model is waking up (about 2 minutes). Try again shortly."
        case .unauthorized: "The app's token was rejected."
        case .invalid(let detail): detail
        case .server(let code): "Server error \(code)."
        }
    }
}

enum SaySoAPI {
    static func reply(screenshot: Data) async throws -> ReplyResponse {
        try await send("reply", body: jpeg(screenshot), contentType: "image/jpeg", timeout: 25)
    }

    static func reply(messages: String, audience: Audience?) async throws -> ReplyResponse {
        var body: [String: String] = ["messages": messages]
        body["audience"] = audience?.rawValue
        return try await send("reply", json: body, timeout: 20)
    }

    static func rewrite(_ text: String, audience: Audience) async throws -> StyledResponse {
        try await send("rewrite", json: ["text": text, "audience": audience.rawValue], timeout: 15)
    }

    static func compose(_ instruction: String, audience: Audience) async throws -> StyledResponse {
        try await send("compose", json: ["instruction": instruction, "audience": audience.rawValue], timeout: 15)
    }

    static func latest() async throws -> LatestReplies {
        try await send("latest", method: "GET", timeout: 10)
    }

    /// Waits until the GPU is up; a cold start takes a few minutes.
    static func warmup() async throws {
        struct Ready: Decodable { let ready: Bool }
        let ready: Ready = try await send("warmup", method: "GET", timeout: 600)
        if !ready.ready { throw SaySoError.warming }
    }

    // MARK: - Transport

    private static func send<T: Decodable>(_ path: String, json: [String: String], timeout: TimeInterval) async throws -> T {
        try await send(path, body: try JSONEncoder().encode(json), contentType: "application/json", timeout: timeout)
    }

    private static func send<T: Decodable>(_ path: String, method: String = "POST", body: Data? = nil,
                                           contentType: String? = nil, timeout: TimeInterval) async throws -> T {
        var request = URLRequest(url: Secrets.apiURL.appending(path: path))
        request.httpMethod = method
        request.timeoutInterval = timeout
        request.httpBody = body
        if let contentType { request.setValue(contentType, forHTTPHeaderField: "Content-Type") }
        request.setValue("Bearer \(Secrets.apiToken)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.data(for: request)
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        switch code {
        case 200: return try JSONDecoder().decode(T.self, from: data)
        case 503: throw SaySoError.warming
        case 401: throw SaySoError.unauthorized
        case 413, 422: throw SaySoError.invalid(detail(data) ?? "The request was rejected.")
        default: throw SaySoError.server(code)
        }
    }

    private static func detail(_ data: Data) -> String? {
        (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
    }

    /// Screenshots go up as JPEG, at most 1280 px on the long side: smaller upload, same text for Muse Spark.
    private static func jpeg(_ data: Data) -> Data {
        guard let image = UIImage(data: data) else { return data }
        let scale = min(1, 1280 / max(image.size.width, image.size.height))
        let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
        let resized = UIGraphicsImageRenderer(size: size).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        return resized.jpegData(compressionQuality: 0.75) ?? data
    }
}
