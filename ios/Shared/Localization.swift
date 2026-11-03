import Foundation
import ObjectiveC
import SwiftUI

/// The language of SaySo's own screens: the iPhone's, or English / Russian whatever the iPhone uses. Picked in the
/// app's Settings tab and kept in the App Group (key "appLanguage") so the keyboard follows it.
///
/// It applies at once: the app swaps the SwiftUI locale and rebuilds its screens, and `L()` reads strings from the
/// picked language's table. The system parts (Shortcuts actions, Siri, the microphone prompt) follow the app's
/// language in iOS (`AppleLanguages`), which the picker also sets; iOS reads that when SaySo starts.
enum AppLanguage: String, CaseIterable, Identifiable {
    case system, en, ru

    static let storageKey = "appLanguage"
    private static let supported = ["en", "ru"]

    var id: String { rawValue }

    /// English and Russian in their own words, so anyone can find theirs.
    var title: String {
        switch self {
        case .system: L("Same as iPhone")
        case .en: "English"
        case .ru: "Русский"
        }
    }

    static var current: AppLanguage {
        AppLanguage(rawValue: SharedStore.defaults.string(forKey: storageKey) ?? "") ?? .system
    }

    /// "en" or "ru": the picked one, or the best match for the iPhone's languages.
    var code: String {
        if self != .system { return rawValue }
        return Bundle.preferredLocalizations(from: Self.supported, forPreferences: Locale.preferredLanguages).first ?? "en"
    }

    /// The locale for SwiftUI's environment: this language, with the iPhone's region for dates and numbers.
    var locale: Locale {
        if let region = Locale.current.region?.identifier {
            return Locale(identifier: "\(code)_\(region)")
        }
        return Locale(identifier: code)
    }

    /// Saves the choice for the app and the keyboard, and tells iOS (Shortcuts, Siri) which language SaySo uses.
    /// Only the app calls this: "AppleLanguages" in its own defaults is the app's language in iOS.
    static func save(_ language: AppLanguage) {
        SharedStore.defaults.set(language.rawValue, forKey: storageKey)
        if language == .system {
            UserDefaults.standard.removeObject(forKey: "AppleLanguages")
        } else {
            UserDefaults.standard.set([language.rawValue], forKey: "AppleLanguages")
        }
    }

    // MARK: - Strings

    private static var bundles: [String: Bundle] = [:]
    private static let lock = NSLock()

    /// The table for the current language (the .lproj inside the app or the keyboard).
    static var bundle: Bundle {
        let code = current.code
        lock.lock()
        defer { lock.unlock() }
        if let bundle = bundles[code] { return bundle }
        let bundle = Bundle.main.path(forResource: code, ofType: "lproj").flatMap(Bundle.init(path:)) ?? Bundle.main
        bundles[code] = bundle
        return bundle
    }

    private static let swapped: Void = {
        _ = object_setClass(Bundle.main, LanguageBundle.self)
    }()

    /// Makes `Bundle.main` answer in the picked language too, for anything that reads strings from it directly.
    /// Call once at start (app, keyboard, intents); safe to call again.
    static func install() {
        _ = swapped
    }
}

/// `Bundle.main` after `AppLanguage.install()`: strings come from the picked language's table.
private final class LanguageBundle: Bundle {
    override func localizedString(forKey key: String, value: String?, table tableName: String?) -> String {
        let bundle = AppLanguage.bundle
        guard bundle !== self else { return super.localizedString(forKey: key, value: value, table: tableName) }
        return bundle.localizedString(forKey: key, value: value, table: tableName)
    }
}

/// A UI string from Localizable.xcstrings in the language picked in Settings. `Text("literal")` finds its own; this
/// is for strings kept in variables (labels, toasts, titles passed to cards).
func L(_ key: String) -> String {
    AppLanguage.bundle.localizedString(forKey: key, value: nil, table: nil)
}

/// A UI string with values, e.g. `Lf("Connected in %.1f s", seconds)`; Russian plural forms come from the catalog.
func Lf(_ key: String, _ arguments: CVarArg...) -> String {
    String(format: L(key), locale: Locale(identifier: AppLanguage.current.code), arguments: arguments)
}
