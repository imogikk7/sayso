import Foundation

/// Letter layouts of the SaySo keyboard. Kazakh letters (and ё, ъ) come from a long press on their Russian base.
enum KeyboardLanguage: String {
    case russian, english

    var rows: [[String]] {
        switch self {
        case .russian: [Array("йцукенгшщзх"), Array("фывапролджэ"), Array("ячсмитьбю")].map { $0.map(String.init) }
        case .english: [Array("qwertyuiop"), Array("asdfghjkl"), Array("zxcvbnm")].map { $0.map(String.init) }
        }
    }

    var spaceLabel: String { self == .russian ? "пробел" : "space" }
    var other: KeyboardLanguage { self == .russian ? .english : .russian }
    var switchLabel: String { self == .russian ? "EN" : "RU" }
}

enum KeyPage {
    case letters, numbers, symbols

    var rows: [[String]] {
        switch self {
        case .letters: []
        case .numbers: [Array("1234567890"), ["-", "/", ":", ";", "(", ")", "₸", "&", "@", "\""], [".", ",", "?", "!", "'"]]
            .map { $0.map { String($0) } }
        case .symbols: [["[", "]", "{", "}", "#", "%", "^", "*", "+", "="], ["_", "\\", "|", "~", "<", ">", "$", "€", "₽", "•"],
                        [".", ",", "?", "!", "'"]]
        }
    }
}

/// Long press on a key types its alternate.
let alternates: [String: String] = [
    "е": "ё", "ь": "ъ", "а": "ә", "г": "ғ", "к": "қ", "н": "ң", "о": "ө", "у": "ұ", "х": "һ", "и": "і", "ю": "ү",
]
