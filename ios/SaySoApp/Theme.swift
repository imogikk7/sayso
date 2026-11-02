import SwiftUI

/// The SaySo design system: sky-blue accent, navy, soft blue gradients; radius 4 keys, 8 chips, 12 cards, 16 bubbles.
enum Theme {
    static let navy = Color("Navy")
    static let glow = Color(red: 0.49, green: 0.71, blue: 0.98)
    static let card: CGFloat = 12
    static let bubble: CGFloat = 16
    static let chip: CGFloat = 8

    /// White with a blue glow in the corners, like the icon.
    static var backdrop: some View {
        ZStack {
            Color(.systemBackground)
            RadialGradient(colors: [glow.opacity(0.55), .clear], center: .topLeading, startRadius: 0, endRadius: 420)
            RadialGradient(colors: [glow.opacity(0.45), .clear], center: .bottomTrailing, startRadius: 0, endRadius: 460)
        }
        .ignoresSafeArea()
    }

    /// Big rounded display numbers (the design uses Archivo ExtraBold; SF's heavy expanded width is the closest built-in).
    static func display(_ size: CGFloat) -> Font {
        .system(size: size, weight: .heavy).width(.expanded)
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
            .background(Color.accentColor.opacity(configuration.isPressed ? 0.8 : 1), in: .capsule)
    }
}

/// Splash: the logo on the soft gradient, then onboarding the first time.
struct SplashView: View {
    var body: some View {
        ZStack {
            Theme.backdrop
            VStack(spacing: 18) {
                Image("Logo").resizable().scaledToFit().frame(width: 230)
                Text("Your writing. Our match.").font(.footnote).foregroundStyle(.secondary)
            }
        }
    }
}

struct OnboardingView: View {
    let onDone: () -> Void
    @State private var page = 0

    private let pages: [(icon: String, title: String, text: String)] = [
        ("bubble.left.and.text.bubble.right", "See how much you sound like you.",
         "SaySo learns from your own messages and shows how close its writing is to yours."),
        ("keyboard", "Your style, right in your chat.",
         "Type with SaySo's keyboard, tap ✨, or double-tap the back of your iPhone on any chat."),
    ]

    var body: some View {
        ZStack {
            Theme.backdrop
            VStack(spacing: 24) {
                HStack {
                    Spacer()
                    Button("Skip", action: onDone).font(.subheadline).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: pages[page].icon)
                    .font(.system(size: 72, weight: .light))
                    .foregroundStyle(Color.accentColor)
                    .symbolEffect(.bounce, value: page)
                VStack(alignment: .leading, spacing: 12) {
                    Text(pages[page].title).font(.system(size: 30, weight: .bold))
                    Text(pages[page].text).font(.body).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                HStack(spacing: 8) {
                    ForEach(pages.indices, id: \.self) { i in
                        Circle().fill(i == page ? Color.accentColor : Color.secondary.opacity(0.3)).frame(width: 8, height: 8)
                    }
                }
                Spacer()
                Button(page == pages.count - 1 ? "Get started" : "Continue") {
                    if page < pages.count - 1 { withAnimation { page += 1 } } else { onDone() }
                }
                .buttonStyle(PrimaryButtonStyle())
            }
            .padding(24)
        }
    }
}
