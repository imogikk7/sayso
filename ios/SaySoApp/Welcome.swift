import SwiftUI

// The welcome flow: three illustrated onboarding pages (the splash with the pen-written logo is SplashView).
// Everything is drawn with SwiftUI (no bitmaps). Numbers on page 3 are the committed self-check of the main style:
// form 0.93 with SaySo (eval/results/style_gain_open.json) vs 0.69 for generic Muse Spark (eval/results/style_gain.json).

/// Three illustrated pages: your words vs generic AI, ✨ on the keyboard, the self-check score.
struct WelcomeOnboarding: View {
    let onDone: () -> Void
    @State private var page = 0

    private let pages: [(title: String, text: String)] = [
        ("Your words. Not AI words.",
         "SaySo learns how you write (length, lowercase, punctuation, slang) and answers the way you'd say it."),
        ("Tap ✨ in any chat.",
         "Type with the SaySo keyboard and tap ✨, or double-tap the back of your iPhone on a chat for three replies."),
        ("See how close it gets.",
         "Each style checks itself on messages it hasn't seen and shows how much the result sounds like you."),
    ]

    var body: some View {
        ZStack {
            Theme.backdrop
            VStack(spacing: 18) {
                HStack {
                    LogoView().frame(width: 84)
                    Spacer()
                    Button("Skip", action: onDone)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.secondary)
                }
                TabView(selection: $page) {
                    ForEach(pages.indices, id: \.self) { index in
                        OnboardingPage(title: pages[index].title, text: pages[index].text) {
                            illustration(index)
                        }
                        .tag(index)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                PageDots(count: pages.count, current: page)
                Button {
                    if page < pages.count - 1 { withAnimation(.snappy) { page += 1 } } else { onDone() }
                } label: {
                    HStack(spacing: 8) {
                        Text(page == pages.count - 1 ? "Get started" : "Continue")
                        Image(systemName: page == pages.count - 1 ? "sparkles" : "arrow.right")
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 12)
        }
    }

    @ViewBuilder
    private func illustration(_ index: Int) -> some View {
        switch index {
        case 0: VersusIllustration(active: page == 0)
        case 1: KeyboardIllustration(active: page == 1)
        default: ScoreIllustration(active: page == 2)
        }
    }
}

/// One onboarding page: the illustration on a glass panel, a big headline and a line of text.
private struct OnboardingPage<Illustration: View>: View {
    let title: String
    let text: String
    let illustration: Illustration

    init(title: String, text: String, @ViewBuilder illustration: () -> Illustration) {
        self.title = title
        self.text = text
        self.illustration = illustration()
    }

    var body: some View {
        VStack(spacing: 26) {
            illustration
                .frame(maxWidth: .infinity)
                .frame(height: 280)
                .background(.regularMaterial, in: .rect(cornerRadius: 28, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 28, style: .continuous).stroke(Color.primary.opacity(0.06)))
                .shadow(color: Theme.glow.opacity(0.25), radius: 20, y: 8)
            VStack(alignment: .leading, spacing: 12) {
                Text(title)
                    .font(Theme.title(28))
                    .foregroundStyle(.primary)
                    .minimumScaleFactor(0.75)
                    .fixedSize(horizontal: false, vertical: true)
                Text(text)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Spacer(minLength: 0)
        }
        .padding(.top, 8)
        .padding(.horizontal, 2)
    }
}

/// The active page is a long gradient capsule, the others small dots.
private struct PageDots: View {
    let count: Int
    let current: Int

    var body: some View {
        HStack(spacing: 7) {
            ForEach(0..<count, id: \.self) { index in
                Capsule()
                    .fill(index == current ? AnyShapeStyle(Theme.accentGradient) : AnyShapeStyle(Color.secondary.opacity(0.25)))
                    .frame(width: index == current ? 24 : 8, height: 8)
            }
        }
        .animation(.snappy, value: current)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Page \(current + 1) of \(count)")
    }
}

// MARK: - Page 1: generic AI vs you

private struct VersusIllustration: View {
    let active: Bool
    @State private var struck = false
    @State private var yours = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Their message (made up).
            Text("so how was the trip??")
                .font(.subheadline)
                .padding(.horizontal, 13).padding(.vertical, 8)
                .background(Color(.secondarySystemFill), in: .rect(cornerRadius: Theme.bubble, style: .continuous))
            VStack(alignment: .trailing, spacing: 4) {
                tag("Generic AI", systemImage: "xmark.circle.fill", color: .red)
                Text("The trip was truly wonderful! I hope you are doing well. Let me know if you'd like to hear more.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 13).padding(.vertical, 8)
                    .background(Color(.tertiarySystemFill), in: .rect(cornerRadius: Theme.bubble, style: .continuous))
                    .overlay {
                        Capsule()
                            .fill(Color.red.opacity(0.75))
                            .frame(height: 2.5)
                            .padding(.horizontal, 8)
                            .scaleEffect(x: struck ? 1 : 0, anchor: .leading)
                            .rotationEffect(.degrees(-4))
                    }
                    .opacity(struck ? 0.65 : 1)
            }
            .frame(maxWidth: .infinity, alignment: .trailing)
            .padding(.leading, 34)
            VStack(alignment: .trailing, spacing: 4) {
                tag("You, with SaySo", systemImage: "checkmark.seal.fill", color: .accentColor)
                Text("honestly best week ever 😭 tell u everything tmrw")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 13).padding(.vertical, 8)
                    .background(Theme.accentGradient,
                                in: UnevenRoundedRectangle(topLeadingRadius: Theme.bubble, bottomLeadingRadius: Theme.bubble,
                                                           bottomTrailingRadius: 4, topTrailingRadius: Theme.bubble,
                                                           style: .continuous))
                    .shadow(color: Color.accentColor.opacity(0.4), radius: 10, y: 4)
            }
            .frame(maxWidth: .infinity, alignment: .trailing)
            .padding(.leading, 34)
            .scaleEffect(yours ? 1 : 0.85, anchor: .bottomTrailing)
            .opacity(yours ? 1 : 0)
        }
        .padding(18)
        .onChange(of: active, initial: true) { _, isActive in
            if isActive {
                struck = false
                yours = false
                withAnimation(.easeOut(duration: 0.45).delay(0.35)) { struck = true }
                withAnimation(.spring(duration: 0.55, bounce: 0.35).delay(0.75)) { yours = true }
            }
        }
    }

    private func tag(_ title: String, systemImage: String, color: Color) -> some View {
        Label(title, systemImage: systemImage)
            .font(.caption2.weight(.semibold))
            .foregroundStyle(color)
    }
}

// MARK: - Page 2: the keyboard with a glowing ✨

private struct KeyboardIllustration: View {
    let active: Bool
    @State private var pulse = false

    private let rows = [10, 9, 7]

    var body: some View {
        VStack(spacing: 12) {
            // The message field with a draft in it.
            HStack(spacing: 6) {
                Text("running late sorry")
                    .font(.subheadline)
                Capsule().fill(Color.accentColor).frame(width: 2, height: 18)
                    .opacity(pulse ? 1 : 0.2)
                Spacer(minLength: 0)
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title3)
                    .foregroundStyle(Color.accentColor)
            }
            .padding(.leading, 14).padding(.trailing, 6).padding(.vertical, 6)
            .background(Color(.secondarySystemGroupedBackground), in: .capsule)
            .overlay(Capsule().stroke(Color.primary.opacity(0.08)))

            VStack(spacing: 7) {
                HStack(spacing: 5) {
                    miniChip("Friends", systemImage: "person.2")
                    miniChip("Message", systemImage: "bubble.left")
                    Spacer(minLength: 0)
                    sparkleKey
                }
                .padding(.bottom, 3)
                ForEach(rows.indices, id: \.self) { row in
                    HStack(spacing: 4) {
                        ForEach(0..<rows[row], id: \.self) { _ in key }
                    }
                    .padding(.horizontal, CGFloat(10 - rows[row]) * 6)
                }
                HStack(spacing: 4) {
                    key.frame(width: 34)
                    key
                    key.frame(width: 50)
                }
            }
            .padding(10)
            .background {
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(LinearGradient(colors: [Theme.glow.opacity(0.12), Theme.glow.opacity(0.32)],
                                         startPoint: .top, endPoint: .bottom))
            }
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(Color.primary.opacity(0.06)))
        }
        .padding(18)
        .onChange(of: active, initial: true) { _, isActive in
            if isActive {
                pulse = false
                withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { pulse = true }
            }
        }
    }

    private var key: some View {
        RoundedRectangle(cornerRadius: 4, style: .continuous)
            .fill(Color(.secondarySystemGroupedBackground))
            .frame(height: 24)
            .shadow(color: Theme.navy.opacity(0.18), radius: 0, y: 1)
    }

    private var sparkleKey: some View {
        Image(systemName: "sparkles")
            .font(.subheadline.weight(.bold))
            .foregroundStyle(.white)
            .frame(width: 46, height: 26)
            .background(Theme.accentGradient, in: .capsule)
            .shadow(color: Color.accentColor.opacity(pulse ? 0.9 : 0.3), radius: pulse ? 14 : 4)
            .scaleEffect(pulse ? 1.1 : 1)
    }

    private func miniChip(_ title: String, systemImage: String) -> some View {
        Label(title, systemImage: systemImage)
            .font(.caption2.weight(.semibold))
            .lineLimit(1)
            .padding(.horizontal, 8)
            .frame(height: 24)
            .background(Color(.secondarySystemGroupedBackground), in: .capsule)
    }
}

// MARK: - Page 3: the self-check score

private struct ScoreIllustration: View {
    let active: Bool
    @State private var progress: Double = 0

    private let sayso = 0.93
    private let generic = 0.69

    var body: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(RadialGradient(colors: [Theme.glow.opacity(0.35), Theme.glow.opacity(0)],
                                         center: .center, startRadius: 0, endRadius: 110))
                    .frame(width: 210, height: 210)
                    .opacity(progress)
                Circle().stroke(Color.accentColor.opacity(0.14), lineWidth: 14)
                    .frame(width: 160, height: 160)  // the glow behind is wider; the ring keeps its own size
                Circle()
                    .trim(from: 0, to: CGFloat(progress * sayso))
                    .stroke(Theme.stroke, style: StrokeStyle(lineWidth: 14, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .shadow(color: Color.accentColor.opacity(0.45), radius: 8)
                    .frame(width: 160, height: 160)
                VStack(spacing: 2) {
                    Text("\(Int((progress * sayso * 100).rounded()))%")
                        .font(Theme.display(40))
                        .foregroundStyle(Theme.navy)
                        .contentTransition(.numericText(value: progress))
                    Text("sounds like you")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
            }
            .frame(width: 160, height: 160)
            VStack(spacing: 6) {
                bar("SaySo", value: sayso, fill: AnyShapeStyle(Theme.accentGradient))
                bar("Generic AI", value: generic, fill: AnyShapeStyle(Color.secondary.opacity(0.45)))
            }
            .padding(.horizontal, 6)
        }
        .padding(18)
        .onChange(of: active, initial: true) { _, isActive in
            if isActive {
                progress = 0
                withAnimation(.easeOut(duration: 1.3).delay(0.25)) { progress = 1 }
            }
        }
    }

    private func bar(_ title: String, value: Double, fill: AnyShapeStyle) -> some View {
        HStack(spacing: 8) {
            Text(title)
                .font(.caption.weight(.semibold))
                .frame(width: 70, alignment: .leading)
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.primary.opacity(0.06))
                    Capsule().fill(fill).frame(width: proxy.size.width * CGFloat(value * progress))
                }
            }
            .frame(height: 8)
            Text("\(Int(value * 100))%")
                .font(.caption.monospacedDigit().weight(.semibold))
                .foregroundStyle(.secondary)
                .frame(width: 34, alignment: .trailing)
        }
    }
}
