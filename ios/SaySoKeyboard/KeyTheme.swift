import SwiftUI

/// The SaySo keyboard looks like the stock iOS keyboard: the system's own keyboard backdrop shows through (the
/// extension draws no background of its own), keys use the stock key colors, and the user's accent appears only on ✨
/// and on the strip's chips. The extension can't see the app's asset catalog or fonts, so everything is plain colors
/// and system fonts.
enum KeyTheme {
    static let key: CGFloat = 5  // key corner radius, as on the stock keyboard
    static let chip: CGFloat = 8
    static let card: CGFloat = 10

    /// The accent the user picked; "blue" is the SaySo blue rather than the system one.
    static func accent(_ accent: KeyboardAccent) -> Color {
        accent == .blue ? Color(red: 0.231, green: 0.533, blue: 0.957) : accent.color  // #3B88F4
    }

    /// A light sheen over the ✨ button's accent fill.
    static let gloss = LinearGradient(colors: [Color.white.opacity(0.25), Color.white.opacity(0)],
                                      startPoint: .top, endPoint: .bottom)

    // MARK: Keys (stock iOS colors)

    static func keyText(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.white : Color.black
    }

    /// Letter keys: white (light), #6B6B6B at 90% (dark). Pressed, they take the function-key color.
    static func letterFill(_ scheme: ColorScheme, pressed: Bool) -> Color {
        pressed ? functionColor(scheme) : letterColor(scheme)
    }

    /// Function keys (shift, delete, 123, language, return): #ACB1B9 (light), #464646 at 90% (dark).
    /// Pressed, they light up to the letter-key color, as iOS does.
    static func specialFill(_ scheme: ColorScheme, pressed: Bool) -> Color {
        pressed ? letterColor(scheme) : functionColor(scheme)
    }

    static func letterColor(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color(white: 0.42, opacity: 0.9) : Color.white
    }

    static func functionColor(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color(white: 0.275, opacity: 0.9) : Color(red: 0.675, green: 0.694, blue: 0.725)
    }

    /// The 1 pt shadow under every key: #898A8D (light), black at 35% (dark).
    static func keyShadow(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.black.opacity(0.35) : Color(red: 0.537, green: 0.541, blue: 0.553)
    }

    // MARK: Strip, chips and cards (neutral)

    static func chipFill(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.white.opacity(0.14) : Color.white.opacity(0.6)
    }

    /// Result cards and the panel's draft box: the letter-key color, so they sit on the backdrop like keys.
    static func cardFill(_ scheme: ColorScheme) -> Color {
        letterColor(scheme)
    }
}

/// Sizes of the stock iPhone keyboard. Portrait: a 44 pt strip over 216 pt of keys (key 43, rows 11 apart, 8 above
/// the first row, 3 under the last; 3 pt at the sides, 6 pt between keys, 5 on 11-key rows). Landscape: 38 + 160.
struct KeyMetrics {
    let strip: CGFloat
    let keys: CGFloat
    let keyHeight: CGFloat
    let rowGap: CGFloat
    let top: CGFloat
    let side: CGFloat = 3

    var total: CGFloat { strip + keys }

    static let portrait = KeyMetrics(strip: 44, keys: 216, keyHeight: 43, rowGap: 11, top: 8)
    static let landscape = KeyMetrics(strip: 38, keys: 160, keyHeight: 33, rowGap: 7, top: 4)

    static func current(compactHeight: Bool) -> KeyMetrics {
        compactHeight ? .landscape : .portrait
    }

    /// The gap between keys in a row: 6 pt, or 5 pt on rows of 11 keys (Russian), as iOS does.
    static func keyGap(columns: Int) -> CGFloat {
        columns >= 11 ? 5 : 6
    }
}

/// What a key looks like: a light letter cap, a darker function cap, or a blue cap (send, go, search), as on iOS.
enum KeyKind { case letter, special, accent }

/// A rounded key cap with the stock 1 pt shadow under it.
struct KeyCap<Content: View>: View {
    let kind: KeyKind
    let pressed: Bool
    let content: Content

    @Environment(\.colorScheme) private var scheme

    init(kind: KeyKind, pressed: Bool, @ViewBuilder content: () -> Content) {
        self.kind = kind
        self.pressed = pressed
        self.content = content()
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: KeyTheme.key, style: .continuous)
        content
            .foregroundStyle(kind == .accent && !pressed ? Color.white : KeyTheme.keyText(scheme))
            .background {
                Group {
                    switch kind {
                    case .letter:
                        shape.fill(KeyTheme.letterFill(scheme, pressed: pressed))
                    case .special:
                        shape.fill(KeyTheme.specialFill(scheme, pressed: pressed))
                    case .accent:
                        // The system blue of iOS's send / go / search key, not the SaySo accent.
                        shape.fill(pressed ? KeyTheme.letterFill(scheme, pressed: false) : Color(uiColor: .systemBlue))
                    }
                }
                .shadow(color: KeyTheme.keyShadow(scheme), radius: 0, x: 0, y: 1)
            }
            .contentShape(.rect)
    }
}

/// A full-width action in the panel ("Rewrite in my style"): a neutral key-like bar; only its ✨ icon is in the accent.
struct PanelActionStyle: ButtonStyle {
    @Environment(\.colorScheme) private var scheme

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(KeyTheme.keyText(scheme))
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity, minHeight: 40)
            .background {
                RoundedRectangle(cornerRadius: KeyTheme.chip, style: .continuous)
                    .fill(KeyTheme.letterFill(scheme, pressed: configuration.isPressed))
                    .shadow(color: KeyTheme.keyShadow(scheme), radius: 0, x: 0, y: 1)
            }
    }
}
