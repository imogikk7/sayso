import Foundation
import SwiftUI

/// How a suggestion is written: one chat message, a series sent one by one, an official message or an email.
enum ReplyFormat: String, CaseIterable, Identifiable, Codable {
    case message, series, official, email

    var id: String { rawValue }
    var label: String {
        switch self {
        case .message: "Message"
        case .series: "Series"
        case .official: "Official"
        case .email: "Email"
        }
    }
    var systemImage: String {
        switch self {
        case .message: "bubble.left"
        case .series: "square.stack"
        case .official: "briefcase"
        case .email: "envelope"
        }
    }
}

enum KeyboardAccent: String, CaseIterable, Identifiable, Codable {
    case blue, indigo, teal, orange, pink

    var id: String { rawValue }
    var color: Color {
        switch self {
        case .blue: .blue
        case .indigo: .indigo
        case .teal: .teal
        case .orange: .orange
        case .pink: .pink
        }
    }
}

/// What the user set up in the app's Keyboard tab; the keyboard reads it on every open.
struct KeyboardSettings: Codable, Equatable {
    var audiences: [Audience] = Audience.allCases
    var formats: [ReplyFormat] = ReplyFormat.allCases
    var startsWithLetters = true
    var variants = 3
    var haptics = true
    var accent: KeyboardAccent = .blue
}

/// Shared between the app and the keyboard through the App Group (the keyboard needs Full Access to read it).
enum SharedStore {
    static let defaults = UserDefaults(suiteName: "group.com.imogikk7.sayso") ?? .standard

    /// The style the keyboard and the Back Tap shortcut write in.
    static var styleID: String {
        get { defaults.string(forKey: "styleID") ?? "main" }
        set { defaults.set(newValue, forKey: "styleID") }
    }

    static var styleName: String {
        get { defaults.string(forKey: "styleName") ?? "Me · Telegram" }
        set { defaults.set(newValue, forKey: "styleName") }
    }

    static var keyboard: KeyboardSettings {
        get { defaults.data(forKey: "keyboard").flatMap { try? JSONDecoder().decode(KeyboardSettings.self, from: $0) } ?? KeyboardSettings() }
        set { defaults.set(try? JSONEncoder().encode(newValue), forKey: "keyboard") }
    }

    /// Written by the keyboard when it opens with Full Access: the Setup checklist reads it.
    static var keyboardOpenedWithFullAccess: Date? {
        get { defaults.object(forKey: "keyboardOpened") as? Date }
        set { defaults.set(newValue, forKey: "keyboardOpened") }
    }

    static var shortcutDone: Bool {
        get { defaults.bool(forKey: "shortcutDone") }
        set { defaults.set(newValue, forKey: "shortcutDone") }
    }
}
