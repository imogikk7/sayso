import SwiftUI

/// The SaySo look inside the keyboard. The extension can't see the app's asset catalog or fonts, and has a small memory
/// budget, so everything here is plain colors, gradients, shapes and system fonts.
enum KeyTheme {
    static let brandBlue = Color(red: 0.231, green: 0.533, blue: 0.957)  // #3B88F4
    static let navy = Color(red: 0.043, green: 0.165, blue: 0.357)  // #0B2A5B
    static let glow = Color(red: 0.49, green: 0.71, blue: 0.98)

    static let key: CGFloat = 5
    static let chip: CGFloat = 8
    static let card: CGFloat = 12
    static let bubble: CGFloat = 16

    /// The accent the user picked; "blue" is the SaySo blue rather than the system one.
    static func accent(_ accent: KeyboardAccent) -> Color {
        accent == .blue ? brandBlue : accent.color
    }

    /// A light sheen over a solid accent fill, so buttons and bubbles look lit from above (works for every accent).
    static let gloss = LinearGradient(colors: [Color.white.opacity(0.28), Color.white.opacity(0)],
                                      startPoint: .top, endPoint: .bottom)

    // MARK: Keys

    static func keyText(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.white : Color(red: 0.05, green: 0.09, blue: 0.18)
    }

    static func letterFill(_ scheme: ColorScheme, pressed: Bool) -> LinearGradient {
        let colors: [Color]
        if scheme == .dark {
            colors = pressed
                ? [Color(red: 0.30, green: 0.40, blue: 0.58), Color(red: 0.26, green: 0.35, blue: 0.52)]
                : [Color(red: 0.22, green: 0.27, blue: 0.37), Color(red: 0.18, green: 0.22, blue: 0.31)]
        } else {
            colors = pressed
                ? [Color(red: 0.82, green: 0.89, blue: 0.99), Color(red: 0.77, green: 0.86, blue: 0.98)]
                : [Color.white, Color(red: 0.965, green: 0.977, blue: 1.0)]
        }
        return LinearGradient(colors: colors, startPoint: .top, endPoint: .bottom)
    }

    static func specialFill(_ scheme: ColorScheme, pressed: Bool) -> LinearGradient {
        let colors: [Color]
        if scheme == .dark {
            colors = pressed
                ? [Color(red: 0.22, green: 0.27, blue: 0.37), Color(red: 0.18, green: 0.22, blue: 0.31)]
                : [Color(red: 0.12, green: 0.16, blue: 0.25), Color(red: 0.10, green: 0.13, blue: 0.21)]
        } else {
            colors = pressed
                ? [Color.white, Color(red: 0.965, green: 0.977, blue: 1.0)]
                : [Color(red: 0.81, green: 0.87, blue: 0.95), Color(red: 0.76, green: 0.83, blue: 0.93)]
        }
        return LinearGradient(colors: colors, startPoint: .top, endPoint: .bottom)
    }

    static func keyEdge(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.white.opacity(0.08) : navy.opacity(0.06)
    }

    static func keyShadow(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.black.opacity(0.55) : navy.opacity(0.22)
    }

    // MARK: Strip, chips and cards

    static func chipFill(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.white.opacity(0.10) : Color.white.opacity(0.92)
    }

    static func chipEdge(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.white.opacity(0.12) : navy.opacity(0.08)
    }

    static func softShadow(_ scheme: ColorScheme) -> Color {
        scheme == .dark ? Color.black.opacity(0.35) : navy.opacity(0.10)
    }
}

/// The keyboard's background: white into sky blue with a glow in the corner (light), deep navy (dark).
struct KeyBackdrop: View {
    let accent: Color
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        ZStack {
            if scheme == .dark {
                LinearGradient(colors: [Color(red: 0.06, green: 0.10, blue: 0.19), Color(red: 0.02, green: 0.05, blue: 0.11)],
                               startPoint: .top, endPoint: .bottom)
                RadialGradient(colors: [accent.opacity(0.22), accent.opacity(0)],
                               center: .topTrailing, startRadius: 0, endRadius: 260)
            } else {
                LinearGradient(colors: [Color(red: 0.96, green: 0.975, blue: 1.0), Color(red: 0.86, green: 0.915, blue: 0.985)],
                               startPoint: .top, endPoint: .bottom)
                RadialGradient(colors: [KeyTheme.glow.opacity(0.45), KeyTheme.glow.opacity(0)],
                               center: .topTrailing, startRadius: 0, endRadius: 260)
                RadialGradient(colors: [Color.white.opacity(0.7), Color.white.opacity(0)],
                               center: .bottomLeading, startRadius: 0, endRadius: 220)
            }
        }
        .ignoresSafeArea()
    }
}

/// What a key looks like: a light letter cap, a darker special cap, or an accent cap (send, go, search).
enum KeyKind { case letter, special, accent }

/// A rounded key cap with a hairline edge and a crisp shadow under it.
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
            .foregroundStyle(kind == .accent ? Color.white : KeyTheme.keyText(scheme))
            .background {
                ZStack {
                    switch kind {
                    case .letter:
                        shape.fill(KeyTheme.letterFill(scheme, pressed: pressed))
                    case .special:
                        shape.fill(KeyTheme.specialFill(scheme, pressed: pressed))
                    case .accent:
                        shape.fill(.tint)
                        shape.fill(KeyTheme.gloss)
                        if pressed { shape.fill(Color.black.opacity(0.15)) }
                    }
                    shape.strokeBorder(KeyTheme.keyEdge(scheme), lineWidth: 0.5)
                }
                .shadow(color: KeyTheme.keyShadow(scheme), radius: 0, x: 0, y: 1)
            }
            .contentShape(.rect)
    }
}

/// The main action in the panel: a full-width accent capsule with a soft glow.
struct GlowButtonStyle: ButtonStyle {
    let accent: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(Color.white)
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity, minHeight: 38)
            .background {
                ZStack {
                    Capsule().fill(accent)
                    Capsule().fill(KeyTheme.gloss)
                }
            }
            .shadow(color: accent.opacity(configuration.isPressed ? 0.2 : 0.4), radius: 8, x: 0, y: 3)
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}
