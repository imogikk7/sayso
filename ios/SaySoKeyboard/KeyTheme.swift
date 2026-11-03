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

/// Every size of the keyboard, matched to the stock iOS 26 keyboard. Portrait values were measured on an iPhone 17 Pro
/// (402 × 874 pt) from screenshots of the stock keyboard (with its suggestion bar) in a Telegram chat:
///
///   keyboard top edge  y ≈ 546        suggestion bar  ≈ 52 tall          first key row  y ≈ 599
///   key height         ≈ 41.5         row pitch       ≈ 54 (gap ≈ 12)    space row bottom  y ≈ 802
///   English letter key ≈ 33 wide      key pitch       ≈ 39.8
///
/// So: strip 52, no gap under it, 4 rows of 42 pt keys 12 apart (204 pt), 3 under the space row (where SaySo's rows
/// already lined up with stock), total 259 pt. A 10-key row is 10 × 33 + 9 × 6.8 + 2 × 5.4 = 402, pitch 39.8.
/// Landscape was not measured: it keeps the earlier stock values.
struct KeyMetrics {
    /// The top strip (mode, audience, format, ✨): the stock suggestion bar, 52 pt.
    let strip: CGFloat
    /// From the strip to the top of the first key row: 0 (the bar's 52 pt already end at the first row, y 546 + 52 ≈ 599).
    let top: CGFloat
    /// Key cap height: 42 (stock ≈ 41.5).
    let keyHeight: CGFloat
    /// Between key rows: 12 (stock pitch ≈ 54).
    let rowGap: CGFloat
    /// Under the space row, above the system's globe / dictation bar: 3.
    let bottom: CGFloat
    /// Left and right of a full 10-key row: 5.4 (402 − 10 × 33 − 9 × 6.8 = 10.8).
    let side: CGFloat
    /// Between keys of a 10-key row (English, numbers, symbols), and in the bottom row: 6.8 (pitch 39.8 − key 33).
    let keyGap: CGFloat
    /// Between keys of an 11-key row (Russian): not measured; 6, a little tighter, as iOS does.
    let narrowKeyGap: CGFloat
    /// Shift, delete, 123 and the language key, in English letter-key widths: 1.36 (≈ 45 pt; not measured).
    let functionKey: CGFloat
    /// The return / send key: 88 (the earlier stock value; not measured on iOS 26).
    let returnKey: CGFloat

    /// The four key rows: 4 × 42 + 3 × 12 = 204.
    var rows: CGFloat { 4 * keyHeight + 3 * rowGap }
    /// Everything under the strip: 0 + 204 + 3 = 207.
    var keys: CGFloat { top + rows + bottom }
    /// The keyboard's height: 52 + 207 = 259 (stock: 546 → 805).
    var total: CGFloat { strip + keys }

    static let portrait = KeyMetrics(strip: 52, top: 0, keyHeight: 42, rowGap: 12, bottom: 3, side: 5.4,
                                     keyGap: 6.8, narrowKeyGap: 6, functionKey: 1.36, returnKey: 88)
    static let landscape = KeyMetrics(strip: 38, top: 4, keyHeight: 33, rowGap: 7, bottom: 3, side: 3,
                                      keyGap: 6, narrowKeyGap: 5, functionKey: 1.36, returnKey: 88)

    static func current(compactHeight: Bool) -> KeyMetrics {
        compactHeight ? .landscape : .portrait
    }

    /// The gap between keys of a row with this many columns.
    func gap(columns: Int) -> CGFloat {
        columns >= 11 ? narrowKeyGap : keyGap
    }

    /// The width of a letter key when the widest row has `columns` keys and the keyboard is `width` wide
    /// (portrait iPhone 17 Pro: 33 for English, 30.1 for Russian).
    func keyWidth(_ width: CGFloat, columns: Int) -> CGFloat {
        let columns = max(columns, 1)
        return max(0, (width - 2 * side - CGFloat(columns - 1) * gap(columns: columns)) / CGFloat(columns))
    }

    /// Shift, delete, 123, globe and language keys, the same whatever the language (from the 10-key letter width).
    func functionWidth(_ width: CGFloat) -> CGFloat {
        (functionKey * keyWidth(width, columns: 10)).rounded()
    }

    /// The return / send key.
    func returnWidth(_ width: CGFloat) -> CGFloat {
        max(returnKey, 2 * keyWidth(width, columns: 10))
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
            .transaction { $0.animation = nil }  // a press shows and clears at once, never fades
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
