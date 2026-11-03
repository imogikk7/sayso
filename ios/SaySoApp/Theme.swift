import CoreText
import SwiftUI

/// The SaySo design system: sky-blue accent, navy, soft blue gradients; radius 4 keys, 8 chips, 12 cards, 16 bubbles.
enum Theme {
    static let navy = Color("Navy")
    static let glow = Color(red: 0.49, green: 0.71, blue: 0.98)
    static let card: CGFloat = 12
    static let bubble: CGFloat = 16
    static let chip: CGFloat = 8
    /// The blue of the "So" brush stroke, deep at its tail and light at its end.
    static let stroke = LinearGradient(colors: [Color(red: 0.12, green: 0.37, blue: 0.84), glow],
                                       startPoint: .bottomLeading, endPoint: .topTrailing)
    static let accentGradient = LinearGradient(colors: [Color(red: 0.36, green: 0.62, blue: 1.0), Color.accentColor],
                                               startPoint: .topLeading, endPoint: .bottomTrailing)

    /// White with a blue glow in the corners, like the icon.
    static var backdrop: some View {
        ZStack {
            Color(.systemGroupedBackground)
            RadialGradient(colors: [glow.opacity(0.5), .clear], center: .topLeading, startRadius: 0, endRadius: 420)
            RadialGradient(colors: [glow.opacity(0.35), .clear], center: .bottomTrailing, startRadius: 0, endRadius: 460)
        }
        .ignoresSafeArea()
    }

    /// The brand font, Archivo (SIL Open Font License, Fonts/OFL.txt), bundled as three static cuts.
    static func registerFonts() {
        for name in ["Archivo-ExpandedBlack", "Archivo-ExpandedExtraBold", "Archivo-SemiBold"] {
            if let url = Bundle.main.url(forResource: name, withExtension: "ttf") {
                CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
            }
        }
    }

    /// Big numbers and short headlines: Archivo Expanded ExtraBold.
    static func display(_ size: CGFloat) -> Font { .custom("Archivo-ExpandedExtraBold", size: size, relativeTo: .largeTitle) }
    /// Screen titles: Archivo Expanded Black.
    static func title(_ size: CGFloat = 32) -> Font { .custom("Archivo-ExpandedBlack", size: size, relativeTo: .largeTitle) }
    /// Card titles and labels: Archivo SemiBold.
    static func label(_ size: CGFloat = 16) -> Font { .custom("Archivo-SemiBold", size: size, relativeTo: .headline) }
}

/// The SaySo wordmark, vector: "SAY" in the text color (black in light mode, white in dark), "So" in the blue gradient.
struct LogoView: View {
    var body: some View {
        ZStack {
            Image("LogoSay").resizable().scaledToFit().foregroundStyle(.primary)
            Image("LogoSo").resizable().scaledToFit().foregroundStyle(Theme.stroke)
        }
        .accessibilityLabel("SaySo")
    }
}

/// The wordmark in one line, for headers: "SAY", then the handwritten "So" starting at the Y and running on to the
/// right, its o on SAY's baseline and its swash under the Y. The same two vector assets as LogoView, both drawn in
/// the logo's 847 × 430 units: So is scaled 1.1× and moved 500 right and 133 up (SAY's baseline is at y 198, the
/// o's bottom at 301). Size it by height: about 4.4 times as wide as it is tall.
struct LogoHorizontal: View {
    private static let art = CGSize(width: 847, height: 430)
    private static let soScale: CGFloat = 1.1
    private static let soOffset = CGSize(width: 500, height: -133)
    /// The ink of the whole line: SAY's S starts at x 0 and its top at y 0; the flourish ends at x 1423, the swash at y 325.
    private static let bounds = CGSize(width: 1424, height: 325)

    var body: some View {
        GeometryReader { geometry in
            let unit = geometry.size.width / Self.bounds.width
            ZStack(alignment: .topLeading) {
                ZStack {
                    Image("LogoSay").resizable()
                    SayGapFill()
                }
                .foregroundStyle(.primary)
                .frame(width: Self.art.width * unit, height: Self.art.height * unit)
                Image("LogoSo").resizable()
                    .foregroundStyle(Theme.stroke)
                    .frame(width: Self.art.width * Self.soScale * unit, height: Self.art.height * Self.soScale * unit)
                    .offset(x: Self.soOffset.width * unit, y: Self.soOffset.height * unit)
            }
            .frame(width: geometry.size.width, height: geometry.size.height, alignment: .topLeading)
        }
        .aspectRatio(Self.bounds.width / Self.bounds.height, contentMode: .fit)
        .accessibilityElement()
        .accessibilityLabel("SaySo")
    }
}

/// LogoSay has gaps cut where So crosses it in the stacked logo (the bottom of the A, the foot of the Y's stem).
/// With So beside it they would show, so these shapes fill them back in (847 × 430 logo units, the A's legs follow
/// its outer edges, the lower opening between them stays).
struct SayGapFill: Shape {
    private static let polygons: [[(x: CGFloat, y: CGFloat)]] = [
        [(308.8, 148), (567.6, 148), (576, 162), (300.6, 162)],  // A: the bottom of the crossbar
        [(300.6, 162), (382, 162), (361, 198), (279.5, 198)],  // A: left leg
        [(499.5, 162), (576, 162), (597.6, 198), (501, 198)],  // A: right leg
        [(620.2, 140), (698.4, 140), (698.4, 198), (620.2, 198)],  // Y: the foot of the stem
    ]

    func path(in rect: CGRect) -> Path {
        let sx = rect.width / 847, sy = rect.height / 430
        var path = Path()
        for polygon in Self.polygons {
            path.addLines(polygon.map { point in CGPoint(x: rect.minX + point.x * sx, y: rect.minY + point.y * sy) })
            path.closeSubpath()
        }
        return path
    }
}

/// A rounded card on the backdrop: frosted, with a hairline edge, readable in light and dark mode.
struct GlassCard: ViewModifier {
    var radius: CGFloat = Theme.card + 4
    var padding: CGFloat = 14

    func body(content: Content) -> some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.regularMaterial, in: .rect(cornerRadius: radius))
            .overlay(RoundedRectangle(cornerRadius: radius).stroke(Color.primary.opacity(0.06)))
            .shadow(color: Theme.glow.opacity(0.18), radius: 14, y: 6)
    }
}

extension View {
    func glassCard(radius: CGFloat = Theme.card + 4, padding: CGFloat = 14) -> some View {
        modifier(GlassCard(radius: radius, padding: padding))
    }
}

/// A pill to pick one of a few options (mode, kind, audience).
struct Pill: View {
    let title: String
    var icon: String? = nil
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 5) {
                if let icon { Image(systemName: icon).font(.caption.weight(.semibold)) }
                Text(title).font(.subheadline.weight(selected ? .semibold : .regular))
            }
            .padding(.horizontal, 12).padding(.vertical, 7)
            .foregroundStyle(selected ? Color.white : Color.primary)
            .background {
                if selected { Capsule().fill(Theme.accentGradient) } else { Capsule().fill(.regularMaterial) }
            }
            .overlay(Capsule().stroke(Color.primary.opacity(selected ? 0 : 0.08)))
        }
        .buttonStyle(.plain)
        .animation(.snappy(duration: 0.2), value: selected)
    }
}

/// A small section title over a group of cards.
struct SectionTitle: View {
    let text: String
    var body: some View {
        Text(text).font(Theme.display(17)).foregroundStyle(.primary)
    }
}

/// "Sounds like you 78% (generic AI 41%)" with a small rising line, as in the design.
struct ScoreCard: View {
    let title: String
    let value: String
    var detail: String? = nil
    var trend = true

    var body: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.subheadline.weight(.medium))
                Text(value).font(Theme.display(32)).foregroundStyle(Theme.navy)
                if let detail { Text(detail).font(.caption).foregroundStyle(.secondary) }
            }
            Spacer()
            if trend {
                Sparkline().stroke(Color.accentColor, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                    .frame(width: 80, height: 34)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.accentColor.opacity(0.08), in: .rect(cornerRadius: Theme.card))
        .overlay(RoundedRectangle(cornerRadius: Theme.card).stroke(Color.accentColor.opacity(0.15)))
    }
}

struct Sparkline: Shape {
    func path(in rect: CGRect) -> Path {
        let points: [CGFloat] = [0.75, 0.55, 0.7, 0.4, 0.5, 0.25, 0.3, 0.05]
        var path = Path()
        for (i, y) in points.enumerated() {
            let point = CGPoint(x: rect.minX + rect.width * CGFloat(i) / CGFloat(points.count - 1), y: rect.minY + rect.height * y)
            i == 0 ? path.move(to: point) : path.addLine(to: point)
        }
        return path
    }
}

/// The self-check result as a ring: "96% Sounds like you (generic AI 41%)".
struct ScoreRing: View {
    let value: Double
    var caption = "Sounds like you"
    var detail: String? = nil

    var body: some View {
        VStack(spacing: 10) {
            ZStack {
                Circle().stroke(Color.accentColor.opacity(0.15), lineWidth: 12)
                Circle().trim(from: 0, to: max(0, min(value, 1)))
                    .stroke(Color.accentColor, style: StrokeStyle(lineWidth: 12, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text("\(Int(value * 100))%").font(Theme.display(40)).foregroundStyle(Theme.navy)
            }
            .frame(width: 170, height: 170)
            Text(caption).font(.headline)
            if let detail { Text(detail).font(.caption).foregroundStyle(.secondary) }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
    }
}

/// The primary button of the design: full width, accent, rounded.
struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 50)
            .background(Theme.accentGradient, in: .capsule)
            .opacity(configuration.isPressed ? 0.8 : 1)
            .shadow(color: Color.accentColor.opacity(0.35), radius: 10, y: 4)
    }
}

/// Splash: "SAY" lands, then "So" is drawn across like the brush stroke, on a breathing blue glow.
struct SplashView: View {
    @State private var glow = false

    var body: some View {
        ZStack {
            Theme.backdrop
            Circle()
                .fill(RadialGradient(colors: [Theme.glow.opacity(0.55), .clear], center: .center, startRadius: 0, endRadius: 220))
                .frame(width: 440, height: 440)
                .scaleEffect(glow ? 1.15 : 0.8)
                .opacity(glow ? 1 : 0.4)
            AnimatedLogo().frame(width: 250)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.4).repeatForever(autoreverses: true)) { glow = true }
        }
    }
}

/// The logo, written in: "SAY" is there, then a pen writes "So" stroke by stroke (the S, then the o and the flourish).
struct AnimatedLogo: View {
    @State private var shown = false
    @State private var written: CGFloat = 0

    var body: some View {
        ZStack {
            Image("LogoSay").resizable().scaledToFit().foregroundStyle(.primary)
                .opacity(shown ? 1 : 0)
            Image("LogoSo").resizable().scaledToFit().foregroundStyle(Theme.stroke)
                .mask(SoPenMask(progress: written))
        }
        .aspectRatio(SoPen.size.width / SoPen.size.height, contentMode: .fit)
        .accessibilityLabel("SaySo")
        .onAppear {
            withAnimation(.easeOut(duration: 0.3)) { shown = true }
            withAnimation(.timingCurve(0.45, 0.05, 0.35, 1, duration: 1.3).delay(0.35)) { written = 1 }
        }
    }
}
