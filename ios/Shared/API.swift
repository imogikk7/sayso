import Foundation
import UIKit

/// Shared by the app (Back Tap intent, styles, chat) and the keyboard panel.

struct ReplyContext: Codable, Hashable {
    let audience: String
    let situation: String
    let summary: String
    var audiences: [String]? = nil  // the AI's top 3 guesses, most likely first
}

struct ReplyOption: Codable, Hashable {
    let intent: String
    let text: String  // one message (or the whole series / email)
    var tone: String? = nil
    var thought: String? = nil
    var parts: [String]? = nil  // the messages to send one by one (a series has several)
    var styled: Bool? = nil  // false: Muse Spark wrote it in the style; true: the style's own model
}

/// What a reply says (Muse Spark's draft from the chat); sent back to restyle for another audience.
struct ReplyIdea: Codable, Hashable {
    let act: String
    let draft: String
}

struct ReplyResponse: Codable, Hashable {
    let context: ReplyContext
    let replies: [ReplyOption]
    var options: [ReplyIdea]? = nil
}

struct StyledResponse: Codable, Hashable {
    let text: String
    let candidates: [String]
    var parts: [String]? = nil
    var audiences: [String]? = nil
}

/// The last screenshot replies, as the keyboard fetches them (no summary of the other person's messages).
struct LatestReplies: Codable, Hashable {
    var audience: String? = nil
    var situation: String? = nil
    var replies: [ReplyOption]? = nil
    var at: Double? = nil
}

enum Audience: String, CaseIterable, Identifiable, Codable {
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

// MARK: - Styles

struct StyleScores: Codable, Hashable {
    var soundsLikeYou: Double? = nil
    var generic: Double? = nil
    var makesSense: Double? = nil
    var checked: Int? = nil
    var samples: [StyleSample]? = nil
    var note: String? = nil

    enum CodingKeys: String, CodingKey {
        case soundsLikeYou = "sounds_like_you", generic, makesSense = "makes_sense", checked, samples, note
    }
}

struct StyleSample: Codable, Hashable {
    let suggested: String
    let real: String
}

struct AudienceProfile: Codable, Hashable {
    var turns: Int? = nil
    var acts: [String: Double]? = nil
    var tones: [String: Double]? = nil
    var medianChars: Double? = nil
    var lowercaseStart: Double? = nil
    var endsWithPunctuation: Double? = nil
    var emoji: Double? = nil
    var laughter: Double? = nil
    var swear: Double? = nil

    enum CodingKeys: String, CodingKey {
        case turns, acts, tones, medianChars = "median_chars", lowercaseStart = "lowercase_start",
             endsWithPunctuation = "ends_with_punctuation", emoji, laughter, swear
    }
}

/// A style as the server describes it; the list leaves out profile, preferences and examples.
struct Style: Codable, Hashable, Identifiable {
    let id: String
    var name: String
    var status: String? = nil  // building | ready | failed
    var stage: String? = nil  // uploading | parsing | needs_me | reading | profile | checking | training | ready | failed
    var progress: Double? = nil
    var error: String? = nil
    var source: String? = nil
    var counts: [String: Int]? = nil
    var scores: StyleScores? = nil
    var lora: String? = nil
    var adapterReady: Bool? = nil
    var needs: [String]? = nil
    var participants: [String]? = nil
    var chats: [String: String]? = nil  // chat name → audience
    var me: String? = nil
    var preferences: [String]? = nil
    var profile: [String: AudienceProfile]? = nil
    var examples: [String: [String]]? = nil

    enum CodingKeys: String, CodingKey {
        case id, name, status, stage, progress, error, source, counts, scores, lora, adapterReady = "adapter_ready",
             needs, participants, chats, me, preferences, profile, examples
    }

    var isReady: Bool { status == "ready" }
    var isBuilding: Bool { status == "building" || stage == "training" }
}

struct StyleList: Codable { let styles: [Style] }

/// One file to build a style from: a chat export, a screenshot or a frame of a screen recording.
struct Upload {
    let name: String
    let data: Data
    let mimeType: String
}

// MARK: - Chat

enum ChatMode: String, CaseIterable, Identifiable {
    case write, rewrite, reply

    var id: String { rawValue }
    var label: String { rawValue.capitalized }
}

struct ChatTurn: Codable, Hashable {
    var answer: String
    var feedback: String = ""
}

struct ChatAnswer: Codable, Hashable {
    let text: String
    var parts: [String]? = nil
    var alternatives: [String]? = nil
    var audience: String? = nil
    var audiences: [String]? = nil
    var learned: String? = nil
}

struct FeedbackResult: Codable { var learned: String? = nil }

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
    private static var style: String { SharedStore.styleID }

    /// instruction: optional "politely decline, I'm busy" or extra context; audience: nil = detect from the chat.
    static func reply(screenshot: Data, audience: Audience? = nil, instruction: String? = nil,
                      format: ReplyFormat = .message) async throws -> ReplyResponse {
        var body: [String: String] = ["image": jpeg(screenshot).base64EncodedString(), "image_type": "image/jpeg",
                                      "style": style, "format": format.rawValue]
        body["audience"] = audience?.rawValue
        body["instruction"] = instruction?.trimmingCharacters(in: .whitespacesAndNewlines)
        return try await send("reply", json: body, timeout: 25)
    }

    /// Same replies (same meaning), written for another audience; skips reading the chat again.
    static func restyle(_ response: ReplyResponse, for audience: Audience) async throws -> ReplyResponse {
        struct Body: Encodable {
            let summary, situation, audience, style: String
            let options: [ReplyIdea]
        }
        let body = Body(summary: response.context.summary, situation: response.context.situation,
                        audience: audience.rawValue, style: style, options: response.options ?? [])
        return try await send("reply", body: try JSONEncoder().encode(body), contentType: "application/json", timeout: 20)
    }

    static func reply(messages: String, audience: Audience?, format: ReplyFormat = .message) async throws -> ReplyResponse {
        var body: [String: String] = ["messages": messages, "style": style, "format": format.rawValue]
        body["audience"] = audience?.rawValue
        return try await send("reply", json: body, timeout: 20)
    }

    static func rewrite(_ text: String, audience: Audience, format: ReplyFormat = .message) async throws -> StyledResponse {
        try await send("rewrite", json: ["text": text, "audience": audience.rawValue, "style": style,
                                         "format": format.rawValue], timeout: 20)
    }

    static func compose(_ instruction: String, audience: Audience, format: ReplyFormat = .message) async throws -> StyledResponse {
        try await send("compose", json: ["instruction": instruction, "audience": audience.rawValue, "style": style,
                                         "format": format.rawValue], timeout: 20)
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

    // MARK: Chat

    /// history: the answers so far with the user's feedback; feedback on the last one revises it.
    static func chat(mode: ChatMode, text: String, audience: Audience, format: ReplyFormat,
                     history: [ChatTurn] = []) async throws -> ChatAnswer {
        struct Body: Encodable {
            let mode, text, audience, format, style: String
            let history: [ChatTurn]
        }
        let body = Body(mode: mode.rawValue, text: text, audience: audience.rawValue, format: format.rawValue,
                        style: style, history: history)
        return try await send("chat", body: try JSONEncoder().encode(body), contentType: "application/json", timeout: 30)
    }

    /// The user liked an answer, or wrote their own version: it becomes an example of the style (and maybe a rule).
    static func feedback(answer: String, edited: String? = nil, liked: Bool = false, audience: Audience,
                         format: ReplyFormat) async throws -> FeedbackResult {
        struct Body: Encodable {
            let answer, audience, format, style: String
            let edited: String?
            let liked: Bool
        }
        let body = Body(answer: answer, audience: audience.rawValue, format: format.rawValue, style: style,
                        edited: edited, liked: liked)
        return try await send("feedback", body: try JSONEncoder().encode(body), contentType: "application/json", timeout: 30)
    }

    // MARK: Styles

    static func styles() async throws -> [Style] {
        let list: StyleList = try await send("styles", method: "GET", timeout: 20)
        return list.styles
    }

    static func style(_ id: String) async throws -> Style {
        try await send("styles/\(id)", method: "GET", timeout: 20)
    }

    static func createStyle(name: String, files: [Upload]) async throws -> Style {
        let boundary = "sayso-\(UUID().uuidString)"
        var body = Data()
        func field(_ header: String, _ content: Data) {
            body.append("--\(boundary)\r\n\(header)\r\n\r\n".data(using: .utf8)!)
            body.append(content)
            body.append("\r\n".data(using: .utf8)!)
        }
        field("Content-Disposition: form-data; name=\"name\"", Data(name.utf8))
        for file in files {
            let safe = file.name.replacingOccurrences(of: "\"", with: "")
            field("Content-Disposition: form-data; name=\"files\"; filename=\"\(safe)\"\r\nContent-Type: \(file.mimeType)", file.data)
        }
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        return try await send("styles", body: body, contentType: "multipart/form-data; boundary=\(boundary)", timeout: 300)
    }

    /// The answers to "Which one is you?" and each chat's audience, or a new name, or a learned rule to forget.
    static func updateStyle(_ id: String, name: String? = nil, me: String? = nil, chats: [String: String]? = nil,
                            removePreference: Int? = nil) async throws -> Style {
        struct Body: Encodable {
            let name, me: String?
            let chats: [String: String]?
            let removePreference: Int?
            enum CodingKeys: String, CodingKey { case name, me, chats, removePreference = "remove_preference" }
        }
        let body = Body(name: name, me: me, chats: chats, removePreference: removePreference)
        return try await send("styles/\(id)", method: "PATCH", body: try JSONEncoder().encode(body),
                              contentType: "application/json", timeout: 20)
    }

    static func deleteStyle(_ id: String) async throws {
        struct Deleted: Decodable { let deleted: String }
        let _: Deleted = try await send("styles/\(id)", method: "DELETE", timeout: 20)
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
        case 404, 409, 413, 422: throw SaySoError.invalid(detail(data) ?? "The request was rejected.")
        default: throw SaySoError.server(code)
        }
    }

    private static func detail(_ data: Data) -> String? {
        (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
    }

    /// Screenshots go up as JPEG, at most 1280 px on the long side: smaller upload, same text for Muse Spark.
    static func jpeg(_ data: Data) -> Data {
        guard let image = UIImage(data: data) else { return data }
        return jpeg(image) ?? data
    }

    static func jpeg(_ image: UIImage) -> Data? {
        let scale = min(1, 1280 / max(image.size.width, image.size.height))
        let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
        let resized = UIGraphicsImageRenderer(size: size).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        return resized.jpegData(compressionQuality: 0.75)
    }
}
