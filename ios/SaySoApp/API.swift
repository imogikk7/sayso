import Foundation
import UIKit

struct ReplyContext: Codable, Hashable {
    let audience: String
    let situation: String
    let summary: String
}

struct ReplyOption: Codable, Hashable {
    let intent: String
    let text: String
}

struct ReplyResponse: Codable, Hashable {
    let context: ReplyContext
    let replies: [ReplyOption]
}

enum SaySoAPI {
    /// Uploads a screenshot to /reply. The image is sent as JPEG and never stored on the server.
    static func reply(screenshot: Data) async throws -> ReplyResponse {
        let body = UIImage(data: screenshot)?.jpegData(compressionQuality: 0.7) ?? screenshot
        var request = URLRequest(url: Secrets.apiURL.appending(path: "reply"))
        request.httpMethod = "POST"
        request.timeoutInterval = 25
        request.setValue("image/jpeg", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(Secrets.apiToken)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.upload(for: request, from: body)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(ReplyResponse.self, from: data)
    }
}
